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
"""ioc configuration stored in an UCL file."""
import typing

import libioc.Config
import libioc.Config.Data
import libioc.Config.Prototype
import libioc.Config.Dataset
import libioc.errors


class ConfigUCL(libioc.Config.Prototype.Prototype):
    """ioc configuration stored in an UCL file."""

    config_type = "ucl"

    def map_input(self, data: typing.TextIO) -> typing.Dict[str, typing.Any]:
        """Normalize data read from the UCL file."""
        import ucl
        result = ucl.load(data.read())  # type: typing.Dict[str, typing.Any]
        result["legacy"] = True
        return result

    def map_output(self, data: libioc.Config.Data.Data) -> str:
        """Output configuration in UCL format."""
        return str(libioc.helpers.to_ucl(data))


class DatasetConfigUCL(
    libioc.Config.Dataset.DatasetConfig,
    ConfigUCL
):
    """ConfigFile in UCL format."""

    pass
