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

import iocage.lib.helpers
import iocage.lib.CommandQueue


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
    settings: typing.Dict[str, typing.Union[str, typing.List[str]]]
    extra_settings: typing.List[str]
    rename: bool
    create: bool
    destroy: bool

    def __init__(
        self,
        name: typing.Optional[str]="vnet0",
        create: bool=False,
        ipv4_addresses: typing.Optional[typing.List[str]]=[],
        ipv6_addresses: typing.Optional[typing.List[str]]=[],
        mac: typing.Optional[
            typing.Union[str, 'iocage.lib.MacAddress.MacAddress']
        ]=None,
        mtu: typing.Optional[int]=None,
        description: typing.Optional[str]=None,
        rename: typing.Optional[str]=None,
        group: typing.Optional[str]=None,
        addm: typing.Optional[typing.Union[str, typing.List[str]]]=None,
        vnet: typing.Optional[str]=None,
        jail: typing.Optional['iocage.lib.Jail.JailGenerator']=None,
        extra_settings: typing.Optional[typing.List[str]]=None,
        destroy: bool=False,
        auto_apply: typing.Optional[bool]=True,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None
    ) -> None:

        self.jail = jail
        self.logger = iocage.lib.helpers.init_logger(self, logger)

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

        for key in self.settings:
            value = self.settings[key]
            if not isinstance(value, list):
                values = [value]
            else:
                values = value
            for value in values:
                command.append(key)
                command.append(str(value))

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
        if isinstance(self.settings["name"], str):
            self._destroy_interfaces([self.settings["name"]])
        else:
            self._destroy_interfaces(self.settings["name"])

    def _destroy_interfaces(self, nic_names: typing.List[str]) -> None:
        for nic_name_to_destroy in nic_names:
            iocage.lib.helper.exec([
                self.ifconfig_command,
                nic_name_to_destroy,
                "destroy"
            ])

    def apply_addresses(self) -> None:
        """Apply the configured IP addresses."""
        if self.ipv4_addresses is not None:
            self.__apply_addresses(self.ipv4_addresses, ipv6=False)
        if self.ipv6_addresses is not None:
            self.__apply_addresses(self.ipv6_addresses, ipv6=True)

    @property
    def current_nic_name(self) -> str:
        """Return the current NIC reference for usage in shell scripts."""
        return str(self.name)

    def __apply_addresses(
        self,
        addresses: typing.List[str],
        ipv6: bool=False
    ) -> None:

        family = "inet6" if ipv6 else "inet"
        for i, address in enumerate(addresses):
            name = self.current_nic_name
            if (ipv6 is False) and (address.lower() == "dhcp"):
                command = [self.dhclient_command, name]
            else:
                command = [self.ifconfig_command, name, family, address]

            if i > 0:
                command.append("alias")

            self._exec(command)

            if (ipv6 is True) and (address.lower() == "accept_rtadv"):
                self._exec([
                    self.rtsold_command,
                    self.current_nic_name
                ])

    def _exec(
        self,
        command: typing.List[str]
    ) -> str:

        if self.jail is not None:
            stdout, _, _ = self.jail.exec(command)
        else:
            stdout, _, _ = iocage.lib.helpers.exec(command, logger=self.logger)

        self._handle_exec_stdout(stdout)

        return str(stdout)

    def _handle_exec_stdout(self, stdout: str) -> None:
        if (self.create or self.rename) is True:
            self.name = stdout.strip()


class QueuingNetworkInterface(
    NetworkInterface,
    iocage.lib.CommandQueue.CommandQueue
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

        self.clear()
        NetworkInterface.__init__(self, name=name, **network_interface_options)

        if (self.create or self.rename) is False:
            self.set_shell_variable_nic_name()

    def set_shell_variable_nic_name(
        self,
        name: typing.Optional[str]=None
    ) -> None:
        """Append an environment variable for the current NIC to the queue."""
        _name = self.name if name is None else name
        if (_name is None) or (self.shell_variable_nic_name is None):
            return
        setter_command = f"export {self.shell_variable_nic_name}=\"{_name}\""
        self.command_queue.append(setter_command)

    @property
    def current_nic_name(self) -> str:
        """Return the current NIC reference for usage in shell scripts."""
        _has_no_variable_name = (self.shell_variable_nic_name is None)
        if (_has_no_variable_name or self.create) and (self.name is not None):
            return str(self.name)
        return f"${self.shell_variable_nic_name}"

    def _exec(self, command: typing.List[str]) -> str:

        _command = " ".join(command)
        _has_variable_name = (self.shell_variable_nic_name is not None)

        if self.rename is True:
            new_name = self.settings["name"]
            if isinstance(new_name, str) is True:
                self.name = str(new_name)
            else:
                raise TypeError("Cannot rename multiple interfaces")

        if (_has_variable_name and (self.create or self.rename)) is True:
            self.command_queue.append(
                # export the ifconfig output
                f"export {self.shell_variable_nic_name}=\"$({_command})\""
            )

            if self.jail is None:
                self.command_queue += [
                    # persist env immediately
                    (
                        "echo \"export IOCAGE_JID=$IOCAGE_JID\" > "
                        "\"$(dirname $0)/.env\""
                    ), (
                        "env | grep ^IOCAGE_NIC | sed 's/^/export /' >> "
                        "\"$(dirname $0)/.env\""
                    )
                ]
        else:
            self.command_queue.append(_command)

        return ""

    def _destroy_interfaces(self, nic_names: typing.List[str]) -> None:
        for nic_name_to_destroy in nic_names:
            self.command_queue.append(" ".join([
                self.ifconfig_command,
                nic_name_to_destroy,
                "destroy"
                " 2>/dev/null || :"
            ]))
