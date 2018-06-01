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
import os.path
import re
import shutil
import urllib

import iocage.lib.events
import iocage.lib.errors
import iocage.lib.Jail

# MyPy
import libzfs


class Updater:
    """Updater for Releases and other LaunchableResources like Jails."""

    update_name: str
    update_script_name: str
    update_conf_name: str

    _temporary_jail: 'iocage.lib.Jail.JailGenerator'

    def __init__(
        self,
        resource: 'iocage.lib.LaunchableResource.LaunchableResource',
        distribution: 'iocage.lib.Distribution.Distribution'
    ) -> None:
        self.resource = resource
        self.distribution = distribution

    @property
    def logger(self) -> 'iocage.lib.Logger.Logger':
        """Shortcut to the resources logger."""
        return self.resource.logger

    @property
    def local_release_updates_dir(self) -> str:
        """Return the absolute path to updater directory (os-dependend)."""
        return f"/var/db/{self.update_name}"

    @property
    def host_updates_dataset_name(self) -> str:
        """Return the name of the updates dataset."""
        ReleaseGenerator = iocage.lib.Release.ReleaseGenerator
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
    def release(self) -> 'iocage.lib.Release.ReleaseGenerator':
        """Return the associated release."""
        if isinstance(self.resource, iocage.lib.Release.ReleaseGenerator):
            return self.resource
        return self.resource.release

    def _wrap_command(self, command: str, kind: str) -> str:
        return command

    @property
    def temporary_jail(self) -> 'iocage.lib.Jail.JailGenerator':
        """Temporary jail instance that will be created to run the update."""
        if hasattr(self, "_temporary_jail") is False:
            temporary_name = self.resource.name.replace(".", "-") + "_u"
            temporary_jail = iocage.lib.Jail.JailGenerator(
                {
                    "name": temporary_name,
                    "basejail": False,
                    "allow_mount_nullfs": "1",
                    "release": self.release.name,
                    "exec.start": None,
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

            root_path = temporary_jail.root_path
            destination_dir = f"{root_path}{self.local_release_updates_dir}"
            temporary_jail.fstab.file = "fstab_update"
            temporary_jail.fstab.new_line(
                source=self.host_updates_dir,
                destination=destination_dir,
                options="rw"
            )
            temporary_jail.fstab.save()
            self._temporary_jail = temporary_jail
        return self._temporary_jail

    @property
    def _fetch_command(self) -> typing.List[str]:
        raise NotImplementedError("To be implemented by inheriting classes")

    @property
    def _update_command(self) -> typing.List[str]:
        raise NotImplementedError("To be implemented by inheriting classes")

    def _ensure_release_is_supported(self) -> None:
        return

    def _get_release_trunk_file_url(
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
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
        if os.path.isdir(directory):
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

        self.logger.verbose(f"Downloading {url}")
        _request = urllib.request  # type: ignore
        _request.urlretrieve(url, local)  # nosec: url validated
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

        self._download_updater_asset(
            mode=0o644,
            remote=f"etc/{self.update_conf_name}",
            local=f"{self.host_updates_dir}/{self.update_conf_name}"
        )

        self._modify_updater_config(
            path=f"{self.host_updates_dir}/{self.update_conf_name}"
        )

    def fetch(
        self
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:
        """Fetch the update of a release."""
        ReleaseGenerator = iocage.lib.Release.ReleaseGenerator
        if isinstance(self.resource, ReleaseGenerator) is False:
            raise iocage.lib.errors.NonReleaseUpdateFetch(
                resource=self.resource,
                logger=self.logger
            )

        self._ensure_release_is_supported()

        events = iocage.lib.events
        releaseUpdatePullEvent = events.ReleaseUpdatePull(self.release)
        releaseUpdateDownloadEvent = events.ReleaseUpdateDownload(self.release)

        yield releaseUpdatePullEvent.begin()
        try:
            self._pull_updater()
        except Exception as e:
            yield releaseUpdatePullEvent.fail(e)
            raise
        yield releaseUpdatePullEvent.end()

        yield releaseUpdateDownloadEvent.begin()
        self.logger.verbose(
            f"Fetching updates for release '{self.release.name}'"
        )
        try:
            self._create_download_dir()
            iocage.lib.helpers.exec(
                self._wrap_command(" ".join(self._fetch_command), "fetch"),
                shell=True,  # nosec: B604
                logger=self.logger
            )
        except Exception as e:
            yield releaseUpdateDownloadEvent.fail(e)
            raise
        yield releaseUpdateDownloadEvent.end()

    def apply(
        self
    ) -> typing.Generator[typing.Union[
        'iocage.lib.events.IocageEvent',
        bool
    ], None, None]:
        """Apply the fetched updates to the associated release or jail."""
        dataset = self.host_updates_dataset
        snapshot_name = iocage.lib.ZFS.append_snapshot_datetime(
            f"{dataset.name}@pre-update"
        )

        runResourceUpdateEvent = iocage.lib.events.RunResourceUpdate(
            self.resource
        )
        yield runResourceUpdateEvent.begin()

        # create snapshot before the changes
        dataset.snapshot(name=snapshot_name, recursive=True)

        def _rollback_snapshot() -> None:
            self.logger.spam(f"Rolling back to snapshot {snapshot_name}")
            snapshot = self.resource.zfs.get_snapshot(snapshot_name)
            snapshot.rollback(force=True)
            snapshot.delete()

        runResourceUpdateEvent.add_rollback_step(_rollback_snapshot)

        jail = self.temporary_jail
        changed: bool = False

        try:
            for event in self._update_jail(jail):
                if isinstance(event, iocage.lib.events.IocageEvent):
                    yield event
                else:
                    changed = (event is True)
        except Exception as e:
            yield runResourceUpdateEvent.fail(e)
            raise

        _rollback_snapshot()
        yield runResourceUpdateEvent.end()
        yield changed

    def _update_jail(
        self,
        jail: 'iocage.lib.Jail.JailGenerator'
    ) -> typing.Generator[typing.Union[
        'iocage.lib.events.IocageEvent',
        bool
    ], None, None]:

        events = iocage.lib.events
        executeResourceUpdateEvent = events.ExecuteResourceUpdate(
            self.resource
        )
        yield executeResourceUpdateEvent.begin()

        skipped = False
        try:
            self._create_jail_update_dir()
            for event in iocage.lib.Jail.JailGenerator.fork_exec(
                jail,
                self._wrap_command(" ".join(self._update_command), "update"),
                passthru=False
            ):
                if isinstance(event, iocage.lib.events.JailLaunch) is True:
                    if event.done is True:
                        _skipped_text = "No updates are available to install."
                        skipped = (_skipped_text in event.stdout)
                yield event
            self.logger.debug(
                f"Update of resource '{self.resource.name}' finished"
            )
        except Exception as e:
            err = iocage.lib.errors.UpdateFailure(
                name=self.release.name,
                reason=(
                    f"{self.update_name} failed"
                ),
                logger=self.logger
            )
            yield executeResourceUpdateEvent.fail(err)
            raise e
        finally:
            jail.state.query()
            if jail.running:
                self.logger.debug(
                    "The update jail is still running. "
                    "Force-stopping it now."
                )
                for event in iocage.lib.Jail.JailGenerator.stop(
                    jail,
                    force=True
                ):
                    yield event

        if skipped is True:
            yield executeResourceUpdateEvent.skip()
        else:
            yield executeResourceUpdateEvent.end()

        self.logger.verbose(f"Resource '{self.resource.name}' updated")
        yield True  # ToDo: yield False if nothing was updated


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
            "-v", "latest", "-U",  # skip version check
            "-n",  # no kernel
            "-V",
            "-D",  # no download
        ] + self._version_dependent_command_attributes

    @property
    def _fetch_command(self) -> typing.List[str]:
        return [
            f"{self.host_updates_dir}/{self.update_script_name}",
            f"{self.host_updates_dir}/temp",
            "-k",
            self.release.name,
            "-f",  # fetch only
            "-c",
            f"{self.host_updates_dir}/{self.update_conf_name}",
            "-V"
        ] + self._version_dependent_command_attributes

    @property
    def _version_dependent_command_attributes(self) -> typing.List[str]:
        version = self.release.version_number
        if (version >= 10.4) or (version == 0):
            return [
                "-T",
                "-t",
                self.local_temp_dir
            ]  # keep temp
        elif version >= 10.3:
            return ["-t", self.local_temp_dir]

    def _ensure_release_is_supported(self) -> None:
        version = self.release.version_number
        if (version == 0) or (version >= 10.3):
            return
        raise iocage.lib.errors.UnsupportedRelease(
            version=version,
            logger=self.logger
        )

    def _get_release_trunk_file_url(
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
        filename: str
    ) -> str:

        return "/".join([
            "https://raw.githubusercontent.com/HardenedBSD/hardenedBSD",
            release.hbds_release_branch,
            filename
        ])


class FreeBSD(Updater):
    """Updater for FreeBSD."""

    update_name: str = "freebsd-update"
    update_script_name: str = "freebsd-update.sh"
    update_conf_name: str = "freebsd-update.conf"

    def _get_release_trunk_file_url(
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
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
    def _update_command(self) -> typing.List[str]:
        return [
            f"{self.local_release_updates_dir}/{self.update_script_name}",
            "--not-running-from-cron",
            "-d",
            self.local_temp_dir,
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
            "-f",
            f"{self.host_updates_dir}/{self.update_conf_name}",
            "--not-running-from-cron",
            "fetch"
        ]

    def _modify_updater_config(self, path: str) -> None:
        with open(path, "r+") as f:
            content = f.read()
            pattern = re.compile("^Components .+$", re.MULTILINE)
            f.seek(0)
            f.write(pattern.sub(
                "Components world",
                content
            ))
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
            "echo $OUTPUT",
            "RC=$?",
            "if [ $RC -gt 0 ]; then",
            tolerated_error_message,
            "fi"
        ])
        return _command


def get_launchable_update_resource(  # noqa: T484
    distribution: 'iocage.lib.Distribution.Distribution',
    **kwargs
) -> Updater:
    """Return an updater instance for the host distribution."""
    _class: typing.Type[Updater]

    if distribution.name == "HardenedBSD":
        _class = HardenedBSD
    else:
        _class = FreeBSD

    return _class(
        distribution=distribution,
        **kwargs
    )
