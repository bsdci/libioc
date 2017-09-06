import os.path
import json

import libiocage.lib.helpers


class JsonConfigFile:

    def __init__(
        self,
        file: str,
        logger: libiocage.lib.Logger.Logger
    ):

        libiocage.lib.helpers.init_logger(self, logger)
        self._file = file

    @property
    def file(self) -> str:
        return self._file

    def read(self) -> dict:
        if os.path.isfile(self.file) is True:
            with open(self.file, "r") as conf:
                return json.load(conf)
        return {}

    def write(self, data: dict):
        """
        Writes changes to the config file
        """
        with open(self.file, "w") as conf:
            conf.write(self._to_json(data))
            conf.truncate()

    def _to_json(self, data: dict) -> str:
        output_data = {}
        for key, value in data.items():
            output_data[key] = libiocage.lib.helpers.to_string(
                value,
                true="yes",
                false="no",
                none="none"
            )
        return json.dumps(output_data, sort_keys=True, indent=4)


class ResourceJsonConfigFile:

    def __init__(
        self,
        resource: libiocage.lib.Resource.Resource,
        **kwargs
    ):

        self.resource = resource
        JsonConfigFile.__init__(self, **kwargs)

    @property
    def file(self) -> str:
        return os.path.join(self.resource.dataset.mountpoint, self._file)
