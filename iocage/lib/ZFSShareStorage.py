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
import iocage.lib.errors


class ZFSShareStorage:
    @property
    def zfs_datasets(self):
        return self._get_zfs_datasets(auto_create=self.auto_create)

    def mount_zfs_shares(self, auto_create=False):
        self.logger.log("Mounting ZFS shares")
        self._mount_procfs()
        self._mount_jail_datasets(auto_create=auto_create)

    def _get_zfs_datasets(self, auto_create=None):
        dataset_names = self.jail.config["jail_zfs_dataset"]

        auto_create = self.auto_create if auto_create is None else auto_create

        datasets = set()
        for name in dataset_names:

            zpool = None
            try:
                zpool = self._get_pool_from_dataset_name(name)
            except:
                pass

            pool_name = f"{self.jail.pool_name}/{name}"
            try:
                # legacy support (datasets not prefixed with pool/)
                zpool = self._get_pool_from_dataset_name(pool_name)
                name = f"{self.jail.pool_name}/{name}"
            except:
                pass

            try:
                if auto_create:
                    zpool.create(name, {}, create_ancestors=True)
            except:
                pass

            try:
                dataset = self.zfs.get_dataset(name)
                datasets.add(dataset)
            except:
                raise iocage.lib.errors.DatasetNotAvailable(
                    dataset_name=name,
                    logger=self.logger
                )

        return datasets

    def _mount_jail_dataset(self, dataset_name):
        self.jail.exec(['zfs', 'mount', dataset_name])

    def _mount_jail_datasets(self, auto_create=None):

        auto_create = self.auto_create if auto_create is None else (
            auto_create is True)

        if self.safe_mode:
            self._require_datasets_exist_and_jailed()

        for dataset in self.zfs_datasets:

            self._unmount_local(dataset)

            # ToDo: bake jail feature into py-libzfs
            iocage.lib.helpers.exec(
                ["zfs", "jail", self.jail.identifier, dataset.name])

            if dataset.properties['mountpoint']:
                for child in list(dataset.children):
                    self._ensure_dataset_exists(child)
                    self._mount_jail_dataset(child.name)

    def _get_pool_name_from_dataset_name(self, dataset_name):
        return dataset_name.split("/", maxsplit=1)[0]

    def _get_pool_from_dataset_name(self, dataset_name):
        target_pool_name = self._get_pool_name_from_dataset_name(dataset_name)
        for zpool in list(self.zfs.pools):
            if zpool.name == target_pool_name:
                return zpool

        # silent exception, no logger defined
        raise iocage.lib.errors.ZFSPoolUnavailable(
            pool_name=target_pool_name
        )

    def _require_datasets_exist_and_jailed(self):
        existing_datasets = self.get_zfs_datasets(auto_create=False)
        for existing_dataset in existing_datasets:
            if existing_dataset.properties["jailed"] != "on":
                raise iocage.lib.errors.DatasetNotJailed(
                    dataset=existing_dataset,
                    logger=self.logger
                )
