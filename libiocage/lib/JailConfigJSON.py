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
