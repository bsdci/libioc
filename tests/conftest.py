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
import os.path
import sys
import tempfile

# Inject lib directory to path
iocage_lib_dir = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    ".."
))
if iocage_lib_dir not in sys.path:
    sys.path = [iocage_lib_dir] + sys.path

import libioc.Datasets
import libioc.Host
import libioc.Logger
import libioc.Release

_force_clean = False


def pytest_addoption(parser: typing.Any) -> None:
    """Add force option to pytest."""
    parser.addoption(
        "--force-clean",
        action="store_true",
        help="Force cleaning the /iocage-test dataset"
    )
    parser.addoption(
        "--dataset-name",
        action="store",
        help="Select a ZFS dataset for the unit tests"
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
def logger() -> 'libioc.Logger.Logger':
    """Make the iocage Logger available to the tests."""
    return libioc.Logger.Logger(print_level="spam")


@pytest.fixture
def root_dataset(
    request: typing.Any,
    force_clean: bool,
    zfs: libzfs.ZFS,
) -> libzfs.ZFSDataset:
    """Return the root dataset for tests."""
    dataset_name = request.config.getoption("--dataset-name")

    pool = list(filter(
        lambda pool: (pool.name == dataset_name[:dataset_name.index("/")]),
        zfs.pools
    ))[0]

    if force_clean:
        try:
            dataset = zfs.get_dataset(dataset_name)
            helper_functions.unmount_and_destroy_dataset_recursive(
                dataset
            )
        except libzfs.ZFSException:
            pass

    try:
        pool.create(dataset_name, {})
    except libzfs.ZFSException:
        if force_clean is True:
            raise

    dataset = zfs.get_dataset(dataset_name)
    temp_dir = tempfile.mkdtemp(suffix="ioc")
    new_mountpoint = libzfs.ZFSUserProperty(temp_dir)
    dataset.properties["mountpoint"] = new_mountpoint
    if not dataset.mountpoint:
        dataset.mount()

    return dataset

    if force_clean:
        helper_functions.unmount_and_destroy_dataset_recursive(dataset)


@pytest.fixture
def datasets(
    root_dataset: libzfs.ZFSDataset,
    logger: 'libioc.Logger.Logger',
    zfs: libzfs.ZFS
) -> libioc.Datasets.Datasets:
    return libioc.Datasets.Datasets(
        sources=dict(testing=root_dataset),
        logger=logger,
        zfs=zfs
    )


@pytest.fixture
def host(
    datasets: libioc.Datasets,
    logger: 'libioc.Logger.Logger',
    zfs: libzfs.ZFS
) -> 'libioc.Host.HostGenerator':
    """Make the libioc.Host available to the tests."""
    return libioc.Host.Host(
        datasets=datasets,
        logger=logger,
        zfs=zfs
    )


@pytest.fixture
def release(
    host: 'libioc.Host.HostGenerator',
    logger: 'libioc.Logger.Logger',
    zfs: libzfs.ZFS
) -> 'libioc.Release.ReleaseGenerator':
    """Return the test release matching the host release version."""
    return libioc.Release.Release(
        name=host.release_version, host=host, logger=logger, zfs=zfs
    )
