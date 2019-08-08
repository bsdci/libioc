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
"""ioc MacAddress module."""
import typing
import collections.abc

import libioc.helpers_object
import libioc.errors


class MacAddress:
    """Representation of a NICs hardware address."""

    _address: str

    def __init__(
        self,
        mac_address: str,
        logger: 'libioc.Logger.Logger'
    ) -> None:
        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.address = mac_address

    @property
    def address(self) -> str:
        """Return the actual hardware address."""
        return self._address

    @address.setter
    def address(self, mac_address: str) -> None:
        """Set the hardware address."""
        address = mac_address.replace(":", "").replace("-", "").lower()

        if len(address) != 12:
            raise libioc.errors.InvalidMacAddress(
                mac_address=mac_address,
                logger=self.logger
            )

        self._address = address

    def __str__(self) -> str:
        """Return the hardware address as string."""
        address = self.address
        mac_bytes = [address[i:(i + 2)] for i in range(0, len(address), 2)]
        return ":".join(mac_bytes)


class MacAddressPair:
    """Representation of a hardware address pair (of epair devices)."""

    a: MacAddress
    b: MacAddress

    def __init__(
        self,
        mac_pair: typing.Union[
            str,
            typing.Tuple[MacAddress, MacAddress],
            typing.Tuple[str, str]
        ],
        logger: 'libioc.Logger.Logger'
    ) -> None:

        self.logger = libioc.helpers_object.init_logger(self, logger)
        a: MacAddress
        b: MacAddress

        if isinstance(mac_pair, str):
            a, b = [MacAddress(
                mac_address=x,
                logger=self.logger
            ) for x in mac_pair.split(",")]
        elif all((
            isinstance(mac_pair, collections.abc.Iterable),
            (len(mac_pair) == 2)
        )) is True:
            left, right = mac_pair
            if isinstance(left, MacAddress) and isinstance(right, MacAddress):
                a = left
                b = right
            elif isinstance(left, str) and isinstance(right, str):
                a = MacAddress(left, logger=self.logger)
                b = MacAddress(right, logger=self.logger)
            else:
                raise ValueError("tuple of string or MacAddress expected")
        else:
            raise ValueError("str or tuple of 2 items required")

        self.a = a
        self.b = b

    def __str__(self) -> str:
        """Return the epairs hardware addresses concatenated with a comma."""
        return f"{self.a},{self.b}"
