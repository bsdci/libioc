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
import libzfs

import iocage.lib.Jail
import iocage.lib.Filter
import iocage.lib.Resource
import iocage.lib.helpers


class JailsGenerator(iocage.lib.Resource.ListableResource):

    _class_jail = iocage.lib.Jail.JailGenerator

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
        filters: iocage.lib.Filter.Terms=None,
        host=None,
        logger=None,
        zfs=None
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)
        self.host = iocage.lib.helpers.init_host(self, host)

        iocage.lib.Resource.ListableResource.__init__(
            self,
            dataset=self.host.datasets.jails,
            filters=filters
        )

    def _create_resource_instance(
        self,
        dataset: libzfs.ZFSDataset,
        *args,
        **kwargs
    ) -> iocage.lib.Jail.JailGenerator:

        kwargs["data"] = {
            "id": dataset.name.split("/").pop()
        }
        kwargs["dataset"] = dataset
        kwargs["logger"] = self.logger
        kwargs["host"] = self.host
        kwargs["zfs"] = self.zfs
        jail = self._class_jail(*args, **kwargs)
        return jail


class Jails(JailsGenerator):

    _class_jail = iocage.lib.Jail.Jail
