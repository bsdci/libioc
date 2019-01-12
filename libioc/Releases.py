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
"""Model of multiple iocage Releases."""
import libioc.Release
import libioc.ListableResource
import libioc.Filter
import libioc.helpers_object

import typing

# MyPy
import libzfs
ReleaseListType = typing.List['libioc.Release.ReleaseGenerator']


class ReleasesGenerator(libioc.ListableResource.ListableResource):
    """Generator Model of multiple iocage Releases."""

    host: 'libioc.Host.HostGenerator'
    zfs: 'libioc.ZFS.ZFS'
    logger: 'libioc.Logger.Logger'

    def __init__(
        self,
        filters: typing.Optional[libioc.Filter.Terms]=None,
        host: typing.Optional['libioc.Host.HostGenerator']=None,
        zfs: typing.Optional['libioc.ZFS.ZFS']=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)
        self.host = libioc.helpers_object.init_host(self, host)

        libioc.ListableResource.ListableResource.__init__(
            self,
            sources=self.host.datasets,
            namespace="releases",
            filters=filters,
            zfs=zfs,
            logger=logger
        )

    @property
    def _class_release(self) -> 'libioc.Release.ReleaseGenerator':
        return libioc.Release.ReleaseGenerator

    @property
    def local(self) -> ReleaseListType:
        """Return the locally available releases."""
        datasets = libioc.ListableResource.ListableResource.__iter__(self)
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
    ) -> 'libioc.Release.ReleaseGenerator':
        return self._class_release(
            name=self._get_asset_name_from_dataset(dataset),
            root_datasets_name=self.sources.find_root_datasets_name(
                dataset.name
            ),
            logger=self.logger,
            host=self.host,
            zfs=self.zfs
        )

    def __getitem__(self, index: int) -> 'libioc.Release.ReleaseGenerator':
        """Return the ReleaseGenerator at a certain index position."""
        _getitem = libioc.ListableResource.ListableResource.__getitem__
        r = _getitem(self, index)  # type: libioc.Release.ReleaseGenerator
        return r


class Releases(ReleasesGenerator):
    """Model of multiple iocage Releases."""

    @property
    def _class_release(self) -> 'libioc.Release.Release':
        return libioc.Release.Release

    def __getitem__(self, index: int) -> 'libioc.Release.Release':
        """Return the Jail object at a certain index position."""
        _getitem = ReleasesGenerator.__getitem__
        release = _getitem(self, index)  # type: libioc.Release.Release
        return release
