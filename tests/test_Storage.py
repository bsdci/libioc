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
import pytest
import json

import libioc.Jail

class Storage(object):

    def test_nullfs_basejail_is_default(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        NullFSBasejailStorage = libioc.Storage.NullFSBasejail.NullFSBasejail
        assert existing_jail.storage_backend == NullFSBasejailStorage
        assert existing_jail.config["basejail"] == True
        assert existing_jail.config["basejail_type"] == "nullfs"

    def test_does_not_mount_devfs_by_default(
        self,
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        existing_jail.start()
        stdout = subprocess.check_output(
            [f"/sbin/mount | grep {existing_jail.root_dataset.name}"],
            shell=True
        ).decode("utf-8")
        assert "/dev" not in stdout

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
