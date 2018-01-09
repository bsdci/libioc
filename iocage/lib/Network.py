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
from hashlib import sha224

import iocage.lib.BridgeInterface
import iocage.lib.NetworkInterface
import iocage.lib.errors
import iocage.lib.helpers


class Network:
    """
    VNET Jails may have access to different networks. Each is identified by a
    network interface name that is unique to the jail.

    A Network is configured with IPv4 and IPv6 addresses, a bridge interface
    and an optional MTU.
    """

    bridge: typing.Optional['iocage.lib.BridgeInterface.BridgeInterface']
    nic: str = "vnet0"

    def __init__(
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        nic: typing.Optional[str]=None,
        ipv4_addresses: typing.Optional[typing.List[str]]=None,
        ipv6_addresses: typing.Optional[typing.List[str]]=None,
        mtu: typing.Optional[int]=1500,
        bridge: typing.Optional[
            'iocage.lib.BridgeInterface.BridgeInterface'
        ]=None,
        logger: 'iocage.lib.Logger.Logger'=None
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)

        if nic is not None:
            self.nic = nic

        self.vnet = True
        self.bridge = bridge
        self.jail = jail
        self.mtu = mtu
        self.ipv4_addresses = ipv4_addresses or []
        self.ipv6_addresses = ipv6_addresses or []

    def setup(self) -> None:
        """
        Jails call this method to create the network after being started
        and configure the interfaces on jail and host side according to the
        class attributes.
        """
        if (self.vnet is True) and (self.bridge is None):
            raise iocage.lib.errors.VnetBridgeMissing(logger=self.logger)
        self.__create_vnet_iface()

    def teardown(self) -> None:
        """
        After Jails are stopped the devices that were used by it remain on the
        host. This method is called by jails after they terminated.
        """
        if self.vnet is True:
            self.__down_host_interface()
            if self._is_secure_bridge is True:
                self.__down_secure_mode_devices()

    def __down_host_interface(self) -> None:
        iocage.lib.NetworkInterface.NetworkInterface(
            name=self.nic_local_name,
            extra_settings=["destroy"],
            logger=self.logger
        )

    def __down_secure_mode_devices(self) -> None:

        self.logger.verbose("Downing secure mode devices")

        for nic in [
            f"{self.nic_local_name}:a",
            f"{self.nic_local_name}:net"
        ]:

            iocage.lib.NetworkInterface.NetworkInterface(
                name=nic,
                extra_settings=["destroy"],
                logger=self.logger
            )

    @property
    def nic_local_name(self) -> str:
        """
        The Network NIC is unique per jail. Iocage appends the running jails
        JID to the device name, so that the epair device exposed to the jail
        host can be easily identified by the user.

        Example for JID 1: `vnet0:1`
        """
        self.jail.require_jail_running(silent=True)
        return f"{self.nic}:{self.jail.jid}"

    @property
    def nic_local_description(self) -> str:
        return f"associated with jail: {self.jail.humanreadable_name}"

    @property
    def _is_secure_bridge(self) -> bool:
        return (self.bridge is not None) and (self.bridge.secure is True)

    def __create_new_epair_interface(self) -> typing.Tuple[str, str]:
        epair_a = iocage.lib.NetworkInterface.NetworkInterface(
            name="epair",
            create=True,
            logger=self.logger
        )
        epair_a_name = epair_a.name
        epair_b_name = f"{epair_a_name[:-1]}b"
        return epair_a_name, epair_b_name

    def __create_vnet_iface(
        self
    ) -> typing.Tuple[
        iocage.lib.NetworkInterface.NetworkInterface,
        iocage.lib.NetworkInterface.NetworkInterface
    ]:
        if self.bridge is None:
            raise iocage.lib.errors.VnetBridgeMissing(logger=self.logger)

        epair_a, epair_b = self.__create_new_epair_interface()

        try:
            mac_config = self.jail.config[f"{self.nic}_mac"]
            if mac_config is None or mac_config == "":
                raise Exception("no manual mac address")
            mac_a, mac_b = mac_config.split(',')
        except Exception:
            mac_a, mac_b = self.__generate_mac_address_pair()

        host_if = iocage.lib.NetworkInterface.NetworkInterface(
            name=epair_a,
            mac=mac_a,
            mtu=self.mtu,
            description=self.nic_local_description,
            rename=self.nic_local_name,
            logger=self.logger
        )

        if self._is_secure_bridge is False:
            bridge_name = self.bridge.name
            self.__add_nic_to_bridge(self.nic_local_name, bridge_name)
        else:
            epair_c, epair_d = self.__create_new_epair_interface()
            left_if = f"{self.nic_local_name}:a"
            right_if = f"{self.nic_local_name}:b"
            iocage.lib.NetworkInterface.NetworkInterface(
                name=epair_c,
                rename=left_if,
                mtu=self.mtu,
                logger=self.logger
            )
            iocage.lib.NetworkInterface.NetworkInterface(
                name=epair_d,
                rename=right_if,
                mtu=self.mtu,
                logger=self.logger
            )
            # bridge_name is the secondary bridge name in secure mode
            bridge = iocage.lib.NetworkInterface.NetworkInterface(
                name="bridge",
                create=True,
                rename=f"{self.nic_local_name}:net",
            )
            bridge_name = bridge.name
            iocage.lib.NetworkInterface.NetworkInterface(
                name=bridge_name,
                addm=[
                    right_if,
                    self.nic_local_name
                ]
            )
            self.__add_nic_to_bridge(left_if, self.bridge.name)

        self.__up_host_if()

        # assign epair_b to jail
        self.__assign_vnet_iface_to_jail(epair_b, self.jail.identifier)

        jail_if = iocage.lib.NetworkInterface.NetworkInterface(
            name=epair_b,
            mac=mac_b,
            mtu=self.mtu,
            rename=self.nic,
            jail=self.jail,
            ipv4_addresses=self.ipv4_addresses,
            ipv6_addresses=self.ipv6_addresses,
            logger=self.logger
        )

        return jail_if, host_if

    def __add_nic_to_bridge(self, nic: str, bridge_name: str) -> None:
        iocage.lib.NetworkInterface.NetworkInterface(
            name=bridge_name,
            addm=nic,
            logger=self.logger
        )

    def __up_host_if(self) -> None:
        iocage.lib.NetworkInterface.NetworkInterface(
            name=self.nic_local_name,
            logger=self.logger
        )

    def __assign_vnet_iface_to_jail(
        self,
        nic: str,
        jail_name: str
    ) -> None:
        iocage.lib.NetworkInterface.NetworkInterface(
            name=nic,
            vnet=jail_name,
            extra_settings=[],
            logger=self.logger
        )

    def __generate_mac_bytes(self) -> str:
        m = sha224()
        m.update(self.jail.name.encode("utf-8"))
        m.update(self.nic.encode("utf-8"))
        prefix = self.jail.config["mac_prefix"]
        return f"{prefix}{m.hexdigest()[0:12-len(prefix)]}"

    def __generate_mac_address_pair(self) -> typing.Tuple[str, str]:
        mac_a = self.__generate_mac_bytes()
        mac_b = hex(int(mac_a, 16) + 1)[2:].zfill(12)
        return mac_a, mac_b
