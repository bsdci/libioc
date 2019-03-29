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

import libioc.errors
import libioc.helpers
import libioc.IPAddress

# mypy
import libioc.Config.Jail
import libioc.Logger

IPv4Interface = libioc.IPAddress.IPv4Interface
IPv6Interface = libioc.IPAddress.IPv6Interface

IPv4AddressInput = typing.Union[
    str,
    libioc.IPAddress.IPv4Interface
]

IPv6AddressInput = typing.Union[
    str,
    libioc.IPAddress.IPv6Interface
]

IPAddressInput = typing.Union[
    str,
    libioc.IPAddress.IPv4Interface,
    libioc.IPAddress.IPv6Interface
]

IPInterfaceList = typing.Union[
    typing.List[libioc.IPAddress.IPv4Interface],
    typing.List[libioc.IPAddress.IPv6Interface]
]


class AddressSet(set):
    """Set of IP addresses."""

    property_name: str
    config: typing.Optional['libioc.Config.Jail.JailConfig.JailConfig']
    logger: typing.Optional['libioc.Logger.Logger']

    def __init__(
        self,
        config: typing.Optional[
            'libioc.Config.Jail.JailConfig.JailConfig'
        ]=None,
        property_name: str="ip4_address",
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        self.logger = logger
        self.config = config
        set.__init__(self)
        self.property_name = property_name

    def add(
        self,
        value: typing.Union[
            IPv4AddressInput,
            IPv6AddressInput
        ],
        notify: bool=True,
        skip_on_error: bool=False
    ) -> None:
        """Add an address to the set."""
        try:
            set.add(self, self.__parse_address(value))
            if notify:
                self.__notify()
        except Exception as e:
            if skip_on_error is False:
                raise e

    def remove(self, value: IPAddressInput, notify: bool=True) -> None:
        """Remove an address from the set."""
        set.remove(self, self.__parse_address(value))
        if notify:
            self.__notify()

    def __notify(self) -> None:
        if self.config is not None:
            self.config.update_special_property(self.property_name)

    def __parse_address(
        self,
        address: IPAddressInput
    ) -> typing.Union[
        str,
        libioc.IPAddress.IPv4Interface,
        libioc.IPAddress.IPv6Interface
    ]:
        _address = str(address).lower()
        if (_address == "accept_rtadv") or (_address == "dhcp"):
            return str(_address)
        return address


_AddressSetInputType = typing.Union[str, typing.Dict[str, AddressSet]]


class AddressesProp(dict):
    """Special jail config property Addresses."""

    logger: 'libioc.Logger.Logger'
    config: 'libioc.Config.Jail.JailConfig.JailConfig'
    property_name: str = "ip4_address"
    skip_on_error: bool
    delimiter: str = ","

    IP_VERSION: int

    def __init__(
        self,
        config: typing.Optional[
            'libioc.Config.Jail.BaseConfig.BaseConfig'
        ]=None,
        property_name: str="ip4_address",
        logger: typing.Optional['libioc.Logger.Logger']=None,
        skip_on_error: bool=False
    ) -> None:

        dict.__init__(self, {})

        self.logger = logger
        self.config = config
        self.property_name = property_name
        self.skip_on_error = skip_on_error

    def set(
        self,
        data: _AddressSetInputType,
        skip_on_error: bool=False
    ) -> None:
        """Set the special property value."""
        self.clear()
        error_log_level = "warn" if (skip_on_error is True) else "error"
        skip_on_error = (self.skip_on_error or skip_on_error) is True

        try:
            libioc.helpers.parse_none(data)
            return
        except TypeError:
            pass

        if isinstance(data, dict):
            dict.__init__(self, data)
            return

        ip_addresses = data.split(",")
        for ip_address_string in ip_addresses:

            try:
                nic, address = ip_address_string.split("|", maxsplit=1)
                err = None
            except ValueError:
                err = libioc.errors.InvalidJailConfigAddress(
                    jail=self.config.jail,
                    value=ip_address_string,
                    property_name=self.property_name,
                    logger=self.logger,
                    level=error_log_level
                )
            if (err is not None) and (self.skip_on_error is False):
                raise err

            self.add(nic, address, skip_on_error=skip_on_error)  # noqa: T484

    def _add_ip_addresses(
        self,
        nic: str,
        addresses: IPInterfaceList,
        notify: bool=True,
        skip_on_error: bool=False
    ) -> None:
        """Add an address to a NIC."""
        if (addresses is None) or (len(addresses) == 0):
            return

        try:
            prop = self[nic]
        except KeyError:
            prop = self.__empty_prop(nic)

        for address in addresses:
            prop.add(address, notify=False, skip_on_error=skip_on_error)

        if notify:
            self.__notify()

    def add(
        self,
        nic: str,
        addresses: typing.Union[
            IPAddressInput,
            typing.List[IPAddressInput]
        ]=None,
        notify: bool=True,
        skip_on_error: bool=False
    ) -> None:
        """Add one or many IP addresses to an interface."""
        if isinstance(addresses, list) is False:
            _address: IPAddressInput = addresses  # noqa: T484
            self.add(
                nic=nic,
                addresses=[_address],
                notify=False,
                skip_on_error=skip_on_error
            )
            self.__notify()
            return

        error_log_level = "warn" if (skip_on_error is True) else "error"

        own_class = self.ADDRESS_CLASS  # noqa: T484
        _class: typing.Union[
            typing.Callable[..., libioc.IPAddress.IPv4Interface],
            typing.Callable[..., libioc.IPAddress.IPv6Interface]
        ] = own_class
        try:
            _addresses = [_class(x) for x in list(addresses)]  # type: ignore
            err = None
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
            err = e

        if err is not None:
            _e = libioc.errors.InvalidIPAddress(
                reason=str(err),
                ipv6=(self.IP_VERSION == 6),
                logger=self.logger,
                level=error_log_level
            )
            if skip_on_error is False:
                raise _e
            return

        self._add_ip_addresses(
            nic=nic,
            addresses=_addresses,
            notify=False,
            skip_on_error=skip_on_error
        )

        if notify is True:
            self.__notify()

    @property
    def networks(self) -> typing.List[str]:
        """Flat list of all networks configured across all NICs."""
        networks: list = []
        for nic, addresses in self.items():
            networks += addresses
        return networks

    def __setitem__(
        self,
        key: str,
        addresses: typing.Union[
            IPAddressInput,
            typing.List[IPAddressInput]
        ]
    ) -> None:
        """Set all addresses of a NIC."""
        try:
            dict.__delitem__(self, key)
        except KeyError:
            pass

        self.add(key, addresses)

    def __delitem__(self, key: str) -> None:
        """Delete addresses of a NIC."""
        dict.__delitem__(self, key)
        self.__notify()

    def __notify(self) -> None:
        self.config.update_special_property(self.property_name)

    def __empty_prop(self, key: str) -> AddressSet:
        prop = AddressSet(self.config, property_name=self.property_name)
        dict.__setitem__(self, key, prop)
        return prop

    def __str__(self) -> str:
        """
        Return a configuration string of the IP configuration.

        The format matches the iocage address notation used in:
          - ip4_addr
          - ip6_addr
        """
        if len(self) == 0:
            return ""
        out = []
        for nic in self:
            for address in self[nic]:
                out.append(f"{nic}|{address}")
        return str(self.delimiter.join(out))


class IPv4AddressesProp(AddressesProp):
    """Special jail config for IPv4 addresses."""

    IP_VERSION = 4
    ADDRESS_CLASS = IPv4Interface


class IPv6AddressesProp(AddressesProp):
    """Special jail config for IPv6 addresses."""

    IP_VERSION = 6
    ADDRESS_CLASS = IPv6Interface
