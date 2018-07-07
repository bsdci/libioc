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
"""iocage provisioner for ix-plugins."""
import typing
import json
import urllib.error
import urllib.request

import iocage.lib.errors
import iocage.lib.events
import iocage.lib.Provisioning


class PluginDefinition(dict):

    _name: str

    def __init__(
        self,
        name: str,
        logger: 'iocage.lib.Logger.Logger'
    ) -> None:
        self.logger = logger
        self._set_name(name)

    @property
    def name(self) -> str:
        """Return the ix-iocage-plugins name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set the ix-iocage-plugins name."""
        self._set_name(value)

    def _set_name(self, value: str) -> None:
        data = self.__download_definition_data(value)
        self._name = value
        dict.clear(self)
        dict.__init__(self, data)

    @property
    def url(self) -> str:
        return self.get_url(self.name)

    def __get_url(self, name: str) -> str:
        return (
            "https://raw.githubusercontent.com/freenas/iocage-ix-plugins"
            f"/master/{name}.json"
        )

    def __download_definition_data(
        self,
        name: str
    ) -> typing.Dict[str, typing.Any]:
        try:
            resource = urllib.request.urlopen(self.__get_url(name))  # nosec
        except urllib.error.HTTPError as e:
            raise iocage.lib.errors.ProvisioningSourceUnavailable(
                name=name,
                logger=self.logger
            )
        charset = resource.headers.get_content_charset()  # noqa: T484
        response = resource.read().decode(charset if charset else "UTF-8")
        data: typing.Dict[str, typing.Any] = json.loads(response)
        return data


def provision(
    self: 'iocage.lib.Provisioning.Prototype',
    event_scope: typing.Optional['iocage.lib.events.Scope']=None
) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
    """
    Provision the jail from an ix-iocage-plugin.

    Installable ix-iocage plugins can be found on the registry repository
    https://github.com/freenas/iocage-ix-plugins/ and may be configured
    as a jails provisioning.source property, e.g.:

        ioc set provisioning.method=ix provisioning.source=jenkins myjail
    """
    events = iocage.lib.events
    jailProvisioningEvent = events.JailProvisioning(
        jail=self.jail,
        event_scope=event_scope
    )
    _scope = jailProvisioningEvent.scope
    jailProvisioningAssetDownloadEvent = events.JailProvisioningAssetDownload(
        jail=self.jail,
        event_scope=_scope
    )

    yield jailProvisioningEvent.begin()

    try:
        yield jailProvisioningAssetDownloadEvent.begin()
        pluginDefinition = PluginDefinition(
            self.source,
            logger=self.jail.logger
        )
        yield jailProvisioningAssetDownloadEvent.end()
    except Exception as e:
        yield jailProvisioningAssetDownloadEvent.fail(e)
        raise e

    for event in self.jail.fork_exec("whoami"):
        yield event

    yield jailProvisioningEvent.end()

