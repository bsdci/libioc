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
"""Shared code of various Basejail implementations (NullFS, ZFS)."""
import typing

import libioc.Types


class BasejailStorage(libioc.Storage.Storage):
    """Prototype class of Basejail Storage."""

    def _get_basejail_mounts(self) -> typing.Iterator[
        typing.Tuple[libioc.Types.AbsolutePath, libioc.Types.AbsolutePath]
    ]:
        """
        Auto-generate lines of NullFS basejails.

        When a jail is a NullFS basejail, this list represent the corresponding
        fstab lines that mount the release.

        Return a list of tuples (source, destination,).
        """
        try:
            self.jail.release
        except AttributeError:
            return []

        if self.jail.config["basejail_type"] != "nullfs":
            return []

        basedirs = libioc.helpers.get_basedir_list(
            distribution_name=self.jail.host.distribution.name
        )

        release_root_path = "/".join([
            self.jail.release.root_dataset.mountpoint,
            f".zfs/snapshot/{self.jail.release_snapshot.snapshot_name}"
        ])
        for basedir in basedirs:
            source = f"{release_root_path}/{basedir}"
            destination = f"{self.jail.root_dataset.mountpoint}/{basedir}"
            yield (source, destination,)
