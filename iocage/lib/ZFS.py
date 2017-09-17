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
import libzfs

import iocage.lib.Logger
import iocage.lib.helpers
import iocage.lib.errors


def get_zfs(
    logger: 'iocage.lib.Logger.Logger'=None,
    history: bool=True,
    history_prefix: str="<iocage>"
):
    zfs = ZFS(history=history, history_prefix=history_prefix)
    zfs.logger = iocage.lib.helpers.init_logger(zfs, logger)
    return zfs


class ZFS(libzfs.ZFS):

    logger: iocage.lib.Logger.Logger = None

    def create_dataset(
        self,
        dataset_name: str,
        **kwargs
    ) -> libzfs.ZFSDataset:

        pool = self.get_pool(dataset_name)
        pool.create(dataset_name, kwargs, create_ancestors=True)

        dataset = self.get_dataset(dataset_name)
        dataset.mount()
        return dataset

    def get_or_create_dataset(
        self,
        dataset_name: str,
        **kwargs
    ) -> libzfs.ZFSDataset:

        try:
            return self.get_dataset(dataset_name)
        except:
            pass

        return self.create_dataset(dataset_name, **kwargs)

    def get_pool(self, name: str) -> libzfs.ZFSPool:
        pool_name = name.split("/")[0]
        for pool in self.pools:
            if pool.name == pool_name:
                return pool
        raise iocage.lib.errors.ZFSPoolUnavailable(
            pool_name=pool_name,
            logger=self.logger
        )
