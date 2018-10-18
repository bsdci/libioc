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
"""Model of multiple iocage Releases."""
import iocage.Release
import iocage.ListableResource
import iocage.Filter
import iocage.helpers_object

import typing

# MyPy
import libzfs
ReleaseListType = typing.List['iocage.Release.ReleaseGenerator']


class ReleasesGenerator(iocage.ListableResource.ListableResource):
    """Generator Model of multiple iocage Releases."""

    host: 'iocage.Host.HostGenerator'
    zfs: 'iocage.ZFS.ZFS'
    logger: 'iocage.Logger.Logger'

    def __init__(
        self,
        filters: typing.Optional[iocage.Filter.Terms]=None,
        host: typing.Optional['iocage.Host.HostGenerator']=None,
        zfs: typing.Optional['iocage.ZFS.ZFS']=None,
        logger: typing.Optional['iocage.Logger.Logger']=None
    ) -> None:

        self.logger = iocage.helpers_object.init_logger(self, logger)
        self.zfs = iocage.helpers_object.init_zfs(self, zfs)
        self.host = iocage.helpers_object.init_host(self, host)

        iocage.ListableResource.ListableResource.__init__(
            self,
            sources=self.host.datasets,
            namespace="releases",
            filters=filters,
            zfs=zfs,
            logger=logger
        )

    @property
    def _class_release(self) -> 'iocage.Release.ReleaseGenerator':
        return iocage.Release.ReleaseGenerator

    @property
    def local(self) -> ReleaseListType:
        """Return the locally available releases."""
        datasets = iocage.ListableResource.ListableResource.__iter__(self)
        return list(map(
            lambda x: self._class_release(  # noqa: T484
                name=x.name.split("/").pop(),
                root_datasets_name=self.host.datasets.find_root_datasets_name(
                    x.name
                ),
                logger=self.logger,
                host=self.host,
                zfs=self.zfs
            ),
            datasets
        ))

    @property
    def available(self) -> ReleaseListType:
        """Return the list of available releases."""
        distribution = self.host.distribution
        releases = distribution.releases  # type: ReleaseListType
        return releases

    def _create_resource_instance(
        self,
        dataset: libzfs.ZFSDataset
    ) -> 'iocage.Release.ReleaseGenerator':
        return self._class_release(
            name=self._get_asset_name_from_dataset(dataset),
            root_datasets_name=self.sources.find_root_datasets_name(
                dataset.name
            ),
            logger=self.logger,
            host=self.host,
            zfs=self.zfs
        )


class Releases(ReleasesGenerator):
    """Model of multiple iocage Releases."""

    @property
    def _class_release(self) -> 'iocage.Release.Release':
        return iocage.Release.Release
