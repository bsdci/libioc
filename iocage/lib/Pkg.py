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
import math
import os.path
import re

import libzfs
import ucl

import iocage.lib.events
import iocage.lib.LaunchableResource


class Pkg:
    """iocage pkg management utility."""

    _dataset: libzfs.ZFSDataset
    package_source_directory: str = "/.iocage-pkg"

    def __init__(
        self,
        zfs: typing.Optional[iocage.lib.ZFS.ZFS]=None,
        host: typing.Optional['iocage.lib.Host.Host']=None,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None
    ) -> None:
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)
        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.host = iocage.lib.helpers.init_host(self, host)

    def fetch(
        self,
        packages: typing.Union[str, typing.List[str]],
        release: 'iocage.lib.Release.ReleaseGenerator',
        event_scope: typing.Optional['iocage.lib.events.Scope']=None
    ) -> typing.Generator[iocage.lib.events.IocageEvent, None, None]:
        """Fetch a bunch of packages to the local mirror."""
        _packages = self._normalize_packages(packages)
        _packages.append("pkg")
        release_major_version = math.floor(release.version_number)
        dataset = self._get_release_mirror_dataset(release_major_version)

        packageFetchEvent = iocage.lib.events.PackageFetch(
            packages=_packages,
            logger=self.logger,
            scope=event_scope
        )

        yield packageFetchEvent.begin()
        try:
            self.logger.spam("Configuring host pkg repositories")
            self._config_host_repo(release_major_version)
            self.logger.spam("Update from release pkg remote")
            self._update_host_repo(release_major_version)
            self.logger.spam("Mirroring packages")
            self._mirror_packages(_packages, dataset, release_major_version)
            self.logger.spam("Build mirror index")
            self._build_mirror_index(dataset)
        except iocage.lib.errors.IocageException as e:
            yield packageFetchEvent.fail(e)
            raise e
        yield packageFetchEvent.end()

    def _update_host_repo(self, release_major_version: int) -> None:
        iocage.lib.helpers.exec(
            [
                "/usr/sbin/pkg",
                "update",
                "--repository", self._get_repo_name(release_major_version)
            ],
            logger=self.logger,
            env=dict(
                SIGNATURE_TYPE="fingerprints"
            )
        )

    def _mirror_packages(
        self,
        packages: typing.List[str],
        dataset: libzfs.ZFSDataset,
        release_major_version: int
    ) -> None:
        iocage.lib.helpers.exec(
            [
                "/usr/sbin/pkg",
                "fetch",
                "--yes",
                "--dependencies",
                "--repository", self._get_repo_name(release_major_version),
                "--output", dataset.mountpoint,
            ] + packages,
            logger=self.logger,
            env=dict(
                SIGNATURE_TYPE="fingerprints"
            )
        )

    def _build_mirror_index(self, dataset: libzfs.ZFSDataset) -> None:
        iocage.lib.helpers.exec(
            [
                "/usr/sbin/pkg",
                "repo",
                dataset.mountpoint
            ],
            env=dict(
                SIGNATURE_TYPE="fingerprints",
                FINGERPRINTS="/usr/share/keys/pkg"
            ),
            logger=self.logger
        )

    def _get_base_url(self, release_major_version: int) -> str:
        """Return the distributions pkg base url for the major release."""
        if self.host.distribution.name == "HardenedBSD":
            return (
                "https://pkg.hardenedbsd.org/HardenedBSD/pkg/"
                f"FreeBSD:{release_major_version}:{self.host.processor}"
            )
        else:
            return (
                "https://pkg.freebsd.org/"
                f"FreeBSD:{release_major_version}:{self.host.processor}/"
                "latest"
            )

    def install(
        self,
        packages: typing.Union[str, typing.List[str]],
        jail: 'iocage.lib.Jail.JailGenerator',
        event_scope: typing.Optional['iocage.lib.events.Scope']=None,
        postinstall: typing.List[str]=[]
    ) -> typing.Generator[iocage.lib.events.IocageEvent, None, None]:
        """Install locally mirrored packages to a jail."""
        _packages = self._normalize_packages(packages)
        release_major_version = math.floor(jail.release.version_number)
        dataset = self._get_release_mirror_dataset(release_major_version)

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
            self._config_jail_repo(jail)
        except Exception as e:
            yield packageConfigurationEvent.fail(e)
            raise e
        yield packageConfigurationEvent.end()

        yield packageInstallEvent.begin()
        try:
            pkg_archive_name = self._get_latest_pkg_archive(dataset.mountpoint)
            command = "\n".join([
                "export ASSUME_ALWAYS_YES=yes",
                " ".join([
                    "/usr/sbin/pkg",
                    "add",
                    f"{self.package_source_directory}/All/{pkg_archive_name}"
                ]),
                " ".join([
                    "/usr/sbin/pkg",
                    "update",
                    "--force",
                    "--repository", "libiocage"
                ]),
                " ".join([
                    "/usr/sbin/pkg",
                    "install",
                    "--yes",
                    "--repository", "libiocage",
                    " ".join(packages)
                ])
            ] + postinstall)
            temporary_jail = self._get_temporary_jail(jail)
            jail_exec_events = temporary_jail.fork_exec(
                command,
                passthru=False,
                event_scope=packageInstallEvent.scope
            )
            skipped = False
            for event in jail_exec_events:
                if isinstance(event, iocage.lib.events.JailLaunch) is True:
                    if event.done is True:
                        stdout = event.stdout.strip("\r\n")
                        skipped = stdout.endswith("already installed")
                yield event
            if skipped is True:
                yield packageInstallEvent.skip()
            else:
                yield packageInstallEvent.end()
        except Exception as e:
            yield packageInstallEvent.fail(e)
            raise e

    def _get_latest_pkg_archive(self, package_source_directory: str) -> str:
        packages_directory = f"{package_source_directory}/All"
        for package_archive in os.listdir(packages_directory):
            if package_archive.endswith(".txz") is False:
                continue
            if package_archive.startswith("pkg"):
                return str(package_archive)
        raise iocage.lib.errors.PkgNotFound(logger=self.logger)

    def fetch_and_install(
        self,
        packages: typing.Union[str, typing.List[str]],
        jail: 'iocage.lib.Jail.JailGenerator',
        event_scope: typing.Optional['iocage.lib.events.Scope']=None,
        postinstall: typing.List[str]=[]
    ) -> typing.Generator[iocage.lib.events.IocageEvent, None, None]:
        """Mirror and install packages to a jail."""
        yield from self.fetch(
            packages=packages,
            release=jail.release,
            event_scope=event_scope
        )
        yield from self.install(
            packages=packages,
            jail=jail,
            event_scope=event_scope,
            postinstall=postinstall
        )

    def _normalize_packages(
        self,
        packages: typing.Union[str, typing.List[str]]
    ) -> typing.List[str]:
        _packages = [packages] if isinstance(packages, str) else packages
        pattern = re.compile("^(?:[A-z0-9](?:[A-z0-9\-\/]?[A-z0-9])*)+$")
        for package in _packages:
            if pattern.match(package) is None:
                raise iocage.lib.errors.SecurityViolation(
                    reason="Invalid package name",
                    logger=self.logger
                )
        return _packages

    def _get_repo_name(self, release_major_version: int) -> str:
        return f"iocage-release-{release_major_version}"

    def _config_jail_repo(self, jail: 'iocage.lib.Jail.JailGenerator') -> None:
        jail_directory = "/usr/local/etc/pkg/repos"
        host_directory = f"{jail.root_path}/{jail_directory}"
        self._update_repo_conf(
            repo_name="libiocage",
            url=f"file://{self.package_source_directory}",
            directory=host_directory,
            signature_type="none"
        )

    def _config_host_repo(
        self,
        release_major_version: int
    ) -> None:
        repo_name = self._get_repo_name(release_major_version)
        base_url = self._get_base_url(release_major_version)
        self._update_repo_conf(
            repo_name=repo_name,
            directory="/usr/local/etc/pkg/repos",
            enabled=True,
            url=f"pkg+{base_url}",
            mirror_type="srv",
            fingerprints="/usr/share/keys/pkg"
        )

    def _update_repo_conf(
        self,
        repo_name: str,
        directory: str,
        url: str,
        enabled: bool=True,
        signature_type: str="fingerprints",
        **repo_kwargs: typing.Union[str, bool]
    ) -> None:
        iocage.lib.helpers.makedirs_safe(
            directory,
            logger=self.logger
        )

        repo_config_data = {
            repo_name: dict(
                enabled=enabled,
                url=url,
                signature_type=signature_type,
                **repo_kwargs
            )
        }

        config_path = f"{directory}/{repo_name}.conf"
        if os.path.exists(config_path) and os.path.islink(config_path):
            raise iocage.lib.errors.SecurityViolation(
                reason="Refusing to write to a symlink",
                logger=self.logger
            )
        with open(config_path, "w") as f:
            f.write(ucl.dump(repo_config_data, ucl.UCL_EMIT_JSON))

    def _get_release_mirror_dataset(
        self,
        release_major_version: int
    ) -> libzfs.ZFSDataset:
        """Return the global package mirror dataset for the release."""
        dataset: libzfs.ZFSDataset = self.zfs.get_or_create_dataset(
            f"{self.host.datasets.main.pkg.name}/{release_major_version}"
        )
        return dataset

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
                "mount_devfs": True,
                "mount_fdescfs": False
            },
            new=True,
            fstab=source_jail.fstab,
            logger=self.logger,
            zfs=source_jail.zfs,
            host=source_jail.host,
            dataset=source_jail.dataset
        )

        root_path = temporary_jail.root_path
        destination_dir = f"{root_path}{self.package_source_directory}"

        release_major_version = math.floor(source_jail.release.version_number)
        dataset = self._get_release_mirror_dataset(release_major_version)
        try:
            temporary_jail.fstab.new_line(
                source=dataset.mountpoint,
                destination=destination_dir,
                options="ro",
                auto_create_destination=True,
                replace=True
            )
            temporary_jail.fstab.save()
        except iocage.lib.errors.FstabDestinationExists:
            pass

        return temporary_jail
