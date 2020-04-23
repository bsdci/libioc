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
"""Sysctl jail params signeton."""
import typing
import freebsd_sysctl
import freebsd_sysctl.types
import collections.abc
import shlex

import libioc.helpers

JailParamValueType = typing.Optional[typing.Union[bool, int, str]]


class JailParam(freebsd_sysctl.Sysctl):
    """Single jail parameter represented by sysctl."""

    user_value: JailParamValueType

    @property
    def value(self) -> JailParamValueType:
        """Return the user defined value of this jail parameter."""
        return self.user_value

    @value.setter
    def value(self, value: JailParamValueType) -> None:
        """Set the user defined value of this jail parameter."""
        if self.ctl_type in (
            freebsd_sysctl.types.STRING,
            freebsd_sysctl.types.OPAQUE,
            freebsd_sysctl.types.NODE
        ):
            if (isinstance(value, int) or isinstance(value, str)) is False:
                try:
                    value = str(value)
                except Exception:
                    self.__raise_value_type_error()
        else:
            if (isinstance(value, int) or isinstance(value, bool)) is False:
                try:
                    value = int(value)  # noqa: T484
                except Exception:
                    self.__raise_value_type_error()
        self.user_value = value

    @property
    def sysctl_value(self) -> JailParamValueType:
        """Return the original freebsd_sysctl.Sysctl value."""
        return typing.cast(
            JailParamValueType,
            super().value
        )

    def __raise_value_type_error(self) -> None:
        type_name = self.ctl_type.__name__
        raise TypeError(f"{self.name} sysctl requires {type_name}")

    @property
    def jail_arg_name(self) -> str:
        """Return the name of the param formatted for the jail command."""
        name = str(self.name)
        prefix = "security.jail.param."
        if name.startswith(prefix) is True:
            return name[len(prefix):]
        return name

    @property
    def iocage_name(self) -> str:
        """Return the name of the param formatted for iocage config."""
        return self.jail_arg_name.rstrip(".").replace(".", "_")

    def __str__(self) -> str:
        """Return the jail command argument notation of the param."""
        if (self.value is None):
            return self.jail_arg_name

        if (self.ctl_type == freebsd_sysctl.types.STRING):
            escaped_value = shlex.quote(str(self.value))
            return f"{self.jail_arg_name}={escaped_value}"

        mapped_value = str(libioc.helpers.to_string(
            self.value,
            true="1",
            false="0"
        ))
        return f"{self.jail_arg_name}={mapped_value}"


class JailParams(collections.abc.MutableMapping):
    """Collection of jail parameters."""

    __base_class = JailParam
    __sysctl_params: typing.Dict[str, JailParam]

    def __iter__(self) -> typing.Iterator[str]:
        """Iterate over the jail param names."""
        yield from self.memoized_params.__iter__()

    def __len__(self) -> int:
        """Return the number of available jail params."""
        return self.memoized_params.__len__()

    def items(self) -> typing.ItemsView[str, JailParam]:
        """Iterate over the keys and values."""
        return self.memoized_params.items()

    def keys(self) -> typing.KeysView[str]:
        """Return a list of all jail param names."""
        return collections.abc.KeysView(list(self.__iter__()))  # noqa: T484

    def __getitem__(self, key: str) -> typing.Any:
        """Set of jail params sysctl is not implemented."""
        return self.memoized_params.__getitem__(key)

    def __setitem__(self, key: str, value: typing.Any) -> None:
        """Set of jail params sysctl is not supportes."""
        self.memoized_params.__setitem__(key, value)

    def __delitem__(self, key: str) -> None:
        """Delete of jail param sysctl not supported."""
        self.memoized_params.__delitem__(key)

    @property
    def memoized_params(self) -> typing.Dict[str, JailParam]:
        """Return the memorized params initialized on first access."""
        try:
            return self.__sysctl_params
        except AttributeError:
            pass
        self.__update_sysctl_jail_params()
        return self.__sysctl_params

    def __update_sysctl_jail_params(self) -> None:
        prefix = "security.jail.param"
        jail_params = filter(
            # security.jail.allow_raw_sockets deprecated
            lambda x: x.name != "security.jail.allow_raw_sockets",
            self.__base_class(prefix).children
        )
        # permanently store the queried sysctl in the singleton class
        JailParams.__sysctl_params = dict([
            (x.name.rstrip("."), x,)
            for x in jail_params
        ])


class HostJailParams(JailParams):
    """Read-only host jail parameters obtained from sysctl."""

    __base_class = freebsd_sysctl.Sysctl

    def __setitem__(self, key: str, value: typing.Any) -> None:
        """Set of jail params sysctl is not supportes."""
        raise NotImplementedError("jail param sysctl cannot be modified")

    def __delitem__(self, key: str) -> None:
        """Delete of jail param sysctl not supported."""
        raise NotImplementedError("jail param sysctl cannot be deleted")
