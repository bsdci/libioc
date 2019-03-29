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
"""A dataset default configuration."""
import typing

import libioc.helpers_object
import libioc.Config.Data
import libioc.Config.Jail.Globals
import libioc.Config.Jail.BaseConfig

_DEFAULTS = libioc.Config.Jail.Globals.DEFAULTS


class JailConfigDefaults(libioc.Config.Jail.BaseConfig.BaseConfig):
    """BaseConfig object filled with global defaults."""

    user_data: libioc.Config.Data.Data

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        self.user_data = libioc.Config.Data.Data()
        super().__init__(logger=logger)

    @property
    def data(self) -> libioc.Config.Data.Data:
        """Return the Config.Data object."""
        return self.user_data

    @data.setter
    def data(self, value: libioc.Config.Data.Data) -> None:
        """Override the Config.Data object."""
        if isinstance(value, libioc.Config.Data.Data) is False:
            raise ValueError("expecting Config.Data structure")
        self.user_data = value

    def clone(
        self,
        data: typing.Dict[str, typing.Any],
        skip_on_error: bool=False
    ) -> None:
        """Clone data from another dict."""
        for key in data:
            self.user_data[key] = data[key]

    def _getitem_special_property(
        self,
        key: str,
        data: libioc.Config.Data.Data
    ) -> libioc.Config.Jail.Properties.Property:
        try:
            return super()._getitem_special_property(key, data)
        except KeyError:
            return super()._getitem_special_property(key, _DEFAULTS)

    def __getitem__(self, key: str) -> typing.Any:
        """Return a user provided value or the hardcoded default."""
        try:
            return super().__getitem__(key)
        except libioc.errors.IocException:
            raise
        except KeyError:
            pass

        try:
            return self.getitem_default(key)
        except libioc.errors.IocException:
            raise
        except KeyError:
            pass

        raise libioc.errors.UnknownConfigProperty(
            key=key,
            logger=self.logger
        )

    def __contains__(self, key: typing.Any) -> bool:
        """Return true if the storage or hardcoded defaults contain the key."""
        return ((key in self.user_data) or (key in _DEFAULTS)) is True

    def getitem_default(self, key: str) -> typing.Any:
        """Return the interpreted hardcoded default value."""
        try:
            return _DEFAULTS.__getitem__(key)
        except KeyError:
            if self.special_properties.is_special_property(key):
                return None
            raise

    def __delitem__(self, key: str) -> None:
        """Remove a user provided default setting."""
        self.user_data.__delitem__(key)

    def __iter__(self) -> typing.Iterator[str]:
        """Iterate over all default properties."""
        return iter(self.user_properties.union(_DEFAULTS.keys()))

    def __len__(self) -> int:
        """Return the number of default config properties."""
        return len(self.keys())

    def keys(self) -> typing.KeysView[str]:
        """List all default property keys."""
        return typing.cast(
            typing.KeysView[str],
            list(self.user_properties.union(_DEFAULTS.keys()))
        )

    @property
    def user_properties(self) -> typing.Set[str]:
        """Return a set of user defined properties."""
        return set(self.user_data.keys())

    @property
    def exclusive_user_data(self) -> dict:
        """Return a dictionary of user provided default settings."""
        data = {}
        for key in self.user_properties:
            data[key] = self[key]
        return data
