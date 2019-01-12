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
"""Pkg abstraction for Resources."""
import typing
import math
import os.path
import re

import libzfs

import libioc.events
import libioc.helpers
import libioc.helpers_object
import libioc.LaunchableResource
import libioc.Config.Jail.File.Fstab

_PkgConfDataType = typing.Union[
    str, int, bool,
    typing.List[typing.Union[str, int, bool]],
    typing.Dict[str, typing.Union[str, int, bool]]
]


class Pkg:
    """iocage pkg management utility."""

    _dataset: libzfs.ZFSDataset
    package_source_directory: str = "/.iocage-pkg"
    __pkg_directory_mounted: bool

    def __init__(
        self,
        zfs: typing.Optional[libioc.ZFS.ZFS]=None,
        host: typing.Optional['libioc.Host.Host']=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)
        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.host = libioc.helpers_object.init_host(self, host)
        self.__pkg_directory_mounted = False

    def fetch(
        self,
        packages: typing.Union[str, typing.List[str]],
        release: 'libioc.Release.ReleaseGenerator',
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator[libioc.events.IocEvent, None, None]:
        """Fetch a bunch of packages to the local mirror."""
        _packages = self._normalize_packages(packages)
        _packages.append("pkg")
        release_major_version = math.floor(release.version_number)
        pkg_ds = self._get_release_pkg_dataset(release_major_version)

        packageFetchEvent = libioc.events.PackageFetch(
            packages=_packages,
            scope=event_scope
        )

        yield packageFetchEvent.begin()
        try:
            self.logger.spam("Configuring host pkg repositories")
            self._config_host_repo(release_major_version)
            self.logger.spam("Update from release pkg remote")
            self._update_host_repo(release_major_version)
            self.logger.spam("Mirroring packages")
            self._mirror_packages(_packages, pkg_ds, release_major_version)
            self.logger.spam("Build mirror index")
            self._build_mirror_index(release_major_version)
        except libioc.errors.IocException as e:
            yield packageFetchEvent.fail(e)
            raise e
        yield packageFetchEvent.end()

    def _get_pkg_command(self, release_major_version: int) -> typing.List[str]:
        pkg_ds = self._get_release_pkg_dataset(release_major_version)
        conf_ds = self.zfs.get_or_create_dataset(f"{pkg_ds.name}/conf")
        repos_ds = self.zfs.get_or_create_dataset(f"{pkg_ds.name}/repos")
        return [
            "/usr/sbin/pkg",
            "--config",
            f"{conf_ds.mountpoint}/pkg.conf",
            "--repo-conf-dir",
            repos_ds.mountpoint
        ]

    def _update_host_repo(self, release_major_version: int) -> None:
        libioc.helpers.exec(
            self._get_pkg_command(release_major_version) + [
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
        stdout, stderr, returncode = libioc.helpers.exec(
            self._get_pkg_command(release_major_version) + [
                "fetch",
                "--yes",
                "--dependencies",
                "--repository", self._get_repo_name(release_major_version)
            ] + packages,
            logger=self.logger,
            env=dict(
                SIGNATURE_TYPE="fingerprints"
            )
        )

        if (stderr is not None) and (len(stderr) > 0):
            raise libioc.errors.PkgNotFound(stderr, logger=self.logger)

    def _build_mirror_index(self, release_major_version: int) -> None:
        pkg_ds = self._get_release_pkg_dataset(release_major_version)
        cache_ds = self.zfs.get_or_create_dataset(f"{pkg_ds.name}/cache")

        libioc.helpers.exec(
            self._get_pkg_command(release_major_version) + [
                "repo",
                cache_ds.mountpoint
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
        jail: 'libioc.Jail.JailGenerator',
        event_scope: typing.Optional['libioc.events.Scope']=None,
        postinstall: typing.List[str]=[]
    ) -> typing.Generator[libioc.events.IocEvent, None, None]:
        """Install locally mirrored packages to a jail."""
        _packages = self._normalize_packages(packages)
        release_major_version = math.floor(jail.release.version_number)
        dataset = self._get_release_pkg_dataset(release_major_version)

        packageInstallEvent = libioc.events.PackageInstall(
            packages=_packages,
            jail=jail,
            scope=event_scope
        )

        packageConfigurationEvent = libioc.events.PackageConfiguration(
            jail=jail,
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
                    f"{self.package_source_directory}/{pkg_archive_name}"
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
                    " ".join(_packages)
                ])
            ] + postinstall)

            if jail.running is True:
                self.__mount_pkg_directory(jail)
                stdout, stderr, code = jail.exec(["/bin/sh", "-c", command])
                stdout = stdout.strip("\r\n")
            else:
                temporary_jail = self._get_temporary_jail(jail)
                jail_exec_events = temporary_jail.fork_exec(
                    command,
                    passthru=False,
                    event_scope=packageInstallEvent.scope
                )
                for event in jail_exec_events:
                    if isinstance(event, libioc.events.JailLaunch) is True:
                        if event.done is True:
                            stdout = event.stdout.strip("\r\n")
                    yield event
            skipped = stdout.endswith("already installed")
            if skipped is True:
                yield packageInstallEvent.skip()
            else:
                yield packageInstallEvent.end()
        except Exception as e:
            yield packageInstallEvent.fail(e)
            raise e

    def remove(
        self,
        packages: typing.Union[str, typing.List[str]],
        jail: 'libioc.Jail.JailGenerator',
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator[libioc.events.IocEvent, None, None]:
        """Remove installed packages from a jail."""
        _packages = self._normalize_packages(packages)

        packageRemoveEvent = libioc.events.PackageRemove(
            packages=_packages,
            jail=jail,
            scope=event_scope
        )
        command = [
            "/usr/sbin/pkg",
            "remove",
            "--yes",
            " ".join(_packages)
        ]
        yield packageRemoveEvent.begin()
        try:
            if jail.running is False:
                temporary_jail = self._get_temporary_jail(jail)
                _command = "\n".join([
                    "export ASSUME_ALWAYS_YES=yes",
                    " ".join(command)
                ])
                yield from temporary_jail.fork_exec(
                    _command,
                    passthru=False,
                    event_scope=packageRemoveEvent.scope
                )
            else:
                jail.exec(command)
        except Exception as err:
            yield packageRemoveEvent.fail(err)
            raise err
        yield packageRemoveEvent.end()

    def _get_latest_pkg_archive(self, package_source_directory: str) -> str:
        for package_archive in os.listdir(f"{package_source_directory}/cache"):
            if package_archive.endswith(".txz") is False:
                continue
            if package_archive.startswith("pkg"):
                return str(package_archive)
        raise libioc.errors.PkgNotFound(logger=self.logger)

    def fetch_and_install(
        self,
        packages: typing.Union[str, typing.List[str]],
        jail: 'libioc.Jail.JailGenerator',
        event_scope: typing.Optional['libioc.events.Scope']=None,
        postinstall: typing.List[str]=[]
    ) -> typing.Generator[libioc.events.IocEvent, None, None]:
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
        pattern = re.compile(r"^(?:[A-z0-9](?:[A-z0-9\-\/]?[A-z0-9])*)+$")
        for package in _packages:
            if pattern.match(package) is None:
                raise libioc.errors.SecurityViolation(
                    reason="Invalid package name",
                    logger=self.logger
                )
        return _packages

    def _get_repo_name(self, release_major_version: int) -> str:
        return f"iocage-release-{release_major_version}"

    def _config_jail_repo(self, jail: 'libioc.Jail.JailGenerator') -> None:
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

        pkg_ds = self._get_release_pkg_dataset(release_major_version)
        db_ds = self.zfs.get_or_create_dataset(f"{pkg_ds.name}/db")
        conf_ds = self.zfs.get_or_create_dataset(f"{pkg_ds.name}/conf")
        cache_ds = self.zfs.get_or_create_dataset(f"{pkg_ds.name}/cache")
        repos_ds = self.zfs.get_or_create_dataset(f"{pkg_ds.name}/repos")

        self._update_pkg_conf(
            filename=f"{conf_ds.mountpoint}/pkg.conf",
            data=dict(
                PKG_DBDIR=db_ds.mountpoint,
                PKG_CACHEDIR=cache_ds.mountpoint,
                REPOS_DIR=[str(repos_ds.mountpoint)],
                SYSLOG=False
            )
        )

        self._update_repo_conf(
            repo_name=repo_name,
            directory=repos_ds.mountpoint,
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
        libioc.helpers.makedirs_safe(
            directory,
            logger=self.logger
        )

        repo_config_data: typing.Dict[str, _PkgConfDataType] = {
            repo_name: dict(
                enabled=enabled,
                url=url,
                signature_type=signature_type,
                **repo_kwargs
            )
        }

        config_path = f"{directory}/{repo_name}.conf"
        self._update_pkg_conf(
            filename=config_path,
            data=repo_config_data
        )

    def _update_pkg_conf(
        self,
        filename: str,
        data: typing.Dict[str, _PkgConfDataType]
    ) -> None:
        if os.path.exists(filename) and os.path.islink(filename):
            raise libioc.errors.SecurityViolation(
                reason="Refusing to write to a symlink",
                logger=self.logger
            )
        import ucl
        with open(filename, "w") as f:
            f.write(ucl.dump(data, ucl.UCL_EMIT_JSON))

    def _get_release_pkg_dataset(
        self,
        release_major_version: int
    ) -> libzfs.ZFSDataset:
        """Return the global package mirror dataset for the release."""
        dataset: libzfs.ZFSDataset = self.zfs.get_or_create_dataset(
            f"{self.host.datasets.main.pkg.name}/{release_major_version}"
        )
        return dataset

    def __get_pkg_directory_fstab_line(
        self,
        jail: 'libioc.Jail.JailGenerator'
    ) -> libioc.Config.Jail.File.Fstab.FstabLine:
        destination_dir = f"{jail.root_path}{self.package_source_directory}"

        release_major_version = math.floor(jail.release.version_number)
        repo_ds = self._get_release_pkg_dataset(release_major_version)
        cache_ds = self.zfs.get_or_create_dataset(f"{repo_ds.name}/cache")
        return libioc.Config.Jail.File.Fstab.FstabLine(dict(
            source=cache_ds.mountpoint,
            destination=f"{destination_dir}",
            options="ro",
            type="nullfs"
        ))

    def _get_temporary_jail(
        self,
        source_jail: 'libioc.Jail.JailGenerator'
    ) -> 'libioc.Jail.JailGenerator':
        temporary_name = source_jail.name + "_pkg"
        temporary_jail = libioc.Jail.JailGenerator(
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
        temporary_jail.config.ignore_user_defaults = True
        self.__mount_pkg_directory(temporary_jail)

        return temporary_jail

    def __mount_pkg_directory(self, jail: libioc.Jail.JailGenerator) -> None:
        try:
            jail.fstab.add_line(
                line=self.__get_pkg_directory_fstab_line(jail),
                auto_create_destination=True,
                auto_mount_jail=True,
                replace=True
            )
            self.__pkg_directory_mounted = True
        except (
            libioc.errors.FstabDestinationExists,
            libioc.errors.UnmountFailed
        ):
            pass
        finally:
            jail.fstab.save()
