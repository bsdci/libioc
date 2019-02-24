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
import random

import pytest
import libzfs

import libioc.Jail


def read_jail_config_json(config_file: str) -> dict:
    """Read the jail JSON config file."""
    with open(config_file, "r") as conf:
        return dict(json.load(conf))


@pytest.fixture(scope="function")
def shared_zfs_dataset(
    root_dataset: libzfs.ZFSDataset,
    zfs: libzfs.ZFS
) -> libzfs.ZFSDataset:
    name = f"{root_dataset.name}/shared-" + str(random.randint(1, 32768))
    root_dataset.pool.create(name, {})
    dataset = zfs.get_dataset(name)
    dataset.properties["jailed"] = libzfs.ZFSUserProperty("on")
    yield dataset
    dataset.delete()


class TestSharedZFSDataset(object):
    """Run Jail unit tests."""

    def test_mount_shared_zfs_dataset_on_start(
        self,
        shared_zfs_dataset: libzfs.ZFSDataset,
        new_jail: 'libioc.Jail.Jail',
        local_release: 'libioc.Release.ReleaseGenerator',
    ) -> None:
        """Test if jails can be created."""
        new_jail.config["jail_zfs"] = True
        new_jail.config["jail_zfs_dataset"] = shared_zfs_dataset.name
        new_jail.create(local_release)

        new_jail.start()

        stdout, _, code = new_jail.exec(["/sbin/zfs", "list"])
        assert shared_zfs_dataset.name in stdout
