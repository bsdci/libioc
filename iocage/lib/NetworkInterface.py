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
import iocage.lib.helpers


class NetworkInterface:
    ifconfig_command = "/sbin/ifconfig"
    dhclient_command = "/sbin/dhclient"

    def __init__(self,
                 name="vnet0",
                 ipv4_addresses=[],
                 ipv6_addresses=[],
                 mac=None,
                 mtu=None,
                 description=None,
                 rename=None,
                 addm=None,
                 vnet=None,
                 jail=None,
                 extra_settings=[],
                 auto_apply=True,
                 logger=None):

        self.jail = jail

        self.name = name
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

        # rename interface when applying settings next time
        if isinstance(rename, str):
            self.rename = True
            self.settings["name"] = rename
        else:
            self.rename = False

        if auto_apply:
            self.apply()

    def apply(self):
        self.apply_settings()
        self.apply_addresses()

    def apply_settings(self):
        command = [self.ifconfig_command, self.name]
        for key in self.settings:
            command.append(key)
            command.append(self.settings[key])

        if self.extra_settings:
            command += self.extra_settings

        self.exec(command)

        # update name when the interface was renamed
        if self.rename:
            self.name = self.settings["name"]
            del self.settings["name"]
            self.rename = False

    def apply_addresses(self):
        self.__apply_addresses(self.ipv4_addresses, ipv6=False)
        self.__apply_addresses(self.ipv6_addresses, ipv6=True)

    def __apply_addresses(self, addresses, ipv6=False):
        family = "inet6" if ipv6 else "inet"
        for address in addresses:
            if address.lower() == "dhcp":
                command = [self.dhclient_command, self.name]
            else:
                command = [self.ifconfig_command, self.name, family, address]
            self.exec(command)

    def exec(self, command, force_local=False):
        if self.__is_jail():
            return self.jail.exec(command)
        else:
            return iocage.lib.helpers.exec(command)

    def __is_jail(self):
        return self.jail is not None
