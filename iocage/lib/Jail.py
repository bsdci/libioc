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
import re
import subprocess  # nosec: B404
import shlex

import iocage.lib.Types
import iocage.lib.errors
import iocage.lib.events
import iocage.lib.helpers
import iocage.lib.JailState
import iocage.lib.DevfsRules
import iocage.lib.Host
import iocage.lib.Config.Jail.JailConfig
import iocage.lib.Network
import iocage.lib.NullFSBasejailStorage
import iocage.lib.Release
import iocage.lib.StandaloneJailStorage
import iocage.lib.Storage
import iocage.lib.ZFSBasejailStorage
import iocage.lib.ZFSShareStorage
import iocage.lib.LaunchableResource
import iocage.lib.VersionedResource
import iocage.lib.Config.Jail.File.Fstab


class JailResource(
    iocage.lib.LaunchableResource.LaunchableResource,
    iocage.lib.VersionedResource.VersionedResource
):

    _jail: 'JailGenerator'
    _fstab: 'iocage.lib.Config.Jail.File.Fstab.Fstab'

    def __init__(
        self,
        host: 'iocage.lib.Host.HostGenerator',
        jail: typing.Optional['JailGenerator']=None,
        **kwargs
    ) -> None:

        self.__jails_dataset_name = host.datasets.jails.name
        self.host = iocage.lib.helpers.init_host(self, host)

        if jail is not None:
            self._jail = jail

        iocage.lib.LaunchableResource.LaunchableResource.__init__(
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
        try:
            return self._jail
        except AttributeError:
            pass

        # is instance of Jail itself
        if isinstance(self, JailGenerator):
            jail = self  # type: JailGenerator
            return jail

        raise Exception("This resource is not a jail or not linked to one")

    @property
    def fstab(self) -> 'iocage.lib.Config.Jail.File.Fstab.Fstab':
        """
        Memoized fstab wrapper of a Jail

        The fstab file is stored in the top level of a Jails dataset
        """

        try:
            return self._fstab
        except AttributeError:
            pass

        fstab = iocage.lib.Config.Jail.File.Fstab.Fstab(
            jail=self.jail,
            release=self.jail.release,
            logger=self.logger,
            host=self.jail.host
        )
        self._fstab = fstab
        return fstab

    @property
    def dataset_name(self) -> str:
        """
        Name of the jail base ZFS dataset

        If the resource has no dataset or dataset_name assigned yet,
        the jail id is used to find name the dataset
        """
        try:
            return str(self._assigned_dataset_name)
        except AttributeError:
            pass

        try:
            return str(self._dataset.name)
        except AttributeError:
            pass

        return self._dataset_name_from_jail_name

    @dataset_name.setter
    def dataset_name(self, value: str) -> None:
        """
        Overrides a jails dataset name

        This will cause Jail.dataset to point to this specific dataset instead
        of an auto-detected one to enable referencing jails from datasets
        that are not managed by iocage
        """
        self._dataset_name = value

    @property
    def _dataset_name_from_jail_name(self) -> str:

        jail_id = str(self.jail.config["id"])
        if jail_id is None:
            raise iocage.lib.errors.JailUnknownIdentifier()

        return f"{self.__jails_dataset_name}/{jail_id}"

    def get(self, key: str) -> typing.Any:
        try:
            out = self.jail.config[key]
            return out
        except KeyError:
            pass

        return iocage.lib.Resource.Resource.get(self, key)


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

    _class_storage = iocage.lib.Storage.Storage
    _state: typing.Optional[iocage.lib.JailState.JailState]

    def __init__(
        self,
        data: typing.Union[str, typing.Dict[str, typing.Any]]={},
        zfs: typing.Optional['iocage.lib.ZFS.ZFS']=None,
        host: typing.Optional['iocage.lib.Host.Host']=None,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None,
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

            host (iocage.lib.Host): (optional)
                Inherit an existing Host instance from ancestor classes

            logger (iocage.lib.Logger): (optional)
                Inherit an existing Logger instance from ancestor classes

        """

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)
        self.host = iocage.lib.helpers.init_host(self, host)

        if isinstance(data, str):
            data = {
                "id": self._resolve_name(data)
            }

        JailResource.__init__(
            self,
            jail=self,
            host=self.host,
            logger=self.logger,
            zfs=self.zfs,
            **resource_args
        )

        if not new and (("id" not in data) or (data["id"] is None)):
            try:
                # try to get the Jail name from it's dataset_name
                data["id"] = self.dataset_name.split("/").pop()
            except iocage.lib.errors.JailUnknownIdentifier:
                pass

        self.config = iocage.lib.Config.Jail.JailConfig.JailConfig(
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

        if new is False:
            self.config.read(data=self.read_config())
            if self.config["id"] is None:
                self.config["id"] = self.dataset_name.split("/").pop()

    @property
    def state(self) -> iocage.lib.JailState.JailState:
        """
        Memoized JailState.

        This object holds information about the jail state. The information
        is memoized on first access because the lookup is expensive. Please
        keep in mind to update the object when executing operations that
        potentially change a jails state.
        """
        if "_state" not in object.__dir__(self):
            return self._init_state()
        elif object.__getattribute__(self, "_state") is None:
            return self._init_state()
        return object.__getattribute__(self, "_state")

    @state.setter
    def state(self, value: iocage.lib.JailState):
        """
        A public interface to set a jails state. This behavior is part of a
        performance optimization when dealing with large numbers of jails.
        """
        object.__setattr__(self, '_state', value)

    def _init_state(self) -> iocage.lib.JailState.JailState:
        state = iocage.lib.JailState.JailState(self.identifier)
        self.state = state
        state.query()
        return state

    def start(
        self,
        quick: bool=False,
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """
        Start the jail.
        """

        self.require_jail_existing()
        self.require_jail_stopped()

        release = self.release

        events: typing.Any = iocage.lib.events
        jailLaunchEvent = events.JailLaunch(jail=self)
        jailVnetConfigurationEvent = events.JailVnetConfiguration(jail=self)
        JailZfsShareMount = events.JailZfsShareMount(jail=self)
        jailServicesStartEvent = events.JailServicesStart(jail=self)

        yield jailLaunchEvent.begin()

        if self.is_basejail is True:
            self.storage_backend.apply(self.storage, release)

        if quick is False:
            self._save_autoconfig()

        self._run_hook("prestart")
        self._launch_jail()

        yield jailLaunchEvent.end()

        if self.config["vnet"]:
            yield jailVnetConfigurationEvent.begin()
            self._start_vimage_network()
            self._configure_routes()
            self._configure_localhost()
            yield jailVnetConfigurationEvent.end()

        self._limit_resources()
        self._configure_nameserver()

        if self.config["jail_zfs"] is True:
            yield JailZfsShareMount.begin()
            share_storage = iocage.lib.ZFSShareStorage.ZFSShareStorage(
                jail=self,
                logger=self.logger
            )
            share_storage.mount_zfs_shares()
            yield JailZfsShareMount.end()

        if self.config["exec_start"] is not None:
            yield jailServicesStartEvent.begin()
            self._start_services()
            yield jailServicesStartEvent.end()

        self._run_hook("poststart")

    def fork_exec(
        self,
        command: typing.List[str],
        **temporary_config_override
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """
        Starts a jail, runs a command and exists
        """
        self.require_jail_existing()
        self.require_jail_stopped()

        events: typing.Any = iocage.lib.events
        jailForkExecEvent = events.JailForkExec(jail=self)
        jailExecEvent = events.JailExec(jail=self)

        yield jailForkExecEvent.begin()

        original_config = self.config
        config_data = original_config.data

        for key, value in temporary_config_override.items():
            config_data[key] = value

        self.config = iocage.lib.Config.Jail.JailConfig.JailConfig(
            data=original_config.data,
            host=self.host,
            jail=self,
            logger=self.logger
        )

        for event in self.start():
            yield event

        yield jailExecEvent.begin()
        try:
            self.passthru(command)
            yield jailExecEvent.end()
        except:
            yield jailExecEvent.fail()

        for event in self.stop():
            yield event

        self.config = original_config

        yield jailForkExecEvent.end()

    @property
    def basejail_backend(self):

        if self.config["basejail"] is False:
            return None

        if self.config["basejail_type"] == "nullfs":
            return iocage.lib.NullFSBasejailStorage.NullFSBasejailStorage

        if self.config["basejail_type"] == "zfs":
            return iocage.lib.ZFSBasejailStorage.ZFSBasejailStorage

        return None

    def _run_hook(self, hook_name: str):

        key = f"exec_{hook_name}"
        value = self.config[key]

        if value == "/usr/bin/true":
            return

        self.logger.verbose(
            f"Running {hook_name} hook for {self.humanreadable_name}"
        )

        lex = shlex.shlex(value)  # noqa: T484
        lex.whitespace_split = True
        command = list(lex)

        return iocage.lib.helpers.exec(
            command,
            logger=self.logger,
            env=self.env
        )

    def _start_services(self) -> None:
        command = str(self.config["exec_start"]).strip().split()
        self.logger.debug(f"Running exec_start on {self.humanreadable_name}")
        self.exec(command)

    def stop(
        self,
        force: bool=False
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """
        Stop a jail.

        Args:

            force (bool): (default=False)
                Ignores failures and enforces teardown if True
        """

        if force is True:
            for event in self._force_stop():
                yield event
            return

        self.require_jail_existing()
        self.require_jail_running()

        events: typing.Any = iocage.lib.events
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

        self.state.query()

    def destroy(self, force: bool=False) -> None:
        """
        Destroy a Jail and it's datasets

        Args:

            force (bool): (default=False)
                This flag enables whether an existing jail should be shut down
                before destroying the dataset. By default destroying a jail
                requires it to be stopped.
        """

        self.state.query()

        if self.running is True and force is True:
            self.stop(force=True)
        else:
            self.require_jail_stopped()

        self.zfs.delete_dataset_recursive(self.dataset)

    def rename(
        self,
        new_name: str
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """
        Change the name of a jail

        Args:

            new_name (str):
                The new name of a jail. It might not be used by another Jail
                and must differ from the current name.
        """

        self.require_jail_existing()
        self.require_jail_stopped()
        self.require_storage_backend()

        current_id = self.config["id"]
        current_mountpoint = self.dataset.mountpoint

        jailRenameEvent = iocage.lib.events.JailRename(
            jail=self,
            current_name=current_id,
            new_name=new_name
        )

        self.config["id"] = new_name  # validates new_name

        yield jailRenameEvent.begin()
        self.logger.debug(f"Renaming jail {current_id} to {new_name}")

        def revert_id_change() -> None:
            self.config["id"] = current_id
            self.logger.debug(f"Jail id reverted to {current_id}")
        jailRenameEvent.add_rollback_step(revert_id_change)

        try:
            events = self.storage_backend.rename(
                self.storage,
                new_name=new_name
            )
            for event in events:
                yield jailRenameEvent.child_event(event)
                if event.error is not None:
                    raise event.error
        except BaseException as e:
            yield jailRenameEvent.fail(e)
            raise

        # Update fstab to the new dataset
        jailFstabUpdateEvent = iocage.lib.events.JailFstabUpdate(
            jail=self
        )
        yield jailFstabUpdateEvent.begin()
        try:
            self.fstab.read_file()
            self.fstab.replace_path(
                re.compile(f"^{current_mountpoint}"),
                self.dataset.mountpoint
            )
            self.fstab.save()
            yield jailFstabUpdateEvent.end()
            yield jailRenameEvent.end()
        except BaseException:
            yield jailFstabUpdateEvent.fail()
            raise

    def _force_stop(
        self
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        events: typing.Any = iocage.lib.events
        jailDestroyEvent = events.JailDestroy(self)
        jailNetworkTeardownEvent = events.JailNetworkTeardown(self)
        jailMountTeardownEvent = events.JailMountTeardown(self)

        try:
            self._run_hook("prestop")
        except Exception:
            self.logger.warn("pre-stop script failed")

        yield jailDestroyEvent.begin()
        try:
            self._destroy_jail()
            self.logger.debug(f"{self.humanreadable_name}: jail destroyed")
            yield jailDestroyEvent.end()
        except Exception as e:
            yield jailDestroyEvent.skip()

        if self.config["vnet"]:
            yield jailNetworkTeardownEvent.begin()
            try:
                self._stop_vimage_network()
                self.logger.debug(f"{self.humanreadable_name}: VNET stopped")
                yield jailNetworkTeardownEvent.end()
            except Exception as e:
                yield jailNetworkTeardownEvent.skip()

        yield jailMountTeardownEvent.begin()
        try:
            self._teardown_mounts()
            self.logger.debug(f"{self.humanreadable_name}: mounts destroyed")
            yield jailMountTeardownEvent.end()
        except Exception as e:
            yield jailMountTeardownEvent.skip()

        try:
            self.state.query()
        except Exception as e:
            self.logger.warn(str(e))

    def create(
        self,
        resource: typing.Union[
            'JailGenerator',
            'iocage.lib.Release.ReleaseGenerator',
        ]
    ) -> None:
        """
        Create a Jail from a given Resource

        Args:

            resource (Jail or Release):
                The (new) jail is created from this resource.
        """
        if isinstance(resource, JailGenerator):
            self.create_from_template(template=resource)
        else:
            self.create_from_release(release=resource)

    def create_from_release(
        self,
        release: iocage.lib.Release.ReleaseGenerator
    ) -> None:
        """
        Create a Jail from a Release

        Args:

            resource (Release):
                The jail is created from the provided resource.
                This can be either another Jail or a Release.
        """
        if release.fetched is False:
            raise iocage.lib.errors.ReleaseNotFetched(
                name=release.name,
                logger=self.logger
            )

        self.config["release"] = release.name
        self._create_from_resource(release)

    def create_from_template(
        self,
        template: 'JailGenerator'
    ) -> None:
        """
        Create a Jail from another Jail
        """

        template.require_jail_is_template()
        self.config['release'] = template.config['release']
        self.config['basejail'] = template.config['basejail']
        self.config['basejail_type'] = template.config['basejail_type']
        self._create_from_resource(template)

    def _create_from_resource(
        self,
        resource: 'iocage.lib.Resource.Resource'
    ) -> None:

        if self.config["id"] is None:
            self.config["id"] = str(iocage.lib.helpers.get_random_uuid())

        self.require_jail_not_existing()

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

        backend = self.storage_backend
        if backend is not None:
            backend.setup(self.storage, resource)

        self.save()

    @property
    def is_basejail(self):
        """
        Returns True if a Jail is a basejail.

        If this is the case, parts of the jails dataset will be mounted
        from its release or upstream Jail (for example a Template)
        """
        return self.config.get("basejail", False)

    @property
    def storage_backend(self) -> iocage.lib.Storage.Storage:
        """
        Returns the class that represents the jails storage backend according
        to its configuration.
        """
        if not self.is_basejail:
            return iocage.lib.StandaloneJailStorage.StandaloneJailStorage
        if self.config["basejail_type"] == "nullfs":
            return iocage.lib.NullFSBasejailStorage.NullFSBasejailStorage
        if self.config["basejail_type"] == "zfs":
            return iocage.lib.ZFSBasejailStorage.ZFSBasejailStorage

    def save(self) -> None:
        """
        Permanently safe a Jails configuration
        """
        self.write_config(self.config.data)
        self._save_autoconfig()

    def _save_autoconfig(self) -> None:
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

    def exec(
        self,
        command: typing.List[str],
        **kwargs
    ) -> typing.Tuple[subprocess.Popen, str, str]:
        """
        Execute a command in a started jail

        command (list):
            A list of command and it's arguments

            Example: ["/usr/bin/whoami"]
        """

        command = ["/usr/sbin/jexec", self.identifier] + command

        child, stdout, stderr = iocage.lib.helpers.exec(
            command,
            logger=self.logger,
            env=self.env,
            **kwargs
        )

        return child, stdout, stderr

    def passthru(self, command: typing.List[str]):
        """
        Execute a command in a started jail ans passthrough STDIN and STDOUT

        command (list):
            A list of command and it's arguments

            Example: ["/bin/sh"]
        """

        if isinstance(command, str):
            command = [command]

        return iocage.lib.helpers.exec_passthru(
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

    def _destroy_jail(self) -> None:

        command = ["/usr/sbin/jail", "-r"]
        command.append(self.identifier)

        subprocess.check_output(
            command,
            shell=False,  # nosec; TODO use helper
            stderr=subprocess.DEVNULL
        )

    @property
    def _dhcp_enabled(self) -> bool:
        """
        True if any ip4_addr uses DHCP
        """
        if self.config["ip4_addr"] is None:
            return False

        return ("dhcp" in self.config["ip4_addr"].networks) is True

    @property
    def devfs_ruleset(self) -> iocage.lib.DevfsRules.DevfsRuleset:
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

        devfs_ruleset = iocage.lib.DevfsRules.DevfsRuleset()
        devfs_ruleset.clone(configured_devfs_ruleset)

        if self._dhcp_enabled is True:
            devfs_ruleset.append("add path 'bpf*' unhide")

        if self._allow_mount_zfs == "1":
            devfs_ruleset.append("add path zfs unhide")

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

    def _launch_jail(self) -> None:

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
            f"securelevel={self._get_value('securelevel')}",
            f"host.hostuuid={self.name}",
            f"devfs_ruleset={self.devfs_ruleset}",
            f"enforce_statfs={self._get_value('enforce_statfs')}",
            f"children.max={self._get_value('children_max')}",
            f"allow.set_hostname={self._get_value('allow_set_hostname')}",
            f"allow.sysvipc={self._get_value('allow_sysvipc')}"
        ]

        if self.host.userland_version > 10.3:
            command += [
                f"sysvmsg={self._get_value('sysvmsg')}",
                f"sysvsem={self._get_value('sysvsem')}",
                f"sysvshm={self._get_value('sysvshm')}"
            ]

        command += [
            f"allow.raw_sockets={self._get_value('allow_raw_sockets')}",
            f"allow.chflags={self._get_value('allow_chflags')}",
            f"allow.mount={self._allow_mount}",
            f"allow.mount.devfs={self._get_value('allow_mount_devfs')}",
            f"allow.mount.nullfs={self._get_value('allow_mount_nullfs')}",
            f"allow.mount.procfs={self._get_value('allow_mount_procfs')}",
            f"allow.mount.zfs={self._allow_mount_zfs}",
            f"allow.quotas={self._get_value('allow_quotas')}",
            f"allow.socket_af={self._get_value('allow_socket_af')}",
            f"exec.stop={self._get_value('exec_stop')}",
            f"exec.clean={self._get_value('exec_clean')}",
            f"exec.timeout={self._get_value('exec_timeout')}",
            f"stop.timeout={self._get_value('stop_timeout')}",
            f"mount.fstab={self.fstab.path}",
            f"mount.devfs={self._get_value('mount_devfs')}"
        ]

        if self.host.userland_version > 9.3:
            command += [
                f"mount.fdescfs={self._get_value('mount_fdescfs')}",
                f"allow.mount.tmpfs={self._get_value('allow_mount_tmpfs')}"
            ]

        command += [
            "allow.dying",
            "persist"
        ]

        humanreadable_name = self.humanreadable_name
        try:
            iocage.lib.helpers.exec(command, logger=self.logger)
            self.state.query()
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

    def _get_value(self, key: str) -> str:
        """
        Return jail command consumable config value string
        """
        return str(iocage.lib.helpers.to_string(
            self.config[key],
            true="1",
            false="0",
            none=""
        ))

    @property
    def networks(self) -> typing.List[iocage.lib.Network.Network]:
        """
        List of a Jails configured networks
        """

        networks = []

        nics = self.config["interfaces"]

        if nics is None:
            return []

        for nic in nics:

            bridge = self.config["interfaces"][nic]

            try:
                ipv4_addresses = self.config["ip4_addr"][nic]
            except KeyError:
                ipv4_addresses = []

            try:
                ipv6_addresses = self.config["ip6_addr"][nic]
            except KeyError:
                ipv6_addresses = []

            net = iocage.lib.Network.Network(
                jail=self,
                nic=nic,
                ipv4_addresses=ipv4_addresses,
                ipv6_addresses=ipv6_addresses,
                bridge=bridge,
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

    def _configure_localhost(self) -> None:
        self.exec(["ifconfig", "lo0", "localhost"])

    def _limit_resources(self) -> None:

        if self.config['rlimits'] is False:
            self.logger.verbose("Resource limits disabled")
            return

        for key, limit, action in map(
            lambda name: (name, ) + self._get_resource_limit(name),
            self._resource_limit_config_keys
        ):

            if (limit is None) and (action is None):
                # this resource is not limited (limit disabled)
                continue

            command = [
                "/usr/bin/rctl",
                "-a",
                f"jail:{self.identifier}:{key}:{action}={limit}"
            ]
            iocage.lib.helpers.exec(command, logger=self.logger)

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

    @property
    def _allow_mount(self) -> str:
        if self._allow_mount_zfs == "1":
            return "1"
        return self._get_value("allow_mount")

    @property
    def _allow_mount_zfs(self) -> str:
        if self.config["jail_zfs"] is True:
            return "1"
        return self._get_value("allow_mount_zfs")

    def _get_resource_limit(
        self,
        key: str
    ) -> typing.Union[typing.Tuple[str, str], typing.Tuple[None, None]]:

        try:
            if isinstance(self.config[key], str):
                return self._parse_resource_limit(self.config[key])
        except KeyError:
            pass

        return None, None

    def _parse_resource_limit(
        self,
        value: str
    ) -> typing.Tuple[str, str]:

        limit, action = value.split(":", maxsplit=1)
        return limit, action

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

        # router@interface syntax for static pointopoint route
        if "@" in gateway:
            gateway, nic = gateway.split("@", maxsplit=1)
            self.logger.verbose(
                f"setting pointopoint route to {gateway} via {nic}"
            )
            self.exec(["/sbin/route", "add", gateway, "-iface", nic])

        self.logger.verbose(
            f"setting default IPv{ip_version} gateway to {gateway}",
            jail=self
        )
        self.exec(
            ["/sbin/route", "add"] +
            (["-6"] if (ipv6 is True) else []) +
            ["default", gateway]
        )

    def require_jail_is_template(self, **kwargs) -> None:
        """
        Raise JailIsTemplate exception if the jail is a template
        """
        if self.config['template'] is False:
            raise iocage.lib.errors.JailNotTemplate(
                jail=self,
                logger=self.logger,
                **kwargs
            )

    def require_storage_backend(self) -> None:
        """
        Raise if the jail was not initialized with a storage backend
        """
        if self.storage_backend is None:
            raise Exception("")

    def require_jail_not_template(self, **kwargs) -> None:
        """
        Raise JailIsTemplate exception if the jail is a template
        """
        if self.config['template'] is True:
            raise iocage.lib.errors.JailIsTemplate(
                jail=self,
                logger=self.logger,
                **kwargs
            )

    def require_jail_not_existing(self, **kwargs) -> None:
        """
        Raise JailAlreadyExists exception if the jail already exists
        """
        if self.exists:
            raise iocage.lib.errors.JailAlreadyExists(
                jail=self,
                logger=self.logger,
                **kwargs
            )

    def require_jail_existing(self, **kwargs) -> None:
        """
        Raise JailDoesNotExist exception if the jail does not exist
        """
        if not self.exists:
            raise iocage.lib.errors.JailDoesNotExist(
                jail=self,
                logger=self.logger,
                **kwargs
            )

    def require_jail_stopped(self, **kwargs) -> None:
        """
        Raise JailAlreadyRunning exception if the jail is runninhg
        """
        if self.running is not False:
            raise iocage.lib.errors.JailAlreadyRunning(
                jail=self,
                logger=self.logger,
                **kwargs
            )

    def require_jail_running(self, **kwargs) -> None:
        """
        Raise JailNotRunning exception if the jail is stopped
        """
        if not self.running:
            raise iocage.lib.errors.JailNotRunning(
                jail=self,
                logger=self.logger,
                **kwargs
            )

    def _teardown_mounts(self) -> None:

        mountpoints = list(filter(
            os.path.isdir,
            map(
                self._get_absolute_path_from_jail_asset,
                [
                    "/usr/bin",
                    "/dev/fd",
                    "/dev",
                    "/proc",
                    "/root/compat/linux/proc",
                    "/root/etcupdate",
                    "/root/usr/ports",
                    "/root/usr/src",
                    "/tmp"  # nosec: B108
                ]
            )
        ))

        iocage.lib.helpers.umount(
            mountpoints,
            force=True,
            logger=self.logger,
            ignore_error=True
        )

        iocage.lib.helpers.umount(
            ["-a", "-F", self.fstab.path],
            force=True,
            logger=self.logger,
            ignore_error=True
        )

        if self.config.legacy is True:
            command = [
                "/bin/sh",
                "-c",
                " | ".join([
                    "mount -t nullfs",
                    "sed -r 's/(.+) on (.+) \\(nullfs, .+\\)$/\\2/'",
                    f"grep '^{self.root_dataset.mountpoint}/'",
                    "xargs umount"
                ])
            ]
            iocage.lib.helpers.exec(
                command,
                logger=self.logger
            )

    def _get_absolute_path_from_jail_asset(
        self,
        value: str
    ) -> iocage.lib.Types.AbsolutePath:

        return iocage.lib.Types.AbsolutePath(f"{self.root_path}{value}")

    def _resolve_name(self, text) -> str:

        if (text is None) or (len(text) == 0):
            raise iocage.lib.errors.JailNotSupplied(logger=self.logger)

        jails_dataset = self.host.datasets.jails

        for dataset in list(jails_dataset.children):

            dataset_name = str(dataset.name[(len(jails_dataset.name) + 1):])
            humanreadable_name = iocage.lib.helpers.to_humanreadable_name(
                dataset_name
            )

            if text in [dataset_name, humanreadable_name]:
                return dataset_name

        raise iocage.lib.errors.JailNotFound(text, logger=self.logger)

    @property
    def name(self) -> str:
        """
        The name (formerly UUID) of the Jail
        """
        return str(self.config["id"])

    @property
    def humanreadable_name(self) -> str:
        """
        A human-readable identifier to print in logs and CLI output

        Whenever a Jail is found to have a UUID as identifier,
        a shortened string of the first 8 characters is returned
        """
        try:
            return str(iocage.lib.helpers.to_humanreadable_name(self.name))
        except KeyError:
            raise iocage.lib.errors.JailUnknownIdentifier(
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
    def jid(self) -> typing.Optional[int]:
        """
        The JID of a running jail or None if the jail is not running
        """

        # force state init when jid was requested
        if "_state" not in object.__dir__(self):
            self._init_state()

        try:
            return int(self.state["jid"])
        except (KeyError, TypeError):
            return None

    @property
    def env(self):
        """
        Environment variables for hook scripts
        """
        jail_env = os.environ.copy()

        for prop in self.config.all_properties:
            prop_name = f"IOCAGE_{prop.upper()}"
            jail_env[prop_name] = self.getstring(prop)

        jail_env["IOCAGE_JAIL_PATH"] = self.root_dataset.mountpoint

        return jail_env

    @property
    def identifier(self):
        """
        Used internally to identify jails (in snapshots, jls, etc)
        """
        config = object.__getattribute__(self, 'config')
        return f"ioc-{config['id']}"

    @property
    def release(self):
        """
        The iocage.Release instance linked with the jail
        """
        return iocage.lib.Release.Release(
            name=self.config["release"],
            logger=self.logger,
            host=self.host,
            zfs=self.zfs
        )

    def __getattribute__(self, key: str):

        try:
            return object.__getattribute__(self, key)
        except AttributeError:
            pass

        if "_state" in object.__dir__(self):
            try:
                return object.__getattribute__(self, "state")[key]
            except (AttributeError, KeyError):
                pass

        raise AttributeError(f"Jail property {key} not found")

    def __dir__(self):

        properties = set()

        for prop in dict.__dir__(self):
            if not prop.startswith("_"):
                properties.add(prop)

        return list(properties)


class Jail(JailGenerator):

    def start(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> typing.List['iocage.lib.events.IocageEvent']:

        return list(JailGenerator.start(self, *args, **kwargs))

    def stop(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> typing.List['iocage.lib.events.IocageEvent']:

        return list(JailGenerator.stop(self, *args, **kwargs))

    def rename(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> typing.List['iocage.lib.events.IocageEvent']:

        return list(JailGenerator.rename(self, *args, **kwargs))
