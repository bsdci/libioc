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
"""Updater for Releases and other LaunchableResources like Jails."""
import typing
import os
import os.path
import re
import shutil
import urllib
import urllib.request
import urllib.error

import libioc.events
import libioc.errors
import libioc.Jail

# MyPy
import libzfs


class Updater:
    """Updater for Releases and other LaunchableResources like Jails."""

    update_name: str
    update_script_name: str
    update_conf_name: str

    _temporary_jail: 'libioc.Jail.JailGenerator'

    def __init__(
        self,
        resource: 'libioc.LaunchableResource.LaunchableResource',
        host: 'libioc.Host.HostGenerator'
    ) -> None:
        self.resource = resource
        self.host = host

    @property
    def logger(self) -> 'libioc.Logger.Logger':
        """Shortcut to the resources logger."""
        return self.resource.logger

    @property
    def local_release_updates_dir(self) -> str:
        """Return the absolute path to updater directory (os-dependend)."""
        return f"/var/db/{self.update_name}"

    @property
    def host_updates_dataset_name(self) -> str:
        """Return the name of the updates dataset."""
        ReleaseGenerator = libioc.Release.ReleaseGenerator
        if isinstance(self.resource, ReleaseGenerator):
            release_dataset = self.resource.dataset
        else:
            release_dataset = self.resource.release.dataset
        return f"{release_dataset.name}/updates"

    @property
    def host_updates_dataset(self) -> libzfs.ZFSDataset:
        """Return the updates dataset."""
        dataset_name = self.host_updates_dataset_name
        zfs = self.resource.zfs
        _dataset = zfs.get_or_create_dataset(dataset_name)
        dataset = _dataset  # type: libzfs.ZFSDataset
        return dataset

    @property
    def host_updates_dir(self) -> str:
        """Return the mountpoint of the updates dataset."""
        return str(self.host_updates_dataset.mountpoint)

    @property
    def local_temp_dir(self) -> str:
        """Return the update temp directory relative to the jail root."""
        return f"{self.local_release_updates_dir}/temp"

    @property
    def release(self) -> 'libioc.Release.ReleaseGenerator':
        """Return the associated release."""
        if isinstance(self.resource, libioc.Release.ReleaseGenerator):
            return self.resource
        return self.resource.release

    def _wrap_command(self, command: str, kind: str) -> str:
        return command

    @property
    def patch_version(self) -> int:
        """
        Return the latest known patch version.

        When no patch version is known the release was not updated yet.
        """
        return 0

    @property
    def temporary_jail(self) -> 'libioc.Jail.JailGenerator':
        """Temporary jail instance that will be created to run the update."""
        if hasattr(self, "_temporary_jail") is False:
            temporary_name = self.resource.name.replace(".", "-") + "_u"
            temporary_jail = libioc.Jail.JailGenerator(
                {
                    "name": temporary_name,
                    "basejail": False,
                    "allow_mount_nullfs": "1",
                    "release": self.release.name,
                    "exec_start": None,
                    "securelevel": "0",
                    "allow_chflags": True,
                    "vnet": False,
                    "ip4_addr": None,
                    "ip6_addr": None,
                    "defaultrouter": None,
                    "mount_devfs": True,
                    "mount_fdescfs": False
                },
                new=True,
                logger=self.resource.logger,
                zfs=self.resource.zfs,
                host=self.resource.host,
                dataset=self.resource.dataset
            )
            temporary_jail.config.file = "config_update.json"
            temporary_jail.config.ignore_source_config = True

            root_path = temporary_jail.root_path
            destination_dir = f"{root_path}{self.local_release_updates_dir}"
            temporary_jail.fstab.file = "fstab_update"
            temporary_jail.fstab.new_line(
                source=self.host_updates_dir,
                destination=destination_dir,
                options="rw"
            )
            if os.path.isdir(destination_dir) is False:
                os.makedirs(destination_dir, 0o755)
            temporary_jail.fstab.save()
            self._temporary_jail = temporary_jail
        return self._temporary_jail

    @property
    def _fetch_command(self) -> typing.List[str]:
        raise NotImplementedError("To be implemented by inheriting classes")

    @property
    def _update_command(self) -> typing.List[str]:
        raise NotImplementedError("To be implemented by inheriting classes")

    def _get_release_trunk_file_url(
        self,
        release: 'libioc.Release.ReleaseGenerator',
        filename: str
    ) -> str:
        raise NotImplementedError("To be implemented by inheriting classes")

    def _create_updates_dir(self) -> None:
        self._create_dir(self.host_updates_dir)

    def _create_download_dir(self) -> None:
        self._create_dir(f"{self.host_updates_dir}/temp")

    def _create_jail_update_dir(self) -> None:
        root_path = self.release.root_path
        jail_update_dir = f"{root_path}{self.local_release_updates_dir}"
        self._clean_create_dir(jail_update_dir)
        shutil.chown(jail_update_dir, "root", "wheel")
        os.chmod(jail_update_dir, 0o755)  # nosec: accessible directory

    def _create_dir(self, directory: str) -> None:
        if os.path.isdir(directory):
            return
        os.makedirs(directory)

    def _clean_create_dir(self, directory: str) -> None:
        if os.path.ismount(directory) is True:
            libioc.helpers.umount(directory, force=True, logger=self.logger)
        if os.path.isdir(directory) is True:
            self.logger.verbose(f"Deleting existing directory {directory}")
            shutil.rmtree(directory)
        self._create_dir(directory)

    @property
    def local_release_updater_config(self) -> str:
        """Return the local path to the release updater config."""
        return f"{self.local_release_updates_dir}/{self.update_conf_name}"

    def _download_updater_asset(
        self,
        local: str,
        remote: str,
        mode: int
    ) -> None:

        url = self._get_release_trunk_file_url(
            release=self.release,
            filename=remote
        )

        if os.path.isfile(local):
            os.remove(local)

        _request = urllib.request
        try:
            self.logger.verbose(f"Downloading update assets from {url}")
            _request.urlretrieve(url, local)  # nosec: url validated
        except urllib.error.HTTPError as http_error:
            raise libioc.errors.DownloadFailed(
                url="EOL Warnings",
                code=http_error.code,
                logger=self.logger
            )
        os.chmod(local, mode)

        self.logger.debug(
            f"Update-asset {remote} for release '{self.release.name}'"
            f" saved to {local}"
        )

    def _modify_updater_config(self, path: str) -> None:
        pass

    def _pull_updater(self) -> None:

        self._create_updates_dir()

        self._download_updater_asset(
            mode=0o744,
            remote=f"usr.sbin/{self.update_name}/{self.update_script_name}",
            local=f"{self.host_updates_dir}/{self.update_script_name}"
        )

        if self.release.version_number >= 12:
            conf_path = f"usr.sbin/{self.update_name}/{self.update_conf_name}"
        else:
            conf_path = f"etc/{self.update_conf_name}"

        self._download_updater_asset(
            mode=0o644,
            remote=conf_path,
            local=f"{self.host_updates_dir}/{self.update_conf_name}"
        )

        self._modify_updater_config(
            path=f"{self.host_updates_dir}/{self.update_conf_name}"
        )

    def fetch(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Fetch the update of a release."""
        ReleaseGenerator = libioc.Release.ReleaseGenerator
        if isinstance(self.resource, ReleaseGenerator) is False:
            raise libioc.errors.NonReleaseUpdateFetch(
                resource=self.resource,
                logger=self.logger
            )

        self.resource._require_release_supported()

        events = libioc.events
        releaseUpdatePullEvent = events.ReleaseUpdatePull(
            self.release,
            scope=event_scope
        )
        releaseUpdateDownloadEvent = events.ReleaseUpdateDownload(
            self.release,
            scope=releaseUpdatePullEvent.scope
        )

        yield releaseUpdatePullEvent.begin()
        try:
            self._pull_updater()

            # Additional pre-fetch check on HardenedBSD
            if self.host.distribution.name == "HardenedBSD":
                _version_snapshot_name = (
                    f"{self.release.root_dataset.name}"
                    f"@p{self.patch_version}"
                )
                try:
                    self.resource.zfs.get_snapshot(_version_snapshot_name)
                    yield releaseUpdatePullEvent.skip()
                except libzfs.ZFSException:
                    yield releaseUpdatePullEvent.end()
            else:
                yield releaseUpdatePullEvent.end()
        except Exception as e:
            yield releaseUpdatePullEvent.fail(e)
            raise

        yield releaseUpdateDownloadEvent.begin()

        if releaseUpdatePullEvent.skipped is True:
            yield releaseUpdateDownloadEvent.skip()
            return

        self.logger.verbose(
            f"Fetching updates for release '{self.release.name}'"
        )

        self._pre_fetch()

        try:
            env = dict()
            env_clone_keys = ["http_proxy"]
            for key in os.environ:
                if key.lower() in env_clone_keys:
                    env[key.lower()] = os.environ[key]

            self._create_download_dir()
            libioc.helpers.exec(
                self._wrap_command(" ".join(self._fetch_command), "fetch"),
                shell=True,  # nosec: B604
                logger=self.logger,
                env=env
            )
        except Exception as e:
            yield releaseUpdateDownloadEvent.fail(e)
            raise
        finally:
            self._post_fetch()
        yield releaseUpdateDownloadEvent.end()

    def _snapshot_release_after_update(self) -> None:
        self.release.snapshot(f"p{self.patch_version}")

    def apply(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator[typing.Union[
        'libioc.events.IocEvent',
        bool
    ], None, None]:
        """Apply the fetched updates to the associated release or jail."""
        updates_dataset = self.host_updates_dataset
        snapshot_name = libioc.ZFS.append_snapshot_datetime(
            f"{updates_dataset.name}@pre-update"
        )

        runResourceUpdateEvent = libioc.events.RunResourceUpdate(
            self.resource,
            scope=event_scope
        )
        _scope = runResourceUpdateEvent.scope
        yield runResourceUpdateEvent.begin()

        # create snapshot before the changes
        updates_dataset.snapshot(name=snapshot_name, recursive=True)

        def _rollback_updates_snapshot() -> None:
            self.logger.spam(f"Rolling back to snapshot {snapshot_name}")
            snapshot = self.resource.zfs.get_snapshot(snapshot_name)
            snapshot.rollback(force=True)
            snapshot.delete()

        runResourceUpdateEvent.add_rollback_step(_rollback_updates_snapshot)

        jail = self.temporary_jail
        changed: bool = False

        try:
            for event in self._update_jail(jail, event_scope=_scope):
                if isinstance(event, libioc.events.IocEvent):
                    yield event
                else:
                    changed = (event is True)
        except Exception as e:
            yield runResourceUpdateEvent.fail(e)
            raise

        # restore any changes to the update dataset
        _rollback_updates_snapshot()

        if isinstance(self.resource, libioc.Release.ReleaseGenerator):
            self._snapshot_release_after_update()

        yield runResourceUpdateEvent.end()
        yield changed

    def _update_jail(
        self,
        jail: 'libioc.Jail.JailGenerator',
        event_scope: typing.Optional['libioc.events.Scope']
    ) -> typing.Generator[typing.Union[
        'libioc.events.IocEvent',
        bool
    ], None, None]:

        events = libioc.events
        executeResourceUpdateEvent = events.ExecuteResourceUpdate(
            self.resource,
            scope=event_scope
        )
        _scope = executeResourceUpdateEvent.scope
        yield executeResourceUpdateEvent.begin()

        skipped = False
        self._pre_update()

        try:
            self._create_jail_update_dir()
            for event in libioc.Jail.JailGenerator.fork_exec(
                jail,
                self._wrap_command(" ".join(self._update_command), "update"),
                passthru=False,
                start_dependant_jails=False,
                event_scope=_scope
            ):
                if isinstance(event, libioc.events.JailCommand) is True:
                    if (event.done is True) and (event.error is None):
                        _skipped_text = "No updates are available to install."
                        skipped = (_skipped_text in event.stdout) is True
                yield event
            self.logger.debug(
                f"Update of resource '{self.resource.name}' finished"
            )
        except Exception as e:
            err = libioc.errors.UpdateFailure(
                name=self.release.name,
                reason=(
                    f"{self.update_name} failed"
                ),
                logger=self.logger
            )
            yield executeResourceUpdateEvent.fail(err)
            raise e
        finally:
            if jail.running:
                self.logger.debug(
                    "The update jail is still running. "
                    "Force-stopping it now."
                )
                yield from libioc.Jail.JailGenerator.stop(
                    jail,
                    force=True,
                    event_scope=executeResourceUpdateEvent.scope
                )
            self._post_update()

        if skipped is True:
            yield executeResourceUpdateEvent.skip("already up to date")
        else:
            yield executeResourceUpdateEvent.end()

        self.logger.verbose(f"Resource '{self.resource.name}' updated")
        yield True  # ToDo: yield False if nothing was updated

    def _pre_fetch(self) -> None:
        """Execute before executing the fetch command."""
        pass

    def _post_fetch(self) -> None:
        """Execute after executing the fetch command."""
        pass

    def _pre_update(self) -> None:
        """Execute before executing the update command."""
        pass

    def _post_update(self) -> None:
        """Execute after executing the update command."""
        pass


class HardenedBSD(Updater):
    """Updater for HardenedBSD."""

    update_name: str = "hbsd-update"
    update_script_name: str = "hbsd-update"
    update_conf_name: str = "hbsd-update.conf"

    @property
    def _update_command(self) -> typing.List[str]:
        return [
            f"{self.local_release_updates_dir}/{self.update_script_name}",
            "-c",
            f"{self.local_release_updates_dir}/{self.update_conf_name}",
            "-i",  # ignore version check (offline)
            "-v", str(self.patch_version), "-U",  # skip version check
            "-n",  # no kernel
            "-V",
            "-D",  # no download,
            "-T",
            "-t",
            self.local_temp_dir
        ]

    @property
    def _fetch_command(self) -> typing.List[str]:
        return [
            f"{self.host_updates_dir}/{self.update_script_name}",
            "-k",
            self.release.name,
            "-f",  # fetch only
            "-c",
            f"{self.host_updates_dir}/{self.update_conf_name}",
            "-V",
            "-T",
            "-t",
            f"{self.host_updates_dir}/temp",
            "-r"
            f"{self.resource.root_path}"
        ]

    def _get_release_trunk_file_url(
        self,
        release: 'libioc.Release.ReleaseGenerator',
        filename: str
    ) -> str:

        return "/".join([
            "https://raw.githubusercontent.com/HardenedBSD/hardenedBSD",
            release.hbds_release_branch,
            filename
        ])

    @property
    def release_branch_name(self) -> str:
        """Return the branch name of the HBSD release."""
        return f"hardened/{self.host.release_version.lower()}/master"

    def _pull_updater(self) -> None:
        super()._pull_updater()
        update_info_url = "/".join([
            "https://updates.hardenedbsd.org/pub/HardenedBSD/updates/",
            self.release_branch_name,
            self.host.processor,
            "update-latest.txt"
        ])
        local_path = f"{self.host_updates_dir}/update-latest.txt"
        _request = urllib.request
        _request.urlretrieve(  # nosec: official HardenedBSD URL
            update_info_url,
            local_path
        )
        os.chmod(local_path, 0o744)

    @property
    def patch_version(self) -> int:
        """
        Return the latest known patch version.

        On HardenedBSD this version is published among the updated downloaded
        by hbsd-update. Right before fetching an updater this file is
        downloaded, so that the revision mentioned can be used for snapshot
        creation.
        """
        local_path = f"{self.host_updates_dir}/update-latest.txt"
        if os.path.isfile(local_path):
            with open(local_path, "r", encoding="utf-8") as f:
                return int(f.read().split("|")[1].split("-")[1][1:])
        else:
            return 0


class FreeBSD(Updater):
    """Updater for FreeBSD."""

    update_name: str = "freebsd-update"
    update_script_name: str = "freebsd-update.sh"
    update_conf_name: str = "freebsd-update.conf"

    def _get_release_trunk_file_url(
        self,
        release: 'libioc.Release.ReleaseGenerator',
        filename: str
    ) -> str:

        if release.name == "11.0-RELEASE":
            release_name = "11.0.1"
        else:
            fragments = release.name.split("-", maxsplit=1)
            release_name = f"{fragments[0]}.0"

        base_url = "https://svn.freebsd.org/base/release"
        return f"{base_url}/{release_name}/{filename}"

    @property
    def _base_release_symlink_location(self) -> str:
        """Return the virtual path of a symlink to the release p0 snapshot."""
        return f"/tmp/ioc-release-{self.release.full_name}-p0"  # nosec: B108

    @property
    def _update_command(self) -> typing.List[str]:
        return [
            f"{self.local_release_updates_dir}/{self.update_script_name}",
            "--not-running-from-cron",
            "-d",
            self.local_temp_dir,
            "-b",
            f"{self._base_release_symlink_location}/",
            "--currently-running",
            self.release.name,
            "-r",
            self.release.name,
            "-f",
            f"{self.local_release_updates_dir}/{self.update_conf_name}",
            "install"
        ]

    @property
    def _fetch_command(self) -> typing.List[str]:
        return [
            f"{self.host_updates_dir}/{self.update_script_name}",
            "-d",
            f"{self.host_updates_dir}/temp",
            "--currently-running",
            self.release.name,
            "-b",
            f"{self._base_release_symlink_location}/",
            "-f",
            f"{self.host_updates_dir}/{self.update_conf_name}",
            "--not-running-from-cron",
            "fetch"
        ]

    def _modify_updater_config(self, path: str) -> None:
        with open(path, "r+", encoding="utf-8") as f:
            content = f.read()
            content = re.sub(
                r"^Components .+$",
                "Components world",
                content,
                flags=re.MULTILINE
            )
            f.seek(0)
            f.write(content)
            f.truncate()

    def _wrap_command(self, command: str, kind: str) -> str:

        if kind == "update":
            tolerated_error_message = (
                "echo $OUTPUT"
                " | grep -c 'No updates are available to install.'"
                " >> /dev/null || exit $RC"
            )
        elif kind == "fetch":
            tolerated_error_message = (
                "echo $OUTPUT"
                " | grep -c 'HAS PASSED ITS END-OF-LIFE DATE.'"
                " >> /dev/null || exit $RC"
            )
        else:
            raise ValueError

        _command = "\n".join([
            "set +e",
            f"OUTPUT=\"$({command})\"",
            "RC=$?",
            "echo $OUTPUT",
            "if [ $RC -gt 0 ]; then",
            tolerated_error_message,
            "fi"
        ])
        return _command

    @property
    def patch_version(self) -> int:
        """
        Return the latest known patch version.

        This version is parsed from FreeBSDs /bin/freebsd-version file.
        """
        return int(libioc.helpers.get_os_version(
            f"{self.resource.root_path}/bin/freebsd-version"
        )["patch"])

    def _pre_fetch(self) -> None:
        """Execute before executing the fetch command."""
        symlink_src = self.release.root_path
        if "p0" in [x.snapshot_name for x in self.release.version_snapshots]:
            # use p0 snapshot if available
            symlink_src += "/.zfs/snapshot/p0"
        os.symlink(symlink_src, self._base_release_symlink_location)

    def _post_fetch(self) -> None:
        """Execute after executing the fetch command."""
        os.unlink(self._base_release_symlink_location)

    def _pre_update(self) -> None:
        """Execute before executing the update command."""
        lnk = f"{self.resource.root_path}{self._base_release_symlink_location}"
        self.resource.require_relative_path(f"{lnk}/..")
        if os.path.islink(lnk) is True:
            os.unlink(lnk)
        os.symlink("/", lnk)

    def _post_update(self) -> None:
        """Execute after executing the update command."""
        lnk = f"{self.resource.root_path}{self._base_release_symlink_location}"
        self.resource.require_relative_path(f"{lnk}/..")
        os.unlink(lnk)


def get_launchable_update_resource(  # noqa: T484
    host: 'libioc.Host.HostGenerator',
    resource: 'libioc.Resource.Resource'
) -> Updater:
    """Return an updater instance for the host distribution."""
    _class: typing.Type[Updater]

    if host.distribution.name == "HardenedBSD":
        _class = HardenedBSD
    else:
        _class = FreeBSD

    return _class(
        host=host,
        resource=resource
    )
