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
import iocage.lib.BridgeInterface


class InterfaceProp(dict):

    config: 'iocage.lib.Config.Jail.JailConfig.JailConfig'
    property_name: str = "interfaces"

    def __init__(
        self,
        config: typing.Optional[
            'iocage.lib.Config.Jail.JailConfig.JailConfig'
        ]=None,
        **kwargs
    ) -> None:

        dict.__init__(self, {})

        if config is not None:
            self.config = config

    def set(
        self,
        data: typing.Union[str, typing.Dict[str, str]]
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
        bridge_if: typing.Optional[str]=None,
        notify: typing.Optional[bool]=True
    ) -> None:
        """
        add an interface/bridge configuration

        Args:

            jail_if (string):
                Interface name inside the jail

            bridge_if (string): (optional)
                Interface name of the host bridge device (VNET only)

                A name beginning with ! (exclamation mark) enables the secure
                mode, that adds a second bridge between the jail and the
                target bridge, so that source IP and mac address cannot be
                spoofed from within the jail

            notify (bool): (default=True)
                Sends an update notification to the jail config instance
        """
        try:
            bridge = iocage.lib.helpers.parse_none(bridge_if)
        except TypeError:
            bridge = iocage.lib.BridgeInterface.BridgeInterface(bridge_if)

        dict.__setitem__(self, jail_if, bridge)

        if notify is True:
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

    def __empty_prop(self, key: str) -> None:
        dict.__setitem__(self, key, None)

    def to_string(self, value: dict) -> str:
        out = []
        for jail_if in value:
            bridge_if = self[jail_if]
            out.append(f"{jail_if}:{bridge_if}")
        return " ".join(out)

    def __str__(self) -> str:
        return self.to_string(value=self)
