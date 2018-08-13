# Copyright (c) 2014-2018, iocage
# Copyright (c) 2017-2018, Stefan Grönke
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
"""Unit tests for Datasets."""
import pytest
import typing
import libzfs

import iocage.lib


class DatasetsMock(iocage.Datasets.Datasets):
    """Mock the database."""

    ZFS_POOL_ACTIVE_PROPERTY = "org.freebsd.ioc-test:active"


class TestDatasets(object):
    """Run Datasets unit tests."""

    @pytest.fixture
    def MockedDatasets(
        self,
        logger: 'iocage.Logger.Logger',
        pool: libzfs.ZFSPool
    ) -> typing.Generator[DatasetsMock, None, None]:
        """Mock a dataset in a disabled pool."""
        yield DatasetsMock  # noqa: T484

        prop = DatasetsMock.ZFS_POOL_ACTIVE_PROPERTY
        pool.root_dataset.properties[prop].value = "no"

    def test_pool_can_be_activated(
        self,
        MockedDatasets: typing.Generator[DatasetsMock, None, None],
        pool: libzfs.ZFSPool,
        logger: 'iocage.Logger.Logger'
    ) -> None:
        """Test if a pool can be activated."""
        datasets = DatasetsMock(pool=pool, logger=logger)
        datasets.deactivate()
        datasets.activate(mountpoint="/iocage-test")
