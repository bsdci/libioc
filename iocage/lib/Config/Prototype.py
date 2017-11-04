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
import typing
import os.path
import iocage.lib.helpers
import iocage.lib.Config.Prototype

# mypy
import iocage.lib.Logger


class Prototype:

    logger: typing.Type[iocage.lib.Logger.Logger]
    data: dict = {}
    _file: str

    def __init__(
        self,
        file: typing.Optional[str]=None,
        logger: typing.Optional[iocage.lib.Logger.Logger]=None
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)

        if file is not None:
            self._file = file

    @property
    def file(self) -> str:
        return self._file

    @file.setter
    def file(self, value: str):
        self._file = value

    def read(self):
        try:
            with open(self.file, "r") as data:
                return self.map_input(data)
        except FileNotFoundError:
            return {}

    def write(self, data: dict) -> None:
        """
        Writes changes to the config file
        """
        with open(self.file, "w") as conf:
            conf.write(self.map_output(data))
            conf.truncate()

    def map_input(self, data: typing.Any):
        # result = data  # type: typing.Dict[str, typing.Any]
        # return result
        return data

    def map_output(self, data: typing.Any):
        # result = data  # type: typing.Dict[str, typing.Any]
        # return result
        return data

    @property
    def exists(self) -> bool:
        return os.path.isfile(self.file)
