import libzfs

import libiocage.lib.Logger
import libiocage.lib.helpers


def get_zfs(
    logger: 'libiocage.lib.Logger.Logger'=None,
    history: bool=True,
    history_prefix: str="<iocage>"
):
    zfs = ZFS(history=history, history_prefix=history_prefix)
    zfs.logger = libiocage.lib.helpers.init_logger(zfs, logger)
    return zfs


class ZFS(libzfs.ZFS):

    logger: libiocage.lib.Logger.Logger = None

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
        raise
