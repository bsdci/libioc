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
"""ioc libzfs enhancement module."""
import typing
import libzfs
import datetime

import libioc.Logger
import libioc.helpers_object
import libioc.errors


class ZFS(libzfs.ZFS):
    """libzfs enhancement module."""

    _logger: typing.Optional['libioc.Logger.Logger']

    @property
    def logger(self) -> 'libioc.Logger.Logger':
        """Return logger or raise an exception when it is unavailable."""
        Logger = libioc.Logger.Logger
        if not (self._has_logger or isinstance(self._logger, Logger)):
            raise Exception("The logger is unavailable")
        return self._logger

    @logger.setter
    def logger(self, logger: 'libioc.Logger.Logger') -> None:
        """Set the ZFS objects logger."""
        self._logger = logger

    def create_dataset(  # noqa: T484
        self,
        dataset_name: str
    ) -> libzfs.ZFSDataset:
        """Automatically get the pool and create a dataset from its name."""
        pool = self.get_pool(dataset_name)
        pool.create(dataset_name, {}, create_ancestors=True)

        dataset = self.get_dataset(dataset_name)
        dataset.mount()
        return dataset

    def get_or_create_dataset(
        self,
        dataset_name: str
    ) -> libzfs.ZFSDataset:
        """Find or create the dataset, then return it."""
        try:
            return self.get_dataset(dataset_name)
        except libzfs.ZFSException:
            pass

        return self.create_dataset(dataset_name)

    def get_pool(self, name: str) -> libzfs.ZFSPool:
        """Get the pool with a given name."""
        pool_name = name.split("/")[0]
        for pool in self.pools:
            if pool.name == pool_name:
                return pool
        raise libioc.errors.ZFSPoolUnavailable(
            pool_name=pool_name,
            logger=self.logger
        )

    def delete_dataset_recursive(
        self,
        dataset: libzfs.ZFSDataset,
        delete_snapshots: bool=True,
        delete_origin_snapshot: bool=False
    ) -> None:
        """Recursively delete a dataset."""
        for child in dataset.children:
            self.delete_dataset_recursive(child)

        if dataset.mountpoint is not None:
            if self._has_logger:
                self.logger.spam(f"Unmounting {dataset.name}")
            dataset.umount()

        if delete_snapshots is True:
            for snapshot in dataset.snapshots:
                if self._has_logger:
                    self.logger.verbose(
                        f"Deleting snapshot {snapshot.name}"
                    )
                snapshot.delete(recursive=True)

        origin = None
        if delete_origin_snapshot is True:
            origin_property = dataset.properties["origin"]
            if origin_property.value != "":
                origin = origin_property

        if self._has_logger:
            self.logger.verbose(f"Deleting dataset {dataset.name}")
        try:
            dataset.umount()
            self.logger.spam(f"Dataset {dataset.name} unmounted")
        except libzfs.ZFSException:
            pass
        dataset.delete()

        if origin is not None:
            if self._has_logger:
                self.logger.verbose(f"Deleting snapshot {origin}")
            origin_snapshot = self.get_snapshot(origin.value)
            origin_snapshot.delete()

    def clone_dataset(
        self,
        source: libzfs.ZFSDataset,
        target: str,
        delete_existing: bool=False
    ) -> None:
        """Clone a ZFSDataset from a source to a target dataset name."""
        # delete target dataset if it already exists
        try:
            existing_dataset = self.get_dataset(target)
        except libzfs.ZFSException:
            pass
        else:
            if delete_existing is False:
                raise libioc.errors.DatasetExists(
                    dataset_name=target
                )
            self.logger.verbose(
                f"Deleting existing dataset {target}"
            )
            if existing_dataset.mountpoint is not None:
                existing_dataset.umount()
            existing_dataset.delete()
            del existing_dataset

        snapshot_name = append_snapshot_datetime("clone")
        snapshot_identifier = f"{source.name}@{snapshot_name}"
        try:
            snapshot = self.get_snapshot(snapshot_identifier)
            delete_snapshot = False
        except libzfs.ZFSException:
            source.snapshot(snapshot_identifier, recursive=True)
            snapshot = self.get_snapshot(snapshot_identifier)
            delete_snapshot = True

        snapshot_error = None
        try:
            self.clone_snapshot(snapshot, target)
        except libzfs.ZFSException as e:
            snapshot_error = e

        if delete_snapshot is True:
            snapshot.delete(recursive=True)

        if snapshot_error is not None:
            raise libioc.errors.SnapshotCreation(
                reason=str(snapshot_error),
                logger=self.logger
            )

        if self._has_logger:
            self.logger.verbose(
                f"Successfully cloned {source} to {target}"
            )

    def clone_snapshot(
        self,
        snapshot: libzfs.ZFSSnapshot,
        target: str
    ) -> None:
        """Clone a ZFSSnapshot to the target dataset name."""
        if self._has_logger:
            self.logger.verbose(
                f"Cloning snapshot {snapshot.name} to {target}"
            )

        source_prefix = snapshot.parent.name
        source_prefix_len = len(source_prefix)
        for current_snapshot in snapshot.parent.snapshots_recursive:
            if current_snapshot.snapshot_name != snapshot.snapshot_name:
                continue
            _ds = current_snapshot.parent.name[source_prefix_len:].strip("/")
            current_target = f"{target}/{_ds}".strip("/")
            self._clone_and_mount(current_snapshot, current_target)

    def promote_dataset(
        self,
        dataset: libzfs.ZFSDataset,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        """Recursively promote a dataset."""
        datasets: typing.List[libzfs.ZFSDataset]
        datasets = list(reversed(list(dataset.children_recursive))) + [dataset]
        promoted_source_datasets: typing.List[str] = []
        error: typing.Optional[Exception] = None
        for child in datasets:
            source_dataset = child.properties["origin"].value
            if source_dataset == "":
                # already promoted
                continue
            try:
                self._promote(child, logger=logger)
                promoted_source_datasets.append(source_dataset)
            except libzfs.ZFSException as e:
                error = e
                break

        if error is not None:
            if logger is not None:
                self.logger.verbose("Promotion failed: Reverting changes.")
            for dataset_name in promoted_source_datasets:
                self.get_dataset(dataset_name).promote()
            raise error

    def _promote(
        self,
        dataset: libzfs.ZFSDataset,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        if logger is not None:
            logger.verbose(f"Promoting ZFS dataset {dataset.name}")
        dataset.promote()

    def _clone_and_mount(
        self,
        snapshot: libzfs.ZFSSnapshot,
        target: str
    ) -> None:
        parent_name = "/".join(target.split("/")[:-1])
        self.get_or_create_dataset(parent_name)

        snapshot.clone(target)

        dataset = self.get_dataset(target)
        dataset.mount()

    def rename_snapshot_recursive(
        self,
        snapshot: libzfs.ZFSSnapshot,
        new_name: str
    ) -> None:
        """Rename a snapshot recursively."""
        # ToDo: replace after https://github.com/freenas/py-libzfs/pull/10
        snapshots_recursive = filter(
            lambda x: x.snapshot_name == snapshot.snapshot_name,
            snapshot.parent.snapshots_recursive
        )
        for _snapshot in snapshots_recursive:
            _snapshot.rename(new_name)

    @property
    def _has_logger(self) -> bool:
        return ("_logger" in self.__dir__())


def get_zfs(
    logger: typing.Optional['libioc.Logger.Logger']=None,
    history: bool=True,
    history_prefix: str="<iocage>"
) -> ZFS:
    """Get an instance of iocages enhanced ZFS class."""
    zfs = ZFS(history=history, history_prefix=history_prefix)
    zfs.logger = libioc.helpers_object.init_logger(zfs, logger)
    return zfs


def append_snapshot_datetime(text: str) -> str:
    """Append the current datetime string to a snapshot name."""
    now = datetime.datetime.utcnow()
    text += now.strftime("%Y%m%d%H%I%S.%f")
    return text
