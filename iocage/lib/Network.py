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
import subprocess
from hashlib import md5

import iocage.lib.NetworkInterface
import iocage.lib.errors
import iocage.lib.helpers


class Network:
    def __init__(self, jail,
                 nic="vnet0",
                 ipv4_addresses=[],
                 ipv6_addresses=[],
                 mtu=1500,
                 bridges=None,
                 logger=None):

        self.logger = iocage.lib.helpers.init_logger(self, logger)

        if bridges is not None:
            if not isinstance(bridges, list):
                raise iocage.lib.errors.InvalidNetworkBridge(
                    reason="Expected None or list of strings",
                    logger=self.logger
                )

        self.vnet = True
        self.bridges = bridges
        self.jail = jail
        self.nic = nic
        self.mtu = mtu
        self.ipv4_addresses = ipv4_addresses
        self.ipv6_addresses = ipv6_addresses

    def setup(self):
        if self.vnet:
            if not self.bridges or len(self.bridges) == 0:
                raise iocage.lib.errors.VnetBridgeMissing(
                    logger=self.logger
                )

            jail_if, host_if = self.__create_vnet_iface()

    def teardown(self):
        if self.vnet:
            # down host_if
            iocage.lib.NetworkInterface.NetworkInterface(
                name=self.nic_local_name,
                extra_settings=["down"],
                logger=self.logger
            )

    @property
    def nic_local_name(self):
        self.jail.require_jail_running(silent=True)
        return f"{self.nic}:{self.jail.jid}"

    @property
    def nic_local_description(self):
        return f"associated with jail: {self.jail.humanreadable_name}"

    def __create_vnet_iface(self):

        # create new epair interface
        epair_a_cmd = ["ifconfig", "epair", "create"]
        epair_a = subprocess.Popen(
            epair_a_cmd, stdout=subprocess.PIPE, shell=False).communicate()[0]
        epair_a = epair_a.decode("utf-8").strip()
        epair_b = f"{epair_a[:-1]}b"

        mac_a, mac_b = self.__generate_mac_address_pair()

        host_if = iocage.lib.NetworkInterface.NetworkInterface(
            name=epair_a,
            mac=mac_a,
            mtu=self.mtu,
            description=self.nic_local_description,
            rename=self.nic_local_name,
            logger=self.logger
        )

        # add host_if to bridges
        for bridge in self.bridges:
            iocage.lib.NetworkInterface.NetworkInterface(
                name=bridge,
                addm=self.nic_local_name,
                extra_settings=["up"],
                logger=self.logger
            )

        # up host_if
        iocage.lib.NetworkInterface.NetworkInterface(
            name=self.nic_local_name,
            extra_settings=["up"],
            logger=self.logger
        )

        # assign epair_b to jail
        self.__assign_vnet_iface_to_jail(epair_b, self.jail.identifier)

        jail_if = iocage.lib.NetworkInterface.NetworkInterface(
            name=epair_b,
            mac=mac_b,
            mtu=self.mtu,
            rename=self.nic,
            jail=self.jail,
            extra_settings=["up"],
            ipv4_addresses=self.ipv4_addresses,
            ipv6_addresses=self.ipv6_addresses,
            logger=self.logger
        )

        return jail_if, host_if

    def __assign_vnet_iface_to_jail(self, nic, jail_name):
        iocage.lib.NetworkInterface.NetworkInterface(
            name=nic,
            vnet=jail_name,
            logger=self.logger
        )

    def __generate_mac_bytes(self):
        m = md5()
        m.update(self.jail.name.encode("utf-8"))
        m.update(self.nic.encode("utf-8"))
        prefix = self.jail.config["mac_prefix"]
        return f"{prefix}{m.hexdigest()[0:12-len(prefix)]}"

    def __generate_mac_address_pair(self):
        mac_a = self.__generate_mac_bytes()
        mac_b = hex(int(mac_a, 16) + 1)[2:].zfill(12)
        return mac_a, mac_b
