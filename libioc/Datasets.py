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
"""ioc datasets module."""
import typing
import os.path
import libzfs

import libioc.errors
import libioc.helpers
import libioc.helpers_object

# MyPy
import libioc.Types
import libioc.ZFS
import libioc.Logger

# MyPy
DatasetIdentifier = typing.Union[str, libzfs.ZFSDataset]
OptionalSourceFilterType = typing.Optional[typing.Tuple[str, ...]]


class RCConfEmptyException(Exception):
    """Exception for internal use."""

    pass


class RootDatasets:
    """
    iocage core dataset abstraction.

    Defined by a ZFSDataset and a given name [#]_, the RootDataset provides
    access to the iocage source datasets. The ability to handle multiple source
    datasets, allows nested iocage usage in other jails.

    .. code-block:: console

        $ sysrc ioc_dataset_ioc="zroot/iocage"
        ioc_dataset_ioc:  -> zroot/iocage
        $ ioc_dataset_nvme:  -> nvme/my-dataset/iocage
        ioc_dataset_nvme:  -> nvme/my-dataset/iocage

    When more than one dataset is enabled, Resource names are displayed
    including their RootDataset prefix (e.g. ``ioc/myjail``).

    .. [#] The ZFS property activated default name is ``ioc``
    """

    zfs: 'libioc.ZFS.ZFS'
    logger: 'libioc.Logger.Logger'
    root: libzfs.ZFSDataset
    _datasets: typing.Dict[str, libzfs.ZFSDataset]

    def __init__(
        self,
        root_dataset: typing.Union[libzfs.ZFSDataset, str],
        zfs: typing.Optional['libioc.ZFS.ZFS']=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)

        self._datasets = {}

        if isinstance(root_dataset, libzfs.ZFSDataset):
            self.root = root_dataset
        elif isinstance(root_dataset, str):
            try:
                self.root = self.zfs.get_dataset(root_dataset)
                _create = False
            except libzfs.ZFSException:
                _create = True

            if _create is True:
                pool_mountpoint = self.zfs.get_dataset(
                    self.zfs.get_pool(root_dataset).name
                ).mountpoint
                preferred_mountpoint = "/iocage"
                preferred_mountpoint_inuse = os.path.ismount(
                    preferred_mountpoint
                ) is True
                if pool_mountpoint is None:
                    if preferred_mountpoint_inuse:
                        raise libioc.errors.ZFSSourceMountpoint(
                            dataset_name=root_dataset,
                            logger=self.logger
                        )

                self.root = self.zfs.create_dataset(root_dataset)

                if preferred_mountpoint_inuse is False:
                    self.logger.spam(
                        "Claiming mountpoint /iocage"
                    )
                    mountpoint = libioc.Types.AbsolutePath(
                        preferred_mountpoint
                    )
                    zfs_property = libzfs.ZFSUserProperty(mountpoint)
                    self.root.properties["mountpoint"] = zfs_property

        if self.root.mountpoint is None:
            raise libioc.errors.ZFSSourceMountpoint(
                dataset_name=self.root.name,
                logger=self.logger
            )

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

    @property
    def pkg(self) -> libzfs.ZFSDataset:
        """Get or create the pkg cache."""
        return self._get_or_create_dataset("pkg")

    def _get_or_create_dataset(
        self,
        asset_name: str
    ) -> libzfs.ZFSDataset:
        if asset_name in self._datasets:
            return self._datasets[asset_name]

        asset = self.zfs.get_or_create_dataset(
            f"{self.root.name}/{asset_name}"
        )
        _asset: libzfs.ZFSDataset = asset
        self._datasets[asset_name] = _asset
        return _asset


class Datasets(dict):
    """
    All source datasets managed by libioc.

    Automatically detects activated iocage datasets from ZFS pool properties
    or sysrc lines in ``/etc/rc.conf``.

    Operations that should be performed on selected iocage datasets, are
    typically achieved by filtering Datasets. Only the matching and activated
    datasets are then taken into account and thus result in a performance
    benefit.

    The iocage dataset configuration from sysrc wins over ZFS pools activated
    by the `org.freebsd.ioc:active` property on their pool root dataset.
    """

    zfs: 'libioc.ZFS.ZFS'
    logger: 'libioc.Logger.Logger'

    main_datasets_name: typing.Optional[str]
    _rc_conf_enabled: bool

    ZFS_POOL_ACTIVE_PROPERTY: str = "org.freebsd.ioc:active"

    def __init__(
        self,
        sources: typing.Optional[
            typing.Dict[str, typing.Union[str, libzfs.ZFSDataset]]
        ]=None,
        zfs: typing.Optional['libioc.ZFS.ZFS']=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        dict.__init__(self)
        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)
        self.main_datasets_name = None

        # assume being managed by rc_conf unless later detection fails
        self._rc_conf_enabled = True

        if sources is not None:
            self.attach_sources(sources)
            return

        try:
            self._configure_from_rc_conf()
            return
        except RCConfEmptyException:
            self._rc_conf_enabled = False
            pass

        try:
            self._configure_from_pool_property()
            return
        except libioc.errors.IocageNotActivated:
            pass

        self.logger.spam("No iocage root dataset configuration found")

    def _configure_from_rc_conf(self) -> None:
        enabled_datasets = self._read_root_datasets_from_rc_conf()
        if len(enabled_datasets) == 0:
            raise RCConfEmptyException()

        _e: typing.Dict[str, typing.Union[str, libzfs.ZFSDataset]] = {}
        for key, value in enabled_datasets.items():
            _e[key] = value
        self.attach_sources(_e)

    def _configure_from_pool_property(self) -> None:
        active_pool = self._active_pool_or_none
        if active_pool is None:
            # raise internally without logging
            raise libioc.errors.IocageNotActivated()
        self.attach_sources(dict(ioc=f"{self.active_pool.name}/iocage"))
        self.logger.spam(f"Found active ZFS pool {self.active_pool.name}")

    @property
    def main(self) -> 'libioc.Datasets.Datasets':
        """Return the source that was attached first."""
        if self.main_datasets_name is None:
            raise libioc.errors.IocageNotActivated(logger=self.logger)
        return self[self.main_datasets_name]

    def find_root_datasets_name(self, dataset_name: str) -> str:
        """Return the name of the source containing the matching dataset."""
        for source_name, source_datasets in self.items():
            if dataset_name == source_datasets.root.name:
                return str(source_name)
            elif dataset_name.startswith(f"{source_datasets.root.name}/"):
                return str(source_name)
        raise libioc.errors.ResourceUnmanaged(
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
    ) -> 'libioc.Datasets.Datasets':
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
        """
        Attach a source by its DatasetIdentifier to the iocage scope.

        Args:

            source_name:
                Name of the source dataset.

            dataset_identifier:
                ZFSDataset structure or dataset name representing the source.
        """
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
        """
        Attach another RootDatasets object to the iocage scope.

        Args:

            source_name:
                Name of the source dataset.

            root_datasets:
                Instance of :class:`~libioc.Datasets.RootDatasets`.
        """
        self[source_name] = root_datasets
        if self.main_datasets_name is None:
            self.main_datasets_name = source_name

    def _read_root_datasets_from_rc_conf(self) -> typing.Dict[str, str]:
        prefix = "ioc_dataset_"

        import libioc.Config.Host
        rc_conf = libioc.Config.Host.rc_conf
        rc_conf_keys = list(filter(lambda x: x.startswith(prefix), rc_conf))

        output: typing.Dict[str, str] = {}
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
            raise libioc.errors.IocageNotActivated(logger=self.logger)
        return pool

    def activate(
        self,
        mountpoint: typing.Optional[libioc.Types.AbsolutePath]=None
    ) -> None:
        """
        Activate the root pool and set the given mountpoint.

        Args:

            mountpoint:
                see :meth:`~libioc.Datasets.Datasets.activate_pool`
        """
        self.activate_pool(self.main.root.pool, mountpoint)

    def activate_pool(
        self,
        pool: libzfs.ZFSPool,
        mountpoint: typing.Optional[libioc.Types.AbsolutePath]=None
    ) -> None:
        """
        Activate the given pool and set its mountpoint.

        Pool activation follows the traditional way of setting a ZFS property
        on the pool that other iocage variants will detect.

        The mechanism cannot be combined with iocage datasets defined in
        /etc/rc.conf, so that using the Multi-Pool feature is not possible.
        When attemptig to activate a pool on a system with such configuration
        an ActivationFailed error is raised.

        Args:

            pool:

                Target of the iocage activation on which an iocage dataset
                is created on the top level (e.g. zfs create <pool>/iocage)

            mountpoint:

                The desired mountpoint for the iocage dataset.
        """
        if self._rc_conf_enabled is True:
            raise libioc.errors.ActivationFailed(
                "iocage ZFS source datasets are managed in /etc/rc.conf",
                logger=self.logger
            )

        if self.is_pool_active(pool):
            msg = f"ZFS pool '{pool.name}' is already active"
            self.logger.warn(msg)

        if not isinstance(pool, libzfs.ZFSPool):
            raise libioc.errors.ZFSPoolInvalid("cannot activate")

        if pool.status == "UNAVAIL":
            raise libioc.errors.ZFSPoolUnavailable(pool.name)

        other_pools = filter(lambda x: x.name != pool.name, self.zfs.pools)
        for other_pool in other_pools:
            self._set_pool_activation(other_pool, False)

        self._set_pool_activation(pool, True)
        self.attach_source("iocage", f"{pool.name}/iocage")

        if self.main.root.mountpoint != mountpoint:
            zfs_property = libzfs.ZFSUserProperty(mountpoint)
            self.main.root.properties["mountpoint"] = zfs_property

    def is_pool_active(
        self,
        pool: typing.Optional[libzfs.ZFSPool]=None
    ) -> bool:
        """
        Return True if the pool is activated for libioc.

        Args:

            pool:

                The specified pool is checked for being activated for libioc.
                When the pool is unset, the main pool is tested against.

        """
        if isinstance(pool, libzfs.ZFSPool):
            return self._is_pool_active(pool)
        else:
            return self._is_pool_active(self.main.root.pool)

    def _is_pool_active(self, pool: libzfs.ZFSPool) -> bool:
        return libioc.helpers.parse_user_input(self._get_pool_property(
            pool,
            self.ZFS_POOL_ACTIVE_PROPERTY
        )) is True

    def _get_pool_property(
        self,
        pool: libzfs.ZFSPool,
        prop: str
    ) -> typing.Optional[str]:

        if pool.status not in ["ONLINE", "DEGRADED"]:
            self.logger.verbose(
                f"The pool {pool.name} is {pool.status} and will be ignored"
            )
            return None

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
            No filters were applied when unset.
            The names contained in the Tuple are matched against the
            dataset names specified in rc.conf.

            .. code-block:: console

                $ sysrc ioc_dataset_main="zroot/iocage"
                $ ioc list --source main

        zfs:
            The shared ZFS object.

        logger:
            The shared logger instance.
    """

    _source_filters: OptionalSourceFilterType
    datasets: Datasets

    def __init__(
        self,
        datasets: Datasets,
        source_filters: OptionalSourceFilterType=None,
        zfs: typing.Optional['libioc.ZFS.ZFS']=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)
        self.datasets = datasets

        self._source_filters = None
        self.source_filters = source_filters

    @property
    def source_filters(self) -> OptionalSourceFilterType:
        """Return the active source filters or None."""
        return self._source_filters  # noqa: T484

    @source_filters.setter
    def source_filters(self, value: OptionalSourceFilterType) -> None:
        """Set or disable source filters."""
        self.clear()
        self._source_filters = value
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
