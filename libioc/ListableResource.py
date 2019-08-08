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
"""
A ListableResource hosts child resources in a flat structure.

In case of a Jail or a Release, those children are ZFS datasets nested in the
listable resource's ZFS dataset.

With filters applied to a ListableResource, all children returned listed have
to match the input filters. Unlike Releases, that can only be filtered by their
dataset name, it is possible to match configuration variables for Jails.
"""
import typing
import libzfs
import abc
import itertools

import libioc.Filter
import libioc.Resource
import libioc.helpers_object


class ListableResource(list):
    """Representation of Resources that can be listed."""

    _filters: typing.Optional['libioc.Filter.Terms'] = None
    sources: 'libioc.Datasets.Datasets'
    namespace: typing.Optional[str]

    def __init__(
        self,
        sources: 'libioc.Datasets.Datasets',
        namespace: typing.Optional[str]=None,
        filters: typing.Optional['libioc.Filter.Terms']=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        zfs: typing.Optional['libioc.ZFS.ZFS']=None
    ) -> None:

        list.__init__(self, [])

        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)

        self.namespace = namespace
        self.sources = sources
        self.filters = filters

    @property
    def filters(self) -> typing.Optional['libioc.Filter.Terms']:
        """Return the filters that are applied on the list items."""
        return self._filters

    @filters.setter
    def filters(
        self,
        value: typing.Iterable[typing.Union['libioc.Filter.Term', str]]
    ) -> None:
        """Set the filters that are applied on the list items."""
        if isinstance(value, libioc.Filter.Terms):
            self._filters = value
        else:
            self._filters = libioc.Filter.Terms(value, logger=self.logger)

    def destroy(self, force: bool=False) -> None:
        """Listable resources by itself cannot be destroyed."""
        raise NotImplementedError("destroy unimplemented for ListableResource")

    def __iter__(
        self
    ) -> typing.Generator['libioc.Resource.Resource', None, None]:
        """Return an iterator over the child datasets."""
        if self.namespace is None:
            raise libioc.errors.ListableResourceNamespaceUndefined(
                logger=self.logger
            )

        filters = self._filters
        has_filters = (filters is not None)

        for root_name, root_datasets in self.sources.items():
            if (filters is not None):
                if (filters.match_source(root_name) is False):
                    # skip when the resources defined source does not match
                    continue
            children = root_datasets.__getattribute__(self.namespace).children
            for child_dataset in children:
                name = self._get_asset_name_from_dataset(child_dataset)
                if has_filters and (filters.match_key("name", name) is False):
                    # Skip all jails that do not even match the name
                    continue

                # ToDo: Do not load jail if filters do not require to
                resource = self._get_resource_from_dataset(child_dataset)
                if self._filters is not None:
                    if self._filters.match_resource(resource):
                        yield resource

    def __getitem__(  # noqa: T484
        self,
        index: int
    ) -> 'libioc.Resource.Resource':
        """Return the resource at a certain index position."""
        items = self.__iter__()
        try:
            for _ in itertools.repeat(None, index):
                next(items)
            return next(items)
        except StopIteration:
            pass
        raise IndexError("list index out of range")

    def __len__(self) -> int:
        """Return the number of resources matching the filters."""
        return len(list(self.__iter__()))

    def __repr__(self) -> str:
        """Return the resource list string representation."""
        resource_names = ", ".join([x.name for x in self.__iter__()])
        return f"[{resource_names}]"

    def _get_asset_name_from_dataset(
        self,
        dataset: libzfs.ZFSDataset
    ) -> str:
        """
        Return the last fragment of a dataset's name.

        Example:
            /iocage/jails/foo -> foo
        """
        return str(dataset.name.split("/").pop())

    def _get_resource_from_dataset(
        self,
        dataset: libzfs.ZFSDataset
    ) -> 'libioc.Resource.Resource':

        return self._create_resource_instance(dataset)

    @abc.abstractmethod
    def _create_resource_instance(  # noqa: T484
        self,
        dataset: libzfs.ZFSDataset
    ) -> 'libioc.Resource.Resource':
        pass

