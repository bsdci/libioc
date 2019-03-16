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
import typing
import json
import os
import subprocess

import pytest
import libzfs

import libioc.Jail


def read_jail_config_json(config_file: str) -> dict:
    """Read the jail JSON config file."""
    with open(config_file, "r") as conf:
        return dict(json.load(conf))


class TestJail(object):
    """Run Jail unit tests."""

    def test_can_be_created(
        self,
        new_jail: 'libioc.Jail.Jail',
        local_release: 'libioc.Release.ReleaseGenerator',
        root_dataset: libzfs.ZFSDataset,
        zfs: libzfs.ZFS
    ) -> None:
        """Test if jails can be created."""
        new_jail.config["basejail"] = False
        new_jail.create(local_release)

        dataset = zfs.get_dataset(f"{root_dataset.name}/jails/{new_jail.name}")

        assert new_jail.is_basejail is False
        assert new_jail.config["basejail"] is False
        assert not new_jail.config["basejail_type"]

        assert dataset.mountpoint is not None
        assert os.path.isfile(f"{dataset.mountpoint}/config.json")
        assert os.path.isdir(f"{dataset.mountpoint}/root")

        data = read_jail_config_json(f"{dataset.mountpoint}/config.json")

        assert data["basejail"] != "yes"
        assert data["basejail"] != "on"
        assert data["basejail"] != 1
        assert data["basejail"] != True

    def test_can_be_started(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        """Test if a jail can be started."""
        existing_jail.config["mount_devfs"] = False
        existing_jail.save()

        assert existing_jail.running is False
        existing_jail.start()
        assert existing_jail.running is True

        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {existing_jail.root_dataset.name}"],
            shell=True
        ).decode("utf-8")

        assert "launch-scripts in stdout"
        assert stdout.strip().count("\n") == 1

    def test_can_be_stopped(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        """Test if a jail can be started."""
        existing_jail.start()
        assert existing_jail.running is True
        existing_jail.stop()
        assert existing_jail.running is False


class TestNullFSBasejail(object):
    """Run tests for NullFS Basejails."""

    @pytest.fixture
    def basedirs(self, host: 'libioc.Host.Host'):
        basedirs = [
            "bin",
            "boot",
            "lib",
            "libexec",
            "rescue",
            "sbin",
            "usr/bin",
            "usr/include",
            "usr/lib",
            "usr/libexec",
            "usr/sbin",
            "usr/share",
            "usr/libdata",
        ]
        if host.distribution.name == "FreeBSD":
            basedirs.append("usr/lib32")
        return basedirs

    def test_can_be_created(
        self,
        new_jail: 'libioc.Jail.Jail',
        local_release: 'libioc.Release.ReleaseGenerator',
        root_dataset: libzfs.ZFSDataset,
        zfs: libzfs.ZFS
    ) -> None:
        """Test if NullFS basejails can be created."""
        new_jail.config["basejail"] = True
        new_jail.create(local_release)

        dataset = zfs.get_dataset(f"{root_dataset.name}/jails/{new_jail.name}")

        assert new_jail.is_basejail is True
        assert new_jail.config["basejail"] is True
        assert new_jail.config["basejail_type"] == "nullfs"

        assert dataset.mountpoint is not None
        assert os.path.isfile(f"{dataset.mountpoint}/config.json")
        assert os.path.isdir(f"{dataset.mountpoint}/root")

        data = read_jail_config_json(f"{dataset.mountpoint}/config.json")

        assert data["basejail"] == "yes"
        if "basejail_type" in data:
            assert data["basejail_type"] == "nullfs"

    def test_can_be_started(
        self,
        existing_jail: 'libioc.Jail.Jail',
        basedirs: typing.List[str]
    ) -> None:
        """Test if a jail can be started."""
        existing_jail.config["mount_devfs"] = False
        existing_jail.config["basejail"] = True
        existing_jail.save()

        assert existing_jail.running is False
        existing_jail.start()
        assert existing_jail.running is True

        root_path = existing_jail.root_dataset.name
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {existing_jail.root_dataset.name}"],
            shell=True
        ).decode("utf-8")
        assert "launch-scripts in stdout"
        assert stdout.strip().count("\n") == 1 + len(basedirs)
        for basedir in basedirs:
            assert f"{root_path}/{basedir}" in stdout

    def test_can_be_stopped(
        self,
        existing_jail: 'libioc.Jail.Jail',
        basedirs: typing.List[str]
    ) -> None:
        """Test if a jail can be started."""
        existing_jail.start()
        assert existing_jail.running is True
        existing_jail.stop()
        assert existing_jail.running is False

        root_path = existing_jail.root_dataset.name
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {root_path}"],
            shell=True
        ).decode("utf-8")
        for basedir in basedirs:
            assert f"{root_path}/{basedir}" not in stdout
