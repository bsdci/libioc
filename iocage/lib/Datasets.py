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
"""iocage datasets module."""
import typing
import os.path
import libzfs

import iocage.lib.errors
import iocage.lib.helpers

# MyPy
import iocage.lib.Types
import iocage.lib.ZFS
import iocage.lib.Logger


class Datasets:
    """iocage core dataset abstraction."""

    ZFS_POOL_ACTIVE_PROPERTY: str = "org.freebsd.ioc:active"

    zfs: 'iocage.lib.ZFS.ZFS'
    logger: 'iocage.lib.Logger.Logger'
    _root: libzfs.ZFSDataset
    _datasets: typing.Dict[str, libzfs.ZFSDataset] = {}

    def __init__(
        self,
        root_dataset: typing.Optional[
            typing.Union[libzfs.ZFSDataset, str]
        ]=None,
        zfs: typing.Optional[iocage.lib.ZFS.ZFS]=None,
        logger: typing.Optional[iocage.lib.Logger.Logger]=None
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)

        if isinstance(root_dataset, libzfs.ZFSDataset):
            self._root = root_dataset
        elif isinstance(root_dataset, str):
            self._root = self.zfs.get_or_create_dataset(root_dataset)

    @property
    def _active_pool_or_none(self) -> typing.Optional[libzfs.ZFSPool]:
        zpools: typing.List[libzfs.ZFSPool] = list(self.zfs.pools)
        for pool in zpools:
            if self.is_pool_active(pool):
                return pool
        return None

    @property
    def active_pool(self) -> libzfs.ZFSPool:
        """Return the currently active iocage pool."""
        pool = self._root_dataset_or_none
        if pool is None:
            raise iocage.lib.errors.IocageNotActivated(logger=self.logger)
        return pool

    @property
    def root(self) -> libzfs.ZFSDataset:
        """Return the iocage root dataset."""
        try:
            return self._root
        except AttributeError:
            pass

        found_pool = self._active_pool_or_none
        if found_pool is None:
            raise iocage.lib.errors.IocageNotActivated(logger=self.logger)

        self._root = self.zfs.get_dataset(f"{found_pool.name}/iocage")
        return self._root

    @property
    def releases(self) -> libzfs.ZFSDataset:
        """Get or create the iocage releases dataset."""
        return self._get_or_create_dataset("releases")

    @property
    def base(self) -> libzfs.ZFSDataset:
        """Get or create the iocage ZFS basejail releases dataset."""
        return self._get_or_create_dataset("base")

    @property
    def jails(self) -> libzfs.ZFSDataset:
        """Get or create the iocage jails dataset."""
        return self._get_or_create_dataset("jails")

    def activate(
        self,
        mountpoint: typing.Optional[iocage.lib.Types.AbsolutePath]=None
    ) -> None:
        """Activate the root pool and set the given mountpoint."""
        self.activate_pool(self.root.pool, mountpoint)

    def activate_pool(
        self,
        pool: libzfs.ZFSPool,
        mountpoint: typing.Optional[iocage.lib.Types.AbsolutePath]=None
    ) -> None:
        """Activate the given pool and set its mountpoint."""
        if self.is_pool_active(pool):
            msg = f"ZFS pool '{pool.name}' is already active"
            self.logger.warn(msg)

        if not isinstance(pool, libzfs.ZFSPool):
            raise iocage.lib.errors.ZFSPoolInvalid("cannot activate")

        if pool.status == "UNAVAIL":
            raise iocage.lib.errors.ZFSPoolUnavailable(pool.name)

        other_pools = filter(lambda x: x.name != pool.name, self.zfs.pools)
        for other_pool in other_pools:
            self._set_pool_activation(other_pool, False)

        self._set_pool_activation(pool, True)

        if (mountpoint is None) and (os.path.ismount('/iocage') is False):
            self.logger.spam(
                "Claiming /iocage as mountpoint of the activated zpool"
            )
            mountpoint = iocage.lib.Types.AbsolutePath('/iocage')

        if self.root.mountpoint != mountpoint:
            zfs_property = libzfs.ZFSUserProperty(mountpoint)
            self.root.properties["mountpoint"] = zfs_property

    def is_pool_active(
        self,
        pool: typing.Optional[libzfs.ZFSPool]=None
    ) -> bool:
        """Return True if the pool is activated for iocage."""
        if isinstance(pool, libzfs.ZFSPool):
            _pool = pool
        else:
            _pool = self.root.pool

        return iocage.lib.helpers.parse_user_input(self._get_pool_property(
            _pool,
            self.ZFS_POOL_ACTIVE_PROPERTY
        )) is True

    def _get_pool_property(
        self,
        pool: libzfs.ZFSPool,
        prop: str
    ) -> typing.Optional[str]:

        if prop in pool.root_dataset.properties:
            zfs_prop = pool.root_dataset.properties[prop]
            return str(zfs_prop.value)

        return None

    def _get_dataset_property(
        self,
        dataset: libzfs.ZFSDataset,
        prop: str
    ) -> typing.Optional[str]:

        try:
            zfs_prop = dataset.properties[prop]
            return str(zfs_prop.value)
        except KeyError:
            return None

    def deactivate(self) -> None:
        """Deactivate a ZFS pool for iocage use."""
        self._set_pool_activation(self.root.pool, False)

    def _set_pool_activation(self, pool: libzfs.ZFSPool, state: bool) -> None:
        value = "yes" if state is True else "no"
        self._set_zfs_property(
            pool.root_dataset,
            self.ZFS_POOL_ACTIVE_PROPERTY,
            value
        )

    def _set_zfs_property(
        self,
        dataset: libzfs.ZFSDataset,
        name: str,
        value: str
    ) -> None:

        current_value = self._get_dataset_property(dataset, name)
        if current_value != value:
            self.logger.verbose(
                f"Set ZFS property {name}='{value}'"
                f" on dataset '{dataset.name}'"
            )
            dataset.properties[name] = libzfs.ZFSUserProperty(value)

    def _get_or_create_dataset(
        self,
        asset_name: str
    ) -> libzfs.ZFSDataset:
        return self.zfs.get_or_create_dataset(
            f"{self.root.name}/{asset_name}"
        )
        
