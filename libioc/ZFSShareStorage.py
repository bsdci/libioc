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
"""ioc ZFS share storage backend."""
import typing
import libzfs
import shlex

import libioc.errors
import libioc.helpers
import libioc.helpers_object


class ZFSShareStorage:
    """Storage backend for ZFS shares."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        logger: typing.Optional['libioc.Logger.Logger']=None,
        zfs: typing.Optional['libioc.ZFS.ZFS']=None
    ) -> None:

        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)
        self.jail = jail

    def mount_zfs_shares(
        self,
        auto_create: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.JailZFSShare', None, None]:
        """Invoke mounting the ZFS shares."""
        event = libioc.events.JailZFSShare(
            jail=self.jail,
            scope=event_scope
        )
        yield event.begin()
        try:
            self._require_datasets_exist_and_jailed()
        except libioc.errors.DatasetNotJailed:
            yield event.fail("ZFS dataset not jailed")
            raise

        yield from self._mount_jail_datasets(auto_create=auto_create)

        yield event.end()

    def get_zfs_datasets(
        self,
        auto_create: bool=False
    ) -> typing.List[libzfs.ZFSDataset]:
        """Get the shared ZFS datasets."""
        dataset_names = self.jail.config["jail_zfs_dataset"]

        datasets = set()
        for name in dataset_names:

            if auto_create is True:
                try:
                    zpool = self._get_pool_from_dataset_name(name)
                except libioc.errors.ZFSPoolUnavailable:
                    # legacy support (datasets not prefixed with pool/)
                    zpool = self.jail.pool
                    name = f"{self.jail.pool_name}/{name}"

                try:
                    zpool.create(name, {}, create_ancestors=True)
                except libzfs.ZFSException:
                    pass

            try:
                dataset = self.zfs.get_dataset(name)
                datasets.add(dataset)
            except libzfs.ZFSException:
                raise libioc.errors.DatasetNotAvailable(
                    dataset_name=name,
                    logger=self.logger
                )

        return list(datasets)

    def _mount_jail_datasets(
        self,
        auto_create: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.AttachZFSDataset', None, None]:

        for dataset in self.get_zfs_datasets():

            event = libioc.events.AttachZFSDataset(
                jail=self.jail,
                dataset=dataset,
                scope=event_scope
            )
            yield event.begin()

            self.logger.verbose(f"Mounting ZFS Dataset {dataset.name}")
            self._umount_dataset(dataset)

            # ToDo: bake jail feature into py-libzfs
            self._exec(
                self._zfs_jail_command + [shlex.quote(dataset.name)],
                logger=self.logger
            )

            yield event.end()

        self._exec_jail(["/sbin/zfs", "mount", "-a"])

    @property
    def _zfs_jail_command(self) -> typing.List[str]:
        return ["/sbin/zfs", "jail", str(self.jail.jid)]

    @property
    def _zfs_unjail_command(self) -> typing.List[str]:
        return ["/sbin/zfs", "unjail", str(self.jail.jid)]

    def _get_pool_name_from_dataset_name(
        self,
        dataset_name: str
    ) -> str:

        return dataset_name.split("/", maxsplit=1)[0]

    def _get_pool_from_dataset_name(
        self,
        dataset_name: str
    ) -> libzfs.ZFSPool:

        target_pool_name = self._get_pool_name_from_dataset_name(dataset_name)

        zpools: typing.List[libzfs.ZFSPool] = list(self.zfs.pools)
        for zpool in zpools:
            if zpool.name == target_pool_name:
                return zpool

        # silent exception, no logger defined
        raise libioc.errors.ZFSPoolUnavailable(
            pool_name=target_pool_name,
            logger=self.logger
        )

    def _require_datasets_exist_and_jailed(self) -> None:

        existing_datasets = self.get_zfs_datasets(auto_create=False)
        for existing_dataset in existing_datasets:
            if existing_dataset.properties["jailed"].value != "on":
                raise libioc.errors.DatasetNotJailed(
                    dataset=existing_dataset,
                    logger=self.logger
                )

    def _umount_dataset(self, dataset: libzfs.ZFSDataset) -> None:
        if dataset.mountpoint is not None:
            dataset.umount()

    def _exec(
        self,
        command: typing.List[str],
        **exec_arguments: typing.Dict[str, typing.Any]
    ) -> 'libioc.helpers.CommandOutput':
        return libioc.helpers.exec(command, **exec_arguments)

    def _exec_jail(
        self,
        command: typing.List[str]
    ) -> 'libioc.helpers.CommandOutput':
        self.jail.exec(command)
