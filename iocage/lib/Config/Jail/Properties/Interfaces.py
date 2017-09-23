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

_ConfigType = 'iocage.lib.Config.Jail.JailConfig.JailConfig'


class BridgeSet(set):

    config: 'iocage.lib.JailConfig.JailConfig'

    def __init__(
        self,
        config: typing.Optional['iocage.lib.JailConfig.JailConfig']=None
    ) -> None:

        if config is not None:
            self.config = config

        set.__init__(self)

    def add(self, value: str, notify: bool=True) -> None:
        set.add(self, value)
        if notify:
            self.__notify()

    def remove(self, value: str, notify: bool=True) -> None:
        set.remove(self, value)
        if notify:
            self.__notify()

    def __notify(self) -> None:
        self.config.update_special_property("interfaces")


class InterfaceProp(dict):

    config: 'iocage.lib.Config.Jail.JailConfig.JailConfig'
    property_name: str = "interfaces"

    def __init__(
        self,
        config: typing.Optional['iocage.lib.JailConfig.JailConfig']=None,
        **kwargs
    ) -> None:

        dict.__init__(self, {})

        if config is not None:
            self.config = config

    def set(
        self,
        data: typing.Union[str, typing.Dict[str, BridgeSet]]
    ) -> None:

        self.clear()

        try:
            iocage.lib.helpers.parse_none(data)
            return
        except TypeError:
            pass

        if isinstance(data, dict):
            dict.__init__(self, data)
            return

        nic_pairs = data.replace(",", " ").split(" ")
        for nic_pair in nic_pairs:
            jail_if, bridge_if = nic_pair.split(":", maxsplit=1)
            self.add(jail_if, bridge_if, notify=False)

        self.__notify()

    def add(
        self,
        jail_if: str,
        bridges: typing.Optional[typing.Union[str, typing.List[str]]]=None,
        notify: bool=True
    ) -> None:

        if bridges is None or bridges == [] or bridges == "":
            return

        if isinstance(bridges, str):
            bridges = [bridges]

        try:
            prop = dict.__getitem__(self, jail_if)
        except:
            prop = self.__empty_prop(jail_if)

        for bridge_if in bridges:
            prop.add(bridge_if, notify=False)

        if notify:
            self.__notify()

    def __setitem__(self, key, values):

        if key in self.keys():
            dict.__delitem__(self, key)

        self.add(key, values)

    def __delitem__(self, key) -> None:
        dict.__delitem__(self, key)
        self.__notify()

    def __notify(self) -> None:
        self.config.update_special_property(self.property_name)

    def __empty_prop(self, key: str) -> BridgeSet:

        prop = BridgeSet(self.config)
        dict.__setitem__(self, key, prop)
        return prop

    def to_string(self, value: dict) -> str:
        out = []
        for jail_if in value:
            for bridge_if in self[jail_if]:
                out.append(f"{jail_if}:{bridge_if}")
        return " ".join(out)

    def __str__(self) -> str:
        return self.to_string(value=self)
