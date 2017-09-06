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

import libiocage.lib.Config
import libiocage.lib.errors


class ConfigUCL(libiocage.lib.Config.BaseConfig):

    config_type = "ucl"

    def map_input(self, data: dict) -> dict:
        return ucl.load(data)

    def map_output(self, data: dict) -> dict:
        # ToDo: Re-Implement UCL output
        raise libiocage.lib.errors.MissingFeature("Writing ConfigUCL")


class ResourceConfigUCL(ConfigUCL, libiocage.lib.Config.ResourceConfig):

    def __init__(
        self,
        resource: 'libiocage.lib.Resource.Resource',
        file: str="config",
        **kwargs
    ):

        self.resource = resource
        libiocage.lib.Config.ResourceConfig.__init__(
            self,
            resource=resource,
            file=file,
            **kwargs
        )

    @property
    def file(self) -> str:
        return os.path.join(self.resource.dataset.mountpoint, self._file)
