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
"""custom iocage types."""
import typing
import re


class Path(str):
    """Wrapper Type for ensuring a `str` matches a Unix Path."""

    blacklist = re.compile(
        r"(\/\/)|(\/\.\.)|(\.\.\/)|(\n)|(\r)|(^\.+$)",
        re.MULTILINE
    )

    def __init__(
        self,
        sequence: str
    ) -> None:
        if isinstance(sequence, str) is False:
            raise TypeError("Path must be a string")

        if len(self.blacklist.findall(sequence)) > 0:
            raise ValueError(f"Illegal path: {sequence}")

        self = sequence  # type: ignore


class AbsolutePath(Path):
    """Wrapper Type for ensuring a `str` matches an absolute Unix Path."""

    def __init__(
        self,
        sequence: str
    ) -> None:
        if isinstance(sequence, str) is False:
            raise TypeError("AbsolutePath must be a string or Path")

        if str(sequence).startswith("/") is False:
            raise ValueError(
                f"Expected AbsolutePath to begin with /, but got: {sequence}"
            )

        super().__init__(sequence)


class UserInput:
    """Any kind of user input data."""

    def __init__(
        self,
        data: typing.Union[str, int, float, bool, None]
    ) -> None:

        ...
