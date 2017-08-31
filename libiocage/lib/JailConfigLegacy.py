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
import os.path

import ucl


class JailConfigLegacy:
    def read(self):
        self.clone(JailConfigLegacy.read_data(self), skip_on_error=True)

    def save(self):
        config_file_path = JailConfigLegacy.__get_config_path(self)
        with open(config_file_path, "w") as f:
            f.write(JailConfigLegacy.toLegacyConfig(self))
            self.logger.verbose(f"Legacy config written to {config_file_path}")

    def read_data(self):
        with open(JailConfigLegacy.__get_config_path(self), "r") as conf:
            data = ucl.load(conf.read())

            try:
                if data["type"] == "basejail":
                    data["basejail"] = "on"
                    data["clonejail"] = "off"
                    data["basejail_type"] = "zfs"
                    data["type"] = "jail"
            except:
                pass

            return data

    def exists(self):
        return os.path.isfile(JailConfigLegacy.__get_config_path(self))

    def __get_config_path(self):
        try:
            return f"{self.jail.dataset.mountpoint}/config"
        except:
            raise "Dataset not found or not mounted"
