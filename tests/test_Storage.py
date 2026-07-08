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
"""Unit tests for Jail and Default Config."""
import subprocess
import unittest.mock

import pytest
import json

import libioc.events
import libioc.Jail
import libioc.Storage.Standalone
import libioc.Storage.ZFSBasejail
import libioc.ZFS


class TestStorage(object):
    """Run tests for jail storage backends."""

    def test_standalone_storage_is_default(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        Standalone = libioc.Storage.Standalone
        assert existing_jail.storage_backend == (
            Standalone.StandaloneJailStorage
        )
        assert existing_jail.config["basejail"] == False
        assert existing_jail.config["basejail_type"] is None

    def test_mounts_devfs_by_default(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        existing_jail.start()
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {existing_jail.root_dataset.name}"],
            shell=True
        ).decode("utf-8")
        assert "/dev" in stdout

    def test_devfs_can_be_enabled_and_is_mounted_and_unmounted(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        existing_jail.config["mount_devfs"] = True
        existing_jail.save()

        existing_jail.start()
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {existing_jail.root_dataset.name}"],
            shell=True
        ).decode("utf-8")
        assert "/dev" in stdout

        existing_jail.stop()
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {existing_jail.root_dataset.name}"],
            shell=True
        ).decode("utf-8")
        assert "/dev" not in stdout


class TestStorageErrorPaths(object):
    """Run tests for the storage backend error paths."""

    def test_standalone_apply_is_not_implemented(
        self,
        logger: 'libioc.Logger.Logger'
    ) -> None:
        storage = libioc.Storage.Standalone.StandaloneJailStorage(
            jail=unittest.mock.Mock(),
            zfs=unittest.mock.Mock(spec=libioc.ZFS.ZFS),
            logger=logger
        )

        with pytest.raises(NotImplementedError):
            storage.apply()

    def test_zfs_basejail_apply_yields_the_config_event(
        self,
        logger: 'libioc.Logger.Logger'
    ) -> None:
        storage = libioc.Storage.ZFSBasejail.ZFSBasejailStorage(
            jail=unittest.mock.Mock(),
            zfs=unittest.mock.Mock(spec=libioc.ZFS.ZFS),
            logger=logger
        )

        events = storage.apply(release=unittest.mock.Mock())

        assert isinstance(next(events), libioc.events.BasejailStorageConfig)
