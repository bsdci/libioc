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
import collections.abc

class HostJailParams(collections.abc.MutableMapping):
    __params: typing.Dict[str, freebsd_sysctl.Sysctl]

    def __iter__(self) -> typing.Iterator[str]:
        """Iterate over the jail param names."""
        yield self.memoized_params.__iter__()
    
    def __len__(self) -> int:
        """Return the number of available jail params."""
        return self.memoized_params.__len__()

    def items(self) -> typing.ItemsView[str, typing.Any]:
        """Iterate over the keys and values."""
        return typing.cast(
            typing.ItemsView[str, typing.Any],
            self.memoized_params.items()
        )

    def keys(self) -> typing.KeysView[str]:
        """Return a list of all jail param names."""
        return collections.abc.KeysView(*list(self.__iter__()))  # noqa: T484

    def __getitem__(self, key: str) -> typing.Any:
        """Set of jail params sysrc is not implemented."""
        return self.memoized_params.__getitem__(key)

    def __setitem__(self, key: str, value: typing.Any) -> None:
        """Set of jail params sysrc is not supportes."""
        raise NotImplementedError("jail param sysctl cannot be modified")

    def __delitem__(self, key: str, value: typing.Any) -> None:
        """Delete of jail param sysrc not supported."""
        raise NotImplementedError("jail param sysctl cannot be deleted")

    @property
    def memoized_params(self) -> typing.Dict[str, freebsd_sysctl.Sysctl]:
        try:
            return self.__params
        except AttributeError:
            pass
        self.__update_sysrc_jail_params()
        return self.__params

    def __update_sysrc_jail_params(self) -> None:
        prefix = "security.jail.param"
        jail_params = filter(
            lambda x: x.name.endswith(".") is False,  # filter NODE
            freebsd_sysctl.Sysctl(prefix).children
        )
        HostJailParams.__params = dict(
            [(x.name[len(prefix) + 1:], x,) for x in jail_params]
        )
