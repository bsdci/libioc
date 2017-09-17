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
import iocage.lib.errors
import iocage.lib.helpers


class Prompts:
    def __init__(self, host=None, logger=None):
        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.host = iocage.lib.helpers.init_host(self, host)

    def release(self):
        default = None
        available_releases = self.host.distribution.releases
        for i, available_release in enumerate(available_releases):
            if available_release.name == self.host.release_version:
                default = i
                print(
                    f"[{i}] \033[1m{available_release.annotated_name}\033[0m"
                )
            else:
                print(f"[{i}] {available_release.annotated_name}")

        if default is not None:
            default_release = available_releases[default]
            selection = input(
                # f"Release ({default_release.name}) [{default}]: "
                "\nType the number of the desired RELEASE\n"
                "Press [Enter] to fetch the default selection"
                f" ({default_release.name}) [{default}]: "
            )
        else:
            default_release = None
            selection = input("Your selection: ")

        if selection == "":
            if default_release is None:
                raise iocage.lib.errors.DefaultReleaseNotFound(
                    host_release_name=self.host.release_version,
                    logger=self.logger
                )
            return default_release
        else:
            return available_releases[int(selection)]
