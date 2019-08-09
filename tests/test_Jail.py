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
"""Unit tests for Jail."""
import typing
import json
import os
import subprocess
import random

import pytest
import pathlib

import libzfs

import libioc.Jail
import libioc.Config.Jail.File.Fstab


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

        assert stdout.strip().count("\n") == 0

    def test_can_mount_devfs(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        """Test if a jail can be started."""
        existing_jail.config["mount_devfs"] = True
        existing_jail.config["mount_fdescfs"] = False
        existing_jail.save()

        existing_jail.start()
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {existing_jail.root_dataset.name}"],
            shell=True
        ).decode("utf-8")
        assert "/dev" in stdout
        assert "/dev/fd" not in stdout

        existing_jail.stop()
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {existing_jail.root_dataset.name}"],
            shell=True
        ).decode("utf-8")
        assert "/dev" not in stdout

    def test_can_mount_fdescfs(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        """Test if a jail can be started."""
        existing_jail.config["mount_devfs"] = False
        existing_jail.config["mount_fdescfs"] = True
        existing_jail.save()

        existing_jail.start()
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {existing_jail.root_dataset.name}"],
            shell=True
        ).decode("utf-8")
        assert "/dev/fd" in stdout
        assert "/dev (" not in stdout

        existing_jail.stop()
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {existing_jail.root_dataset.name}"],
            shell=True
        ).decode("utf-8")
        assert "/dev/fd" not in stdout

    def test_can_mount_devfs_and_fdescfs(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        """Test if a jail can be started."""
        existing_jail.config["mount_devfs"] = True
        existing_jail.config["mount_fdescfs"] = True
        existing_jail.save()

        existing_jail.start()
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {existing_jail.root_dataset.name}"],
            shell=True
        ).decode("utf-8")
        assert "/dev (" in stdout
        assert "/dev/fd" in stdout

        existing_jail.stop()
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {existing_jail.root_dataset.name}"],
            shell=True
        ).decode("utf-8")
        assert "/dev (" not in stdout
        assert "/dev/fd" not in stdout

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
        assert stdout.strip().count("\n") == len(basedirs)
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

        with pytest.raises(subprocess.CalledProcessError):
            stdout = subprocess.check_output(
                [f"/usr/sbin/jls", "-j", existing_jail.identifier]
            ).decode("utf-8")

        root_path = existing_jail.root_dataset.name
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {root_path}"],
            shell=True
        ).decode("utf-8")
        for basedir in basedirs:
            assert f"{root_path}/{basedir}" not in stdout

    def test_fstab_mountpoints_are_unmounted_on_stop(
        self,
        tmp_path: pathlib.Path,
        existing_jail: 'libioc.Jail.Jail',
        basedirs: typing.List[str]
    ) -> None:
        """Test if a jail can be started."""
        existing_jail.fstab.new_line(
            source=str(tmp_path),
            destination=str(tmp_path),
            type="nullfs"
        )
        existing_jail.fstab.save()

        with open(existing_jail.fstab.path, "r", encoding="UTF-8") as f:
            fstab_content = f.read()
            assert len(fstab_content.split("\n")) == 1

        target_mountpoint = existing_jail.root_path + str(tmp_path)
        os.makedirs(target_mountpoint)

        existing_jail.start()
        stdout = subprocess.check_output(
            [f"/sbin/mount"]
        ).decode("utf-8")
        assert str(target_mountpoint) in stdout

        existing_jail.stop()
        stdout = subprocess.check_output(
            [f"/sbin/mount"]
        ).decode("utf-8")
        assert str(target_mountpoint) not in stdout

    def test_getstring_returns_empty_string_for_unknown_user_properties(
        self,
        new_jail: 'libioc.Jail.Jail'
    ) -> None:
        """Test if getstring for an unknown user property is empty."""
        assert new_jail.getstring("user.unknown_propery") == ""
        with pytest.raises(libioc.errors.UnknownConfigProperty):
            new_jail.getstring("unknown_property")

    def test_hooks_can_access_ioc_env_variables(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        """Test if IOC_* ENV variables can be accessed from hook scripts."""
        jail = libioc.Jail.JailGenerator(
            existing_jail.full_name,
            host=existing_jail.host,
            zfs=existing_jail.zfs,
            logger=existing_jail.logger
        )
        jail.config["exec_prestart"] = "env"
        jail.config["exec_start"] = "env"
        jail.config["exec_poststart"] = "env"

        for event in jail.start():
            if event.done is False:
                continue
            if isinstance(event, libioc.events.JailHook):
                assert "\nIOC_" in event.stdout
            if isinstance(event, libioc.events.JailHookPoststart) is True:
                assert f"IOC_JID={jail.jid}" in event.stdout

    def test_jail_name_validation(self) -> None:
        assert libioc.helpers.is_valid_name("ioc") is True
        assert libioc.helpers.is_valid_name("ioc23") is True
        assert libioc.helpers.is_valid_name("23ioc") is True
        assert libioc.helpers.is_valid_name("ioc-23") is True
        assert libioc.helpers.is_valid_name("23-ioc") is True
        assert libioc.helpers.is_valid_name("ioc!jail") is True
        assert libioc.helpers.is_valid_name("ci-bsd!ioc") is True
        assert libioc.helpers.is_valid_name("IOC") is True
        assert libioc.helpers.is_valid_name("IoC23") is True
        assert libioc.helpers.is_valid_name("Grönke") is True
        assert libioc.helpers.is_valid_name("jail>ioc") is True
        assert libioc.helpers.is_valid_name("jail{ioc}23") is True
        assert libioc.helpers.is_valid_name("jail.with.dots") is True

        assert libioc.helpers.is_valid_name("") is False
        assert libioc.helpers.is_valid_name("ioc\n23") is False
        assert libioc.helpers.is_valid_name("ioc\t23") is False
        assert libioc.helpers.is_valid_name("ioc-") is False
        assert libioc.helpers.is_valid_name("!ioc") is False
        assert libioc.helpers.is_valid_name("@gronke") is False
        assert libioc.helpers.is_valid_name("stefan@gronke") is False
        assert libioc.helpers.is_valid_name("23-ioc-") is False
        assert libioc.helpers.is_valid_name("white space") is False
        assert libioc.helpers.is_valid_name("ioc\\jail") is False
        assert libioc.helpers.is_valid_name("jail{ioc}") is False
        assert libioc.helpers.is_valid_name("we❤jails") is False

    def test_jail_with_dot_in_name_can_be_created_and_started(
        self,
        new_jail: 'libioc.Jail.Jail',
        local_release: 'libioc.Release.ReleaseGenerator',
        root_dataset: libzfs.ZFSDataset,
        zfs: libzfs.ZFS
    ) -> None:
        """Test if NullFS basejails can be created."""
        jail_name_with_dots = "dot.test." + str(random.randint(1, 32768))
        new_jail.config["name"] = jail_name_with_dots
        new_jail.config["basejail"] = True

        new_jail.create(local_release)
        assert new_jail.exists is True

        assert new_jail.running is False
        new_jail.start()
        assert new_jail.running is True

        assert new_jail.identifier.endswith(
            # only check suffix, because source dataset name might vary
            "-" + jail_name_with_dots.replace(".", "*")
        )
