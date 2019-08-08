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
"""ioc wrappers for ipaddress.IPv4Interface and ipaddress.IPv6Interface."""
import typing
import ipaddress


class IPv4Interface(ipaddress.IPv4Interface):
    """ipaddress.IPv4Interface extention that accepts DHCP as input."""

    _ip: typing.Union[str, int]

    def __init__(self, address: typing.Union[str, int]) -> None:
        if isinstance(address, str) and (address.lower() == "dhcp"):
            self._ip = "dhcp"
        else:
            super().__init__(address)

    def __str__(self) -> str:
        """Return 'dhcp' or the string representation of the IP."""
        if isinstance(self._ip, int):
            return super().__str__()
        return str(self._ip)

    def __hash__(self) -> int:
        """Return the IPs hash or -1 for DHCP."""
        if (self._ip == "dhcp"):
            return -1
        return super().__hash__()


class IPv6Interface(ipaddress.IPv6Interface):
    """ipaddress.IPv6Interface extention that accepts ACCEPT_RTADV as input."""

    _ip: typing.Union[str, int]

    def __init__(self, address: typing.Union[str, int]) -> None:
        if isinstance(address, str) and (address.lower() == "accept_rtadv"):
            self._ip = "accept_rtadv"
        else:
            super().__init__(address)

    def __str__(self) -> str:
        """Return 'accept_rtadv' or the string representation of the IP."""
        if isinstance(self._ip, int):
            return super().__str__()
        return str(self._ip)

    def __hash__(self) -> int:
        """Return the IPs hash or -1 for ACCEPT_RTADV."""
        if (self._ip == "accept_rtadv"):
            return -1
        return super().__hash__()
