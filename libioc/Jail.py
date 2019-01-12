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
"""iocage Jail module."""
import typing
import os
import random
import shlex
import shutil

import libzfs

import libioc.Types
import libioc.errors
import libioc.events
import libioc.helpers
import libioc.helpers_object
import libioc.JailState
import libioc.DevfsRules
import libioc.Host
import libioc.Config.Jail.JailConfig
import libioc.Network
import libioc.Release
import libioc.Storage
import libioc.Storage.NullFSBasejail
import libioc.Storage.Standalone
import libioc.Storage.ZFSBasejail
import libioc.ZFSShareStorage
import libioc.LaunchableResource
import libioc.VersionedResource
import libioc.Config.Jail.Properties.ResourceLimit
import libioc.ResourceSelector
import libioc.Config.Jail.File.Fstab


class JailResource(
    libioc.LaunchableResource.LaunchableResource,
    libioc.VersionedResource.VersionedResource
):
    """Resource that represents a jail."""

    _jail: 'JailGenerator'
    _fstab: 'libioc.Config.Jail.File.Fstab.Fstab'
    host: 'libioc.Host.HostGenerator'
    root_datasets_name: typing.Optional[str]

    def __init__(
        self,
        jail: 'JailGenerator',
        dataset: typing.Optional[libzfs.ZFSDataset]=None,
        dataset_name: typing.Optional[str]=None,
        config_type: str="auto",
        config_file: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        zfs: typing.Optional[libioc.ZFS.ZFS]=None,
        host: typing.Optional['libioc.Host.HostGenerator']=None,
        fstab: typing.Optional['libioc.Config.Jail.File.Fstab.Fstab']=None,
        root_datasets_name: typing.Optional[str]=None,
    ) -> None:

        self.host = libioc.helpers_object.init_host(self, host)
        self.root_datasets_name = root_datasets_name

        if fstab is not None:
            self._fstab = fstab

        if jail is not None:
            self._jail = jail

        libioc.LaunchableResource.LaunchableResource.__init__(
            self,
            dataset=dataset,
            dataset_name=dataset_name,
            config_type=config_type,
            config_file=config_file,
            logger=logger,
            zfs=zfs
        )

    @property
    def jail(self) -> 'JailGenerator':
        """
        Jail instance that belongs to the resource.

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
    def fstab(self) -> 'libioc.Config.Jail.File.Fstab.Fstab':
        """
        Memoized fstab wrapper of a Jail.

        The fstab file is stored in the top level of a Jails dataset
        """
        try:
            return self._fstab
        except AttributeError:
            pass

        try:
            release = self.release
        except AttributeError:
            release = None

        jail = self.jail
        fstab = libioc.Config.Jail.File.Fstab.Fstab(
            jail=jail,
            release=release,
            logger=self.logger,
            host=jail.host
        )
        self._fstab = fstab
        return fstab

    @property
    def dataset_name(self) -> str:
        """
        Name of the jail base ZFS dataset.

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
        Override a jail's dataset name.

        This will cause Jail.dataset to point to this specific dataset instead
        of an auto-detected one to enable referencing jails from datasets
        that are not managed by iocage
        """
        self._dataset_name = value

    def autoset_dataset_name(self) -> None:
        """
        Automatically determine and set the dataset_name.

        When a jail was created with the new attribute enabled, the dataset
        might not exist, so that a dataset_name lookup would fail. Calling this
        method sets the jails dataset_name to a child dataset of the hosts
        jails dataset with the jails name.
        """
        if self.root_datasets_name is None:
            base_name = self.host.datasets.main.jails.name
        else:
            base_name = self.host.datasets.__getitem__(
                self.root_datasets_name
            ).jails.name

        self.dataset_name = f"{base_name}/{self.name}"

    @property
    def _dataset_name_from_jail_name(self) -> str:
        jail_id = str(self.jail.config["id"])
        if jail_id is None:
            raise libioc.errors.JailUnknownIdentifier()

        if self.root_datasets_name is None:
            base_name = self.host.datasets.main.jails.name
        else:
            try:
                base_name = self.host.datasets.__getitem__(
                    self.root_datasets_name
                ).jails.name
            except KeyError:
                raise libioc.errors.SourceNotFound(logger=self.logger)
        return f"{base_name}/{jail_id}"

    @property
    def source(self) -> str:
        """Return the name of the jails source root datasets."""
        return str(
            self.host.datasets.find_root_datasets_name(self.dataset_name)
        )

    def get(self, key: str) -> typing.Any:
        """Get a config value from the jail or defer to its resource."""
        try:
            return libioc.Resource.Resource.get(self, key)
        except AttributeError:
            pass

        return self.jail.config[key]


class JailGenerator(JailResource):
    """
    iocage unit orchestrates a jail's configuration and manages state.

    Jails are represented as a zfs dataset ``zpool/iocage/jails/<NAME>``

    Directory Structure:

        zpool/iocage/jails/<NAME>:
            The jail's dataset containing it's configuration and root dataset.
            iocage-legacy used to store a jails configuration as ZFS
            properties on this dataset. Even though the modern JSON config
            mechanism is preferred.

        zpool/iocage/jails/<NAME>/root:
            This directory is the dataset used as jail's root when starting a
            jail. Usually the clone source of a root dataset is a snapshot of
            the release's root dataset.

        zpool/iocage/jails/<NAME>/config.json:
            Jails configured with the latest configuration style store their
            information in a JSON file. When this file is found in the jail's
            dataset, libiocage assumes the jail to be a JSON-style jail and
            ignores other configuration mechanisms.

        zpool/iocage/jails/<NAME>/config:
            Another compatible configuration mechanism is a UCL file. It's
            content is only taken into account if no JSON or ZFS configuration
            was found.

    Jail Types:

        Standalone:
            The /root dataset gets cloned from a release at creation time. It
            it not affected by changes to the Release and persists all data
            within the jail.

        NullFS Basejail:
            The fastest method to spawn a basejail by mounting read-only
            directories from the release's root dataset by creating a snapshot
            of the release on each boot of the jail. When a release is
            updated, the jail is updated as well on the next reboot. This type
            is the one used by the Python implementation of libioc.

        ZFS Basejail: Legacy basejails used to clone individual datasets from a
            release (stored in ``zpool/iocage/base/<RELEASE>``).

    """

    _class_storage = libioc.Storage.Storage
    _state: typing.Optional['libioc.JailState.JailState']
    _relative_hook_script_dir: str
    _provisioner: 'libioc.Provisioning.Prototype'

    def __init__(
        self,
        data: typing.Union[str, typing.Dict[str, typing.Any]]={},
        dataset: typing.Optional[libzfs.ZFSDataset]=None,
        dataset_name: typing.Optional[str]=None,
        config_type: str="auto",
        config_file: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        zfs: typing.Optional['libioc.ZFS.ZFS']=None,
        host: typing.Optional['libioc.Host.Host']=None,
        fstab: typing.Optional['libioc.Config.Jail.File.Fstab.Fstab']=None,
        root_datasets_name: typing.Optional[str]=None,
        new: bool=False
    ) -> None:
        """
        Initialize a Jail.

        Args:

            data (string|dict):
                Jail configuration dict or jail name as string identifier.

            zfs (libzfs.ZFS): (optional)
                Inherit an existing libzfs.ZFS() instance from ancestor classes

            host (libioc.Host): (optional)
                Inherit an existing Host instance from ancestor classes

            logger (libioc.Logger): (optional)
                Inherit an existing Logger instance from ancestor classes
        """
        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)
        self.host = libioc.helpers_object.init_host(self, host)
        self._relative_hook_script_dir = "/.iocage"

        if isinstance(data, str):
            data = dict(id=data)

        if "id" in data.keys():
            data["id"] = self._resolve_name(data["id"])

        JailResource.__init__(
            self,
            jail=self,
            dataset=dataset,
            dataset_name=dataset_name,
            config_type=config_type,
            config_file=config_file,
            logger=self.logger,
            zfs=self.zfs,
            host=self.host,
            fstab=fstab,
            root_datasets_name=root_datasets_name
        )

        if not new and (("id" not in data) or (data["id"] is None)):
            try:
                # try to get the Jail name from it's dataset_name
                data["id"] = self.dataset_name.split("/").pop()
            except libioc.errors.JailUnknownIdentifier:
                pass

        self.config = libioc.Config.Jail.JailConfig.JailConfig(
            host=self.host,
            jail=self,
            logger=self.logger
        )
        self.config.clone(data)

        self.storage = self._class_storage(
            safe_mode=False,
            jail=self,
            logger=self.logger,
            zfs=self.zfs
        )

        if new is False:
            self.config.read(data=self.read_config(), skip_on_error=True)
            if self.config["id"] is None:
                self.config["id"] = self.dataset_name.split("/").pop()

    @property
    def state(self) -> 'libioc.JailState.JailState':
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
    def state(self, value: 'libioc.JailState.JailState') -> None:
        """
        Return the jails JailState object.

        A public interface to set a jails state. This behavior is part of a
        performance optimization when dealing with large numbers of jails.
        """
        object.__setattr__(self, '_state', value)

    @property
    def provisioner(self) -> 'libioc.Provisioning.prototype.Provisioner':
        """
        Return the jails Provisioner instance.

        The provisioner itself is going to interpret the jails configuration
        dynamically, so that the Provisioner instance can be memoized.
        """
        try:
            return self._provisioner
        except AttributeError:
            pass

        import libioc.Provisioning
        self._provisioner = libioc.Provisioning.Provisioner(jail=self)
        return self._provisioner

    def _init_state(self) -> 'libioc.JailState.JailState':
        state = libioc.JailState.JailState(
            self.identifier,
            logger=self.logger
        )
        self.state = state
        state.query()
        return state

    def start(
        self,
        quick: bool=False,
        passthru: bool=False,
        single_command: typing.Optional[str]=None,
        event_scope: typing.Optional['libioc.events.Scope']=None,
        dependant_jails_seen: typing.List['JailGenerator']=[],
        start_dependant_jails: bool=True
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """
        Start the jail.

        Args:

            quick (bool):

                Skip several operations that are not required when a jail
                was unchanged since its last start (for example when restarting
                it).

            passthru (bool):

                Execute commands in an interactive shell.

            single_command (str):

                When set the jail is launched non-persistent. The startup cycle
                reduces to the `prestart`, `command` and `poststop` hooks with
                the singe_command being executed in a /bin/sh context.

            event_scope (libioc.lib.events.Scope): (default=None)

                Provide an existing libiocage event scope or automatically
                create a new one instead.

            dependant_jails_seen (list[libioc.JailGenerator]):

                Jail depends can have circular dependencies. By passing a list
                of already started jails to the start command, iocage does not
                need to query their state, because they are known to be running
                already. This argument is internally used when starting a jails
                dependants recursively.

            start_dependant_jails (bool):

                When disabled, no dependant jails will be started.
        """
        self.require_jail_existing()
        self.require_jail_stopped()

        try:
            yield from self.config["resolver"].apply(
                jail=self,
                event_scope=event_scope
            )
        except Exception as e:
            raise e

        events: typing.Any = libioc.events
        jailLaunchEvent = events.JailLaunch(jail=self, scope=event_scope)

        dependant_jails_started: typing.List[JailGenerator] = []
        if start_dependant_jails is True:
            dependant_jails_seen.append(self)
            DependantsStartEvent = libioc.events.JailDependantsStart
            for event in self._start_dependant_jails(
                self.config["depends"],
                event_scope=event_scope,
                dependant_jails_seen=dependant_jails_seen
            ):
                if isinstance(event, DependantsStartEvent) is True:
                    if event.done and (event.error is None):
                        dependant_jails_started.extend(event.started_jails)
                yield event

        self._ensure_script_dir()
        jail_start_script_dir = "".join([
            self.root_dataset.mountpoint,
            self._relative_hook_script_dir
        ])
        if os.path.isdir(jail_start_script_dir) is False:
            os.makedirs(jail_start_script_dir, 0o755)

        exec_prestart: typing.List[str] = self._get_resource_limits_commands()
        exec_start: typing.List[str] = [
            f". {self._relative_hook_script_dir}/.env"
        ]
        exec_created: typing.List[str] = [
            f"echo \"export IOCAGE_JID=$IOCAGE_JID\" > {self.script_env_path}",
            "set -eu",
        ]
        exec_poststart: typing.List[str] = []

        if self.config["vnet"]:
            _created, _start = self._start_vimage_network()
            exec_created += _created
            exec_start += _start
            exec_start += self._configure_localhost_commands()
            exec_start += self._configure_routes_commands()
            if self.host.ipfw_enabled is True:
                exec_start.append("service ipfw onestop")

        if self.config["jail_zfs"] is True:
            share_storage = libioc.ZFSShareStorage.QueuingZFSShareStorage(
                jail=self,
                logger=self.logger
            )
            share_storage.mount_zfs_shares()
            exec_start += share_storage.read_commands("jail")
            exec_created += share_storage.read_commands()

        if self.config["exec_prestart"] is not None:
            exec_prestart += [self.config["exec_prestart"]]
        if self.config["exec_created"] is not None:
            exec_created += [self.config["exec_created"]]
        if self.config["exec_start"] is not None and (single_command is None):
            exec_start += [self.config["exec_start"]]
        if self.config["exec_poststart"] is not None:
            exec_poststart += [self.config["exec_poststart"]]

        self._write_hook_script(
            "prestart",
            self._wrap_hook_script_command_string(
                exec_prestart,
                ignore_errors=False
            )
        )
        self._write_hook_script(
            "created",
            self._wrap_hook_script_command_string(
                exec_created,
            )
        )
        self._write_hook_script(
            "start",
            self._wrap_hook_script_command_string(
                exec_start,
                jailed=True,
                ignore_errors=False
            )
        )
        self._write_hook_script(
            "poststart",
            self._wrap_hook_script_command_string([
                "set -eu",
                "/bin/echo running exec.created hook on the host",
                f"/bin/sh {self.get_hook_script_path('created')} 2>&1",
                "/bin/echo running exec.start hook in the jail",
                (
                    f"/usr/sbin/jexec {self.identifier} "
                    f"{self._relative_hook_script_dir}/start.sh"
                ),
                "/bin/echo running exec.poststart hook on the host",
            ] + exec_poststart)
        )

        yield jailLaunchEvent.begin()

        def _stop_failed_jail(
        ) -> typing.Generator['libioc.events.IocEvent', None, None]:
            jails_to_stop = [self]
            if start_dependant_jails is True:
                jails_to_stop.extend(list(reversed(dependant_jails_started)))
            for jail_to_stop in jails_to_stop:
                yield from jail_to_stop.stop(
                    force=True,
                    event_scope=jailLaunchEvent.scope
                )
        jailLaunchEvent.add_rollback_step(_stop_failed_jail)

        if self.is_basejail is True:
            self.storage_backend.apply(self.storage, self.release)

        if quick is False:
            self._save_autoconfig()

        try:
            self._prepare_stop()
            if single_command is None:
                stdout, stderr, returncode = self._launch_persistent_jail(
                    passthru=passthru
                )
            else:
                stdout, stderr, returncode = self._launch_single_command_jail(
                    single_command,
                    passthru=passthru
                )
            if returncode != 0:
                raise libioc.errors.JailLaunchFailed(
                    jail=self,
                    logger=self.logger
                )
        except libioc.errors.IocException as e:
            yield from jailLaunchEvent.fail_generator(e)
            raise e

        yield jailLaunchEvent.end(stdout=stdout)

    def _start_dependant_jails(
        self,
        terms: libioc.Filter.Terms,
        dependant_jails_seen: typing.List['JailGenerator'],
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:

        jailDependantsStartEvent = libioc.events.JailDependantsStart(
            jail=self,
            scope=event_scope
        )
        started_jails: typing.List[JailGenerator] = []

        yield jailDependantsStartEvent.begin()
        _depends = self.config["depends"]
        if len(_depends) == 0:
            yield jailDependantsStartEvent.skip("No dependant jails")
            return

        dependant_jails = sorted(
            libioc.Jails.JailsGenerator(
                filters=_depends,
                host=self.host,
                logger=self.logger,
                zfs=self.zfs
            ),
            key=lambda x: x.config["priority"]
        )

        for dependant_jail in dependant_jails:
            if dependant_jail == self:
                self.logger.warn(f"The jail {self.name} depends on itself")
                continue
            if dependant_jail in dependant_jails_seen:
                self.logger.spam(
                    f"Circular dependency {dependant_jail.name} - skipping"
                )
                continue
            dependant_jails_seen.append(dependant_jail)
            jailDependantStartEvent = libioc.events.JailDependantStart(
                jail=dependant_jail,
                scope=jailDependantsStartEvent.scope
            )
            yield jailDependantStartEvent.begin()
            dependant_jail.state.query()
            if dependant_jail.running is True:
                yield jailDependantStartEvent.skip("already running")
                continue

            try:
                yield from dependant_jail.start(
                    event_scope=jailDependantStartEvent.scope,
                    dependant_jails_seen=dependant_jails_seen
                )
            except libioc.errors.IocException as err:
                yield jailDependantStartEvent.fail(err)
                yield from jailDependantsStartEvent.fail_generator(err)
                raise err
            yield jailDependantStartEvent.end()

            started_jails.append(dependant_jail)

            # revert start of previously started dependants after failure
            def _revert_start(
                jail: JailGenerator
            ) -> typing.Callable[
                [],
                typing.Generator['libioc.events.IocEvent', None, None]
            ]:
                def revert_method() -> typing.Generator[
                    'libioc.events.IocEvent',
                    None,
                    None
                ]:
                    yield from jail.stop(force=True)
                return revert_method
            jailDependantsStartEvent.add_rollback_step(
                _revert_start(dependant_jail)
            )

        yield jailDependantsStartEvent.end(
            started_jails=started_jails
        )

    def _run_poststop_hook_manually(self) -> None:
        self.logger.debug("Running poststop hook manually")
        libioc.helpers.exec(self.get_hook_script_path("poststop"))

    def _wrap_jail_command(
        self,
        commands: typing.Optional[typing.List[str]]
    ) -> typing.List[str]:
        """Wrap a jail hook command for a host hook script."""
        if commands is None:
            return []

        EOF_IDENTIFIER = f"EOF{random.getrandbits(64)}"
        output: typing.List[str] = [
            "set -eu",
            "echo 'Executing jail start scripts'",
            "jexec -j {self.identifier} /bin/sh <<{EOF_IDENTIFIER}"
        ] + commands + [
            EOF_IDENTIFIER,
            "set +e"
        ]
        return output

    def _wrap_hook_script_command(
        self,
        commands: typing.Optional[typing.Union[str, typing.List[str]]],
        ignore_errors: bool=True,
        jailed: bool=False,
        write_env: bool=True
    ) -> typing.List[str]:

        if isinstance(commands, str):
            return [commands]
        elif commands is None:
            return []
        else:
            return commands

    def _wrap_hook_script_command_string(
        self,
        commands: typing.Optional[typing.Union[str, typing.List[str]]],
        ignore_errors: bool=True,
        jailed: bool=False,
        write_env: bool=True
    ) -> str:
        return "\n".join(self._wrap_hook_script_command(
            commands=commands,
            ignore_errors=ignore_errors,
            jailed=jailed,
            write_env=write_env
        ))

    def fork_exec(
        self,
        command: str,
        passthru: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None,
        start_dependant_jails: bool=True,
        dependant_jails_seen: typing.List['JailGenerator']=[],
        **temporary_config_override: typing.Any
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """
        Start a jail, run a command and shut it down immediately.

        Args:

            command (string):

                The command to execute in the jail.

            passthru (bool):

                Execute commands in an interactive shell.

            event_scope (libioc.lib.events.Scope): (default=None)

                Provide an existing libiocage event scope or automatically
                create a new one instead.

            dependant_jails_seen (list[libioc.JailGenerator]):

                Jail depends can have circular dependencies. By passing a list
                of already started jails to the start command, iocage does not
                need to query their state, because they are known to be running
                already. This argument is internally used when starting a jails
                dependants recursively.

            start_dependant_jails (bool):

                When disabled, no dependant jails will be started.

            **temporary_config_override (dict(str, any)):

                Other named arguments temporary override JailConfig properties.

                For example:

                    jail = libioc.JailGenerator("myjail")
                    events = jail.fork_exec("ifconfig", vnet=False)
                    print(list(events))
        """
        self.require_jail_existing()
        self.require_jail_stopped()

        original_config = self.config
        config_data = original_config.data

        for key, value in temporary_config_override.items():
            config_data[key] = value

        self.config = libioc.Config.Jail.JailConfig.JailConfig(
            host=self.host,
            jail=self,
            logger=self.logger
        )
        self.config.clone(original_config.data)

        try:
            fork_exec_events = JailGenerator.start(
                self,
                single_command=command,
                passthru=passthru,
                event_scope=event_scope,
                dependant_jails_seen=dependant_jails_seen,
                start_dependant_jails=start_dependant_jails
            )
            for event in fork_exec_events:
                yield event
        finally:
            self.config = original_config

    def _run_hook(self, hook_name: str) -> typing.Optional[
        libioc.helpers.CommandOutput
    ]:
        """
        Execute a jail hook.

        Hooks are executed during the start and stop process of the jail.
        """
        key = f"exec_{hook_name}"
        value = str(self.config.get(key, "/usr/bin/true"))

        if value == "/usr/bin/true":
            return None

        self.logger.verbose(
            f"Running {hook_name} hook for {self.humanreadable_name}"
        )

        lex = shlex.shlex(value)  # noqa: T484
        lex.whitespace_split = True
        command = list(lex)

        if (hook_name == "start") or (hook_name == "stop"):
            return self.exec(
                command,
                passthru=False
            )

        # ToDo: Deprecate and remove this method
        raise NotImplementedError("_run_hook only supports start/stop")

    def _ensure_script_dir(self) -> None:
        realpath = os.path.realpath(self.launch_script_dir)
        if realpath.startswith(self.dataset.mountpoint) is False:
            raise libioc.errors.SecurityViolationConfigJailEscape(
                file=realpath
            )
        if os.path.isdir(realpath) is False:
            os.makedirs(realpath, 0o755)

    def _prepare_stop(self) -> None:
        self._ensure_script_dir()

        exec_prestop = []
        exec_stop = []
        exec_poststop = self._teardown_mounts() + self._clear_resource_limits()

        # ToDo: self.config.get("exec_prestop", "")
        if self.config["exec_prestop"] is not None:
            exec_prestop.append(self.config["exec_prestop"])
        if self.config["exec_stop"] is not None:
            exec_stop.append(self.config["exec_stop"])
        if self.config["exec_poststop"] is not None:
            exec_poststop.append(self.config["exec_poststop"])

        if self.config["vnet"]:
            exec_poststop = self._stop_vimage_network() + exec_poststop

        if self.config["jail_zfs"] is True:
            share_storage = libioc.ZFSShareStorage.QueuingZFSShareStorage(
                jail=self,
                logger=self.logger
            )
            share_storage.umount_zfs_shares()
            exec_stop += share_storage.read_commands("jail")
            exec_poststop += share_storage.read_commands()

        if self.running and (os.path.isfile(self.script_env_path) is False):
            # when a jail was started from other iocage variants
            self._write_temporary_script_env()
            exec_poststop.append(f"rm \"{shlex.quote(self.script_env_path)}\"")

        self._write_hook_script(
            "prestop",
            self._wrap_hook_script_command_string(exec_prestop)
        )
        self._write_hook_script(
            "stop",
            self._wrap_hook_script_command_string(
                exec_stop,
                jailed=True,
                ignore_errors=True
            )
        )
        self._write_hook_script(
            "poststop",
            self._wrap_hook_script_command_string(
                exec_poststop,
                write_env=False,
                ignore_errors=True
            )
        )

    def stop(
        self,
        force: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None,
        log_errors: bool=True
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """
        Stop a jail.

        Args:

            force (bool): (default=False)
                Ignores failures and enforces teardown if True.

            event_scope (libioc.lib.events.Scope): (default=None)
                Provide an existing libiocage event scope or automatically
                create a new one instead.

            log_errors (bool): (default=True)
                When disabled errors are not passed to the logger. This is
                useful in scripted contexts when then stop operation was
                executed to enforce a defined jail state.
        """
        if force is False:
            self.require_jail_existing(log_errors=log_errors)
            self.require_jail_running(log_errors=log_errors)

        events: typing.Any = libioc.events
        jailDestroyEvent = events.JailDestroy(self, scope=event_scope)

        self._prepare_stop()

        yield jailDestroyEvent.begin()
        try:
            self._write_jail_conf(force=force)
            self._destroy_jail(log_errors=log_errors)
        except Exception as e:
            if force is True:
                yield jailDestroyEvent.skip()
                self.logger.debug(
                    "Manually executing prestop and poststop hooks"
                )
                try:
                    for hook_name in ["prestop", "poststop"]:
                        libioc.helpers.exec(
                            command=[self.get_hook_script_path(hook_name)]
                        )
                except Exception as e:
                    self.logger.warn(str(e))
            else:
                yield jailDestroyEvent.fail(e)
                raise e
        yield jailDestroyEvent.end()

        try:
            self.state.query()
        except Exception as e:
            if force is True:
                self.logger.warn(str(e))
            else:
                raise e

    def _write_temporary_script_env(self) -> None:
        self.logger.debug(
            f"Writing the hook script .env file {self.script_env_path}"
            f" for JID {self.jid}"
        )
        self._ensure_script_dir()
        with open(self.script_env_path, "w") as f:
            f.write(f"export IOCAGE_JID={self.jid}")

    def _write_jail_conf(self, force: bool=False) -> None:
        if force is True:
            stop_command = "/usr/bin/true"
        else:
            stop_command = (
                f"[ -f \"{self._relative_hook_script_dir}/stop.sh\" ]"
                " || exit 0; "
                f". {self._relative_hook_script_dir}/stop.sh"
            )

        content = "\n".join([
            self.identifier + " {",
            (
                "exec.prestop = "
                f"\"/bin/sh {self.get_hook_script_path('prestop')}\";"
            ), (
                "exec.poststop = "
                f"\"/bin/sh {self.get_hook_script_path('poststop')}\";"
            ), (
                f"exec.stop = \"{stop_command}\";"
            ), (
                f"exec.jail_user = {self._get_value('exec_jail_user')};"
            ),
            "}"
        ])
        self.logger.debug(f"Writing jail.conf file to {self._jail_conf_file}")
        with open(self._jail_conf_file, "w") as f:
            f.write(content)

    @property
    def _jail_conf_file(self) -> str:
        return f"{self.launch_script_dir}/jail.conf"

    def restart(
        self,
        shutdown: bool=False,
        force: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Restart the jail."""
        failed: bool = False
        jailRestartEvent = libioc.events.JailRestart(
            jail=self,
            scope=event_scope
        )
        jailShutdownEvent = libioc.events.JailShutdown(
            jail=self,
            scope=jailRestartEvent.scope
        )
        JailSoftShutdownEvent = libioc.events.JailSoftShutdown(
            jail=self,
            scope=jailRestartEvent.scope
        )
        jailStartEvent = libioc.events.JailStart(
            jail=self,
            scope=jailRestartEvent.scope
        )

        yield jailRestartEvent.begin()

        if shutdown is False:

            # soft stop
            yield JailSoftShutdownEvent.begin()
            try:
                self._run_hook("stop")
                yield JailSoftShutdownEvent.end()
            except libioc.errors.IocException:
                yield JailSoftShutdownEvent.fail(exception=False)

            # service start
            yield jailStartEvent.begin()
            try:
                self._run_hook("start")
                yield jailStartEvent.end()
            except libioc.errors.IocException:
                yield jailStartEvent.fail(exception=False)

        else:

            # full shutdown
            yield jailShutdownEvent.begin()
            try:
                for event in self.stop():
                    yield event
                yield jailShutdownEvent.end()
            except libioc.errors.IocException:
                failed = True
                yield jailShutdownEvent.fail(exception=False)
                if force is False:
                    # only continue when force is enabled
                    yield jailRestartEvent.fail(exception=False)
                    return

            # start
            yield jailStartEvent.begin()
            try:
                for event in self.start():
                    yield event
                yield jailStartEvent.end()
            except libioc.errors.IocException:
                failed = True
                yield jailStartEvent.fail(exception=False)

            # respond to failure
            if failed is True:
                yield jailRestartEvent.fail(exception=False)
                return

        yield jailRestartEvent.end()

    def destroy(
        self,
        force: bool=False,
        force_stop: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """
        Destroy a Jail and it's datasets.

        Args:

            force (bool): (default=False)
                This flag enables whether an existing jail should be shut down
                before destroying the dataset. By default destroying a jail
                requires it to be stopped.

            force_stop (bool): (default=False)
                A jail is force stopped when either the force_stop argument was
                set or the force option was enabled and the jail is running.
                When being enabled the argument invokes a full stop before
                destroying the jail.
        """
        self.state.query()

        if event_scope is None:
            event_scope = libioc.events.Scope()

        _stop_jail = force_stop
        if force is False:
            self.require_jail_stopped()
        else:
            _stop_jail = (self.running is True)

        if _stop_jail is True:
            try:
                stop_events = JailGenerator.stop(
                    self,
                    force=True,
                    event_scope=event_scope,
                    log_errors=(force_stop is False)
                )
                for event in stop_events:
                    yield event
            except libioc.lib.errors.JailDestructionFailed:
                pass

        zfsDatasetDestroyEvent = libioc.events.ZFSDatasetDestroy(
            dataset=self.dataset,
            scope=event_scope
        )

        yield zfsDatasetDestroyEvent.begin()
        try:
            self.zfs.delete_dataset_recursive(self.dataset)
        except Exception as e:
            zfsDatasetDestroyEvent.fail(e)
            raise e
        yield zfsDatasetDestroyEvent.end()

    def rename(
        self,
        new_name: str,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """
        Change the name of a jail.

        Args:

            new_name (str):
                The new name of a jail. It might not be used by another Jail
                and must differ from the current name.
        """
        self.require_jail_existing()
        self.require_jail_stopped()
        self.require_storage_backend()

        if libioc.helpers.validate_name(new_name) is False:
            raise libioc.errors.InvalidJailName(
                name=new_name,
                logger=self.logger
            )

        current_id = self.config["id"]
        current_mountpoint = self.dataset.mountpoint

        jailRenameEvent = libioc.events.JailRename(
            jail=self,
            current_name=current_id,
            new_name=new_name,
            scope=event_scope
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
                new_name=new_name,
                event_scope=jailRenameEvent.scope
            )
            for event in events:
                yield jailRenameEvent.child_event(event)
                if event.error is not None:
                    raise event.error
        except BaseException as e:
            yield jailRenameEvent.fail(e)
            raise e

        # Update fstab to the new dataset
        fstab_path_events = self._update_fstab_paths(
            current_mountpoint,
            event_scope=jailRenameEvent.scope
        )
        for event in fstab_path_events:
            yield event

        yield jailRenameEvent.end()

    def _update_fstab_paths(
        self,
        old_path_prefix: str,
        new_path_prefix: typing.Optional[str]=None,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """
        Update a path in the whole fstab file.

        When no new_path_prefix is provided, the jail's root dataset is used.
        """
        if new_path_prefix is None:
            _new_path_prefix = self.dataset.mountpoint
        else:
            _new_path_prefix = new_path_prefix

        jailFstabUpdateEvent = libioc.events.JailFstabUpdate(
            jail=self,
            scope=event_scope
        )
        yield jailFstabUpdateEvent.begin()
        try:
            self.fstab.read_file()
            self.fstab.replace_path(
                old_path_prefix,
                _new_path_prefix
            )
            self.fstab.save()
            yield jailFstabUpdateEvent.end()
        except BaseException as e:
            yield jailFstabUpdateEvent.fail(e)
            raise e

    def create(
        self,
        resource: typing.Optional[typing.Union[
            'JailGenerator',
            'libioc.Release.ReleaseGenerator',
            str
        ]]=None
    ) -> None:
        """
        Create a Jail from a given Resource.

        Args:

            resource (Jail or Release):
                The (new) jail is created from this resource.
                If no resource is specified, an empty dataset will be created
        """
        if isinstance(resource, str):
            resource = libioc.Release(resource)

        if isinstance(resource, JailGenerator):
            self.create_from_template(template=resource)
        elif isinstance(resource, libioc.Release.ReleaseGenerator):
            self.create_from_release(release=resource)
        else:
            self.create_from_scratch()

        self._ensure_script_dir()

    def create_from_scratch(
        self
    ) -> None:
        """Create a new jail without any root dataset content."""
        self._create_skeleton()

    def create_from_release(
        self,
        release: 'libioc.Release.ReleaseGenerator'
    ) -> None:
        """
        Create a Jail from a Release.

        Args:

            resource (Release):
                The jail is created from the provided resource.
                This can be either another Jail or a Release.
        """
        if release.fetched is False:
            raise libioc.errors.ReleaseNotFetched(
                name=release.name,
                logger=self.logger
            )

        self.config["release"] = release.full_name
        self._create_from_resource(release)

    def create_from_template(
        self,
        template: 'JailGenerator'
    ) -> None:
        """Create a Jail from a template Jail."""
        template.require_jail_is_template()
        existing_config_keys = list(self.config.keys())
        for key in template.config.keys():
            if key in (["id", "name", "template"] + existing_config_keys):
                continue
            self.config[key] = template.config[key]
        self.config['release'] = template.release.full_name
        self.config['basejail'] = template.config['basejail']
        self.config['basejail_type'] = template.config['basejail_type']
        self._create_from_resource(template)

    def promote(self) -> None:
        """Promote all datasets of the jail."""
        self.zfs.promote_dataset(self.dataset, logger=self.logger)

    def clone_from_jail(
        self,
        source_jail: 'JailGenerator',
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Create a Jail from another Jail."""
        self.autoset_dataset_name()
        if event_scope is None:
            event_scope = libioc.events.Scope()
        yield from source_jail.clone_to_dataset(
            self.dataset_name,
            event_scope=event_scope
        )

        self.config.clone(source_jail.config.data, skip_on_error=True)
        self.save()

        fstab_update_generator = self._update_fstab_paths(
            source_jail.root_dataset.mountpoint,
            event_scope=event_scope
        )
        for event in fstab_update_generator:
            yield event

    def clone_to_dataset(
        self,
        destination_dataset_name: str,
        delete_existing: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Clones the jails dataset to another dataset with the given name."""
        jailCloneEvent = libioc.events.JailClone(
            jail=self,
            scope=event_scope
        )
        yield jailCloneEvent.begin()

        try:
            self.zfs.clone_dataset(
                source=self.dataset,
                target=destination_dataset_name,
                delete_existing=delete_existing
            )
        except Exception as e:
            err = libioc.errors.ZFSException(
                *e.args,
                logger=self.logger
            )
            yield jailCloneEvent.fail(err)
            raise err

        yield jailCloneEvent.end()

    def _create_skeleton(self) -> None:

        if self.config["id"] is None:
            self.config["id"] = str(libioc.helpers.get_random_uuid())

        self.require_jail_not_existing()

        self.logger.verbose(
            f"Creating jail '{self.config['id']}'"
        )

        for key, value in self.config.data.items():
            msg = f"{key} = {value}"
            self.logger.spam(msg, indent=1)

        self.create_resource()

    def _create_from_resource(
        self,
        resource: 'libioc.Resource.Resource'
    ) -> None:

        self._create_skeleton()

        backend = self.storage_backend
        if backend is not None:
            backend.setup(self.storage, resource)

        self._update_fstab()
        self.save()

    @property
    def is_basejail(self) -> bool:
        """
        Return True if a Jail is a basejail.

        If this is the case, parts of the jails dataset will be mounted
        from its release or upstream Jail (for example a Template)
        """
        return self.config.get("basejail", False) is True

    @property
    def storage_backend(self) -> libioc.Storage.Storage:
        """
        Return the jail storage abstraction class.

        Returns the class that represents the jails storage backend according
        to its configuration.
        """
        if not self.is_basejail:
            return libioc.Storage.Standalone.StandaloneJailStorage
        if self.config["basejail_type"] == "nullfs":
            return libioc.Storage.NullFSBasejail.NullFSBasejailStorage
        if self.config["basejail_type"] == "zfs":
            return libioc.Storage.ZFSBasejail.ZFSBasejailStorage

    def save(self) -> None:
        """Permanently save a jail's configuration."""
        self._write_config(self.config.data)
        self._save_autoconfig()

    def _save_autoconfig(self) -> None:
        """Save auto-generated files."""
        self.rc_conf.save()
        self._update_fstab()

    def _update_fstab(self) -> None:
        if self.config["basejail_type"] == "nullfs":
            self.fstab.release = self.release
        else:
            self.fstab.release = None

        self.fstab.read_file()
        self.fstab.save()

    def exec(
        self,
        command: typing.List[str],
        env: typing.Dict[str, str]={},
        passthru: bool=False,
        **kwargs: typing.Any
    ) -> libioc.helpers.CommandOutput:
        """
        Execute a command in a running jail.

        command (list):
            A list of command and it's arguments

            Example: ["/usr/bin/whoami"]

        env (dict):
            The dictionary may contain env variables that will be forwarded to
            the executed jail command.

        passthru (bool): (default=False)
            When enabled the commands stdout and stderr are directory forwarded
            to the attached terminal. The results will not be included in the
            CommandOutput, so that (None, None, <returncode>) is returned.
        """
        command = ["/usr/sbin/jexec", str(self.jid)] + command

        command_env = self.env
        for env_key, env_value in env.items():
            command_env[env_key] = env_value

        stdout, stderr, returncode = self._exec_host_command(
            command,
            env=command_env,
            passthru=passthru
        )

        return stdout, stderr, returncode

    def passthru(
        self,
        command: typing.List[str],
        env: typing.Optional[typing.Dict[str, str]]=None
    ) -> libioc.helpers.CommandOutput:
        """
        Execute a command in a started jail and passthrough STDIN and STDOUT.

        command (list):
            A list of command and it's arguments

            Example: ["/bin/sh"]
        """
        if isinstance(command, str):
            command = [command]

        return self._exec_host_command(
            command=[
                "/usr/sbin/jexec",
                str(self.jid)
            ] + command,
            passthru=True,
            env=env
        )

    def exec_console(
        self
    ) -> libioc.helpers.CommandOutput:
        """Shortcut to drop into a shell of a started jail."""
        self.require_jail_running()
        return self.passthru(
            ["/usr/bin/login"] + self.config["login_flags"]
        )

    def _destroy_jail(self, log_errors: bool=True) -> None:

        stdout, stderr, returncode = self._exec_host_command(
            [
                "/usr/sbin/jail",
                "-v",
                "-r",
                "-f",
                self._jail_conf_file,
                self.identifier
            ],
            passthru=False,
            env=self.env
        )

        if returncode > 0:
            raise libioc.errors.JailDestructionFailed(
                jail=self,
                logger=(self.logger if log_errors else None)
            )

    @property
    def _dhcp_enabled(self) -> bool:
        """Return True if any ip4_addr uses DHCP."""
        if self.config["ip4_addr"] is None:
            return False

        return ("dhcp" in self.config["ip4_addr"].networks) is True

    @property
    def devfs_ruleset(self) -> libioc.DevfsRules.DevfsRuleset:
        """
        Return the number of the jail's devfs ruleset.

        When a new combination of the base ruleset specified in
        jail.config["devfs_ruleset"] and rules automatically added by iocage
        appears, the according rule is automatically created and added to the
        /etc/devfs.rules file on the host

        Users may reference a rule by numeric identifier or name. This numbers
        are automatically selected, so it's advisable to use names.1
        """
        try:
            configured_devfs_ruleset = self.host.devfs.find_by_number(
                int(self.config["devfs_ruleset"])
            )
        except ValueError:
            configured_devfs_ruleset = self.host.devfs.find_by_name(
                self.config["devfs_ruleset"]
            )

        devfs_ruleset = libioc.DevfsRules.DevfsRuleset()
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

    @property
    def _launch_command(self) -> typing.List[str]:

        command = ["/usr/sbin/jail", "-c"]

        if self.config["vnet"]:
            command.append("vnet")
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
            f"allow.sysvipc={self._get_value('allow_sysvipc')}",
            f"exec.prestart=\"{self.get_hook_script_path('prestart')}\"",
            f"exec.prestop=\"{self.get_hook_script_path('prestop')}\"",
            f"exec.poststop=\"{self.get_hook_script_path('poststop')}\"",
            f"exec.jail_user={self._get_value('exec_jail_user')}"
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
            f"allow.mount.fdescfs={self._get_value('allow_mount_fdescfs')}",
            f"allow.mount.zfs={self._allow_mount_zfs}",
            f"allow.quotas={self._get_value('allow_quotas')}",
            f"allow.socket_af={self._get_value('allow_socket_af')}",
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

        command += ["allow.dying"]
        return command

    def _launch_persistent_jail(
        self,
        passthru: bool
    ) -> libioc.helpers.CommandOutput:
        command = self._launch_command + [
            "persist",
            f"exec.poststart=\"{self.get_hook_script_path('poststart')}\""
        ]

        stdout, stderr, returncode = self._exec_host_command(
            command=command,
            passthru=passthru,
            env=self.env
        )
        if returncode > 0:
            self.logger.verbose(
                f"Jail '{self.humanreadable_name}' was not started"
            )
            return stdout, stderr, returncode

        self.state.query()
        self.logger.verbose(
            f"Jail '{self.humanreadable_name}' started with JID {self.jid}"
        )

        return stdout, stderr, returncode

    def _exec_host_command(
        self,
        command: typing.List[str],
        passthru: bool,
        env: typing.Optional[typing.Dict[str, str]]=None
    ) -> libioc.helpers.CommandOutput:
        try:
            if passthru is True:
                return libioc.helpers.exec_passthru(
                    command,
                    logger=self.logger,
                    env=env
                )
            else:
                exec_events = libioc.helpers.exec_generator(
                    command,
                    logger=self.logger,
                    env=env
                )
                try:
                    while True:
                        self.logger.spam(
                            next(exec_events).decode("UTF-8"),
                            indent=1
                        )
                except StopIteration as return_statement:
                    output: libioc.helpers.CommandOutput
                    output = return_statement.value
                    return output
        except (KeyboardInterrupt, SystemExit):
            raise libioc.errors.JailExecutionAborted(
                jail=self,
                logger=None
            )

    def _launch_single_command_jail(
        self,
        jail_command: str,
        passthru: bool
    ) -> libioc.helpers.CommandOutput:
        command = self._launch_command + [
            "nopersist",
            f"exec.poststart=\"{self.get_hook_script_path('host_command')}\"",
            "command=/usr/bin/true"
        ]

        _identifier = str(shlex.quote(self.identifier))
        _jls_command = f"/usr/sbin/jls -j {_identifier} jid"
        self._write_hook_script("host_command", "\n".join(
            [
                f"IOCAGE_JID=$({_jls_command} 2>&1 || echo -1)",
                "set -e",
                f"/bin/sh {self.get_hook_script_path('created')}",
                (
                    f"/usr/sbin/jexec {self.identifier} "
                    f"{self._relative_hook_script_dir}/command.sh"
                    " 2>&1"
                ),
                f"/bin/sh {self.get_hook_script_path('poststop')}"
            ]
        ))

        _ipfw_enabled = self.host.ipfw_enabled
        self._write_hook_script("command", "\n".join(
            (["set +e", "service ipfw onestop"] if _ipfw_enabled else []) + [
                "set -e",
                f". {self._relative_hook_script_dir}/start.sh",
                jail_command,
            ]
        ))

        stdout, stderr, returncode = self._exec_host_command(
            command=command,
            passthru=passthru,
            env=self.env
        )

        if returncode > 0:
            message = f"Jail {self.humanreadable_name} command failed."
        else:
            message = f"Jail {self.humanreadable_name} command finished."
        self.logger.verbose(message)

        return stdout, stderr, returncode

    def _get_value(self, key: str) -> str:
        """Return jail command consumable config value string."""
        return str(libioc.helpers.to_string(
            self.config[key],
            true="1",
            false="0",
            none=""
        ))

    @property
    def networks(self) -> typing.List[libioc.Network.Network]:
        """Return the list of a jails configured networks."""
        networks = []

        nics = self.config["interfaces"]

        if nics is None:
            return []

        for nic in nics:

            bridge = nics[nic]

            try:
                ipv4_addresses = self.config["ip4_addr"][nic]
            except (KeyError, TypeError):
                ipv4_addresses = []

            try:
                ipv6_addresses = self.config["ip6_addr"][nic]
            except (KeyError, TypeError):
                ipv6_addresses = []

            net = libioc.Network.Network(
                jail=self,
                nic=nic,
                ipv4_addresses=ipv4_addresses,
                ipv6_addresses=ipv6_addresses,
                bridge=bridge,
                logger=self.logger
            )
            networks.append(net)

        return networks

    def _write_hook_script(self, hook_name: str, command_string: str) -> None:
        file = self.get_hook_script_path(hook_name)
        existed = os.path.isfile(file)
        if hook_name in ["created", "poststart", "prestop"]:
            _identifier = str(shlex.quote(self.identifier))
            _jls_command = f"/usr/sbin/jls -j {_identifier} jid"
            command_string = (
                "IOCAGE_JID="
                f"$({_jls_command} 2>&1 || echo -1)"
                "\n" + command_string
            )
        if hook_name == "poststop":
            command_string = (
                "[ -f \"$(dirname $0)/.env\" ] && "
                ". \"$(dirname $0)/.env\""
                "\n"
            ) + command_string
        with open(file, "w") as f:
            f.write("\n".join([
                "#!/bin/sh",
                command_string
            ]))
        if existed is False:
            shutil.chown(file, "root", "wheel")
            os.chmod(file, 0o755)  # nosec: executable script

    @property
    def launch_script_dir(self) -> str:
        """Return the launch-scripts directory path of the jail."""
        return f"{self.jail.dataset.mountpoint}/launch-scripts"

    @property
    def script_env_path(self) -> str:
        """Return the absolute path to the jail script env file."""
        return f"{self.launch_script_dir}/.env"

    def get_hook_script_path(self, hook_name: str) -> str:
        """Return the absolute path to the hook script file."""
        return f"{self.jail.launch_script_dir}/{hook_name}.sh"

    def _start_vimage_network(self) -> typing.Tuple[
        'libioc.Network.CreatedCommandList',
        'libioc.Network.JailCommandList'
    ]:
        self.logger.debug("Starting VNET/VIMAGE")

        created: typing.List[str] = []
        start: typing.List[str] = []

        for network in self.networks:
            _created, _start = network.setup()

            created += _created
            start += _start

        return created, start

    def _stop_vimage_network(self) -> typing.List[str]:
        commands: typing.List[str] = []
        for network in self.networks:
            commands += network.teardown()
        return commands

    def _configure_localhost_commands(self) -> typing.List[str]:
        return ["/sbin/ifconfig lo0 localhost"]

    def _get_resource_limits_commands(self) -> typing.List[str]:

        commands: typing.List[str] = []

        if self.config['rlimits'] is False:
            self.logger.verbose("Resource limits disabled")
            return commands

        for key in libioc.Config.Jail.Properties.ResourceLimit.properties:
            try:
                rlimit_prop = self.config[key]
                if rlimit_prop.is_unset is True:
                    continue
            except (KeyError, AttributeError):
                continue
            commands.append(" ".join([
                "/usr/bin/rctl",
                "-a",
                f"jail:{self.identifier}:{key}:{rlimit_prop.limit_string}"
            ]))
        return commands

    def _clear_resource_limits(self) -> typing.List[str]:
        if self.config['rlimits'] is False:
            return []
        self.logger.verbose("Clearing resource limits")
        return [f"/usr/bin/rctl -r jail:{self.identifier} 2>/dev/null || true"]

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

    def _configure_routes_commands(self) -> typing.List[str]:

        defaultrouter = self.config["defaultrouter"]
        defaultrouter6 = self.config["defaultrouter6"]

        commands: typing.List[str] = []

        if defaultrouter is not None:
            commands += list(defaultrouter.apply(jail=self))

        if defaultrouter6 is not None:
            commands += list(defaultrouter6.apply(jail=self))

        if len(commands) == 0:
            self.logger.spam("no static routes configured")

        return commands

    def require_jail_is_template(self, log_errors: bool=True) -> None:
        """Raise JailIsTemplate exception if the jail is a template."""
        if self.config['template'] is False:
            raise libioc.errors.JailNotTemplate(
                jail=self,
                logger=(self.logger if log_errors else None)
            )

    def require_storage_backend(self, log_errors: bool=True) -> None:
        """Raise if the jail was not initialized with a storage backend."""
        if self.storage_backend is None:
            raise Exception("The jail has no storage backend.")

    def require_jail_not_template(self, log_errors: bool=True) -> None:
        """Raise JailIsTemplate exception if the jail is a template."""
        if self.config['template'] is True:
            raise libioc.errors.JailIsTemplate(
                jail=self,
                logger=(self.logger if log_errors else None)
            )

    def require_jail_not_existing(self, log_errors: bool=True) -> None:
        """Raise JailAlreadyExists exception if the jail already exists."""
        if self.exists:
            raise libioc.errors.JailAlreadyExists(
                jail=self,
                logger=(self.logger if log_errors else None)
            )

    def require_jail_existing(self, log_errors: bool=True) -> None:
        """Raise JailDoesNotExist exception if the jail does not exist."""
        if not self.exists:
            raise libioc.errors.JailDoesNotExist(
                jail=self,
                logger=(self.logger if log_errors else None)
            )

    def require_jail_stopped(self, log_errors: bool=True) -> None:
        """Raise JailAlreadyRunning exception if the jail is running."""
        if self.running is not False:
            raise libioc.errors.JailAlreadyRunning(
                jail=self,
                logger=(self.logger if log_errors else None)
            )

    def require_jail_running(self, log_errors: bool=True) -> None:
        """Raise JailNotRunning exception if the jail is stopped."""
        if not self.running:
            raise libioc.errors.JailNotRunning(
                jail=self,
                logger=(self.logger if log_errors else None)
            )

    def _teardown_mounts(self) -> typing.List[str]:

        commands: typing.List[str] = []

        fstab_destinations = [line["destination"] for line in self.fstab]
        system_mountpoints = list(filter(
            os.path.isdir,
            map(
                self._get_absolute_path_from_jail_asset,
                [
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

        mountpoints = fstab_destinations + system_mountpoints

        commands.append(" ".join(libioc.helpers.umount_command(
            mountpoints,
            force=True,
            ignore_error=True
        )))

        commands.append(" ".join(libioc.helpers.umount_command(
            ["-a", "-F", self.fstab.path],
            force=True,
            ignore_error=True
        )))

        if self.config.legacy is True:
            commands.append(" | ".join([
                "mount -t nullfs",
                "sed -r 's/(.+) on (.+) \\(nullfs, .+\\)$/\\2/'",
                f"grep '^{self.root_dataset.mountpoint}/'",
                "xargs umount"
            ]))

        return commands

    def _get_absolute_path_from_jail_asset(
        self,
        value: str
    ) -> libioc.Types.AbsolutePath:

        return libioc.Types.AbsolutePath(f"{self.root_path}{value}")

    def _resolve_name(self, text: str) -> str:

        if (text is None) or (len(text) == 0):
            raise libioc.errors.JailNotSupplied(logger=self.logger)

        resource_selector = libioc.ResourceSelector.ResourceSelector(
            name=text,
            logger=self.logger
        )

        root_datasets = resource_selector.filter_datasets(self.host.datasets)

        for datasets_key, datasets in root_datasets.items():
            for dataset in list(datasets.jails.children):
                dataset_name = str(
                    dataset.name[(len(datasets.jails.name) + 1):]
                )
                humanreadable_name = libioc.helpers.to_humanreadable_name(
                    dataset_name
                )
                possible_names = [dataset_name, humanreadable_name]
                if resource_selector.name in possible_names:
                    return dataset_name

        raise libioc.errors.JailNotFound(text, logger=self.logger)

    @property
    def name(self) -> str:
        """Return the configured jail id."""
        return str(self.config["id"])

    @property
    def full_name(self) -> str:
        """
        Return the full identifier of a jail.

        When more than one root dataset is managed by iocage, the full source
        and name are returned. Otherwise just the name.

        For example `mydataset/jailname` or just `jailname`.
        """
        if len(self.host.datasets) > 1:
            return f"{self.source}/{self.name}"
        else:
            return self.name

    @property
    def humanreadable_name(self) -> str:
        """
        Return the human-readable identifier to print in logs and CLI output.

        Whenever a Jail is found to have a UUID as identifier,
        a shortened string of the first 8 characters is returned
        """
        try:
            return str(libioc.helpers.to_humanreadable_name(self.name))
        except KeyError:
            raise libioc.errors.JailUnknownIdentifier(
                logger=self.logger
            )

    @property
    def stopped(self) -> bool:
        """Return True if a jail is stopped."""
        return self.running is not True

    @property
    def running(self) -> bool:
        """Return True if a jail is running."""
        return self.jid is not None

    @property
    def jid(self) -> typing.Optional[int]:
        """Return a jails JID if it is running or None."""
        if "_state" not in object.__dir__(self):
            # force state init when jid was requested
            self._init_state()

        try:
            return int(self.state["jid"])
        except (KeyError, TypeError):
            return None

    @property
    def env(self) -> typing.Dict[str, str]:
        """Return the environment variables for hook scripts."""
        jail_env: typing.Dict[str, str]
        if self.config["exec_clean"] is False:
            jail_env = os.environ.copy()
        else:
            jail_env = {}

        for prop in self.config.all_properties:
            prop_name = f"IOCAGE_{prop.replace('.', '_').upper()}"
            jail_env[prop_name] = str(self.config[prop])

        jail_env["IOCAGE_JAIL_PATH"] = self.root_dataset.mountpoint
        jail_env["IOCAGE_JID"] = str(self.jid)

        return jail_env

    @property
    def identifier(self) -> str:
        """Return the jail id used in snapshots, jls, etc."""
        config = object.__getattribute__(self, 'config')
        return f"{self.source}-{config['id']}"

    @property
    def release(self) -> 'libioc.Release.ReleaseGenerator':
        """Return the libioc.Release instance linked with the jail."""
        return libioc.Release.ReleaseGenerator(
            name=self.config["release"],
            root_datasets_name=self.root_datasets_name,
            logger=self.logger,
            host=self.host,
            zfs=self.zfs
        )

    @property
    def release_snapshot(self) -> libzfs.ZFSSnapshot:
        """Return the matching release verion snaphsot."""
        snapshot: libzfs.ZFSSnapshot = self.release.current_snapshot
        return snapshot

    def __getattribute__(self, key: str) -> typing.Any:
        """Get an attribute from the jail, state or configuration."""
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

    def __dir__(self) -> typing.List[str]:
        """Get all accessible properties of a jail."""
        properties = set()
        for prop in dict.__dir__(self):
            if not prop.startswith("_"):
                properties.add(prop)
        return list(properties)

    def __eq__(self, other: typing.Any) -> bool:
        """
        Compare two Jails by their name.

        The jail is identified by its full name, including the iocage root
        dataset name in case there is more than one enabled on the host.
        """
        if isinstance(other, JailGenerator):
            return False
        return (self.full_name == other.full_name) is True


class Jail(JailGenerator):
    """Synchronous wrapper of JailGenerator."""

    def start(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> typing.List['libioc.events.IocEvent']:
        """Start the jail."""
        return list(JailGenerator.start(self, *args, **kwargs))

    def stop(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> typing.List['libioc.events.IocEvent']:
        """Stop the jail."""
        return list(JailGenerator.stop(self, *args, **kwargs))

    def rename(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> typing.List['libioc.events.IocEvent']:
        """Rename the jail."""
        return list(JailGenerator.rename(self, *args, **kwargs))

    def _update_fstab_paths(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> typing.List['libioc.events.IocEvent']:
        """Update a path in the whole fstab file."""
        return list(JailGenerator._update_fstab_paths(self, *args, **kwargs))

    def destroy(  # noqa: T484
        self,
        force: bool=False
    ) -> typing.List['libioc.events.IocEvent']:
        """
        Destroy a Jail and it's datasets.

        Args:

            force (bool): (default=False)
                This flag enables whether an existing jail should be shut down
                before destroying the dataset. By default destroying a jail
                requires it to be stopped.
        """
        return list(JailGenerator.destroy(self, force=force))

    def fork_exec(  # noqa: T484
        self,
        command: str,
        passthru: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None,
        dependant_jails_seen: typing.List['JailGenerator']=[],
        start_dependant_jails: bool=True,
        **temporary_config_override
    ) -> str:
        """
        Start a jail, run a command and shut it down immediately.

        Args:

            command (string):

                The command to execute in the jail.

            passthru (bool):

                Execute commands in an interactive shell.

            event_scope (libioc.lib.events.Scope): (default=None)

                Provide an existing libiocage event scope or automatically
                create a new one instead.

            dependant_jails_seen (list[libioc.JailGenerator]):

                Jail depends can have circular dependencies. By passing a list
                of already started jails to the start command, iocage does not
                need to query their state, because they are known to be running
                already. This argument is internally used when starting a jails
                dependants recursively.

            start_dependant_jails (bool):

                When disabled, no dependant jails will be started.

            **temporary_config_override (dict(str, any)):

                Other named arguments temporary override JailConfig properties.

                For example:

                    jail = libioc.JailGenerator("myjail")
                    events = jail.fork_exec("ifconfig", vnet=False)
                    print(list(events))
        """
        events = JailGenerator.fork_exec(
            self,
            command=command,
            passthru=passthru,
            event_scope=event_scope,
            dependant_jails_seen=dependant_jails_seen,
            start_dependant_jails=start_dependant_jails,
            **temporary_config_override
        )
        for event in events:
            if isinstance(event, libioc.events.JailLaunch) and event.done:
                return str(event.stdout)
