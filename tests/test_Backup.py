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
"""Unit tests for Jail Import/Export."""
import typing
import json
import os
import os.path
import pathlib

import pytest
import libzfs

import libioc.Jail
import libioc.ResourceBackup


def read_jail_config_json(config_file: str) -> dict:
    """Read the jail JSON config file."""
    with open(config_file, "r") as conf:
        return dict(json.load(conf))


class TestBackup(object):
    """Run Jail Backup (import/export) unit tests."""

    def test_nullfs_basejail_can_be_exported_standalone(
        self,
        tmp_path: pathlib.Path,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        """Test if a jail can be started."""
        existing_jail.config["basejail"] = True
        existing_jail.config["basejail_type"] = "nullfs"
        existing_jail.save()

        work_dir = tmp_path / "export"

        export_events = list(existing_jail.backup.export(
            destination=work_dir,
            backup_format=libioc.ResourceBackup.Format.DIRECTORY,
            standalone=True
        ))

        assert os.path.isdir(work_dir)

        config_file_path = str(work_dir / "config.json")
        assert os.path.exists(config_file_path)
        assert os.path.isfile(config_file_path)

        config_data = read_jail_config_json(config_file_path)
        assert config_data["release"] == existing_jail.config["release"]
        assert config_data["basejail"] == "yes"

        assert os.path.exists(str(work_dir / "root.zfs"))

    def test_nullfs_basejail_can_be_exported_differentially(
        self,
        tmp_path: pathlib.Path,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        """Test if a jail can be started."""
        existing_jail.config["basejail"] = True
        existing_jail.config["basejail_type"] = "nullfs"
        existing_jail.save()

        work_dir = tmp_path / "export"

        export_events = list(existing_jail.backup.export(
            destination=work_dir,
            backup_format=libioc.ResourceBackup.Format.DIRECTORY,
            standalone=False
        ))

        assert os.path.isdir(work_dir)

        config_file_path = str(work_dir / "config.json")
        assert os.path.exists(config_file_path)
        assert os.path.isfile(config_file_path)

        config_data = read_jail_config_json(config_file_path)
        assert config_data["release"] == existing_jail.config["release"]
        assert config_data["basejail"] == "yes"

        assert os.path.exists(str(work_dir / "root.zfs")) is False
        assert os.path.isdir(str(work_dir / "root")) is True

    def test_import_empty_differential_backup(
        self,
        tmp_path: pathlib.Path,
        new_jail: 'libioc.Jail.Jail',
        release: 'libioc.Release.Release',
        host: 'libioc.Host.Host'
    ) -> None:
        """Test if differential backups with empty root can be imported."""
        new_jail_name = new_jail.name
        backup_config_file = str(tmp_path / "config.json")
        backup_config_data = dict(
            release=release.name,
            ip4_addr="vnet0|192.168.24.2/24",
            interfaces="vnet0:bridge0"
        )
        os.makedirs(tmp_path / "root", mode=0o770)
        with open(backup_config_file, "w") as f:
            json.dump(backup_config_data, f)

        restore_events = list(new_jail.backup.restore(tmp_path))

        assert new_jail.exists
        jail = libioc.Jail.Jail(new_jail_name, host=host)
        assert jail.name == new_jail_name
        for key, value in backup_config_data.items():
            assert jail.config.data[key] == backup_config_data[key]
