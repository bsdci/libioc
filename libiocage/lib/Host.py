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

import libiocage.lib.Datasets
import libiocage.lib.DevfsRules
import libiocage.lib.Distribution
import libiocage.lib.helpers


class HostGenerator:

    _class_distribution = libiocage.lib.Distribution.DistributionGenerator

    def __init__(self, root_dataset=None, zfs=None, logger=None):

        libiocage.lib.helpers.init_logger(self, logger)
        libiocage.lib.helpers.init_zfs(self, zfs)
        self.datasets = libiocage.lib.Datasets.Datasets(
            root=root_dataset,
            logger=self.logger,
            zfs=self.zfs
        )
        self.distribution = self._class_distribution(
            host=self,
            logger=self.logger
        )

        self._devfs = None
        self.releases_dataset = None

    @property
    def devfs(self):
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

    class_distribution = libiocage.lib.Distribution.DistributionGenerator
