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
"""iocage firewall module."""
import typing
import shlex

import sysctl

import libioc.helpers
import libioc.helpers_object
import libioc.CommandQueue


class Firewall:
    """iocage host firewall abstraction."""

    IPFW_RULE_OFFSET: int
    IPFW_COMMAND: str = "/sbin/ipfw"

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        self.IPFW_RULE_OFFSET = 10000
        self.logger = libioc.helpers_object.init_logger(self, logger)

    @property
    def _required_sysctl_properties(self) -> typing.Dict[str, int]:
        return {
            "net.inet.ip.fw.enable": 1,
            "net.link.ether.ipfw": 1,
            "net.link.bridge.ipfw": 1
        }

    def ensure_firewall_enabled(self) -> None:
        """Raise an FirewallDisabled exception if the firewall is disabled."""
        requirements = self._required_sysctl_properties
        requirement_keys = list(requirements.keys())
        for item in sysctl.filter("net"):
            if item.name in requirement_keys:
                if item.value != requirements[item.name]:
                    state = ("en" if (item.value == 0) else "dis") + "abled"
                    raise libioc.errors.FirewallDisabled(
                        hint=f"sysctl {item.name} is not {state}",
                        logger=self.logger
                    )

    def delete_rule(
        self,
        rule_number: typing.Union[int, str],
        insecure: bool=False
    ) -> None:
        """Delete a firewall rule by its number."""
        command = [
            self.IPFW_COMMAND,
            "-q", "delete",
            self._offset_rule_number(rule_number, insecure=insecure)
        ]
        self._exec(command, ignore_error=True)

    def add_rule(
        self,
        rule_number: typing.Union[int, str],
        rule_arguments: typing.List[str],
        insecure: bool=False
    ) -> None:
        """Add a rule to the firewall configuration."""
        command = [
            self.IPFW_COMMAND,
            "-q", "add",
            self._offset_rule_number(rule_number, insecure=insecure)
        ] + rule_arguments

        self._exec(command)

    def _offset_rule_number(
        self,
        rule_number: typing.Union[int, str],
        insecure: bool=False
    ) -> str:
        if insecure is True:
            raise NotImplementedError(
                "Insecure rule numbers supported by Firewall"
            )
        if isinstance(rule_number, str) is True:
            raise ValueError("Firewall rule_number must be a number")
        _rule_number = int(rule_number)
        return str(_rule_number + self.IPFW_RULE_OFFSET)

    def _exec(
        self,
        command: typing.List[str],
        ignore_error: bool=False
    ) -> None:
        try:
            libioc.helpers.exec(command, ignore_error=ignore_error)
        except libioc.errors.CommandFailure:
            raise libioc.errors.FirewallCommandFailure(
                logger=self.logger
            )


class QueuingFirewall(Firewall, libioc.CommandQueue.CommandQueue):
    """Command queuing Firewall for bulk execution."""

    def __init__(  # noqa: T484
        self,
        insecure: bool=False,
        **firewall_arguments
    ) -> None:
        self.clear_command_queue()

        # disable shlex.quote on rule numbers (e.g. $IOCAGE_JID)
        self.insecure = insecure

        Firewall.__init__(self, **firewall_arguments)

    def _offset_rule_number(
        self,
        rule_number: typing.Union[int, str],
        insecure: bool=False
    ) -> str:
        if isinstance(rule_number, int):
            return str(rule_number + self.IPFW_RULE_OFFSET)
        _rule_number = rule_number if insecure else self._escape(rule_number)
        return f"$(expr {_rule_number} + {self.IPFW_RULE_OFFSET})"

    def _exec(
        self,
        command: typing.List[str],
        ignore_error: bool=False
    ) -> None:
        command_line = " ".join(command)
        if ignore_error is True:
            command_line += " || true"
        self.append_command_queue(command_line)

    def _escape(self, value: str) -> str:
        return str(shlex.quote(value))
