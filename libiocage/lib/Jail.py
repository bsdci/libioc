import os
import subprocess
import uuid

import libiocage.lib.JailConfig
import libiocage.lib.Network
import libiocage.lib.NullFSBasejailStorage
import libiocage.lib.RCConf
import libiocage.lib.Release
import libiocage.lib.Releases
import libiocage.lib.StandaloneJailStorage
import libiocage.lib.Storage
import libiocage.lib.ZFSBasejailStorage
import libiocage.lib.ZFSShareStorage
import libiocage.lib.errors
import libiocage.lib.helpers


class Jail:
    """
    iocage unit orchestrates a jail's configuration and manages state

    Jails are represented as a zfs dataset `zpool/iocage/jails/<NAME>`

    Directory Structure:

        zpool/iocage/jails/<NAME>: The jail's dataset containing it's
            configuration and root dataset. iocage-legacy used to store
            a jails configuration as ZFS properties on this dataset. Even
            though the modern JSON config mechanism is preferred.

        zpool/iocage/jails/<NAME>/root: This directory is the dataset
            used as jail's root when starting a jail. Usually the clone source
            of a root dataset is a snapshot of the release's root dataset.

        zpool/iocage/jails/<NAME>/config.json: Jails configured with the latest
            configuration style store their information in a JSON file. When
            this file is found in the jail's dataset, libiocage assumes
            the jail to be a JSON-style jail and ignores other configuration
            mechanisms

        zpool/iocage/jails/<NAME>/config: Another compatible configuration
            mechanism is a UCL file. It's content is only taken into account if
            no JSON or ZFS configuration was found

    Jail Types:

        Standalone: The /root dataset gets cloned from a release at creation
            time. It it not affected by changes to the Release and persists all
            data within the jail

        NullFS Basejail: The fastest method to spawn a basejail by mounting
            read-only directories from the release's root dataset by creating
            a snapshot of the release on each boot of the jail. When a release
            is updated, the jail is updated as well on the next reboot. This
            type is the one used by the Python implementation of iocage.

        ZFS Basejail: Legacy basejails used to clone individual datasets from a
            release (stored in `zpool/iocage/base/<RELEASE>)
    """

    def __init__(self, data={}, zfs=None, host=None, logger=None, new=False):
        """
        Initializes a Jail

        Args:

            data (string|dict):
                Jail configuration dict or jail name as string identifier.

            zfs (libzfs.ZFS): (optional)
                Inherit an existing libzfs.ZFS() instance from ancestor classes

            host (libiocage.lib.Host): (optional)
                Inherit an existing Host instance from ancestor classes

            logger (libiocage.lib.Logger): (optional)
                Inherit an existing Logger instance from ancestor classes

        """

        libiocage.lib.helpers.init_logger(self, logger)
        libiocage.lib.helpers.init_zfs(self, zfs)
        libiocage.lib.helpers.init_host(self, host)

        if isinstance(data, str):
            data = {"id": self._resolve_name(data)}

        self.config = libiocage.lib.JailConfig.JailConfig(
            data=data,
            jail=self,
            logger=self.logger
        )

        self.networks = []

        self.storage = libiocage.lib.Storage.Storage(
            auto_create=True, safe_mode=False,
            jail=self, logger=self.logger, zfs=self.zfs)

        self.jail_state = None
        self._dataset_name = None
        self._rc_conf = None

        self.config.read()

    @property
    def zfs_pool_name(self):
        """
        Name of the ZFS pool the jail is stored on
        """
        return self.host.datasets.root.name.split("/", maxsplit=1)[0]

    @property
    def _rc_conf_path(self):
        """
        Absolute path to the jail's rc.conf file
        """
        return f"{self.path}/root/etc/rc.conf"

    @property
    def rc_conf(self):
        """
        The jail's libiocage.RCConf instance (lazy-loaded on first access)
        """
        if self._rc_conf is None:
            self._rc_conf = libiocage.lib.RCConf.RCConf(
                path=self._rc_conf_path,
                jail=self,
                logger=self.logger
            )
        return self._rc_conf

    def start(self):
        """
        Start the jail.
        """

        self.require_jail_existing()
        self.require_jail_stopped()

        release = self.release

        backend = None

        if self.config["basejail_type"] == "zfs":
            backend = libiocage.lib.ZFSBasejailStorage.ZFSBasejailStorage

        if self.config["basejail_type"] == "nullfs":
            backend = libiocage.lib.NullFSBasejailStorage.NullFSBasejailStorage

        if backend is not None:
            backend.apply(self.storage, release)

        self.config.fstab.read_file()
        self.config.fstab.save_with_basedirs()
        self._launch_jail()

        if self.config["vnet"]:
            self._start_vimage_network()
            self._configure_routes()

        self._configure_nameserver()

        if self.config["jail_zfs"] is True:
            libiocage.lib.ZFSShareStorage.ZFSShareStorage.mount_zfs_shares(
                self.storage
            )

    def stop(self, force=False):
        """
        Stop a jail.

        Args:

            force (bool): (default=False)
                Ignores failures and enforces teardown if True
        """

        if force is True:
            return self._force_stop()

        self.require_jail_existing()
        self.require_jail_running()
        self._destroy_jail()
        if self.config["vnet"]:
            self._stop_vimage_network()
        self._teardown_mounts()
        self.update_jail_state()

    def destroy(self, force=False):
        """
        Destroy a Jail and it's datasets

        Args:

            force (bool): (default=False)
                This flag enables whether an existing jail should be shut down
                before destroying the dataset. By default destroying a jail
                requires it to be stopped.
        """

        self.update_jail_state()

        if self.running is True and force is True:
            self.stop(force=True)
        else:
            self.require_jail_stopped()

        self.storage.delete_dataset_recursive(self.dataset)

    def _force_stop(self):

        successful = True

        try:
            self._destroy_jail()
            self.logger.debug(f"{self.humanreadable_name}: jail destroyed")
        except Exception as e:
            successful = False
            self.logger.warn(str(e))

        if self.config["vnet"]:
            try:
                self._stop_vimage_network()
                self.logger.debug(f"{self.humanreadable_name}: VNET stopped")
            except Exception as e:
                successful = False
                self.logger.warn(str(e))

        try:
            self._teardown_mounts()
            self.logger.debug(f"{self.humanreadable_name}: mounts destroyed")
        except Exception as e:
            successful = False
            self.logger.warn(str(e))

        try:
            self.update_jail_state()
        except Exception as e:
            successful = False
            self.logger.warn(str(e))

        return successful

    def create(self, release_name):
        """
        Create a Jail from a Release

        Args:

            release_name (string):
                The jail is created from the release matching the name provided
        """

        self.require_jail_not_existing()

        # check if release exists
        releases = libiocage.lib.Releases.Releases(
            host=self.host,
            zfs=self.zfs,
            logger=self.logger
        )

        filteres_released = list(filter(
            lambda x: x.name == release_name,
            releases.local
        ))

        if len(filteres_released) == 0:
            raise libiocage.lib.errors.ReleaseNotFetched(
                release_name,
                logger=self.logger
            )

        release = filteres_released[0]
        self.config["release"] = release.name

        if not self.config["id"]:
            self.config["name"] = str(uuid.uuid4())

        self.logger.verbose(
            f"Creating jail '{self.config['id']}'",
            jail=self
        )

        for key, value in self.config.data.items():
            msg = f"{key} = {value}"
            self.logger.spam(msg, jail=self, indent=1)

        self.storage.create_jail_dataset()
        self.config.fstab.update()

        backend = None

        is_basejail = self.config["type"] == "basejail"
        if not is_basejail:
            backend = libiocage.lib.StandaloneJailStorage.StandaloneJailStorage
        if is_basejail and self.config["basejail_type"] == "nullfs":
            backend = libiocage.lib.NullFSBasejailStorage.NullFSBasejailStorage
        elif is_basejail and self.config["basejail_type"] == "zfs":
            backend = libiocage.lib.ZFSBasejailStorage.ZFSBasejailStorage

        if backend is not None:
            backend.setup(self.storage, release)

        self.config.data["release"] = release.name
        self.config.save()

    def exec(self, command, **kwargs):
        """
        Execute a command in a started jail

        command (list):
            A list of command and it's arguments

            Example: ["/usr/bin/whoami"]
        """

        command = [
                      "/usr/sbin/jexec",
                      self.identifier
                  ] + command

        return libiocage.lib.helpers.exec(
            command,
            logger=self.logger,
            **kwargs
        )

    def passthru(self, command):
        """
        Execute a command in a started jail ans passthrough STDIN and STDOUT

        command (list):
            A list of command and it's arguments

            Example: ["/bin/sh"]
        """

        if isinstance(command, str):
            command = [command]

        return libiocage.lib.helpers.exec_passthru(
            [
                "/usr/sbin/jexec",
                self.identifier
            ] + command,
            logger=self.logger
        )

    def exec_console(self):
        """
        Shortcut to drop into a shell of a started jail
        """
        return self.passthru(
            ["/usr/bin/login"] + self.config["login_flags"]
        )

    def _destroy_jail(self):

        command = ["jail", "-r"]
        command.append(self.identifier)

        subprocess.check_output(
            command,
            shell=False,
            stderr=subprocess.DEVNULL
        )

    def _launch_jail(self):

        command = ["jail", "-c"]

        if self.config["vnet"]:
            command.append('vnet')
        else:

            if self.config["ip4_addr"] is not None:
                ip4_addr = self.config["ip4_addr"]
                command += [
                    f"ip4.addr={ip4_addr}",
                    f"ip4.saddrsel={self.config['ip4_saddrsel']}",
                    f"ip4={self.config['ip4']}",
                ]

            if self.config['ip6_addr'] is not None:
                ip6_addr = self.config['ip6_addr']
                command += [
                    f"ip6.addr={ip6_addr}",
                    f"ip6.saddrsel={self.config['ip6_saddrsel']}",
                    f"ip6={self.config['ip6']}",
                ]

        command += [
            f"name={self.identifier}",
            f"host.hostname={self.config['host_hostname']}",
            f"host.domainname={self.config['host_domainname']}",
            f"path={self.path}/root",
            f"securelevel={self.config['securelevel']}",
            f"host.hostuuid={self.name}",
            f"devfs_ruleset={self.config['devfs_ruleset']}",
            f"enforce_statfs={self.config['enforce_statfs']}",
            f"children.max={self.config['children_max']}",
            f"allow.set_hostname={self.config['allow_set_hostname']}",
            f"allow.sysvipc={self.config['allow_sysvipc']}"
        ]

        if self.host.userland_version > 10.3:
            command += [
                f"sysvmsg={self.config['sysvmsg']}",
                f"sysvsem={self.config['sysvsem']}",
                f"sysvshm={self.config['sysvshm']}"
            ]

        command += [
            f"allow.raw_sockets={self.config['allow_raw_sockets']}",
            f"allow.chflags={self.config['allow_chflags']}",
            f"allow.mount={self.config['allow_mount']}",
            f"allow.mount.devfs={self.config['allow_mount_devfs']}",
            f"allow.mount.nullfs={self.config['allow_mount_nullfs']}",
            f"allow.mount.procfs={self.config['allow_mount_procfs']}",
            f"allow.mount.zfs={self.config['allow_mount_zfs']}",
            f"allow.quotas={self.config['allow_quotas']}",
            f"allow.socket_af={self.config['allow_socket_af']}",
            f"exec.prestart={self.config['exec_prestart']}",
            f"exec.poststart={self.config['exec_poststart']}",
            f"exec.prestop={self.config['exec_prestop']}",
            f"exec.start={self.config['exec_start']}",
            f"exec.stop={self.config['exec_stop']}",
            f"exec.clean={self.config['exec_clean']}",
            f"exec.timeout={self.config['exec_timeout']}",
            f"stop.timeout={self.config['stop_timeout']}",
            f"mount.fstab={self.path}/fstab",
            f"mount.devfs={self.config['mount_devfs']}"
        ]

        if self.host.userland_version > 9.3:
            command += [
                f"mount.fdescfs={self.config['mount_fdescfs']}",
                f"allow.mount.tmpfs={self.config['allow_mount_tmpfs']}"
            ]

        command += [
            "allow.dying",
            f"exec.consolelog={self.logfile_path}",
            "persist"
        ]

        humanreadable_name = self.humanreadable_name
        try:
            libiocage.lib.helpers.exec(command, logger=self.logger)
            self.update_jail_state()
            self.logger.verbose(
                f"Jail '{humanreadable_name}' started with JID {self.jid}",
                jail=self
            )
        except subprocess.CalledProcessError as exc:
            code = exc.returncode
            self.logger.error(
                f"Jail '{humanreadable_name}' failed with exit code {code}",
                jail=self
            )
            raise

    def _start_vimage_network(self):

        self.logger.log("Starting VNET/VIMAGE", jail=self)

        nics = self.config["interfaces"]
        for nic in nics:

            bridges = list(self.config["interfaces"][nic])

            try:
                ipv4_addresses = self.config["ip4_addr"][nic]
            except:
                ipv4_addresses = []

            try:
                ipv6_addresses = self.config["ip6_addr"][nic]
            except:
                ipv6_addresses = []

            net = libiocage.lib.Network.Network(
                jail=self,
                nic=nic,
                ipv4_addresses=ipv4_addresses,
                ipv6_addresses=ipv6_addresses,
                bridges=bridges,
                logger=self.logger
            )
            net.setup()
            self.networks.append(net)

    def _stop_vimage_network(self):
        for network in self.networks:
            network.teardown()
            self.networks.remove(network)

    def _configure_nameserver(self):
        self.config["resolver"].apply(self)

    def _configure_routes(self):

        defaultrouter = self.config["defaultrouter"]
        defaultrouter6 = self.config["defaultrouter6"]

        if not defaultrouter or defaultrouter6:
            self.logger.spam("no static routes configured")
            return

        if defaultrouter:
            self.logger.verbose(
                f"setting default IPv4 gateway to {defaultrouter}",
                jail=self
            )
            self._configure_route(defaultrouter)

        if defaultrouter6:
            self._configure_route(defaultrouter6, ipv6=True)

    def _configure_route(self, gateway, ipv6=False):

        ip_version = 4 + 2 * (ipv6 is True)

        self.logger.verbose(
            f"setting default IPv{ip_version} gateway to {gateway}",
            jail=self
        )

        command = [
                      "/sbin/route",
                      "add"
                  ] + (["-6"] if (ipv6 is True) else []) + [
                      "default",
                      gateway
                  ]

        self.exec(command)

    def require_jail_not_existing(self):
        """
        Raise JailAlreadyExists exception if the jail already exists
        """
        if self.exists:
            raise libiocage.lib.errors.JailAlreadyExists(
                jail=self,
                logger=self.logger
            )

    def require_jail_existing(self):
        """
        Raise JailDoesNotExist exception if the jail does not exist
        """
        if not self.exists:
            raise libiocage.lib.errors.JailDoesNotExist(
                jail=self,
                logger=self.logger
            )

    def require_jail_stopped(self):
        """
        Raise JailAlreadyRunning exception if the jail is runninhg
        """
        if self.running:
            raise libiocage.lib.errors.JailAlreadyRunning(
                jail=self,
                logger=self.logger
            )

    def require_jail_running(self):
        """
        Raise JailNotRunning exception if the jail is stopped
        """
        if not self.running:
            raise libiocage.lib.errors.JailNotRunning(
                jail=self,
                logger=self.logger
            )

    def update_jail_state(self):
        """
        Invoke update of the jail state from jls output
        """
        try:
            import json
            stdout = subprocess.check_output([
                "/usr/sbin/jls",
                "-j",
                self.identifier,
                "-v",
                "-h",
                "--libxo=json"
            ], shell=False, stderr=subprocess.DEVNULL)
            output = stdout.decode().strip()

            self.jail_state = json.loads(output)["jail-information"]["jail"][0]

        except:
            self.jail_state = None

    def _teardown_mounts(self):

        mountpoints = list(map(
            lambda mountpoint: f"{self.path}/root{mountpoint}",
            [
                "/dev/fd",
                "/dev",
                "/proc",
                "/root/compat/linux/proc"
            ]
        ))

        mountpoints += list(map(lambda x: x["destination"],
                                list(self.config.fstab)))

        for mountpoint in mountpoints:
            if os.path.isdir(mountpoint):
                libiocage.lib.helpers.umount(
                    mountpoint,
                    force=True,
                    logger=self.logger,
                    ignore_error=True  # maybe it was not mounted
                )

    def _resolve_name(self, text):
        jails_dataset = self.host.datasets.jails
        best_guess = ""
        for dataset in list(jails_dataset.children):
            dataset_name = dataset.name[(len(jails_dataset.name) + 1):]
            if text == dataset_name:
                # Exact match, immediately return
                return dataset_name
            elif dataset_name.startswith(text) and len(text) > len(best_guess):
                best_guess = text

        if len(best_guess) > 0:
            self.logger.debug(f"Resolved {text} to uuid {dataset_name}")
            return best_guess

        if not best_guess:
            raise libiocage.lib.errors.JailNotSupplied(logger=self.logger)

        raise libiocage.lib.errors.JailNotFound(text, logger=self.logger)

    @property
    def name(self):
        """
        The name (formerly UUID) of the Jail
        """
        return self.config["id"]

    @property
    def humanreadable_name(self):
        """
        A human-readable identifier to print in logs and CLI output

        Whenever a Jail is found to have a UUID as identifier,
        a shortened string of the first 8 characters is returned
        """

        try:
            uuid.UUID(self.name)
            return str(self.name)[:8]
        except (TypeError, ValueError):
            pass

        try:
            return self.name
        except AttributeError:
            pass

        raise libiocage.lib.errors.JailUnknownIdentifier(logger=self.logger)

    @property
    def stopped(self):
        """
        Boolean value that is True if a jail is stopped
        """
        return self.running is not True

    @property
    def running(self):
        """
        Boolean value that is True if a jail is running
        """
        return self.jid is not None

    @property
    def jid(self):
        """
        The JID of a running jail or None if the jail is not running
        """
        try:
            return self.jail_state["jid"]
        except (TypeError, AttributeError, KeyError):
            pass

        try:
            self.update_jail_state()
            return self.jail_state["jid"]
        except (TypeError, AttributeError, KeyError):
            return None

    @property
    def identifier(self):
        """
        Used internally to identify jails (in snapshots, jls, etc)
        """
        return f"ioc-{self.config['id']}"

    @property
    def exists(self):
        """
        Boolean value that is True if the Jail datset exists locally
        """
        try:
            self.dataset
            return True
        except:
            return False

    @property
    def release(self):
        """
        The libiocage.Release instance linked with the jail
        """
        return libiocage.lib.Release.Release(
            name=self.config["release"],
            logger=self.logger,
            host=self.host,
            zfs=self.zfs
        )

    @property
    def dataset_name(self):
        """
        Name of the jail's base ZFS dataset
        """
        if self._dataset_name is not None:
            return self._dataset_name
        else:
            return f"{self.host.datasets.root.name}/jails/{self.config['id']}"

    @dataset_name.setter
    def dataset_name(self, value=None):
        self._dataset_name = value

    @property
    def dataset(self):
        """
        The jail's base ZFS dataset
        """
        return self.zfs.get_dataset(self.dataset_name)

    @property
    def path(self):
        """
        Mountpoint of the jail's base ZFS dataset
        """
        return self.dataset.mountpoint

    @property
    def logfile_path(self):
        """
        Absolute path of the jail log file
        """
        return f"{self.host.datasets.logs.mountpoint}-console.log"

    def __getattr__(self, key):

        try:
            return object.__getattribute__(self, key)
        except AttributeError:
            pass

        try:
            method = object.__getattribute__(self, f"_get_{key}")
            return method()
        except:
            pass

        try:
            jail_state = object.__getattribute__(self, "jail_state")
        except:
            jail_state = None
            raise

        if jail_state is not None:
            try:
                return jail_state[key]
            except:
                pass

        raise AttributeError(f"Jail property {key} not found")

    def getstring(self, key):
        """
        Returns a jail properties string or '-'

        Args:
            key (string):
                Name of the jail property to return
        """
        try:
            if key == "jid" and self.__getattr__(key) is None:
                return "-"

            return str(self.__getattr__(key))
        except AttributeError:
            return "-"

    def __dir__(self):

        properties = set()

        for prop in dict.__dir__(self):
            if prop.startswith("_get_"):
                properties.add(prop[5:])
            elif not prop.startswith("_"):
                properties.add(prop)

        return list(properties)
