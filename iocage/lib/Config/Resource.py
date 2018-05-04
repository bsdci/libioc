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
"""Configuration stored on a resource."""
import typing
import os.path
import libzfs
import iocage.lib.Config.Prototype


class ResourceConfig(iocage.lib.Config.Prototype.Prototype):
    """Configuration stored on a resource."""

    resource: 'iocage.lib.Resource.Resource' = None

    def __init__(
        self,
        resource: 'iocage.lib.Resource.Resource',
        file: typing.Optional[str]=None,
        logger: typing.Optional[iocage.lib.Logger.Logger]=None
    ) -> None:
        self.resource = resource
        iocage.lib.Config.Prototype.Prototype.__init__(
            self,
            file=file,
            logger=logger
        )

    @property
    def dataset(self) -> libzfs.ZFSDataset:
        """Wrap the resource dataset."""
        dataset: libzfs.ZFSDataset = self.resource.dataset
        return dataset

    @property
    def file(self) -> str:
        """Absolute path to the configuration file."""
        return str(os.path.join(
            self.resource.dataset.mountpoint,
            self._file
        ))

    @file.setter
    def file(self, value: str) -> None:
        """Set the configuration file path relative to the resource."""
        self._file = value
