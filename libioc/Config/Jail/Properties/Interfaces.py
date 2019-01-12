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
"""Jail config interfaces property."""
import typing

import libioc.helpers
import libioc.BridgeInterface


class InterfaceProp(dict):
    """Special jail config property Interfaces."""

    config: 'libioc.Config.Jail.JailConfig.JailConfig'
    property_name: str
    logger: typing.Optional['libioc.Logger.Logger']
    delimiter: str = ","

    def __init__(
        self,
        config: typing.Optional[
            'libioc.Config.Jail.JailConfig.JailConfig'
        ]=None,
        property_name: str="interfaces",
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        self.property_name = property_name
        dict.__init__(self, {})
        self.logger = logger
        if config is not None:
            self.config = config

    def set(
        self,
        data: typing.Union[str, typing.Dict[str, str]],
        skip_on_error: bool=False
    ) -> None:
        """Clear and set all interfaces from data."""
        self.clear()
        error_log_level = "warn" if (skip_on_error is True) else "error"

        try:
            libioc.helpers.parse_none(data)
            return
        except TypeError:
            pass

        if isinstance(data, dict):
            dict.__init__(self, data)
            return

        if isinstance(data, list):
            nic_pairs = data
        else:
            nic_pairs = data.replace(",", " ").split(" ")

        if not all([(":" in nic_pair) for nic_pair in nic_pairs]):
            e = libioc.errors.InvalidJailConfigValue(
                reason="Invalid NIC pair (should be <nic>:<bridge>)",
                property_name=self.property_name,
                jail=self.config.jail,
                logger=self.logger,
                level=error_log_level
            )
            if skip_on_error is False:
                raise e

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
        Add an interface/bridge configuration entry.

        Args:

            jail_if (string):
                Interface name inside the jail

            bridge_if (string): (optional)
                Interface name of the host bridge device (VNET only)

                A name beginning with : (colon) enables the secure
                mode, that adds a second bridge between the jail and the
                target bridge, so that source IP and mac address cannot be
                spoofed from within the jail.

                  ioc set interfaces="vnet0::bridge0" my-jail

            notify (bool): (default=True)
                Sends an update notification to the jail config instance
        """
        try:
            bridge = libioc.helpers.parse_none(bridge_if)
        except TypeError:
            bridge = libioc.BridgeInterface.BridgeInterface(bridge_if)

        dict.__setitem__(self, jail_if, bridge)

        if notify is True:
            self.__notify()

    def __delitem__(self, key: typing.Any) -> None:
        """Remove a jail NIC."""
        dict.__delitem__(self, key)
        self.__notify()

    def __notify(self) -> None:
        self.config.update_special_property(self.property_name)

    def __empty_prop(self, key: str) -> None:
        dict.__setitem__(self, key, None)

    def to_string(self, value: dict) -> str:
        """Return the iocage formatted string of interfaces."""
        out = []
        for jail_if in value:
            bridge_if = self[jail_if]
            out.append(f"{jail_if}:{bridge_if}")
        return self.delimiter.join(out)

    def __str__(self) -> str:
        """Return the iocage formatted string of interfaces."""
        return self.to_string(value=self)
