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
"""ioc network abstraction module."""
import typing
import shlex
import ipaddress
from hashlib import sha224

import libioc.BridgeInterface
import libioc.MacAddress
import libioc.NetworkInterface
import libioc.Firewall
import libioc.errors
import libioc.helpers_object

CreatedCommandList = typing.List[str]
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

    bridge: typing.Optional[libioc.BridgeInterface.BridgeInterface]
    nic: str = "vnet0"
    _nic_hash_cache: typing.Dict[str, str]
    _mtu: typing.Optional[int]

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        nic: typing.Optional[str]=None,
        ipv4_addresses: typing.Optional[typing.List[str]]=None,
        ipv6_addresses: typing.Optional[typing.List[str]]=None,
        mtu: typing.Optional[int]=None,
        bridge: typing.Optional[
            'libioc.BridgeInterface.BridgeInterface'
        ]=None,
        logger: 'libioc.Logger.Logger'=None
    ) -> None:

        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.firewall = libioc.Firewall.Firewall(
            logger=self.logger
        )

        if nic is not None:
            self.nic = nic

        self.vnet = True
        self.bridge = bridge
        self.jail = jail
        self._mtu = mtu
        self.ipv4_addresses = ipv4_addresses or []
        self.ipv6_addresses = ipv6_addresses or []
        self._nic_hash_cache = {}

    def setup(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.VnetInterfaceConfig', None, None]:
        """
        Apply the network configuration.

        Jails call this method to create the network after being started
        and configure the interfaces on jail and host side according to the
        class attributes.
        """
        if (self.vnet is True):
            self.__require_bridge()

        event = libioc.events.VnetInterfaceConfig(
            jail=self.jail,
            scope=event_scope
        )
        yield event.begin()

        try:
            self.__create_vnet_iface()
        except Exception as e:
            yield event.fail(e)
            raise e

        yield event.end()

    def teardown(
        self,
        jid: typing.Optional[int]=None,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.VnetInterfaceConfig', None, None]:
        """
        Teardown the applied changes.

        After Jails are stopped the devices that were used by it remain on the
        host. This method is called by jails after they terminated.
        """
        event = libioc.events.VnetInterfaceConfig(
            jail=self.jail,
            scope=event_scope
        )
        yield event.begin()

        if self.vnet is False:
            yield event.skip()
            return

        if jid is None:
            jid = self.jail.jid

        try:
            self.__down_host_interface(jid)

            if self._is_secure_vnet_bridge is True:
                self.__down_secure_mode_devices(jid)
                self.firewall.delete_rule(jid)
        except Exception as e:
            yield event.fail(e)
            raise e

        yield event.end()

    def __require_bridge(self) -> None:
        if (self.bridge is None):
            raise libioc.errors.VnetBridgeMissing(logger=self.logger)

    def __down_host_interface(self, jid: int) -> None:
        libioc.NetworkInterface.NetworkInterface(
            name=f"{self._escaped_nic_name}:{jid}",
            extra_settings=["destroy"],
            logger=self.logger
        )

    def __down_secure_mode_devices(self, jid: int) -> None:
        self.logger.verbose("Downing secure mode devices")
        secure_mode_nics = [
            f"{self._escaped_nic_name}:{jid}:a",
            f"{self._escaped_nic_name}:{jid}:net"
        ]
        for nic in secure_mode_nics:
            libioc.NetworkInterface.NetworkInterface(
                name=nic,
                extra_settings=["destroy"]
            )

    @property
    def mtu(self) -> int:
        """Return the configured MTU."""
        if self._mtu is not None:
            return self._mtu
        return self.__autodetected_bridge_mtu

    @mtu.setter
    def mtu(self, mtu: int) -> None:
        """Set the networks MTU."""
        self._mtu = mtu

    @property
    def __autodetected_bridge_mtu(self) -> int:
        self.__require_bridge()
        bridge = self.bridge  # type: libioc.BridgeInterface.BridgeInterface
        try:
            mtu = int(libioc.helpers_ioctl.get_interface_mtu(bridge.name))
            self.logger.debug(f"Bridge {bridge.name} MTU detected: {mtu}")
        except OSError:
            self.logger.debug(f"Bridge {bridge.name} MTU detection failed")
            raise libioc.errors.VnetBridgeDoesNotExist(
                bridge_name=bridge.name,
                logger=self.logger
            )
        self._mtu = mtu
        return mtu

    @property
    def nic_local_description(self) -> str:
        """Return the description text of the local NIC."""
        return f"associated with jail: {self.jail.humanreadable_name}"

    @property
    def _escaped_nic_name(self) -> str:
        return str(shlex.quote(self.nic))

    @property
    def _is_secure_vnet_bridge(self) -> bool:
        return (self.bridge is not None) and (self.bridge.secure_vnet is True)

    @property
    def _nic_hash(self) -> str:
        """Return the uppercase nic name."""
        if self.nic in self._nic_hash_cache:
            return self._nic_hash_cache[self.nic]
        m = sha224()
        m.update(self.nic.encode("UTF-8", errors="ignore"))
        short_hash = str(hex(abs(int(m.hexdigest(), 16)) % (2 << 32))[2:])
        short_hash = short_hash.upper()
        self._nic_hash_cache[self.nic] = short_hash
        return short_hash

    @property
    def epair_id(self) -> int:
        """Return a unique ID for the jail network device combination."""
        m = sha224()
        m.update(self.jail.full_name.encode("UTF-8", errors="ignore"))
        m.update(self.nic.encode("UTF-8", errors="ignore"))
        return abs(int(m.hexdigest(), 16)) % (2 << 14)

    def __create_new_epair_interface(
        self,
        nic_suffix_a: str=":a",
        nic_suffix_b: str=":b",
        mac_addresses: typing.Optional[libioc.MacAddress.MacAddressPair]=None,
        **nic_args: typing.Any
    ) -> typing.Tuple[
        libioc.NetworkInterface.NetworkInterface,
        libioc.NetworkInterface.NetworkInterface
    ]:

        if mac_addresses is None:
            nic_a_mac = None
            nic_b_mac = None
        else:
            nic_a_mac = mac_addresses.a
            nic_b_mac = mac_addresses.b

        nic_a = libioc.NetworkInterface.NetworkInterface(
            name="epair",
            create=True,
            logger=self.logger
        )
        nic_b_name = nic_a.name[:-1] + "b"

        nic_a = libioc.NetworkInterface.NetworkInterface(
            name=nic_a.name,
            rename=f"{self._escaped_nic_name}:{self.jail.jid}{nic_suffix_a}",
            logger=self.logger,
            mac=nic_a_mac,
            **nic_args
        )

        nic_b = libioc.NetworkInterface.NetworkInterface(
            name=nic_b_name,
            rename=f"{self._escaped_nic_name}:{self.jail.jid}{nic_suffix_b}",
            logger=self.logger,
            mac=nic_b_mac,
            **nic_args
        )

        return nic_a, nic_b

    def __create_vnet_iface(
        self
    ) -> None:

        if self._is_secure_vnet_bridge is True:
            try:
                self.firewall.ensure_firewall_enabled()
            except libioc.errors.FirewallDisabled as error:
                raise error

        mac_config_key = f"{self._escaped_nic_name}_mac"
        if mac_config_key in self.jail.config.keys():
            mac_config = self.jail.config[mac_config_key]
        else:
            mac_config = None

        if mac_config is None or mac_config == "":
            mac_address_pair = self.__generate_mac_address_pair()
        else:
            mac_address_pair = libioc.MacAddress.MacAddressPair(
                mac_config,
                logger=self.logger
            )

        nic_a, nic_b = self.__create_new_epair_interface(
            nic_suffix_a="",
            nic_suffix_b=":j",
            mac_addresses=mac_address_pair,
            mtu=self.mtu,
            description=self.nic_local_description,
        )

        self.__require_bridge()
        bridge = self.bridge  # type: libioc.BridgeInterface.BridgeInterface

        if self._is_secure_vnet_bridge is False:
            libioc.NetworkInterface.NetworkInterface(
                name=bridge.name,
                addm=nic_a.name,
                logger=self.logger
            )
        else:
            nic_c, nic_d = self.__create_new_epair_interface(
                nic_suffix_a=":a",
                nic_suffix_b=":b",
                mtu=self.mtu
            )

            self.__configure_firewall(
                mac_address=str(mac_address_pair.b)
            )

            # the secondary bridge in secure mode
            sec_bridge = libioc.NetworkInterface.NetworkInterface(
                name="bridge",
                create=True,
                destroy=True,
                rename=f"{self._escaped_nic_name}:{self.jail.jid}:net"
            )

            # ToDo: merge with above step by moving addm
            # add nic to secure bridge
            libioc.NetworkInterface.NetworkInterface(
                name=sec_bridge.name,
                addm=[
                    nic_a.name,
                    nic_d.name
                ],
                logger=self.logger
            )

            # add nic to jail bridge
            libioc.NetworkInterface.NetworkInterface(
                name=bridge.name,
                addm=nic_c.name,
                logger=self.logger
            )

        # up host if
        libioc.NetworkInterface.NetworkInterface(
            name=nic_a.name,
            logger=self.logger
        )

        # assign epair_b to jail
        libioc.NetworkInterface.NetworkInterface(
            name=nic_b.name,
            vnet=self.jail.identifier,
            extra_settings=[],
            logger=self.logger
        )

        # configure network inside the jail
        libioc.NetworkInterface.NetworkInterface(
            name=f"{self._escaped_nic_name}:{self.jail.jid}:j",
            mac=str(mac_address_pair.b),
            mtu=self.mtu,
            rename=self._escaped_nic_name,
            jail=self.jail,
            ipv4_addresses=self.ipv4_addresses,
            ipv6_addresses=self.ipv6_addresses,
            logger=self.logger
        )

    def __configure_firewall(self, mac_address: str) -> None:

        self.logger.verbose(
            f"Configuring Secure VNET Firewall for {self._escaped_nic_name}"
        )
        firewall_rule_number = self.jail.jid

        for protocol in ["ipv4", "ipv6"]:
            addresses = self.__getattribute__(f"{protocol}_addresses")
            for address in addresses:
                try:
                    _address = str(address.ip)
                except ipaddress.AddressValueError:
                    self.logger.warn(
                        f"Firewall permit not possible for address '{address}'"
                    )
                    continue
                self.firewall.add_rule(firewall_rule_number, [
                    "allow", protocol,
                    "from", _address, "to", "any",
                    "layer2",
                    "MAC", "any", mac_address,
                    "via", f"{self._escaped_nic_name}:{self.jail.jid}:b",
                    "out"
                ])
                self.firewall.add_rule(firewall_rule_number, [
                    "allow", protocol,
                    "from", "any", "to", _address,
                    "layer2",
                    "MAC", mac_address, "any",
                    "via", f"{self._escaped_nic_name}:{self.jail.jid}",
                    "out"
                ])
                self.firewall.add_rule(firewall_rule_number, [
                    "allow", protocol,
                    "from", "any", "to", _address,
                    "via", f"{self._escaped_nic_name}:{self.jail.jid}",
                    "out"
                ])
            self.firewall.add_rule(firewall_rule_number, [
                "deny", "log", protocol,
                "from", "any", "to", "any",
                "layer2",
                "via", f"{self._escaped_nic_name}:{self.jail.jid}:b",
                "out"
            ])
            self.firewall.add_rule(firewall_rule_number, [
                "deny", "log", protocol,
                "from", "any", "to", "any",
                "via", f"{self._escaped_nic_name}:{self.jail.jid}",
                "out"
            ])
        self.logger.debug("Firewall rules added")

    def __generate_mac_bytes(self) -> str:
        m = sha224()
        m.update(self.jail.name.encode("utf-8"))
        m.update(self.nic.encode("utf-8", errors="ignore"))
        prefix = self.jail.config["mac_prefix"]
        return f"{prefix}{m.hexdigest()[0:12-len(prefix)]}"

    def __generate_mac_address_pair(
        self
    ) -> libioc.MacAddress.MacAddressPair:
        mac_a = self.__generate_mac_bytes()
        mac_b = hex(int(mac_a, 16) + 1)[2:].zfill(12)
        return libioc.MacAddress.MacAddressPair(
            (mac_a, mac_b,),
            logger=self.logger
        )
