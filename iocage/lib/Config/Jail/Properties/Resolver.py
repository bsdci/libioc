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
"""Jail config resolver property."""
import typing
import collections
import shutil

import iocage.lib.helpers
import iocage.lib.Config.Jail

# mypy
import iocage.lib.Logger


class ResolverProp(collections.MutableSequence):
    """Handle the special jail property (DNS) Resolver."""

    config: 'iocage.lib.Config.Jail.JailConfig.JailConfig'
    property_name: str = "resolver"
    none_matches: typing.List[str] = ["/dev/null", "-", ""]
    _entries: typing.List[str] = []

    def __init__(
        self,
        config: 'iocage.lib.Config.Jail.JailConfig.JailConfig',
        logger: typing.Optional[iocage.lib.Logger.Logger]=None,
        **kwargs
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.config = config
        self.config.attach_special_property(
            name="resolver",
            special_property=self
        )

    @property
    def conf_file_path(self) -> str:
        """Unconfigurable path of the config file."""
        return "/etc/resolv.conf"

    @property
    def method(self) -> str:
        """Return the selected configuration method."""
        return self._get_method(self.value)

    def _get_method(self, value: typing.Any) -> str:
        if value is None:
            return "skip"
        elif value == "/etc/resolv.conf":
            return "copy"
        else:
            return "manual"

    @property
    def value(self) -> typing.Optional[str]:
        """Return the raw configuration string or None."""
        value = self.config.data["resolver"]
        try:
            iocage.lib.helpers.parse_none(value, self.none_matches)
            return None
        except TypeError:
            return str(value)

    def apply(self, jail: 'iocage.lib.Jail.JailGenerator') -> None:
        """Apply the settings to a jail."""
        self.logger.verbose(
            f"Configuring nameserver for Jail '{jail.humanreadable_name}'"
        )

        remote_path = f"{jail.root_path}/{self.conf_file_path}"

        if self.method == "skip":
            self.logger.verbose("resolv.conf untouched")

        elif self.method == "copy":
            shutil.copy(self.conf_file_path, remote_path)
            self.logger.verbose("resolv.conf copied from host")

        elif self.method == "manual":
            lines = map(lambda address: f"nameserver {address}", self._entries)
            with open(remote_path, "w") as f:
                f.write("\n".join(lines))
                f.close()
            self.logger.verbose("resolv.conf written manually")

    def set(
        self,
        value: typing.Optional[typing.Union[str, typing.List[str]]]=None,
        notify: bool=True
    ) -> None:
        """Clear and set all nameservers."""
        self._entries.clear()
        method = self._get_method(value)
        if method == "manual":
            if isinstance(value, str):
                self._entries += str(value).split(";")  # noqa: T484
            elif isinstance(value, list):
                self._entries += list(value)  # noqa: T484
            else:
                raise TypeError("value can be list or string")
        elif method == "skip":
            # directly set config property
            self.config.data["resolver"] = None
        else:
            if isinstance(value, str):
                self.append(str(value), notify=False)
            else:
                raise ValueError(
                    "list of strings or ; separated string expected"
                )

        self.__notify(notify)

    def append(self, value: str, notify: bool=True) -> None:
        """Add a nameserver."""
        self._entries.append(value)
        self.__notify(notify)

    def insert(
        self,
        index: int,
        value: str
    ) -> None:
        """Insert a nameserver at a given position."""
        self._entries.insert(index, value)
        self.__notify()

    def __delitem__(self, key) -> None:
        """Delete the nameserver at the given position."""
        del self._entries[key]

    def __getitem__(self, key) -> typing.Any:
        """Get the nameserver from the given position."""
        return self._entries[key]

    def __len__(self) -> int:
        """Return the number of nameservers."""
        return self._entries.__len__()

    def __setitem__(  # noqa: T484
        self,
        key: str,
        value: str
    ) -> None:
        """Set the nameserver at a given position."""
        list.__setitem__(self, key, value)   # noqa: T484
        self.__notify()

    def __str__(self):
        """Return semicolon separated list of nameservers."""
        return iocage.lib.helpers.to_string(self._entries, delimiter=";")

    def __notify(self, notify: bool=True):
        if not notify:
            return
        self.config.update_special_property("resolver")
