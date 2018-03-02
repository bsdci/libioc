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
"""iocage host bridge interface module."""
import typing


class BridgeInterface:
    """Representation of an iocage host bridge interface."""

    name: str
    secure: bool

    SECURE_BRIDGE_PREFIX = ":"

    def __init__(
        self,
        name: str,
        secure: typing.Optional[bool]=None
    ) -> None:

        if name.startswith(self.SECURE_BRIDGE_PREFIX):
            self.secure = True
            self.name = name[1:]
        else:
            self.name = name
            self.secure = False

        # may override name set secure mode
        if secure is not None:
            self.secure = secure

    def __str__(self) -> str:
        """
        Return the internal interface name string.

        It begins with a colon when an additional virtual bridge interface is
        used to mitigate ARP spoofing with IPFW.
        """
        if self.secure is True:
            return f"{self.SECURE_BRIDGE_PREFIX}{self.name}"
        else:
            return self.name

