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

import libioc.errors
import libioc.events
import libioc.Pkg
import libioc.Provisioning

__puppet_env_dir = "/usr/local/etc/puppet/environments"


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
            self._pkgs += ['rubygem-r10k', 'git-lite']

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
    If the repo is a filesystem path, it will be mounted to
    `/usr/local/etc/puppet/environments`.
    If the repo is a URL, we will setup a ZFS dataset and mount that to
    `/usr/local/etc/puppet/environments`, before deploying it with `r10k`.

    Example:

        ioc set \
            provision.method=puppet \
            provision.source=http://github.com/bsdci/puppet-control-repo \
            webserver

    This should install a webserver that listens on port 80, and delivers a
    Hello-World HTML site.
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
                property_name="provision.source",
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
        plugin_dataset = self.jail.zfs.get_or_create_dataset(
            plugin_dataset_name
        )

        mount_source = plugin_dataset.mountpoint
    else:
        mode = 'ro'
        mount_source = self.source

    if self.jail.stopped is True:
        started = True
        yield from self.jail.start(event_scope=_scope)
    else:
        started = False

    # Install packages
    pkg = libioc.Pkg.Pkg(
        logger=self.jail.logger,
        zfs=self.jail.zfs,
        host=self.jail.host
    )
    yield from pkg.fetch(
        packages=list(pluginDefinition.pkgs),
        release=self.jail.release,
        event_scope=_scope
    )
    yield from pkg.fetch_and_install(
        jail=self.jail,
        packages=list(pluginDefinition.pkgs),
        event_scope=_scope
    )

    self.jail.logger.spam("Mounting puppet environment")
    fstab_line = self.jail.fstab.new_line(
        source=mount_source,
        destination=__puppet_env_dir,
        options=mode,
        auto_create_destination=True,
        replace=True
    )

    try:
        if self.source.remote is True:
            yield from __deploy_r10k(self, event_scope=_scope)
        yield from __apply_puppet(self, event_scope=_scope)
        if started is True:
            yield from self.jail.stop(event_scope=_scope)
    finally:
        del self.jail.fstab[self.jail.fstab.index(fstab_line)]

    yield jailProvisioningEvent.end()


def __apply_puppet(
    self: 'libioc.Provisioning.Prototype',
    event_scope: libioc.events.Scope
) -> typing.Generator[R10kDeployEvent, None, None]:
    puppetApplyEvent = PuppetApplyEvent(
        scope=event_scope,
        jail=self.jail
    )
    yield puppetApplyEvent.begin()
    _, _, returncode = self.jail.exec([
        "puppet",
        "apply",
        "--debug",
        "--logdest",
        "syslog",
        f"{__puppet_env_dir}/production/manifests/site.pp"
    ])
    if returncode == 0:
        yield puppetApplyEvent.end()
    else:
        yield puppetApplyEvent.fail(f"exited with {returncode}")


def __deploy_r10k(
    self: 'libioc.Provisioning.Prototype',
    event_scope: libioc.events.Scope
) -> typing.Generator[R10kDeployEvent, None, None]:
    r10kDeployEvent = R10kDeployEvent(
        scope=event_scope,
        jail=self.jail
    )
    yield r10kDeployEvent.begin()
    try:
        __write_r10k_config(self.jail, __puppet_env_dir, self.source)
        __deploy_r10k_config(self.jail)
    except Exception as e:
        yield r10kDeployEvent.fail(e)
        raise e
    yield r10kDeployEvent.end()


def __deploy_r10k_config(jail: libioc.Jail.JailGenerator) -> None:
    jail.logger.verbose("Deploying r10k config")
    jail.exec([
        "r10k",
        "deploy",
        "environment",
        "-pv"
    ])


def __write_r10k_config(
    jail: libioc.Jail.JailGenerator,
    basedir: str,
    remote: str
) -> None:
    with __securely_open_r10k_config(jail) as f:
        jail.logger.verbose(f"Writing r10k config {f.name}")
        f.write("\n".join((
            f"---",
            ":sources:",
            "    puppet:",
            f"       basedir: {basedir}",
            f"       remote: {remote}\n"
        )))


def __securely_open_r10k_config(
    jail: libioc.Jail.JailGenerator
) -> typing.TextIO:
    etc_dir = f"{jail.root_path}/usr/local/etc"
    jail.require_relative_path(etc_dir)
    r10k_config_dir = f"{etc_dir}/r10k"
    if not os.path.isdir(f"{r10k_config_dir}"):
        os.makedirs(r10k_config_dir, mode=0o755)
    else:
        jail.require_relative_path(r10k_config_dir)
    r10k_config_file = f"{r10k_config_dir}/r10k.yaml"
    if os.path.exists(r10k_config_file) is True:
        jail.require_relative_path(r10k_config_file)
    return open(r10k_config_file, "w", encoding="UTF-8")
