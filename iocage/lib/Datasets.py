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

# MyPy
DatasetIdentifier = typing.Union[str, libzfs.ZFSDataset]
OptionalSourceFilterType = typing.Optional[typing.Tuple[str, ...]]


class RCConfEmptyException(Exception):
    """Exception for internal use."""

    pass


class RootDatasets:
    """iocage core dataset abstraction."""

    zfs: 'iocage.lib.ZFS.ZFS'
    logger: 'iocage.lib.Logger.Logger'
    root: libzfs.ZFSDataset
    _datasets: typing.Dict[str, libzfs.ZFSDataset]

    def __init__(
        self,
        root_dataset: typing.Union[libzfs.ZFSDataset, str],
        zfs: typing.Optional[iocage.lib.ZFS.ZFS]=None,
        logger: typing.Optional[iocage.lib.Logger.Logger]=None
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)

        self._datasets = {}

        if isinstance(root_dataset, libzfs.ZFSDataset):
            self.root = root_dataset
        elif isinstance(root_dataset, str):
            self.root = self.zfs.get_or_create_dataset(root_dataset)

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

    def _get_or_create_dataset(
        self,
        asset_name: str
    ) -> libzfs.ZFSDataset:
        if asset_name in self._datasets:
            return self._datasets[asset_name]

        asset = self.zfs.get_or_create_dataset(
            f"{self.root.name}/{asset_name}"
        )
        self._datasets[asset_name] = asset
        return asset


class Datasets(dict):
    """All source datasets managed by iocage."""

    zfs: 'iocage.lib.ZFS.ZFS'
    logger: 'iocage.lib.Logger.Logger'

    main_datasets_name: typing.Optional[str]

    ZFS_POOL_ACTIVE_PROPERTY: str = "org.freebsd.ioc:active"

    def __init__(
        self,
        zfs: typing.Optional[iocage.lib.ZFS.ZFS]=None,
        logger: typing.Optional[iocage.lib.Logger.Logger]=None
    ) -> None:

        dict.__init__(self)
        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)
        self.main_datasets_name = None

        try:
            self._configure_from_rc_conf()
        except RCConfEmptyException:
            self._configure_from_pool_property()

    def _configure_from_rc_conf(self) -> None:
        enabled_datasets = self._read_root_datasets_from_rc_conf()
        if len(enabled_datasets) == 0:
            raise RCConfEmptyException()
        self.attach_sources(enabled_datasets)

    def _configure_from_pool_property(self) -> None:
        self.attach_sources(dict(iocage=self.active_pool))

    @property
    def main(self) -> 'iocage.lib.Datasets.Datasets':
        """Return the source that was attached first."""
        return self[self.main_datasets_name]

    def find_root_datasets_name(self, dataset_name: str) -> str:
        """Return the name of the source containing the matching dataset."""
        for source_name, source_datasets in self.items():
            if dataset_name.startswith(source_datasets.root.name):
                return str(source_name)
        raise iocage.lib.errors.ResourceUnmanaged(
            dataset_name=dataset_name,
            logger=self.logger
        )

    def find_root_datasets(self, dataset_name: str) -> RootDatasets:
        """Return the RootDatasets instance containing the dataset."""
        root_datasets_name = self.find_root_datasets_name(dataset_name)
        root_datasets: RootDatasets = self.__getitem__(root_datasets_name)
        return root_datasets

    def get_root_source(
        self,
        source_name: typing.Optional[str]=None
    ) -> 'iocage.lib.Datasets.Datasets':
        """
        Get the root source with a certain name.

        When the source name is empty, the main source is returned.
        """
        if source_name is None:
            return self.main
        return self[source_name]

    def attach_sources(
        self,
        sources: typing.Dict[str, DatasetIdentifier]
    ) -> None:
        """Attach a sources dictionary at once."""
        for key, dataset_identifier in sources.items():
            self.attach_source(key, dataset_identifier)

    def attach_source(
        self,
        source_name: str,
        dataset_identifier: DatasetIdentifier
    ) -> None:
        """Attach a source by its DatasetIdentifier to the iocage scope."""
        self.attach_root_datasets(
            source_name=source_name,
            root_datasets=RootDatasets(
                root_dataset=dataset_identifier,
                zfs=self.zfs,
                logger=self.logger
            )
        )

    def attach_root_datasets(
        self,
        source_name: str,
        root_datasets: RootDatasets
    ) -> None:
        """Attach another RootDatasets object to the iocage scope."""
        self[source_name] = root_datasets
        if self.main_datasets_name is None:
            self.main_datasets_name = source_name

    def _read_root_datasets_from_rc_conf(self) -> typing.Dict[str, str]:
        prefix = "ioc_dataset_"

        import iocage.lib.Config.Jail.File.RCConf
        rc_conf = iocage.lib.Config.Jail.File.RCConf.RCConf(
            logger=self.logger
        )
        rc_conf_keys = list(filter(lambda x: x.startswith(prefix), rc_conf))

        output = dict()
        for rc_conf_key in rc_conf_keys:
            datasets_name = rc_conf_key[len(prefix):]
            output[datasets_name] = rc_conf[rc_conf_key]
        return output

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
        pool = self._active_pool_or_none
        if pool is None:
            raise iocage.lib.errors.IocageNotActivated(logger=self.logger)
        return pool

    def activate(
        self,
        mountpoint: typing.Optional[iocage.lib.Types.AbsolutePath]=None
    ) -> None:
        """Activate the root pool and set the given mountpoint."""
        self.activate_pool(self.main.root.pool, mountpoint)

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

        if self.main.root.mountpoint != mountpoint:
            zfs_property = libzfs.ZFSUserProperty(mountpoint)
            self.main.root.properties["mountpoint"] = zfs_property

    def is_pool_active(
        self,
        pool: typing.Optional[libzfs.ZFSPool]=None
    ) -> bool:
        """Return True if the pool is activated for iocage."""
        if isinstance(pool, libzfs.ZFSPool):
            _pool = pool
        else:
            _pool = self.main.root.pool

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
        self._set_pool_activation(self.main.root.pool, False)

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


class FilteredDatasets(Datasets):
    """
    A wrapper around Datasets that limits access to certain root datasets.

    Args:

        datasets:
            The Datasets hosts instance

        source_filters:
            No filters were applied when unset. The names contained in the
            Tuple are matched against the dataset names specified in rc.conf.

            For example:
                echo 'ioc_dataset_main="zroot/iocage"' >> /etc/rc.conf
                ioc list --source main

        zfs:
            The shared ZFS object.

        logger:
            The shared logger instance.
    """

    _source_filters = OptionalSourceFilterType
    datasets: Datasets

    def __init__(
        self,
        datasets: Datasets,
        source_filters: OptionalSourceFilterType=None,
        zfs: typing.Optional[iocage.lib.ZFS.ZFS]=None,
        logger: typing.Optional[iocage.lib.Logger.Logger]=None
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)
        self.datasets = datasets
        self.source_filters = source_filters

    @property
    def source_filters(self) -> OptionalSourceFilterType:
        """Return the active source filters or None."""
        return self._source_filters  # noqa: T484

    @source_filters.setter
    def source_filters(self, value: OptionalSourceFilterType) -> None:
        """Set or disable source filters."""
        self.clear()
        self._source_filters = value  # noqa: T484
        self._clone_from_datasets()

    def _clone_from_datasets(self) -> None:
        self.main_datasets_name = self.datasets.main_datasets_name
        for name, root_datasets in self.datasets.items():
            if self._name_matches_filters(name) is True:
                self.attach_root_datasets(name, root_datasets)

    def _name_matches_filters(self, name: str) -> bool:
        return (self.source_filters is None) or (name in self.source_filters)


def filter_datasets(
    datasets: Datasets,
    sources: OptionalSourceFilterType
) -> FilteredDatasets:
    """Return FilteredDatasets by a tuple of sources."""
    return FilteredDatasets(
        datasets=datasets,
        source_filters=sources,
        zfs=datasets.zfs,
        logger=datasets.logger
    )
