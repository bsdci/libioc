import os
import platform

import libiocage.lib.Datasets
import libiocage.lib.DevfsRules
import libiocage.lib.Distribution
import libiocage.lib.helpers


class HostGenerator:

    _class_distribution = libiocage.lib.Distribution.DistributionGenerator

    def __init__(self, root_dataset=None, zfs=None, logger=None):

        libiocage.lib.helpers.init_logger(self, logger)
        libiocage.lib.helpers.init_zfs(self, zfs)
        self.datasets = libiocage.lib.Datasets.Datasets(
            root=root_dataset,
            logger=self.logger,
            zfs=self.zfs
        )
        self.distribution = self._class_distribution(
            host=self,
            logger=self.logger
        )

        self._devfs = None
        self.releases_dataset = None

    @property
    def devfs(self):
        """
        Lazy-loaded DevfsRules instance
        """
        if self._devfs is None:
            self._devfs = libiocage.lib.DevfsRules.DevfsRules(
                logger=self.logger
            )
        return self._devfs

    @property
    def userland_version(self):
        return float(self.release_version.partition("-")[0])

    @property
    def release_minor_version(self):
        release_version_string = os.uname()[2]
        release_version_fragments = release_version_string.split("-")

        if len(release_version_fragments) < 3:
            return 0

        return int(release_version_fragments[2])

    @property
    def release_version(self):
        release_version_string = os.uname()[2]
        release_version_fragments = release_version_string.split("-")

        if len(release_version_fragments) > 1:
            return "-".join(release_version_fragments[0:2])

    @property
    def processor(self):
        return platform.processor()


class Host(HostGenerator):

    class_distribution = libiocage.lib.Distribution.DistributionGenerator
