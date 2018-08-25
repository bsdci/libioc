# Copyright (c) 2014-2018, iocage
# Copyright (c) 2017-2018, Stefan Grönke
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
"""iocage module for launchable resources."""
import libzfs
import typing

import iocage.helpers_object
import iocage.Resource
import iocage.ResourceBackup


class LaunchableResource(iocage.Resource.Resource):
    """Representation of launchable resources like jails."""

    _rc_conf: typing.Optional[
        'iocage.Config.Jail.File.RCConf.ResourceRCConf'
    ]
    _sysctl_conf: typing.Optional[
        'iocage.Config.Jail.File.SysctlConf.SysctlConf'
    ]
    host: 'iocage.Host.HostGenerator'
    _updater: typing.Optional[
        'iocage.ResourceUpdater.LaunchableResourceUpdate'
    ]
    _backup: typing.Optional[
        'iocage.ResourceBackup.LaunchableResourceBackup'
    ]
    config: 'iocage.Config.Jail.JailConfig.JailConfig'

    def __init__(
        self,
        dataset: typing.Optional[libzfs.ZFSDataset]=None,
        dataset_name: typing.Optional[str]=None,
        config_type: str="auto",
        config_file: typing.Optional[str]=None,
        logger: typing.Optional['iocage.Logger.Logger']=None,
        zfs: typing.Optional[iocage.ZFS.ZFS]=None,
        host: typing.Optional[
            'iocage.Host.HostGenerator'
        ]=None,
    ) -> None:
        self.host = iocage.helpers_object.init_host(self, host)
        self._updater = None
        self._backup = None
        self._rc_conf = None
        self._sysctl_conf = None
        self._updater = None
        self._backup = None
        iocage.Resource.Resource.__init__(
            self,
            dataset=dataset,
            dataset_name=dataset_name,
            config_type=config_type,
            config_file=config_file,
            logger=logger,
            zfs=zfs
        )

    @property
    def updater(
        self
    ) -> 'iocage.ResourceUpdater.Updater':
        """Return the lazy-loaded resource updater."""
        if self._updater is not None:
            return self._updater

        updater = iocage.ResourceUpdater.get_launchable_update_resource(
            resource=self,
            host=self.host
        )
        self._updater = updater
        return updater

    @property
    def backup(
        self
    ) -> 'iocage.ResourceUpdater.Updater':
        """Return the lazy-loaded resource backup tool."""
        if self._backup is not None:
            return self._backup

        backup = iocage.ResourceBackup.LaunchableResourceBackup(
            resource=self
        )
        self._backup = backup
        return backup

    def _require_dataset_mounted(self, dataset: libzfs.ZFSDataset) -> None:
        if dataset.mountpoint is None:
            raise iocage.errors.DatasetNotMounted(
                dataset=dataset,
                logger=self.logger
            )

    @property
    def root_path(self) -> str:
        """Return the absolute path to the root filesystem of a jail."""
        return str(self.root_dataset.mountpoint)

    @property
    def root_dataset(self) -> libzfs.ZFSDataset:
        """Return the resources root dataset."""
        # ToDo: Memoize root_dataset
        root_dataset = self.get_dataset("root")  # type: libzfs.ZFSDataset
        self._require_dataset_mounted(root_dataset)
        return root_dataset

    @property
    def root_dataset_name(self) -> str:
        """
        Return the resources root dataset name.

        The root dasaset has the name `root` and is always a direct ancestor
        of a resources top-level dataset.
        """
        return f"{self.dataset_name}/root"

    @property
    def dataset_name(self) -> str:
        """Return the resources dataset name."""
        raise NotImplementedError(
            "This needs to be implemented by the inheriting class"
        )

    @dataset_name.setter
    def dataset_name(self, value: str) -> None:
        """Interface for setting a resources dataset name."""
        raise NotImplementedError(
            "This needs to be implemented by the inheriting class"
        )

    @property
    def rc_conf(self) -> 'iocage.Config.Jail.File.RCConf.ResourceRCConf':
        """Return a lazy-loaded instance of the resources RCConf."""
        if self._rc_conf is None:
            import iocage.Config.Jail.File.RCConf
            self._rc_conf = iocage.Config.Jail.File.RCConf.ResourceRCConf(
                resource=self,
                logger=self.logger
            )
        return self._rc_conf

    @property
    def sysctl_conf(
        self
    ) -> 'iocage.Config.Jail.File.SysctlConf.SysctlConf':
        """Return a lazy-loaded instance of the resources SysctlConf."""
        if self._sysctl_conf is None:
            import iocage.Config.Jail.File.SysctlConf
            sysctl_conf = iocage.Config.Jail.File.SysctlConf.SysctlConf(
                resource=self,
                logger=self.logger
            )
            self._sysctl_conf = sysctl_conf
        return self._sysctl_conf
