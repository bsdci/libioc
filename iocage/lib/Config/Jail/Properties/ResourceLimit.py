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
"""Jail config resource limit."""
import typing
import iocage.lib.errors

properties: typing.List[str] = [
    "cputime",
    "datasize",
    "stacksize",
    "coredumpsize",
    "memoryuse",
    "memorylocked",
    "maxproc",
    "openfiles",
    "vmemoryuse",
    "pseudoterminals",
    "swapuse",
    "nthr",
    "msgqqueued",
    "msgqsize",
    "nmsgq",
    "nsem",
    "nsemop",
    "nshm",
    "shmsize",
    "wallclock",
    "pcpu",
    "readbps",
    "writebps",
    "readiops",
    "writeiops"
]


class ResourceLimitValue:

    amount: str
    action: str
    per: str

    def __init__(self, data: str) -> None:
        amount, action, per = self._parse_resource_limit(data)
        self.amount = amount
        self.action = action
        self.per = per

    def _parse_resource_limit(
        self,
        value: str
    ) -> typing.Tuple[str, str, str]:

        try:
            if ("=" not in value) and (":" not in value):
                # simplified syntax vmemoryuse=128M
                amount = value
                action = "deny"
                per = "jail"
            elif "=" in value:
                # rctl syntax
                action, _rest = value.split("=", maxsplit=1)
                amount, per = _rest.split("/", maxsplit=1)
            elif ":" in value:
                # iocage legacy syntax
                amount, action = value.split(":", maxsplit=1)
                per = "jail"
            else:
                raise ValueError("invalid syntax")
        except ValueError:
            raise iocage.lib.errors.ResourceLimitSyntax(logger=self.logger)

        return amount, action, per

    def __str__(self) -> str:
        """
        Return the resource limit value in string format.

        When self.per is "jail" the legacy compatible format is used.
        """
        if self.per == "jail":
            return f"{self.amount}:{self.action}"
        else:
            return self.limit_string

    @property
    def limit_string(self) -> str:
        return f"{self.action}={self.amount}/{self.per}"


_ResourceLimitInputType = typing.Optional[
    typing.Union[str, ResourceLimitValue]
]


class ResourceLimitProp(ResourceLimitValue):
    """Special jail config property for resource limits."""

    amount: typing.Optional[str]
    action: typing.Optional[str]
    per: typing.Optional[str]

    def __init__(
        self,
        config: typing.Optional[
            'iocage.lib.Config.Jail.BaseConfig.BaseConfig'
        ]=None,
        property_name: str="ip4_address",
        logger: typing.Optional['iocage.lib.Logger.Logger']=None,
        skip_on_error: bool=False
    ) -> None:

        self.logger = logger
        self.config = config
        self.property_name = property_name

        if property_name not in properties:
            raise iocage.lib.errors.ResourceLimitUnknown(logger=self.logger)

        self.__update_from_config()

    def __update_from_config(self) -> None:
        if self.property_name not in self.config.data.keys():
            self.amount = None
            self.action = None
            self.per = None
        else:
            ResourceLimitValue.__init__(self.config.data[self.property_name])

    def set(self, data: _ResourceLimitInputType) -> None:
        if data is None:
            self.config.data.__delitem__(self.property_name),
            amount = None
            action = None
            per = None
        if isinstance(data, str):
            amount, action, per = self._parse_resource_limit(data)
        elif isinstance(data, ResourceLimitValue):
            amount = data.amount
            action = data.action
            per = data.per
        else:
            raise TypeError("invalid ResourceLimit input type")

        self.amount = amount
        self.action = action
        self.per = per
        self.__notify()

    def __notify(self) -> None:
        self.config.update_special_property(self.property_name)
