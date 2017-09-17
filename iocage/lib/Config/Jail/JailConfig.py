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

import iocage.lib.helpers
import iocage.lib.Config.Jail.BaseConfig

# MyPy
import iocage.lib.Jail

_usp = iocage.lib.Config.Jail.BaseConfig.BaseConfig.update_special_property


class JailConfig(iocage.lib.Config.Jail.BaseConfig.BaseConfig):

    legacy: bool = None
    jail: 'iocage.lib.Jail.JailGenerator' = None
    data: dict = {}

    def __init__(
        self,
        data: dict=None,
        jail: 'iocage.lib.Jail.JailGenerator'=None,
        new: bool=False,
        logger: 'iocage.lib.Logger.Logger'=None,
        host: 'iocage.lib.Host.HostGenerator'=None
    ) -> None:

        iocage.lib.Config.Jail.BaseConfig.BaseConfig.__init__(
            self,
            logger=logger
        )

        self.host = iocage.lib.helpers.init_host(self, host)

        if len(data.keys()) == 0:
            self.data = {
                "id": None
            }

        self.jail = jail

        # the name is used in many other variables and needs to be set first
        for key in ["id", "name", "uuid"]:
            if key in data.keys():
                self["id"] = data[key]
                break

        self.clone(data)

    def update_special_property(self, name: str) -> None:

        _usp(
            self,
            name=name
        )

        if (name == "ip6_addr") and (self.jail is not None):
            rc_conf = self.jail.rc_conf
            rc_conf["rtsold_enable"] = "accept_rtadv" in str(self["ip6_addr"])

    def _get_host_hostname(self):
        try:
            return self.data["host_hostname"]
        except KeyError:
            return self.jail.humanreadable_name

    def __getitem__(self, key: str) -> typing.Any:
        try:
            return super().__getitem__(key)
        except KeyError:
            # fall back to default
            return self.host.default_config[key]

    @property
    def all_properties(self) -> list:
        jail_config_properties = set(super().all_properties)
        default_config_properties = set(
            self.host.default_config.all_properties)
        return sorted(list(jail_config_properties | default_config_properties))
