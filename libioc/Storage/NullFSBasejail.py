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
"""iocage NullFS basejail storage backend."""
import libioc.Storage
import libioc.Storage.Standalone
import libioc.helpers


class NullFSBasejailStorage(libioc.Storage.Storage):
    """iocage NullFS basejail storage backend."""

    def apply(self, release=None):
        """Attach the jail storage."""
        NullFSBasejailStorage._create_nullfs_directories(self)

    def setup(self, release):
        """Prepare the jail storage."""
        libioc.Storage.Standalone.StandaloneJailStorage.setup(
            self,
            release
        )

    def umount_nullfs(self):
        """
        Unmount all NullFS mounts from fstab.

        In preparation of starting the jail with NullFS mounts all mountpoints
        that are listed in fstab need to be unmounted
        """
        with open(f"{self.jail.path}/fstab") as f:
            mounts = []
            for mount in f.read().splitlines():
                mount_line_data = mount.replace("\t", " ").split()
                if len(mount_line_data) > 2:
                    # line has a mountpoint
                    mounts.append(mount_line_data[1])

            if (len(mounts) > 0):
                try:
                    libioc.helpers.exec(["/sbin/umount"] + mounts)
                except libioc.errors.CommandFailure:
                    # in case directories were not mounted
                    pass

    def _create_nullfs_directories(self):
        basedirs = libioc.helpers.get_basedir_list(
            distribution_name=self.jail.host.distribution.name
        ) + ["dev", "etc"]

        for basedir in basedirs:
            self.create_jail_mountpoint(basedir)
