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
"""ioc module of jail collections."""
import libzfs
import typing

import libioc.Jail
import libioc.Filter
import libioc.ListableResource
import libioc.helpers_object


class JailsGenerator(libioc.ListableResource.ListableResource):
    """Asynchronous representation of a collection of jails."""

    # Keys that are stored on the Jail object, not the configuration
    JAIL_KEYS = [
        "jid",
        "name",
        "running",
        "ip4.addr",
        "ip6.addr"
    ]

    resource_args: typing.Dict[str, typing.Any]

    def __init__(
        self,
        filters: typing.Optional[libioc.Filter.Terms]=None,
        host: typing.Optional['libioc.Host.HostGenerator']=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        zfs: typing.Optional['libioc.ZFS.ZFS']=None,
        **resource_args: typing.Any
    ) -> None:

        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)
        self.host = libioc.helpers_object.init_host(self, host)

        self.resource_args = resource_args

        libioc.ListableResource.ListableResource.__init__(
            self,
            sources=self.host.datasets,
            namespace="jails",
            filters=filters,
            zfs=zfs,
            logger=logger
        )

    @property
    def _class_jail(self) -> libioc.Jail.JailGenerator:
        return libioc.Jail.JailGenerator

    def _create_resource_instance(
        self,
        dataset: libzfs.ZFSDataset
    ) -> 'libioc.Jail.JailGenerator':

        jail = self._class_jail(
            data=dict(id=dataset.name.split("/").pop()),
            root_datasets_name=self.sources.find_root_datasets_name(
                dataset.name
            ),
            logger=self.logger,
            host=self.host,
            zfs=self.zfs,
            **self.resource_args
        )

        return jail

    def __getitem__(self, index: int) -> 'libioc.Jail.JailGenerator':
        """Return the JailGenerator at a certain index position."""
        _getitem = libioc.ListableResource.ListableResource.__getitem__
        jail = _getitem(self, index)  # type: libioc.Jail.JailGenerator
        return jail


class Jails(JailsGenerator):
    """Synchronous wrapper ofs JailsGenerator."""

    @property
    def _class_jail(self) -> libioc.Jail.Jail:
        return libioc.Jail.Jail

    def __getitem__(self, index: int) -> 'libioc.Jail.Jail':
        """Return the Jail object at a certain index position."""
        _getitem = JailsGenerator.__getitem__
        jail = _getitem(self, index)  # type: libioc.Jail.Jail
        return jail
