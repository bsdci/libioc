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
"""Jail State collection."""
import typing
import subprocess

import iocage.lib.errors
import iocage.lib.helpers

JailStatesDict = typing.Dict[str, 'JailState']

_userland_version = float(iocage.lib.helpers.get_os_version()["userland"])
if _userland_version >= 11:
    import json
else:
    import shlex


def _parse(text: str) -> JailStatesDict:
    output: JailStatesDict = {}
    for line in text.splitlines():
        if line == "":
            continue
        data: typing.Dict[str, str] = {}
        for item in shlex.split(line):
            if "=" not in item:
                data[item] = ""
            else:
                pair = item.split("=", maxsplit=1)
                if len(pair) == 2:
                    data[pair[0]] = pair[1]
                else:
                    data[pair[0]] = ""
        output[data["name"]] = JailState(data["name"], data)
    return output


def _parse_json(data: str) -> JailStatesDict:
    output: typing.Dict[str, 'JailState'] = {}
    jail_states = json.loads(data)["jail-information"]["jail"]
    for jail_state_data in jail_states:
        identifier = jail_state_data["name"]
        output[identifier] = JailState(identifier, jail_state_data)
    return output


class JailState(dict):
    """State of a running Resource/Jail."""

    name: str
    _data: typing.Optional[typing.Dict[str, str]] = None
    updated = False

    logger: typing.Optional['iocage.lib.Logger.Logger']

    def __init__(
        self,
        name: str,
        data: typing.Optional[typing.Dict[str, str]]=None,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None
    ) -> None:

        self.logger = logger
        self.name = name

        if data is not None:
            self._data = data

    def query(self) -> typing.Dict[str, str]:
        """Execute jls to update a jails state."""
        if _userland_version >= 11:
            return self._query_libxo()
        else:
            return self._query_list()

    def _query_libxo(self) -> typing.Dict[str, str]:
        data: typing.Dict[str, str] = {}
        stdout, _, returncode = iocage.lib.helpers.exec(
            [
                "/usr/sbin/jls",
                "-j",
                self.name,
                "-v",
                "--libxo=json"
            ],
            stderr=subprocess.DEVNULL,
            ignore_error=True,
            logger=self.logger
        )

        if returncode > 0:
            self.clear()
            return {}

        data = _parse_json(stdout)[self.name]
        self._data = data
        return data

    def _query_list(self) -> typing.Dict[str, str]:
        data: typing.Dict[str, str] = {}
        stdout, _, returncode = iocage.lib.helpers.exec(
            [
                "/usr/sbin/jls",
                "-j",
                self.name,
                "-v",
                "-n",
                "-q"
            ],
            stderr=subprocess.DEVNULL,
            ignore_error=True,
            logger=self.logger
        )

        if returncode > 0:
            self.clear()
            return {}

        data = _parse(stdout)[self.name]
        self._data = data
        return data

    @property
    def data(self) -> typing.Dict[str, str]:
        """Return the jail state data that was previously queried."""
        if self._data is None:
            self._data = self.query()
        return self._data

    def clear(self) -> None:
        """Clear the jail state."""
        self._data = None

    def __getitem__(self, name: str) -> str:
        """Get a value from the jail state."""
        return self.data[name]

    def __iter__(
        self
    ) -> typing.Iterator[str]:
        """Iterate over the jail state entries."""
        return self.data.__iter__()

    def keys(self) -> typing.List[str]:  # noqa: T484
        """Return all available jail state keys."""
        return list(self.data.keys())


class JailStates(dict):
    """A dictionary of JailStates."""

    logger: typing.Optional['iocage.lib.Logger.Logger']
    queried: bool

    def __init__(
        self,
        states: typing.Optional[JailStatesDict]=None
    ) -> None:

        if states is None:
            dict.__init__(self, {})
            self.queried = False
        else:
            dict.__init__(self, states)
            self.queried = True

    def query(
        self,
        logger: 'iocage.lib.Logger.Logger'=None
    ) -> None:
        """Invoke update of the jail state from jls output."""
        try:
            if _userland_version >= 11:
                self._query_libxo(logger=logger)
            else:
                self._query_list(logger=logger)
        except BaseException:
            raise iocage.lib.errors.JailStateUpdateFailed()
        self.queried = True

    def _query_libxo(self, logger: 'iocage.lib.Logger.Logger'=None) -> None:
        stdout, _, returncode = iocage.lib.helpers.exec(
            [
                "/usr/sbin/jls",
                "-v",
                "--libxo=json"
            ],
            stderr=subprocess.DEVNULL,
            ignore_error=True,
            logger=logger
        )

        if returncode > 0:
            self.clear()
            return

        output_data = _parse_json(stdout)
        for name in output_data:
            dict.__setitem__(self, name, output_data[name])

    def _query_list(self, logger: 'iocage.lib.Logger.Logger'=None) -> None:
        stdout, _, returncode = iocage.lib.helpers.exec(
            [
                "/usr/sbin/jls",
                "-v",
                "-n",
                "-q"
            ],
            stderr=subprocess.DEVNULL,
            ignore_error=True,
            logger=logger
        )

        if returncode > 0:
            self.clear()
            return

        output_data = _parse(stdout)
        for name in output_data:
            dict.__setitem__(self, name, output_data[name])
