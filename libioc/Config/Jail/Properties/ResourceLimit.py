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
"""Jail config resource limit."""
import typing
import libioc.errors

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

ResourceLimitValueTuple = typing.Tuple[
    typing.Optional[str],
    typing.Optional[str],
    typing.Optional[str]
]


class ResourceLimitValue:
    """Model of a resource limits value."""

    amount: typing.Optional[str]
    action: typing.Optional[str]
    per: typing.Optional[str]

    def __init__(
        self,
        *args: typing.List[str],
        **kwargs: typing.Union[int, str]
    ) -> None:
        _values: ResourceLimitValueTuple = (None, None, None,)
        if len(args) > 0:
            _values = self._parse_resource_limit(str(args[0]))

        amount = kwargs.get("amount", _values[0])
        self.amount = amount if isinstance(amount, str) else None

        action = kwargs.get("action", _values[1])
        self.action = action if isinstance(action, str) else None

        per = kwargs.get("per", _values[2])
        self.per = per if isinstance(per, str) else None

    @property
    def is_unset(self) -> bool:
        """Return whether any parameter is None."""
        return (None in [self.amount, self.action, self.per]) is True

    def _parse_resource_limit(self, value: str) -> ResourceLimitValueTuple:
        _default_per = "jail"

        if (value is False) or (value is None) or (value == "None=None/None"):
            amount = None
            action = None
            per = None
        elif ("=" not in value) and (":" not in value):
            # simplified syntax vmemoryuse=128M
            amount = value
            action = "deny"
            per = _default_per
        elif "=" in value:
            # rctl syntax
            action, _rest = value.split("=", maxsplit=1)
            try:
                amount, per = _rest.split("/", maxsplit=1)
            except ValueError:
                amount = _rest
                per = _default_per
        elif ":" in value:
            # iocage legacy syntax
            amount, action = value.split(":", maxsplit=1)
            per = _default_per
        else:
            raise ValueError("invalid syntax")

        if (amount == "") or (action == "") or (per == ""):
            raise ValueError("value may not be empty")

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

    def __repr__(self) -> str:
        """Return a string representation of the object."""
        return f"<{self.__class__.__name__} {self.limit_string}>"

    @property
    def limit_string(self) -> str:
        """Return the limit string in rctl syntax."""
        return f"{self.action}={self.amount}/{self.per}"


_ResourceLimitInputType = typing.Optional[
    typing.Union[int, str, ResourceLimitValue]
]


class ResourceLimitProp(ResourceLimitValue):
    """Special jail config property for resource limits."""

    property_name: str
    config: 'libioc.Config.Jail.JailConfig.JailConfig'

    def __init__(
        self,
        property_name: str,
        config: typing.Optional[
            'libioc.Config.Jail.BaseConfig.BaseConfig'
        ]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
    ) -> None:

        self.logger = logger
        self.config = config
        self.property_name = property_name

        if property_name not in properties:
            raise libioc.errors.ResourceLimitUnknown(logger=self.logger)

        ResourceLimitValue.__init__(self)
        self.__update_from_config()

    def _parse_resource_limit(self, value: str) -> typing.Tuple[
        typing.Optional[str],
        typing.Optional[str],
        typing.Optional[str]
    ]:
        return ResourceLimitValue._parse_resource_limit(self, value=value)

    def __update_from_config(self) -> None:
        name = self.property_name
        if (self.config is None) or (name not in self.config):
            self.set(None)
        else:
            self.set(
                self.config.get_raw(self.property_name)
            )

    def set(
        self,
        data: _ResourceLimitInputType,
        skip_on_error: bool=False
    ) -> None:
        """
        Set the resource limit value.

        Setting it to None will remove it from the configuration.
        """
        error_log_level = "warn" if (skip_on_error is True) else "error"
        if data is None:
            name = self.property_name
            config = self.config
            if (config is not None) and (name in config):
                del config[name]
            amount = None
            action = None
            per = None
        elif isinstance(data, str) or isinstance(data, int):
            amount, action, per = self._parse_resource_limit(str(data))
        elif isinstance(data, ResourceLimitValue):
            amount = data.amount
            action = data.action
            per = data.per
        else:
            e = libioc.errors.InvalidJailConfigValue(
                reason="invalid ResourceLimit input type",
                property_name=self.property_name,
                jail=self.config.jail,
                logger=self.logger,
                level=error_log_level
            )
            if skip_on_error is False:
                raise e

        self.amount = amount
        self.action = action
        self.per = per

    def __notify(self) -> None:
        if self.config is None:
            return
        self.config.update_special_property(self.property_name)

    def __repr__(self) -> str:
        """Return a string representation of the object."""
        class_name = self.__class__.__name__
        return f"<{class_name} {self.property_name}={self.limit_string}>"
