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
"""iocage configuration stored in an UCL file."""
import typing

import ucl

import iocage.lib.Config
import iocage.lib.Config.Prototype
import iocage.lib.Config.Dataset
import iocage.lib.errors


class ConfigUCL(iocage.lib.Config.Prototype.Prototype):
    """iocage configuration stored in an UCL file."""

    config_type = "ucl"

    def map_input(self, data: typing.TextIO) -> typing.Dict[str, typing.Any]:
        """Normalize data read from the UCL file."""
        result = ucl.load(data.read())  # type: typing.Dict[str, typing.Any]
        result["legacy"] = True
        return result

    def map_output(self, data: dict) -> str:
        """Output configuration in UCL format."""
        return str(iocage.lib.helpers.to_ucl(data))


class DatasetConfigUCL(
    iocage.lib.Config.Dataset.DatasetConfig,
    ConfigUCL
):
    """ResourceConfig in UCL format."""

    pass
