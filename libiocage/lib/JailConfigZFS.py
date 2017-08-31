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

import libiocage.lib.errors


class JailConfigZFS:
    property_prefix = "org.freebsd.iocage:"

    def read(self):

        data = {}

        for prop in self.jail.dataset.properties:
            if JailConfigZFS._is_iocage_property(self, prop):
                name = JailConfigZFS._get_iocage_property_name(self, prop)
                data[name] = self.jail.dataset.properties[prop].value

        self.clone(data, skip_on_error=True)

        if not self.exists:
            raise libiocage.lib.errors.JailConfigNotFound("ZFS")

        if self.data["basejail"] == "on":
            self.data["basejail"] = "on"
            self.data["basejail_type"] = "zfs"
            self.data["clonejail"] = "off"
        else:
            self.data["basejail"] = "off"
            self.data["clonejail"] = "off"

    def exists(self):

        for prop in self.jail.dataset.properties:
            if JailConfigZFS._is_iocage_property(self, prop):
                return True

        return False

    def save(self):

        # ToDo: Delete unnecessary ZFS options
        # existing_property_names = list(
        #   map(lambda x: JailConfigZFS._get_iocage_property_name(self, x),
        #     filter(
        #       lambda name: JailConfigZFS._is_iocage_property(self, name),
        #       self.jail.dataset.properties
        #     )
        #   )
        # )
        # data_keys = list(self.data)
        # for existing_property_name in existing_property_names:
        #   if not existing_property_name in data_keys:
        #     pass

        for zfs_property_name in self.data:
            zfs_property = libzfs.ZFSUserProperty(
                str(self.data[zfs_property_name])
            )
            self.jail.dataset.property[zfs_property_name] = zfs_property

    def _is_iocage_property(self, name):
        return name.startswith(JailConfigZFS.property_prefix)

    def _get_iocage_property_name(self, zfs_property_name):
        return zfs_property_name[len(JailConfigZFS.property_prefix):]
