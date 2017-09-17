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
import iocage.lib.errors
import iocage.lib.helpers


class AddressSet(set):

    config: 'iocage.lib.Config.Jail.JailConfig.JailConfig'  # type: ignore

    def __init__(
        self,
        config=None,
        property_name="ip4_address"
    ):

        self.config = config
        set.__init__(self)
        object.__setattr__(self, 'property_name', property_name)

    def add(self, value, notify=True):
        set.add(self, value)
        if notify:
            self.__notify()

    def remove(self, value, notify=True):
        set.remove(self, value)
        if notify:
            self.__notify()

    def __notify(self):
        self.config.update_special_property(self.property_name)


_AddressSetInputType = typing.Union[str, typing.Dict[str, AddressSet]]


class AddressesProp(dict):

    logger: 'iocage.lib.Logger.Logger'
    config: 'iocage.lib.Config.Jail.JailConfig.JailConfig'  # type: ignore
    property_name: str = "ip4_address"
    skip_on_error: bool

    def __init__(
        self,
        config=None,  # type: ignore
        property_name: str="ip4_address",
        logger: 'iocage.lib.Logger.Logger'=None,
        skip_on_error: bool=False
    ) -> None:

        dict.__init__(self, {})

        self.logger = logger
        self.config = config
        self.property_name = property_name
        self.skip_on_error = skip_on_error

    def set(self, data: _AddressSetInputType) -> None:

        self.clear()

        try:
            iocage.lib.helpers.parse_none(data)
            return
        except TypeError:
            pass

        if isinstance(data, dict):
            dict.__init__(self, data)
            return

        ip_addresses = data.split(" ")
        for ip_address_string in ip_addresses:

            try:
                nic, address = ip_address_string.split("|", maxsplit=1)
                self.add(nic, address)
            except ValueError:

                level = "warn" if (self.skip_on_error is True) else "error"

                iocage.lib.errors.InvalidJailConfigAddress(
                    jail=self.config.jail,
                    value=ip_address_string,
                    property_name=self.property_name,
                    logger=self.logger,
                    level=level
                )

                if self.skip_on_error is False:
                    exit(1)

    def add(
        self,
        nic: str,
        addresses: typing.Union[typing.List[str], str]=None,
        notify: bool=True
    ) -> None:

        if addresses is None or addresses == [] or addresses == "":
            return

        if isinstance(addresses, str):
            addresses = [addresses]

        try:
            prop = self[nic]
        except KeyError:
            prop = self.__empty_prop(nic)

        for address in addresses:
            prop.add(address, notify=False)

        if notify:
            self.__notify()

    @property
    def networks(self) -> typing.List[str]:
        """
        Flat list of all networks configured across all nics
        """
        networks: list = []
        for nic, addresses in self.items():
            networks += addresses
        return networks

    def __setitem__(
        self,
        key: str,
        addresses: typing.Union[typing.List[str], str]
    ) -> None:

        try:
            dict.__delitem__(self, key)
        except KeyError:
            pass

        self.add(key, addresses)

    def __delitem__(self, key: str) -> None:
        dict.__delitem__(self, key)
        self.__notify()

    def __notify(self) -> None:
        self.config.update_special_property(self.property_name)

    def __empty_prop(self, key: str) -> AddressSet:
        prop = AddressSet(self.config, property_name=self.property_name)
        dict.__setitem__(self, key, prop)
        return prop

    def __str__(self) -> str:
        if len(self) == 0:
            return ""
        out = []
        for nic in self:
            for address in self[nic]:
                out.append(f"{nic}|{address}")
        return str(" ".join(out))
