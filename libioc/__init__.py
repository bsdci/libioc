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
"""Python jail management module using ioc{age,ell}."""
import sys
import os.path
import importlib
import typing


def _get_version():
    __dirname = os.path.dirname(__file__)
    __version_file = os.path.join(__dirname, 'VERSION')
    with open(__version_file, "r", encoding="utf-8") as f:
        return f.read().split("\n")[0]


class _HookedModule:

    def __call__(self, *args, **kwargs) -> None:
        return self.main_module(*args, **kwargs)

    @property
    def main_module(self) -> typing.Any:
        name = self.__name__
        return sys.modules[name].__getattribute__(name.split(".").pop())


class _IocModule(sys.modules["libioc"].__class__):

    hooked_modules = [
        "Host",
        "Distribution",
        "Jails",
        "Jail",
        "Releases",
        "Release"
    ]

    def __getattribute__(self, key: str) -> typing.Any:
        if key == "VERSION":
            return _get_version()
        if key.startswith("_") is True:
            return super().__getattribute__(key)

        if key not in sys.modules.keys():
            if key in object.__getattribute__(self, "hooked_modules"):
                self.__load_hooked_module(key)
            else:
                self.__load_module(key)
        return super().__getattribute__(key)

    def __load_module(self, name: str) -> None:
        module = importlib.import_module(f"libioc.{name}")
        sys.modules[name] = module

    def __load_hooked_module(self, name: str) -> None:
        module = importlib.import_module(f"libioc.{name}")
        sys.modules[name] = self.__hook_module(module)

    def __hook_module(self, module: typing.Any) -> None:

        class _Module(module.__class__, _HookedModule):

            pass


        module.__class__ = _Module
        return module


sys.modules["libioc"].__class__ = _IocModule
