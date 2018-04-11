# Copyright (c) 2014-2017, iocage
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

    def export(
        self,
        destination: str
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """
        Export the resource.

        Jail exports contain the jails configuration and differing files
        between the jails root dataset and its release. Other datasets in the
        jails dataset are snapshotted and attached to the export entirely.

        Args:

            destination (str):

                The resource is exported to this location as archive file.
        """
        events = iocage.lib.events
        exportConfigEvent = events.ExportConfig(self.resource)
        exportRootDatasetEvent = events.ExportRootDataset(self.resource)
        exportOtherDatasetsEvent = events.ExportOtherDatasets(self.resource)
        bundleBackupEvent = events.BundleBackup(
            destination=destination,
            resource=self.resource
        )

        self._lock()
        self._take_resource_snapshot()

        yield exportConfigEvent.begin()
        # ToDo: skip when the resource has no configuration (e.g. Release)
        try:
            self._export_config()
        except iocage.lib.errors.IocageException as e:
            yield exportConfigEvent.fail(e)
            raise e
        yield exportConfigEvent.end()

        yield exportRootDatasetEvent.begin()
        try:
            self._export_root_dataset()
        except iocage.lib.errors.IocageException as e:
            yield exportRootDatasetEvent.fail(e)
            raise e
        yield exportRootDatasetEvent.end()

        yield exportOtherDatasetsEvent.begin()
        hasExportedOtherDatasets = False
        for event in self._export_other_datasets_recursive():
            hasExportedOtherDatasets = True
            yield event
        if hasExportedOtherDatasets is False:
            yield exportOtherDatasetsEvent.skip()
        else:
            yield exportOtherDatasetsEvent.end()

        self._delete_resource_snapshot()

        yield bundleBackupEvent.begin()
        try:
            self._bundle_backup(destination=destination)
        except iocage.lib.errors.IocageException as e:
            yield bundleBackupEvent.fail(e)
            raise e
        yield bundleBackupEvent.end()

        self._unlock()

    def _take_resource_snapshot(self) -> None:
        self.resource.dataset.snapshot(
            self.full_snapshot_name,
            recursive=True
        )

    def _delete_resource_snapshot(self) -> None:
        self.zfs.get_snapshot(self.full_snapshot_name).delete(recursive=True)

    def _export_config(self) -> None:
        temp_config = iocage.lib.Config.Type.JSON.ConfigJSON(
            file=f"{self.temp_dir}/config.json",
            logger=self.logger
        )
        temp_config.data = self.resource.config.data
        temp_config.write(temp_config.data)
        self.logger.verbose(f"Config duplicated to {temp_config.file}")

    def _export_root_dataset(self) -> None:
        temp_root_dir = f"{self.temp_dir}/root"
        os.mkdir(temp_root_dir)

        self.logger.verbose(f"Writing root dataset delta to {temp_root_dir}")
        iocage.lib.helpers.exec([
            "rsync",
            "-rv",
            "--checksum",
            f"--compare-dest={self.resource.release.root_dataset.mountpoint}/",
            f"{self.resource.root_dataset.mountpoint}/",
            temp_root_dir
        ])

    def _export_other_datasets_recursive(
        self
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        for dataset in self.resource.dataset.children_recursive:
            if dataset.name == self.resource.root_dataset.name:
                continue

            exportOtherDatasetEvent = iocage.lib.events.ExportOtherDataset(
                dataset=dataset,
                resource=self.resource
            )
            yield exportOtherDatasetEvent.begin()
            try:
                self._export_other_dataset(dataset)
            except iocage.lib.errors.IocageException as e:
                yield exportOtherDatasetEvent.fail(e)
                raise e
            yield exportOtherDatasetEvent.end()

    def _export_other_dataset(self, dataset: libzfs.ZFSDataset) -> None:
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
            snapshot.send(f.fileno(), fromname=None)

    def _bundle_backup(self, destination: str) -> None:
        """Create the an archive file from the backup assets."""
        self.logger.verbose(f"Bundling backup to {destination}")
        tar = tarfile.open(destination, "w:gz")
        tar.add(self.temp_dir, arcname=".")
        tar.close()

    def _get_relative_dataset_name(self, dataset: libzfs.ZFSDataset) -> str:
        return str(dataset.name[(len(self.resource.dataset.name) + 1):])
