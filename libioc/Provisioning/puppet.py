# Copyright (c) 2017-2019, Stefan Grönke, Igor Galić
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
"""ioc provisioner for use with `puppet apply`."""
import typing
import os.path

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


class R10kDeployEvent(libioc.events.JailEvent):
    """Deploy control repo and install puppet modules."""

    pass


class PuppetApplyEvent(libioc.events.JailEvent):
    """Apply the puppet manifest."""

    pass


class ControlRepoDefinition(dict):
    """Puppet control-repo definition."""

    __source: str
    _pkgs: typing.List[str]

    def __init__(
        self,
        source: 'libioc.Provisioning.Source',
        logger: 'libioc.Logger.Logger'
    ) -> None:
        self.logger = logger

        self.source = source
        self._pkgs = ['puppet6']  # make this a Global Varialbe
        if source.remote is True:
            self._pkgs += 'rubygem-r10k'

    @property
    def source(
        self
    ) -> 'libioc.Provisioning.Source':
        """Return the Puppet Control-Repo URL."""
        return self.__source

    @source.setter
    def source(self, source: 'libioc.Provisioning.Source') -> None:
        """Set the Puppet Control-Repo URL."""
        if isinstance(source, libioc.Provisioning.Source) is False:
            raise TypeError("Source must be libioc.Provisioning.Source")
        self.__source = source

    @property
    def pkgs(self) -> typing.List[str]:
        """Return list of packages required for this Provisioning method."""
        return self._pkgs


def provision(
    self: 'libioc.Provisioning.Prototype',
    event_scope: typing.Optional['libioc.events.Scope']=None
) -> typing.Generator['libioc.events.IocEvent', None, None]:
    r"""
    Provision the jail with Puppet apply using the supplied control-repo.

    The repo can either be a filesystem path, or a http[s]/git URL.
    If the repo is a filesystem path, it will be mounted appropriately.
    If the repo is a URL, it will be setup with `r10k`.

        ioc set \
            provisioning.method=puppet \
            provisioning.source=http://example.com/my/puppet-env \
            myjail

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

    # download / mount provisioning assets
    try:
        yield jailProvisioningAssetDownloadEvent.begin()
        if self.source is None:
            raise libioc.errors.InvalidJailConfigValue(
                property_name="provisioning.source",
                reason="Source may not be empty",
                logger=self.jail.logger
            )
        pluginDefinition = ControlRepoDefinition(
            source=self.source,
            logger=self.jail.logger
        )
        yield jailProvisioningAssetDownloadEvent.end()
    except Exception as e:
        yield jailProvisioningAssetDownloadEvent.fail(e)
        raise e

    if self.source.remote:
        mode = 'rw'  # we'll need to run r10k here..
        plugin_dataset_name = f"{self.jail.dataset.name}/puppet"
        plugin_dataset = self.zfs.get_or_create_dataset(
            plugin_dataset_name
        )

        if not os.path.isdir(plugin_dataset_name):
            # only clone if it doesn't already exist
            git.Repo.clone_from(
                pluginDefinition.source,
                plugin_dataset.mountpoint
            )

        mount_source = plugin_dataset.mountpoint
    else:
        mode = 'ro'
        mount_source = self.source

    if self.jail.stopped is True:
        started = True
        jailStartEvent = libioc.events.JailStart(
            jail=self.jail,
            scope=jailProvisioningEvent.scope
        )
        yield jailStartEvent.begin()
        yield from self.jail.start(event_scope=jailStartEvent.scope)
        yield jailStartEvent.end()
    else:
        started = False

    pkg = libioc.Pkg.Pkg(
        logger=self.jail.logger,
        zfs=self.jail.zfs,
        host=self.jail.host
    )

    yield from pkg.install(
        jail=self.jail,
        packages=list(pluginDefinition.pkgs),
        event_scope=jailProvisioningEvent.scope
    )

    puppet_env_dir = "/usr/local/etc/puppet/environments"

    self.jail.logger.spam("Mounting puppet environment")
    self.jail.fstab.new_line(
        source=mount_source,
        destination=puppet_env_dir,
        options=mode,
        auto_create_destination=True,
        replace=True
    )

    try:
        if self.source.remote is True:

            r10kDeployEvent = R10kDeployEvent(
                scope=jailProvisioningEvent.scope,
                jail=self.jail
            )

            yield r10kDeployEvent.begin()
            try:
                r10k_cfg = f"{self.jail.root_path}/usr/local/etc/r10k/r10k.yml"
                self.jail.logger.verbose(f"Writing r10k config {r10k_cfg}")
                with open(r10k_cfg, "w") as f:
                    f.write(f"""---
                    :source:
                        puppet:
                            basedir: {puppet_env_dir}
                            remote: {self.source}
                    """)

                self.jail.logger.verbose("Deploying r10k config")
                self.jail.exec([
                    "r10k",
                    "deploy",
                    "environment",
                    "-pv"
                ])
            except Exception as e:
                yield r10kDeployEvent.fail(e)
                raise e
            yield r10kDeployEvent.end()

        puppetApplyEvent = PuppetApplyEvent(
            scope=jailProvisioningEvent.scope,
            jail=self.jail
        )
        yield puppetApplyEvent.begin()
        try:
            self.jail.exec([
                "puppet",
                "apply",
                "--debug",
                "--logdest",
                "syslog",
                f"{puppet_env_dir}/production/manifests/site.pp"
            ])
            yield puppetApplyEvent.end()
        except Exception as e:
            yield puppetApplyEvent.fail(e)
            raise e

        if started is True:
            jailStopEvent = libioc.events.JailShutdown(
                jail=self.jail,
                scope=jailProvisioningEvent.scope
            )
            yield jailStopEvent.begin()
            yield from self.jail.stop(event_scope=jailStopEvent.scope)
            yield jailStopEvent.end()
    finally:
        # in case anything fails the fstab mount needs to be removed
        del self.jail.fstab[-1]

    yield jailProvisioningEvent.end()
