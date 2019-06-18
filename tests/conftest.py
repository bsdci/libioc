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
"""Unit test configuration."""
import typing
import os
import os.path
import sys
import subprocess
import random
import pytest

import helper_functions
import libzfs

import libioc
import libioc.Host
import libioc.Distribution
import libioc.Logger
import libioc.Release
import libioc.Pkg

import release_mirror_cache
cache_server = release_mirror_cache.BackgroundServer(8081)
os.environ["http_proxy"] = "http://127.0.0.1:8081"


def pytest_addoption(parser: typing.Any) -> None:
    """Add force option to pytest."""
    parser.addoption(
        "--zpool",
        action="store",
        help="Select a ZFS pool for the unit tests"
    )


@pytest.fixture
def zfs() -> libzfs.ZFS:
    """Make ZFS available to the tests."""
    return libzfs.ZFS(history=True, history_prefix="<iocage>")


@pytest.fixture(scope="session")
def pool(
    request: typing.Any,
    zfs: libzfs.ZFS,
    logger: 'libioc.Logger.Logger'
) -> libzfs.ZFSPool:
    """Find the active iocage pool."""
    requested_pool = request.config.getoption("--zpool")

    if requested_pool is None:
        logger.error(
            "No ZFS pool was activated. "
            "Please activate or specify a pool using the "
            "--zpool option"
        )
        exit(1)

    target_pool = list(filter(
        lambda pool: (pool.name == requested_pool),
        zfs.pools
    ))[0]
    return target_pool


@pytest.fixture
def logger() -> 'libioc.Logger.Logger':
    """Make the iocage Logger available to the tests."""
    return libioc.Logger.Logger()


@pytest.fixture(scope="session")
def root_dataset(
    zfs: libzfs.ZFS,
    pool: libzfs.ZFSPool
) -> libzfs.ZFSDataset:
    """Return the root dataset for tests."""
    dataset_name = f"{pool.name}/libioc-test"

    try:
        pool.create(dataset_name, {})
    except libzfs.ZFSException:
        pass

    dataset = zfs.get_dataset(dataset_name)

    if dataset.properties["mountpoint"].value == "none":
        mountpoint = libzfs.ZFSUserProperty("/.libioc-test")
        dataset.properties["mountpoint"] = mountpoint

    if not dataset.mountpoint:
        dataset.mount()

    return dataset


class MockedDistribution(libioc.Distribution.Distribution):

    @property
    def mirror_url(self) -> str:
        """Return the mirror URL of the distribution."""
        architecture = os.uname().machine
        return (
            "http://download.FreeBSD.org/ftp/releases"
            f"/{architecture}/{architecture}"
        )


class MockedHost(libioc.Host.Host):

    _class_distribution = MockedDistribution


@pytest.fixture
def host(
    root_dataset: libzfs.ZFSDataset,
    logger: 'libioc.Logger.Logger',
    zfs: libzfs.ZFS
) -> 'libioc.Host.Host':
    """Make the libioc.Host available to the tests."""
    datasets = libioc.Datasets.Datasets(
        sources=dict(test=root_dataset),
        logger=logger,
        zfs=zfs
    )
    host = MockedHost(
        datasets=datasets,
        logger=logger,
        zfs=zfs
    )
    return host


@pytest.fixture
def release(
    host: 'libioc.Host.HostGenerator',
    logger: 'libioc.Logger.Logger',
    zfs: libzfs.ZFS
) -> 'libioc.Release.ReleaseGenerator':
    """Return the test release matching the host release version."""
    if host.release_version.endswith("RELEASE"):
        target_release = host.release_version
    else:
        target_release = "12.0-RELEASE"

    release = libioc.Release.Release(
        name=target_release, host=host, logger=logger, zfs=zfs
    )
    return release


@pytest.fixture
def local_release(
    release: 'libioc.Release.ReleaseGenerator',
    root_dataset: libzfs.ZFSDataset,
    zfs: libzfs.ZFS
) -> 'libioc.Release.ReleaseGenerator':
    """Mock a local release."""
    if not release.fetched:
        release.fetch(fetch_updates=True, update=True)

    yield release
    del release


@pytest.fixture(scope="function")
def new_jail(
    host: 'libioc.Host.Host',
    logger: 'libioc.Logger.Logger',
    zfs: libzfs.ZFS
) -> 'libioc.Jail.Jail':
    jail_name = "new-jail-" + str(random.randint(1, 32768))
    new_jail = libioc.Jail.Jail(
        dict(name=jail_name),
        new=True,
        host=host,
        logger=logger,
        zfs=zfs
    )
    yield new_jail
    if new_jail.exists is True:
        new_jail.stop(force=True)
        new_jail.destroy()


@pytest.fixture(scope="function")
def existing_jail(
    new_jail: 'libioc.Jail.Jail',
    local_release: 'libioc.Release.ReleaseGenerator',
) -> 'libioc.Jail.Jail':
    new_jail.create(local_release)
    yield new_jail


@pytest.fixture(scope="function")
def bridge_interface() -> str:
    bridge_name = "bridgeTest" + str(random.randint(1024, 4096))
    subprocess.check_output(
        ["/sbin/ifconfig", "bridge", "create", "name", str(bridge_name), "up"]
    )
    yield bridge_name
    subprocess.check_output(
        ["/sbin/ifconfig", str(bridge_name), "destroy"]
    )


@pytest.fixture
def pkg(
    host: 'libioc.Host.Host',
    logger: 'libioc.Logger.Logger',
    zfs: libzfs.ZFS
) -> 'libioc.Pkg.Pkg':
    return libioc.Pkg.Pkg(
        logger=logger,
        zfs=zfs,
        host=host
    )


def pytest_unconfigure() -> None:
    cache_server.stop()
