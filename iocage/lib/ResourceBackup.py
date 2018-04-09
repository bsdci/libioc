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
"""iocage Resource extension that managed exporting and importing backups."""
import typing


class LaunchableResourceBackup:
    """Create and restore backups of a LaunchableResource."""

    def __init__(
        self,
        resource: 'iocage.lib.LaunchableResource.LaunchableResource'
    ) -> None:
        self.resource = resource

    def export(self, destination: str) -> None:
        """
        Export the resource.

        Jail exports contain the jails configuration and differing files
        between the jails root dataset and its release. Other datasets in the
        jails dataset are snapshotted and attached to the export entirely.

        Args:

            destination (str):

                The resource is exported to this location as archive file.
        """
        temp_dir = tempfile.TemporaryDirectory()
        temp_config = iocage.lib.Config.Type.JSON.ConfigJSON(
            file=f"{temp_dir.name}/config.json",
            logger=self.logger
        )
        temp_config.data = self.config.data
        temp_config.write(temp_config.data)
        self.logger.verbose(f"Duplicating jail config to {temp_config.file}")

        temp_root_dir = f"{temp_dir.name}/root"
        os.mkdir(temp_root_dir)

        self.logger.verbose(f"Writing jail delta to {temp_root_dir}")
        iocage.lib.helpers.exec([
            "rsync",
            "-rv",
            "--checksum",
            f"--compare-dest={self.release.root_dataset.mountpoint}/",
            f"{self.root_dataset.mountpoint}/",
            temp_root_dir
        ])
