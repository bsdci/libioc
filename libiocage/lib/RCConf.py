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
import os

import ucl

import libiocage.lib.helpers


class RCConf(dict):
    def __init__(self, path, data={}, logger=None, jail=None):

        dict.__init__(self, {})
        self.logger = libiocage.lib.helpers.init_logger(self, logger)
        self.jail = jail

        # No file was loaded yet, so we can't know the delta yet
        self._file_content_changed = True
        self._path = None
        self.path = path

    @property
    def path(self):
        return object.__getattribute__(self, "_path")

    @path.setter
    def path(self, value):
        if self.path != value:
            new_path = None if value is None else os.path.realpath(value)
            dict.__setattr__(self, "_path", new_path)
            self._read_file()

    def _read_file(self, silent=False, delete=False):
        try:
            if (self.path is not None) and os.path.isfile(self.path):
                data = self._read(silent=silent)
        except:
            data = {}
            pass

        existing_keys = set(self.keys())
        new_keys = set(data.keys())
        delete_keys = existing_keys - new_keys

        if delete is True:
            for key in delete_keys:
                del self[key]

        for key in new_keys:
            self[key] = data[key]

        if silent is False:
            self.logger.verbose(f"Updated rc.conf data from {self.path}")

        if delete is False and len(delete_keys) > 0:
            # There are properties that are not in the file
            self._file_content_changed = True
        else:
            # Current data matches with file contents
            self._file_content_changed = False

    def _read(self, silent=False):
        data = ucl.load(open(self.path).read())
        self.logger.spam(
            f"rc.conf was read from {self.path}",
            jail=self.jail
        )
        return data

    def save(self):

        if self._file_content_changed is False:
            self.logger.debug("rc.conf was not modified - skipping write")
            return

        with open(self.path, "w") as rcconf:
            output = ucl.dump(self, ucl.UCL_EMIT_CONFIG)
            output = output.replace(" = \"", "=\"")
            output = output.replace("\";\n", "\"\n")

            self.logger.verbose(
                f"Writing rc.conf to {self.path}",
                jail=self.jail
            )

            rcconf.write(output)
            rcconf.truncate()
            rcconf.close()

            self.logger.spam(output[:-1], jail=self.jail, indent=1)

    def __setitem__(self, key, value):
        val = libiocage.lib.helpers.to_string(
            libiocage.lib.helpers.parse_user_input(value),
            true="YES",
            false="NO"
        )

        dict.__setitem__(self, key, val)

    def __getitem__(self, key):
        val = dict.__getitem__(self, key)
        return libiocage.lib.helpers.parse_user_input(val)
