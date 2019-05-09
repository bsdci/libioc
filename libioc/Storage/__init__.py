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
"""Abstraction of jail storage operations."""
import grp
import os
import pwd
import typing

import libioc.events
import libioc.helpers
import libioc.helpers_object


class Storage:
    """Abstraction of jail storage operations."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        zfs: typing.Optional['libioc.ZFS.ZFS']=None,
        safe_mode: bool=True,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)
        self.jail = jail

        # safe-mody only attaches zfs datasets to jails that were tagged with
        # jailed=on already exist
        self.safe_mode = safe_mode

    def clone_resource(
        self,
        resource: 'libioc.Resource.Resource'
    ) -> None:
        """Clone another resource to a the current dataset_name."""
        if isinstance(resource, libioc.Release.ReleaseGenerator) is True:
            self._clone_release(resource)
        else:
            self._clone_jail(resource)

    def _clone_release(
        self,
        release: 'libioc.Release.ReleaseGenerator'
    ) -> None:
        """Clone a release to a the current dataset_name."""
        self.zfs.clone_snapshot(
            release.latest_snapshot,
            self.jail.root_dataset_name
        )
        jail_name = self.jail.humanreadable_name
        self.logger.verbose(
            f"Cloned release '{release.name}' to {jail_name}"
        )

    def _clone_jail(
        self,
        jail: 'libioc.Jail.JailGenerator'
    ) -> None:
        """Clone a release to a the current dataset_name."""
        self.zfs.clone_dataset(
            jail.root_dataset,
            self.jail.root_dataset_name
        )
        jail_name = self.jail.humanreadable_name
        self.logger.verbose(
            f"Cloned jail '{jail.name}' to {jail_name}"
        )

    def rename(
        self,
        new_name: str,
        event_scope: typing.Optional[int]=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Rename the dataset and its snapshots."""
        for event in self._rename_dataset(new_name, event_scope=event_scope):
            yield event
        for event in self._rename_snapshot(new_name, event_scope=event_scope):
            yield event

    def teardown(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.TeardownSystemMounts', None, None]:
        """Unmount system mountpoints and devices from a jail."""

        system_mountpoints = list(filter(
            os.path.isdir,
            map(
                self.__get_absolute_path_from_jail_asset,
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

        event = libioc.events.TeardownSystemMounts(
            jail=self.jail,
            scope=event_scope
        )
        yield event.begin()

        try:
            for mountpoint in system_mountpoints:
                self.jail.require_relative_path(mountpoint)
        except Exception as e:
            yield event.fail(str(e))
            raise e

        has_unmounted_any = False
        try:
            for mountpoint in system_mountpoints:
                if os.path.ismount(mountpoint) is False:
                    continue
                libioc.helpers.umount(
                    mountpoint=mountpoint,
                    force=True,
                    logger=self.logger
                )
                has_unmounted_any = True
        except Exception:
            yield event.fail("Failed to unmount system mountpoints")
            raise

        if has_unmounted_any is False:
            yield event.skip()
        else:
            yield event.end()

    def __get_absolute_path_from_jail_asset(
        self,
        value: str
    ) -> libioc.Types.AbsolutePath:
        return libioc.Types.AbsolutePath(f"{self.jail.root_path}{value}")

    def _rename_dataset(
        self,
        new_name: str,
        event_scope: typing.Optional[int]
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:

        current_dataset_name = self.jail.dataset.name
        renameDatasetEvent = libioc.events.ZFSDatasetRename(
            dataset=self.jail.dataset,
            scope=event_scope
        )
        yield renameDatasetEvent.begin()

        try:
            new_dataset_name = "/".join([
                self.jail.host.datasets[self.jail.source].jails.name,
                new_name
            ])
            dataset = self.jail.dataset
            dataset.rename(new_dataset_name)
            self.jail._dataset = self.zfs.get_dataset(new_dataset_name)
            self.jail.dataset_name = new_dataset_name
            self.logger.verbose(
                f"Dataset {current_dataset_name} renamed to {new_dataset_name}"
            )
            yield renameDatasetEvent.end()
        except BaseException as e:
            yield renameDatasetEvent.fail(e)

    def _rename_snapshot(
        self,
        new_name: str,
        event_scope: typing.Optional[int]
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:

        root_dataset_properties = self.jail.root_dataset.properties

        renameSnapshotEvent = libioc.events.ZFSSnapshotRename(
            snapshot=self.jail.dataset,
            scope=event_scope
        )
        yield renameSnapshotEvent.begin()

        if "origin" not in root_dataset_properties:
            yield renameSnapshotEvent.skip()
            return

        origin_snapshot_name = str(root_dataset_properties["origin"].value)

        if origin_snapshot_name == '':
            yield renameSnapshotEvent.skip()
            return

        snapshot = self.zfs.get_snapshot(origin_snapshot_name)

        try:
            new_snapshot_name = f"{snapshot.parent.name}@{new_name}"
            snapshot.rename(new_snapshot_name)
            yield renameSnapshotEvent.end()
        except BaseException as e:
            yield renameSnapshotEvent.fail(e)

    def create_jail_mountpoint(self, basedir: str) -> None:
        """Ensure the destination mountpoint exists relative to the jail."""
        basedir = f"{self.jail.root_dataset.mountpoint}/{basedir}"
        if os.path.islink(basedir):
            self.logger.verbose("Deleting existing symlink {basedir}")
            os.unlink(basedir)
        libioc.helpers.makedirs_safe(basedir)

    def _mount_procfs(self) -> None:
        try:
            if self.jail.config["mount_procfs"] is True:
                libioc.helpers.exec([
                    "mount"
                    "-t",
                    "procfs"
                    "proc"
                    f"{self.jail.root_dataset.mountpoint}/proc"
                ])
        except KeyError:
            raise libioc.errors.MountFailed(
                "procfs",
                logger=self.logger
            )

    # ToDo: Remove unused function?
    def _mount_linprocfs(self) -> None:
        try:
            if not self.jail.config["mount_linprocfs"]:
                return
        except KeyError:
            pass

        linproc_path = self._jail_mkdirp("/compat/linux/proc")

        try:
            if self.jail.config["mount_procfs"] is True:
                libioc.helpers.exec([
                    "mount"
                    "-t",
                    "linprocfs",
                    "linproc",
                    linproc_path
                ])
        except KeyError:
            raise libioc.errors.MountFailed("linprocfs")

    def _jail_mkdirp(
        self,
        directory: str,
        permissions: int=0o775,
        user: str="root",
        group: str="wheel"
    ) -> str:

        uid = pwd.getpwnam(user).pw_uid
        gid = grp.getgrnam(group).gr_gid
        folder = f"{self.jail.root_dataset.mountpoint}{directory}"
        if not os.path.isdir(folder):
            os.makedirs(folder, permissions)
            os.chown(folder, uid, gid, follow_symlinks=False)
        return str(os.path.abspath(folder))
