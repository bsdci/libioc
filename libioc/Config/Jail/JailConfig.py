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
"""Configuration of a Jail or other LaunchableResource."""
import typing

import libioc.helpers_object
import libioc.Config.Jail.BaseConfig

BaseConfig = libioc.Config.Jail.BaseConfig.BaseConfig


class JailConfig(libioc.Config.Jail.BaseConfig.BaseConfig):
    """
    The configuration of a Jail or other LaunchableResource.

    In extend to a BaseConfig a JailConfig is related to a Jail.
    """

    legacy: bool = False
    jail: typing.Optional['libioc.Jail.JailGenerator']
    data: dict
    ignore_source_config: bool

    def __init__(
        self,
        jail: typing.Optional['libioc.Jail.JailGenerator']=None,
        new: bool=False,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        host: typing.Optional['libioc.Host.HostGenerator']=None
    ) -> None:

        self.ignore_source_config = False
        libioc.Config.Jail.BaseConfig.BaseConfig.__init__(
            self,
            logger=logger
        )

        self.host = libioc.helpers_object.init_host(self, host)
        self.jail = jail

    def update_special_property(self, name: str) -> None:
        """Triggered when a special property was updated."""
        super().update_special_property(name)
        if (name == "ip6_addr") and (self.jail is not None):
            rc_conf = self.jail.rc_conf
            ip6_networks = self.special_properties[name].networks
            rc_conf["rtsold_enable"] = "accept_rtadv" in ip6_networks

    def _get_host_hostname(self) -> str:
        try:
            return str(self.data["host_hostname"])
        except KeyError as e:
            jail = self.jail
            if jail is not None:
                return str(jail.humanreadable_name)
            raise e

    def _get_legacy(self) -> bool:
        return self.legacy

    def _get_mount_fdescfs(self) -> int:
        return self.__get_mount(key="mount_fdescfs")

    def _set_mount_fdescfs(self, value: typing.Union[str, int, bool]) -> None:
        self.__set_mount(key="mount_fdescfs", value=value)

    def _get_mount_devfs(self) -> int:
        return self.__get_mount(key="mount_devfs")

    def _set_mount_devfs(self, value: typing.Union[str, int, bool]) -> None:
        self.__set_mount(key="mount_devfs", value=value)

    def __get_mount(self, key: str) -> int:
        return 1 * ((int(self.data[key]) == 1) is True)

    def __set_mount(
        self,
        key: str,
        value: typing.Union[str, int, bool]
    ) -> None:

        error_reason: typing.Optional[str] = None
        if isinstance(value, bool) is True:
            enabled = (value is True)
        else:
            try:
                str_value = str(int(value))
            except ValueError:
                error_reason = "invalid input type (expected int, str or bool)"

            if (str_value != "0") and (str_value != "1"):
                error_reason = f"Boolean input expected, but got {str_value}"

            enabled = (str_value == "1")

        if error_reason is not None:
            raise libioc.errors.InvalidJailConfigValue(
                jail=self.jail,
                property_name="mount_fdescfs",
                reason=error_reason,
                logger=self.logger
            )

        self.data[key] = ("1" if enabled else "0")

    def __getitem__(self, key: str) -> typing.Any:
        """Get the value of a configuration argument or its default."""
        try:
            return super().__getitem__(key)
        except libioc.errors.UnknownConfigProperty:
            raise
        except KeyError:
            pass

        # fall back to default
        if self.ignore_source_config is True:
            # only hardcoded defaults
            return self.host.defaults.config.getitem_default(key)
        else:
            # mixed with user defaults
            return self.host.defaults.config[key]

    def get_raw(self, key: str) -> typing.Any:
        """Return the raw data value or its raw default."""
        self._require_known_config_property(key)
        if key in self.data:
            return self.data[key]
        return self.host.defaults.config[key]

    @property
    def all_properties(self) -> list:
        """Return a list of all config properties (default and custom)."""
        jail_config_properties = set(super().all_properties)
        default_config_properties = set(
            self.host.default_config.all_properties
        )
        return sorted(list(jail_config_properties | default_config_properties))
