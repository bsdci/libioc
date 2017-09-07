import os.path

import libzfs

import libiocage.lib.ConfigJSON
import libiocage.lib.ConfigUCL
import libiocage.lib.ConfigZFS
import libiocage.lib.Fstab
import libiocage.lib.RCConf
import libiocage.lib.Jail
import libiocage.lib.Logger
import libiocage.lib.ZFS
import libiocage.lib.Release
import libiocage.lib.helpers


class Resource:
    """
    iocage resource

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

    _dataset_name: str = None
    _config_type: int = None
    _config_file: str = None
    _dataset: libzfs.ZFSDataset = None

    def __init__(
        self,
        dataset: libzfs.ZFSDataset=None,
        dataset_name: str=None,
        config_type: str="auto",  # auto, json, zfs, ucl
        config_file: str=None,  # 'config.json', 'config', etc
        logger: 'libiocage.lib.Logger.Logger'=None,
        zfs: 'libiocage.lib.ZFS.ZFS'=None
    ) -> None:

        self.logger = libiocage.lib.helpers.init_logger(self, logger)
        self.zfs = libiocage.lib.helpers.init_zfs(self, zfs)

        self.config_json = libiocage.lib.ConfigJSON.ResourceConfigJSON(
            resource=self,
            logger=self.logger
        )

        self.config_ucl = libiocage.lib.ConfigUCL.ResourceConfigUCL(
            resource=self,
            logger=self.logger
        )

        self.config_zfs = libiocage.lib.ConfigZFS.ResourceConfigZFS(
            resource=self,
            logger=self.logger
        )

        self._config_file = config_file
        self.config_type = config_type

        if dataset_name is not None:
            self.dataset_name = dataset_name
        elif dataset is not None:
            self.dataset = dataset

    @property
    def pool_name(self) -> str:
        return self.zfs.get_pool(self.dataset_name).name

    @property
    def exists(self) -> bool:
        try:
            return os.path.isdir(self.dataset.mountpoint)
        except:
            return False

    @property
    def _assigned_dataset_name(self) -> str:
        """
        Name of the jail's base ZFS dataset manually assigned to this resource
        """
        if self._dataset_name is not None:
            return self._dataset_name
        else:
            return self._dataset.name

    @property
    def dataset_name(self) -> str:
        return self._assigned_dataset_name

    @dataset_name.setter
    def dataset_name(self, value: str):
        self._dataset_name = value

    @property
    def dataset(self) -> libzfs.ZFSDataset:
        """
        The jail's base ZFS dataset
        """
        if self._dataset_name is not None:
            # sets self._dataset_name to None and memoize the dataset
            self._dataset = self.zfs.get_dataset(self.dataset_name)

        return self._dataset

    @dataset.setter
    def dataset(self, value: libzfs.ZFSDataset):
        self._set_dataset(value)

    def _set_dataset(self, value) -> None:
        self._dataset_name = None
        self._dataset = value

    # @property
    # def path(self):
    #     """
    #     Mountpoint of the jail's base ZFS dataset
    #     """
    #     return self.dataset.mountpoint

    @property
    def config_type(self) -> str:
        if self._config_type is None:
            return None
        elif self._config_type == self.CONFIG_TYPES.index("auto"):
            self._config_type = self._find_config_type()
        return self.CONFIG_TYPES[self._config_type]

    @config_type.setter
    def config_type(self, value: str):
        if value is None:
            self._config_type = None
        else:
            self._config_type = self.CONFIG_TYPES.index(value)

    def _find_config_type(self) -> int:

        if self.config_json.exists:
            return self.CONFIG_TYPES.index("json")

        if self.config_ucl.exists:
            return self.CONFIG_TYPES.index("ucl")

        if self.config_zfs.exists:
            return self.CONFIG_TYPES.index("zfs")

        return 0

    @property
    def config_file(self) -> str:
        """
        Relative path of the resource config file
        """
        if self.config_type is None:
            return None

        elif self._config_file is not None:
            return self._config_file

        elif self.config_type == "json":
            return self.DEFAULT_JSON_FILE

        elif self.config_type == "ucl":
            return self.DEFAULT_UCL_FILE

        return None

    def create_resource(self) -> None:
        """
        Creates the dataset
        """
        self.dataset = self.zfs.create_dataset(self.dataset_name)

    def get_dataset(self, name: str) -> libzfs.ZFSDataset:
        dataset_name = f"{self.dataset_name}/{name}"
        return self.zfs.get_dataset(dataset_name)

    def get_or_create_dataset(self, name: str, **kwargs) -> libzfs.ZFSDataset:
        dataset_name = f"{self.dataset_name}/{name}"
        return self.zfs.get_or_create_dataset(dataset_name, **kwargs)

    def abspath(self, relative_path: str) -> str:
        return os.path.join(self.dataset.mountpoint, relative_path)

    def write_config(self, data: dict):
        return self.config_handler.write(data)

    def read_config(self) -> dict:
        return self.config_handler.read()

    @property
    def config_handler(self):

        handler = object.__getattribute__(self, f"config_{self.config_type}")
        return handler


class DefaultResource(Resource):

    DEFAULT_JSON_FILE = "defaults.json"
    DEFAULT_UCL_FILE = "defaults"

    DEFAULTS = {
        "id": None,
        "release": None,
        "boot": False,
        "legacy": False,
        "priority": 0,
        "basejail": False,
        "clonejail": True,
        "defaultrouter": None,
        "defaultrouter6": None,
        "mac_prefix": "02ff60",
        "vnet": False,
        "ip4": "new",
        "ip4_saddrsel": 1,
        "ip6": "new",
        "ip6_saddrsel": 1,
        "resolver": "/etc/resolv.conf",
        "host_domainname": "none",
        "devfs_ruleset": 4,
        "enforce_statfs": 2,
        "children_max": 0,
        "allow_set_hostname": 1,
        "allow_sysvipc": 0,
        "allow_raw_sockets": 0,
        "allow_chflags": 0,
        "allow_mount": 0,
        "allow_mount_devfs": 0,
        "allow_mount_nullfs": 0,
        "allow_mount_procfs": 0,
        "allow_mount_zfs": 0,
        "allow_mount_tmpfs": 0,
        "allow_quotas": 0,
        "allow_socket_af": 0,
        "sysvmsg": "new",
        "sysvsem": "new",
        "sysvshm": "new",
        "exec_clean": 1,
        "exec_fib": 1,
        "exec_prestart": "/usr/bin/true",
        "exec_start": "/bin/sh /etc/rc",
        "exec_poststart": "/usr/bin/true",
        "exec_prestop": "/usr/bin/true",
        "exec_stop": "/bin/sh /etc/rc.shutdown",
        "exec_poststop": "/usr/bin/true",
        "exec_timeout": "60",
        "stop_timeout": "30",
        "mount_devfs": "1",
        "mount_fdescfs": "1",
        "securelevel": "2",
        "tags": []
    }

    def read_config(self) -> dict:
        defaults = self.config_handler.read()
        user_defaults_keys = defaults.keys()

        for key, value in self.DEFAULTS.items():
            if key not in user_defaults_keys:
                defaults[key] = value

        return defaults


class LaunchableResource(Resource):

    _rc_conf: libiocage.lib.RCConf.RCConf = None

    def create_resource(self) -> None:
        """
        Creates the root dataset
        """
        Resource.create_resource(self)
        self.zfs.create_dataset(self.root_dataset_name)

    @property
    def root_path(self):
        return self.root_dataset.mountpoint

    @property
    def root_dataset(self) -> libzfs.ZFSDataset:
        # ToDo: Memoize root_dataset
        return self.get_dataset("root")

    @property
    def root_dataset_name(self) -> str:
        return f"{self.dataset_name}/root"

    @property
    def dataset_name(self) -> str:
        raise NotImplementedError(
            "This needs to be implemented by the inheriting class"
        )

    @dataset_name.setter
    def dataset_name(self, value: str) -> str:
        raise NotImplementedError(
            "This needs to be implemented by the inheriting class"
        )

    @property
    def dataset(self) -> libzfs.ZFSDataset:
        if self._dataset is None:
            self._dataset = self.zfs.get_dataset(self.dataset_name)

        return self._dataset

    @dataset.setter
    def dataset(self, value: libzfs.ZFSDataset):
        self._set_dataset(value)

    @property
    def rc_conf(self) -> libiocage.lib.RCConf.RCConf:
        if self._rc_conf is None:
            self._rc_conf = libiocage.lib.RCConf.RCConf(
                resource=self,
                logger=self.logger
            )
        return self._rc_conf


class JailResource(LaunchableResource):

    _jail: 'libiocage.lib.Jail.JailGenerator' = None
    _fstab: libiocage.lib.Fstab.Fstab = None

    def __init__(
        self,
        host: 'libiocage.lib.Host.HostGenerator',
        jail: 'libiocage.lib.Jail.JailGenerator'=None,
        **kwargs
    ) -> None:

        self.__jails_dataset_name = host.datasets.jails.name
        self.host = libiocage.lib.helpers.init_host(self, host)

        self._jail = jail

        Resource.__init__(
            self,
            **kwargs
        )

    @property
    def jail(self) -> 'libiocage.lib.Jail.JailGenerator':
        """
        Jail instance that belongs to the resource

        Usually the resource becomes inherited from the jail itself.
        It can still be used linked to a foreign jail by passing jail as
        named attribute to the __init__ function
        """
        if self._jail is not None:
            return self._jail

        elif isinstance(self, libiocage.lib.Jail.JailGenerator):
            return self

        raise Exception(
            "Resource is not a valid jail itself and has no linked jail"
        )

    @property
    def fstab(self) -> libiocage.lib.Fstab.Fstab:
        if self._fstab is None:
            self._fstab = libiocage.lib.Fstab.Fstab(
                jail=self.jail,
                release=self.jail.release,
                logger=self.logger,
                host=self.jail.host
            )
        return self._fstab

    @property
    def dataset_name(self) -> str:
        """
        Name of the jail base ZFS dataset

        If the resource has no dataset or dataset_name assigned yet,
        the jail id is used to find name the dataset
        """
        try:
            return self._assigned_dataset_name
        except:
            pass

        jail_id = self.jail.config["id"]
        if jail_id is None:
            raise libiocage.lib.errors.JailUnknownIdentifier()

        return f"{self.__jails_dataset_name}/{jail_id}"

    @dataset_name.setter
    def dataset_name(self, value: str):
        self._dataset_name = value


class ReleaseResource(LaunchableResource):

    _release: 'libiocage.lib.Release.ReleaseGenerator' = None

    def __init__(
        self,
        host: 'libiocage.lib.Host.HostGenerator',
        release: 'libiocage.lib.Release.ReleaseGenerator'=None,
        **kwargs
    ) -> None:

        self.__releases_dataset_name = host.datasets.releases.name
        self.__base_dataset_name = host.datasets.base.name
        self.host = libiocage.lib.helpers.init_host(self, host)

        Resource.__init__(
            self,
            **kwargs
        )

        self._release = release

    @property
    def release(self) -> 'libiocage.lib.Release.ReleaseGenerator':
        """
        Release instance that belongs to the resource

        Usually the resource becomes inherited from the Release itself.
        It can still be used linked to a foreign ReleaseGenerator by passing
        release as named attribute to the __init__ function
        """
        if self._release is not None:
            return self._release

        elif isinstance(self, libiocage.lib.Release.ReleaseGenerator):
            return self

        raise Exception(
            "Resource is not a valid release itself and has no linked release"
        )

    @property
    def dataset_name(self) -> str:
        """
        Name of the release base ZFS dataset

        If the resource has no dataset or dataset_name assigned yet,
        the release id is used to find name the dataset
        """
        try:
            return self._assigned_dataset_name
        except:
            pass

        return f"{self.__releases_dataset_name}/{self.release.name}"

    @dataset_name.setter
    def dataset_name(self, value: str):
        self._dataset_name = value

    @property
    def base_dataset(self) -> libzfs.ZFSDataset:
        # base datasets are created from releases. required to start
        # zfs-basejails
        return self.zfs.get_dataset(self.base_dataset_name)

    @property
    def base_dataset_name(self) -> str:
        return f"{self.__base_dataset_name}/{self.release.name}/root"
