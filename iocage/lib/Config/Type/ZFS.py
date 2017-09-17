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

import iocage.lib.Config.Dataset
import iocage.lib.Resource
import iocage.lib.errors


ZFS_PROPERTY_PREFIX = "org.freebsd.iocage:"


def is_iocage_property(name):

    return name.startswith(ZFS_PROPERTY_PREFIX)


def get_iocage_property_name(zfs_property_name):

    if is_iocage_property(zfs_property_name) is False:
        raise iocage.lib.errors.NotAnIocageZFSProperty(
            property_name=zfs_property_name
        )

    return zfs_property_name[len(ZFS_PROPERTY_PREFIX):]


class BaseConfigZFS(iocage.lib.Config.Dataset.DatasetConfig):

    config_type = "zfs"

    def read(self) -> dict:
        try:
            return self.map_input(self._read_properties())
        except:
            return {}

    def write(self, data: dict):
        """
        Writes changes to the config file
        """
        output_data = self.map_output(data)

        # ToDo: Delete unnecessary ZFS options
        # existing_property_names = list(
        #   map(lambda x: get_iocage_property_name(x),
        #     filter(
        #       lambda name: is_iocage_property(name),
        #       self.jail.dataset.properties
        #     )
        #   )
        # )
        # data_keys = list(self.data)
        # for existing_property_name in existing_property_names:
        #   if not existing_property_name in data_keys:
        #     pass

        for key, value in output_data.items():
            prop_name = f"{ZFS_PROPERTY_PREFIX}{key}"
            prop = libzfs.ZFSUserProperty(
                self._to_string(value)
            )
            self.dataset.properties[prop_name] = prop

    def map_input(self, data: dict) -> dict:
        parse_user_input = iocage.lib.helpers.parse_user_input
        return dict([(x, parse_user_input(y)) for (x, y) in data.items()])

    def map_output(self, data: dict) -> dict:
        output = {}
        for key, value in data.items():
            output[key] = self._to_string(value)
        return output

    def _to_string(self, value) -> str:
        return iocage.lib.helpers.to_string(
            value,
            true="on",
            false="off",
            none="none"
        )

    @property
    def exists(self) -> bool:
        """
        Returns True, when this configuration was found in the dataset
        """
        for prop in self.dataset.properties:
            if is_iocage_property(prop):
                return True

        return False

    def _read_properties(self) -> dict:
        data = {}
        for prop in self.dataset.properties:
            if is_iocage_property(prop):
                name = get_iocage_property_name(prop)
                data[name] = self.dataset.properties[prop].value
        return data


class ConfigZFS(BaseConfigZFS):

    def __init__(
        self,
        dataset: libzfs.ZFSDataset,
        **kwargs
    ) -> None:

        self._dataset = dataset
        BaseConfigZFS.__init__(self, **kwargs)

    @property
    def dataset(self) -> libzfs.ZFSDataset:
        return self._dataset


class ResourceConfigZFS(BaseConfigZFS):

    def __init__(
        self,
        resource: 'iocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        self.resource = resource
        BaseConfigZFS.__init__(self, **kwargs)

    @property
    def dataset(self) -> libzfs.ZFSDataset:
        return self.resource.dataset
