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

import ioc.helpers_object
import ioc.Config.Jail.BaseConfig

BaseConfig = ioc.Config.Jail.BaseConfig.BaseConfig


class JailConfig(ioc.Config.Jail.BaseConfig.BaseConfig):
    """The configuration of a Jail or other LaunchableResource."""

    legacy: bool = False
    jail: typing.Optional['ioc.Jail.JailGenerator']
    data: dict = {}
    ignore_user_defaults: bool

    def __init__(
        self,
        jail: typing.Optional['ioc.Jail.JailGenerator']=None,
        new: bool=False,
        logger: typing.Optional['ioc.Logger.Logger']=None,
        host: typing.Optional['ioc.Host.HostGenerator']=None
    ) -> None:

        self.ignore_user_defaults = False
        ioc.Config.Jail.BaseConfig.BaseConfig.__init__(
            self,
            logger=logger
        )

        self.host = ioc.helpers_object.init_host(self, host)
        self.jail = jail

    def update_special_property(self, name: str) -> None:
        """Triggered when a special property was updated."""
        self.data[name] = str(self.special_properties[name])

        if (name == "ip6_addr") and (self.jail is not None):
            rc_conf = self.jail.rc_conf
            rc_conf["rtsold_enable"] = "accept_rtadv" in str(self["ip6_addr"])

    def attach_special_property(
        self,
        name: str,
        special_property: 'ioc.Config.Jail.Properties.Property'
    ) -> None:
        """Attach a special property to the configuration."""
        self.special_properties[name] = special_property

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

    def _key_is_mac_config(self, key: str, explicit: bool=False) -> bool:
        fragments = key.rsplit("_", maxsplit=1)
        if len(fragments) < 2:
            return False
        elif fragments[1].lower() != "mac":
            return False
        elif explicit is False:
            # do not explicitly check if the interface exists
            return True
        return (fragments[0] in self["interfaces"].keys()) is True

    def _is_user_property(self, key: str) -> bool:
        return key.startswith("user.") is True

    def _is_known_property(self, key: str) -> bool:
        if key in self.host.defaults.config.keys():
            return True  # key is default
        if f"_set_{key}" in dict.__dir__(self):
            return True  # key is setter
        if key in ioc.Config.Jail.Properties.properties:
            return True  # key is special property
        if self._key_is_mac_config(key) is True:
            return True  # nic mac config property
        if self._is_user_property(key) is True:
            return True  # user.* property
        return False

    def __setitem__(
        self,
        key: str,
        value: typing.Any,
        skip_on_error: bool=False
    ) -> None:
        """Set a configuration value."""
        # require the config property to be defined in the defaults
        if self._is_known_property(key) is False:
            err = ioc.errors.UnknownJailConfigProperty(
                jail=self.jail,
                key=key,
                logger=self.logger,
                level=("warn" if skip_on_error else "error")
            )
            if skip_on_error is False:
                raise err

        try:

            if self.special_properties.is_special_property(key):
                special_property = self.special_properties.get_or_create(key)
                special_property.set(value, skip_on_error=skip_on_error)
                self.update_special_property(key)
                return

            parsed_value = ioc.helpers.parse_user_input(value)
            setter_method_name = f"_set_{key}"
            if setter_method_name in object.__dir__(self):
                setter_method = self.__getattribute__(setter_method_name)
                setter_method(parsed_value)
                return

            error = None

        except ValueError as err:
            error = ioc.errors.InvalidJailConfigValue(
                reason=str(err),
                property_name=key,
                logger=self.logger,
                level=("warn" if (skip_on_error is True) else "error")
            )

        if (error is not None) and (skip_on_error is False):
            raise error

        BaseConfig.__setitem__(
            self,
            key=key,
            value=value,
            skip_on_error=skip_on_error
        )

    def _getitem_user(self, key: str) -> typing.Any:

        # special property
        _rlimits = ioc.Config.Jail.Properties.ResourceLimit.properties
        if self.special_properties.is_special_property(key) is True:
            is_existing = key in self.data.keys()
            is_resource_limit = key in _rlimits
            if is_existing is True:
                return self.special_properties.get_or_create(key)
            elif is_resource_limit is True:
                return None

        return BaseConfig._getitem_user(
            self,
            key=key
        )

    def __getitem__(self, key: str) -> typing.Any:
        """Get the value of a configuration argument or its default."""
        try:
            return super().__getitem__(key)
        except KeyError:
            if self.ignore_user_defaults is True:
                raise
            pass

        # fall back to default
        return self.host.defaults.config[key]

    @property
    def all_properties(self) -> list:
        """Return a list of all config properties (default and custom)."""
        jail_config_properties = set(super().all_properties)
        default_config_properties = set(
            self.host.default_config.all_properties
        )
        return sorted(list(jail_config_properties | default_config_properties))
