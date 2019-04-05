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
"""Unit tests for VNET."""
import json
import os
import subprocess

import pytest
import libzfs

import libioc.Jail

class TestVNET(object):
    """Run tests for VNET networking."""

    def test_vnet_without_interfaces_can_only_see_lo0(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        """Test if a VNET jail without interfaces can only see lo0."""
        existing_jail.config["vnet"] = True
        existing_jail.save()

        assert len(list(existing_jail.networks)) == 0

        existing_jail.start()

        stdout = subprocess.check_output(
            ["/usr/sbin/jexec", str(existing_jail.jid), "/sbin/ifconfig"]
        ).decode("utf-8")

        # filter lines that begin with a whitespace
        configured_nics = [
            x.split(": ", maxsplit=1)[0]
            for x in stdout.split("\n")
            if (x.startswith("\t") is False) and (len(x) > 0)
        ]

        assert len(configured_nics) == 1
        assert configured_nics[0] == "lo0"
        assert "127.0.0.1" in stdout

    def test_static_ip_configuration(
        self,
        existing_jail: 'libioc.Jail.Jail',
        bridge_interface: str
    ) -> None:
        """Test if static IPv4 and IPv6 addresses can be configured."""
        existing_jail.config["vnet"] = True
        existing_jail.config["interfaces"] = f"vnet23:{bridge_interface}"
        existing_jail.config["ip4_addr"] = f"vnet23|172.16.99.23/24"
        existing_jail.save()

        assert len(list(existing_jail.networks)) == 1

        existing_jail.start()

        stdout = subprocess.check_output([
            "/usr/sbin/jexec",
            str(existing_jail.jid),
            "/sbin/ifconfig",
            "vnet23"
        ]).decode("utf-8")

        # filter lines that begin with a whitespace
        assert "172.16.99.23" in stdout

    def test_vnet_interfaces_are_removed_on_stop(
        self,
        existing_jail: 'libioc.Jail.Jail',
        bridge_interface: str
    ) -> None:
        """Test if VNET interfaces are removed from the host on stop."""
        existing_jail.config["vnet"] = True
        existing_jail.config["interfaces"] = f"vnet22:{bridge_interface}"
        existing_jail.config["ip4_addr"] = f"vnet22|172.16.99.23/24"
        existing_jail.save()

        existing_jail.start()
        jid = existing_jail.jid

        stdout = subprocess.check_output(
            ["/sbin/ifconfig", f"vnet22:{jid}"]
        ).decode("utf-8")

        assert "UP" in stdout

        existing_jail.stop()

        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            stdout = subprocess.check_output(
                ["/sbin/ifconfig", f"vnet22:{jid}"]
            ).decode("utf-8")

    def test_vnet_mac_address_can_be_configured(
        self,
        existing_jail: 'libioc.Jail.Jail',
        bridge_interface: str
    ) -> None:
        """Test manual MAC address setting."""
        mac_a = "02:ab:cd:ef:23:01"
        mac_b = "02:ab:cd:ef:23:02"

        existing_jail.config["vnet"] = True
        existing_jail.config["interfaces"] = f"vnet7:{bridge_interface}"
        existing_jail.config["ip4_addr"] = f"vnet7|172.16.99.7/24"
        existing_jail.config["vnet7_mac"] = (mac_a, mac_b)
        existing_jail.save()
        existing_jail.start()

        stdout = subprocess.check_output([
            "/usr/sbin/jexec",
            str(existing_jail.jid),
            "/sbin/ifconfig",
            "vnet7"
        ]).decode("utf-8")
        assert mac_b in stdout

        stdout = subprocess.check_output([
            "/sbin/ifconfig",
            f"vnet7:{existing_jail.jid}"
        ]).decode("utf-8")
        assert mac_a in stdout
