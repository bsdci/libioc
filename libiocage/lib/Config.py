import typing
import os.path
import libzfs

import libiocage.lib.helpers


class BaseConfig:

    def __init__(
        self,
        logger: 'libiocage.lib.Logger.Logger'=None
    ) -> None:

        self.logger = libiocage.lib.helpers.init_logger(self, logger)


class ConfigFile(BaseConfig):

    def __init__(
        self,
        file: str=None,
        logger: 'libiocage.lib.Logger.Logger'=None
    ) -> None:

        BaseConfig.__init__(self, logger=logger)
        self._file = file

    @property
    def file(self) -> str:
        return self._file

    @file.setter
    def file(self, value: str):
        self._file = value

    def read(self) -> dict:
        try:
            with open(self.file, "r") as data:
                return self.map_input(data)
        except:
            return {}

    def write(self, data: dict) -> None:
        """
        Writes changes to the config file
        """
        with open(self.file, "w") as conf:
            conf.write(self.map_output(data))
            conf.truncate()

    def map_input(self, data: typing.Any) -> dict:
        return data

    def map_output(self, data: typing.Any) -> typing.Any:
        return data

    def exists(self) -> bool:
        return os.path.isfile(self.file)


class DatasetConfig(ConfigFile):

    def __init__(
        self,
        dataset: libzfs.ZFSDataset = None,
        **kwargs
    ) -> None:

        self._dataset = dataset
        ConfigFile.__init__(self, **kwargs)

    @property
    def dataset(self) -> libzfs.ZFSDataset:
        return self._dataset

    @property
    def file(self) -> str:
        return os.path.join(self.dataset.mountpoint, self._file)

    @file.setter
    def file(self, value: str):
        self._file = value


class ResourceConfig(DatasetConfig):

    resource: 'libiocage.lib.Resource.Resource' = None

    def __init__(
        self,
        resource: 'libiocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        self.resource = resource
        DatasetConfig.__init__(self, **kwargs)

    @property
    def dataset(self) -> libzfs.ZFSDataset:
        return self.resource.dataset
