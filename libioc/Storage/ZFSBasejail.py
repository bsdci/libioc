# Copyright (c) 2017-2019, Stefan Grönke
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
"""ioc ZFS basejail storage backend."""
import typing

import libioc.Storage.Basejail
import libioc.helpers


class ZFSBasejailStorage(libioc.Storage.Basejail.BasejailStorage):
    """ioc ZFS basejail storage backend."""

    def apply(
        self,
        release: 'libioc.Release.ReleaseGenerator'=None,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Attach the jail storage."""
        if release is None:
            release = self.jail.cloned_release

        event = libioc.events.BaseJailStorageConfig(
            jail=self.jail,
        )
        yield event.begin()

        try:
            ZFSBasejailStorage.clone(self, release)
        except Exception as e:
            yield event.fail(e)
            raise

        yield event.end()

    def setup(
        self,
        release: 'libioc.Release.ReleaseGenerator'=None
    ) -> None:
        """Configure the jail storage."""
        libioc.Storage.Standalone.StandaloneJailStorage.setup(
            self,
            release
        )

    def clone(
        self,
        release: 'libioc.Release.ReleaseGenerator'
    ) -> None:
        """Clone ZFS basejail datasets from a release."""
        if isinstance(release, libioc.Release.ReleaseGenerator) is False:
            raise ValueError("ReleaseGenerator required")
        current_basejail_type = self.jail.config["basejail_type"]
        if not current_basejail_type == "zfs":
            raise libioc.errors.InvalidJailConfigValue(
                property_name="basejail_type",
                reason="Expected ZFS, but saw {current_basejail_type}",
                logger=self.logger
            )

        ZFSBasejailStorage._create_mountpoints(self)

        basedirs = libioc.helpers.get_basedir_list(
            distribution_name=self.jail.host.distribution.name
        )

        for basedir in basedirs:
            source_dataset = self.zfs.get_dataset(
                f"{release.base_dataset.name}/{basedir}"
            )
            target_dataset_name = f"{self.jail.root_dataset_name}/{basedir}"
            self.zfs.clone_dataset(
                source=source_dataset,
                target=target_dataset_name,
                delete_existing=True
            )

    def _create_mountpoints(self) -> None:
        for basedir in ["dev", "etc"]:
            self.create_jail_mountpoint(basedir)
