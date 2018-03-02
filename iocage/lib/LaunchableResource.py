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
"""iocage module for launchable resources."""
import libzfs
import typing

import iocage.lib.Config.Jail.File.RCConf
import iocage.lib.Config.Jail.File.SysctlConf
import iocage.lib.Resource
import iocage.lib.ResourceUpdater

# MyPy
import iocage.lib.Config.Jail.JailConfig
import iocage.lib.Config.Jail.File


class LaunchableResource(iocage.lib.Resource.Resource):
    """Representation of launchable resources like jails."""

    _rc_conf: typing.Optional[iocage.lib.Config.Jail.File.RCConf.RCConf] = None
    _sysctl_conf: typing.Optional[
        iocage.lib.Config.Jail.File.SysctlConf.SysctlConf
    ] = None
    _distribution: 'iocage.lib.Distribution.Distribution' = None
    _updater: 'iocage.lib.ResourceUpdater.LaunchableResourceUpdate' = None
    config: iocage.lib.Config.Jail.JailConfig.JailConfig

    def __init__(
        self,
        distribution: typing.Optional[
            'iocage.lib.Distribution.Distribution'
        ]=None,
        **kwargs  # noqa: T484
    ) -> None:
        self._distribution = distribution
        iocage.lib.Resource.Resource.__init__(self, **kwargs)

    @property
    def updater(
        self
    ) -> iocage.lib.ResourceUpdater.Updater:
        """Return the lazy-loaded resource updater."""
        if self._updater is not None:
            return self._updater

        if self._distribution is None:
            self._distribution = iocage.lib.helpers.init_distribution(self)
        updater = iocage.lib.ResourceUpdater.get_launchable_update_resource(
            resource=self,
            distribution=self._distribution
        )
        self._updater = updater
        return updater

    def _require_dataset_mounted(self, dataset: libzfs.ZFSDataset) -> None:
        if dataset.mountpoint is None:
            raise iocage.lib.errors.DatasetNotMounted(
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
    def rc_conf(self) -> 'iocage.lib.Config.Jail.File.RCConf.RCConf':
        """Return a lazy-loaded instance of the resources RCConf."""
        if self._rc_conf is None:
            self._rc_conf = iocage.lib.Config.Jail.File.RCConf.RCConf(
                resource=self,
                logger=self.logger
            )
        return self._rc_conf

    @property
    def sysctl_conf(
        self
    ) -> 'iocage.lib.Config.Jail.File.SysctlConf.SysctlConf':
        """Return a lazy-loaded instance of the resources SysctlConf."""
        if self._sysctl_conf is None:
            sysctl_conf = iocage.lib.Config.Jail.File.SysctlConf.SysctlConf(
                resource=self,
                logger=self.logger
            )
            self._sysctl_conf = sysctl_conf
        return self._sysctl_conf
