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
"""Model if an iocage jails network interface."""
import typing
import ipaddress
import shlex

import libioc.helpers
import libioc.helpers_object
import libioc.CommandQueue


class NetworkInterface:
    """
    Model if an iocage jails network interface.

    NetworkInterface abstracts interface configurations and commands executed
    on the host or within jails. This class is internally used by Network.
    """

    ifconfig_command = "/sbin/ifconfig"
    dhclient_command = "/sbin/dhclient"
    rtsold_command = "/usr/sbin/rtsold"

    name: typing.Optional[str]
    settings: typing.Dict[
        str,
        typing.Union[
            str,
            int,
            typing.List[str],
            typing.List[int]
        ]
    ]
    extra_settings: typing.List[str]
    rename: bool
    create: bool
    destroy: bool
    insecure: bool

    def __init__(
        self,
        name: typing.Optional[str]="vnet0",
        create: bool=False,
        ipv4_addresses: typing.List[ipaddress.IPv4Interface]=[],
        ipv6_addresses: typing.List[ipaddress.IPv6Interface]=[],
        mac: typing.Optional[
            typing.Union[str, 'libioc.MacAddress.MacAddress']
        ]=None,
        mtu: typing.Optional[int]=None,
        description: typing.Optional[str]=None,
        rename: typing.Optional[str]=None,
        group: typing.Optional[str]=None,
        addm: typing.Optional[typing.Union[str, typing.List[str]]]=None,
        vnet: typing.Optional[str]=None,
        jail: typing.Optional['libioc.Jail.JailGenerator']=None,
        extra_settings: typing.Optional[typing.List[str]]=None,
        destroy: bool=False,
        auto_apply: typing.Optional[bool]=True,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        insecure: bool=False
    ) -> None:

        self.jail = jail
        self.logger = libioc.helpers_object.init_logger(self, logger)

        # disable shlex quoting on purpose (use with caution)
        self.insecure = (insecure is True)

        self.name = name
        self.create = create
        self.destroy = destroy
        self.ipv4_addresses = ipv4_addresses
        self.ipv6_addresses = ipv6_addresses
        self.settings = {}
        if (extra_settings is None):
            self.extra_settings = ["up"]
        else:
            self.extra_settings = extra_settings

        if mac:
            if isinstance(mac, str):
                mac = libioc.MacAddress.MacAddress(mac, logger=self.logger)
            self.settings["link"] = mac

        if mtu:
            self.settings["mtu"] = None if (mtu is None) else int(mtu)

        if description:
            self.settings["description"] = str(shlex.quote(description))

        if vnet is not None:
            self.settings["vnet"] = str(self._escape(vnet))

        if addm is not None:
            _addm_list = self._escape_list(addm)
            if _addm_list is not None:
                self.settings["addm"] = _addm_list

        if group is not None:
            self.settings["group"] = str(self._escape(group))

        # rename interface when applying settings next time
        if isinstance(rename, str):
            self.rename = True
            self.settings["name"] = rename
        else:
            self.rename = False

        if auto_apply:
            self.apply()

    def apply(self) -> None:
        """Apply the interface settings and configure IP address."""
        self.apply_settings()
        self.apply_addresses()

    def apply_settings(self) -> None:
        """Apply the interface settings only."""
        command: typing.List[str] = [
            self.ifconfig_command, self.current_nic_name
        ]

        if self.create is True:
            command.append("create")

        values: typing.List[str]
        for key in self.settings:
            value = self.settings[key]
            if isinstance(value, list) is True:
                _value: typing.Any = value
                values = [str(x) for x in _value]
            else:
                values = [str(value)]
            for _value in values:
                command.append(key)
                command.append(_value)

        if self.extra_settings:
            command += self.extra_settings

        has_name = "name" in self.settings
        if self.destroy and has_name and not self.rename:
            self.destroy_interface()

        self._exec(command)

        # update name when the interface was renamed
        if self.rename:
            self.name = str(self.settings["name"])
            del self.settings["name"]
            self.rename = False

    def destroy_interface(self) -> None:
        """Destroy the interface."""
        name = self.settings["name"]  # typing.Union[str, typing.List[str]]
        names: typing.List[str]
        if isinstance(name, str):
            names = [str(name)]
        elif isinstance(name, list):
            names = [str(x) for x in name]
        else:
            raise ValueError("Invalid NetworkInterface name")
        self._destroy_interfaces(names)

    def _destroy_interfaces(self, nic_names: typing.List[str]) -> None:
        for nic_name_to_destroy in nic_names:
            libioc.helper.exec([
                self.ifconfig_command,
                self._escape(nic_name_to_destroy),
                "destroy"
            ])

    def apply_addresses(self) -> None:
        """Apply the configured IP addresses."""
        if self.ipv4_addresses is not None:
            self.__apply_addresses(self.ipv4_addresses)
        if self.ipv6_addresses is not None:
            self.__apply_addresses(self.ipv6_addresses)

    @property
    def current_nic_name(self) -> str:
        """Return the current NIC reference for usage in shell scripts."""
        return str(self._escape(self.name))

    def __apply_addresses(
        self,
        addresses: typing.Union[
            typing.List[ipaddress.IPv4Interface],
            typing.List[ipaddress.IPv6Interface]
        ]
    ) -> None:

        for i, address in enumerate(list(addresses)):  # noqa: T484
            name = self.current_nic_name

            if str(address).lower() == "dhcp":
                command = [self.dhclient_command, name]
            elif str(address).lower() == "accept_rtadv":
                command = [self.rtsold_command, name]
            else:
                is_ipv6 = isinstance(address, ipaddress.IPv6Interface) is True
                family = "inet6" if is_ipv6 else "inet"
                command = [self.ifconfig_command, name, family]

                if i > 0:
                    command.append("alias")

                command.append(str(address))

            self._exec(command)

    def _exec(
        self,
        command: typing.List[str]
    ) -> str:

        if self.jail is not None:
            stdout, _, _ = self.jail.exec(command)
        else:
            stdout, _, _ = libioc.helpers.exec(command, logger=self.logger)

        self._handle_exec_stdout(stdout)

        return str(stdout)

    def _handle_exec_stdout(self, stdout: str) -> None:
        if (self.create or self.rename) is True:
            self.name = stdout.strip()

    def _escape(self, value: typing.Optional[str]) -> typing.Optional[str]:
        if value is None:
            return None
        elif self.insecure is True:
            return value
        else:
            return str(shlex.quote(value))

    def _escape_list(
        self,
        value: typing.Optional[typing.Union[str, typing.List[str]]]
    ) -> typing.Optional[typing.List[str]]:
        if value is None:
            return None
        value_list = [value] if (isinstance(value, str) is True) else value
        return [str(self._escape(str(x))) for x in value_list]


class QueuingNetworkInterface(
    NetworkInterface,
    libioc.CommandQueue.CommandQueue
):
    """Delay command execution for bulk execution."""

    shell_variable_nic_name: typing.Optional[str]

    def __init__(  # noqa: T484
        self,
        name: typing.Optional[str]="vnet0",
        shell_variable_nic_name: typing.Optional[str]=None,
        **network_interface_options
    ) -> None:

        self.shell_variable_nic_name = shell_variable_nic_name

        self.clear_command_queue()
        NetworkInterface.__init__(self, name=name, **network_interface_options)

        if (self.create or self.rename) is False:
            self._set_shell_variable_nic_name()

    def _set_shell_variable_nic_name(
        self,
        name: typing.Optional[str]=None
    ) -> None:
        """Append an environment variable for the current NIC to the queue."""
        name = self.name if name is None else name
        if (name is None) or (self.shell_variable_nic_name is None):
            return
        _name = str(self._escape(name))
        setter_command = f"export {self.shell_variable_nic_name}={_name}"
        self.append_command_queue(setter_command)

    @property
    def current_nic_name(self) -> str:
        """Return the current NIC reference for usage in shell scripts."""
        _has_no_variable_name = (self.shell_variable_nic_name is None)
        if (_has_no_variable_name or self.create) and (self.name is not None):
            return str(self._escape(self.name))
        return f"${self.shell_variable_nic_name}"

    def _exec(self, command: typing.List[str]) -> str:

        _command = " ".join(command)
        _has_variable_name = (self.shell_variable_nic_name is not None)

        if self.rename is True:
            new_name = self.settings["name"]
            if isinstance(new_name, str) is True:
                self.name = str(self._escape(str(new_name)))
            else:
                raise ValueError("Cannot rename multiple interfaces")

        if (_has_variable_name and (self.create or self.rename)) is True:
            self.append_command_queue(
                # export the ifconfig output
                f"export {self.shell_variable_nic_name}=\"$({_command})\""
            )
        else:
            self.append_command_queue(f"{_command} > /dev/null")

        return ""

    def _destroy_interfaces(self, nic_names: typing.List[str]) -> None:
        for nic_name_to_destroy in nic_names:
            self.append_command_queue(" ".join([
                self.ifconfig_command,
                str(self._escape(nic_name_to_destroy)),
                "destroy"
                " 2>/dev/null || :"
            ]))
