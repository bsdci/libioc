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
import shutil

import iocage.lib.helpers
import iocage.lib.Config.Jail

# mypy
import iocage.lib.Logger


class ResolverProp(list):

    config: 'iocage.lib.Config.Jail.JailConfig.JailConfig'
    property_name: str = "resolver"

    def __init__(
        self,
        config,
        logger: typing.Optional[iocage.lib.Logger.Logger]=None,
        **kwargs
    ) -> None:

        list.__init__(self, [])
        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.config = config
        self.config.attach_special_property(
            name="resolver",
            special_property=self
        )

    @property
    def conf_file_path(self) -> str:
        return "/etc/resolv.conf"

    @property
    def method(self) -> str:
        return self._get_method(self.value)

    def _get_method(self, value: typing.Any) -> str:
        if value == "/etc/resolv.conf":
            return "copy"

        elif value == "/dev/null":
            return "skip"

        else:
            return "manual"

    @property
    def value(self) -> str:
        return str(self.config.data["resolver"])

    def apply(self, jail):
        self.logger.verbose(
            f"Configuring nameserver for Jail '{jail.humanreadable_name}'"
        )

        remote_path = f"{jail.root_path}/{self.conf_file_path}"

        if self.method == "copy":
            shutil.copy(self.conf_file_path, remote_path)
            self.logger.verbose("resolv.conf copied from host")

        elif self.method == "manual":
            with open(remote_path, "w") as f:
                f.write("\n".join(self))
                f.close()
            self.logger.verbose("resolv.conf written manually")

        else:
            self.logger.verbose("resolv.conf not touched")

    def set(
        self,
        value: typing.Optional[typing.Union[str, list]]=None,
        notify: bool=True
    ) -> None:

        self.clear()
        method = self._get_method(value)
        if method == "manual":
            if isinstance(value, str):
                self += str(value).split(";")  # noqa: T484
            elif isinstance(value, list):
                self += list(value)  # noqa: T484
            elif value is None:
                return
            else:
                raise TypeError("value can be list or string")
        else:
            if isinstance(value, str):
                self.append(str(value), notify=False)
            else:
                raise ValueError(
                    "list of strings or ; separated string expected"
                )

        self.__notify(notify)

    def append(self, value: str, notify: bool=True):
        list.append(self, value)
        self.__notify(notify)

    def __setitem__(  # noqa: T484
        self,
        key: str,
        value: str
    ) -> None:

        list.__setitem__(self, key, value)   # noqa: T484
        self.__notify()

    def __str__(self):
        out = ";".join(list(self))
        return out

    def __notify(self, notify: bool=True):
        if not notify:
            return
        self.config.update_special_property("resolver")
