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
import libiocage.lib.errors


class AddressSet(set):
    def __init__(self, jail_config=None, property_name="ip4_address"):
        self.jail_config = jail_config
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
        self.jail_config.update_special_property(self.property_name)


class JailConfigAddresses(dict):
    def __init__(self, value, jail_config=None, property_name="ip4_address",
                 logger=None, skip_on_error=False):
        dict.__init__(self, {})
        dict.__setattr__(self, 'logger', logger)
        dict.__setattr__(self, 'jail_config', jail_config)
        dict.__setattr__(self, 'property_name', property_name)
        dict.__setattr__(self, 'skip_on_error', skip_on_error)

        if value != None:
            self.read(value)

    def read(self, config_line):

        config_line = config_line.strip()

        if config_line == "" or config_line == "-" or config_line == "none":
            return

        ip_addresses = config_line.split(" ")
        for ip_address_string in ip_addresses:

            try:
                nic, address = ip_address_string.split("|", maxsplit=1)
                self.add(nic, address)
            except ValueError:

                level = "warn" if (self.skip_on_error is True) else "error"

                libiocage.lib.errors.InvalidJailConfigAddress(
                    jail=self.jail_config.jail,
                    value=ip_address_string,
                    property_name=self.property_name,
                    logger=self.logger,
                    level=level
                )

                if self.skip_on_error is False:
                    exit(1)

    def add(self, nic, addresses=None, notify=True):

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
    def networks(self):
        """
        Flat list of all networks configured across all nics
        """
        networks = []
        for nic, addresses in self.items():
            networks += addresses
        return networks

    def __setitem__(self, key, values):

        try:
            dict.__delitem__(self, key)
        except KeyError:
            pass

        self.add(key, values)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self.__notify()

    def __notify(self):
        self.jail_config.update_special_property(self.property_name)

    def __empty_prop(self, key):

        prop = AddressSet(self.jail_config, property_name=self.property_name)
        dict.__setitem__(self, key, prop)
        return prop

    def __str__(self):
        out = []
        for nic in self:
            for address in self[nic]:
                out.append(f"{nic}|{address}")
        return str(" ".join(out))
