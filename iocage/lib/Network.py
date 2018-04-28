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
"""iocage network abstraction module."""
import typing
from hashlib import sha224

import iocage.lib.BridgeInterface
import iocage.lib.MacAddress
import iocage.lib.NetworkInterface
import iocage.lib.Firewall
import iocage.lib.errors
import iocage.lib.helpers

PrestartCommandList = typing.List[str]
PoststartCommandList = typing.List[str]
JailCommandList = typing.List[str]


class Network:
    """
    Networking for VNET jails.

    VNET Jails may have access to different networks. Each is identified by a
    network interface name that is unique to the jail.

    A Network is configured with IPv4 and IPv6 addresses, a bridge interface
    and an optional MTU.
    """

    bridge: typing.Optional['iocage.lib.BridgeInterface.BridgeInterface']
    nic: str = "vnet0"
    epair_counter: int

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
        self.firewall = iocage.lib.Firewall.QueuingFirewall(
            logger=self.logger
        )

        self.epair_counter = 0

        if nic is not None:
            self.nic = nic

        self.vnet = True
        self.bridge = bridge
        self.jail = jail
        self.mtu = mtu
        self.ipv4_addresses = ipv4_addresses or []
        self.ipv6_addresses = ipv6_addresses or []

    def setup(self) -> typing.Tuple[
        PrestartCommandList,
        PoststartCommandList,
        JailCommandList,
        str
    ]:
        """
        Apply the network configuration.

        Jails call this method to create the network after being started
        and configure the interfaces on jail and host side according to the
        class attributes.
        """
        if (self.vnet is True) and (self.bridge is None):
            raise iocage.lib.errors.VnetBridgeMissing(logger=self.logger)
        return self.__create_vnet_iface()

    def teardown(self) -> None:
        """
        Teardown the applied changes.

        After Jails are stopped the devices that were used by it remain on the
        host. This method is called by jails after they terminated.
        """
        if self.vnet is True:
            self.__down_host_interface()
            if self._is_secure_bridge is True:
                self.__down_secure_mode_devices()
                self.firewall.delete_rule(self.jail.jid)

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
    def nic_local_description(self) -> str:
        """Return the description text of the local NIC."""
        return f"associated with jail: {self.jail.humanreadable_name}"

    @property
    def _is_secure_bridge(self) -> bool:
        return (self.bridge is not None) and (self.bridge.secure is True)

    def __hash__(self) -> int:
        return hash("".join([
            self.jail.full_name,
            self.nic,
            str(self.epair_counter)
        ]))

    @property
    def epair_id(self) -> int:
        return self.__hash__() % 32768

    def __create_new_epair_interface(
        self,
        variable_name_a: str="_IOCAGE_NIC_EPAIR_A",
        variable_name_b: str="_IOCAGE_NIC_EPAIR_B",
        variable_epair_id: str="_IOCAGE_NIC_EPAIR_NUMBER",
    ) -> typing.List[str]:

        commands = iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name="epair",
            create=True,
            shell_variable_nic_name=variable_name_a,
            logger=self.logger
        ).read_commands()

        self.epair_counter += 1

        commands.append(
            f"export {variable_name_b}="
            f"$(echo ${variable_name_a} | sed 's/.$/b/')"
        )

        commands.append(
            f"export {variable_epair_id}={self.epair_id}"
        )

        commands += iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name=None,
            rename=f"ioc{self.epair_id}a",
            shell_variable_nic_name=variable_name_a,
            logger=self.logger
        ).read_commands()

        epair_b = iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name=None,
            rename=f"ioc{self.epair_id}b",
            shell_variable_nic_name=variable_name_b,
            logger=self.logger
        )
        commands += epair_b.read_commands()

        return commands

    def __create_vnet_iface(self) -> typing.Tuple[
        PrestartCommandList,
        PoststartCommandList,
        JailCommandList,
        str
    ]:

        commands_prestart: typing.List[str] = []
        commands_poststart: typing.List[str] = []
        commands_jail: typing.List[str] = []
        env_variables: typing.Dict[str, str] = {}

        if self.bridge is None:
            raise iocage.lib.errors.VnetBridgeMissing(logger=self.logger)

        if self._is_secure_bridge is True:
            self.firewall.ensure_firewall_enabled()

        commands_prestart += self.__create_new_epair_interface()
        # this interface will be assigned to the jail later on
        vnet_if = f"ioc{self.epair_id}b"

        try:
            mac_config = self.jail.config[f"{self.nic}_mac"]
        except KeyError:
            mac_config = None
        if mac_config is None or mac_config == "":
            mac_address_pair = self.__generate_mac_address_pair()
        else:
            mac_address_pair = iocage.lib.MacAddress.MacAddressPair(
                mac_config,
                logger=self.logger
            )

        host_if = iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name=None,
            shell_variable_nic_name="_IOCAGE_NIC_EPAIR_A",
            mac=mac_address_pair.a,
            mtu=self.mtu,
            description=self.nic_local_description,
            # rename=self.nic_local_name,
            logger=self.logger
        )
        commands_prestart += host_if.read_commands()

        if self._is_secure_bridge is False:
            bridge_name = self.bridge.name
            jail_bridge = iocage.lib.NetworkInterface.QueuingNetworkInterface(
                name=self.bridge.name,
                addm="$_IOCAGE_NIC_EPAIR_A",
                logger=self.logger
            )
            commands_prestart += jail_bridge.read_commands()
        else:
            commands_prestart += self.__create_new_epair_interface(
                "_IOCAGE_NIC_EPAIR_C",
                "_IOCAGE_NIC_EPAIR_D",
                "_IOCAGE_NIC_SECURE_EPAIR_NUMBER"
            )
            #left_if = f"{self.nic_local_name}:a"
            #right_if = f"{self.nic_local_name}:b"
            epair_c = iocage.lib.NetworkInterface.QueuingNetworkInterface(
                name=None,
                shell_variable_nic_name="_IOCAGE_NIC_EPAIR_C",
                #rename=left_if,
                mtu=self.mtu,
                logger=self.logger
            )
            commands_prestart += epair_c.read_commands()
            epair_d = iocage.lib.NetworkInterface.QueuingNetworkInterface(
                name=None,
                shell_variable_nic_name="_IOCAGE_NIC_EPAIR_D",
                #rename=right_if,
                mtu=self.mtu,
                logger=self.logger
            )
            commands_prestart += epair_d.read_commands()

            self.logger.verbose("Configuring Secure VNET Firewall")

            firewall_rule_number = "$_IOCAGE_NIC_SECURE_EPAIR_NUMBER"
            for ipv4_address in self.ipv4_addresses:
                address = ipv4_address.split("/", maxsplit=1)[0]
                self.firewall.add_rule(firewall_rule_number, [
                    "allow", "ip4",
                    "from", address, "to", "any",
                    "layer2",
                    "MAC", "any", str(mac_address_pair.b),
                    "via", epair_d.current_nic_name,
                    "out"
                ])
                self.firewall.add_rule(firewall_rule_number, [
                    "allow", "ip4",
                    "from", "any", "to", address,
                    "layer2",
                    "MAC", str(mac_address_pair.b), "any",
                    "via", host_if.current_nic_name,
                    "out"
                ])
                self.firewall.add_rule(firewall_rule_number, [
                    "allow", "ip4",
                    "from", "any", "to", address,
                    "via", host_if.current_nic_name,
                    "out"
                ])
            self.firewall.add_rule(firewall_rule_number, [
                "deny", "log", "ip4",
                "from", "any", "to", "any",
                "layer2",
                "via", epair_d.current_nic_name,
                "out"
            ])
            self.firewall.add_rule(firewall_rule_number, [
                "deny", "log", "ip4",
                "from", "any", "to", "any",
                "via", host_if.current_nic_name,
                "out"
            ])
            self.logger.debug("Firewall rules added")
            commands_prestart += self.firewall.read_commands()

            # the secondary bridge in secure mode
            sec_bridge = iocage.lib.NetworkInterface.QueuingNetworkInterface(
                name="bridge",
                create=True,
                rename=f"ioc{self.epair_id}sec",
                shell_variable_nic_name="_IOCAGE_SEC_BRIDGE"
            )
            commands_prestart += sec_bridge.read_commands()

            # add nic to secure bridge
            sec_bridge = iocage.lib.NetworkInterface.QueuingNetworkInterface(
                name=None,
                shell_variable_nic_name="_IOCAGE_SEC_BRIDGE",
                addm=[
                    "$_IOCAGE_NIC_EPAIR_A",
                    "$_IOCAGE_NIC_EPAIR_D",
                ],
                logger=self.logger
            )
            commands_prestart += sec_bridge.read_commands()

            # add nic to jail bridge
            jail_bridge = iocage.lib.NetworkInterface.QueuingNetworkInterface(
                name=self.bridge.name,
                addm="$_IOCAGE_NIC_EPAIR_C",
                logger=self.logger
            )
            commands_prestart += jail_bridge.read_commands()

        commands_prestart += self.__up_host_if()

        # configure network inside the jail
        jail_if = iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name=None,
            shell_variable_nic_name="_IOCAGE_NIC_EPAIR_B",
            mac=str(mac_address_pair.b),
            mtu=self.mtu,
            rename=self.nic,
            jail=self.jail,
            ipv4_addresses=self.ipv4_addresses,
            ipv6_addresses=self.ipv6_addresses,
            logger=self.logger
        )
        commands_jail += jail_if.read_commands()

        # copy env variables from pre-start to post-start
        commands_prestart.append(
            f"env | grep ^_IOCAGE_ > {self.jail.script_env_path}"
        )

        return commands_prestart, commands_poststart, commands_jail, vnet_if

    def __up_host_if(self) -> typing.List[str]:
        host_if = iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name=None,
            shell_variable_nic_name="_IOCAGE_NIC_EPAIR_A",
            logger=self.logger
        )
        return host_if.read_commands()

    def __generate_mac_bytes(self) -> str:
        m = sha224()
        m.update(self.jail.name.encode("utf-8"))
        m.update(self.nic.encode("utf-8"))
        prefix = self.jail.config["mac_prefix"]
        return f"{prefix}{m.hexdigest()[0:12-len(prefix)]}"

    def __generate_mac_address_pair(
        self
    ) -> iocage.lib.MacAddress.MacAddressPair:
        mac_a = self.__generate_mac_bytes()
        mac_b = hex(int(mac_a, 16) + 1)[2:].zfill(12)
        return iocage.lib.MacAddress.MacAddressPair(
            (mac_a, mac_b,),
            logger=self.logger
        )
