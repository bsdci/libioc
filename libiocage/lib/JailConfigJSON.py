import json
import os.path

import libiocage.lib.helpers


class JailConfigJSON:
    def toJSON(self):
        data = self.data
        output_data = {}
        for key, value in data.items():
            output_data[key] = libiocage.lib.helpers.to_string(
                value,
                true="yes",
                false="no",
                none="none"
            )
        return json.dumps(output_data, sort_keys=True, indent=4)

    def save(self):
        config_file_path = JailConfigJSON.__get_config_json_path(self)
        with open(config_file_path, "w") as f:
            self.logger.verbose(f"Writing JSON config to {config_file_path}")
            f.write(JailConfigJSON.toJSON(self))
            self.logger.debug(f"File {config_file_path} written")

    def read(self):
        return self.clone(JailConfigJSON.read_data(self), skip_on_error=True)

    def read_data(self):
        with open(JailConfigJSON.__get_config_json_path(self), "r") as conf:
            return json.load(conf)

    def exists(self):
        return os.path.isfile(JailConfigJSON.__get_config_json_path(self))

    def __get_config_json_path(self):
        try:
            return f"{self.jail.dataset.mountpoint}/config.json"
        except:
            raise libiocage.lib.errors.DatasetNotMounted(
                dataset=self.jail.dataset,
                logger=self.logger
            )
