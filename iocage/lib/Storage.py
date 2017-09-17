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
import grp
import os
import pwd

import iocage.lib.helpers


class Storage:
    def __init__(self, jail,
                 zfs=None,
                 safe_mode=True,
                 logger=None):

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)
        self.jail = jail

        # safe-mody only attaches zfs datasets to jails that were tagged with
        # jailed=on already exist
        self.safe_mode = safe_mode

    def clone_release(self, release):
        self.clone_zfs_dataset(
            release.root_dataset_name,
            self.jail.root_dataset_name
        )
        jail_name = self.jail.humanreadable_name
        self.logger.verbose(
            f"Cloned release '{release.name}' to {jail_name}",
            jail=self.jail
        )

    def delete_dataset_recursive(self, dataset, delete_snapshots=True):

        for child in dataset.children:
            self.delete_dataset_recursive(child)

        if dataset.mountpoint is not None:
            self.logger.spam("Unmounting {dataset.name}")
            dataset.umount()

        origin = None
        if delete_snapshots is False:
            origin_property = dataset.properties["origin"]
            if origin_property.value != "":
                origin = origin_property

        self.logger.verbose("Deleting dataset {dataset.name}")
        dataset.delete()

        if origin is not None:
            self.logger.verbose("Deleting snapshot {origin}")
            origin_snapshot = self.zfs.get_snapshot(origin)
            origin_snapshot.delete()

    def clone_zfs_dataset(self, source, target):

        snapshot_name = f"{source}@{self.jail.name}"

        # delete target dataset if it already exists
        try:
            existing_dataset = self.zfs.get_dataset(target)
            self.logger.verbose(
                f"Deleting existing dataset {target}",
                jail=self.jail
            )
            if existing_dataset.mountpoint is not None:
                existing_dataset.umount()
            existing_dataset.delete()
            del existing_dataset
        except:
            pass

        # delete existing snapshot if existing
        existing_snapshot = None
        try:
            existing_snapshot = self.zfs.get_snapshot(snapshot_name)
        except:
            pass

        if existing_snapshot:
            self.logger.verbose(
                f"Deleting existing snapshot {snapshot_name}",
                jail=self.jail
            )
            existing_snapshot.delete()

        # snapshot release
        self.zfs.get_dataset(source).snapshot(snapshot_name)
        snapshot = self.zfs.get_snapshot(snapshot_name)

        # clone snapshot
        try:
            self.logger.verbose(
                f"Cloning snapshot {snapshot_name} to {target}",
                jail=self.jail
            )
            snapshot.clone(target)
        except:
            parent = "/".join(target.split("/")[:-1])
            self.logger.debug(
                "Cloning was unsuccessful - "
                f"trying to create the parent dataset '{parent}' first",
                jail=self.jail
            )
            self.zfs.create_dataset(parent)
            snapshot.clone(target)

        target_dataset = self.zfs.get_dataset(target)
        target_dataset.mount()
        self.logger.verbose(
            f"Successfully cloned {source} to {target}",
            jail=self.jail
        )

    def create_jail_mountpoint(self, basedir: str):
        basedir = f"{self.jail.root_dataset.mountpoint}/{basedir}"
        if not os.path.isdir(basedir):
            self.logger.verbose(f"Creating mountpoint {basedir}")
            os.makedirs(basedir)

    def _mount_procfs(self):
        try:
            if self.jail.config["mount_procfs"]:
                iocage.lib.helpers.exec([
                    "mount"
                    "-t",
                    "procfs"
                    "proc"
                    f"{self.jail.root_dataset.mountpoint}/proc"
                ])
        except:
            raise iocage.lib.errors.MountFailed("procfs")

    # ToDo: Remove unused function?
    def _mount_linprocfs(self):
        try:
            if not self.jail.config["mount_linprocfs"]:
                return
        except:
            pass

        linproc_path = self._jail_mkdirp("/compat/linux/proc")

        try:
            if self.jail.config["mount_procfs"]:
                iocage.lib.helpers.exec([
                    "mount"
                    "-t",
                    "linprocfs",
                    "linproc",
                    linproc_path
                ])
        except:
            raise iocage.lib.errors.MountFailed("linprocfs")

    def _unmount_local(self, dataset):
        if dataset.mountpoint:
            dataset.unmount()

    def _jail_mkdirp(
        self,
        directory: str,
        permissions=0o775,
        user: str="root",
        group: str="wheel"
    ) -> str:

        uid = pwd.getpwnam(user).pw_uid
        gid = grp.getgrnam(group).gr_gid
        folder = f"{self.jail.root_dataset.mountpoint}{directory}"
        if not os.path.isdir(folder):
            os.makedirs(folder, permissions)
            os.chown(folder, uid, gid, follow_symlinks=False)  # type: ignore
        return os.path.abspath(folder)
