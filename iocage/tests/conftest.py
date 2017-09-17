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
import helper_functions
import libzfs
import pytest

import iocage.lib.Host
import iocage.lib.Logger
import iocage.lib.Release

# Inject lib directory to path
# iocage_lib_dir = os.path.abspath(os.path.join(
#     os.path.dirname(__file__),
#     "..", "lib"
# ))
# if iocage_lib_dir not in sys.path:
#     sys.path = [iocage_lib_dir] + sys.path

_force_clean = False


def pytest_addoption(parser):
    parser.addoption("--force-clean", action="store_true",
                     help="Force cleaning the /iocage-test dataset")


def pytest_generate_tests(metafunc):
    metafunc.config.getoption("force_clean")


@pytest.fixture
def force_clean():
    return _force_clean


@pytest.fixture
def zfs():
    return libzfs.ZFS(history=True, history_prefix="<iocage>")


@pytest.fixture
def pool(zfs, logger):
    # find active zpool
    active_pool = None
    for pool in zfs.pools:
        properties = pool.root_dataset.properties
        try:
            value = properties["org.freebsd.ioc:active"].value
            if value == "yes":
                active_pool = pool
        except:
            pass

    if active_pool is None:
        logger.error("No ZFS pool was activated."
                     " Please activate or specify a pool using the"
                     " --pool option")
        exit(1)

    return active_pool


@pytest.fixture
def logger():
    return iocage.lib.Logger.Logger()


@pytest.fixture
def root_dataset(force_clean, zfs, pool):
    dataset_name = f"{pool.name}/iocage-test"

    if force_clean:
        try:
            dataset = zfs.get_dataset(dataset_name)
            helper_functions.unmount_and_destroy_dataset_recursive(dataset)
        except:
            pass

    try:
        pool.create(dataset_name, {})
    except:
        if force_clean:
            raise
        pass

    dataset = zfs.get_dataset(dataset_name)
    if not dataset.mountpoint:
        dataset.mount()

    yield dataset

    if force_clean:
        helper_functions.unmount_and_destroy_dataset_recursive(dataset)


@pytest.fixture
def host(root_dataset, logger, zfs):
    host = iocage.lib.Host.Host(
        root_dataset=root_dataset, logger=logger, zfs=zfs
    )
    yield host
    del host


@pytest.fixture
def release(host, logger, zfs):
    return iocage.lib.Release.Release(
        name=host.release_version, host=host, logger=logger, zfs=zfs
    )
