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
"""Jail config address property."""
import typing
import ipaddress

# mypy
import libioc.Logger

IPAddressInput = typing.Optional[typing.Union[
    str,
    ipaddress.IPv4Address,
    ipaddress.IPv6Address
]]


class DefaultrouterMixin:
    """Special jail config property mixin defaultrouter and defaultrouter6."""

    config: 'libioc.Config.Jail.JailConfig.JailConfig'
    property_name: str = "defaultrouter"
    logger: typing.Optional['libioc.Logger.Logger']
    interface_delimiter: str = "@"

    _ip: typing.Optional[int]  # from ipaddress.IPv*Address class
    static_interface: typing.Optional[str]

    def __init__(
        self,
        config: typing.Optional[
            'libioc.Config.Jail.BaseConfig.BaseConfig'
        ]=None,
        property_name: str="defaultrouter",
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        self.logger = logger
        self.config = config
        self.property_name = property_name
        self.static_interface = None

    def set(
        self,
        data: IPAddressInput,
        notify: bool=True,
        skip_on_error: bool=False
    ) -> None:
        """Set the defaultrouter property."""
        gateway: typing.Optional[typing.Union[
            str,
            ipaddress.IPv4Address,
            ipaddress.IPv6Address
        ]]
        static_interface = None

        if isinstance(data, str) is True:
            data = libioc.helpers.parse_user_input(data)

        if data is None:
            gateway = None
            self._ip = None
            return
        else:
            if isinstance(data, str) is True:
                _data = str(data)
                if "@" in _data:
                    address, static_interface = _data.split("@", maxsplit=1)
                else:
                    address = _data
                gateway = self._ipaddress_class(address)
            else:
                gateway = data
            self._ipaddress_class.__init__(self, gateway)  # noqa: T484
            self.static_interface = static_interface

        self.__notify(notify)

    @property
    def _ipaddress_class(self) -> typing.Union[
        typing.Callable[..., ipaddress.IPv4Address],
        typing.Callable[..., ipaddress.IPv6Address]
    ]:
        return self.__class__.__bases__[-1]

    def __notify(self, notify: bool=True) -> None:
        if notify is True:
            self.config.update_special_property(self.property_name)

    @property
    def _gateway_address(self) -> typing.Optional[str]:
        try:
            return self._ipaddress_class.__str__(self)  # noqa: T484
        except Exception:
            return None

    def __str__(self) -> str:
        """Return the gateway address including the static interface."""
        return self._tostring()

    def _tostring(self, delimiter: str="@") -> str:
        gateway = self._gateway_address
        if gateway is None:
            return ""
        if self.static_interface is None:
            return str(gateway)
        return f"{gateway}{delimiter}{self.static_interface}"


class DefaultrouterProp(DefaultrouterMixin, ipaddress.IPv4Address):
    """Special jail config property defaultrouter."""

    def apply(self, jail: 'libioc.Jail.JailGenerator') -> typing.List[str]:
        """Return a list of commands that configure the default IPv4 route."""
        commands: typing.List[str] = []
        gateway_address = self._gateway_address

        if gateway_address is None:
            return []

        gateway = str(gateway_address)

        if self.static_interface is not None:
            nic = self.static_interface
            if self.logger is not None:
                self.logger.verbose(
                    f"setting pointopoint route to {gateway} via {nic}"
                )
            commands.append(f"/sbin/route -q add {gateway} -iface {nic}")

        if self.logger is not None:
            self.logger.verbose(
                f"setting default IPv4 gateway to {gateway}"
            )
        commands.append(f"/sbin/route -q add default {gateway}")

        return commands


class Defaultrouter6Prop(DefaultrouterMixin, ipaddress.IPv6Address):
    """Special jail config property defaultrouter6."""

    def apply(self, jail: 'libioc.Jail.JailGenerator') -> typing.List[str]:
        """Return a list of commands that configure the default IPv6 route."""
        commands: typing.List[str] = []
        gateway_address = self._gateway_address

        if gateway_address is None:
            return []
        elif gateway_address.startswith("fe80:") is True:
            gateway = str(self._tostring(delimiter="%"))
        else:
            gateway = str(gateway_address)
            if self.static_interface is not None:
                nic = self.static_interface
                if self.logger is not None:
                    self.logger.verbose(
                        f"setting pointopoint route to {gateway} via {nic}"
                    )
                commands.append(
                    f"/sbin/route -q add -6 -host {gateway} -iface {nic}"
                )

        if self.logger is not None:
            self.logger.verbose(
                f"setting default IPv6 gateway to {gateway}",
            )
        commands.append(f"/sbin/route -q add -6 default {gateway}")
        return commands

