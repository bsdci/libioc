# Copyright (c) 2017-2019, Stefan Grönke
# Copyright (c) 2014-2018, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""ioc Resource extension that managed exporting and importing backups."""
import typing
import tarfile
import tempfile
import os
import os.path
import enum
import libzfs

import libioc.events


class Format(enum.Enum):
    """Enum of the backup formats."""

    TAR = "1"
    DIRECTORY = "2"


class LaunchableResourceBackup:
    """
    Create and restore backups of a LaunchableResource.

    It is only possible to run one concurrent backup operation because this
    instance uses a global temp directory that is deleted when the lock is
    removed. In fact the existence of a temp directory indicates the locked
    state.
    """

    resource: 'libioc.LaunchableResource.LaunchableResource'
    _work_dir: typing.Optional[typing.Union[str, tempfile.TemporaryDirectory]]
    _snapshot_name: typing.Optional[str]

    def __init__(
        self,
        resource: 'libioc.LaunchableResource.LaunchableResource'
    ) -> None:
        self.resource = resource
        self._work_dir = None
        self._snapshot_name = None

    @property
    def logger(self) -> 'libioc.Logger.Logger':
        """Return the resources logger instance."""
        return self.resource.logger

    @property
    def zfs(self) -> 'libioc.ZFS.ZFS':
        """Return the resources ZFS instance."""
        return self.resource.zfs

    @property
    def work_dir(self) -> str:
        """Return the absolute path to the current temporary directory."""
        if self._work_dir is not None:
            if isinstance(self._work_dir, tempfile.TemporaryDirectory):
                return self._work_dir.name
            else:
                return self._work_dir
        raise self.__unlocked_error

    @property
    def snapshot_name(self) -> str:
        """Return the snapshot_name that was chosen when locking."""
        if self._snapshot_name is not None:
            return self._snapshot_name
        raise self.__unlocked_error

    @property
    def full_snapshot_name(self) -> str:
        """Return the dataset name with the snapshot name."""
        return f"{self.resource.dataset_name}@{self.snapshot_name}"

    @property
    def __has_release(self) -> bool:
        """Return True if the resource is forked from a release."""
        if "config" in self.resource.__dir__():
            return ("release" in self.resource.config.keys()) is True
        return False

    @property
    def __unlocked_error(self) -> Exception:
        # this error cannot occur when using public API
        return Exception("Resource backup is not locked")

    @property
    def locked(self) -> bool:
        """Return True when a temporary directory exists."""
        return (self._work_dir is None) is False

    def _lock(self, work_dir: typing.Optional[str]=None) -> None:
        self._require_unlocked()
        _work_dir: typing.Union[str, tempfile.TemporaryDirectory]
        if work_dir is None:
            _work_dir = tempfile.TemporaryDirectory()
            self.logger.spam(
                f"Resource backup temp directory created: {_work_dir.name}"
            )
        else:
            _work_dir = str(work_dir)
            if os.path.exists(_work_dir) is False:
                os.makedirs(_work_dir, mode=0o0750)
                self.logger.spam(
                    f"Resource backup temp directory created: {_work_dir}"
                )
        self._work_dir = _work_dir
        self._snapshot_name = libioc.ZFS.append_snapshot_datetime("backup")

    def _unlock(self) -> None:
        work_dir = self.work_dir
        self.logger.spam(f"Deleting Resource backup temp directory {work_dir}")
        if (self._work_dir is not None):
            if isinstance(self._work_dir, tempfile.TemporaryDirectory):
                self._work_dir.cleanup()

    def _require_unlocked(self) -> None:
        if self.locked is False:
            return
        raise libioc.errors.BackupInProgress(logger=self.logger)

    def restore(
        self,
        source: str,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """
        Import a resource from an archive.

        Resource archives created with libiocage backup export can be restored
        on any host. When importing a basejail the linked release needs to
        exist on the host.

        Args:

            source (str):

                The path to the exported archive file (tar.gz)
        """
        if os.path.exists(source) is False:
            raise libioc.errors.BackupSourceDoesNotExist(
                source=source,
                logger=self.logger
            )

        if os.path.isdir(source) is True:
            backup_format = Format.DIRECTORY
        elif (source.endswith(".txz") or source.endswith(".tar.gz")) is True:
            backup_format = Format.TAR
        else:
            raise libioc.errors.BackupSourceUnknownFormat(
                source=source,
                logger=self.logger
            )

        resourceBackupEvent = libioc.events.ResourceBackup(
            self.resource,
            scope=event_scope
        )
        scope = resourceBackupEvent.scope
        yield resourceBackupEvent.begin()

        self._lock(
            work_dir=(None if (backup_format == Format.TAR) else source)
        )

        def _unlock_resource_backup() -> None:
            self._unlock()

        resourceBackupEvent.add_rollback_step(_unlock_resource_backup)

        if (backup_format == Format.TAR):
            yield from self._extract_bundle(source, event_scope=scope)

        def _destroy_failed_import() -> None:
            try:
                self.zfs.delete_dataset_recursive(self.resource.dataset)
            except libzfs.ZFSException:
                pass

        resourceBackupEvent.add_rollback_step(_destroy_failed_import)

        # ToDo: Allow importing of releases or empty jails
        archived_config = libioc.Config.Type.JSON.ConfigJSON(
            file=f"{self.work_dir}/config.json",
            logger=self.logger
        ).read()

        is_standalone = os.path.isfile(f"{self.work_dir}/root.zfs") is True
        has_release = ("release" in archived_config.keys()) is True

        try:
            if has_release and not is_standalone:
                release = libioc.Release.ReleaseGenerator(
                    name=archived_config["release"],
                    logger=self.logger,
                    zfs=self.zfs,
                    host=self.resource.host
                )
                self.resource.create_from_release(release)
            else:
                self.resource.create_from_scratch()

            if is_standalone is False:
                yield from self._import_root_dataset(event_scope=scope)

            yield from self._import_other_datasets_recursive(event_scope=scope)
            yield from self._import_config(
                libioc.Config.Data.Data(archived_config),
                event_scope=scope
            )
            yield from self._import_fstab(event_scope=scope)
        except Exception as e:
            yield resourceBackupEvent.fail(e)
            raise e

        _unlock_resource_backup()
        yield resourceBackupEvent.end()

    def _extract_bundle(
        self,
        source: str,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:

        extractBundleEvent = libioc.events.ExtractBundle(
            source=source,
            destination=self.work_dir,
            resource=self.resource,
            scope=event_scope
        )
        yield extractBundleEvent.begin()
        try:
            libioc.SecureTarfile.extract(
                file=source,
                compression_format="gz",
                destination=self.work_dir,
                logger=self.logger
            )
        except Exception as e:
            yield extractBundleEvent.fail(e)
            raise e

        yield extractBundleEvent.end()

    def _import_config(
        self,
        data: libioc.Config.Data.Data,
        event_scope: typing.Optional['libioc.events.Scope']
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:

        importConfigEvent = libioc.events.ImportConfig(
            self.resource,
            scope=event_scope
        )
        yield importConfigEvent.begin()

        try:
            self.resource.config.clone(data, skip_on_error=True)
            self.resource.config_handler.write(self.resource.config.data)
            self.logger.verbose(
                f"Config imported from {self.resource.config_handler.file}"
            )
        except libioc.errors.IocException as e:
            yield importConfigEvent.fail(e)
            raise e

        yield importConfigEvent.end()

    def _import_fstab(
        self,
        event_scope: typing.Optional['libioc.events.Scope']
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:

        importFstabEvent = libioc.events.ImportFstab(
            self.resource,
            scope=event_scope
        )
        yield importFstabEvent.begin()

        fstab_file_path = f"{self.work_dir}/fstab"
        if os.path.isfile(fstab_file_path) is False:
            yield importFstabEvent.skip()
            return

        try:
            fstab = self.resource.fstab
            _old_fstab_file = fstab.file
            fstab.file = fstab_file_path
            fstab.read_file()
            fstab.file = _old_fstab_file
            fstab.save()
            self.logger.verbose(f"Fstab restored from {fstab.file}")
        except libioc.errors.IocException as e:
            yield importFstabEvent.fail(e)
            raise e
        yield importFstabEvent.end()

    def _import_root_dataset(
        self,
        event_scope: typing.Optional['libioc.events.Scope']
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """
        Import data from an exported root dataset.

        The file structure is imported using using rsync. All assets that
        already exist in the resources root dataset will be overwritten.
        """
        importRootDatasetEvent = libioc.events.ImportRootDataset(
            self.resource,
            scope=event_scope
        )
        yield importRootDatasetEvent.begin()

        try:
            temp_root_dir = f"{self.work_dir}/root"
            self.logger.verbose(
                f"Importing root dataset data from {temp_root_dir}"
            )
            libioc.helpers.exec([
                "rsync",
                "-av",
                "--links",
                "--hard-links",
                "--safe-links",
                f"{temp_root_dir}/",
                f"{self.resource.root_dataset.mountpoint}/"
            ])
        except libioc.errors.IocException as e:
            yield importRootDatasetEvent.fail(e)
            raise e
        yield importRootDatasetEvent.end()

    def _import_other_datasets_recursive(
        self,
        event_scope: typing.Optional['libioc.events.Scope']
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:

        importOtherDatasetsEvent = libioc.events.ImportOtherDatasets(
            self.resource,
            scope=event_scope
        )
        yield importOtherDatasetsEvent.begin()
        hasImportedOtherDatasets = False

        for dataset_name in self._list_importable_datasets():
            absolute_asset_name = f"{self.work_dir}/{dataset_name}.zfs"
            importOtherDatasetEvent = libioc.events.ImportOtherDataset(
                dataset_name=dataset_name,
                resource=self.resource,
                scope=importOtherDatasetsEvent.scope
            )
            yield importOtherDatasetEvent.begin()
            try:
                with open(absolute_asset_name, "r", encoding="utf-8") as f:
                    dataset = self.resource.zfs.get_or_create_dataset(
                        f"{self.resource.dataset.name}/{dataset_name}"
                    )
                    dataset.receive(f.fileno(), force=True)
                    hasImportedOtherDatasets = True
            except libioc.errors.IocException as e:
                yield importOtherDatasetEvent.fail(e)
                raise e
            yield importOtherDatasetEvent.end()

        if hasImportedOtherDatasets is False:
            yield importOtherDatasetsEvent.skip()
        else:
            yield importOtherDatasetsEvent.end()

    def _list_importable_datasets(
        self,
        current_directory: typing.Optional[str]=None
    ) -> typing.List[str]:

        if current_directory is None:
            current_directory = self.work_dir

        suffix = ".zfs"

        files: typing.List[str] = []
        current_files = os.listdir(current_directory)
        for current_file in current_files:
            if current_file == f"{self.work_dir}/root":
                continue
            if current_file == f"{self.work_dir}/fstab":
                continue
            if os.path.isdir(current_file):
                nested_files = self._list_importable_datasets(current_file)
                files = files + [f"{current_file}/{x}" for x in nested_files]
            elif current_file.endswith(suffix):
                files.append(current_file[:-len(suffix)])
        return files

    def export(
        self,
        destination: str,
        standalone: typing.Optional[bool]=None,
        recursive: bool=False,
        backup_format: Format=Format.TAR,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """
        Export the resource.

        Resource exports contain the jails configuration and differing files
        between the jails root dataset and its release. Other datasets in the
        jails dataset are snapshotted and attached to the export entirely.

        Args:

            destination (str):

                The resource is exported to this location as archive file.

            standalone (bool):

                The default depends on whether the resource is forked from a
                release or not. If there is a origin release, the export will
                contain the changed files relative to the release. Enabling
                this option will enforce ZFS dataset exports instead of rsync
                compare-dest diffs.
                Standalone exports will cause duplicated data on the importing
                host, but are independent of any release.

            recursive (bool):

                    Includes snapshots of all exported ZFS datasets.
        """
        resourceBackupEvent = libioc.events.ResourceBackup(
            self.resource,
            scope=event_scope
        )
        _scope = resourceBackupEvent.scope
        yield resourceBackupEvent.begin()

        if backup_format == Format.TAR:
            self._lock(None)  # use temporary directory and tar later
        else:
            if os.path.exists(destination) is True:
                raise libioc.errors.ExportDestinationExists(
                    destination=destination,
                    logger=self.logger
                )
            self._lock(destination)  # directly output to this directory

        self._take_resource_snapshot()

        zfs_send_flags = set()
        if recursive is True:
            zfs_send_flags.add(libzfs.SendFlag.REPLICATE)

        is_standalone = (standalone is not False) and self.__has_release

        def _unlock_resource_backup() -> None:
            self._delete_resource_snapshot()
            self._unlock()

        resourceBackupEvent.add_rollback_step(_unlock_resource_backup)

        if "config" in self.resource.__dir__():
            # only export config when the resource has one
            yield from self._export_config(event_scope=_scope)
            yield from self._export_fstab(event_scope=_scope)

        if is_standalone is False:
            yield from self._export_root_dataset(
                flags=zfs_send_flags,
                event_scope=_scope
            )

        # other datasets include `root` when the resource is no basejail
        yield from self._export_other_datasets_recursive(
            flags=zfs_send_flags,
            standalone=is_standalone,
            limit_depth=(recursive is True),
            event_scope=_scope
        )

        if backup_format == Format.TAR:
            yield from self._bundle_backup(
                destination=destination,
                event_scope=_scope
            )

        _unlock_resource_backup()
        yield resourceBackupEvent.end()

    def _take_resource_snapshot(self) -> None:
        self.resource.dataset.snapshot(
            self.full_snapshot_name,
            recursive=True
        )

    def _delete_resource_snapshot(self) -> None:
        self.zfs.get_snapshot(self.full_snapshot_name).delete(recursive=True)

    def _export_config(
        self,
        event_scope: typing.Optional['libioc.events.Scope']
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:

        exportConfigEvent = libioc.events.ExportConfig(
            self.resource,
            scope=event_scope
        )
        yield exportConfigEvent.begin()

        try:
            temp_config = libioc.Config.Type.JSON.ConfigJSON(
                file=f"{self.work_dir}/config.json",
                logger=self.logger
            )
            temp_config.data = self.resource.config.data
            temp_config.write(temp_config.data)
            self.logger.verbose(f"Config duplicated to {temp_config.file}")
        except libioc.errors.IocException as e:
            yield exportConfigEvent.fail(e)
            raise e
        yield exportConfigEvent.end()

    def _export_fstab(
        self,
        event_scope: typing.Optional['libioc.events.Scope']
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:

        exportFstabEvent = libioc.events.ExportFstab(
            self.resource,
            scope=event_scope
        )
        yield exportFstabEvent.begin()

        try:
            fstab = libioc.Config.Jail.File.Fstab.JailFstab(
                jail=self.resource,
                logger=self.resource.logger,
                host=self.resource.host
            )
            fstab.read_file()
            fstab.file = f"{self.work_dir}/fstab"
            fstab.replace_path(
                self.resource.dataset.mountpoint,
                "backup:///"
            )
            fstab.save()
            self.logger.verbose(f"Fstab saved to {fstab.file}")
        except libioc.errors.IocException as e:
            yield exportFstabEvent.fail(e)
            raise e
        yield exportFstabEvent.end()

    def _export_root_dataset(
        self,
        flags: typing.Set[libzfs.SendFlag],
        event_scope: typing.Optional['libioc.events.Scope']
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:

        exportRootDatasetEvent = libioc.events.ExportRootDataset(
            self.resource,
            scope=event_scope
        )
        yield exportRootDatasetEvent.begin()

        try:
            temp_root_dir = f"{self.work_dir}/root"
            compare_dest = "/".join([
                self.resource.release.root_dataset.mountpoint,
                f".zfs/snapshot/{self.resource.release_snapshot.snapshot_name}"
            ])
            os.mkdir(temp_root_dir)

            excludes: typing.List[str] = []
            basedirs = libioc.helpers.get_basedir_list(
                distribution_name=self.resource.host.distribution.name
            )
            for basedir in basedirs:
                _exclude = f"{self.resource.root_dataset.mountpoint}/{basedir}"
                excludes.append("--exclude")
                excludes.append(_exclude)

            self.logger.verbose(
                f"Writing root dataset delta to {temp_root_dir}"
            )
            libioc.helpers.exec([
                "rsync",
                "-av",
                "--checksum",
                "--links",
                "--hard-links",
                "--safe-links"
            ] + excludes + [
                f"--compare-dest={compare_dest}/",
                f"{self.resource.root_dataset.mountpoint}/",
                temp_root_dir,
            ], logger=self.logger)
        except libioc.errors.IocException as e:
            yield exportRootDatasetEvent.fail(e)
            raise e
        yield exportRootDatasetEvent.end()

    def _export_other_datasets_recursive(
        self,
        standalone: bool,
        flags: typing.Set[libzfs.SendFlag],
        event_scope: typing.Optional['libioc.events.Scope'],
        limit_depth: bool=False,
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:

        exportOtherDatasetsEvent = libioc.events.ExportOtherDatasets(
            self.resource,
            scope=event_scope
        )
        yield exportOtherDatasetsEvent.begin()
        hasExportedOtherDatasets = False

        if limit_depth is True:
            child_datasets = self.resource.dataset.children
        else:
            child_datasets = self.resource.dataset.children_recursive

        for dataset in child_datasets:
            __is_root = (dataset.name == self.resource.root_dataset.name)
            if __is_root and not standalone:
                continue

            hasExportedOtherDatasets = True
            exportOtherDatasetEvent = libioc.events.ExportOtherDataset(
                dataset=dataset,
                flags=flags,
                resource=self.resource,
                scope=exportOtherDatasetsEvent.scope
            )
            yield exportOtherDatasetEvent.begin()
            try:
                self._export_other_dataset(dataset, flags)
            except libioc.errors.IocException as e:
                yield exportOtherDatasetEvent.fail(e)
                raise e
            yield exportOtherDatasetEvent.end()

        if hasExportedOtherDatasets is False:
            yield exportOtherDatasetsEvent.skip()
        else:
            yield exportOtherDatasetsEvent.end()

    def _export_other_dataset(
        self,
        dataset: libzfs.ZFSDataset,
        flags: typing.Set[libzfs.SendFlag]
    ) -> None:
        relative_name = self._get_relative_dataset_name(dataset)
        name_fragments = relative_name.split("/")
        minor_dataset_name = name_fragments.pop()
        relative_dir_name = "/".join(name_fragments)
        absolute_dir_name = f"{self.work_dir}/{relative_dir_name}".rstrip("/")
        absolute_asset_name = f"{absolute_dir_name}/{minor_dataset_name}.zfs"

        if os.path.isdir(absolute_dir_name) is False:
            os.makedirs(absolute_dir_name)
            # ToDo: manually set permissions

        full_snapshot_name = f"{dataset.name}@{self.snapshot_name}"
        snapshot = self.zfs.get_snapshot(full_snapshot_name)

        self.logger.verbose(
            f"Exporting dataset {dataset.name} to {absolute_asset_name}"
        )

        with open(absolute_asset_name, "w", encoding="utf-8") as f:
            snapshot.send(f.fileno(), fromname=None, flags=flags)

    def _bundle_backup(
        self,
        destination: str,
        event_scope: typing.Optional['libioc.events.Scope']
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Create the an archive file from the backup assets."""
        bundleBackupEvent = libioc.events.BundleBackup(
            destination=destination,
            resource=self.resource,
            scope=event_scope
        )
        yield bundleBackupEvent.begin()

        try:
            self.logger.verbose(f"Bundling backup to {destination}")
            tar = tarfile.open(destination, "w:gz")
            tar.add(self.work_dir, arcname=".")
            tar.close()
        except libioc.errors.IocException as e:
            yield bundleBackupEvent.fail(e)
            raise e

        yield bundleBackupEvent.end()

    def _get_relative_dataset_name(self, dataset: libzfs.ZFSDataset) -> str:
        return str(dataset.name[(len(self.resource.dataset.name) + 1):])
