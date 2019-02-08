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
"""ioc provisioning prototype."""
import typing
import urllib.parse

import libioc.errors
import libioc.Types
import libioc.helpers
import libioc.Provisioning.ix
import libioc.Provisioning.puppet

_SourceType = typing.Union[
    urllib.parse.ParseResult,
    libioc.Types.AbsolutePath,
]
_SourceInputType = typing.Union[_SourceType, str]

class Source(str):

    _value: _SourceType

    def __init__(
        self,
        value: _SourceInputType
    ) -> None:
        self.value = value

    @property
    def value(self) -> _SourceType:
        return self._value

    @value.setter
    def value(self, value: _SourceInputType) -> None:

        if isinstance(value, libioc.Types.AbsolutePath) is True:
            self._value = typing.cast(libioc.Types.AbsolutePath, value)
            return
        elif isinstance(value, urllib.parse.ParseResult) is True:
            url = typing.cast(urllib.parse.ParseResult, value)
            self.__require_valid_url(url)
            self._value = url
            return
        elif isinstance(value, str) is False:
            raise TypeError(
                f"Input must be URL, AbsolutePath or str, "
                "but was {type(value)}"
            )

        try:
            self._value = libioc.Types.AbsolutePath(value)
            return
        except ValueError:
            pass

        try:
            url = urllib.parse.urlparse(value)
            self.__require_valid_url(url)
            self._value = url
            return
        except ValueError:
            pass

        raise ValueError("Provisioning Source must be AbsolutePath or URL")

    @property
    def local(self) -> bool:
        """Return True when the source is local."""
        return (isinstance(self.value, libioc.Types.AbsolutePath) is True)

    @property
    def remote(self) -> bool:
        """Return True when the source is a remote URL."""
        return (self.local is False)

    def __require_valid_url(self, url: urllib.parse.ParseResult) -> None:
        if url.scheme not in ("https", "http", "ssh", "git"):
            raise ValueError(f"Invalid Source Scheme: {url.scheme}")

    def __str__(self) -> str:
        """Return the Provisioning Source as string."""
        value = self.value
        if isinstance(value, urllib.parse.ParseResult) is True:
            return value.geturl()
        else:
            return str(value)

    def __repr__(self) -> str:
        return f"<Source '{self.__str__()}'>"


class Prototype:

    jail: 'libioc.Jail.JailGenerator'
    __METHOD: str

    def __init__(
            self,
            jail: 'libioc.Jail.JailGenerator'
    ) -> None:
        self.jail = jail

    @property
    def method(self) -> str:
        return self.__METHOD

    @property
    def source(self) -> typing.Optional[Source]:
        config_value = self.jail.config["provision.source"]
        return None if (config_value is None) else Source(config_value)

    @property
    def rev(self) -> typing.Optional[str]:
        config_value = self.jail.config["provision.rev"]
        return None if (config_value is None) else str(Source(config_value))

    def check_requirements(self) -> None:
        """Check requirements before executing the provisioner."""
        if self.source is None:
            raise libioc.errors.UndefinedProvisionerSource(
                logger=self.jail.logger
            )
        if self.method is None:
            raise libioc.errors.UndefinedProvisionerMethod(
                logger=self.jail.logger
            )


class Provisioner(Prototype):

    @property
    def method(self) -> str:
        method = self.jail.config["provision.method"]
        if method in self.__available_provisioning_modules:
            return method
        raise libioc.errors.InvalidProvisionerMethod(
            method,
            logger=self.jail.logger
        )

    @property
    def __available_provisioning_modules(
            self
    ) -> typing.Dict[str, Prototype]:
        return dict(
            ix=libioc.Provisioning.ix,
            puppet=libioc.Provisioning.puppet
        )

    @property
    def __provisioning_module(self) -> 'libioc.Provisioning.Provisioner':
        """Return the class of the currently configured provisioner."""
        return self.__available_provisioning_modules[self.method]

    def provision(
            self
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Run the provision method on the enabled provisioner."""
        Prototype.check_requirements(self)
        yield from self.__provisioning_module.provision(self)
