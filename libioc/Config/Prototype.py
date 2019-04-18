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
"""Prototype of a Jail configuration."""
import typing
import os.path

import libioc.helpers_object
import libioc.Config.Data

# MyPy
import libioc.Logger


ConfigDataDict = typing.Dict[str, typing.Optional[typing.Union[
    int,
    str,
    dict,
    list
]]]


class Prototype:
    """Prototype of a JailConfig."""

    logger: typing.Type['libioc.Logger.Logger']
    data: ConfigDataDict
    _file: str

    def __init__(
        self,
        file: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.data = libioc.Config.Data.Data()

        if file is not None:
            self._file = file

    @property
    def file(self) -> str:
        """Return the relative path to the config file."""
        return self._file

    @file.setter
    def file(self, value: str) -> None:
        self._file = value

    def read(self) -> libioc.Config.Data.Data:
        """
        Read from the configuration file.

        This method may be overriden by non file-based implementations.
        """
        try:
            with open(self.file, "r") as data:
                return self.map_input(data)
        except FileNotFoundError:
            return {}

    def write(self, data: ConfigDataDict) -> None:
        """
        Write changes to the config file.

        This method may be overriden by non file-based implementations.
        """
        with open(self.file, "w") as conf:
            text_data = str(self.map_output(data))
            conf.write(text_data)
            conf.truncate()

    def map_input(
        self,
        data: typing.Union[typing.TextIO, ConfigDataDict]
    ) -> libioc.Config.Data.Data:
        """
        Map input data (for reading from the configuration).

        Implementing classes may provide individual mappings.
        """
        if not isinstance(data, typing.TextIO):
            return libioc.Config.Data.Data(data)

        raise NotImplementedError("Mapping not implemented on the prototype")

    def map_output(
        self,
        data: ConfigDataDict
    ) -> typing.Union[str, ConfigDataDict]:
        """
        Map output data (for writing to the configuration).

        Implementing classes may provide individual mappings.
        """
        if not isinstance(data, str):
            return data

        raise NotImplementedError("Mapping not implemented on the prototype")

    @property
    def exists(self) -> bool:
        """Return True when the configuration file exists on the filesystem."""
        return os.path.isfile(self.file)
