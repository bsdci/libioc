# Copyright (c) 2017-2019, Stefan Grönke
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
"""Unit tests for non-VNET jails."""
import ipaddress
import subprocess

import libioc.Jail

class TestNetwork(object):
    """Run tests for non-VNET networking."""

    def test_can_set_non_vnet_ip_addresses(
        self,
        existing_jail: 'libioc.Jail.Jail',
        bridge_interface: str
    ) -> None:

        ip4_addr = ipaddress.IPv4Interface("172.16.78.4/24")
        ip6_addr = ipaddress.IPv6Interface("2001:db8:c0de::/64")

        existing_jail.config["vnet"] = False
        existing_jail.config["ip4_addr"] = f"{bridge_interface}|{ip4_addr}"
        existing_jail.config["ip6_addr"] = f"{bridge_interface}|{ip6_addr}"
        existing_jail.save()

        existing_jail.start()
        stdout, _, returncode = existing_jail.exec([
            "/sbin/ifconfig",
            bridge_interface
        ])

        assert returncode == 0
        assert str(ip4_addr.ip) in stdout
        assert str(ip6_addr.ip) in stdout

        existing_jail.stop()
        stdout = subprocess.check_output(["/sbin/ifconfig"]).decode("utf-8")
        assert str(ip4_addr.ip) not in stdout
        assert str(ip6_addr.ip) not in stdout


    def test_can_set_multiple_non_vnet_ip_addresses(
        self,
        existing_jail: 'libioc.Jail.Jail',
        bridge_interface: str
    ) -> None:

        ip4_addr1 = ipaddress.IPv4Interface("172.16.79.4/24")
        ip4_addr2 = ipaddress.IPv4Interface("172.16.81.5/24")
        ip6_addr1 = ipaddress.IPv6Interface("2001:db8:c0de::3/64")
        ip6_addr2 = ipaddress.IPv6Interface("2001:db8:10c::2/64")

        existing_jail.config["vnet"] = False
        existing_jail.config["ip4_addr"] = ",".join([
            f"{bridge_interface}|{ip4_addr1}",
            f"{bridge_interface}|{ip4_addr2}"
        ])
        existing_jail.config["ip6_addr"] = ",".join([
            f"{bridge_interface}|{ip6_addr1}",
            f"{bridge_interface}|{ip6_addr2}"
        ])
        existing_jail.save()

        existing_jail.start()
        stdout, _, returncode = existing_jail.exec([
            "/sbin/ifconfig",
            bridge_interface
        ])

        print(stdout)
        print("-----")
        print(subprocess.check_output(["jls", "-n"]).decode("utf-8"))
        assert returncode == 0
        assert str(ip4_addr1.ip) in stdout
        assert str(ip4_addr2.ip) in stdout
        assert str(ip6_addr1.ip) in stdout
        assert str(ip6_addr2.ip) in stdout

        existing_jail.stop()
        stdout = subprocess.check_output(["/sbin/ifconfig"]).decode("utf-8")
        assert str(ip4_addr1.ip) not in stdout
        assert str(ip4_addr2.ip) not in stdout
        assert str(ip6_addr1.ip) not in stdout
        assert str(ip6_addr2.ip) not in stdout
