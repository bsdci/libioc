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
import re

import libzfs

import iocage.lib.Datasets
import iocage.lib.DevfsRules
import iocage.lib.Distribution
import iocage.lib.Resource
import iocage.lib.helpers

# MyPy
import iocage.lib.Config.Jail.BaseConfig  # noqa: F401


class HostGenerator:

    _class_distribution = iocage.lib.Distribution.DistributionGenerator

    _devfs: 'iocage.lib.DevfsRules.DevfsRules'
    _defaults: 'iocage.lib.Resource.DefaultResource'
    releases_dataset: libzfs.ZFSDataset

    def __init__(
        self,
        root_dataset: libzfs.ZFSDataset=None,
        defaults: 'iocage.lib.Resource.DefaultResource'=None,
        zfs: 'iocage.lib.ZFS.ZFS'=None,
        logger: 'iocage.lib.Logger.Logger'=None
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)

        self.datasets = iocage.lib.Datasets.Datasets(
            root=root_dataset,
            logger=self.logger,
            zfs=self.zfs
        )
        self.distribution = self._class_distribution(
            host=self,
            logger=self.logger
        )
        if defaults is not None:
            self._defaults = defaults

    @property
    def defaults(self) -> 'iocage.lib.Resource.DefaultResource':
        if "_defaults" not in dir(self):
            self._defaults = self._load_defaults()
        return self._defaults

    @property
    def default_config(
        self
    ) -> 'iocage.lib.Config.Jail.BaseConfig.BaseConfig':
        return self.defaults.config

    def _load_defaults(self) -> 'iocage.lib.Resource.DefaultResource':
        defaults_resource = iocage.lib.Resource.DefaultResource(
            dataset=self.datasets.root,
            logger=self.logger,
            zfs=self.zfs
        )
        defaults_resource.config.read(data=defaults_resource.read_config())
        return defaults_resource

    @property
    def devfs(self) -> 'iocage.lib.DevfsRules.DevfsRules':
        """
        Lazy-loaded DevfsRules instance
        """
        if "_devfs" not in dir(self):
            self._devfs = iocage.lib.DevfsRules.DevfsRules(
                logger=self.logger
            )
        return self._devfs

    @property
    def userland_version(self) -> float:
        return float(self.release_version.partition("-")[0])

    @property
    def release_version(self):

        if self.distribution.name == "FreeBSD":
            release_version_string = os.uname()[2]
            release_version_fragments = release_version_string.split("-")

            if len(release_version_fragments) > 1:
                return "-".join(release_version_fragments[0:2])

        elif self.distribution.name == "HardenedBSD":
            pattern = re.compile(
                r"""\(hardened\/
                    (?P<release>[A-z0-9]+(?:[A-z0-9\-]+[A-z0-9]))
                    \/
                    (?P<branch>[A-z0-9]+)
                    \):""", re.X)

            return re.search(pattern, os.uname()[3])["release"].upper()

    @property
    def processor(self) -> str:
        return platform.processor()


class Host(HostGenerator):

    _class_distribution = iocage.lib.Distribution.Distribution
