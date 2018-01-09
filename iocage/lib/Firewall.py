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

import sysctl

import iocage.lib.helpers


class Firewall:

    IPFW_RULE_OFFSET: int = 10000
    IPFW_COMMAND: str = "/sbin/ipfw"

    def __init__(
        self,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)

    @property
    def _required_sysctl_properties(self):
        return {
            "net.inet.ip.fw.enable": 1,
            "net.link.ether.ipfw": 1
        }

    @property
    def ipfw_enabled(self):
        requirements = self._required_sysctl_properties
        requirement_keys = list(requirements.keys())
        for item in sysctl.filter("net"):
            if item.name in requirement_keys:
                if item.value != requirements[item.name]:
                    return False
        return True

    def delete_rule(self, rule_number: int) -> None:
        iocage.lib.helpers.exec(
            [
                self.IPFW_COMMAND,
                "-q", "delete",
                str(rule_number + self.IPFW_RULE_OFFSET)
            ],
            ignore_error=True
        )

    def add_rule(
        self,
        rule_number: int,
        rule_arguments: typing.List[str]
    ) -> None:
        iocage.lib.helpers.exec([
            self.IPFW_COMMAND,
            "-q", "add",
            str(rule_number + self.IPFW_RULE_OFFSET)
        ] + rule_arguments)
