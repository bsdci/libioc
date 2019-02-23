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
"""Unit tests for Jail."""
import json
import os
import subprocess

import pytest
import libzfs

import libioc.Jail

class TestVNET(object):
    """Run tests for NullFS Basejails."""

    def test_vnet_without_interfaces_can_only_see_lo0(
        self,
        new_jail: 'libioc.Jail.Jail',
        local_release: 'libioc.Release.ReleaseGenerator'
    ) -> None:
        """Test if a VNET jail without interfaces can only see lo0."""
        new_jail.config["vnet"] = True
        new_jail.create(local_release)

        assert len(list(new_jail.networks)) == 0

        new_jail.start()

        stdout_lines = subprocess.check_output(
            ["/usr/sbin/jexec", str(new_jail.jid), "/sbin/ifconfig"]
        ).decode().split("\n")

        # filter lines that begin with a whitespace
        configured_nics = [
            x.split(": ", maxsplit=1)[0]
            for x in stdout_lines
            if (x.startswith("\t") is False) and (len(x) > 0)
        ]

        assert len(configured_nics) == 1
        assert configured_nics[0] == "lo0"

    def test_static_ip_configuration(
        self,
        new_jail: 'libioc.Jail.Jail',
        local_release: 'libioc.Release.ReleaseGenerator',
        bridge_interface: str
    ) -> None:
        """Test if static IPv4 and IPv6 addresses can be configured."""
        new_jail.config["vnet"] = True
        new_jail.config["interfaces"] = f"vnet23:{bridge_interface}"
        new_jail.config["ip4_addr"] = f"vnet23|172.16.99.23/24"
        new_jail.create(local_release)

        assert len(list(new_jail.networks)) == 1

        new_jail.start()

        stdout = subprocess.check_output(
            ["/usr/sbin/jexec", str(new_jail.jid), "/sbin/ifconfig", "vnet23"]
        ).decode()

        # filter lines that begin with a whitespace
        assert "172.16.99.23" in stdout
