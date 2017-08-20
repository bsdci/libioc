import pytest

import libiocage.lib


class TestDatasets(object):

    @pytest.fixture
    def MockedDatasets(self, logger, pool):

        class DatasetsMock(libiocage.lib.Datasets.Datasets):
            ZFS_POOL_ACTIVE_PROPERTY = "org.freebsd.ioc-test:active"

        yield DatasetsMock

        prop = DatasetsMock.ZFS_POOL_ACTIVE_PROPERTY
        pool.root_dataset.properties[prop].value = "no"

    def test_pool_can_be_activated(self, MockedDatasets, pool, logger):
        datasets = MockedDatasets(pool=pool, logger=logger)
        datasets.activate()
