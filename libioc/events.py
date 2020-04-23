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
"""ioc events collection."""
import typing
from timeit import default_timer as timer

import libioc.errors

# MyPy
import libzfs

EVENT_STATUS = (
    "pending",
    "done",
    "failed"
)


class Scope(list):
    """An independent event history scope."""

    PENDING_COUNT: int

    def __init__(self) -> None:
        self.PENDING_COUNT = 0
        super().__init__([])


class IocEvent:
    """The base event class of liblibioc."""

    _scope: Scope

    identifier: typing.Optional[str]
    _started_at: float
    _stopped_at: float
    _pending: bool
    skipped: bool
    done: bool
    reverted: bool
    error: typing.Optional[typing.Union[bool, BaseException]]
    _rollback_steps: typing.List[typing.Callable[[], typing.Optional[
        typing.Generator['IocEvent', None, None]
    ]]]
    _child_events: typing.List['IocEvent']

    def __init__(
        self,
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:
        """Initialize an IocEvent."""
        if scope is not None:
            self.scope = scope
        else:
            self.scope = Scope()

        for event in self.scope:
            if event.__hash__() == self.__hash__():
                return event  # type: ignore

        self._pending = False
        self.skipped = False
        self.done = True
        self.reverted = False
        self.error = None
        self._rollback_steps = []
        self._child_events = []

        self._rollback_steps = []
        self.number = len(self.scope) + 1
        self.parent_count = self.scope.PENDING_COUNT

        self.message = message

    @property
    def scope(self) -> Scope:
        """Return the currently used event scope."""
        return self._scope

    @scope.setter
    def scope(self, scope: typing.Optional[Scope]) -> None:
        if scope is None:
            self._scope = Scope()
        else:
            self._scope = scope

    def get_state_string(
        self,
        error: str="failed",
        skipped: str="skipped",
        done: str="done",
        pending: str="pending"
    ) -> str:
        """Get a humanreadable string according to the jail state."""
        if self.error is not None:
            return error

        if self.skipped is True:
            return skipped

        if self.done is True:
            return done

        return pending

    def child_event(self, event: 'IocEvent') -> 'IocEvent':
        """Append the event to the child_events for later notification."""
        self._child_events.append(event)
        return event

    def add_rollback_step(self, method: typing.Callable[[], None]) -> None:
        """Add a rollback step that is executed when the event fails."""
        self._rollback_steps.append(method)

    def rollback(
        self
    ) -> typing.Optional[typing.Generator['IocEvent', None, None]]:
        """Rollback all rollback steps in reverse order."""
        if self.reverted is True:
            return

        self.reverted = True

        # Notify child_events in reverse order
        for event in reversed(self._child_events):
            rollback_actions = event.rollback()
            if rollback_actions is not None:
                for rollback_action in rollback_actions:
                    yield rollback_action

        # Execute rollback steps in reverse order
        reversed_rollback_steps = reversed(self._rollback_steps)
        self._rollback_steps = []
        for revert_step in reversed_rollback_steps:
            revert_events = revert_step()
            if revert_events is not None:
                for event in revert_events:
                    yield event

    @property
    def type(self) -> str:
        """
        Return the events type.

        The event type is obtained from an IocEvent's class name.
        """
        return type(self).__name__

    @property
    def pending(self) -> bool:
        """Return True if the event is pending."""
        return self._pending

    @pending.setter
    def pending(self, state: bool) -> None:
        """
        Set the pending state.

        Changes invoke internal processing as for example the calculation of
        the event duration and the global PENDING_COUNT.
        """
        current = self._pending
        new_state = (state is True)

        if current == new_state:
            return

        if new_state is True:
            try:
                self._started_at
                raise libioc.errors.EventAlreadyFinished(event=self)
            except AttributeError:
                self._started_at = float(timer())
        if new_state is False:
            self._stopped_at = float(timer())

        self._pending = new_state
        self.scope.PENDING_COUNT += 1 if (state is True) else -1

    @property
    def duration(self) -> typing.Optional[float]:
        """Return the duration of finished events."""
        try:
            return self._stopped_at - self._started_at
        except AttributeError:
            return None

    def _update_message(
        self,
        message: typing.Optional[str]=None,
    ) -> None:
        self.message = message

    def begin(self, message: typing.Optional[str]=None) -> 'IocEvent':
        """Begin an event."""
        self._update_message(message)
        self.pending = True
        self.done = False
        self.parent_count = self.scope.PENDING_COUNT - 1
        return self

    def end(self, message: typing.Optional[str]=None) -> 'IocEvent':
        """Successfully finish an event."""
        self._update_message(message)
        self.done = True
        self.pending = False
        self.parent_count = self.scope.PENDING_COUNT
        return self

    def step(self, message: typing.Optional[str]=None) -> 'IocEvent':
        """Reflect partial event progress."""
        self._update_message(message)
        self.parent_count = self.scope.PENDING_COUNT
        return self

    def skip(self, message: typing.Optional[str]=None) -> 'IocEvent':
        """Mark an event as skipped."""
        self._update_message(message)
        self.skipped = True
        self.pending = False
        self.parent_count = self.scope.PENDING_COUNT
        return self

    def fail(
        self,
        exception: bool=True,
        message: typing.Optional[str]=None
    ) -> 'IocEvent':
        """End an event with a failure."""
        list(self.fail_generator(exception=exception, message=message))
        return self

    def fail_generator(
        self,
        exception: bool=True,
        message: typing.Optional[str]=None
    ) -> typing.Generator['IocEvent', None, None]:
        """End an event with a failure via a generator of rollback steps."""
        self._update_message(message)
        self.error = exception

        actions = self.rollback()
        if isinstance(actions, typing.Generator):
            for action in actions:
                yield action

        self.pending = False
        self.parent_count = self.scope.PENDING_COUNT

        yield self

    def __hash__(self) -> typing.Any:
        """Compare an event by its type and identifier."""
        has_identifier = ("identifier" in self.__dir__()) is True
        identifier = "generic" if has_identifier is False else self.identifier
        return hash((self.type, identifier))


# Jail


class JailEvent(IocEvent):
    """Any event related to a jail."""

    jail: 'libioc.Jail.JailGenerator'
    identifier: typing.Optional[str]

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        try:
            self.identifier = jail.full_name
        except AttributeError:
            self.identifier = None
        self.jail = jail
        IocEvent.__init__(self, message=message, scope=scope)


class JailRename(JailEvent):
    """Change the name of a jail."""

    current_name: str
    new_name: str

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        current_name: str,
        new_name: str,
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        self.current_name = current_name
        self.new_name = new_name
        JailEvent.__init__(self, jail=jail, message=message, scope=scope)


class JailStop(JailEvent):
    """Destroy the jail."""

    pass


class JailRemove(JailEvent):
    """Remove the jail(2)."""

    pass


class TeardownSystemMounts(JailStop):
    """Teardown a jails mountpoints."""

    pass


class JailResourceLimitAction(JailEvent):
    """Set or unset a jails resource limits."""

    pass


class VnetEvent(JailEvent):
    """A group of events around VNET operations."""

    pass


class JailNetworkSetup(VnetEvent):
    """Start VNET networks."""

    pass


class JailNetworkTeardown(JailStop):
    """Teardown a jails network."""

    pass


class VnetInterfaceConfig(JailNetworkSetup):
    """Configure VNET network interfaces and firewall."""

    pass


class VnetSetupLocalhost(JailNetworkSetup):
    """Configure a VNET jails localhost."""

    pass


class VnetSetRoutes(JailNetworkSetup):
    """Set a VNET jails network routes."""

    pass


class JailAttach(JailEvent):
    """Remove the jail(2)."""

    pass


class DevFSEvent(JailEvent):
    """Group of events that occor on DevFS operations."""

    pass


class MountDevFS(DevFSEvent):
    """Mount /dev into a jail."""

    pass


class MountFdescfs(DevFSEvent):
    """Mount /dev/fd into a jail."""

    pass


class FstabEvent(JailEvent):
    """Group of events that occor on Fstab operations."""

    pass


class MountFstab(FstabEvent):
    """Mount entries from a jails fstab file."""

    pass


class UnmountFstab(FstabEvent):
    """Unmount entries from a jails fstab file."""

    pass


class JailHook(JailEvent):
    """Run jail hook."""

    stdout: typing.Optional[str]

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        self.stdout = None
        super().__init__(
            jail=jail,
            message=message,
            scope=scope
        )

    def end(
        self,
        message: typing.Optional[str]=None,
        stdout: str=""
    ) -> 'IocEvent':
        """Successfully finish an event."""
        self.stdout = stdout
        return super().end(message)

    def fail(
        self,
        exception: bool=True,
        message: typing.Optional[str]=None,
        stdout: str=""
    ) -> 'IocEvent':
        """Successfully finish an event."""
        self.stdout = stdout
        return super().fail(
            exception=exception,
            message=message
        )


class JailHookPrestart(JailHook):
    """Run jail prestart hook."""

    pass


class JailHookStart(JailHook):
    """Run jail start hook."""

    pass


class JailCommand(JailHook):
    """Run command in a jail."""

    stdout: typing.Optional[str]
    stderr: typing.Optional[str]
    code: typing.Optional[int]


class JailHookCreated(JailHook):
    """Run jail created hook."""

    pass


class JailHookPoststart(JailHook):
    """Run jail poststart hook."""

    pass


class JailHookPrestop(JailHook):
    """Run jail prestop hook."""

    pass


class JailHookStop(JailHook):
    """Run jail stop hook."""

    pass


class JailHookPoststop(JailHook):
    """Run jail poststop hook."""

    pass


class JailFstabUpdate(JailEvent):
    """Update a jails fstab file."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        JailEvent.__init__(self, jail=jail, message=message, scope=scope)


class JailResolverConfig(JailEvent):
    """Update a jails /etc/resolv.conf file."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        JailEvent.__init__(self, jail=jail, message=message, scope=scope)


class JailZFSShare(JailEvent):
    """Group of events that mounts or unmounts shared ZFS datasets."""

    pass


class BasejailStorageConfig(JailEvent):
    """Mount or unmount basejail storage of a jail."""

    pass


class AttachZFSDataset(JailZFSShare):
    """Mount an individual dataset when starting a jail with shared ZFS."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        dataset: libzfs.ZFSDataset,
        scope: typing.Optional[Scope]=None
    ) -> None:

        msg = f"Dataset {dataset.name} was attached to Jail {jail.full_name}"
        JailEvent.__init__(self, jail=jail, message=msg, scope=scope)


class JailClone(JailEvent):
    """Clone a jail."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        JailEvent.__init__(self, jail=jail, message=message, scope=scope)

# Release


class ReleaseEvent(IocEvent):
    """Event related to a release."""

    release: 'libioc.Release.ReleaseGenerator'

    def __init__(
        self,
        release: 'libioc.Release.ReleaseGenerator',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        self.identifier = release.full_name
        self.release = release
        IocEvent.__init__(self, message=message, scope=scope)


class ReleaseUpdate(ReleaseEvent):
    """Update a release."""

    pass


class FetchRelease(ReleaseEvent):
    """Fetch release assets."""

    pass


class ReleasePrepareStorage(FetchRelease):
    """Prepare the storage of a release before fetching it."""

    pass


class ReleaseDownload(FetchRelease):
    """Download release assets."""

    pass


class ReleaseAssetDownload(FetchRelease):
    """Download release assets."""

    pass


class ReleaseExtraction(FetchRelease):
    """Extract a release asset."""

    pass


class ReleaseCopyBase(FetchRelease):
    """Copy the basejail folders of a release into individual ZFS datasets."""

    pass


class ReleaseConfiguration(FetchRelease):
    """Pre-configure a release with reasonable defaults."""

    pass


class ReleaseUpdatePull(ReleaseUpdate):
    """Pull resource updater and patches from the remote."""

    pass


class ReleaseUpdateDownload(ReleaseUpdate):
    """Download resource updates/patches."""

    pass


# Resource


class ResourceEvent(IocEvent):
    """Event with a resource."""

    def __init__(
        self,
        resource: 'libioc.Resource.Resource',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        self.identifier = resource.full_name
        IocEvent.__init__(self, message)


class ResourceUpdate(ResourceEvent):
    """Update a resource."""

    pass


class RunResourceUpdate(ResourceUpdate):
    """Run the update of a resource."""

    pass


class ExecuteResourceUpdate(ResourceUpdate):
    """Execute the updater script in a jail."""

    pass


# ZFS


class ZFSEvent(IocEvent):
    """Event related to ZFS storage."""

    def __init__(
        self,
        zfs_object: libzfs.ZFSObject,
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        self.identifier = zfs_object.name
        self.zfs_object = zfs_object
        IocEvent.__init__(self, message=message, scope=scope)


class ZFSDatasetRename(ZFSEvent):
    """Rename a ZFS dataset."""

    def __init__(
        self,
        dataset: libzfs.ZFSDataset,
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        ZFSEvent.__init__(
            self,
            zfs_object=dataset,
            message=message,
            scope=scope
        )


class ZFSDatasetDestroy(ZFSEvent):
    """Rename a ZFS dataset."""

    def __init__(
        self,
        dataset: libzfs.ZFSDataset,
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        ZFSEvent.__init__(
            self,
            zfs_object=dataset,
            message=message,
            scope=scope
        )


class ZFSSnapshotRename(ZFSEvent):
    """Rename a ZFS snapshot."""

    def __init__(
        self,
        snapshot: libzfs.ZFSDataset,
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        ZFSEvent.__init__(
            self,
            zfs_object=snapshot,
            message=message,
            scope=scope
        )


class ZFSSnapshotClone(ZFSEvent):
    """Clone a ZFS snapshot to a target."""

    def __init__(
        self,
        snapshot: libzfs.ZFSDataset,
        target: str,
        scope: typing.Optional[Scope]=None
    ) -> None:

        message = f"Could not clone to {target}"
        ZFSEvent.__init__(
            self,
            zfs_object=snapshot,
            message=message,
            scope=scope
        )


class ZFSSnapshotRollback(ZFSEvent):
    """Rollback a ZFS dataset to a snapshot."""

    def __init__(
        self,
        snapshot: libzfs.ZFSSnapshot,
        target: str,
        scope: typing.Optional[Scope]=None
    ) -> None:

        message = f"Rolling back {target} to snapshot {snapshot.snapshot_name}"
        ZFSEvent.__init__(
            self,
            zfs_object=snapshot,
            message=message,
            scope=scope
        )


# Backup


class ResourceBackup(IocEvent):
    """Events that occur when backing up a resource."""

    resource: 'libioc.Resource.Resource'

    def __init__(
        self,
        resource: 'libioc.Resource.Resource',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        if "name" in resource.__dir__():
            self.identifier = resource.name
        else:
            self.identifier = resource.dataset_name
        self.resource = resource
        IocEvent.__init__(
            self,
            message=message,
            scope=scope
        )


class ExportConfig(ResourceBackup):
    """Event that occurs when the config of a resource is exported."""

    pass


class ExportFstab(ResourceBackup):
    """Event that occurs when the fstab file of a jail is exported."""

    pass


class ExportRootDataset(ResourceBackup):
    """Export a resources root dataset."""

    pass


class ExportOtherDatasets(ResourceBackup):
    """Event that occurs when other resource datasets get exported."""

    pass


class ExportOtherDataset(ResourceBackup):
    """Export one of a resources datasets."""

    dataset: libzfs.ZFSDataset

    def __init__(
        self,
        resource: 'libioc.Resource.Resource',
        dataset: libzfs.ZFSDataset,
        flags: typing.Set[libzfs.SendFlag]=set(),
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        self.dataset = dataset
        self.flags = flags
        ResourceBackup.__init__(
            self,
            resource=resource,
            message=message,
            scope=scope
        )

        # The identifier is the dataset name relative to the resource
        relative_dataset_name = dataset.name[len(resource.dataset_name):]
        self.identifier = str(self.identifier) + str(relative_dataset_name)


class BundleBackup(ResourceBackup):
    """Bundle exported data into a backup archive."""

    destination: str

    def __init__(
        self,
        destination: str,
        resource: 'libioc.Resource.Resource',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        self.destination = destination
        ResourceBackup.__init__(
            self,
            resource=resource,
            message=message,
            scope=scope
        )


# Backup import/restore


class ExtractBundle(ResourceBackup):
    """Extract a bundled backup archive."""

    destination: str
    resource: 'libioc.Resource.Resource'

    def __init__(
        self,
        source: str,
        destination: str,
        resource: 'libioc.Resource.Resource',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        self.destination = destination
        self.resource = resource
        ResourceBackup.__init__(
            self,
            resource=resource,
            message=message,
            scope=scope
        )


class ImportConfig(ResourceBackup):
    """Event that occurs when the config of a resource is imported."""

    pass


class ImportFstab(ResourceBackup):
    """Event that occurs when the fstab file of a jail is imported."""

    pass


class ImportRootDataset(ResourceBackup):
    """Import data from an an archived root dataset."""

    pass


class ImportOtherDatasets(ResourceBackup):
    """Event that occurs when other resource datasets get exported."""

    pass


class ImportOtherDataset(ResourceBackup):
    """Export one of a resources datasets."""

    def __init__(
        self,
        resource: 'libioc.Resource.Resource',
        dataset_name: str,
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        self.identifier = dataset_name
        ResourceBackup.__init__(
            self,
            resource=resource,
            scope=scope
        )

    @property
    def dataset_name(self) -> str:
        """Map the event identifier to dataset_name."""
        return str(self.identifier)


# CLI


class JailRestart(JailEvent):
    """Restart a jail."""

    pass


class JailSoftShutdown(JailEvent):
    """Soft-restart a jail."""

    pass


class JailStart(JailEvent):
    """Start a jail."""

    pass


class JailDependantsStart(JailEvent):
    """Start dependant jails."""

    started_jails: typing.List['libioc.Jail.JailGenerator']

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        try:
            self.identifier = jail.full_name
        except AttributeError:
            self.identifier = None
        self.started_jails = []
        JailEvent.__init__(self, jail=jail, message=message, scope=scope)

    def end(
        self,
        message: typing.Optional[str]=None,
        started_jails: typing.List['libioc.Jail.JailGenerator']=[],
    ) -> 'IocEvent':
        """Successfully finish starting dependant Jails."""
        self.started_jails = started_jails
        return JailEvent.end(self, message)


class JailDependantStart(JailEvent):
    """Start one dependant jail."""

    pass


class JailProvisioning(JailEvent):
    """Provision a jail."""

    pass


class JailProvisioningAssetDownload(JailEvent):
    """Provision a jail."""

    pass


# PKG


class PkgEvent(IocEvent):
    """Collection of events related to Pkg."""

    pass


class PackageFetch(PkgEvent):
    """Fetch packages for offline installation."""

    packages: typing.List[str]

    def __init__(
        self,
        packages: typing.List[str],
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        self.identifier = "global"
        self.packages = packages
        IocEvent.__init__(self, message=message, scope=scope)


class BootstrapPkg(JailEvent, PkgEvent):
    """Bootstrap pkg within a jail."""

    pass


class PackageInstall(JailEvent, PkgEvent):
    """Install packages in a jail."""

    def __init__(
        self,
        packages: typing.List[str],
        jail: 'libioc.Jail.JailGenerator',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        self.packages = packages
        JailEvent.__init__(self, jail=jail, message=message, scope=scope)


class PackageRemove(JailEvent, PkgEvent):
    """Remove packages from a jail."""

    def __init__(
        self,
        packages: typing.List[str],
        jail: 'libioc.Jail.JailGenerator',
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None
    ) -> None:

        self.packages = packages
        JailEvent.__init__(self, jail=jail, message=message, scope=scope)


class PackageConfiguration(JailEvent, PkgEvent):
    """Install packages in a jail."""

    pass
