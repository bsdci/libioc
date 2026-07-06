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
"""
Unit test configuration.

The suite runs in two modes.
On a FreeBSD host with py-libzfs and an activated ZFS pool (--zpool) the
whole suite is available.
On other platforms the import-time shims from tests/linux_shims stand in
for the FreeBSD-only packages, so that the platform-independent tests
run and every ZFS or jail dependent test is skipped visibly.
"""
import typing
import os
import os.path
import sys
import subprocess
import random
import pytest

import helper_functions

_HERE = os.path.dirname(os.path.abspath(__file__))

try:
    import libzfs
except ImportError:
    sys.path.insert(0, os.path.join(_HERE, "linux_shims"))
    import libzfs

HAS_REAL_LIBZFS = not getattr(libzfs, "__libioc_test_shim__", False)
_SKIP_REASON = "requires FreeBSD (py-libzfs)"

import libioc  # noqa: E402
import libioc.Distribution  # noqa: E402
import libioc.Host  # noqa: E402
import libioc.Logger  # noqa: E402
import libioc.Pkg  # noqa: E402
import libioc.Release  # noqa: E402

if HAS_REAL_LIBZFS is True:
    import release_mirror_cache
    cache_server = release_mirror_cache.BackgroundServer(8081)
    os.environ["http_proxy"] = "http://127.0.0.1:8081"
else:
    cache_server = None


def pytest_addoption(parser: typing.Any) -> None:
    """Add the --zpool option to pytest."""
    parser.addoption(
        "--zpool",
        action="store",
        help="Select a ZFS pool for the unit tests"
    )


def pytest_report_header(config: typing.Any) -> str:
    """Report whether the FreeBSD-only tests are available."""
    if HAS_REAL_LIBZFS is True:
        return "libioc: py-libzfs found, full suite available"
    return "libioc: py-libzfs unavailable, FreeBSD-only tests are skipped"


@pytest.fixture(scope="session")
def zfs() -> 'libzfs.ZFS':
    """Make ZFS available to the tests."""
    if HAS_REAL_LIBZFS is False:
        pytest.skip(_SKIP_REASON)
    return libzfs.ZFS(history=True, history_prefix="<iocage>")


@pytest.fixture(scope="session")
def pool(
    request: typing.Any,
    zfs: 'libzfs.ZFS',
    logger: 'libioc.Logger.Logger'
) -> 'libzfs.ZFSPool':
    """Find the active iocage pool."""
    requested_pool = request.config.getoption("--zpool")

    if requested_pool is None:
        pytest.skip(
            "No ZFS pool was activated. "
            "Please activate or specify a pool using the --zpool option"
        )

    target_pool = list(filter(
        lambda pool: (pool.name == requested_pool),
        zfs.pools
    ))[0]
    return target_pool


@pytest.fixture(scope="session")
def logger(tmp_path_factory: typing.Any) -> 'libioc.Logger.Logger':
    """Make the iocage Logger available to the tests.

    The log directory points into the test's temporary directory, so
    that the suite does not require write access to /var/log.
    """
    log_directory = tmp_path_factory.mktemp("iocage-log")
    return libioc.Logger.Logger(log_directory=str(log_directory))


@pytest.fixture(scope="session")
def root_dataset(
    zfs: 'libzfs.ZFS',
    pool: 'libzfs.ZFSPool'
) -> 'libzfs.ZFSDataset':
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
    """Distribution that downloads releases from a configurable mirror."""

    @property
    def mirror_url(self) -> str:
        """Return the mirror URL of the distribution.

        The FreeBSD releases the test suite runs on have reached their
        end of life, so the archive server is the default source.
        The LIBIOC_TEST_MIRROR environment variable overrides it.
        """
        architecture = os.uname().machine
        default_mirror = (
            "http://ftp-archive.freebsd.org/pub/FreeBSD-Archive"
            f"/old-releases/{architecture}/{architecture}"
        )
        return os.environ.get("LIBIOC_TEST_MIRROR", default_mirror)


class MockedHost(libioc.Host.Host):
    """Host with the mocked distribution class."""

    _class_distribution = MockedDistribution


@pytest.fixture
def host(
    root_dataset: 'libzfs.ZFSDataset',
    logger: 'libioc.Logger.Logger',
    zfs: 'libzfs.ZFS'
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
    zfs: 'libzfs.ZFS'
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
    root_dataset: 'libzfs.ZFSDataset',
    zfs: 'libzfs.ZFS'
) -> typing.Iterator['libioc.Release.ReleaseGenerator']:
    """Mock a local release.

    Updating the release requires the freebsd-update infrastructure,
    which no longer serves end-of-life releases, so fetching updates is
    disabled unless LIBIOC_TEST_FETCH_UPDATES is set to 1.
    """
    if not release.fetched:
        fetch_updates = os.environ.get("LIBIOC_TEST_FETCH_UPDATES", "0")
        want_updates = (fetch_updates == "1")
        release.fetch(fetch_updates=want_updates, update=want_updates)

    yield release
    del release


@pytest.fixture(scope="function")
def new_jail(
    host: 'libioc.Host.Host',
    logger: 'libioc.Logger.Logger',
    zfs: 'libzfs.ZFS'
) -> typing.Iterator['libioc.Jail.Jail']:
    """Return a Jail object that does not exist on disk yet."""
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
) -> typing.Iterator['libioc.Jail.Jail']:
    """Return a Jail that exists on disk."""
    new_jail.create(local_release)
    yield new_jail


@pytest.fixture(scope="function")
def bridge_interface() -> typing.Iterator[str]:
    """Create a temporary bridge interface on the host."""
    if HAS_REAL_LIBZFS is False:
        pytest.skip(_SKIP_REASON)
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
    zfs: 'libzfs.ZFS'
) -> 'libioc.Pkg.Pkg':
    """Make the Pkg module available to the tests."""
    return libioc.Pkg.Pkg(
        logger=logger,
        zfs=zfs,
        host=host
    )


def pytest_unconfigure() -> None:
    """Stop the release mirror cache server."""
    if cache_server is not None:
        cache_server.stop()
