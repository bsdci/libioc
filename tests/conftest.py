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
"""Unit test configuration."""
import typing
import helper_functions
import libzfs
import pytest

import libioc.Host
import libioc.Distribution
import libioc.Logger
import libioc.Release

# Inject lib directory to path
# iocage_lib_dir = os.path.abspath(os.path.join(
#     os.path.dirname(__file__),
#     "..", "lib"
# ))
# if iocage_lib_dir not in sys.path:
#     sys.path = [iocage_lib_dir] + sys.path

_force_clean = False


def pytest_addoption(parser: typing.Any) -> None:
    """Add force option to pytest."""
    parser.addoption(
        "--force-clean",
        action="store_true",
        help="Force cleaning the /libioc-test dataset"
    )
    parser.addoption(
        "--zpool",
        action="store",
        help="Select a ZFS pool for the unit tests"
    )


def pytest_generate_tests(metafunc: typing.Any) -> None:
    """Configure test function creation."""
    metafunc.config.getoption("force_clean")


@pytest.fixture
def force_clean() -> bool:
    """Return True when force-clean is enabled."""
    return _force_clean


@pytest.fixture
def zfs() -> libzfs.ZFS:
    """Make ZFS available to the tests."""
    return libzfs.ZFS(history=True, history_prefix="<iocage>")


@pytest.fixture
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


@pytest.fixture
def root_dataset(
    force_clean: bool,
    zfs: libzfs.ZFS,
    pool: libzfs.ZFSPool
) -> libzfs.ZFSDataset:
    """Return the root dataset for tests."""
    dataset_name = f"{pool.name}/libioc-test"

    if force_clean:
        try:
            dataset = zfs.get_dataset(dataset_name)
            helper_functions.unmount_and_destroy_dataset_recursive(dataset)
        except libzfs.ZFSException:
            pass

    try:
        pool.create(dataset_name, {})
    except libzfs.ZFSException:
        if force_clean is True:
            raise

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
        print("MIRROR REQUESTED")
        return "http://127.0.0.1:8081"


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


import release_mirror_cache
release_mirror_cache.run_thread(8081)

