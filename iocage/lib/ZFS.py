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
"""iocage libzfs enhancement module."""
import typing
import libzfs

import iocage.lib.Logger
import iocage.lib.helpers
import iocage.lib.errors


class ZFS(libzfs.ZFS):
    """libzfs enhancement module."""

    logger: typing.Optional[iocage.lib.Logger.Logger] = None

    def create_dataset(
        self,
        dataset_name: str,
        **kwargs
    ) -> libzfs.ZFSDataset:
        """Automatically get the pool and create a dataset from its name."""
        pool = self.get_pool(dataset_name)
        pool.create(dataset_name, kwargs, create_ancestors=True)

        dataset = self.get_dataset(dataset_name)
        dataset.mount()
        return dataset

    def get_or_create_dataset(
        self,
        dataset_name: str,
        **kwargs
    ) -> libzfs.ZFSDataset:
        """Find or create the dataset, then return it."""
        try:
            return self.get_dataset(dataset_name)
        except libzfs.ZFSException:
            pass

        return self.create_dataset(dataset_name, **kwargs)

    def get_pool(self, name: str) -> libzfs.ZFSPool:
        """Get the pool with a given name."""
        pool_name = name.split("/")[0]
        for pool in self.pools:
            if pool.name == pool_name:
                return pool
        raise iocage.lib.errors.ZFSPoolUnavailable(
            pool_name=pool_name,
            logger=self.logger
        )

    def delete_dataset_recursive(
        self,
        dataset: libzfs.ZFSDataset,
        delete_snapshots: bool=True,
        delete_origin_snapshot: bool=True
    ) -> None:
        """Recursively delete a dataset."""
        for child in dataset.children:
            self.delete_dataset_recursive(child)

        if dataset.mountpoint is not None:
            if self.logger is not None:
                self.logger.spam(f"Unmounting {dataset.name}")
            dataset.umount()

        if delete_snapshots is True:
            for snapshot in dataset.snapshots:
                if self.logger is not None:
                    self.logger.verbose(
                        f"Deleting snapshot {snapshot.name}"
                    )
                snapshot.delete()

        origin = None
        if delete_origin_snapshot is True:
            origin_property = dataset.properties["origin"]
            if origin_property.value != "":
                origin = origin_property

        if self.logger is not None:
            self.logger.verbose(f"Deleting dataset {dataset.name}")
        dataset.delete()

        if origin is not None:
            if self.logger is not None:
                self.logger.verbose(f"Deleting snapshot {origin}")
            origin_snapshot = self.get_snapshot(origin.value)
            origin_snapshot.delete()


def get_zfs(
    logger: typing.Optional[iocage.lib.Logger.Logger]=None,
    history: bool=True,
    history_prefix: str="<iocage>"
) -> ZFS:
    """Get an instance of iocages enhanced ZFS class."""
    zfs = ZFS(history=history, history_prefix=history_prefix)
    zfs.logger = iocage.lib.helpers.init_logger(zfs, logger)
    return zfs
