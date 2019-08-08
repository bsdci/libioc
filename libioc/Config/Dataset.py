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
"""ioc configuration associated with ZFS datasets."""
import os.path
import libzfs
import typing

import libioc.Config.Prototype


class DatasetConfig(libioc.Config.Prototype.Prototype):
    """ioc configuration associated with ZFS datasets."""

    _dataset: libzfs.ZFSDataset

    def __init__(
        self,
        dataset: typing.Optional[libzfs.ZFSDataset]=None,
        file: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        if dataset is not None:
            self._dataset = dataset

        libioc.Config.Prototype.Prototype.__init__(
            self,
            file=file,
            logger=logger
        )

    @property
    def dataset(self) -> libzfs.ZFSDataset:
        """Get the configured dataset."""
        return self._dataset

    @property
    def file(self) -> str:
        """Get the absolute path to the config file."""
        return str(os.path.join(self.dataset.mountpoint, self._file))

    @file.setter
    def file(self, value: str) -> None:
        """Set the relative path of the config file."""
        self._file = value
