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
import typing
import datetime
import os.path
import re
import shutil
import urllib

import iocage.lib.events
import iocage.lib.errors
import iocage.lib.Jail

# MyPy
import subprocess

class LaunchableResourceUpdate:

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
    def logger(self):
        return self.resource.logger    

    @property
    def local_release_updates_dir(self):
        return f"/var/db/{self.update_name}"

    @property
    def host_release_updates_dir(self) -> str:
        return f"{self.release.dataset.mountpoint}/updates"

    @property
    def local_temp_dir(self):
        # ToDo: Resolve resource deadlock when mounting rw in ro nullfs mount
        # return f"{self.local_release_updates_dir}/temp",
        return "/tmp/iocage-update"
    
    @property
    def release(self):
        if isinstance(self.resource, iocage.lib.Release.ReleaseGenerator):
            return self.resource
        return self.resource.release
    
    @property
    def _install_error_handler(self):
        return None

    @property
    def temporary_jail(self):
        """
        Temporary jail instance that will be created to run the update
        """
        if hasattr(self, "_temporary_jail") is False:
            temporary_name = self.resource.name.replace(".", "-") + "_u"
            temporary_jail = iocage.lib.Jail.JailGenerator(
                {
                    "name": temporary_name,
                    "basejail": False,
                    "allow_mount_nullfs": "1",
                    "release": self.release.name,
                    "securelevel": "0",
                    "vnet": False,
                    "ip4_addr": None,
                    "ip6_addr": None,
                    "defaultrouter": None
                },
                new=True,
                logger=self.resource.logger,
                zfs=self.resource.zfs,
                host=self.resource.host,
                dataset=self.resource.dataset
            )
            temporary_jail.config.file = "config_update.json"

            root_path = temporary_jail.root_path
            destination_dir = f"{root_path}/{self.local_release_updates_dir}"
            temporary_jail.fstab.file = "fstab_update"
            temporary_jail.fstab.new_line(
                source=self.host_release_updates_dir,
                destination=destination_dir
            )
            temp_dir = f"{root_path}{self.local_temp_dir}"
            self._clean_create_dir(temp_dir)
            temporary_jail.fstab.new_line(
                source=f"{self.host_release_updates_dir}/temp",
                destination=temp_dir,
                options="rw"
            )
            temporary_jail.fstab.save()
            self._temporary_jail = temporary_jail
        return self._temporary_jail

    def _update_jail(self) -> None:
        return NotImplementedError("To be implemented by inheriting classes")

    def _create_updates_dir(self) -> None:
        self._create_dir(self.host_release_updates_dir)

    def _clean_create_download_dir(self) -> None:
        self._clean_create_dir(f"{self.host_release_updates_dir}/temp")

    def _create_jail_update_dir(self) -> None:
        root_path = self.release.root_path
        jail_update_dir = f"{root_path}{self.local_release_updates_dir}"
        self._clean_create_dir(jail_update_dir)
        shutil.chown(jail_update_dir, "root", "wheel")
        os.chmod(jail_update_dir, 0o755)

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
        urllib.request.urlretrieve(url, local)  # nosec: url validated
        os.chmod(local, mode)

        self.logger.debug(
            f"Update-asset {remote} for release '{self.release.name}'"
            f" saved to {local}"
        )

    def _modify_updater_config(self, path: str) -> None:
        pass

    def _pull_updater(self):

        self._create_updates_dir()

        self._download_updater_asset(
            mode=0o744,
            remote=f"usr.sbin/{self.update_name}/{self.update_script_name}",
            local=f"{self.host_release_updates_dir}/{self.update_script_name}"
        )

        self._download_updater_asset(
            mode=0o644,
            remote=f"etc/{self.update_conf_name}",
            local=f"{self.host_release_updates_dir}/{self.update_conf_name}"
        )

        self._modify_updater_config(
            path=f"{self.host_release_updates_dir}/{self.update_conf_name}"
        )

    def _append_datetime(self, text: str) -> str:
        now = datetime.datetime.utcnow()
        text += now.strftime("%Y%m%d%H%I%S.%f")
        return text

    def fetch(
        self
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        ReleaseGenerator = iocage.lib.Release.ReleaseGenerator
        if isinstance(self.resource, ReleaseGenerator) is False:
            raise iocage.lib.errors.NonReleaseUpdateFetch(
                resource=self.resource,
                logger=self.logger
            )

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
            self._clean_create_download_dir()
            iocage.lib.helpers.exec(
                self._fetch_command,
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

        dataset = self.resource.dataset
        snapshot_name = self._append_datetime(f"{dataset.name}@pre-update")

        runReleaseUpdateEvent = iocage.lib.events.RunReleaseUpdate(
            self.release
        )
        yield runReleaseUpdateEvent.begin()

        # create snapshot before the changes
        dataset.snapshot(snapshot_name, recursive=True)

        jail = self.temporary_jail
        changed: bool = False

        def _revert_changes():
            for event in jail.stop(force=True):
                yield event
            self.logger.verbose(f"Rolling back to {snapshot_name}")
            self.resource.zfs.get_snapshot(snapshot_name).rollback(force=True)
        runReleaseUpdateEvent.add_rollback_step(_revert_changes)

        try:
            for event in self._update_jail(jail):
                if isinstance(event, iocage.lib.events.IocageEvent):
                    yield event
                else:
                    changed = event
        except Exception as e:
            yield runReleaseUpdateEvent.fail(e)
            raise e

        jail.stop()
        yield runReleaseUpdateEvent.end()
        yield changed

    def _update_jail(
        self,
        jail: 'iocage.lib.Jail.JailGenerator'
    ) -> typing.Generator[typing.Union[
        'iocage.lib.events.IocageEvent',
        bool
    ], None, None]:

        events = iocage.lib.events
        executeReleaseUpdateEvent = events.ExecuteReleaseUpdate(self.release)

        try:
            self._create_jail_update_dir()
            for event in jail.fork_exec(
                self._update_command,
                error_handler=self._install_error_handler
            ):
                yield event
            self.logger.debug(
                f"Update of release '{self.release.name}' finished"
            )
        except Exception:
            raise
            err = iocage.lib.errors.ReleaseUpdateFailure(
                release_name=self.release.name,
                reason=(
                    f"{self.update_name} failed"
                ),
                logger=self.logger
            )
            yield executeReleaseUpdateEvent.fail(err)
            raise err

        yield executeReleaseUpdateEvent.end()

        self.logger.verbose(f"Release '{self.release.name}' updated")
        yield True  # ToDo: yield False if nothing was updated


class LaunchableResourceUpdateHardenedBSD(LaunchableResourceUpdate):

    update_name: str = "hbsd-update"
    update_script_name: str = "hbsd-update"
    update_conf_name: str = "hbsd-update.conf"

    @property
    def _update_command(self) -> typing.List[str]:
        return [
            f"{self.local_release_updates_dir}/{self.update_script_name}",
            "-c",
            f"{self.local_release_updates_dir}/{self.update_conf_name}",
            "-V",
            "-D",  # no download
            "-T",  # keep temp
            "-t",
            self.local_temp_dir
        ]

    @property
    def _fetch_command(self) -> typing.List[str]:
        return [
            f"{self.host_release_updates_dir}/{self.update_script_name}"
            "--not-running-from-cron",
            "-T",  # keep temp
            "-t",
            f"{self.host_release_updates_dir}/temp",
            "-k",
            self.release.name,
            "-f",  # fetch only
            "-c",
            f"{self.host_release_updates_dir}/{self.update_conf_name}",
            "-V"
        ]

    def _get_release_trunk_file_url(
        self,
        release: 'iocage.lib.Release.ReleaseGenerator',
        filename: str
    ) -> str:

        # return "/".join([
        #     "https://raw.githubusercontent.com/HardenedBSD/hardenedBSD",
        #     release.hbds_release_branch,
        #     filename
        # ])

        return "/".join([
            (
                "https://raw.githubusercontent.com/gronke/hardenedBSD"
                "/hbsd-update-fetchonly"
            ),
            release.hbds_release_branch,
            filename
        ])


class LaunchableResourceUpdateFreeBSD(LaunchableResourceUpdate):

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
            f"{self.host_release_updates_dir}/{self.update_script_name}",
            "--not-running-from-cron",
            "-d",
            f"{self.host_release_updates_dir}/temp",
            "--currently-running",
            self.release.name,
            "-f",
            f"{self.host_release_updates_dir}/{self.update_conf_name}",
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

    @property
    def _install_error_handler(self):
        def error_handler(
            child: subprocess.Popen,
            stdout: str,
            stderr: str
        ) -> typing.Tuple[bool, str]:
            if "No updates are available to install." in stdout:
                return (True, "already up to date",)
            else:
                return (False, (
                    "freebsd-update.sh exited "
                    f"with returncode {child.returncode}"
                ),)

def get_launchable_update_resource(
    distribution: 'iocage.lib.Distribution.Distribution',
    **kwargs
) -> LaunchableResourceUpdate:
    
    if distribution.name == "HardenedBSD":
        _class = LaunchableResourceUpdateHardenedBSD
    else:
        _class = LaunchableResourceUpdateFreeBSD

    return _class(
        distribution=distribution,
        **kwargs
    )
