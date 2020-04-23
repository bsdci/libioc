# Copyright (c) 2017-2019, Stefan Grönke
# Copyright (c) 2014-2018, iocage
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
"""Prototype of config files stored on the filesystem."""
import typing
import os.path

import libioc.helpers
import libioc.helpers_object
import libioc.LaunchableResource

class ConfigFile(dict):
    """Abstraction of UCL file based config files in Resources."""

    _file: str
    _file_content_changed: bool = False
    logger: typing.Optional['libioc.Logger.Logger']

    def __init__(
        self,
        file: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        dict.__init__(self, {})
        self.logger = logger

        # No file was loaded yet, so we can't know the delta yet
        self._file_content_changed = True

        if file is not None:
            self._file = file

        self._read_file()

    @property
    def path(self) -> str:
        """Absolute path to the file."""
        return self.file

    @property
    def file(self) -> str:
        """File path relative to the Resources root_dataset."""
        return self._file

    @file.setter
    def file(self, value: str) -> None:
        if self._file != value:
            self._file = value

    @property
    def changed(self) -> bool:
        """Return true when the file was changed since reading it."""
        return (self._file_content_changed is True)

    def _read_file(
        self,
        delete: bool=False,
        merge: bool=False
    ) -> None:
        """
        Read the config file.

        Args:

            delete:
                Delete entries that do not exist in the file

            merge:
                Do not change already existing properties
        """
        try:
            if (self.path is not None) and os.path.isfile(self.path):
                data = self._read()
            else:
                data = {}
        except (FileNotFoundError, ValueError):
            data = {}

        existing_keys = list(self.keys())
        new_keys = list(data.keys())
        delete_keys = [x for x in existing_keys if x not in new_keys]

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

        if self.logger is not None:
            self.logger.verbose(f"Updated {self._file} data from {self.path}")

        if delete is False and len(delete_keys) > 0:
            # There are properties that are not in the file
            self._file_content_changed = True
        else:
            # Current data matches with file contents
            self._file_content_changed = False

    def _read(self) -> dict:
        import ucl
        data = dict(ucl.load(open(self.path).read()))
        if self.logger is not None:
            self.logger.spam(f"{self._file} was read from {self.path}")
        return data

    def save(self) -> bool:
        """Save the changes to the file."""
        if self.changed is False:
            if self.logger is not None:
                self.logger.debug(
                    f"{self._file} was not modified - skipping write"
                )
            return False

        with open(self.path, "w") as rcconf:
            import ucl
            output = ucl.dump(self, ucl.UCL_EMIT_CONFIG)
            output = output.replace(" = \"", "=\"")
            output = output.replace("\";\n", "\"\n")

            if self.logger is not None:
                self.logger.verbose(f"Writing {self._file} to {self.path}")

            rcconf.write(output)
            rcconf.truncate()
            rcconf.close()

            self._file_content_changed = False
            if self.logger is not None:
                self.logger.spam(output[:-1], indent=1)

            return True

    def __setitem__(
        self,
        key: str,
        value: typing.Union[str, int, bool]
    ) -> None:
        """Set a value in the config file."""
        val = libioc.helpers.to_string(
            libioc.helpers.parse_user_input(value),
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

    def __getitem__(
        self,
        key: str
    ) -> typing.Optional[typing.Union[str, bool]]:
        """Get a value of the config file."""
        val = dict.__getitem__(self, key)
        output = libioc.helpers.parse_user_input(val)
        if isinstance(output, str) or isinstance(output, bool):
            return output
        return None


class ResourceConfigFile(ConfigFile):
    """Abstraction of UCL file based config files in Resources."""

    def __init__(
        self,
        resource: 'libioc.LaunchableResource.LaunchableResource',
        file: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        self.resource = resource
        ConfigFile.__init__(self, file=file, logger=logger)

    @property
    def path(self) -> str:
        """Absolute path to the file."""
        path = f"{self.resource.root_dataset.mountpoint}/{self.file}"
        self.resource.require_relative_path(path)
        return os.path.abspath(path)
