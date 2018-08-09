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
"""iocage module of jail collections."""
import libzfs
import typing

import iocage.lib.Jail
import iocage.lib.Filter
import iocage.lib.ListableResource
import iocage.lib.helpers


class JailsGenerator(iocage.lib.ListableResource.ListableResource):
    """Asynchronous representation of a collection of jails."""

    _class_jail = iocage.lib.Jail.JailGenerator
    states = iocage.lib.JailState.JailStates()

    # Keys that are stored on the Jail object, not the configuration
    JAIL_KEYS = [
        "jid",
        "name",
        "running",
        "ip4.addr",
        "ip6.addr"
    ]

    def __init__(
        self,
        filters: typing.Optional[iocage.lib.Filter.Terms]=None,
        host: typing.Optional['iocage.lib.Host.HostGenerator']=None,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None,
        zfs: typing.Optional['iocage.lib.ZFS.ZFS']=None
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)
        self.host = iocage.lib.helpers.init_host(self, host)

        iocage.lib.ListableResource.ListableResource.__init__(
            self,
            sources=self.host.datasets,
            namespace="jails",
            filters=filters,
            zfs=zfs,
            logger=logger
        )

    def _create_resource_instance(
        self,
        dataset: libzfs.ZFSDataset
    ) -> iocage.lib.Jail.JailGenerator:

        jail = self._class_jail(
            data=dict(id=dataset.name.split("/").pop()),
            root_datasets_name=self.sources.find_root_datasets_name(
                dataset.name
            ),
            logger=self.logger,
            host=self.host,
            zfs=self.zfs
        )

        if jail.identifier in self.states:
            self.logger.spam(
                f"Injecting pre-loaded state to '{jail.humanreadable_name}'"
            )
            jail.jail_state = self.states[jail.identifier]

        return jail

    def __iter__(
        self
    ) -> typing.Generator['iocage.lib.Resource.Resource', None, None]:
        """Iterate over all jails matching the filter criteria."""
        if self.states.queried is False:
            self.states.query(logger=self.logger)

        iterator = iocage.lib.ListableResource.ListableResource.__iter__(self)
        for jail in iterator:

            if jail.identifier in self.states:
                jail.state = self.states[jail.identifier]
            else:
                jail.state = iocage.lib.JailState.JailState(
                    jail.identifier, {}
                )

            yield jail


class Jails(JailsGenerator):
    """Synchronous wrapper ofs JailsGenerator."""

    _class_jail = iocage.lib.Jail.Jail
