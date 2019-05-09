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
"""Unit tests for the Pkg Jail module."""
import typing
import pytest
import os
import os.path
import subprocess

import libzfs

import libioc.Pkg


class TestPkg(object):

    @pytest.fixture(scope="function")
    def pkg(
        self,
        host: 'libioc.Host.HostGenerator',
        logger: 'libioc.Logger.LoggerGenerator',
        zfs: 'libioc.ZFS.ZFS'
    ) -> libioc.Pkg.Pkg:
        return libioc.Pkg.Pkg(
            host=host,
            logger=logger,
            zfs=zfs
        )

    def test_can_mirror_packages(
        self,
        pkg: libioc.Pkg.Pkg,
        release: 'libioc.Release.ReleaseGenerator',
        root_dataset: libzfs.ZFSDataset
    ) -> None:

        major_version = int(release.version_number)
        local_pkg_dir = f"{root_dataset.mountpoint}/pkg/{major_version}"

        list(pkg.fetch(
            ["sl", "git-lite"],
            release=release
        ))

        assert os.path.exists(local_pkg_dir)
        assert os.path.isdir(local_pkg_dir)
        assert os.path.exists(
            f"{local_pkg_dir}/repos/ioc-release-{major_version}.conf"
        )

        cache_dir_index = os.listdir(f"{local_pkg_dir}/cache")
        assert any([x.startswith("sl") for x in cache_dir_index])
        assert any([x.startswith("git-lite") for x in cache_dir_index])

    def test_can_install_packages_to_stopped_jail(
        self,
        pkg: libioc.Pkg.Pkg,
        release: 'libioc.Release.ReleaseGenerator',
        existing_jail: 'libioc.Jail.Jail'
    ) -> None:
        packages = ["sl"]
        list(pkg.fetch_and_install(
            packages=packages,
            jail=existing_jail
        ))
        assert os.path.exists(f"{existing_jail.root_path}/usr/local/bin/sl")
        assert existing_jail.running is False

        pkg_mountpoint = existing_jail.root_path + "/.ioc-pkg"
        stdout = subprocess.check_output(
            [f"/sbin/mount"]
        ).decode("utf-8")
        assert str(pkg_mountpoint) not in stdout
