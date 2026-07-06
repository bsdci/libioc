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
"""ioc configuration stored in ZFS properties."""
import typing
import libzfs

import libioc.Config.Prototype
import libioc.Config.Dataset
import libioc.Resource
import libioc.errors


ZFS_PROPERTY_PREFIX = "org.freebsd.iocage:"


def is_iocage_property(name: str) -> bool:
    """Determine if a property name is prefixed as iocage configuration."""
    return name.startswith(ZFS_PROPERTY_PREFIX)


def get_iocage_property_name(zfs_property_name: str) -> str:
    """Determine if a ZFS property is an iocage configuration property."""
    if is_iocage_property(zfs_property_name) is False:
        raise libioc.errors.NotAnIocageZFSProperty(
            property_name=zfs_property_name
        )
    return zfs_property_name[len(ZFS_PROPERTY_PREFIX):]


class BaseConfigZFS(libioc.Config.Dataset.DatasetConfig):
    """ioc configuration stored in ZFS properties."""

    config_type = "zfs"

    def read(self) -> dict:
        """Read the configuration from the ZFS dataset."""
        try:
            data = self.map_input(self._read_properties())
            data["legacy"] = True
            return dict(data)
        except AttributeError:
            return {
                "legacy": True
            }

    def write(self, data: dict) -> None:
        """Write changes to ZFS properties of the dataset."""
        output_data = {}
        for key, value in data.items():
            output_data[key] = self._to_string(value)

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

    def map_input(
        self,
        data: typing.Dict[str, str]
    ) -> libioc.Config.Data.Data:
        """Normalize data read from ZFS properties."""
        parse_user_input = libioc.helpers.parse_user_input
        return libioc.Config.Data.Data(
            dict([(x, parse_user_input(y)) for (x, y) in data.items()])
        )

    def _to_string(
        self,
        value: typing.Union[
            str,
            bool,
            int,
            None,
            typing.List[typing.Union[str, bool, int]]
        ]
    ) -> str:
        """Transform config data to iocage_legacy compatible values."""
        return str(libioc.helpers.to_string(
            value,
            true="on",
            false="off",
            none="none"
        ))

    @property
    def exists(self) -> bool:
        """Signal if iocage ZFS configuration properties were found."""
        if self.dataset is None:
            return False
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


class DatasetConfigZFS(BaseConfigZFS):
    """ioc ZFS jail configuration for legacy support."""

    def __init__(
        self,
        dataset: libzfs.ZFSDataset,
        file: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        self._dataset = dataset
        libioc.Config.Dataset.DatasetConfig.__init__(
            self,
            file=file,
            logger=logger
        )

    @property
    def dataset(self) -> libzfs.ZFSDataset:
        """Shortcut to the config dataset."""
        return self._dataset
