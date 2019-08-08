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
"""
A Jail defines the configuration of a FreeBSD jail managed by ioc.

It consists of kernel state and configuration assets (config.json).

Configuration values are in a JailConfig, that maps the Jail configuration to
permanent disk storage. The latest version used a config.json JSON config file.
For compatibility with older versions of iocage (shell), UCL config files and
storage as ZFS properties on the jails ZFS dataset are supported as well.

The state of a Jail is managed by the kernel, that ioc interfaces with libc.
"""
import typing
import os
import shlex
import shutil

import libzfs
import freebsd_sysctl
import jail as libjail
import freebsd_sysctl.types

import libioc.Types
import libioc.errors
import libioc.events
import libioc.helpers
import libioc.helpers_object
import libioc.DevfsRules
import libioc.Host
import libioc.Config.Jail.BaseConfig
import libioc.Config.Jail.JailConfig
import libioc.Network
import libioc.Release
import libioc.Storage
import libioc.Storage.Basejail
import libioc.Storage.NullFSBasejail
import libioc.Storage.Standalone
import libioc.Storage.ZFSBasejail
import libioc.ZFSShareStorage
import libioc.LaunchableResource
import libioc.VersionedResource
import libioc.Config.Jail.Properties.ResourceLimit
import libioc.ResourceSelector
import libioc.Config.Jail.File.Fstab

import ctypes.util
import errno
_dll = ctypes.CDLL(str(ctypes.util.find_library("c")), use_errno=True)


class JailResource(
    libioc.LaunchableResource.LaunchableResource,
    libioc.VersionedResource.VersionedResource
):
    """Resource that represents a jail."""

    _jail: 'JailGenerator'
    _fstab: 'libioc.Config.Jail.File.Fstab.JailFstab'
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
        fstab: typing.Optional['libioc.Config.Jail.File.Fstab.JailFstab']=None,
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
    def fstab(self) -> 'libioc.Config.Jail.File.Fstab.JailFstab':
        """
        Memoized fstab wrapper of a Jail.

        The fstab file is stored in the top level of a Jails dataset
        """
        try:
            return self._fstab
        except AttributeError:
            pass

        jail = self.jail
        fstab = libioc.Config.Jail.File.Fstab.JailFstab(
            jail=jail,
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

    def getstring(self, key: str) -> str:
        """
        Get any resource property as string or '-'.

        Returns the string value, or an empty string in case of an unknown user
        config property.

        Args:
            key (string):
                Name of the jail property to return
        """
        try:
            return str(super().getstring(key))
        except libioc.errors.UnknownConfigProperty:
            if libioc.Config.Jail.BaseConfig.BaseConfig.is_user_property(key):
                return ""
            raise


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
    _provisioner: 'libioc.Provisioning.Prototype'
    __jid: typing.Optional[int]

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
        new: bool=False,
        skip_invalid_config: bool=False
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
            self.config.read(
                data=self.read_config(),
                skip_on_error=skip_invalid_config
            )
            if self.config["id"] is None:
                self.config["id"] = self.dataset_name.split("/").pop()

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

    def start(
        self,
        quick: bool=False,
        passthru: bool=False,
        single_command: typing.Optional[str]=None,
        event_scope: typing.Optional['libioc.events.Scope']=None,
        dependant_jails_seen: typing.List['JailGenerator']=[],
        start_dependant_jails: bool=True,
        env: typing.Dict[str, str]={}
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

            event_scope (libioc.events.Scope): (default=None)

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

            env (dict):

                Environment variables that are available in all jail hooks.
                Existing environment variables (provided by the system or ioc)
                can be overridden with entries in this dictionary.
        """
        self.require_jail_existing()
        self.require_jail_stopped()
        self.require_jail_match_hostid()

        jailStartEvent = libioc.events.JailStart(
            jail=self,
            scope=event_scope
        )
        yield jailStartEvent.begin()

        # Start Dependant Jails
        dependant_jails_started: typing.List[JailGenerator] = []
        if start_dependant_jails is True:
            dependant_jails_seen.append(self)
            DependantsStartEvent = libioc.events.JailDependantsStart
            for event in self._start_dependant_jails(
                self.config["depends"],
                event_scope=jailStartEvent.scope,
                dependant_jails_seen=dependant_jails_seen
            ):
                if isinstance(event, DependantsStartEvent) is True:
                    if event.done and (event.error is None):
                        dependant_jails_started.extend(event.started_jails)
                yield event

        # Apply Resolver Config
        try:
            yield from self.config["resolver"].apply(
                jail=self,
                event_scope=jailStartEvent.scope
            )
        except Exception as e:
            raise e

        # Apply Resource Limits
        yield from self._apply_resource_limits(
            event_scope=jailStartEvent.scope
        )

        # Prestart Hook
        yield from self.__run_hook(
            "prestart",
            force=False,
            event_scope=jailStartEvent.scope,
            env=env
        )

        # Basejail Actions
        if self.is_basejail is True:
            yield from self.storage_backend.apply(
                self.storage,
                self.release,
                event_scope=jailStartEvent.scope
            )

        # Jail Fstab
        yield from self.fstab.mount(event_scope=jailStartEvent.scope)

        # Jail Creation
        jailAttachEvent = libioc.events.JailAttach(
            jail=self,
            scope=jailStartEvent.scope
        )
        yield jailAttachEvent.begin()
        jiov = libjail.Jiov(self._launch_params)
        jid = _dll.jail_set(jiov.pointer, len(jiov), 1)

        if jid > 0:
            self.__jid = jid
            yield jailAttachEvent.end()
        else:
            error_code = ctypes.get_errno()
            if error_code > 0:
                error_name = errno.errorcode[error_code]
                error_text = f"{error_code} [{error_name}]"
            else:
                error_text = jiov.errmsg.value.decode("UTF-8")
            error = libioc.errors.JailLaunchFailed(
                jail=self,
                reason=error_text,
                logger=self.logger
            )
            yield jailAttachEvent.fail(error_text)
            raise error

        def _stop_jails(
        ) -> typing.Generator['libioc.events.IocEvent', None, None]:
            if single_command is None:
                jails_to_stop = [self]
            else:
                jails_to_stop = []
                if self.config["vnet"] is False:
                    yield from self._stop_non_vimage_network(
                        force=False,
                        event_scope=jailStartEvent.scope
                    )
                yield from self.__destroy_jail(
                    event_scope=jailStartEvent.scope
                )
                if (jid is not None) and (self.config["vnet"] is True):
                    yield from self.__stop_vimage_network(
                        jid,
                        event_scope=jailStartEvent.scope
                    )
                yield from self.fstab.unmount(event_scope=jailStartEvent.scope)
                yield from self.storage_backend.teardown(
                    self.storage,
                    event_scope=jailStartEvent.scope
                )
                yield from self.__clear_resource_limits(
                    force=False,
                    event_scope=jailStartEvent.scope
                )
            if start_dependant_jails is True:
                jails_to_stop.extend(list(reversed(dependant_jails_started)))
            for jail_to_stop in jails_to_stop:
                yield from jail_to_stop.stop(
                    force=True,
                    event_scope=jailAttachEvent.scope
                )
        jailStartEvent.add_rollback_step(_stop_jails)

        # Created Hook
        yield from self.__run_hook(
            "created",
            force=False,
            event_scope=jailStartEvent.scope,
            env=env
        )

        # Mount Devfs
        yield from self.__mount_devfs(jailStartEvent.scope)

        # Mount Fdescfs
        yield from self.__mount_fdescfs(jailStartEvent.scope)

        # Setup Network
        yield from self.__start_network(jailStartEvent.scope)

        # Attach shared ZFS datasets
        if self.config["jail_zfs"] is True:
            yield from self._zfs_share_storage.mount_zfs_shares(
                event_scope=jailStartEvent.scope
            )

        if quick is False:
            unknown_config_parameters = list(
                self.config.unknown_config_parameters
            )
            if len(unknown_config_parameters) > 0:
                _unused_parameters = str(", ".join(unknown_config_parameters))
                self.logger.warn(
                    f"Unused JailConfig parameters: {_unused_parameters}"
                )
            self._save_autoconfig()

        try:
            if single_command is None:
                # Start and Poststart Hooks
                yield from self.__run_hook(
                    "start",
                    force=False,
                    event_scope=jailStartEvent.scope,
                    env=env
                )
                yield from self.__run_hook(
                    "poststart",
                    force=False,
                    event_scope=jailStartEvent.scope,
                    env=env
                )
            else:
                yield from self.__run_hook(
                    "command",
                    force=False,
                    event_scope=jailStartEvent.scope,
                    script=str(single_command),
                    passthru=passthru,
                    env=env
                )
        except Exception as e:
            yield jailStartEvent.fail(e)
            raise e

        if single_command is not None:
            yield from _stop_jails()
        yield jailStartEvent.end()

    def __mount_devfs(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.MountDevFS', None, None]:
        yield from self.__mount_in_jail(
            filesystem="devfs",
            mountpoint="/dev",
            event=libioc.events.MountDevFS,
            event_scope=event_scope,
            ruleset=self.devfs_ruleset
        )

    def __mount_fdescfs(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.MountFdescfs', None, None]:
        yield from self.__mount_in_jail(
            filesystem="fdescfs",
            mountpoint="/dev/fd",
            event=libioc.events.MountFdescfs,
            event_scope=event_scope
        )

    def __mount_in_jail(
        self,
        filesystem: str,
        mountpoint: str,
        event: 'libioc.events.JailEvent',
        event_scope: typing.Optional['libioc.events.Scope']=None,
        **extra_args: str
    ) -> typing.Generator['libioc.events.MountFdescfs', None, None]:

        _event = event(
            jail=self,
            scope=event_scope
        )
        yield _event.begin()

        if int(self.config[f"mount_{filesystem}"]) == 0:
            yield _event.skip("disabled")
            return

        try:
            _mountpoint = str(f"{self.root_path}{mountpoint}")
            self.require_relative_path(_mountpoint)
            if os.path.islink(_mountpoint) or os.path.isfile(_mountpoint):
                raise libioc.errors.InsecureJailPath(
                    path=_mountpoint,
                    logger=self.logger
                )
        except Exception as e:
            yield _event.fail(str(e))
            raise e
        if os.path.isdir(_mountpoint) is False:
            os.makedirs(_mountpoint, mode=0o555)

        try:
            libioc.helpers.mount(
                destination=_mountpoint,
                fstype=filesystem,
                logger=self.logger,
                **extra_args
            )
        except Exception as e:
            yield _event.fail(str(e))
            raise e

        yield _event.end()

    @property
    def _zfs_share_storage(
        self
    ) -> libioc.ZFSShareStorage.ZFSShareStorage:
        return libioc.ZFSShareStorage.ZFSShareStorage(
            jail=self,
            logger=self.logger
        )

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

    def fork_exec(
        self,
        command: str,
        passthru: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None,
        start_dependant_jails: bool=True,
        dependant_jails_seen: typing.List['JailGenerator']=[],
        env: typing.Dict[str, str]={},
        **temporary_config_override: typing.Any
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """
        Start a jail, run a command and shut it down immediately.

        Args:

            command (string):

                The command to execute in the jail.

            passthru (bool):

                Execute commands in an interactive shell.

            event_scope (libioc.events.Scope): (default=None)

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
            yield from JailGenerator.start(
                self,
                single_command=command,
                passthru=passthru,
                event_scope=event_scope,
                dependant_jails_seen=dependant_jails_seen,
                start_dependant_jails=start_dependant_jails,
                env=env
            )
        finally:
            self.config = original_config

    def __merge_env(
        self,
        env: typing.Dict[str, str]={}
    ) -> typing.Dict[str, str]:
        _env = dict()
        _env_keys = env.keys()
        for key in _env_keys:
            _env[key] = env[key]

        global_env = self.env
        for key, value in global_env.items():
            if key not in _env_keys:
                _env[key] = global_env[key]

        return _env

    def __run_hook(
        self,
        hook: str,
        force: bool,
        event_scope: 'libioc.events.Scope',
        script: typing.Optional[str]=None,
        passthru: bool=False,
        env: typing.Dict[str, str]={}
    ) -> typing.Generator['libioc.events.JailHook', None, None]:
        _env = self.__merge_env(env)
        exec_func = libioc.helpers.exec
        exec_args = dict(logger=self.logger, env=_env)
        if hook == "prestart":
            Event = libioc.events.JailHookPrestart
        elif hook == "created":
            Event = libioc.events.JailHookCreated
        elif hook == "start":
            Event = libioc.events.JailHookStart
            exec_func = self.exec
            exec_args = dict(env=_env)
        elif hook == "command":
            Event = libioc.events.JailCommand
            exec_func = self.exec
            exec_args = dict(passthru=passthru, env=_env)
        elif hook == "poststart":
            Event = libioc.events.JailHookPoststart
        elif hook == "prestop":
            Event = libioc.events.JailHookPrestop
        elif hook == "stop":
            Event = libioc.events.JailHookStop
            if self.running is False:
                event = Event(self, scope=event_scope)
                yield event.begin()
                yield event.skip("not running")
                return
            exec_func = self.exec
            exec_args = dict(env=_env)
        elif hook == "poststop":
            Event = libioc.events.JailHookPoststop
        else:
            raise NotImplementedError(f"jail hook {hook} is unsupported")

        event = Event(self, scope=event_scope)
        yield event.begin()

        if script is None:
            config_value = self.config[f"exec_{hook}"]
            if config_value is None:
                yield event.skip()
                return
            script = str(config_value)

        stdout, stderr, code = exec_func(
            ["/bin/sh", "-c", script],
            **exec_args
        )
        event.stdout = stdout
        event.stderr = stderr
        event.code = code
        if code > 0:
            if force is True:
                yield event.skip("ERROR")
            else:
                yield event.fail(f"command exited with {code}")
                raise libioc.errors.JailHookFailed(
                    jail=self,
                    hook=hook,
                    logger=self.logger
                )
        else:
            yield event.end(stdout=stdout)

    def stop(
        self,
        force: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None,
        log_errors: bool=True,
        env: typing.Dict[str, str]={}
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """
        Stop a jail.

        Args:

            force (bool): (default=False)

                Ignores failures and enforces teardown if True.

            event_scope (libioc.events.Scope): (default=None)

                Provide an existing libiocage event scope or automatically
                create a new one instead.

            log_errors (bool): (default=True)

                When disabled errors are not passed to the logger. This is
                useful in scripted contexts when then stop operation was
                executed to enforce a defined jail state.

            env (dict):

                Environment variables that are available in all jail hooks.
                Existing environment variables (provided by the system or ioc)
                can be overridden with entries in this dictionary.
        """
        if force is False:
            self.require_jail_existing(log_errors=log_errors)
            self.require_jail_running(log_errors=log_errors)

        events: typing.Any = libioc.events
        jailStopEvent = events.JailStop(self, scope=event_scope)

        yield jailStopEvent.begin()
        jid = self.jid

        yield from self.__run_hook(
            "prestop",
            force=force,
            event_scope=jailStopEvent.scope,
            env=env
        )
        yield from self.__run_hook(
            "stop",
            force=force,
            event_scope=jailStopEvent.scope,
            env=env
        )
        yield from self.__destroy_jail(jailStopEvent.scope)
        if self.config["vnet"] is False:
            yield from self._stop_non_vimage_network(
                force=force,
                event_scope=jailStopEvent.scope
            )
        yield from self.__run_hook(
            "poststop",
            force=force,
            event_scope=jailStopEvent.scope
        )
        if (jid is not None) and (self.config["vnet"] is True):
            yield from self.__stop_vimage_network(
                jid,
                event_scope=jailStopEvent.scope
            )
        yield from self.fstab.unmount(event_scope=jailStopEvent.scope)
        yield from self.storage_backend.teardown(
            self.storage,
            event_scope=jailStopEvent.scope
        )
        yield from self.__clear_resource_limits(force, jailStopEvent.scope)

        yield jailStopEvent.end()

    @property
    def _jail_conf_file(self) -> str:
        return f"{self.launch_script_dir}/jail.conf"

    def restart(
        self,
        shutdown: bool=False,
        force: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None,
        env: typing.Dict[str, str]={}
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Restart the jail."""
        jailRestartEvent = libioc.events.JailRestart(
            jail=self,
            scope=event_scope
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
                yield from self.__run_hook(
                    "stop",
                    force=force,
                    event_scope=JailSoftShutdownEvent.scope,
                    env=env
                )
                yield JailSoftShutdownEvent.end()
            except libioc.errors.IocException:
                yield JailSoftShutdownEvent.fail(exception=False)

            # service start
            yield jailStartEvent.begin()
            try:
                yield from self.__run_hook(
                    "start",
                    force=force,
                    event_scope=JailSoftShutdownEvent.scope,
                    env=env
                )
                yield jailStartEvent.end()
            except libioc.errors.IocException:
                yield jailStartEvent.fail(exception=False)

        else:

            yield from self.stop(
                force=force,
                event_scope=jailRestartEvent.scope,
                env=env
            )
            yield from self.start(
                event_scope=jailRestartEvent.scope,
                env=env
            )

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
        if event_scope is None:
            event_scope = libioc.events.Scope()

        _stop_jail = force_stop
        if force is False:
            self.require_jail_stopped()
        else:
            _stop_jail = (self.running is True)

        if _stop_jail is True:
            try:
                yield from JailGenerator.stop(
                    self,
                    force=True,
                    event_scope=event_scope,
                    log_errors=(force_stop is False)
                )
            except libioc.errors.JailDestructionFailed:
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
        self.config["hostid"] = self.host.id
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
        libioc.LaunchableResource.LaunchableResource.save(self)
        self._write_config(self.config.data)
        self._save_autoconfig()

    def _save_autoconfig(self) -> None:
        """
        Save auto-generated files.

        Such files reflect changes to the JailConfig and need to be refreshed
        before each jail start.
        """
        self.rc_conf.save()

    def exec(
        self,
        command: typing.List[str],
        env: typing.Dict[str, str]={},
        passthru: bool=False,
        **kwargs: typing.Any
    ) -> libioc.helpers.CommandOutput:
        """
        Execute a command in a running jail.

        Args:

            command (list):

                A list of command and it's arguments

                Example: ["/usr/bin/whoami"]

            env (dict):

                The dictionary may contain env variables that will be
                forwarded to the executed jail command.

            passthru (bool): (default=False)

                When enabled the commands stdout and stderr are directory
                forwarded to the attached terminal. The results will not be
                included in the CommandOutput, so that (None, None,
                <returncode>) is returned.
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

    def __destroy_jail(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.JailStop', None, None]:

        jailRemoveEvent = libioc.events.JailRemove(
            jail=self,
            scope=event_scope
        )

        yield jailRemoveEvent.begin()

        if self.running is False:
            yield jailRemoveEvent.skip()
            return

        jid = self.jid
        try:
            libjail.dll.jail_remove(jid)
            while self.running or (libjail.is_jid_dying(jid) is True):
                # wait for death
                continue
            self.__jid = None
            yield jailRemoveEvent.end()
            return
        except Exception:
            pass

        yield jailRemoveEvent.fail(f"libc jail_remove failed for {jid}")
        raise libioc.errors.JailDestructionFailed(
            jail=self,
            logger=self.logger
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

        if self.config["jail_zfs"] is True:
            unhidden_parents: typing.Set[str] = set()
            shared_datasets = self._zfs_share_storage.get_zfs_datasets()
            if len(shared_datasets) > 0:
                devfs_ruleset.append("add path zvol unhide")
                for shared_dataset in shared_datasets:
                    current_dataset_name = "zvol"
                    for fragment in shared_dataset.name.split("/"):
                        current_dataset_name += f"/{fragment}"
                        if current_dataset_name in unhidden_parents:
                            continue
                        unhidden_parents.add(current_dataset_name)
                        devfs_ruleset.append(
                            f"add path {current_dataset_name} unhide"
                        )
                    devfs_ruleset.append(
                        f"add path {current_dataset_name}/* unhide"
                    )

        if self.config["allow_vmm"] is True:
            devfs_ruleset.append("add path vmm unhide")
            devfs_ruleset.append("add path vmm/* unhide")
            devfs_ruleset.append("add path nmdm* unhide")

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
    def _launch_params(self) -> libjail.Jiov:
        config = self.config
        vnet = (config["vnet"] is True)
        value: libjail.RawIovecValue
        jail_params: typing.Dict[str, libioc.JailParams.JailParam] = {}
        for sysctl_name, sysctl in libioc.JailParams.JailParams().items():
            if sysctl_name == "security.jail.param.devfs_ruleset":
                value = int(self.devfs_ruleset)
            elif sysctl_name == "security.jail.param.path":
                value = self.root_dataset.mountpoint
            elif sysctl_name == "security.jail.param.name":
                value = self.identifier
            elif sysctl_name == "security.jail.param.allow.mount.zfs":
                value = int(self._allow_mount_zfs)
            elif sysctl_name == "security.jail.param.vnet":
                if vnet is False:
                    # vnet is only used when explicitly enabled
                    # (friendly to Kernels without VIMAGE support)
                    continue
                value = 1
            elif sysctl_name == "security.jail.param.ip4.addr":
                if vnet is True:
                    continue
                value = []
                for _, addresses in self.config["ip4_addr"].items():
                    value += [x.ip for x in addresses]
            elif sysctl_name == "security.jail.param.ip6.addr":
                if vnet is True:
                    continue
                value = []
                for _, addresses in self.config["ip6_addr"].items():
                    value += [x.ip for x in addresses]
            elif vnet and (sysctl_name.startswith("security.jail.param.ip")):
                continue
            else:
                config_property_name = sysctl.iocage_name
                if self.config.is_known_property(
                    config_property_name,
                    explicit=False
                ) is True:
                    value = config[config_property_name]
                    if sysctl.ctl_type in (
                        freebsd_sysctl.types.NODE,
                        freebsd_sysctl.types.INT,
                    ):
                        sysctl_state_names = ["disable", "inherit", "new"]
                        if value in sysctl_state_names:
                            value = sysctl_state_names.index(value)
                else:
                    continue

            jail_params[sysctl.jail_arg_name.rstrip(".")] = value

        jail_params["persist"] = None
        return jail_params

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
                    output = return_statement.value  # noqa: T484
                    return output
        except (KeyboardInterrupt, SystemExit):
            raise libioc.errors.JailExecutionAborted(
                jail=self,
                logger=None
            )

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
        if hook_name in ["created", "poststart"]:
            _identifier = str(shlex.quote(self.identifier))
            _jls_command = f"/usr/sbin/jls -j {_identifier} jid"
            command_string = (
                "IOC_JID="
                f"$({_jls_command} 2>&1 || echo -1)"
                "\n" + command_string
            )
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

    def __start_vimage_network(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.JailNetworkSetup', None, None]:
        event = libioc.events.JailNetworkSetup(
            jail=self,
            scope=event_scope
        )
        yield event.begin()
        for network in self.networks:
            yield from network.setup(event_scope=event.scope)
        yield event.end()

    def __start_network(
        self,
        event_scope: 'libioc.events.Scope'
    ) -> typing.Generator['libioc.events.IocEvnet', None, None]:
        if self.config["vnet"] is True:
            yield from self.__start_vimage_network(event_scope)
            yield from self.__configure_localhost_commands(event_scope)
            yield from self.__configure_routes_commands(event_scope)
            if self.host.ipfw_enabled is True:
                self.logger.verbose(
                    f"Disabling IPFW in the jail {self.full_name}"
                )
                self.exec(["service", "ipfw", "onestop"])
        else:
            yield from self._start_non_vimage_network(event_scope)

    def _start_non_vimage_network(
        self,
        event_scope: 'libioc.event.Scope'
    ) -> typing.Generator['libioc.events.IocEvnet', None, None]:
        yield from self.__apply_non_vnet_network(
            force=False,
            event=libioc.events.JailNetworkSetup,
            event_scope=event_scope,
            teardown=False
        )

    def _stop_non_vimage_network(
        self,
        force: bool,
        event_scope: 'libioc.events.Scope'
    ) -> typing.Generator['libioc.events.JailNetworkTeardown', None, None]:
        yield from self.__apply_non_vnet_network(
            force=force,
            event=libioc.events.JailNetworkTeardown,
            event_scope=event_scope,
            teardown=True
        )

    def __apply_non_vnet_network(
        self,
        force: bool,
        event: 'libioc.event.IocEvent',
        event_scope: 'libioc.events.Scope',
        teardown: bool=False
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        network_event = event(
            jail=self,
            scope=event_scope
        )
        yield network_event.begin()
        try:
            for protocol in (4, 6,):
                config_value = self.config[f"ip{protocol}_addr"]
                if config_value is None:
                    continue
                for nic, addresses in config_value.items():
                    if addresses is None:
                        continue
                    for address in addresses:
                        if isinstance(address, str):
                            # skip DHCP and ACCEPT_RTADV
                            continue
                        inet = "inet" if (protocol == 4) else "inet6"
                        command = [
                            "/sbin/ifconfig",
                            nic,
                            inet,
                            str(address)
                        ]
                        if teardown is True:
                            command.append("remove")
                        else:
                            command.append("alias")
                        libioc.helpers.exec(command, logger=self.logger)
        except Exception:
            yield network_event.fail()
            if (force is False) or (teardown is False):
                raise
            else:
                return
        yield network_event.end()

    def __stop_vimage_network(
        self,
        jid: int,
        event_scope: 'libioc.events.Scope'
    ) -> typing.Generator['libioc.events.JailNetworkTeardown', None, None]:
        event = libioc.events.JailNetworkTeardown(
            jail=self,
            scope=event_scope
        )
        yield event.begin()

        for network in self.networks:
            yield from network.teardown(jid, event_scope=event.scope)

        yield event.end()

    def __configure_localhost_commands(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.VnetInterfaceConfig', None, None]:
        event = libioc.events.VnetSetupLocalhost(
            jail=self,
            scope=event_scope
        )
        yield event.begin()
        try:
            self.exec(["/sbin/ifconfig", "lo0", "localhost"])
        except Exception as e:
            yield event.fail(e)
            raise e
        yield event.end()

    def _apply_resource_limits(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocageEvent', None, None]:

        event = libioc.events.JailResourceLimitAction(
            jail=self,
            scope=event_scope
        )
        yield event.begin()

        if self.__resource_limits_enabled is False:
            yield event.skip("disabled")
            return

        skipped = True
        for key in libioc.Config.Jail.Properties.ResourceLimit.properties:
            try:
                rlimit_prop = self.config[key]
                if rlimit_prop.is_unset is True:
                    continue
            except (KeyError, AttributeError):
                continue

            rule = f"jail:{self.identifier}:{key}:{rlimit_prop.limit_string}"
            try:
                libioc.helpers.exec(
                    ["/usr/bin/rctl", "-a", rule],
                    logger=self.logger
                )
                skipped = False
            except Exception:
                yield event.fail()
                raise

        if skipped is True:
            yield event.skip()
        else:
            yield event.end()

    @property
    def __resource_limits_enabled(self) -> bool:
        return (self.config["rlimits"] is True)

    def __clear_resource_limits(
        self,
        force: bool,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.JailResourceLimitAction', None, None]:
        jailResourceLimitActionEvent = libioc.events.JailResourceLimitAction(
            jail=self,
            scope=event_scope
        )

        yield jailResourceLimitActionEvent.begin()

        if self.__resource_limits_enabled is False:
            yield jailResourceLimitActionEvent.skip()
            return

        self.logger.verbose("Clearing resource limits")
        stdout, _, returncode = libioc.helpers.exec(
            " ".join([
                "/usr/bin/rctl",
                "-r",
                f"jail:{self.identifier}",
                "2>&1"
            ]),
            ignore_error=True,
            shell=True  # nosec: B604
        )

        if (returncode > 0) and ("No such process" not in stdout):
            yield jailResourceLimitActionEvent.fail()
            if force is False:
                raise libioc.errors.ResourceLimitActionFailed(
                    action=f"clear resource limits of jail {self.full_name}",
                    logger=self.logger
                )

        yield jailResourceLimitActionEvent.end()

    @property
    def _allow_mount(self) -> int:
        if self._allow_mount_zfs == 1:
            return 1
        return int(self._get_value("allow_mount"))

    @property
    def _allow_mount_zfs(self) -> int:
        if self.config["jail_zfs"] is True:
            return 1
        return int(self._get_value("allow_mount_zfs"))

    def __configure_routes_commands(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.VnetInterfaceConfig', None, None]:
        event = libioc.events.VnetSetRoutes(
            jail=self,
            scope=event_scope
        )
        yield event.begin()
        try:
            defaultrouter = self.config["defaultrouter"]
            defaultrouter6 = self.config["defaultrouter6"]

            commands: typing.List[str] = []

            if defaultrouter is not None:
                commands += list(defaultrouter.apply(jail=self))

            if defaultrouter6 is not None:
                commands += list(defaultrouter6.apply(jail=self))

            if len(commands) == 0:
                self.logger.spam("no static routes configured")

            self.exec(["/bin/sh", "-c", "\n".join(commands)])
        except Exception as e:
            yield event.fail(e)
            raise e
        yield event.end()

    def require_jail_is_template(self, log_errors: bool=True) -> None:
        """Raise JailIsTemplate exception if the jail is a template."""
        if self.config['template'] is False:
            raise libioc.errors.JailNotTemplate(
                jail=self,
                logger=(self.logger if log_errors else None)
            )

    def require_jail_match_hostid(self, log_errors: bool=True) -> None:
        """Raise JailIsTemplate exception if the jail is a template."""
        if self.hostid_check_ok is False:
            raise libioc.errors.JailHostIdMismatch(
                jail=self,
                host_hostid=self.host.id,
                logger=(self.logger if log_errors else None)
            )

    @property
    def hostid_check_ok(self) -> bool:
        """Return true if the hostid check passes."""
        if self.config["hostid_strict_check"] is False:
            self.logger.spam("hostid_strict_check is disabled")
            return True
        jail_hostid = self.config["hostid"]
        if (jail_hostid is None) or (jail_hostid == self.host.id):
            return True
        return False

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
        self.query_jid()
        return self.jid is not None

    @property
    def jid(self) -> typing.Optional[int]:
        """Return a jails JID if it is running or None."""
        try:
            return self.__jid
        except AttributeError:
            self.query_jid()
        return self.__jid

    def query_jid(self) -> None:
        """Invoke update of the jails JID."""
        try:
            jid = int(libjail.get_jid_by_name(self.identifier))
            self.__jid = jid if (jid > 0) else None
        except Exception:
            self.__jid = None

    @property
    def env(self) -> typing.Dict[str, str]:
        """Return the environment variables for hook scripts."""
        jail_env: typing.Dict[str, str]
        if self.config["exec_clean"] is False:
            jail_env = os.environ.copy()
        else:
            jail_env = {}

        for prop in self.config.all_properties:
            prop_name = f"IOC_{prop.replace('.', '_').upper()}"
            jail_env[prop_name] = str(self.config[prop])

        jail_env["IOC_JAIL_PATH"] = self.root_dataset.mountpoint
        jail_env["IOC_JID"] = str(self.jid)
        jail_env["PATH"] = ":".join((
            "/sbin",
            "/bin",
            "/usr/sbin",
            "/usr/bin",
            "/usr/local/sbin",
            "/usr/local/bin",
        ))

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

            event_scope (libioc.events.Scope): (default=None)

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
        stdout = ""
        for event in events:
            if isinstance(
                event,
                libioc.events.JailCommand
            ) and event.done:
                stdout = event.stdout
        return stdout
