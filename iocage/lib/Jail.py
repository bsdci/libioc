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
"""iocage Jail module."""
import typing
import os
import random
import subprocess  # nosec: B404
import shlex
import shutil

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
import iocage.lib.ResourceSelector
import iocage.lib.Config.Jail.File.Fstab


class JailResource(
    iocage.lib.LaunchableResource.LaunchableResource,
    iocage.lib.VersionedResource.VersionedResource
):
    """Resource that represents a jail."""

    _jail: 'JailGenerator'
    _fstab: 'iocage.lib.Config.Jail.File.Fstab.Fstab'
    host: 'iocage.lib.Host.HostGenerator'
    root_datasets_name: typing.Optional[str]

    def __init__(  # noqa: T484
        self,
        host: 'iocage.lib.Host.HostGenerator',
        jail: typing.Optional['JailGenerator']=None,
        root_datasets_name: typing.Optional[str]=None,
        **kwargs
    ) -> None:

        self.host = iocage.lib.helpers.init_host(self, host)
        self.root_datasets_name = root_datasets_name

        if jail is not None:
            self._jail = jail

        iocage.lib.LaunchableResource.LaunchableResource.__init__(
            self,
            **kwargs  # noqa: T484
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
    def fstab(self) -> 'iocage.lib.Config.Jail.File.Fstab.Fstab':
        """
        Memoized fstab wrapper of a Jail.

        The fstab file is stored in the top level of a Jails dataset
        """
        try:
            return self._fstab
        except AttributeError:
            pass

        jail = self.jail
        release = None if ("release" not in jail.__dir__()) else jail.release
        fstab = iocage.lib.Config.Jail.File.Fstab.Fstab(
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
            raise iocage.lib.errors.JailUnknownIdentifier()

        if self.root_datasets_name is None:
            base_name = self.host.datasets.main.jails.name
        else:
            base_name = self.host.datasets.__getitem__(
                self.root_datasets_name
            ).jails.name
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
            out = self.jail.config[key]
            return out
        except KeyError:
            pass

        return iocage.lib.Resource.Resource.get(self, key)


class JailGenerator(JailResource):
    """
    iocage unit orchestrates a jail's configuration and manages state.

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
    _relative_hook_script_dir: str

    def __init__(  # noqa: T484
        self,
        data: typing.Union[str, typing.Dict[str, typing.Any]]={},
        root_datasets_name: typing.Optional[str]=None,
        zfs: typing.Optional['iocage.lib.ZFS.ZFS']=None,
        host: typing.Optional['iocage.lib.Host.Host']=None,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None,
        new: bool=False,
        **resource_args
    ) -> None:
        """
        Initialize a Jail.

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
        self._relative_hook_script_dir = "/usr/local/iocage-scripts"

        if isinstance(data, str):
            data = {
                "id": data
            }

        if "id" in data.keys():
            data["id"] = self._resolve_name(data["id"])

        JailResource.__init__(
            self,
            jail=self,
            root_datasets_name=root_datasets_name,
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
    def state(self, value: iocage.lib.JailState) -> None:
        """
        Return the jails JailState object.

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
        passthru: bool=False,
        single_command: typing.Optional[str]=None
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """
        Start the jail.

        Args:

            quick (bool):

                Skip several operations that are not required when a jail
                was unchanged since its last start (for example when restarting
                it).

            passthru (bool):

                Execute commands in an interactive shell.

            single_command (bool):

                When set the jail is launched non-persistent. The startup cycle
                reduces to the `prestart`, `command` and `poststop` hooks with
                the singe_command being executed in a /bin/sh context.
        """
        self.require_jail_existing()
        self.require_jail_stopped()

        release = self.release

        events: typing.Any = iocage.lib.events
        jailLaunchEvent = events.JailLaunch(jail=self)
        JailZfsShareMount = events.JailZfsShareMount(jail=self)

        self._ensure_script_dir()
        jail_start_script_dir = "/".join([
            self.root_dataset.mountpoint,
            self._relative_hook_script_dir
        ])
        if os.path.isdir(jail_start_script_dir) is False:
            os.mkdir(jail_start_script_dir, 0o755)

        exec_prestart: typing.List[str] = []
        exec_start: typing.List[str] = []
        exec_poststart: typing.List[str] = []

        if self.config["vnet"]:
            _pre, _start, _poststart = self._start_vimage_network()
            exec_prestart += _pre
            exec_start += _start
            exec_start += self._configure_localhost_commands()
            exec_start += self._configure_routes_commands()
            if self.host.ipfw_enabled is True:
                exec_start.append("service ipfw onestop")
            exec_poststart += _poststart

        if self.config["exec_prestart"] is not None:
            exec_prestart += [self.config["exec_prestart"]]
        if self.config["exec_start"] is not None:
            exec_start += [self.config["exec_start"]]
        if self.config["exec_poststart"] is not None:
            exec_poststart += [self.config["exec_poststart"]]

        exec_prestart = self._wrap_hook_script_command_string(
            exec_prestart,
            ignore_errors=False
        )
        exec_start = self._wrap_hook_script_command_string(
            exec_start,
            jailed=True,
            ignore_errors=False
        )
        exec_poststart = self._wrap_hook_script_command_string(
            exec_poststart
        )

        self._write_hook_script("prestart", exec_prestart)
        self._write_hook_script("start", exec_start)
        self._write_hook_script("poststart", exec_poststart)

        yield jailLaunchEvent.begin()

        def _stop_failed_jail(
        ) -> typing.Generator[iocage.lib.events.IocageEvent, None, None]:
            if single_command is None:
                for event in self.stop(force=True):
                    yield event
            else:
                self._run_poststop_hook_manually()
        jailLaunchEvent.add_rollback_step(_stop_failed_jail)

        if self.is_basejail is True:
            self.storage_backend.apply(self.storage, release)

        if quick is False:
            self._save_autoconfig()

        try:
            if single_command is None:
                stdout, stderr, returncode = self._launch_persistent_jail(
                    passthru=passthru
                )
            else:
                self._prepare_stop()
                stdout, stderr, returncode = self._launch_single_command_jail(
                    " ".join(single_command),
                    passthru=passthru
                )
        except Exception as e:
            yield jailLaunchEvent.fail(e)
            raise e

        yield jailLaunchEvent.end()

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

    def _run_poststop_hook_manually(self) -> None:
        self.logger.debug("Running poststop hook manually")
        iocage.lib.helpers.exec(self.get_hook_script_path("poststop"))

    def _wrap_hook_script_command(
        self,
        commands: typing.Optional[typing.Union[str, typing.List[str]]],
        ignore_errors: bool=True,
        jailed: bool=False,
        write_env: bool=True
    ) -> typing.List[str]:

        pre_commands: typing.List[str] = []
        pre_commands.append(f"set {'+' if ignore_errors else '-'}e")
        pre_commands.append(
            "[ -f \"$(dirname $0)/.env\" ] && . \"$(dirname $0)/.env\""
        )
        if jailed is False:
            pre_commands.append(
                f"export IOCAGE_JID="
                f"$(/usr/sbin/jls -j {self.identifier} jid 2>/dev/null || :)"
            )

        if isinstance(commands, str):
            _commands = [commands]
        elif commands is None:
            _commands = []
        else:
            _commands = commands

        post_commands: typing.List[str] = []
        env_path = self.script_env_path
        if (jailed is False) and (write_env is True):
            if self.running:
                post_commands.append(
                    f"echo \"export IOCAGE_JID={self.jid}\" > {env_path}"
                )
                file_pipe = ">>"
            else:
                file_pipe = ">"

            post_commands += [(
                f"env | grep ^IOCAGE_NIC | sed 's/^/export /' {file_pipe} "
                f"{self.jail.script_env_path}"
            )]
        else:
            post_commands = []

        return pre_commands + _commands + post_commands

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

    def fork_exec(  # noqa: T484
        self,
        command: typing.List[str],
        error_handler: typing.Optional[typing.Callable[
            [subprocess.Popen, str, str],
            typing.Tuple[bool, str],
        ]]=None,
        passthru: bool=False,
        **temporary_config_override
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """Start a jail, run a command and shut it down immediately."""
        self.require_jail_existing()
        self.require_jail_stopped()

        events: typing.Any = iocage.lib.events
        jailForkExecEvent = events.JailForkExec(jail=self)

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

        list(JailGenerator.start(self, single_command=command, passthru=True))
        yield jailForkExecEvent.end()

    @property
    def basejail_backend(self) -> typing.Optional[typing.Union[
        iocage.lib.NullFSBasejailStorage.NullFSBasejailStorage,
        iocage.lib.ZFSBasejailStorage.ZFSBasejailStorage
    ]]:
        """Return the basejail backend or None."""
        if self.config["basejail"] is False:
            return None

        if self.config["basejail_type"] == "nullfs":
            return iocage.lib.NullFSBasejailStorage.NullFSBasejailStorage

        if self.config["basejail_type"] == "zfs":
            return iocage.lib.ZFSBasejailStorage.ZFSBasejailStorage

        return None

    def _run_hook(
        self,
        hook_name: str
    ) -> typing.Optional[typing.Tuple[str, str, int]]:
        """
        Execute a jail hook.

        Hooks are executed during the start and stop process of the jail.
        """
        key = f"exec_{hook_name}"
        value = self.config[key]

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
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            return iocage.lib.helpers.exec(
                [value],
                logger=self.logger,
                env=self.env,
                shell=True  # nosec: B604
            )

    def _ensure_script_dir(self) -> None:
        if os.path.isdir(self.launch_script_dir) is False:
            os.mkdir(self.launch_script_dir, 0o755)

    def _prepare_stop(self) -> None:
        exec_prestop = ""
        exec_stop = ""
        exec_poststop = "\n".join(self._teardown_mounts())

        # ToDo: self.config.get("exec_prestop", "")
        if self.config["exec_prestop"] is not None:
            exec_prestop = self.config["exec_prestop"]
        if self.config["exec_stop"] is not None:
            exec_stop = self.config["exec_stop"]
        if self.config["exec_poststop"] is not None:
            exec_poststop += "\n" + self.config["exec_poststop"]

        if self.config["vnet"]:
            exec_poststop = self._stop_vimage_network() + [exec_poststop]

        exec_prestop = self._wrap_hook_script_command_string(
            exec_prestop
        )

        exec_stop = self._wrap_hook_script_command_string(
            exec_stop,
            jailed=True,
            ignore_errors=True
        )

        exec_poststop = self._wrap_hook_script_command_string(
            exec_poststop,
            write_env=False,
            ignore_errors=True
        )

        if self.running and (os.path.isfile(self.script_env_path) is False):
            self.logger.debug(
                f"Overwriting the hook script .env file {self.script_env_path}"
                f" for JID {self.jid}"
            )
            script_env: typing.Dict[str, str] = {}
            for network in self.networks:
                for key, value in network.env.items():
                    script_env[key] = str(value).replace("$", "\\$")

            self._ensure_script_dir()
            with open(self.script_env_path, "w") as f:
                f.write("\n".join(
                    [f"export IOCAGE_JID={self.jid}"] +
                    [
                        f"export {key}=\"{value}\""
                        for key, value
                        in script_env.items()
                    ]
                ))

        self._write_hook_script("prestop", exec_prestop)
        self._write_hook_script("stop", exec_stop)
        self._write_hook_script("poststop", exec_poststop)

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
        if force is False:
            self.require_jail_existing()
            self.require_jail_running()

        events: typing.Any = iocage.lib.events
        jailDestroyEvent = events.JailDestroy(self)

        self._prepare_stop()

        yield jailDestroyEvent.begin()
        try:
            self._write_jail_conf(force=force)
            self._destroy_jail()
        except Exception as e:
            if force is True:
                yield jailDestroyEvent.skip()
                self.logger.debug(
                    "Manually executing prestop and poststop hooks"
                )
                try:
                    for hook_name in ["prestop", "poststop"]:
                        iocage.lib.helpers.exec([
                            "/bin/sh",
                            self.get_hook_script_path(hook_name)
                        ], logger=self.logger)
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
            ),
            (
                f"exec.stop = \"{stop_command}\";"
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
        force: bool=False
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """Restart the jail."""
        failed: bool = False
        jailRestartEvent = iocage.lib.events.JailRestart(jail=self)
        jailShutdownEvent = iocage.lib.events.JailShutdown(jail=self)
        JailSoftShutdownEvent = iocage.lib.events.JailSoftShutdown(jail=self)
        jailStartEvent = iocage.lib.events.JailStart(jail=self)

        yield jailRestartEvent.begin()

        if shutdown is False:

            # soft stop
            yield JailSoftShutdownEvent.begin()
            try:
                self._run_hook("stop")
                yield JailSoftShutdownEvent.end()
            except iocage.lib.errors.IocageException:
                yield JailSoftShutdownEvent.fail(exception=False)

            # service start
            yield jailStartEvent.begin()
            try:
                self._run_hook("start")
                yield jailStartEvent.end()
            except iocage.lib.errors.IocageException:
                yield jailStartEvent.fail(exception=False)

        else:

            # full shutdown
            yield jailShutdownEvent.begin()
            try:
                for event in self.stop():
                    yield event
                yield jailShutdownEvent.end()
            except iocage.lib.errors.IocageException:
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
            except iocage.lib.errors.IocageException:
                failed = True
                yield jailStartEvent.fail(exception=False)

            # respond to failure
            if failed is True:
                yield jailRestartEvent.fail(exception=False)
                return

        yield jailRestartEvent.end()

    def destroy(self, force: bool=False) -> None:
        """
        Destroy a Jail and it's datasets.

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
        Change the name of a jail.

        Args:

            new_name (str):
                The new name of a jail. It might not be used by another Jail
                and must differ from the current name.
        """
        self.require_jail_existing()
        self.require_jail_stopped()
        self.require_storage_backend()

        if iocage.lib.helpers.validate_name(new_name) is False:
            raise iocage.lib.errors.InvalidJailName(logger=self.logger)

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
        for event in self.update_fstab_paths(current_mountpoint):
            yield event

        yield jailRenameEvent.end()

    def update_fstab_paths(
        self,
        old_path_prefix: str,
        new_path_prefix: typing.Optional[str]=None
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """
        Update a path in the whole fstab file.

        When no new_path_prefix is provided, the jail's root dataset is used.
        """
        if new_path_prefix is None:
            _new_path_prefix = self.root_dataset.mountpoint
        else:
            _new_path_prefix = new_path_prefix

        jailFstabUpdateEvent = iocage.lib.events.JailFstabUpdate(
            jail=self
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
        except BaseException:
            yield jailFstabUpdateEvent.fail()
            raise

    def create(
        self,
        resource: typing.Optional[typing.Union[
            'JailGenerator',
            'iocage.lib.Release.ReleaseGenerator',
        ]]=None
    ) -> None:
        """
        Create a Jail from a given Resource.

        Args:

            resource (Jail or Release):
                The (new) jail is created from this resource.
                If no resource is specified, an empty dataset will be created
        """
        if isinstance(resource, JailGenerator):
            self.create_from_template(template=resource)
        elif isinstance(resource, iocage.lib.Release.ReleaseGenerator):
            self.create_from_release(release=resource)
        else:
            self.create_from_scratch()

    def create_from_scratch(
        self
    ) -> None:
        """Create a new jail without any root dataset content."""
        self._create_skeletron()

    def create_from_release(
        self,
        release: iocage.lib.Release.ReleaseGenerator
    ) -> None:
        """
        Create a Jail from a Release.

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
        """Create a Jail from a template Jail."""
        template.require_jail_is_template()
        self.config['release'] = template.config['release']
        self.config['basejail'] = template.config['basejail']
        self.config['basejail_type'] = template.config['basejail_type']
        self._create_from_resource(template)

    def promote(self) -> None:
        """Promote all datasets of the jail."""
        self.zfs.promote_dataset(self.dataset)

    def clone_from_jail(
        self,
        source_jail: 'JailGenerator'
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """Create a Jail from another Jail."""
        self.autoset_dataset_name()
        for event in source_jail.clone_to_dataset(self.dataset_name):
            yield event

        self.config.clone(source_jail.config.data)
        self.save()

        fstab_update_generator = self.update_fstab_paths(
            source_jail.root_dataset.mountpoint
        )
        for event in fstab_update_generator:
            yield event

    def clone_to_dataset(
        self,
        destination_dataset_name: str,
        delete_existing: bool=False
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """Clones the jails dataset to another dataset with the given name."""
        jailCloneEvent = iocage.lib.events.JailClone(jail=self)
        yield jailCloneEvent.begin()

        try:
            self.zfs.clone_dataset(
                source=self.dataset,
                target=destination_dataset_name,
                delete_existing=delete_existing,
                snapshot_name=iocage.lib.ZFS.append_snapshot_datetime("clone")
            )
        except Exception as e:
            err = iocage.lib.errors.ZFSException(
                *e.args,
                logger=self.logger
            )
            yield jailCloneEvent.fail(err)
            raise err

        yield jailCloneEvent.end()

    def _create_skeletron(self) -> None:

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

    def _create_from_resource(
        self,
        resource: 'iocage.lib.Resource.Resource'
    ) -> None:

        self._create_skeletron()

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
    def storage_backend(self) -> iocage.lib.Storage.Storage:
        """
        Return the jail storage abstraction class.

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

        # launch command mountpoint
        jail_start_script_dir = "".join([
            self.root_dataset.mountpoint,
            self._relative_hook_script_dir
        ])
        iocage_helper_line = iocage.lib.Config.Jail.File.Fstab.FstabLine(dict(
            source=self.launch_script_dir,
            destination=jail_start_script_dir,
            type="nullfs",
            options="ro"
        ))
        self.fstab.read_file()
        if self.fstab.line_exists(iocage_helper_line) is False:
            self.fstab.add_line(iocage_helper_line)
        self.fstab.save()

    def exec(  # noqa: T484
        self,
        command: typing.List[str],
        **kwargs
    ) -> typing.Tuple[str, str, int]:
        """
        Execute a command in a running jail.

        command (list):
            A list of command and it's arguments

            Example: ["/usr/bin/whoami"]
        """
        command = ["/usr/sbin/jexec", str(self.jid)] + command

        child, stdout, stderr = iocage.lib.helpers.exec(
            command,
            logger=self.logger,
            env=self.env,
            **kwargs  # noqa: T484
        )

        return child, stdout, stderr

    def passthru(
        self,
        command: typing.List[str]
    ) -> typing.Tuple[str, str, int]:
        """
        Execute a command in a started jail and passthrough STDIN and STDOUT.

        command (list):
            A list of command and it's arguments

            Example: ["/bin/sh"]
        """
        if isinstance(command, str):
            command = [command]

        return iocage.lib.helpers.exec_passthru(
            [
                "/usr/sbin/jexec",
                str(self.jid)
            ] + command,
            logger=self.logger
        )

    def exec_console(self) -> typing.Tuple[str, str]:
        """Shortcut to drop into a shell of a started jail."""
        self.require_jail_running()
        return self.passthru(
            ["/usr/bin/login"] + self.config["login_flags"]
        )

    def _destroy_jail(self) -> None:

        commands = [
            [
                "/usr/sbin/jail",
                "-v",
                "-r",
                "-f",
                self._jail_conf_file,
                self.identifier
            ]
        ]

        for command in commands:
            iocage.lib.helpers.exec(
                command,
                logger=self.logger
            )

    @property
    def _dhcp_enabled(self) -> bool:
        """Return True if any ip4_addr uses DHCP."""
        if self.config["ip4_addr"] is None:
            return False

        return ("dhcp" in self.config["ip4_addr"].networks) is True

    @property
    def devfs_ruleset(self) -> iocage.lib.DevfsRules.DevfsRuleset:
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

    @property
    def _launch_command(self) -> typing.List[str]:

        command = ["jail", "-c"]

        if self.config["vnet"]:
            command.append("vnet")
            command.append(
                f"vnet.interface={self._get_value('vnet_interfaces')}"
            )
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
            f"exec.poststop=\"{self.get_hook_script_path('poststop')}\""
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

        command += ["allow.dying"]
        return command

    def _launch_persistent_jail(
        self,
        passthru: bool
    ) -> typing.Union[str, str, int]:
        command = self._launch_command + [
            "persist",
            f"exec.start=\"{self._relative_hook_script_dir}/start.sh\"",
            f"exec.poststart=\"{self.get_hook_script_path('poststart')}\""
        ]

        humanreadable_name = self.humanreadable_name

        stdout, stderr, returncode = self._exec_launch_command(
            command=command,
            passthru=passthru
        )
        if returncode > 0:
            raise iocage.lib.errors.JailLaunchFailed(
                jail=self,
                logger=self.logger
            )

        self.state.query()
        self.logger.verbose(
            f"Jail '{self.humanreadable_name}' started with JID {self.jid}",
            jail=self
        )

        return stdout, stderr, returncode

    def _exec_launch_command(
        self,
        command: typing.List[str],
        passthru: bool
    ) -> typing.Tuple[str, str, int]:

        aborted = False
        try:
            if passthru is True:
                return iocage.lib.helpers.exec_passthru(
                    command,
                    logger=self.logger
                )
            else:
                return iocage.lib.helpers.exec(command, logger=self.logger)
        except (KeyboardInterrupt, SystemExit):
            list(self.stop(force=True))
            aborted = True

        if aborted is True:
            raise iocage.lib.errors.JailExecutionAborted(
                jail=self,
                logger=None
            )

    def _launch_single_command_jail(
        self,
        jail_command: str,
        passthru: bool
    ) -> typing.Tuple[str, str, int]:
        command = self._launch_command + [
            "nopersist",
            f"exec.poststart=\"{self.get_hook_script_path('poststop')}\"",
            "command=/bin/sh",
            f"{self._relative_hook_script_dir}/command.sh"
        ]

        EOF_IDENTIFIER = f"EOF{random.getrandbits(64)}"
        self._write_hook_script("command", "\n".join(
            (["service ipfw onestop"] if self.host.ipfw_enabled else []) +
            [
                f". {self._relative_hook_script_dir}/start.sh",
                "set -e",
                jail_command,
            ]
        ))

        stdout, stderr, returncode = self._exec_launch_command(
            command,
            passthru=passthru
        )

        if returncode > 0:
            raise iocage.lib.errors.JailCommandFailed(
                returncode=returncode,
                logger=self.logger
            )

        return stdout, stderr, returncode

    def _get_value(self, key: str) -> str:
        """Return jail command consumable config value string."""
        return str(iocage.lib.helpers.to_string(
            self.config[key],
            true="1",
            false="0",
            none=""
        ))

    @property
    def networks(self) -> typing.List[iocage.lib.Network.Network]:
        """Return the list of a jails configured networks."""
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

    def _write_hook_script(self, hook_name: str, command_string: str) -> None:
        file = self.get_hook_script_path(hook_name)
        existed = os.path.isfile(file)
        with open(file, "w") as f:
            f.write(f"#!/bin/sh\n{command_string}")
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
        'iocage.lib.Network.PrestartCommandList',
        'iocage.lib.Network.JailCommandList',
        'iocage.lib.Network.PoststartCommandList'
    ]:
        self.logger.debug("Starting VNET/VIMAGE", jail=self)

        prestart: typing.List[str] = []
        start: typing.List[str] = []
        poststart: typing.List[str] = []

        for network in self.networks:
            _vnet_nic_name = f"{network.temporary_nic_prefix}:j"
            _pre, _start, _post = network.setup()

            # ToDo: would be great to write as config[key] += ["iface1"]
            vnet_interfaces = self.config["vnet_interfaces"] + [_vnet_nic_name]
            self.config["vnet_interfaces"] = list(vnet_interfaces)

            prestart += _pre
            start += _start
            poststart += _post

        return prestart, start, poststart

    def _stop_vimage_network(self) -> typing.List[str]:
        commands: typing.List[str] = []
        for network in self.networks:
            commands += network.teardown()
        return commands

    def _configure_nameserver(self) -> None:
        self.config["resolver"].apply(self)

    def _configure_localhost_commands(self) -> typing.List[str]:
        return ["ifconfig lo0 localhost"]

    def _limit_resources(self) -> None:

        if self.config['rlimits'] is False:
            self.logger.verbose("Resource limits disabled")
            return

        for key, limit, action in map(
            lambda name: (
                (name, ) + self._get_resource_limit(name)  # noqa: T484
            ),
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
    def _resource_limit_config_keys(self) -> typing.List[str]:
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

    def _configure_routes_commands(self) -> typing.List[str]:

        defaultrouter = self.config["defaultrouter"]
        defaultrouter6 = self.config["defaultrouter6"]

        if not defaultrouter or defaultrouter6:
            self.logger.spam("no static routes configured")
            return []

        commands: typing.List[str] = []

        if defaultrouter:
            commands.append(
                self._configure_route_command(defaultrouter)
            )

        if defaultrouter6:
            commands.append(
                self._configure_route_command(defaultrouter6, ipv6=True)
            )

        return commands

    def _configure_route_command(self, gateway: str, ipv6: bool=False) -> str:

        ip_version = 4 + 2 * (ipv6 is True)

        # router@interface syntax for static pointopoint route
        if "@" in gateway:
            gateway, nic = gateway.split("@", maxsplit=1)
            self.logger.verbose(
                f"setting pointopoint route to {gateway} via {nic}"
            )
            self.exec(["/sbin/route", "-q", "add", gateway, "-iface", nic])

        self.logger.verbose(
            f"setting default IPv{ip_version} gateway to {gateway}",
            jail=self
        )
        return " ".join(
            ["/sbin/route", "-q", "add"] +
            (["-6"] if (ipv6 is True) else []) +
            ["default", gateway]
        )

    def require_jail_is_template(self) -> None:
        """Raise JailIsTemplate exception if the jail is a template."""
        if self.config['template'] is False:
            raise iocage.lib.errors.JailNotTemplate(
                jail=self,
                logger=self.logger
            )

    def require_storage_backend(self) -> None:
        """Raise if the jail was not initialized with a storage backend."""
        if self.storage_backend is None:
            raise Exception("")

    def require_jail_not_template(self, **kwargs) -> None:  # noqa: T484
        """Raise JailIsTemplate exception if the jail is a template."""
        if self.config['template'] is True:
            raise iocage.lib.errors.JailIsTemplate(
                jail=self,
                logger=self.logger,
                **kwargs  # noqa: T484
            )

    def require_jail_not_existing(self, **kwargs) -> None:  # noqa: T484
        """Raise JailAlreadyExists exception if the jail already exists."""
        if self.exists:
            raise iocage.lib.errors.JailAlreadyExists(
                jail=self,
                logger=self.logger,
                **kwargs  # noqa: T484
            )

    def require_jail_existing(self, **kwargs) -> None:  # noqa: T484
        """Raise JailDoesNotExist exception if the jail does not exist."""
        if not self.exists:
            raise iocage.lib.errors.JailDoesNotExist(
                jail=self,
                logger=self.logger,
                **kwargs  # noqa: T484
            )

    def require_jail_stopped(self, **kwargs) -> None:  # noqa: T484
        """Raise JailAlreadyRunning exception if the jail is running."""
        if self.running is not False:
            raise iocage.lib.errors.JailAlreadyRunning(
                jail=self,
                logger=self.logger,
                **kwargs  # noqa: T484
            )

    def require_jail_running(self, **kwargs) -> None:  # noqa: T484
        """Raise JailNotRunning exception if the jail is stopped."""
        if not self.running:
            raise iocage.lib.errors.JailNotRunning(
                jail=self,
                logger=self.logger,
                **kwargs  # noqa: T484
            )

    def _teardown_mounts(self) -> typing.List[str]:

        commands: typing.List[str] = []

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

        commands.append(" ".join(iocage.lib.helpers.umount_command(
            mountpoints,
            force=True,
            ignore_error=True
        )))

        commands.append(" ".join(iocage.lib.helpers.umount_command(
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
    ) -> iocage.lib.Types.AbsolutePath:

        return iocage.lib.Types.AbsolutePath(f"{self.root_path}{value}")

    def _resolve_name(self, text: str) -> str:

        if (text is None) or (len(text) == 0):
            raise iocage.lib.errors.JailNotSupplied(logger=self.logger)

        resource_selector = iocage.lib.ResourceSelector.ResourceSelector(
            name=text
        )

        root_datasets = resource_selector.filter_datasets(self.host.datasets)

        for datasets_key, datasets in root_datasets.items():
            for dataset in list(datasets.jails.children):
                dataset_name = str(
                    dataset.name[(len(datasets.jails.name) + 1):]
                )
                humanreadable_name = iocage.lib.helpers.to_humanreadable_name(
                    dataset_name
                )
                possible_names = [dataset_name, humanreadable_name]
                if resource_selector.name in possible_names:
                    return dataset_name

        raise iocage.lib.errors.JailNotFound(text, logger=self.logger)

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
            return str(iocage.lib.helpers.to_humanreadable_name(self.name))
        except KeyError:
            raise iocage.lib.errors.JailUnknownIdentifier(
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
        jail_env = os.environ.copy()  # type: typing.Dict[str, str]

        for prop in self.config.all_properties:
            prop_name = f"IOCAGE_{prop.upper()}"
            jail_env[prop_name] = self.getstring(prop)

        jail_env["IOCAGE_JAIL_PATH"] = self.root_dataset.mountpoint
        jail_env["IOCAGE_JID"] = str(self.jid)

        return jail_env

    @property
    def identifier(self) -> str:
        """Return the jail id used in snapshots, jls, etc."""
        config = object.__getattribute__(self, 'config')
        return f"{self.source}-{config['id']}"

    @property
    def release(self) -> 'iocage.lib.Release.ReleaseGenerator':
        """Return the iocage.Release instance linked with the jail."""
        return iocage.lib.Release.Release(
            name=self.config["release"],
            root_datasets_name=self.root_datasets_name,
            logger=self.logger,
            host=self.host,
            zfs=self.zfs
        )

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


class Jail(JailGenerator):
    """Synchronous wrapper of JailGenerator."""

    def start(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> typing.List['iocage.lib.events.IocageEvent']:
        """Start the jail."""
        return list(JailGenerator.start(self, *args, **kwargs))

    def stop(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> typing.List['iocage.lib.events.IocageEvent']:
        """Stop the jail."""
        return list(JailGenerator.stop(self, *args, **kwargs))

    def rename(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> typing.List['iocage.lib.events.IocageEvent']:
        """Rename the jail."""
        return list(JailGenerator.rename(self, *args, **kwargs))

    def update_fstab_paths(  # noqa: T484
        self,
        *args,
        **kwargs
    ) -> typing.List['iocage.lib.events.IocageEvent']:
        """Update a path in the whole fstab file."""
        return list(JailGenerator.update_fstab_paths(self, *args, **kwargs))
