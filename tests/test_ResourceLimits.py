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
"""Unit tests for Jail Resource Limits."""
import typing
import pytest
import subprocess


class TestResourceLimits(object):
    """Run Resource Limit tests."""

    @staticmethod
    def __mib_to_bytes(value: int) -> int:
        return value * 1024 * 1024

    def test_limits_are_applied_to_jails_on_start(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:

        vmemoryuse_bytes = self.__mib_to_bytes(1024)
        memoryuse_bytes = self.__mib_to_bytes(512)

        existing_jail.config["pcpu"] = 20
        existing_jail.config["vmemoryuse"] = "1024M"
        existing_jail.config["memoryuse"] = "512M"
        existing_jail.save()

        existing_jail.start()
        identifier = existing_jail.identifier

        lines = subprocess.check_output(
            [f"/usr/bin/rctl | grep {identifier}"],
            shell=True
        ).decode("utf-8").strip().split("\n")

        assert f"jail:{identifier}:pcpu:deny=20" in lines
        assert f"jail:{identifier}:vmemoryuse:deny={vmemoryuse_bytes}" in lines
        assert f"jail:{identifier}:memoryuse:deny={memoryuse_bytes}" in lines
        assert len(lines) == 3

        lines = subprocess.check_output(
            [f"/usr/bin/rctl", "-u", f"jail:{identifier}"]
        ).decode("utf-8").strip().split("\n")

    def test_limits_are_removed_when_a_jail_is_stopped(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:

        existing_jail.config["pcpu"] = 20
        existing_jail.config["vmemoryuse"] = "1024M"
        existing_jail.config["memoryuse"] = "512M"
        existing_jail.save()

        existing_jail.start()
        existing_jail.stop()

        # rctl timing issue
        import time
        time.sleep(1)

        stdout = subprocess.check_output(
            [f"/usr/bin/rctl | grep {existing_jail.identifier} | 2>&1"],
            shell=True
        ).decode("utf-8").strip()

        assert len(stdout) == 0
