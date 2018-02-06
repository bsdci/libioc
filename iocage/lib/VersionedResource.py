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
import libzfs

import iocage.lib.Resource
import iocage.lib.Jail


class ResourceSnapshots:

    def __init__(self, resource: iocage.lib.Resource.Resource) -> None:
        self.resource = resource

    def __iter__(self):
        return self.resource.dataset.snapshots

    def create(self, snapshot_name: str) -> None:
        self._ensure_dataset_unlocked()
        snapshot_identifier = self._get_snapshot_identifier(snapshot_name)
        try:
            self.resource.dataset.snapshot(snapshot_identifier, recursive=True)
        except libzfs.ZFSException as e:
            raise iocage.lib.errors.SnapshotCreation(
                reason=str(e),
                logger=self.resource.logger
            )

        self.resource.logger.verbose(
            f"Snapshot created: {snapshot_identifier}"
        )

    def delete(self, snapshot_name: str) -> None:
        self._ensure_dataset_unlocked()
        snapshot = self._get_snapshot(snapshot_name)
        try:
            snapshot.delete(recursive=True)
        except libzfs.ZFSException as e:
            raise iocage.lib.errors.SnapshotDeletion(
                reason=str(e),
                logger=self.resource.logger
            )

    def rollback(self, snapshot_name: str, force: bool=False) -> None:
        self._ensure_dataset_unlocked()

        snapshot = self._get_snapshot(snapshot_name)
        try:
            for snap in reversed(list(snapshot.parent.snapshots_recursive)):
                snap.rollback(force=force)
        except libzfs.ZFSException as e:
            raise iocage.lib.errors.SnapshotRollback(
                reason=str(e),
                logger=self.resource.logger
            )

    def _get_snapshot_identifier(self, snapshot_name: str) -> str:
        return f"{self.resource.dataset.name}@{snapshot_name}"

    def _get_snapshot(self, snapshot_name: str) -> libzfs.ZFSSnapshot:
        identifier = self._get_snapshot_identifier(snapshot_name)

        try:
            zfs = self.resource.zfs
            snap = zfs.get_snapshot(identifier)  # type: libzfs.ZFSSnapshot
            return snap
        except libzfs.ZFSException:
            raise iocage.lib.errors.SnapshotNotFound(
                snapshot_name=snapshot_name,
                dataset_name=self.resource.dataset.name,
                logger=self.resource.logger
            )

    def _ensure_dataset_unlocked(self) -> None:
        """
        Prevent operations on datasets in use (e.g. running jails)
        """
        if isinstance(self, iocage.lib.Jail.JailGenerator):
            self.resource.require_jail_stopped()


class VersionedResource(iocage.lib.Resource.Resource):

    _snapshots: ResourceSnapshots

    @property
    def snapshots(self) -> ResourceSnapshots:

        if "_snapshots" not in object.__dir__(self):
            self._snapshots = ResourceSnapshots(self)

        return self._snapshots
