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
"""iocage Host module."""
import typing
import os
import platform
import re
import sysctl

import libzfs

import iocage.lib.Datasets
import iocage.lib.DevfsRules
import iocage.lib.Distribution
import iocage.lib.Resource
import iocage.lib.helpers

# MyPy
import iocage.lib.Config.Jail.BaseConfig  # noqa: F401
import iocage.lib.DevfsRules
_distribution_types = typing.Union[
    iocage.lib.Distribution.DistributionGenerator,
    iocage.lib.Distribution.Distribution,
]


class HostGenerator:
    """Asynchronous representation of the jail host."""

    _class_distribution = iocage.lib.Distribution.DistributionGenerator

    _devfs: iocage.lib.DevfsRules.DevfsRules
    _defaults: iocage.lib.Resource.DefaultResource
    _defaults_initialized = False
    releases_dataset: libzfs.ZFSDataset
    datasets: iocage.lib.Datasets.Datasets
    distribution: _distribution_types

    branch_pattern = re.compile(
        r"""\(hardened/
        (?P<release>[A-z0-9]+(?:[A-z0-9\-]+[A-z0-9]))
        /
        (?P<branch>[A-z0-9]+)
        \):""",
        re.X
    )

    release_name_pattern = re.compile(
        r"^(?P<major>\d+)(?:\.(?P<minor>\d+))-(?P<type>[A-Z]+)-HBSD$",
        re.X
    )

    def __init__(
        self,
        defaults: typing.Optional[iocage.lib.Resource.DefaultResource]=None,
        zfs: typing.Optional[iocage.lib.ZFS.ZFS]=None,
        logger: typing.Optional[iocage.lib.Logger.Logger]=None
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)

        self.datasets = iocage.lib.Datasets.Datasets(
            logger=self.logger,
            zfs=self.zfs
        )

        self.distribution = self._class_distribution(
            host=self,
            logger=self.logger,
            zfs=self.zfs
        )

        self._init_defaults(defaults)

    def _init_defaults(
        self,
        defaults: typing.Optional[iocage.lib.Resource.DefaultResource]=None
    ) -> None:

        if defaults is not None:
            self._defaults = defaults
        else:
            self._defaults = iocage.lib.Resource.DefaultResource(
                dataset=self.datasets.main.root,
                logger=self.logger,
                zfs=self.zfs
            )

    @property
    def defaults(self) -> 'iocage.lib.Resource.DefaultResource':
        """Return the lazy-loaded defaults."""
        if self._defaults_initialized is False:
            self._defaults.read_config()
            self._defaults_initialized = True
        return self._defaults

    @property
    def default_config(
        self
    ) -> 'iocage.lib.Config.Jail.BaseConfig.BaseConfig':
        """Return the lazy-loaded default configuration."""
        return self.defaults.config

    @property
    def devfs(self) -> 'iocage.lib.DevfsRules.DevfsRules':
        """Return the lazy-loaded DevfsRules instance."""
        if "_devfs" not in dir(self):
            self._devfs = iocage.lib.DevfsRules.DevfsRules(
                logger=self.logger
            )
        return self._devfs

    @property
    def userland_version(self) -> float:
        """Return the host userland version number."""
        return float(iocage.lib.helpers.get_userland_version())

    @property
    def release_version(self) -> str:
        """Return the host release version."""
        if self.distribution.name == "FreeBSD":
            release_version_string = os.uname()[2]
            release_version_fragments = release_version_string.split("-")

            if len(release_version_fragments) > 1:
                return "-".join(release_version_fragments[0:2])

        elif self.distribution.name == "HardenedBSD":

            match = re.search(self.branch_pattern, os.uname()[3])
            if match is not None:
                return match["release"].upper()

            match = re.search(self.release_name_pattern, os.uname()[2])
            if match is not None:
                return f"{match['major']}-{match['type']}"

        raise iocage.lib.errors.HostReleaseUnknown()

    @property
    def processor(self) -> str:
        """Return the hosts processor architecture."""
        return platform.processor()

    @property
    def ipfw_enabled(self):
        _sysctl = sysctl.filter("net.inet.ip.fw.enable")
        return ((len(_sysctl) == 1) and (_sysctl[0].value == 1))


class Host(HostGenerator):
    """Synchronous wrapper of HostGenerator."""

    _class_distribution = iocage.lib.Distribution.Distribution
