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
import typing
import os
import subprocess
import uuid

import libiocage.lib.DevfsRules
import libiocage.lib.Host
import libiocage.lib.JailConfig
import libiocage.lib.Network
import libiocage.lib.NullFSBasejailStorage
import libiocage.lib.RCConf
import libiocage.lib.Release
import libiocage.lib.StandaloneJailStorage
import libiocage.lib.Storage
import libiocage.lib.ZFSBasejailStorage
import libiocage.lib.ZFSShareStorage
import libiocage.lib.LaunchableResource
import libiocage.lib.Fstab
import libiocage.lib.errors
import libiocage.lib.events
import libiocage.lib.helpers


class JailResource(libiocage.lib.LaunchableResource.LaunchableResource):

    _jail: 'JailGenerator' = None
    _fstab: 'libiocage.lib.Fstab.Fstab' = None

    def __init__(
        self,
        host: 'libiocage.lib.Host.HostGenerator',
        jail: 'JailGenerator'=None,
        **kwargs
    ) -> None:

        self.__jails_dataset_name = host.datasets.jails.name
        self.host = libiocage.lib.helpers.init_host(self, host)

        self._jail = jail

        libiocage.lib.LaunchableResource.LaunchableResource.__init__(
            self,
            **kwargs
        )

    @property
    def jail(self) -> 'JailGenerator':
        """
        Jail instance that belongs to the resource

        Usually the resource becomes inherited from the jail itself.
        It can still be used linked to a foreign jail by passing jail as
        named attribute to the __init__ function
        """
        if self._jail is not None:
            return self._jail

        # is instance of Jail itself
        if isinstance(self, JailGenerator):
            return self

        raise Exception("This resource is not a jail or not linked to one")

    @property
    def fstab(self) -> 'libiocage.lib.Fstab.Fstab':
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

    def getstring(self, key):
        """
        Returns a jail properties string or '-'

        Args:
            key (string):
                Name of the jail property to return
        """

        try:
            return libiocage.lib.helpers.to_string(self.jail.config[key])
        except:
            pass

        return libiocage.lib.Resource.Resource.getstring(self, key)


class JailGenerator(JailResource):
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

    _class_storage = libiocage.lib.Storage.Storage

    config: libiocage.lib.JailConfig.JailConfig = None
    jail_state: dict = None

    def __init__(
        self,
        data: typing.Union[str, typing.Dict[str, typing.Any]]={},
        zfs=None,
        host=None,
        logger=None,
        new=False,
        **resource_args
    ) -> None:
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

        self.logger = libiocage.lib.helpers.init_logger(self, logger)
        self.zfs = libiocage.lib.helpers.init_zfs(self, zfs)
        self.host = libiocage.lib.helpers.init_host(self, host)

        if isinstance(data, str):
            data = {
                "id": self._resolve_name(data)
            }

        self.config = libiocage.lib.JailConfig.JailConfig(
            data=data,
            host=self.host,
            jail=self,
            logger=self.logger
        )

        self.storage = self._class_storage(
            safe_mode=False,
            jail=self,
            logger=self.logger,
            zfs=self.zfs
        )

        JailResource.__init__(
            self,
            jail=self,
            host=self.host,
            logger=self.logger,
            zfs=self.zfs,
            **resource_args
        )

        if new is False:
            self.config.read()
            if self.config["id"] is None:
                self.config["id"] = self.dataset_name.split("/").pop()

    def start(
        self,
        quick: bool=False
    ) -> typing.Generator['libiocage.lib.events.IocageEvent', None, None]:
        """
        Start the jail.
        """

        self.require_jail_existing()
        self.require_jail_stopped()

        release = self.release

        events: typing.Any = libiocage.lib.events
        jailLaunchEvent = events.JailLaunch(jail=self)
        jailVnetConfigurationEvent = events.JailVnetConfiguration(jail=self)
        JailZfsShareMount = events.JailZfsShareMount(jail=self)
        jailServicesStartEvent = events.JailServicesStart(jail=self)

        yield jailLaunchEvent.begin()

        if self.basejail_backend is not None:
            self.basejail_backend.apply(self.storage, release)

        if quick is False:
            self._save_autoconfig()

        self._run_hook("prestart")
        self._launch_jail()

        yield jailLaunchEvent.end()

        if self.config["vnet"]:
            yield jailVnetConfigurationEvent.begin()
            self._start_vimage_network()
            self._configure_routes()
            yield jailVnetConfigurationEvent.end()

        self._limit_resources()
        self._configure_nameserver()

        if self.config["jail_zfs"] is True:
            yield JailZfsShareMount.begin()
            libiocage.lib.ZFSShareStorage.ZFSShareStorage.mount_zfs_shares(
                self.storage
            )
            yield JailZfsShareMount.end()

        if self.config["exec_start"] is not None:
            yield jailServicesStartEvent.begin()
            self._start_services()
            yield jailServicesStartEvent.end()

        self._run_hook("poststart")

    @property
    def basejail_backend(self):

        if self.config["basejail"] is False:
            return None

        if self.config["basejail_type"] == "nullfs":
            return libiocage.lib.NullFSBasejailStorage.NullFSBasejailStorage

        if self.config["basejail_type"] == "zfs":
            return libiocage.lib.ZFSBasejailStorage.ZFSBasejailStorage

        return None

    def _run_hook(self, hook_name: str):

        key = f"exec_{hook_name}"
        value = self.config[key]

        if value == "/usr/bin/true":
            return

        self.logger.verbose(
            f"Running {hook_name} hook for {self.humanreadable_name}"
        )

        return libiocage.lib.helpers.exec(
            value.split(" "),
            logger=self.logger,
            env=self.env
        )

    def _start_services(self):
        command = self.config["exec_start"].strip().split()
        self.logger.debug(f"Running exec_start on {self.humanreadable_name}")
        self.exec(command)

    def stop(
        self,
        force: bool=False
    ) -> typing.Generator['libiocage.lib.events.IocageEvent', None, None]:
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

        events: typing.Any = libiocage.lib.events
        jailDestroyEvent = events.JailDestroy(self)
        jailNetworkTeardownEvent = events.JailNetworkTeardown(self)
        jailMountTeardownEvent = events.JailMountTeardown(self)

        self._run_hook("prestop")

        yield jailDestroyEvent.begin()
        self._destroy_jail()
        yield jailDestroyEvent.end()

        if self.config["vnet"]:
            yield jailNetworkTeardownEvent.begin()
            self._stop_vimage_network()
            yield jailNetworkTeardownEvent.end()

        yield jailMountTeardownEvent.begin()
        self._teardown_mounts()
        yield jailMountTeardownEvent.end()

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

    def rename(self, new_name: str):
        """
        Change the name of a jail
        """

        self.require_jail_existing()
        self.require_jail_stopped()

        current_id = self.config["id"]
        dataset = self.dataset
        self.config["name"] = new_name  # validates new_name
        try:
            dataset.rename(self.dataset_name)
        except:
            self.config["name"] = current_id
            raise

    def _force_stop(self):

        successful = True

        try:
            self._run_hook("prestop")
        except:
            successful = False
            self.logger.warn("pre-stop script failed")

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

        if self.config["id"] is None:
            self.config["name"] = str(uuid.uuid4())

        self.require_jail_not_existing()

        # check if release exists
        release = libiocage.lib.Release.Release(
            name=release_name,
            host=self.host,
            zfs=self.zfs,
            logger=self.logger
        )

        if release.fetched is False:
            raise libiocage.lib.errors.ReleaseNotFetched(
                name=release_name,
                logger=self.logger
            )

        self.config["release"] = release.name

        self.logger.verbose(
            f"Creating jail '{self.config['id']}'",
            jail=self
        )

        for key, value in self.config.data.items():
            msg = f"{key} = {value}"
            self.logger.spam(msg, jail=self, indent=1)

        self.create_resource()
        self.get_or_create_dataset("root")
        self._update_fstab()

        backend = None

        is_basejail = self.config.get("basejail", False)
        if not is_basejail:
            backend = libiocage.lib.StandaloneJailStorage.StandaloneJailStorage
        if is_basejail and self.config["basejail_type"] == "nullfs":
            backend = libiocage.lib.NullFSBasejailStorage.NullFSBasejailStorage
        elif is_basejail and self.config["basejail_type"] == "zfs":
            backend = libiocage.lib.ZFSBasejailStorage.ZFSBasejailStorage

        if backend is not None:
            backend.setup(self.storage, release)

        self.config.data["release"] = release.name
        self.save()

    def save(self):
        self.write_config(self.config.data)
        self._save_autoconfig()

    def _save_autoconfig(self):
        """
        Saves auto-generated files
        """
        self.rc_conf.save()
        self._update_fstab()

    def _update_fstab(self) -> None:

        if self.config["basejail_type"] == "nullfs":
            self.fstab.release = self.release
        else:
            self.fstab.release = None

        self.fstab.update_and_save()

    def exec(self, command, **kwargs):
        """
        Execute a command in a started jail

        command (list):
            A list of command and it's arguments

            Example: ["/usr/bin/whoami"]
        """

        command = ["/usr/sbin/jexec", self.identifier] + command

        return libiocage.lib.helpers.exec(
            command,
            logger=self.logger,
            env=self.env,
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

    @property
    def _dhcp_enabled(self):
        """
        True if any ip4_addr uses DHCP
        """
        if self.config["ip4_addr"] is None:
            return False

        return ("dhcp" in self.config["ip4_addr"].networks)

    @property
    def devfs_ruleset(self):
        """
        The number of the jails devfs ruleset

        When a new combination of the base ruleset specified in
        jail.config["devfs_ruleset"] and rules automatically added by iocage
        appears, the according rule is automatically created and added to the
        /etc/devfs.rules file on the host
        """

        # users may reference a rule by numeric identifier or name
        # numbers are automatically selected, so it's advisable to use names
        try:
            configured_devfs_ruleset = self.host.devfs.find_by_number(
                int(self.config["devfs_ruleset"])
            )
        except ValueError:
            configured_devfs_ruleset = self.host.devfs.find_by_name(
                self.config["devfs_ruleset"]
            )

        devfs_ruleset = libiocage.lib.DevfsRules.DevfsRuleset()
        devfs_ruleset.clone(configured_devfs_ruleset)

        if self._dhcp_enabled:
            devfs_ruleset.append("add path 'bpf*' unhide")

        # create if the final rule combination does not exist as ruleset
        if devfs_ruleset not in self.host.devfs:
            self.logger.verbose("New devfs ruleset combination")
            # note: name and number of devfs_ruleset are both None
            new_ruleset_number = self.host.devfs.new_ruleset(devfs_ruleset)
            self.host.devfs.save()
            return new_ruleset_number
        else:
            ruleset_line_position = self.host.devfs.index(devfs_ruleset)
            return self.host.devfs[ruleset_line_position].number

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
            f"path={self.root_dataset.mountpoint}",
            f"securelevel={self.config['securelevel']}",
            f"host.hostuuid={self.name}",
            f"devfs_ruleset={self.devfs_ruleset}",
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
            f"exec.stop={self.config['exec_stop']}",
            f"exec.clean={self.config['exec_clean']}",
            f"exec.timeout={self.config['exec_timeout']}",
            f"stop.timeout={self.config['stop_timeout']}",
            f"mount.fstab={self.fstab.file_path}",
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

    @property
    def networks(self) -> list:

        networks = []

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
            networks.append(net)

        return networks

    def _start_vimage_network(self) -> None:
        self.logger.debug("Starting VNET/VIMAGE", jail=self)
        for network in self.networks:
            network.setup()

    def _stop_vimage_network(self) -> None:
        for network in self.networks:
            network.teardown()

    def _configure_nameserver(self) -> None:
        self.config["resolver"].apply(self)

    def _limit_resources(self) -> None:

        for resource in self._resource_limit_config_keys:
            try:
                limit, action = self.config[resource].split(":", maxsplit=1)
                command = [
                    "/usr/bin/rctl",
                    "-a",
                    f"jail:{self.identifier}:{resource}:{action}={limit}"
                ]
                libiocage.lib.helpers.exec(command, logger=self.logger)
            except KeyError:
                pass

    @property
    def _resource_limit_config_keys(self):
        return [
            "cputime",
            "datasize",
            "stacksize",
            "coredumpsize",
            "memoryuse",
            "memorylocked",
            "maxproc",
            "openfiles",
            "vmemoryuse",
            "pseudoterminals",
            "swapuse",
            "nthr",
            "msgqqueued",
            "msgqsize",
            "nmsgq",
            "nsem",
            "nsemop",
            "nshm",
            "shmsize",
            "wallclock",
            "pcpu",
            "readbps",
            "writebps",
            "readiops",
            "writeiops"
        ]

    def _configure_routes(self) -> None:

        defaultrouter = self.config["defaultrouter"]
        defaultrouter6 = self.config["defaultrouter6"]

        if not defaultrouter or defaultrouter6:
            self.logger.spam("no static routes configured")
            return

        if defaultrouter:
            self._configure_route(defaultrouter)

        if defaultrouter6:
            self._configure_route(defaultrouter6, ipv6=True)

    def _configure_route(self, gateway, ipv6=False) -> None:

        ip_version = 4 + 2 * (ipv6 is True)

        self.logger.verbose(
            f"setting default IPv{ip_version} gateway to {gateway}",
            jail=self
        )

        command = ["/sbin/route", "add"] + \
            (["-6"] if (ipv6 is True) else []) + ["default", gateway]

        self.exec(command)

    def require_jail_not_existing(self) -> None:
        """
        Raise JailAlreadyExists exception if the jail already exists
        """
        if self.exists:
            raise libiocage.lib.errors.JailAlreadyExists(
                jail=self, logger=self.logger
            )

    def require_jail_existing(self) -> None:
        """
        Raise JailDoesNotExist exception if the jail does not exist
        """
        if not self.exists:
            raise libiocage.lib.errors.JailDoesNotExist(
                jail=self,
                logger=self.logger
            )

    def require_jail_stopped(self) -> None:
        """
        Raise JailAlreadyRunning exception if the jail is runninhg
        """
        if self.running:
            raise libiocage.lib.errors.JailAlreadyRunning(
                jail=self,
                logger=self.logger
            )

    def require_jail_running(self) -> None:
        """
        Raise JailNotRunning exception if the jail is stopped
        """
        if not self.running:
            raise libiocage.lib.errors.JailNotRunning(
                jail=self,
                logger=self.logger
            )

    def update_jail_state(self) -> None:
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

    def _teardown_mounts(self) -> None:

        mountpoints = list(map(
            lambda mountpoint: f"{self.root_path}{mountpoint}",
            [
                "/dev/fd",
                "/dev",
                "/proc",
                "/root/compat/linux/proc"
            ]
        ))

        mountpoints += list(map(
            lambda x: x["destination"],
            list(self.fstab)
        ))

        for mountpoint in mountpoints:
            if os.path.isdir(mountpoint):
                libiocage.lib.helpers.umount(
                    mountpoint,
                    force=True,
                    logger=self.logger,
                    ignore_error=True  # maybe it was not mounted
                )

    def _resolve_name(self, text) -> str:

        if (text is None) or (len(text) == 0):
            raise libiocage.lib.errors.JailNotSupplied(logger=self.logger)

        jails_dataset = self.host.datasets.jails

        for dataset in list(jails_dataset.children):

            dataset_name = dataset.name[(len(jails_dataset.name) + 1):]
            humanreadable_name = libiocage.lib.helpers.to_humanreadable_name(
                dataset_name
            )

            if text in [dataset_name, humanreadable_name]:
                return dataset_name

        raise libiocage.lib.errors.JailNotFound(text, logger=self.logger)

    @property
    def name(self) -> str:
        """
        The name (formerly UUID) of the Jail
        """
        return self.config["id"]

    @property
    def humanreadable_name(self) -> str:
        """
        A human-readable identifier to print in logs and CLI output

        Whenever a Jail is found to have a UUID as identifier,
        a shortened string of the first 8 characters is returned
        """
        try:
            return libiocage.lib.helpers.to_humanreadable_name(self.name)
        except:
            raise libiocage.lib.errors.JailUnknownIdentifier(
                logger=self.logger
            )

    @property
    def stopped(self) -> bool:
        """
        Boolean value that is True if a jail is stopped
        """
        return self.running is not True

    @property
    def running(self) -> bool:
        """
        Boolean value that is True if a jail is running
        """
        return self.jid is not None

    @property
    def jid(self) -> int:
        """
        The JID of a running jail or None if the jail is not running
        """
        try:
            return int(self.jail_state["jid"])
        except (TypeError, AttributeError, KeyError):
            pass

        try:
            self.update_jail_state()
            return int(self.jail_state["jid"])
        except (TypeError, AttributeError, KeyError):
            return None

    @property
    def env(self):
        """
        Environment variables for hook scripts
        """
        jail_env = os.environ.copy()

        for prop in self.config.all_properties:
            jail_env[prop] = self.getstring(prop)

        return jail_env

    @property
    def identifier(self):
        """
        Used internally to identify jails (in snapshots, jls, etc)
        """
        return f"ioc-{self.config['id']}"

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
    def logfile_path(self):
        """
        Absolute path of the jail log file
        """
        return f"{self.host.datasets.logs.mountpoint}-console.log"

    def __getattribute__(self, key):

        try:
            return object.__getattribute__(self, key)
        except AttributeError:
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

    def __dir__(self):

        properties = set()

        for prop in dict.__dir__(self):
            if not prop.startswith("_"):
                properties.add(prop)

        return list(properties)


class Jail(JailGenerator):

    def start(self, *args, **kwargs):
        return list(JailGenerator.start(self, *args, **kwargs))

    def stop(self, *args, **kwargs):
        return list(JailGenerator.stop(self, *args, **kwargs))
