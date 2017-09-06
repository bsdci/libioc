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
import shutil

import libiocage.lib.helpers
import libiocage.lib.JailConfig


class JailConfigResolver(list):
    def __init__(
        self,
        jail_config: 'libiocage.lib.JailConfig.JailConfig',
        host: 'libiocage.lib.Host.HostGenerator'=None,
        logger: 'libiocage.lib.Logger.Logger'=None
    ) -> None:

        list.__init__(self, [])
        self.logger = libiocage.lib.helpers.init_logger(self, logger)
        self.host = libiocage.lib.helpers.init_host(self, host)
        self.jail_config = jail_config
        self.jail_config.attach_special_property(
            name="resolver",
            special_property=self
        )

    @property
    def conf_file_path(self):
        return "/etc/resolv.conf"

    @property
    def method(self):
        if self.value == "/etc/resolv.conf":
            return "copy"

        elif self.value == "/dev/null":
            return "skip"

        else:
            return "manual"

    @property
    def value(self):
        try:
            return self.jail_config.data["resolver"]
        except KeyError:
            return self.host.defaults["resolver"]

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

    def update(self, value=None, notify=True):
        value = value if value is not None else self.value
        self.clear()

        if self.method == "manual":
            if isinstance(value, str):
                self += value.split(";")
            elif isinstance(value, list):
                self += value
            else:
                raise TypeError("value can be list or string")
        else:
            self.append(value, notify=False)

        self.__notify(notify)

    def append(self, value, notify=True):
        list.append(self, value)
        self.__notify(notify)

    def __setitem__(self, key, value, notify=True):
        list.__setitem__(self, key, value)
        self.__notify(notify)

    def __str__(self):
        out = ";".join(list(self))
        return out

    def __notify(self, notify=True):

        if not notify:
            return

        try:
            self.jail_config.update_special_property("resolver")
        except:
            raise
