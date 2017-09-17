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

import iocage.lib.Config.Jail.Property

init_property = iocage.lib.Config.Jail.Property.init_property


class JailConfigProperties(dict):

    def __init__(
        self,
        config: 'iocage.lib.Config.Jail.BaseConfig.BaseConfig',
        logger: 'iocage.lib.Logger.Logger'
    ) -> None:

        self.logger = logger
        self.config = config

    def is_special_property(self, property_name: str) -> bool:
        classes = iocage.lib.Config.Jail.Property.CLASSES
        return (property_name in classes.keys())

    def get_or_create(
        self,
        property_name: str
    ) -> typing.Any:

        if property_name not in self.keys():
            self[property_name] = init_property(
                property_name=property_name,
                config=self.config,
                logger=self.logger
            )

        return self[property_name]
