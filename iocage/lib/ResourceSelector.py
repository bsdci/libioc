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
"""iocage resource selector type."""
import typing

import iocage.lib.Datasets


class ResourceSelector:
    """Parse and wrap resource selectors."""

    source_name: typing.Optional[str]
    _name: str

    def __init__(
        self,
        name: str
    ) -> None:
        self.name = name

    @property
    def name(self) -> str:
        """Return the given name without the source."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        name_components = value.split("/", maxsplit=1)
        if len(name_components) == 2:
            self._name = name_components[1]
            self.source_name = name_components[0]
        else:
            self._name = value
            self.source_name = None

    def __str__(self) -> str:
        """Return the full resource selector string."""
        if self.source_name is None:
            return self._name
        else:
            return f"{self.source_name}/{self._name}"

    def filter_datasets(
        self,
        datasets: iocage.lib.Datasets.Datasets
    ) -> iocage.lib.Datasets.FilteredDatasets:
        """Filter given Datasets according to the resource selector source."""
        if self.source_name is None:
            return datasets

        return iocage.lib.Datasets.filter_datasets(
            datasets=datasets,
            sources=(self.source_name,)
        )
