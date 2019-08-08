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
"""ioc resource selector type."""
import typing
import re

import libioc.Datasets


class ResourceSelector:
    """Parse and wrap resource selectors."""

    source_name: typing.Optional[str]
    _name: str

    SOURCE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9]+((\-|_)?[A-Za-z0-9]+)*$")

    def __init__(
        self,
        name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        self.logger = logger
        self.name = name

    @property
    def name(self) -> str:
        """Return the given name without the source."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        name_components = value.split("/", maxsplit=1)
        _source_name: typing.Optional[str]
        if len(name_components) == 2:
            _name = name_components[1]
            _source_name = name_components[0]
            if self._validate_source_name(_source_name) is False:
                raise libioc.errors.InvalidSourceName(logger=self.logger)
        else:
            _name = value
            _source_name = None

        _name_without_globs = _name.replace("*", "").replace("+", "")
        has_valid_name = libioc.helpers.validate_name(_name_without_globs)
        is_valid_uuid = libioc.helpers.is_uuid(_name_without_globs)
        if (_name not in ["*", "+"]) and not (has_valid_name or is_valid_uuid):
            raise libioc.errors.InvalidJailName(name=_name, logger=self.logger)

        self.source_name = _source_name
        self._name = _name

    def _validate_source_name(self, name: str) -> bool:
        return self.SOURCE_NAME_PATTERN.match(name) is not None

    def __str__(self) -> str:
        """Return the full resource selector string."""
        if self.source_name is None:
            return self._name
        else:
            return f"{self.source_name}/{self._name}"

    def filter_datasets(
        self,
        datasets: 'libioc.Datasets.Datasets'
    ) -> 'libioc.Datasets.FilteredDatasets':
        """Filter given Datasets according to the resource selector source."""
        if self.source_name is None:
            return datasets

        return libioc.Datasets.filter_datasets(
            datasets=datasets,
            sources=(self.source_name,)
        )
