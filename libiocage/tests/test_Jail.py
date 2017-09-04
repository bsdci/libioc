# Copyright (c) 2014-2017, iocage
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
import json
import os
import uuid

import helper_functions
import pytest

import libiocage.lib.Jail


def read_jail_config_json(config_file):
    with open(config_file, "r") as conf:
        return json.load(conf)


class TestJail(object):

    @pytest.fixture
    def local_release(self, release, root_dataset, force_clean, zfs):

        if not release.fetched:
            release.fetch()

        yield release

        if force_clean:
            release.dataset.umount()
            release.dataset.delete()

        del release

    def test_can_be_created(self, host, local_release, logger, zfs,
                            root_dataset, capsys):

        jail = libiocage.lib.Jail.Jail(
            new=True,
            host=host,
            logger=logger,
            zfs=zfs
        )
        jail.create(local_release.name)

        dataset = zfs.get_dataset(f"{root_dataset.name}/jails/{jail.name}")

        def cleanup():
            helper_functions.unmount_and_destroy_dataset_recursive(dataset)

        try:
            uuid.UUID(jail.name)
            assert len(str(jail.name)) == 36
            assert not jail.config["basejail"]
            assert not jail.config["basejail_type"]

            assert dataset.mountpoint is not None
            assert os.path.isfile(f"{dataset.mountpoint}/config.json")
            assert os.path.isdir(f"{dataset.mountpoint}/root")

            data = read_jail_config_json(f"{dataset.mountpoint}/config.json")

            try:
                assert data["basejail"] is "no"
            except (KeyError) as e:
                pass

            try:
                assert (data["basejail"] is "") or (data["basejail"] == "none")
            except (KeyError) as e:
                pass

        except Exception as e:
            cleanup()
            raise e

        cleanup()


class TestNullFSBasejail(object):

    @pytest.fixture
    def local_release(self, release, root_dataset, force_clean, zfs):

        if not release.fetched:
            release.fetch()

        yield release

        if force_clean:
            release.dataset.umount()
            release.dataset.delete()

        del release

    def test_can_be_created(self, host, local_release, logger, zfs,
                            root_dataset):

        jail = libiocage.lib.Jail.Jail({
                "basejail": True
            },
            new=True,
            host=host,
            logger=logger,
            zfs=zfs
        )
        jail.create(local_release.name)

        dataset = zfs.get_dataset(f"{root_dataset.name}/jails/{jail.name}")

        def cleanup():
            helper_functions.unmount_and_destroy_dataset_recursive(dataset)

        try:
            uuid.UUID(jail.name)
            assert len(str(jail.name)) == 36
            assert jail.config["basejail"]
            assert jail.config["basejail_type"] == "nullfs"

            assert dataset.mountpoint is not None
            assert os.path.isfile(f"{dataset.mountpoint}/config.json")
            assert os.path.isdir(f"{dataset.mountpoint}/root")

            data = read_jail_config_json(f"{dataset.mountpoint}/config.json")

            assert data["basejail"] == "yes"

            try:
                assert data["basejail_type"] == "nullfs"
            except KeyError as e:
                pass

        except Exception as e:
            cleanup()
            raise e

        cleanup()
