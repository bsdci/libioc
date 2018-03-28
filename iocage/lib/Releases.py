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
"""Model of multiple iocage Releases."""
import iocage.lib.Release
import iocage.lib.ListableResource
import iocage.lib.Filter
import iocage.lib.helpers

import typing

# MyPy
import libzfs
ReleaseListType = typing.List[iocage.lib.Release.ReleaseGenerator]


class ReleasesGenerator(iocage.lib.ListableResource.ListableResource):
    """Generator Model of multiple iocage Releases."""

    _class_release = iocage.lib.Release.ReleaseGenerator
    host: 'iocage.lib.Host.HostGenerator'
    zfs: 'iocage.lib.ZFS.ZFS'
    logger: 'iocage.lib.Logger.Logger'

    def __init__(
        self,
        filters: typing.Optional[iocage.lib.Filter.Terms]=None,
        sources: typing.Optional[typing.Tuple[str, ...]]=None,
        host: typing.Optional['iocage.lib.Host.HostGenerator']=None,
        zfs: typing.Optional['iocage.lib.ZFS.ZFS']=None,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None
    ) -> None:

        self.host = iocage.lib.helpers.init_host(self, host)

        iocage.lib.ListableResource.ListableResource.__init__(
            self,
            sources=iocage.lib.Datasets.filter_datasets(
                datasets=self.host.datasets,
                sources=sources
            ),
            namespace="releases",
            filters=filters,
            zfs=zfs,
            logger=logger
        )

    @property
    def local(self) -> ReleaseListType:
        """Return the locally available releases."""

        datasets = iocage.lib.ListableResource.ListableResource.__iter__(self)
        return list(map(
            lambda x: self._class_release(
                name=x.name.split("/").pop(),
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

    def _create_resource_instance(  # noqa T484
        self,
        dataset: libzfs.ZFSDataset,
        *args,
        **kwargs
    ) -> iocage.lib.Release.ReleaseGenerator:

        kwargs["name"] = self._get_asset_name_from_dataset(dataset)
        kwargs["logger"] = self.logger
        kwargs["host"] = self.host
        kwargs["zfs"] = self.zfs
        return self._class_release(*args, **kwargs)

    def _create_instance(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> iocage.lib.Release.ReleaseGenerator:
        return self._class_release(*args, **kwargs)


class Releases(ReleasesGenerator):
    """Model of multiple iocage Releases."""

    _class_release = iocage.lib.Release.Release

    def _create_instance(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> iocage.lib.Release.Release:
        return iocage.lib.Release.Release(*args, **kwargs)
