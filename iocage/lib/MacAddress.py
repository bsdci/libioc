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
import typing

import iocage.lib.helpers
import iocage.lib.errors


class MacAddress:

    _address: str

    def __init__(
        self,
        mac_address: str,
        logger: 'iocage.lib.Logger.Logger'
    ) -> None:
        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.address = mac_address

    @property
    def address(self):
        return self._address

    @address.setter
    def address(self, mac_address: str) -> None:
        address = mac_address.replace(":", "").replace("-", "").lower()

        if len(address) != 12:
            raise iocage.lib.errors.InvalidMacAddress(
                mac_address=mac_address,
                logger=self.logger
            )

        self._address = address

    def __str__(self) -> str:
        address = self.address
        mac_bytes = [address[i:i+2] for i in range(0, len(address), 2)]
        return ":".join(mac_bytes)


class MacAddressPair:

    a: MacAddress
    b: MacAddress

    def __init__(
        self,
        mac_pair: typing.Union[
            str,
            typing.Tuple[MacAddress, MacAddress],
            typing.Tuple[str, str]
        ],
        logger: 'iocage.lib.Logger.Logger'
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)

        if isinstance(mac_pair, str):
            a, b = [MacAddress(
                mac_address=x,
                logger=self.logger
            ) for x in mac_pair.split(",")]
        elif isinstance(mac_pair[0], str):
            a = MacAddress(mac_pair[0], logger=self.logger)
            b = MacAddress(mac_pair[1], logger=self.logger)
        else:
            a, b = mac_pair

        self.a = a
        self.b = b

    def __str__(self) -> str:
        return f"{self.a},{self.b}"
