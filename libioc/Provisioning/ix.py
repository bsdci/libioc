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
"""ioc provisioner for ix-plugins."""
import typing
import os.path
import json
import urllib.error
import urllib.request
import libzfs

import git

import libioc.errors
import libioc.events
import libioc.Pkg
import libioc.Provisioning


class PluginUnavailableError(libioc.errors.IocException):
    """Raised when an iX iocage plugin is not available."""

    def __init__(
        self,
        name: str,
        reason: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"iX iocage plugin '{name}' is not available: {reason}"
        libioc.errors.IocException.__init__(
            self,
            message=msg,
            logger=logger
        )


class PluginDefinition(dict):
    """ix-iocage-plugin definition."""

    _name: str

    def __init__(
        self,
        name: str,
        logger: 'libioc.Logger.Logger'
    ) -> None:
        self.logger = logger
        self._set_name(name)

    @property
    def name(self) -> str:
        """Return the ix-iocage-plugins name."""
        return str(self._name)

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
        """Return the remote URL of the ix-iocage-plugins definition file."""
        return self.__get_url(self.name)

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
            raise PluginUnavailableError(
                name=name,
                reason=str(e),
                logger=self.logger
            )
        charset = resource.headers.get_content_charset()  # noqa: T484
        response = resource.read().decode(charset if charset else "UTF-8")
        data: typing.Dict[str, typing.Any] = json.loads(response)
        return data


def provision(
    self: 'libioc.Provisioning.Prototype',
    event_scope: typing.Optional['libioc.events.Scope']=None
) -> typing.Generator['libioc.events.IocEvent', None, None]:
    """
    Provision the jail from an ix-iocage-plugin.

    Installable ix-iocage plugins can be found on the registry repository
    https://github.com/freenas/iocage-ix-plugins/ and may be configured
    as a jails provision.source property, e.g.:

        ioc set provision.method=ix provision.source=jenkins myjail
    """
    events = libioc.events
    jailProvisioningEvent = events.JailProvisioning(
        jail=self.jail,
        scope=event_scope
    )
    yield jailProvisioningEvent.begin()
    _scope = jailProvisioningEvent.scope
    jailProvisioningAssetDownloadEvent = events.JailProvisioningAssetDownload(
        jail=self.jail,
        scope=_scope
    )

    # download provisioning assets
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

    # clone plugin
    plugin_dataset_name = f"{self.jail.dataset.name}/ix-plugin"
    plugin_dataset = __get_empty_dataset(plugin_dataset_name, self.jail.zfs)
    git.Repo.clone_from(
        pluginDefinition["artifact"],
        plugin_dataset.mountpoint
    )

    self.jail.fstab.new_line(
        source=plugin_dataset.mountpoint,
        destination="/.ix-plugin",
        options="ro",
        auto_create_destination=True,
        replace=True
    )
    self.jail.fstab.save()

    if "pkgs" in pluginDefinition.keys():
        pkg_packages = list(pluginDefinition["pkgs"])
    else:
        pkg_packages = [pluginDefinition.name]

    try:
        pkg = libioc.Pkg.Pkg(
            logger=self.jail.logger,
            zfs=self.jail.zfs,
            host=self.jail.host
        )

        if os.path.isfile(f"{plugin_dataset.mountpoint}/post_install.sh"):
            postinstall = ["/.ix-plugin/post_install.sh"]
        else:
            postinstall = []

        yield from pkg.fetch_and_install(
            jail=self.jail,
            packages=pkg_packages,
            postinstall=postinstall
        )
    except Exception as e:
        yield jailProvisioningEvent.fail(e)
        raise e


def __get_empty_dataset(
    dataset_name: str,
    zfs: 'libioc.ZFS.ZFS'
) -> libzfs.ZFSDataset:
    try:
        dataset = zfs.get_dataset(dataset_name)
    except libzfs.ZFSException:
        dataset = None
        pass
    if dataset is not None:
        dataset.umount()
        zfs.delete_dataset_recursive(dataset)

    output: libzfs.ZFSDataset = zfs.get_or_create_dataset(dataset_name)
    return output
