# Copyright (c) 2017-2019, Stefan Grönke, Igor Galić
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
"""iocage provisioner for use with `puppet apply`."""
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


class ControlRepoUnavailableError(libioc.errors.IocException):
    """Raised when the puppet control-repo is not available."""

    def __init__(
        self,
        url: str,
        reason: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Puppet control-repo '{url}' is not available: {reason}"
        libioc.errors.IocException.__init__(
            self,
            message=msg,
            logger=logger
        )


class ControlRepoDefinition(dict):
    """Puppet control-repo definition."""

    _url: str
    _name: str
    _pkgs: typing.List[str]

    def __init__(
        self,
        name: str,
        url: str,
        logger: 'libioc.Logger.Logger'
    ) -> None:
        self.logger = logger
        self.url = url
        self.name = name

        _pkgs = ['puppet6']  # make this a Global Varialbe
        if not (url.startswith('file://') or url.startswith('/')):
            _pkgs += 'rubygem-r10k'

    @property
    def url(self) -> str:
        """Return the Puppet Control-Repo URL."""
        return str(self._url)

    @property.setter
    def url(self) -> str:
        """Set the Puppet Control-Repo URL."""
        return str(self._url)

    @property
    def name(self, value: str) -> str:
        """Return the unique name for this Puppet Control-Repo URL."""
        return self._name

    @property.setter
    def name(self, value: str) -> None:
        """Set a unique name for this Puppet Control-Repo URL."""
        self._name = value

    @property
    def pkgs(self, value: str) -> typing.List[str]:
        """Return list of packages required for this Provisioning method."""
        return self._pkgs

    #@property.setter
    #def pkgs(self, value: str) -> None:
    #    """Set (list) of additional packagess required for this Puppet Control-Repo URL."""
    #    self._pkgs += value


def provision(
    self: 'libioc.Provisioning.Prototype',
    event_scope: typing.Optional['libioc.events.Scope']=None
) -> typing.Generator['libioc.events.IocEvent', None, None]:
    """
    Provision the jail with Puppet apply using the supplied control-repo.

    The repo can either be a filesystem path, or a http[s]/git URL.
    If the repo is a filesystem path, it will be mounted appropriately.
    If the repo is a URL, it will be setup with `r10k`.

        ioc set provisioning.method=puppet provisioning.source=http://example.com/my/puppet-env myjail

    """
    events = libioc.events
    jailProvisioningEvent = events.JailProvisioning(
        jail=self.jail,
        event_scope=event_scope
    )
    yield jailProvisioningEvent.begin()
    _scope = jailProvisioningEvent.scope
    jailProvisioningAssetDownloadEvent = events.JailProvisioningAssetDownload(
        jail=self.jail,
        event_scope=_scope
    )

    # download / mount provisioning assets
    try:
        yield jailProvisioningAssetDownloadEvent.begin()
        pluginDefinition = ControlRepoDefinition(
            self.source,
            logger=self.jail.logger
        )
        yield jailProvisioningAssetDownloadEvent.end()
    except Exception as e:
        yield jailProvisioningAssetDownloadEvent.fail(e)
        raise e

    if not (self.source.startswith('file://') or self.source.startswith('/')):
        # clone control repo
        controlrepo_dataset_name = f"{self.jail.dataset.name}/puppet"
        controlrepo_dataset = __get_empty_dataset(
            control_repo_dataset_name, self.jail.zfs)

        git.Repo.clone_from(
            ControlRepoDefinition["url"],
            plugin_dataset.mountpoint
        )

    self.jail.fstab.new_line(
        source=plugin_dataset.mountpoint,
        destination="/.puppet",
        options="ro",
        auto_create_destination=True,
        replace=True
    )
    self.jail.fstab.save()

    if "pkgs" in controlRepoDefinition.keys():
        pkg_packages = list(controlRepoDefinition["pkgs"])
    else:
        pkg_packages = []

    try:
        pkg = libioc.Pkg.Pkg(
            logger=self.jail.logger,
            zfs=self.jail.zfs,
            host=self.jail.host
        )

        if os.path.isfile(f"{plugin_dataset.mountpoint}/post_install.sh"):
            postinstall = ["/.puppet/post_install.sh"]
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
