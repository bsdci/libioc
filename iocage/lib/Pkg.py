# Copyright (c) 2014-2018, iocage
# Copyright (c) 2017-2018, Stefan Grönke
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
"""Pkg abstraction for Resources."""
import typing
import os.path
import re

import libzfs
import ucl

import iocage.lib.events
import iocage.lib.LaunchableResource


class Pkg:
    """iocage pkg management utility."""

    _dataset: libzfs.ZFSDataset
    package_source_directory: str = "/.iocage/pkg"

    def __init__(
        self,
        host: typing.Optional['iocage.lib.Host.Host']=None,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None
    ) -> None:
        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.host = iocage.lib.helpers.init_host(self, host)

    def fetch(
        self,
        packages: typing.Union[str, typing.List[str]],
        event_scope: typing.Optional['iocage.lib.events.Scope']=None
    ) -> typing.Generator[iocage.lib.events.IocageEvent, None, None]:
        """Fetch a bunch of packages to the local mirror."""

        _packages = self._normalize_packages(packages)

        packageFetchEvent = iocage.lib.events.PackageFetch(
            packages=_packages,
            logger=self.logger,
            scope=event_scope
        )

        yield packageFetchEvent.begin()
        try:
            iocage.lib.helpers.exec([
                "/usr/sbin/pkg",
                "fetch",
                "--yes",
                "--dependencies",
                "--output", self.dataset.mountpoint,
                " ".join(packages)
            ])
            yield packageFetchEvent.end()
        except Exception as e:
            yield packageFetchEvent.fail(e)
            raise e

    def install(
        self,
        packages: typing.Union[str, typing.List[str]],
        jail: 'iocage.lib.Jail.JailGenerator',
        event_scope: typing.Optional['iocage.lib.events.Scope']=None
    ) -> typing.Generator[iocage.lib.events.IocageEvent, None, None]:
        """Install locally mirrored packages to a jail."""

        _packages = self._normalize_packages(packages)

        packageInstallEvent = iocage.lib.events.PackageInstall(
            packages=_packages,
            jail=jail,
            logger=self.logger,
            scope=event_scope
        )

        packageConfigurationEvent = iocage.lib.events.PackageConfiguration(
            jail=jail,
            logger=self.logger,
            scope=event_scope
        )

        yield packageConfigurationEvent.begin()
        try:
            self._update_repo_conf(jail)
        except Exception as e:
            yield packageConfigurationEvent.fail(e)
            raise e
        yield packageConfigurationEvent.end()

        yield packageInstallEvent.begin()
        try:
            self._get_temporary_jail(jail).fork_exec(" ".join([
                "/usr/sbin/pkg",
                "install",
                "--yes",
                "--repository", "libiocage"
                " ".join(packages)
            ]))
        except Exception as e:
            yield packageInstallEvent.fail(e)
            raise e
        yield packageInstallEvent.end()

    def fetch_and_install(
        self,
        packages: typing.Union[str, typing.List[str]],
        jail: 'iocage.lib.Jail.JailGenerator',
        event_scope: typing.Optional['iocage.lib.events.Scope']=None
    ) -> typing.Generator[iocage.lib.events.IocageEvent, None, None]:
        """Mirror and install packages to a jail."""
        for event in self.fetch(packages, event_scope=event_scope):
            yield event
        for event in self.install(packages, jail, event_scope=event_scope):
            yield event

    def _normalize_packages(
        self,
        packages: typing.Union[str, typing.List[str]]
    ) -> typing.List[str]:
        _packages = [packages] if isinstance(packages, str) else packages
        pattern = re.compile("^(?:[A-z0-9](?:[A-z0-9\-]?[A-z0-9])*)+$")
        for package in _packages:
            if pattern.match(package) is None:
                raise iocage.lib.errors.SecurityViolation(
                    reason="Invalid package name",
                    logger=self.logger
                )
        return _packages

    def _update_repo_conf(self, jail: 'iocage.lib.Jail.JailGenerator') -> None:
        jail_directory = "/usr/local/etc/pkg/repos/"
        host_directory = f"{jail.root_path}/{jail_directory}"

        iocage.lib.helpers.makedirs_safe(
            host_directory,
            logger=self.logger
        )

        repo_config_data = {
            "libiocage": {
                "ENABLED": False,
                "URL": self.package_source_directory
            }
        }

        config_path = f"{host_directory}/libiocage.conf"
        if os.path.exists(config_path) and os.path.islink(config_path):
            raise iocage.lib.errors.SecurityViolation(
                reason="Refusing to write to a symlink",
                logger=self.logger
            )
        with open(config_path, "w") as f:
            f.write(ucl.dump(repo_config_data))

    @property
    def dataset(self):
        """Return the global package mirror dataset."""
        return self.host.datasets.main.pkg

    def _get_temporary_jail(
        self,
        source_jail: 'iocage.lib.Jail.JailGenerator'
    ) -> 'iocage.lib.Jail.JailGenerator':
        temporary_name = source_jail.name + "_pkg"
        temporary_jail = iocage.lib.Jail.JailGenerator(
            {
                "name": temporary_name,
                "basejail": source_jail.config["basejail"],
                "release": source_jail.release.name,
                "exec_start": None,
                "vnet": False,
                "ip4_addr": None,
                "ip6_addr": None,
                "defaultrouter": None,
                "mount_devfs": False,
                "mount_fdescfs": False
            },
            new=True,
            logger=self.logger,
            zfs=source_jail.zfs,
            host=source_jail.host,
            dataset=source_jail.dataset
        )

        root_path = temporary_jail.root_path
        destination_dir = f"{root_path}{self.package_source_directory}"
        temporary_jail.fstab.file = "fstab_pkg"
        temporary_jail.fstab.new_line(
            source=self.dataset.mountpoint,
            destination=destination_dir,
            options="ro"
        )
        if os.path.isdir(destination_dir) is False:
            iocage.lib.helpers.makedirs_safe(
                destination_dir,
                mode=0o755,
                logger=self.logger
            )
        temporary_jail.fstab.save()

        return temporary_jail
