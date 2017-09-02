import os.path

import libiocage.lib.helpers


class BaseConfig:

    def __init__(
        self,
        logger: 'libiocage.lib.Logger.Logger'=None
    ):

        self.logger = libiocage.lib.helpers.init_logger(self, logger)


class ConfigFile:

    def __init__(
        self,
        file: str=None,
        logger: 'libiocage.lib.Logger.Logger'=None
    ):

        BaseConfig.__init__(self, logger=logger)
        self._file = file

    @property
    def file(self):
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

    def write(self, data: dict):
        """
        Writes changes to the config file
        """
        with open(self.file, "w") as conf:
            conf.write(self.map_output(data))
            conf.truncate()

    def map_input(self, data: dict) -> dict:
        return data

    def map_output(self, data: dict) -> dict:
        return data

    def exists(self):
        return os.path.isfile(self.file)


class ResourceConfig(ConfigFile):

    def __init__(
        self,
        resource: 'libiocage.lib.Resource.Resource',
        **kwargs
    ):

        self.resource = resource
        ConfigFile.__init__(self, **kwargs)

    @property
    def file(self):
        return os.path.join(self.dataset.mountpoint, self._file)

    @property
    def dataset(self):
        return self.resource.dataset
