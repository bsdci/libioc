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
import iocage.lib.StandaloneJailStorage
import iocage.lib.helpers


class NullFSBasejailStorage:
    """
    Iocage NullFS storage backend

    This backend is used by NullFS basejails.
    """

    def apply(self, release=None):
        NullFSBasejailStorage._create_nullfs_directories(self)

    def setup(self, release):
        iocage.lib.StandaloneJailStorage.StandaloneJailStorage.setup(
            self, release)

    def umount_nullfs(self):
        """
        Unmount all NullFS mounts from fstab

        In preparation of starting the jail with NullFS mounts all mountpoints
        that are listed in fstab need to be unmounted
        """
        with open(f"{self.jail.path}/fstab") as f:
            mounts = []
            for mount in f.read().splitlines():
                try:
                    mounts.append(mount.replace("\t", " ").split(" ")[1])
                except:
                    pass

            if (len(mounts) > 0):
                try:
                    iocage.lib.helpers.exec(["umount"] + mounts)
                except:
                    # in case directories were not mounted
                    pass

    def _create_nullfs_directories(self):
        basedirs = iocage.lib.helpers.get_basedir_list(
            distribution_name=self.jail.host.distribution.name
        ) + ["dev", "etc"]

        for basedir in basedirs:
            self.create_jail_mountpoint(basedir)
