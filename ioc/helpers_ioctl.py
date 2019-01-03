# Copyright (c) 2017-2018, Stefan Grönke
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
"""Interface for ioctl abstraction."""
import socket
import struct
import fcntl
import ipaddress

from enum import Enum


class SOCKIO_IOCTLS(Enum):
    """Hardcoded ioctl numbers."""

    SIOCGIFADDR = -1071617759
    SIOCGIFMTU = -1071617741


def get_sockio_ioctl(nic_name: str, ioctl: SOCKIO_IOCTLS) -> bytes:
    """Query a sockio ioctl for a given NIC."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0) as sock:
        ifconf = struct.pack('256s', nic_name.encode("UTF-8")[:15])
        return bytes(fcntl.ioctl(sock.fileno(), ioctl.value, ifconf))


def get_interface_ip4_address(nic_name: str) -> ipaddress.IPv4Address:
    """Return the primary IPv4Address of a given NIC."""
    ifconf = get_sockio_ioctl(nic_name, SOCKIO_IOCTLS.SIOCGIFADDR)
    ipv4_hex = struct.unpack('4s', ifconf[20:24])[0]
    return ipaddress.IPv4Address(ipv4_hex)


def get_interface_mtu(nic_name: str) -> int:
    """Return the primary MTU of a given NIC."""
    ifconf = get_sockio_ioctl(nic_name, SOCKIO_IOCTLS.SIOCGIFMTU)
    return int(struct.unpack('<H', ifconf[16:18])[0])


