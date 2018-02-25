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
import iocage.lib.Resource
import iocage.lib.Filter
import iocage.lib.helpers

import typing

# MyPy
import libzfs


class ReleasesGenerator(iocage.lib.Resource.ListableResource):
    """Generator Model of multiple iocage Releases."""

    _class_release = iocage.lib.Release.ReleaseGenerator

    def __init__(
        self,
        filters: typing.Optional[iocage.lib.Filter.Terms]=None,
        host=None,
        zfs=None,
        logger=None
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)
        self.host = iocage.lib.helpers.init_host(self, host)

        iocage.lib.Resource.ListableResource.__init__(
            self,
            dataset=self.host.datasets.releases,
            filters=filters
        )

    @property
    def local(self):
        """Return true if the release is locally available."""
        release_datasets = self.dataset.children
        return list(map(
            lambda x: self._class_release(
                name=x.name.split("/").pop(),
                logger=self.logger,
                host=self.host,
                zfs=self.zfs
            ),
            release_datasets
        ))

    @property
    def available(self):
        """Return true if the release can be fetched from the remote."""
        return self.host.distribution.releases

    def _create_resource_instance(
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

    def _create_instance(self, *args, **kwargs):
        return self._class_release(*args, **kwargs)


class Releases(ReleasesGenerator):
    """Model of multiple iocage Releases."""

    _class_release = iocage.lib.Release.Release

    def _create_instance(self, *args, **kwargs):
        return iocage.lib.Release.Release(*args, **kwargs)
