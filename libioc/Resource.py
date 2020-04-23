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
"""ioc Resource module."""
import typing
import os.path
import abc

import libzfs

import libioc.Config
import libioc.Config.Jail.Defaults
import libioc.Config.Type.JSON
import libioc.Config.Type.UCL
import libioc.Config.Type.ZFS
import libioc.Logger
import libioc.Types
import libioc.ZFS
import libioc.helpers
import libioc.helpers_object


class Resource(metaclass=abc.ABCMeta):
    """
    Representation of an iocage resource.

    An iocage resource is the representation of a jail, release or base release

    File Structure:

        <ZFSDataset>/root:

            This dataset contains the root filesystem of a jail or release.

            In case of a ZFS basejail resource it hosts a tree of child
            datasets that may be cloned into an existing target dataset.

        <ZFSDataset>/config.json:

            The resource configuration in JSON format

        <ZFSDataset>/config:

            The resource configuration in ucl format used by former versions
            of iocage

        <ZFSDataset>.properties:

            iocage legacy used to store resource configuration in ZFS
            properties on the resource dataset

    """

    CONFIG_TYPES = (
        "json",
        "ucl",
        "zfs",
        "auto"
    )

    DEFAULT_JSON_FILE = "config.json"
    DEFAULT_UCL_FILE = "config"
    DEFAULT_ZFS_DATASET_SUFFIX: typing.Optional[str] = None

    _config_type: typing.Optional[int] = None
    _config_file: typing.Optional[str] = None
    _dataset: libzfs.ZFSDataset
    _dataset_name: str

    _config_json: libioc.Config.Type.JSON.DatasetConfigJSON
    _config_ucl: libioc.Config.Type.UCL.DatasetConfigUCL
    _config_zfs: libioc.Config.Type.ZFS.DatasetConfigZFS

    def __init__(
        self,
        dataset: typing.Optional[libzfs.ZFSDataset]=None,
        dataset_name: typing.Optional[str]=None,
        config_type: str="auto",
        config_file: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        zfs: typing.Optional['libioc.ZFS.ZFS']=None
    ) -> None:

        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)

        self._config_file = config_file
        self.config_type = config_type

        if dataset_name is not None:
            self.dataset_name = dataset_name
        elif dataset is not None:
            self.dataset = dataset

    @property
    def config_json(self) -> 'libioc.Config.Type.JSON.DatasetConfigJSON':
        """Return and memoize the resources JSON config handler."""
        if "_config_json" in self.__dir__():
            return self._config_json
        default = self.DEFAULT_JSON_FILE
        file = self._config_file if self._config_file is not None else default
        self._config_json = libioc.Config.Type.JSON.DatasetConfigJSON(
            file=file,
            dataset=self.dataset,
            logger=self.logger
        )
        return self._config_json

    @property
    def config_ucl(self) -> 'libioc.Config.Type.UCL.DatasetConfigUCL':
        """Return and memoize the resources UCL config handler."""
        if "_config_ucl" in self.__dir__():
            return self._config_ucl
        default = self.DEFAULT_UCL_FILE
        file = self._config_file if self._config_file is not None else default
        self._config_ucl = libioc.Config.Type.UCL.DatasetConfigUCL(
            file=file,
            dataset=self.dataset,
            logger=self.logger
        )
        return self._config_ucl

    @property
    def config_zfs(self) -> 'libioc.Config.Type.ZFS.DatasetConfigZFS':
        """Return and memoize the resources ZFS property config handler."""
        if "_config_zfs" in self.__dir__():
            return self._config_zfs
        if self.DEFAULT_ZFS_DATASET_SUFFIX is not None:
            name = f"{self.dataset.name}{self.DEFAULT_ZFS_DATASET_SUFFIX}"
            dataset = self.zfs.get_or_create_dataset(name)
        else:
            dataset = self.dataset

        self._config_zfs = libioc.Config.Type.ZFS.DatasetConfigZFS(
            dataset=dataset,
            logger=self.logger
        )
        return self._config_zfs

    @abc.abstractmethod
    def destroy(
        self,
        force: bool=False
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Destroy the resource."""
        pass

    @property
    def pool(self) -> libzfs.ZFSPool:
        """Return the ZFSPool of the resources dataset."""
        zpool: libzfs.ZFSPool = self.zfs.get_pool(self.dataset_name)
        return zpool

    @property
    def pool_name(self) -> str:
        """Return the name of the ZFSPool of the resources dataset."""
        return str(self.pool.name)

    @property
    def exists(self) -> bool:
        """Return True if the resource exists on the filesystem."""
        try:
            mountpoint = self.dataset.mountpoint
            if isinstance(mountpoint, str):
                return os.path.isdir(mountpoint)
        except (AttributeError, libzfs.ZFSException):
            pass
        return False

    @property
    def _assigned_dataset_name(self) -> str:
        """Name of the jail's base ZFS dataset that was manually assigned."""
        try:
            return str(self._dataset_name)
        except AttributeError:
            pass

        try:
            return str(self._dataset.name)
        except AttributeError:
            pass

        raise AttributeError("Could not determine dataset_name")

    @property
    def dataset_name(self) -> str:
        """Return the name of the resources dataset."""
        return self._assigned_dataset_name

    @dataset_name.setter
    def dataset_name(self, value: str) -> None:
        """Set the name of the resources dataset."""
        self._dataset_name = value

    @property
    def dataset(self) -> libzfs.ZFSDataset:
        """Return the resources dataset."""
        try:
            return self._dataset
        except AttributeError:
            pass

        name = self.dataset_name
        dataset: libzfs.ZFSDataset = self.zfs.get_dataset(name)
        self._dataset = dataset
        return dataset

    @dataset.setter
    def dataset(self, value: libzfs.ZFSDataset) -> None:
        """Set the resources dataset."""
        self._set_dataset(value)

    def _set_dataset(self, value: libzfs.ZFSDataset) -> None:
        try:
            del self._dataset_name
        except AttributeError:
            pass
        self._dataset = value

    @property
    def config_type(self) -> typing.Optional[str]:
        """Return the resources config type (JSON, UCL or ZFS)."""
        if self._config_type is None:
            return None
        elif self._config_type == self.CONFIG_TYPES.index("auto"):
            self._config_type = self._detect_config_type()
        return self.CONFIG_TYPES[self._config_type]

    @config_type.setter
    def config_type(self, value: typing.Optional[int]) -> None:
        """Set the resources config type enum index (JSON, UCL or ZFS)."""
        if value is None:
            self._config_type = None
        else:
            self._config_type = self.CONFIG_TYPES.index(value)

    def _detect_config_type(self) -> int:

        if self.config_json.exists is True:
            return self.CONFIG_TYPES.index("json")

        if self.config_ucl.exists is True:
            return self.CONFIG_TYPES.index("ucl")

        if self.config_zfs.exists is True:
            return self.CONFIG_TYPES.index("zfs")

        return 0

    @property
    def config_file(self) -> typing.Optional[str]:
        """Return the relative path of the resource config file."""
        if self._config_type is None:
            return None

        elif self._config_file is not None:
            return self._config_file

        elif self.config_type == "json":
            return self.DEFAULT_JSON_FILE

        elif self.config_type == "ucl":
            return self.DEFAULT_UCL_FILE

        return None

    @config_file.setter
    def config_file(self, value: str) -> None:
        """Set the relative path of the resources config file."""
        self._config_file = value

    def create_resource(self) -> None:
        """Create the dataset."""
        self.dataset = self.zfs.create_dataset(self.dataset_name)
        os.chmod(self.dataset.mountpoint, 0o700)

    def get_dataset(self, name: str) -> libzfs.ZFSDataset:
        """Get the ZFSDataset relative to the resource datasets name."""
        dataset_name = f"{self.dataset_name}/{name}"
        dataset: libzfs.ZFSDataset = self.zfs.get_dataset(dataset_name)
        return dataset

    def get_or_create_dataset(
        self,
        name: str
    ) -> libzfs.ZFSDataset:
        """
        Get or create a child dataset.

        Returns:
            libzfs.ZFSDataset:
                Existing or newly created ZFS Dataset

        """
        dataset_name = f"{self.dataset_name}/{name}"
        dataset: libzfs.ZFSDataset = self.zfs.get_or_create_dataset(
            dataset_name
        )
        return dataset

    def abspath(self, relative_path: str) -> str:
        """Return the absolute path of a path relative to the resource."""
        return str(os.path.join(self.dataset.mountpoint, relative_path))

    def _write_config(self, data: libioc.Config.Data.Data) -> None:
        """Write the configuration to disk."""
        self.config_handler.write(data)

    def read_config(
        self,
        skip_invalid: bool=False
    ) -> typing.Dict[str, typing.Any]:
        """Read the configuration from disk."""
        data = self.config_handler.read()  # type: typing.Dict[str, typing.Any]
        return data

    @property
    def config_handler(self) -> 'libioc.Config.Prototype.Prototype':
        """Return the config handler according to the detected config_type."""
        handler = object.__getattribute__(self, f"config_{self.config_type}")
        return handler

    def get(self, key: str) -> typing.Any:
        """Get any resource attribute."""
        return self.__getattribute__(key)

    def getstring(self, key: str) -> str:
        """
        Get any resource property as string or '-'.

        Args:
            key (string):
                Name of the jail property to return
        """
        value = self.get(key)
        return str(libioc.helpers.to_string(
            value,
            none="-"
        ))

    def save(self) -> None:
        """Save changes - a placeholder for implementing class."""
        raise NotImplementedError(
            "This needs to be implemented by the inheriting class"
        )

    def require_relative_path(
        self,
        filepath: str,
    ) -> None:
        """Raise an error when the path is not relative to the resource."""
        if self.is_path_relative(filepath) is False:
            raise libioc.errors.SecurityViolationConfigJailEscape(
                file=filepath
            )

    def is_path_relative(
        self,
        filepath: str
    ) -> bool:
        """Return whether the path is relative to the resource."""
        real_resource_path = self._resolve_path(self.dataset.mountpoint)
        real_file_path = self._resolve_path(filepath)

        return real_file_path.startswith(real_resource_path)

    def _resolve_path(self, filepath: str) -> str:
        return os.path.realpath(os.path.abspath(filepath))


class DefaultResource(Resource):
    """The resource storing the default configuration."""

    DEFAULT_JSON_FILE = "defaults.json"
    DEFAULT_UCL_FILE = "defaults"
    DEFAULT_ZFS_DATASET_SUFFIX = "/.defaults"

    def __init__(
        self,
        dataset: typing.Optional[libzfs.ZFSDataset]=None,
        dataset_name: typing.Optional[str]=None,
        config_type: str="auto",
        config_file: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        zfs: typing.Optional['libioc.ZFS.ZFS']=None,
    ) -> None:

        Resource.__init__(
            self,
            dataset=dataset,
            dataset_name=dataset_name,
            config_type=config_type,
            config_file=config_file,
            logger=logger,
            zfs=zfs,
        )

        self.config = libioc.Config.Jail.Defaults.JailConfigDefaults(
            logger=logger
        )

    def read_config(
        self,
        skip_invalid: bool=False
    ) -> typing.Dict[str, typing.Any]:
        """Read the default configuration."""
        o = Resource.read_config(self)
        self.config.clone(o)
        return o

    def destroy(
        self,
        force: bool=False
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Cannot destroy the default resource."""
        raise NotImplementedError("destroy unimplemented for DefaultResource")

    def save(self) -> None:
        """Save changes to the default configuration."""
        self._write_config(self.config.user_data)
