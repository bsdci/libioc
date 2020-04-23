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
"""ioc configuration stored in a JSON file."""
import typing
import json

import libioc.Config
import libioc.Config.Data
import libioc.Config.Prototype
import libioc.Config.Dataset
import libioc.helpers


class ConfigJSON(libioc.Config.Prototype.Prototype):
    """ioc configuration stored in a JSON file."""

    config_type = "json"

    def map_input(self, data: typing.TextIO) -> libioc.Config.Data.Data:
        """Parse and normalize JSON data."""
        try:
            content = data.read().strip()
        except (FileNotFoundError, PermissionError) as e:
            raise libioc.errors.JailConfigError(
                message=str(e),
                logger=self.logger
            )

        if content == "":
            return libioc.Config.Data.Data()

        try:
            result = json.loads(content)  # type: typing.Dict[str, typing.Any]
            return libioc.Config.Data.Data(result)
        except json.decoder.JSONDecodeError as e:
            raise libioc.errors.JailConfigError(
                message=str(e),
                logger=self.logger
            )

    def map_output(self, data: libioc.Config.Data.Data) -> str:
        """Output configuration data as JSON string."""
        return str(libioc.helpers.to_json(data.nested))


class DatasetConfigJSON(
    libioc.Config.Dataset.DatasetConfig,
    ConfigJSON
):
    """ConfigFile in JSON format."""

    pass
