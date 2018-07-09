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
"""iocage events collection."""
import typing
from timeit import default_timer as timer

import iocage.lib.errors

# MyPy
import iocage.lib.Jail  # noqa: F401
import iocage.lib.Release  # noqa: F401
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


class IocageEvent:
    """The base event class of libiocage."""

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
        typing.Generator['IocageEvent', None, None]
    ]]]
    _child_events: typing.List['IocageEvent']

    def __init__(  # noqa: T484
        self,
        message: typing.Optional[str]=None,
        scope: typing.Optional[Scope]=None,
        **kwargs
    ) -> None:
        """Initialize an IocageEvent."""
        self.scope = scope
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

        self.data = kwargs
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

    def child_event(self, event: 'IocageEvent') -> 'IocageEvent':
        """Append the event to the child_events for later notification."""
        self._child_events.append(event)
        return event

    def add_rollback_step(self, method: typing.Callable[[], None]) -> None:
        """Add a rollback step that is executed when the event fails."""
        self._rollback_steps.append(method)

    def rollback(
        self
    ) -> typing.Optional[typing.Generator['IocageEvent', None, None]]:
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

        The event type is obtained from an IocageEvent's class name.
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
                raise iocage.lib.errors.EventAlreadyFinished(event=self)
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

    def _update_message(self, **kwargs) -> None:  # noqa: T484
        for key in kwargs.keys():
            if key == "message":
                self.message = kwargs["message"]
            else:
                self.data[key] = kwargs[key]

    def begin(self, **kwargs) -> 'IocageEvent':  # noqa: T484
        """Begin an event."""
        self._update_message(**kwargs)
        self.pending = True
        self.done = False
        self.parent_count = self.scope.PENDING_COUNT - 1
        return self

    def end(self, **kwargs) -> 'IocageEvent':  # noqa: T484
        """Successfully finish an event."""
        self._update_message(**kwargs)
        self.done = True
        self.pending = False
        self.parent_count = self.scope.PENDING_COUNT
        return self

    def step(self, **kwargs) -> 'IocageEvent':  # noqa: T484
        """Reflect partial event progress."""
        self._update_message(**kwargs)
        self.parent_count = self.scope.PENDING_COUNT
        return self

    def skip(self, **kwargs) -> 'IocageEvent':  # noqa: T484
        """Mark an event as skipped."""
        self._update_message(**kwargs)
        self.skipped = True
        self.pending = False
        self.parent_count = self.scope.PENDING_COUNT
        return self

    def fail(  # noqa: T484
        self,
        exception: bool=True,
        **kwargs
    ) -> 'IocageEvent':
        """End an event with a failure."""
        list(self.fail_generator(exception=exception, **kwargs))
        return self

    def fail_generator(  # noqa: T484
        self,
        exception: bool=True,
        **kwargs
    ) -> typing.Generator['IocageEvent', None, None]:
        """End an event with a failure via a generator of rollback steps."""
        self._update_message(**kwargs)
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


class JailEvent(IocageEvent):
    """Any event related to a jail."""

    def __init__(  # noqa: T484
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        **kwargs
    ) -> None:

        try:
            self.identifier = jail.full_name
        except AttributeError:
            self.identifier = None

        IocageEvent.__init__(self, jail=jail, **kwargs)


class JailLaunch(JailEvent):
    """Launch a jail."""

    stdout: typing.Optional[str]

    def __init__(  # noqa: T484
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        **kwargs
    ) -> None:
        self.stdout = None
        JailEvent.__init__(self, jail, **kwargs)

    def end(self, stdout, **kwargs) -> 'IocageEvent':  # noqa: T484
        """Successfully finish an event."""
        self.stdout = stdout
        return IocageEvent.end(self, **kwargs)


class JailRename(JailEvent):
    """Change the name of a jail."""

    def __init__(  # noqa: T484
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        current_name: str,
        new_name: str,
        **kwargs
    ) -> None:

        kwargs["current_name"] = current_name
        kwargs["new_name"] = new_name
        JailEvent.__init__(self, jail, **kwargs)


class JailDestroy(JailEvent):
    """Destroy the jail."""

    def __init__(  # noqa: T484
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        **kwargs
    ) -> None:

        JailEvent.__init__(self, jail, **kwargs)


class JailFstabUpdate(JailEvent):
    """Update a jails fstab file."""

    def __init__(  # noqa: T484
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        **kwargs
    ) -> None:

        JailEvent.__init__(self, jail, **kwargs)


class JailClone(JailEvent):
    """Clone a jail."""

    def __init__(  # noqa: T484
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        **kwargs
    ) -> None:

        JailEvent.__init__(self, jail, **kwargs)

# Release


class ReleaseEvent(IocageEvent):
    """Event related to a release."""

    def __init__(  # noqa: T484
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
        **kwargs
    ) -> None:

        self.identifier = release.full_name
        IocageEvent.__init__(self, release=release, **kwargs)


class ReleaseUpdate(ReleaseEvent):
    """Update a release."""

    def __init__(  # noqa: T484
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
        **kwargs
    ) -> None:

        ReleaseEvent.__init__(self, release, **kwargs)


class FetchRelease(ReleaseEvent):
    """Fetch release assets."""

    def __init__(  # noqa: T484
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
        **kwargs
    ) -> None:

        ReleaseEvent.__init__(self, release, **kwargs)


class ReleasePrepareStorage(FetchRelease):
    """Prepare the storage of a release before fetching it."""

    def __init__(  # noqa: T484
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
        **kwargs
    ) -> None:

        FetchRelease.__init__(self, release, **kwargs)


class ReleaseDownload(FetchRelease):
    """Download release assets."""

    def __init__(  # noqa: T484
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
        **kwargs
    ) -> None:

        FetchRelease.__init__(self, release, **kwargs)


class ReleaseExtraction(FetchRelease):
    """Extract a release asset."""

    def __init__(  # noqa: T484
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
        **kwargs
    ) -> None:

        FetchRelease.__init__(self, release, **kwargs)


class ReleaseCopyBase(FetchRelease):
    """Copy the basejail folders of a release into individual ZFS datasets."""

    def __init__(  # noqa: T484
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
        **kwargs
    ) -> None:

        FetchRelease.__init__(self, release, **kwargs)


class ReleaseConfiguration(FetchRelease):
    """Pre-configure a release with reasonable defaults."""

    def __init__(  # noqa: T484
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
        **kwargs
    ) -> None:

        FetchRelease.__init__(self, release, **kwargs)


class ReleaseUpdatePull(ReleaseUpdate):
    """Pull resource updater and patches from the remote."""

    def __init__(  # noqa: T484
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
        **kwargs
    ) -> None:

        ReleaseUpdate.__init__(self, release, **kwargs)


class ReleaseUpdateDownload(ReleaseUpdate):
    """Download resource updates/patches."""

    def __init__(  # noqa: T484
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
        **kwargs
    ) -> None:

        ReleaseUpdate.__init__(self, release, **kwargs)


# Resource


class ResourceEvent(IocageEvent):
    """Event with a resource."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.ResourceGenerator',
        **kwargs
    ) -> None:

        self.identifier = resource.full_name
        IocageEvent.__init__(self, **kwargs)


class ResourceUpdate(ResourceEvent):
    """Update a resource."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.ResourceGenerator',
        **kwargs
    ) -> None:

        ResourceEvent.__init__(self, resource, **kwargs)


class RunResourceUpdate(ResourceUpdate):
    """Run the update of a resource."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.ResourceGenerator',
        **kwargs
    ) -> None:

        ResourceUpdate.__init__(self, resource, **kwargs)


class ExecuteResourceUpdate(ResourceUpdate):
    """Execute the updater script in a jail."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.ResourceGenerator',
        **kwargs
    ) -> None:

        ResourceUpdate.__init__(self, resource, **kwargs)


# ZFS


class ZFSEvent(IocageEvent):
    """Event related to ZFS storage."""

    def __init__(  # noqa: T484
        self,
        zfs_object: libzfs.ZFSObject,
        **kwargs
    ) -> None:

        self.identifier = zfs_object.name
        IocageEvent.__init__(self, zfs_object=zfs_object, **kwargs)


class ZFSDatasetRename(ZFSEvent):
    """Rename a ZFS dataset."""

    def __init__(  # noqa: T484
        self,
        dataset: libzfs.ZFSDataset,
        **kwargs
    ) -> None:

        ZFSEvent.__init__(self, zfs_object=dataset, **kwargs)


class ZFSDatasetDestroy(ZFSEvent):
    """Rename a ZFS dataset."""

    def __init__(  # noqa: T484
        self,
        dataset: libzfs.ZFSDataset,
        **kwargs
    ) -> None:

        ZFSEvent.__init__(self, zfs_object=dataset, **kwargs)


class ZFSSnapshotRename(ZFSEvent):
    """Rename a ZFS snapshot."""

    def __init__(  # noqa: T484
        self,
        snapshot: libzfs.ZFSDataset,
        **kwargs
    ) -> None:

        ZFSEvent.__init__(self, zfs_object=snapshot, **kwargs)


class ZFSSnapshotClone(ZFSEvent):
    """Clone a ZFS snapshot to a target."""

    def __init__(  # noqa: T484
        self,
        snapshot: libzfs.ZFSDataset,
        target: str,
        **kwargs
    ) -> None:

        msg = f"Could not clone to {target}"
        ZFSEvent.__init__(self, msg=msg, zfs_object=snapshot, **kwargs)


class ZFSSnapshotRollback(ZFSEvent):
    """Rollback a ZFS dataset to a snapshot."""

    def __init__(  # noqa: T484
        self,
        snapshot: libzfs.ZFSSnapshot,
        target: str,
        **kwargs
    ) -> None:

        msg = f"Rolling back {target} to snapshot {snapshot.snapshot_name}"
        ZFSEvent.__init__(self, msg=msg, zfs_object=snapshot, **kwargs)


# Backup


class ResourceBackup(IocageEvent):
    """Events that occur when backing up a resource."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        if "name" in resource.__dir__():
            self.identifier = resource.name
        else:
            self.identifier = resource.dataset_name
        IocageEvent.__init__(self, resource=resource, **kwargs)


class ExportConfig(ResourceBackup):
    """Event that occurs when the config of a resource is exported."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        ResourceBackup.__init__(self, resource=resource, **kwargs)


class ExportFstab(ResourceBackup):
    """Event that occurs when the fstab file of a jail is exported."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        ResourceBackup.__init__(self, resource=resource, **kwargs)


class ExportRootDataset(ResourceBackup):
    """Export a resources root dataset."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        ResourceBackup.__init__(self, resource=resource, **kwargs)


class ExportOtherDatasets(ResourceBackup):
    """Event that occurs when other resource datasets get exported."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        ResourceBackup.__init__(self, resource=resource, **kwargs)


class ExportOtherDataset(ResourceBackup):
    """Export one of a resources datasets."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.Resource',
        dataset: libzfs.ZFSDataset,
        **kwargs
    ) -> None:

        ResourceBackup.__init__(
            self,
            resource=resource,
            dataset=dataset,
            **kwargs
        )
        # The identifier is the dataset name relative to the resource
        relative_dataset_name = dataset.name[len(resource.dataset_name):]
        self.identifier = str(self.identifier) + str(relative_dataset_name)


class BundleBackup(ResourceBackup):
    """Bundle exported data into a backup archive."""

    def __init__(  # noqa: T484
        self,
        destination: str,
        resource: 'iocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        ResourceBackup.__init__(
            self,
            resource=resource,
            destination=destination,
            **kwargs
        )


# Backup import/restore


class ExtractBundle(ResourceBackup):
    """Extract a bundled backup archive."""

    def __init__(  # noqa: T484
        self,
        source: str,
        destination: str,
        resource: 'iocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        ResourceBackup.__init__(
            self,
            resource=resource,
            destination=destination,
            **kwargs
        )


class ImportConfig(ResourceBackup):
    """Event that occurs when the config of a resource is imported."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        ResourceBackup.__init__(self, resource=resource, **kwargs)


class ImportFstab(ResourceBackup):
    """Event that occurs when the fstab file of a jail is imported."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        ResourceBackup.__init__(self, resource=resource, **kwargs)


class ImportRootDataset(ResourceBackup):
    """Import data from an an archived root dataset."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        ResourceBackup.__init__(self, resource=resource, **kwargs)


class ImportOtherDatasets(ResourceBackup):
    """Event that occurs when other resource datasets get exported."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.Resource',
        **kwargs
    ) -> None:

        ResourceBackup.__init__(self, resource=resource, **kwargs)


class ImportOtherDataset(ResourceBackup):
    """Export one of a resources datasets."""

    def __init__(  # noqa: T484
        self,
        resource: 'iocage.lib.Resource.Resource',
        dataset_name: str,
        **kwargs
    ) -> None:

        self.identifier = dataset_name
        ResourceBackup.__init__(
            self,
            resource=resource,
            dataset_name=dataset_name,
            **kwargs
        )

# CLI


class JailRestart(JailEvent):
    """Restart a jail."""

    def __init__(  # noqa: T484
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        **kwargs
    ) -> None:

        JailEvent.__init__(self, jail, **kwargs)


class JailShutdown(JailEvent):
    """Shutdown a jail."""

    def __init__(  # noqa: T484
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        **kwargs
    ) -> None:

        JailEvent.__init__(self, jail, **kwargs)


class JailSoftShutdown(JailEvent):
    """Soft-restart a jail."""

    def __init__(  # noqa: T484
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        **kwargs
    ) -> None:

        JailEvent.__init__(self, jail, **kwargs)


class JailStart(JailEvent):
    """Start a jail."""

    def __init__(  # noqa: T484
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        **kwargs
    ) -> None:

        JailEvent.__init__(self, jail, **kwargs)
