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
import os.path

import iocage.lib.LaunchableResource


class ResourceConfigFile:

    def _require_path_relative_to_resource(
        self,
        filepath: str,
        resource: 'iocage.lib.LaunchableResource.LaunchableResource'
    ) -> None:

        if self._is_path_relative_to_resource(filepath, resource) is False:
            raise iocage.lib.errors.SecurityViolationConfigJailEscape(
                file=filepath
            )

    def _is_path_relative_to_resource(
        self,
        filepath: str,
        resource: 'iocage.lib.LaunchableResource.LaunchableResource'
    ) -> bool:

        real_resource_path = self._resolve_path(resource.dataset.mountpoint)
        real_file_path = self._resolve_path(filepath)

        return real_file_path.startswith(real_resource_path)

    def _resolve_path(self, filepath: str) -> str:
        return os.path.realpath(os.path.abspath(filepath))
