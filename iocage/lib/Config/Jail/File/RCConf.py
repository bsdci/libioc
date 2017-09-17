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

import iocage.lib.helpers
import iocage.lib.Config.Jail.File.Prototype

# MyPy
import iocage.lib.LaunchableResource


class RCConf(
    dict,
    iocage.lib.Config.Jail.File.Prototype.ResourceConfigFile
):

    # the file is always relative to the resource
    _file: str = "/etc/rc.conf"

    def __init__(
        self,
        resource: 'iocage.lib.LaunchableResource.LaunchableResource',
        file: str=None,
        logger: 'iocage.lib.Logger.Logger'=None
    ) -> None:

        dict.__init__(self, {})
        self.logger = iocage.lib.helpers.init_logger(self, logger)

        # No file was loaded yet, so we can't know the delta yet
        self._file_content_changed = True

        if file is not None:
            self._file = file

        self.resource = resource
        self._read_file()

    @property
    def path(self):
        path = f"{self.resource.root_dataset.mountpoint}/{self.file}"
        self._require_path_relative_to_resource(
            filepath=path,
            resource=self.resource
        )
        return os.path.abspath(path)

    @property
    def file(self):
        return self._file

    @file.setter
    def file(self, value):
        if self._file != value:
            self._file = value
            self._read_file()

    @property
    def changed(self) -> bool:
        return (self._file_content_changed is True)

    def _read_file(
        self,
        silent: bool=False,
        delete: bool=False,
        merge: bool=False
    ) -> None:
        """
        Read the rc.conf file

        Args:

            silent:
                Do not use the logger

            delete:
                Delete entries that do not exist in the file

            merge:
                Do not change already existing properties
        """
        try:
            if (self.path is not None) and os.path.isfile(self.path):
                data = self._read(silent=silent)
            else:
                data = {}
        except:
            data = {}

        existing_keys = set(self.keys())
        new_keys = set(data.keys())
        delete_keys = existing_keys - new_keys

        if delete is True:
            for key in delete_keys:
                del self[key]

        for key in new_keys:
            if key in existing_keys:
                if (merge is True) and (self[key] != data[key]):
                    self[key] = data[key]
                    self._file_content_changed = True
            else:
                self[key] = data[key]
                self._file_content_changed = True

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
        self.logger.spam(f"rc.conf was read from {self.path}")
        return data

    def save(self) -> bool:

        if self.changed is False:
            self.logger.debug("rc.conf was not modified - skipping write")
            return False

        with open(self.path, "w") as rcconf:

            output = ucl.dump(self, ucl.UCL_EMIT_CONFIG)
            output = output.replace(" = \"", "=\"")
            output = output.replace("\";\n", "\"\n")

            self.logger.verbose(f"Writing rc.conf to {self.path}")

            rcconf.write(output)
            rcconf.truncate()
            rcconf.close()

            self._file_content_changed = False
            self.logger.spam(output[:-1], indent=1)
            return True

    def __setitem__(self, key, value):
        val = iocage.lib.helpers.to_string(
            iocage.lib.helpers.parse_user_input(value),
            true="YES",
            false="NO"
        )

        try:
            if self[key] == value:
                return
        except KeyError:
            pass

        dict.__setitem__(self, key, val)
        self._file_content_changed = True

    def __getitem__(self, key):
        val = dict.__getitem__(self, key)
        return iocage.lib.helpers.parse_user_input(val)
