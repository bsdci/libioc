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
PoststopCommandList = typing.List[str]
StartCommandList = typing.List[str]


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
        StartCommandList,
        PoststartCommandList
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

    def teardown(self) -> typing.List[str]:
        """
        Teardown the applied changes.

        After Jails are stopped the devices that were used by it remain on the
        host. This method is called by jails after they terminated.
        """
        commands: typing.List[str] = []

        if self.vnet is False:
            return commands

        commands += self.__down_host_interface()

        if self._is_secure_bridge is True:
            commands += self.__down_secure_mode_devices()
            firewall_rule_number = f"$IOCAGE_NIC_ID_{self._unic}"
            self.firewall.delete_rule(firewall_rule_number)
            commands += self.firewall.read_commands()

        return commands

    def __down_host_interface(self) -> typing.List[str]:
        nic = iocage.lib.NetworkInterface.QueuingNetworkInterface(
            shell_variable_nic_name=f"IOCAGE_NIC_EPAIR_A_{self._unic}",
            extra_settings=["destroy"],
            logger=self.logger
        )
        commands: typing.List[str] = nic.read_commands()
        return commands

    def __down_secure_mode_devices(self) -> typing.List[str]:
        self.logger.verbose("Downing secure mode devices")
        commands: typing.List[str] = []
        secure_mode_nics = [
            f"$IOCAGE_NIC_EPAIR_C_{self._unic}",
            f"$IOCAGE_NIC_BRIDGE_{self._unic}"
        ]
        for nic in secure_mode_nics:
            commands += iocage.lib.NetworkInterface.QueuingNetworkInterface(
                name=nic,
                extra_settings=["destroy"]
            ).read_commands()
        return commands

    @property
    def nic_local_description(self) -> str:
        """Return the description text of the local NIC."""
        return f"associated with jail: {self.jail.humanreadable_name}"

    @property
    def _is_secure_bridge(self) -> bool:
        return (self.bridge is not None) and (self.bridge.secure is True)

    @property
    def temporary_nic_prefix(self) -> str:
        """Return the default NIC name prefix."""
        return f"ioc:{self.epair_id}"

    @property
    def _unic(self) -> str:
        """Return the uppercase nic name."""
        return self.nic.upper()

    @property
    def epair_id(self) -> int:
        """Return a unique ID for the jail network device combination."""
        m = sha224()
        m.update(self.jail.full_name.encode("UTF-8"))
        m.update(self.nic.encode("UTF-8"))
        return abs(int(m.hexdigest(), 16)) % 32678

    def __create_new_epair_interface(
        self,
        variable_name_a: str,
        variable_name_b: str,
        variable_epair_id: typing.Optional[str]=None,
        nic_suffix_a: str=":a",
        nic_suffix_b: str=":b",
        **nic_args: typing.Any
    ) -> PrestartCommandList:

        commands_start: PrestartCommandList = []

        commands_start += iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name="epair",
            create=True,
            shell_variable_nic_name=variable_name_a,
            logger=self.logger
        ).read_commands()

        self.epair_counter += 1

        commands_start.append(
            f"export {variable_name_b}="
            f"$(echo ${variable_name_a} | sed 's/.$/b/')"
        )

        if variable_epair_id is not None:
            commands_start.append(
                f"export {variable_epair_id}={self.epair_id}"
            )

        epair_a = iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name=None,
            rename=f"{self.temporary_nic_prefix}{nic_suffix_a}",
            destroy=True,
            shell_variable_nic_name=variable_name_a,
            logger=self.logger,
            **nic_args
        )
        commands_start += epair_a.read_commands()

        epair_b = iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name=None,
            rename=f"{self.temporary_nic_prefix}{nic_suffix_b}",
            destroy=True,
            shell_variable_nic_name=variable_name_b,
            logger=self.logger,
            **nic_args
        )
        commands_start += epair_b.read_commands()

        return commands_start

    def __create_vnet_iface(self) -> typing.Tuple[
        PrestartCommandList,
        StartCommandList,
        PoststartCommandList
    ]:

        commands_prestart: typing.List[str] = []
        commands_start: typing.List[str] = []
        commands_poststart: typing.List[str] = []

        if self.bridge is None:
            raise iocage.lib.errors.VnetBridgeMissing(logger=self.logger)

        if self._is_secure_bridge is True:
            self.firewall.ensure_firewall_enabled()

        commands_prestart = self.__create_new_epair_interface(
            variable_name_a=f"IOCAGE_NIC_EPAIR_A_{self._unic}",
            variable_name_b=f"IOCAGE_NIC_EPAIR_B_{self._unic}",
            nic_suffix_a="",
            nic_suffix_b=":j"
        )

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

        firewall_variable_name = f"IOCAGE_NIC_ID_{self._unic}"
        commands_prestart.append(
            f"export {firewall_variable_name}=\"{self.epair_id}\""
        )
        commands_poststart.append(
            f"export {firewall_variable_name}=\"\\$IOCAGE_JID\""
        )
        firewall_rule_number = f"${firewall_variable_name}"

        host_if = iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name=None,
            shell_variable_nic_name=f"IOCAGE_NIC_EPAIR_A_{self._unic}",
            mac=mac_address_pair.a,
            mtu=self.mtu,
            description=self.nic_local_description,
            # rename=self.nic_local_name,
            logger=self.logger
        )
        commands_prestart += host_if.read_commands()

        # rename host_if after jail start
        _host_if = iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name=None,
            shell_variable_nic_name=f"IOCAGE_NIC_EPAIR_A_{self._unic}",
            rename=f"{self.nic}:$IOCAGE_JID"
        )
        commands_poststart += _host_if.read_commands()

        if self._is_secure_bridge is False:
            jail_bridge = iocage.lib.NetworkInterface.QueuingNetworkInterface(
                name=self.bridge.name,
                addm=f"$IOCAGE_NIC_EPAIR_A_{self._unic}",
                logger=self.logger
            )
            commands_prestart += jail_bridge.read_commands()
        else:
            commands_prestart += self.__create_new_epair_interface(
                variable_name_a=f"IOCAGE_NIC_EPAIR_C_{self._unic}",
                variable_name_b=f"IOCAGE_NIC_EPAIR_D_{self._unic}",
                variable_epair_id=f"IOCAGE_NIC_EPAIR_ID_{self._unic}",
                nic_suffix_a=":a",
                nic_suffix_b=":b",
                mtu=self.mtu
            )

            self.logger.verbose("Configuring Secure VNET Firewall")

            for ipv4_address in self.ipv4_addresses:
                address = ipv4_address.split("/", maxsplit=1)[0]
                self.firewall.add_rule(firewall_rule_number, [
                    "allow", "ip4",
                    "from", address, "to", "any",
                    "layer2",
                    "MAC", "any", str(mac_address_pair.b),
                    "via", f"$IOCAGE_NIC_EPAIR_D_{self._unic}",
                    "out"
                ])
                self.firewall.add_rule(firewall_rule_number, [
                    "allow", "ip4",
                    "from", "any", "to", address,
                    "layer2",
                    "MAC", str(mac_address_pair.b), "any",
                    "via", f"${host_if.shell_variable_nic_name}",
                    "out"
                ])
                self.firewall.add_rule(firewall_rule_number, [
                    "allow", "ip4",
                    "from", "any", "to", address,
                    "via", f"${host_if.shell_variable_nic_name}",
                    "out"
                ])
            self.firewall.add_rule(firewall_rule_number, [
                "deny", "log", "ip4",
                "from", "any", "to", "any",
                "layer2",
                "via", f"$IOCAGE_NIC_EPAIR_D_{self._unic}",
                "out"
            ])
            self.firewall.add_rule(firewall_rule_number, [
                "deny", "log", "ip4",
                "from", "any", "to", "any",
                "via", f"${host_if.shell_variable_nic_name}",
                "out"
            ])
            self.logger.debug("Firewall rules added")

            firewall_commands = self.firewall.read_commands()
            commands_prestart += firewall_commands

            # the secondary bridge in secure mode
            sec_bridge = iocage.lib.NetworkInterface.QueuingNetworkInterface(
                name="bridge",
                create=True,
                destroy=True,
                rename=f"ioc:{self.epair_id}:net",
                shell_variable_nic_name=f"IOCAGE_NIC_BRIDGE_{self._unic}"
            )
            commands_prestart += sec_bridge.read_commands()

            _rename_cmd = iocage.lib.NetworkInterface.QueuingNetworkInterface(
                rename=f"{self.nic}:$IOCAGE_JID:net",
                shell_variable_nic_name=f"IOCAGE_NIC_BRIDGE_{self._unic}"
            ).read_commands()
            _rename_cmd += iocage.lib.NetworkInterface.QueuingNetworkInterface(
                rename=f"{self.nic}:$IOCAGE_JID:a",
                shell_variable_nic_name=f"IOCAGE_NIC_EPAIR_C_{self._unic}"
            ).read_commands()
            _rename_cmd += iocage.lib.NetworkInterface.QueuingNetworkInterface(
                rename=f"{self.nic}:$IOCAGE_JID:b",
                shell_variable_nic_name=f"IOCAGE_NIC_EPAIR_D_{self._unic}"
            ).read_commands()
            commands_poststart += _rename_cmd
            commands_poststart += firewall_commands

            # add nic to secure bridge
            sec_bridge = iocage.lib.NetworkInterface.QueuingNetworkInterface(
                name=None,
                shell_variable_nic_name=f"IOCAGE_NIC_BRIDGE_{self._unic}",
                addm=[
                    f"$IOCAGE_NIC_EPAIR_A_{self._unic}",
                    f"$IOCAGE_NIC_EPAIR_D_{self._unic}"
                ],
                logger=self.logger
            )
            commands_prestart += sec_bridge.read_commands()

            # add nic to jail bridge
            jail_bridge = iocage.lib.NetworkInterface.QueuingNetworkInterface(
                name=self.bridge.name,
                addm=f"$IOCAGE_NIC_EPAIR_C_{self._unic}",
                logger=self.logger
            )
            commands_prestart += jail_bridge.read_commands()

        commands_prestart += self.__up_host_if()

        # configure network inside the jail
        jail_if = iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name=None,
            shell_variable_nic_name=f"IOCAGE_NIC_EPAIR_B_{self._unic}",
            mac=str(mac_address_pair.b),
            mtu=self.mtu,
            rename=self.nic,
            jail=self.jail,
            ipv4_addresses=self.ipv4_addresses,
            ipv6_addresses=self.ipv6_addresses,
            logger=self.logger
        )
        commands_start += jail_if.read_commands()

        if self._is_secure_bridge is True:
            # replace the temporary rule created during prestart
            self.firewall.delete_rule(firewall_rule_number)
            delete_firewall_command = self.firewall.read_commands()
            commands_poststart = delete_firewall_command + commands_poststart

        return commands_prestart, commands_start, commands_poststart

    def __up_host_if(self) -> typing.List[str]:
        host_if = iocage.lib.NetworkInterface.QueuingNetworkInterface(
            name=None,
            shell_variable_nic_name=f"IOCAGE_NIC_EPAIR_A_{self._unic}",
            logger=self.logger
        )
        commands: typing.List[str] = host_if.read_commands()
        return commands

    @property
    def env(self) -> typing.Dict[str, typing.Union[str, int]]:
        """
        Return a dict of env variables used by the started jail.

        Not all jail variables might be used, but it is more convenient to
        always provide them all (especially for the *stop hooks).
        """
        if self.jail.running:
            return self._env_running
        else:
            return self._env_temporary

    @property
    def _env_running(self) -> typing.Dict[str, typing.Union[str, int]]:
        script_env: typing.Dict[str, typing.Union[str, int]] = {
            f"IOCAGE_NIC_EPAIR_A_{self._unic}": f"{self.nic}:$IOCAGE_JID",
            f"IOCAGE_NIC_EPAIR_B_{self._unic}": self.nic,
            f"IOCAGE_NIC_EPAIR_C_{self._unic}": f"{self.nic}:$IOCAGE_JID:a",
            f"IOCAGE_NIC_EPAIR_D_{self._unic}": f"{self.nic}:$IOCAGE_JID:b",
            f"IOCAGE_NIC_BRIDGE_{self._unic}": f"{self.nic}:$IOCAGE_JID:net",
            f"IOCAGE_NIC_ID_{self._unic}": self.epair_id
        }
        return script_env

    @property
    def _env_temporary(self) -> typing.Dict[str, typing.Union[str, int]]:
        identifier = self.temporary_nic_prefix
        script_env: typing.Dict[str, typing.Union[str, int]] = {
            f"IOCAGE_NIC_EPAIR_A_{self._unic}": identifier,
            f"IOCAGE_NIC_EPAIR_B_{self._unic}": f"{identifier}:j",
            f"IOCAGE_NIC_EPAIR_C_{self._unic}": f"{identifier}:a",
            f"IOCAGE_NIC_EPAIR_D_{self._unic}": f"{identifier}:b",
            f"IOCAGE_NIC_BRIDGE_{self._unic}": f"{identifier}:net",
            f"IOCAGE_NIC_ID_{self._unic}": self.epair_id
        }
        return script_env

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
