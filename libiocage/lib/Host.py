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
import os
import platform

import libzfs

import libiocage.lib.Datasets
import libiocage.lib.DevfsRules
import libiocage.lib.Distribution
import libiocage.lib.Resource
import libiocage.lib.helpers

# MyPy
import libiocage.lib.Config.Jail.BaseConfig  # noqa: F401


class HostGenerator:

    _class_distribution = libiocage.lib.Distribution.DistributionGenerator

    _devfs: 'libiocage.lib.DevfsRules.DevfsRules'
    releases_dataset: libzfs.ZFSDataset

    def __init__(
        self,
        root_dataset: libzfs.ZFSDataset=None,
        defaults: 'libiocage.lib.Resource.DefaultResource'=None,
        zfs: 'libiocage.lib.ZFS.ZFS'=None,
        logger: 'libiocage.lib.Logger.Logger'=None
    ) -> None:

        self.logger = libiocage.lib.helpers.init_logger(self, logger)
        self.zfs = libiocage.lib.helpers.init_zfs(self, zfs)

        self.datasets = libiocage.lib.Datasets.Datasets(
            root=root_dataset,
            logger=self.logger,
            zfs=self.zfs
        )
        self.distribution = self._class_distribution(
            host=self,
            logger=self.logger
        )
        self._defaults = defaults if defaults is not None \
            else libiocage.lib.Resource.DefaultResource(
                    dataset=self.datasets.root,
                    logger=self.logger,
                    zfs=self.zfs
            )

    @property
    def defaults(self) -> 'libiocage.lib.Resource.DefaultResource':
        if self._defaults is None:
            self._defaults = self._load_defaults()
        return self._defaults

    @property
    def default_config(
        self
    ) -> 'libiocage.lib.Config.Jail.BaseConfig.BaseConfig':
        return self.defaults.config

    def _load_defaults(self) -> 'libiocage.lib.Resource.DefaultResource':
        defaults_resource = libiocage.lib.Resource.DefaultResource(
            dataset=self.datasets.root,
            logger=self.logger,
            zfs=self.zfs
        )
        defaults_resource.config.read(data=defaults_resource.read_config())
        return defaults_resource

    @property
    def devfs(self) -> 'libiocage.lib.DevfsRules.DevfsRules':
        """
        Lazy-loaded DevfsRules instance
        """
        if self._devfs is None:
            self._devfs = libiocage.lib.DevfsRules.DevfsRules(
                logger=self.logger
            )
        return self._devfs

    @property
    def userland_version(self):
        return float(self.release_version.partition("-")[0])

    @property
    def release_minor_version(self):
        release_version_string = os.uname()[2]
        release_version_fragments = release_version_string.split("-")

        if len(release_version_fragments) < 3:
            return 0

        return int(release_version_fragments[2])

    @property
    def release_version(self):
        release_version_string = os.uname()[2]
        release_version_fragments = release_version_string.split("-")

        if len(release_version_fragments) > 1:
            return "-".join(release_version_fragments[0:2])

    @property
    def processor(self):
        return platform.processor()


class Host(HostGenerator):

    _class_distribution = libiocage.lib.Distribution.Distribution
