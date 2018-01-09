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


class NetworkInterface:

    ifconfig_command = "/sbin/ifconfig"
    dhclient_command = "/sbin/dhclient"
    rtsold_command = "/usr/sbin/rtsold"

    def __init__(
        self,
        name: typing.Optional[str]="vnet0",
        create: typing.Optional[bool]=False,
        ipv4_addresses: typing.Optional[str]=[],
        ipv6_addresses: typing.Optional[str]=[],
        mac: typing.Optional[str]=None,
        mtu: typing.Optional[int]=None,
        description: typing.Optional[str]=None,
        rename: typing.Optional[str]=None,
        group: typing.Optional[str]=None,
        addm: typing.Optional[typing.Union[str, typing.List[str]]]=None,
        vnet: typing.Optional[str]=None,
        jail: typing.Optional['iocage.lib.Jail.JailGenerator']=None,
        extra_settings: typing.Optional[str]=["up"],
        auto_apply: typing.Optional[bool]=True,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None
    ) -> None:

        self.jail = jail
        self.logger = iocage.lib.helpers.init_logger(self, logger)

        self.name = name
        self.create = create
        self.ipv4_addresses = ipv4_addresses
        self.ipv6_addresses = ipv6_addresses

        self.extra_settings = extra_settings
        self.settings = {}

        if mac:
            self.settings["link"] = mac

        if mtu:
            self.settings["mtu"] = str(mtu)

        if description:
            self.settings["description"] = f"\"{description}\""

        if vnet:
            self.settings["vnet"] = vnet

        if addm:
            self.settings["addm"] = addm

        if group:
            self.settings["group"] = group

        # rename interface when applying settings next time
        if isinstance(rename, str):
            self.rename = True
            self.settings["name"] = rename
        else:
            self.rename = False

        if auto_apply:
            self.apply()

    def apply(self) -> None:
        self.apply_settings()
        self.apply_addresses()

    def apply_settings(self) -> str:
        command = [self.ifconfig_command, self.name]

        if self.create is True:
            command.append("create")

        for key in self.settings:
            value = self.settings[key]
            if isinstance(value, str):
                values = [value]
            else:
                values = value
            for value in values:
                command.append(key)
                command.append(value)

        if self.extra_settings:
            command += self.extra_settings

        self.exec(command)

        # update name when the interface was renamed
        if self.rename:
            self.name = self.settings["name"]
            del self.settings["name"]
            self.rename = False

    def apply_addresses(self) -> None:
        self.__apply_addresses(self.ipv4_addresses, ipv6=False)
        self.__apply_addresses(self.ipv6_addresses, ipv6=True)

    def __apply_addresses(self, addresses, ipv6=False):
        family = "inet6" if ipv6 else "inet"
        for i, address in enumerate(addresses):
            if (ipv6 is False) and (address.lower() == "dhcp"):
                command = [self.dhclient_command, self.name]
            else:
                command = [self.ifconfig_command, self.name, family, address]

            if i > 0:
                command.append("alias")

            self.exec(command)

            if (ipv6 is True) and (address.lower() == "accept_rtadv"):
                self.exec([self.rtsold_command, self.name])

    def exec(
        self,
        command: typing.List[str],
        force_local: typing.Optional[bool]=False
    ) -> typing.Tuple['subprocess.Popen', str, str]:

        if self.__is_jail():
            _, stdout, _ = self.jail.exec(command)
        else:
            _, stdout, _ = iocage.lib.helpers.exec(command, logger=self.logger)

        if (self.create or self.rename) is True:
            self.name = stdout.strip()

    def __is_jail(self) -> bool:
        return (self.jail is not None)
