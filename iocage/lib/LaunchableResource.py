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
"""The main CLI for ioc."""
import libzfs

import iocage.lib.Config.Jail.File.RCConf
import iocage.lib.Resource

# MyPy
import iocage.lib.Config.Jail.JailConfig


class LaunchableResource(iocage.lib.Resource.Resource):

    _rc_conf: 'iocage.lib.Config.Jail.File.RCConf.RCConf' = None
    config: 'iocage.lib.Config.Jail.JailConfig.JailConfig' = None

    def create_resource(self) -> None:
        """
        Creates the root dataset
        """
        iocage.lib.Resource.Resource.create_resource(self)
        self.zfs.create_dataset(self.root_dataset_name)

    @property
    def root_path(self):
        return self.root_dataset.mountpoint

    @property
    def root_dataset(self) -> libzfs.ZFSDataset:
        # ToDo: Memoize root_dataset
        return self.get_dataset("root")

    @property
    def root_dataset_name(self) -> str:
        return f"{self.dataset_name}/root"

    @property
    def dataset_name(self) -> str:
        raise NotImplementedError(
            "This needs to be implemented by the inheriting class"
        )

    @dataset_name.setter
    def dataset_name(self, value: str) -> None:
        raise NotImplementedError(
            "This needs to be implemented by the inheriting class"
        )

    @property
    def dataset(self) -> libzfs.ZFSDataset:
        if self._dataset is None:
            self._dataset = self.zfs.get_dataset(self.dataset_name)

        return self._dataset

    @dataset.setter
    def dataset(self, value: libzfs.ZFSDataset):
        self._set_dataset(value)

    @property
    def rc_conf(self) -> 'iocage.lib.Config.Jail.File.RCConf.RCConf':
        if self._rc_conf is None:
            self._rc_conf = iocage.lib.Config.Jail.File.RCConf.RCConf(
                resource=self,
                logger=self.logger
            )
        return self._rc_conf
