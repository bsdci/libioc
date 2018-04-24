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
"""iocage Resource extension that managed exporting and importing backups."""
import typing
import tarfile
import tempfile
import os
import libzfs

import iocage.lib.events


class LaunchableResourceBackup:
    """
    Create and restore backups of a LaunchableResource.

    It is only possible to run one concurrent backup operation because this
    instance uses a global temp directory that is deleted when the lock is
    removed. In fact the existence of a temp directory indicates the locked
    state.
    """

    resource: 'iocage.lib.LaunchableResource.LaunchableResource'
    _temp_dir: typing.Optional[tempfile.TemporaryDirectory]
    _snapshot_name: typing.Optional[str]

    def __init__(
        self,
        resource: 'iocage.lib.LaunchableResource.LaunchableResource'
    ) -> None:
        self.resource = resource
        self._temp_dir = None
        self._snapshot_name = None

    @property
    def logger(self) -> 'iocage.lib.Logger.Logger':
        """Return the resources logger instance."""
        return self.resource.logger

    @property
    def zfs(self) -> 'iocage.lib.ZFS.ZFS':
        """Return the resources ZFS instance."""
        return self.resource.zfs

    @property
    def temp_dir(self) -> str:
        """Return the absolute path to the current temporary directory."""
        if self._temp_dir is not None:
            return self._temp_dir.name
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
        return (self._temp_dir is not None)

    def _lock(self) -> None:
        self._require_unlocked()
        temp_dir = tempfile.TemporaryDirectory()
        self.logger.spam(
            f"Resource backup temp directory created: {temp_dir.name}"
        )
        self._temp_dir = temp_dir
        self._snapshot_name = iocage.lib.ZFS.append_snapshot_datetime("backup")

    def _unlock(self) -> None:
        temp_dir = self.temp_dir
        self.logger.spam(f"Deleting Resource backup temp directory {temp_dir}")
        if self._temp_dir is not None:
            self._temp_dir.cleanup()

    def _require_unlocked(self) -> None:
        if self.locked is False:
            return
        raise iocage.lib.errors.BackupInProgress(logger=self.logger)

    def restore(
        self,
        source: str
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """
        Import a resource from an archive.

        Resource archives created with libiocage backup export can be restored
        on any host. When importing a basejail the linked release needs to
        exist on the host.

        Args:

            source (str):

                The path to the exported archive file (tar.gz)
        """
        resourceBackupEvent = iocage.lib.events.ResourceBackup(self.resource)
        yield resourceBackupEvent.begin()

        self._lock()

        def _unlock_resource_backup() -> None:
            self._unlock()

        resourceBackupEvent.add_rollback_step(_unlock_resource_backup)

        for event in self._extract_bundle(source):
            yield event

        # ToDo: Allow importing of releases or empty jails
        config_data = iocage.lib.Config.Type.JSON.ConfigJSON(
            file=f"{self.temp_dir}/config.json",
            logger=self.logger
        ).read()

        is_standalone = os.path.isfile(f"{self.temp_dir}/root.zfs") is True
        has_release = ("release" in config_data.keys()) is True

        if has_release and not is_standalone:
            release = iocage.lib.Release.ReleaseGenerator(
                name=config_data["release"],
                logger=self.logger,
                zfs=self.zfs,
                host=self.resource.host
            )
            self.resource.create_from_release(release)
        else:
            self.resource.create_from_scratch()

        if is_standalone is False:
            for event in self._import_root_dataset():
                yield event

        for event in self._import_other_datasets_recursive():
            yield event

        for event in self._import_config(config_data):
            yield event

        for event in self._import_fstab():
            yield event

        _unlock_resource_backup()
        yield resourceBackupEvent.end()

    def _extract_bundle(
        self,
        source: str
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        extractBundleEvent = iocage.lib.events.ExtractBundle(
            source=source,
            destination=self.temp_dir,
            resource=self.resource
        )
        yield extractBundleEvent.begin()
        try:
            iocage.lib.SecureTarfile.extract(
                file=source,
                compression_format="gz",
                destination=self.temp_dir,
                logger=self.logger
            )
        except iocage.lib.errors.IocageException as e:
            yield extractBundleEvent.fail(e)
            raise e

        yield extractBundleEvent.end()

    def _import_config(
        self,
        data: typing.Dict[str, typing.Any]
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        importConfigEvent = iocage.lib.events.ImportConfig(self.resource)
        yield importConfigEvent.begin()

        try:
            self.resource.config.data = data
            self.resource.config_handler.write(data)
            self.logger.verbose(
                f"Config imported from {self.resource.config_handler.file}"
            )
        except iocage.lib.errors.IocageException as e:
            yield importConfigEvent.fail(e)
            raise e

        yield importConfigEvent.end()

    def _import_fstab(
        self
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        importFstabEvent = iocage.lib.events.ImportFstab(self.resource)
        yield importFstabEvent.begin()

        fstab_file_path = f"{self.temp_dir}/fstab"
        if os.path.isfile(fstab_file_path) is False:
            yield importFstabEvent.skip()
            return

        try:
            fstab = self.resource.fstab
            _old_fstab_file = fstab.file
            fstab.file = fstab_file_path
            fstab.read_file()
            fstab.replace_path(
                "backup:///",
                self.resource.dataset.mountpoint
            )
            fstab.file = _old_fstab_file
            fstab.save()
            self.logger.verbose(f"Fstab restored from {fstab.file}")
        except iocage.lib.errors.IocageException as e:
            yield importFstabEvent.fail(e)
            raise e
        yield importFstabEvent.end()

    def _import_root_dataset(
        self
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """
        Import data from an exported root dataset.

        The file structure is imported using using rsync. All assets that
        already exist in the resources root dataset will be overwritten.
        """
        importRootDatasetEvent = iocage.lib.events.ImportRootDataset(
            self.resource
        )
        yield importRootDatasetEvent.begin()

        try:
            temp_root_dir = f"{self.temp_dir}/root"
            self.logger.verbose(
                f"Importing root dataset data from {temp_root_dir}"
            )
            iocage.lib.helpers.exec([
                "rsync",
                "-av",
                "--links",
                "--safe-links",
                f"{temp_root_dir}/",
                f"{self.resource.root_dataset.mountpoint}/"
            ])
        except iocage.lib.errors.IocageException as e:
            yield importRootDatasetEvent.fail(e)
            raise e
        yield importRootDatasetEvent.end()

    def _import_other_datasets_recursive(
        self
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        importOtherDatasetsEvent = iocage.lib.events.ImportOtherDatasets(
            self.resource
        )
        yield importOtherDatasetsEvent.begin()
        hasImportedOtherDatasets = False

        for dataset_name in self._list_importable_datasets():
            absolute_asset_name = f"{self.temp_dir}/{dataset_name}.zfs"
            importOtherDatasetEvent = iocage.lib.events.ImportOtherDataset(
                dataset_name=dataset_name,
                resource=self.resource
            )
            yield importOtherDatasetEvent.begin()
            try:
                with open(absolute_asset_name, "r") as f:
                    dataset = self.resource.zfs.get_or_create_dataset(
                        f"{self.resource.dataset.name}/{dataset_name}"
                    )
                    dataset.receive(f.fileno(), force=True)
                    hasImportedOtherDatasets = True
            except iocage.lib.errors.IocageException as e:
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
            current_directory = self.temp_dir

        suffix = ".zfs"

        files: typing.List[str] = []
        current_files = os.listdir(current_directory)
        for current_file in current_files:
            if current_file == f"{self.temp_dir}/root":
                continue
            if current_file == f"{self.temp_dir}/fstab":
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
        recursive: bool=False
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
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
        resourceBackupEvent = iocage.lib.events.ResourceBackup(self.resource)
        yield resourceBackupEvent.begin()

        self._lock()
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
            for event in self._export_config():
                yield event
            for event in self._export_fstab():
                yield event

        if is_standalone is False:
            for event in self._export_root_dataset(flags=zfs_send_flags):
                yield event

        # other datasets include `root` when the resource is no basejail
        recursive_export_events = self._export_other_datasets_recursive(
            flags=zfs_send_flags,
            standalone=is_standalone,
            limit_depth=(recursive is True)
        )
        for event in recursive_export_events:
            yield event

        for event in self._bundle_backup(destination=destination):
            yield event

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
        self
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        exportConfigEvent = iocage.lib.events.ExportConfig(self.resource)
        yield exportConfigEvent.begin()

        try:
            temp_config = iocage.lib.Config.Type.JSON.ConfigJSON(
                file=f"{self.temp_dir}/config.json",
                logger=self.logger
            )
            temp_config.data = self.resource.config.data
            temp_config.write(temp_config.data)
            self.logger.verbose(f"Config duplicated to {temp_config.file}")
        except iocage.lib.errors.IocageException as e:
            yield exportConfigEvent.fail(e)
            raise e
        yield exportConfigEvent.end()

    def _export_fstab(
        self
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        exportFstabEvent = iocage.lib.events.ExportFstab(self.resource)
        yield exportFstabEvent.begin()

        try:
            fstab = iocage.lib.Config.Jail.File.Fstab.Fstab(
                jail=self.resource,
                release=None,
                logger=self.resource.logger,
                host=self.resource.host
            )
            fstab.read_file()
            fstab.file = f"{self.temp_dir}/fstab"
            fstab.replace_path(
                self.resource.dataset.mountpoint,
                "backup:///"
            )
            fstab.save()
            self.logger.verbose(f"Fstab saved to {fstab.file}")
        except iocage.lib.errors.IocageException as e:
            yield exportFstabEvent.fail(e)
            raise e
        yield exportFstabEvent.end()

    def _export_root_dataset(
        self,
        flags: typing.Set[libzfs.SendFlag]
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        exportRootDatasetEvent = iocage.lib.events.ExportRootDataset(
            self.resource
        )
        yield exportRootDatasetEvent.begin()

        try:
            temp_root_dir = f"{self.temp_dir}/root"
            compare_dest = self.resource.release.root_dataset.mountpoint
            os.mkdir(temp_root_dir)

            self.logger.verbose(
                f"Writing root dataset delta to {temp_root_dir}"
            )
            iocage.lib.helpers.exec([
                "rsync",
                "-av",
                "--checksum",
                "--links",
                "--safe-links",
                f"--compare-dest={compare_dest}/",
                f"{self.resource.root_dataset.mountpoint}/",
                temp_root_dir
            ])
        except iocage.lib.errors.IocageException as e:
            yield exportRootDatasetEvent.fail(e)
            raise e
        yield exportRootDatasetEvent.end()

    def _export_other_datasets_recursive(
        self,
        standalone: bool,
        flags: typing.Set[libzfs.SendFlag],
        limit_depth: bool=False
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        exportOtherDatasetsEvent = iocage.lib.events.ExportOtherDatasets(
            self.resource
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
            exportOtherDatasetEvent = iocage.lib.events.ExportOtherDataset(
                dataset=dataset,
                flags=flags,
                resource=self.resource
            )
            yield exportOtherDatasetEvent.begin()
            try:
                self._export_other_dataset(dataset, flags)
            except iocage.lib.errors.IocageException as e:
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
        absolute_dir_name = f"{self.temp_dir}/{relative_dir_name}".rstrip("/")
        absolute_asset_name = f"{absolute_dir_name}/{minor_dataset_name}.zfs"

        if os.path.isdir(absolute_dir_name) is False:
            os.makedirs(absolute_dir_name)
            # ToDo: manually set permissions

        full_snapshot_name = f"{dataset.name}@{self.snapshot_name}"
        snapshot = self.zfs.get_snapshot(full_snapshot_name)

        self.logger.verbose(
            f"Exporting dataset {dataset.name} to {absolute_asset_name}"
        )

        with open(absolute_asset_name, "w") as f:
            snapshot.send(f.fileno(), fromname=None, flags=flags)

    def _bundle_backup(
        self,
        destination: str
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """Create the an archive file from the backup assets."""
        bundleBackupEvent = iocage.lib.events.BundleBackup(
            destination=destination,
            resource=self.resource
        )
        yield bundleBackupEvent.begin()

        try:
            self.logger.verbose(f"Bundling backup to {destination}")
            tar = tarfile.open(destination, "w:gz")
            tar.add(self.temp_dir, arcname=".")
            tar.close()
        except iocage.lib.errors.IocageException as e:
            yield bundleBackupEvent.fail(e)
            raise e

        yield bundleBackupEvent.end()

    def _get_relative_dataset_name(self, dataset: libzfs.ZFSDataset) -> str:
        return str(dataset.name[(len(self.resource.dataset.name) + 1):])
