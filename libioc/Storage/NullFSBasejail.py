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
"""ioc NullFS basejail storage backend."""
import typing
import os.path

import libioc.Storage
import libioc.Storage.Basejail
import libioc.Storage.Standalone
import libioc.helpers

BasejailStorage = libioc.Storage.Basejail.BasejailStorage


class NullFSBasejailStorage(libioc.Storage.Basejail.BasejailStorage):
    """ioc NullFS basejail storage backend."""

    def apply(
        self,
        release: 'libioc.Release.ReleaseGenerator'=None,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Attach the jail storage."""
        event = libioc.events.BasejailStorageConfig(
            jail=self.jail,
            scope=event_scope
        )
        yield event.begin()

        try:
            NullFSBasejailStorage._create_nullfs_directories(self)
        except Exception:
            yield event.fail("NullFS directory creation failed")
            raise

        try:
            mounts = BasejailStorage._get_basejail_mounts(self)
            for source, destination in mounts:
                if os.path.ismount(destination) is True:
                    libioc.helpers.umount(destination)
                libioc.helpers.mount(
                    source=source,
                    destination=destination,
                    fstype="nullfs",
                    opts=["ro"]
                )
        except Exception:
            yield event.fail("Failed to mount NullFS basedirs")
            raise

        yield event.end()

    def teardown(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Unmount NullFS basejail mounts."""
        event = libioc.events.BasejailStorageConfig(
            jail=self.jail,
            scope=event_scope
        )
        yield event.begin()

        has_unmounted_any = False
        try:
            mounts = BasejailStorage._get_basejail_mounts(self)
            for _, destination in mounts:
                if os.path.ismount(destination) is False:
                    continue
                libioc.helpers.umount(destination, force=True)
                has_unmounted_any = True
        except Exception:
            yield event.fail("Failed to mount NullFS basedirs")
            raise

        if has_unmounted_any is False:
            yield event.skip()
        else:
            yield event.end()

        yield from libioc.Storage.Storage.teardown(
            self,
            event_scope=event_scope
        )

    def setup(
        self,
        release: 'libioc.Release.ReleaseGenerator'=None
    ) -> None:
        """Prepare the jail storage."""
        libioc.Storage.Standalone.StandaloneJailStorage.setup(
            self,
            release
        )

    def _create_nullfs_directories(self) -> None:
        basedirs = libioc.helpers.get_basedir_list(
            distribution_name=self.jail.host.distribution.name
        ) + ["dev", "etc"]

        for basedir in basedirs:
            self.create_jail_mountpoint(basedir)
