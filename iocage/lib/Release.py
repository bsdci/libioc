# Copyright (c) 2014-2017, iocage
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
import hashlib
import os
import re
import shutil
import tarfile
import urllib.request
import urllib.error
import urllib.parse

import libzfs
import ucl

import iocage.lib.ZFS
import iocage.lib.errors
import iocage.lib.helpers
import iocage.lib.events
import iocage.lib.LaunchableResource
import iocage.lib.Jail

# MyPy
import iocage.lib.Resource
import iocage.lib.Host
import iocage.lib.Logger
import iocage.lib.Config.Jail.File.RCConf
import iocage.lib.Config.Jail.File.SysctlConf


class ReleaseResource(iocage.lib.LaunchableResource.LaunchableResource):

    _release: typing.Optional['ReleaseGenerator'] = None

    def __init__(
        self,
        host: iocage.lib.Host.HostGenerator,
        release: typing.Optional['ReleaseGenerator']=None,
        **kwargs
    ) -> None:

        self.__releases_dataset_name = host.datasets.releases.name
        self.__base_dataset_name = host.datasets.base.name
        self.host = iocage.lib.helpers.init_host(self, host)

        iocage.lib.LaunchableResource.LaunchableResource.__init__(
            self,
            **kwargs
        )

        self._release = release

    @property
    def release(self) -> 'ReleaseGenerator':
        """
        Release instance that belongs to the resource

        Usually the resource becomes inherited from the Release itself.
        It can still be used linked to a foreign ReleaseGenerator by passing
        release as named attribute to the __init__ function
        """
        if self._release is not None:
            return self._release

        elif isinstance(self, ReleaseGenerator):
            return self

        raise Exception(
            "Resource is not a valid release itself and has no linked release"
        )

    @property
    def dataset_name(self) -> str:
        """
        Name of the release base ZFS dataset

        If the resource has no dataset or dataset_name assigned yet,
        the release id is used to find name the dataset
        """
        try:
            return str(self._assigned_dataset_name)
        except AttributeError:
            pass

        return f"{self.__releases_dataset_name}/{self.release.name}"

    @dataset_name.setter
    def dataset_name(self, value: str) -> None:
        self._dataset_name = value

    @property
    def base_dataset(self) -> libzfs.ZFSDataset:
        # base datasets are created from releases. required to start
        # zfs-basejails
        ds: libzfs.ZFSDataset = self.zfs.get_dataset(self.base_dataset_name)
        return ds

    @property
    def base_dataset_name(self) -> str:
        return f"{self.__base_dataset_name}/{self.release.name}/root"

    @property
    def file(self) -> typing.Optional[str]:
        return None


class ReleaseGenerator(ReleaseResource):

    DEFAULT_RC_CONF: typing.Dict[str, typing.Union[str, bool]] = {
        "netif_enable": False,
        "sendmail_enable": False,
        "sendmail_submit_enable": False,
        "sendmail_msp_queue_enable": False,
        "sendmail_outbound_enable": False,
        "syslogd_flags": "-ss"
    }

    DEFAULT_SYSCTL_CONF: typing.Dict[str, int] = {
        "net.inet.ip.fw.enable": 0
    }

    name: str
    eol: bool = False

    logger: iocage.lib.Logger.Logger
    zfs: iocage.lib.ZFS.ZFS
    host: iocage.lib.Host.HostGenerator
    _resource: iocage.lib.Resource.Resource
    _assets: typing.List[str]
    _mirror_url: typing.Optional[str] = None

    def __init__(
        self,
        name: str,
        host: typing.Optional[iocage.lib.Host.HostGenerator]=None,
        zfs: typing.Optional[iocage.lib.ZFS.ZFS]=None,
        logger: typing.Optional[iocage.lib.Logger.Logger]=None,
        check_hashes: bool=True,
        eol: bool=False,
        **release_resource_args
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)
        self.host = iocage.lib.helpers.init_host(self, host)

        if not iocage.lib.helpers.validate_name(name):
            raise NameError(f"Invalid 'name' for Release: '{name}'")

        self.name = name
        self.eol = eol
        self._hbsd_release_branch = None

        self._hashes = None
        self.check_hashes = check_hashes is True

        ReleaseResource.__init__(
            self,
            host=self.host,
            logger=self.logger,
            zfs=self.zfs,
            **release_resource_args
        )

        self._assets = ["base"]
        if self.host.distribution.name != "HardenedBSD":
            self._assets.append("lib32")

    @property
    def resource(self) -> 'iocage.lib.Resource.Resource':
        return self._resource

    @resource.setter
    def resource(self, value: 'iocage.lib.Resource.Resource') -> None:
        if value is None:
            self._resource = ReleaseResource(
                release=self,
                host=self.host,
                logger=self.logger,
                zfs=self.zfs
            )
        else:
            self._resource = value

    @property
    def releases_folder(self) -> str:
        return str(self.host.datasets.releases.mountpoint)

    @property
    def download_directory(self) -> str:
        return str(self.dataset.mountpoint)

    @property
    def root_dir(self) -> str:
        try:
            if self.root_dataset.mountpoint:
                return str(self.root_dataset.mountpoint)
        except AttributeError:
            pass

        return f"{self.releases_folder}/{self.name}/root"

    @property
    def assets(self) -> typing.List[str]:
        return self._assets

    @assets.setter
    def assets(self, value: typing.Union[typing.List[str], str]):
        value = [value] if isinstance(value, str) else value
        self._assets = list(map(
            lambda x: x if not x.endswith(".txz") else x[:-4],
            value
        ))

    @property
    def real_name(self) -> str:
        if self.host.distribution.name == "HardenedBSD":
            return f"HardenedBSD-{self.name}-{self.host.processor}-LATEST"
        return self.name

    @property
    def annotated_name(self) -> str:
        annotations = set()

        if self.eol is True:
            annotations.add("EOL")

        if self.newer_than_host is True:
            annotations.add("Newer than Host")

        if len(annotations) > 0:
            return f"{self.name} ({', '.join(annotations)})"

        return f"{self.name}"

    @property
    def mirror_url(self) -> str:
        if self._mirror_url is None:
            return str(self.host.distribution.mirror_url)
        else:
            return self._mirror_url

    @mirror_url.setter
    def mirror_url(self, value: str) -> None:
        url = urllib.parse.urlparse(value)
        if url.scheme not in self._supported_url_schemes:
            raise ValueError(f"Invalid URL scheme '{url.scheme}'")
        self._mirror_url = url.geturl()

    @property
    def remote_url(self) -> str:
        return f"{self.mirror_url}/{self.real_name}"

    @property
    def available(self) -> bool:
        try:
            request = urllib.request.Request(self.remote_url, method="HEAD")
            resource = urllib.request.urlopen(request)  # nosec: see above
            return resource.getcode() == 200  # type: ignore
        except urllib.error.URLError:
            pass
        return False

    @property
    def fetched(self) -> bool:
        if self.exists is False:
            return False

        root_dir_index = os.listdir(self.root_dataset.mountpoint)

        for expected_directory in ["dev", "var", "etc"]:
            if expected_directory not in root_dir_index:
                return False

        return True

    @property
    def newer_than_host(self):
        host_release_name = self._pad_release_name(self.host.release_version)
        release_name = self._pad_release_name(self.name)

        host_is_current = host_release_name.startswith("CURRENT")
        release_is_current = release_name.startswith("CURRENT")

        if release_is_current is True:
            if host_is_current is False:
                return True
            else:
                return False

        cropped_release_name = release_name[:len(host_release_name)]
        return (host_release_name < cropped_release_name)

    def _pad_release_name(self, release_name: str, digits: int=4) -> str:
        """
        pads releases with 0 until it has 4 characters before the first .
        """
        try:
            major_version = int(release_name.split("-")[0].split(".")[0])
            padding = str("0" * (digits - len(str(major_version))))
            return padding + release_name
        except (KeyError, AttributeError, ValueError):
            return release_name

    @property
    def zfs_pool(self) -> libzfs.ZFSPool:
        try:
            root_pool = self.root_dataset.pool  # type: libzfs.ZFSPool
            return root_pool
        except AttributeError:
            pool = self.host.datasets.releases.pool  # type: libzfs.ZFSPool
            return pool

    @property
    def hashes(self):
        if not self._hashes:
            if not os.path.isfile(self.__get_hashfile_location()):
                self.logger.spam("hashes have not yet been downloaded")
                self._fetch_hashes()
            self._hashes = self.read_hashes()

        return self._hashes

    @property
    def _supported_url_schemes(self) -> typing.List[str]:
        return ["https", "http", "ftp"]

    @property
    def release_updates_dir(self) -> str:
        return f"{self.dataset.mountpoint}/updates"

    @property
    def hbds_release_branch(self):

        if self._hbsd_release_branch is not None:
            return self._hbsd_release_branch

        if self.fetched is False:
            raise iocage.lib.errors.ReleaseNotFetched(
                name=self.name,
                logger=self.logger
            )

        root_dataset_mountpoint = self.root_dataset.mountpoint
        source_file = f"{root_dataset_mountpoint}/etc/hbsd-update.conf"

        if not os.path.isfile(source_file):
            raise iocage.lib.errors.ReleaseUpdateBranchLookup(
                release_name=self.name,
                reason=f"{source_file} not found",
                logger=self.logger
            )

        with open(source_file, "r") as f:
            hbsd_update_conf = ucl.load(f.read())
            self._hbsd_release_branch = hbsd_update_conf["branch"]
            return self._hbsd_release_branch

    def fetch(
        self,
        update: typing.Optional[bool]=None,
        fetch_updates: typing.Optional[bool]=None
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        release_changed = False

        events = iocage.lib.events
        fetchReleaseEvent = events.FetchRelease(self)
        releasePrepareStorageEvent = events.ReleasePrepareStorage(self)
        releaseDownloadEvent = events.ReleaseDownload(self)
        releaseExtractionEvent = events.ReleaseExtraction(self)
        releaseConfigurationEvent = events.ReleaseConfiguration(self)
        releaseCopyBaseEvent = events.ReleaseCopyBase(self)

        if self.fetched is False:

            yield fetchReleaseEvent.begin()
            yield releasePrepareStorageEvent.begin()

            # ToDo: allow to reach this for forced re-fetch
            self.create_resource()
            self._ensure_dataset_mounted()

            yield releasePrepareStorageEvent.end()
            yield releaseDownloadEvent.begin()

            self._fetch_assets()

            yield releaseDownloadEvent.end()
            yield releaseExtractionEvent.begin()

            try:
                self._extract_assets()
            except Exception as e:
                yield releaseExtractionEvent.fail(e)
                raise

            yield releaseExtractionEvent.end()
            release_changed = True

            yield fetchReleaseEvent.end()

        else:

            yield fetchReleaseEvent.skip(
                message="already downloaded"
            )

            self.logger.verbose(
                "Release was already downloaded. Skipping download."
            )

        yield releaseConfigurationEvent.begin()
        rc_conf_changed = False
        if self._set_default_rc_conf() is True:
            rc_conf_changed = True
            release_changed = True
        if (self._set_default_sysctl_conf() or rc_conf_changed) is True:
            yield releaseConfigurationEvent.end()
        else:
            yield releaseConfigurationEvent.skip()

        if fetch_updates is True:
            for event in ReleaseGenerator.fetch_updates(self):
                yield event

        if update is True:
            for event in ReleaseGenerator.update(self):
                if isinstance(event, iocage.lib.events.IocageEvent):
                    yield event
                else:
                    # the only non-IocageEvent is our return value
                    release_changed = event

        if release_changed is True:
            yield releaseCopyBaseEvent.begin()
            self.update_base_release()
            yield releaseCopyBaseEvent.end()
        else:
            yield releaseCopyBaseEvent.skip(message="release unchanged")

        self._cleanup()

    def _copy_to_base_release(self) -> None:
        iocage.lib.helpers.exec(
            [
                "rsync",
                "-a",
                "--delete",
                f"{self.root_dataset.mountpoint}/",
                f"{self.base_dataset.mountpoint}"
            ],
            logger=self.logger
        )

    @property
    def _base_resource(self) -> ReleaseResource:
        return ReleaseResource(
            release=self.release,
            logger=self.logger,
            host=self.host,
            zfs=self.zfs
        )
        # ToDo: Memoize ReleaseResource

    def fetch_updates(
        self
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        events = iocage.lib.events
        releaseUpdateDownloadEvent = events.ReleaseUpdateDownload(self)
        yield releaseUpdateDownloadEvent.begin()

        if self.host.distribution.name == "HardenedBSD":
            update_name = "hbsd-update"
            update_script_name = "hbsd-update"
            update_conf_name = "hbsd-update.conf"
            release_updates_dir = "/var/db/hbsd-update/updates"
        else:
            update_name = "freebsd-update"
            update_script_name = "freebsd-update.sh"
            update_conf_name = "freebsd-update.conf"
            release_updates_dir = "/var/db/freebsd-update/updates"

        files = {
            update_script_name: f"usr.sbin/{update_name}/{update_script_name}",
            update_conf_name: f"etc/{update_conf_name}",
        }

        release_update_download_dir = f"{release_updates_dir}"
        if os.path.isdir(release_update_download_dir):
            self.logger.verbose(
                f"Deleting existing updates in {release_update_download_dir}"
            )
            shutil.rmtree(release_update_download_dir)
        os.makedirs(release_update_download_dir)

        for key in files.keys():

            remote_path = files[key]
            url = self.host.distribution.get_release_trunk_file_url(
                release=self,
                filename=remote_path
            )

            local_path = f"{release_updates_dir}/{key}"
            if os.path.isfile(local_path):
                os.remove(local_path)

            self.logger.verbose(f"Downloading {url}")
            urllib.request.urlretrieve(url, local_path)  # nosec: url validated

            if key == update_script_name:
                os.chmod(local_path, 0o744)

            elif key == update_conf_name:

                if self.host.distribution.name == "FreeBSD":
                    with open(local_path, "r+") as f:
                        content = f.read()
                        pattern = re.compile("^Components .+$", re.MULTILINE)
                        f.seek(0)
                        f.write(pattern.sub(
                            "Components world",
                            content
                        ))
                        f.truncate()

                os.chmod(local_path, 0o644)

            self.logger.debug(
                f"Update-asset {key} for release '{self.name}'"
                f" saved to {local_path}"
            )

        self.logger.verbose(f"Fetching updates for release '{self.name}'")
        if self.host.distribution.name == "HardenedBSD":
            """
            Updates in Hardened BSD are directly executed in a jail, so that we
            do not need to pre-fetch the updates
            """
            print("NOOP")
            # iocage.lib.helpers.exec([
            #     f"{self.release_updates_dir}/{update_script_name}",
            #     "--not-running-from-cron",
            #     "-d",
            #     release_update_download_dir,
            #     "--currently-running",
            #     self.name,
            #     "-f",
            #     f"{self.release_updates_dir}/{update_conf_name}",
            #     "--not-running-from-cron",
            #     "fetch"
            #     # TODO: !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            #     update_script_path,
            #     "-c",
            #     update_conf_path,
            #     "-j",
            #     jail.identifier,
            #     "-V",
            #     "-t",
            #     "/var/db/hbsd-update"
            # ], logger=self.logger)

        else:
            iocage.lib.helpers.exec([
                f"{self.release_updates_dir}/{update_script_name}",
                "--not-running-from-cron",
                "-d",
                release_update_download_dir,
                "--currently-running",
                self.name,
                "-f",
                f"{self.release_updates_dir}/{update_conf_name}",
                "--not-running-from-cron",
                "fetch"
            ], logger=self.logger)

        yield releaseUpdateDownloadEvent.end()

    def update(
        self
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        dataset = self.dataset
        snapshot_name = self._append_datetime(f"{dataset.name}@pre-update")

        runReleaseUpdateEvent = iocage.lib.events.RunReleaseUpdate(self)
        yield runReleaseUpdateEvent.begin()

        # create snapshot before the changes
        dataset.snapshot(snapshot_name, recursive=True)

        jail = iocage.lib.Jail.JailGenerator(
            {
                "name": self.name.replace(".", "-"),
                "basejail": False,
                "allow_mount_nullfs": "1",
                "release": self.name,
                "securelevel": "0",
                "vnet": False,
                "ip4_addr": None,
                "ip6_addr": None,
                "defaultrouter": None
            },
            new=True,
            logger=self.logger,
            zfs=self.zfs,
            host=self.host,
            dataset=self.dataset
        )

        changed = False

        try:
            if self.host.distribution.name == "HardenedBSD":
                for event in self._update_hbsd_jail(jail):
                    if isinstance(event, iocage.lib.events.IocageEvent):
                        yield event
                    else:
                        changed = event
            else:
                for event in self._update_freebsd_jail(jail):
                    if isinstance(event, iocage.lib.events.IocageEvent):
                        yield event
                    else:
                        changed = event
            jail.stop()
            yield runReleaseUpdateEvent.end()
        except Exception as e:
            # kill the helper jail and roll back if anything went wrong
            self.logger.verbose(
                "There was an error updating the Jail - reverting the changes"
            )
            jail.stop(force=True)
            self.zfs.get_snapshot(snapshot_name).rollback(force=True)
            yield runReleaseUpdateEvent.fail(e)
            raise e

        yield changed

    def snapshot(
        self,
        identifier: str,
        force: bool=False
    ) -> libzfs.ZFSSnapshot:
        """
        Returns a ZFS snapshot of the release

        Args:

            identifier:
                This string specifies the snapshots name

            force: (default=False)
                Enabling this option forces re-creation of a snapshot in case
                it already exists for the given idenfifier

        Returns:

            libzfs.ZFSSnapshot: The ZFS snapshot object found or created
        """

        snapshot_name = f"{self.dataset.name}@{identifier}"
        existing_snapshot: typing.Optional[libzfs.ZFSSnapshot] = None
        try:
            existing_snapshot = self.zfs.get_snapshot(snapshot_name)
            if (force is False) and (existing_snapshot is not None):
                self.logger.verbose(
                    f"Re-using release snapshot {self.name}@{identifier}"
                )
                return existing_snapshot
        except libzfs.ZFSException:
            existing_snapshot = None
            pass

        if existing_snapshot is not None:
            self.logger.verbose(
                f"Deleting release snapshot {self.name}@{identifier}"
            )
            existing_snapshot.delete()
            existing_snapshot = None

        self.dataset.snapshot(snapshot_name)
        snapshot: libzfs.ZFSSnapshot = self.zfs.get_snapshot(snapshot_name)
        return snapshot

    def _update_hbsd_jail(
        self,
        jail: 'iocage.lib.Jail.JailGenerator'
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        events = iocage.lib.events
        executeReleaseUpdateEvent = events.ExecuteReleaseUpdate(self)

        for event in jail.start():
            yield event

        yield executeReleaseUpdateEvent.begin()

        update_script_path = f"{self.release_updates_dir}/hbsd-update"
        update_conf_path = f"{self.release_updates_dir}/hbsd-update.conf"

        try:

            # ToDo: as bad as print() replace passthru with a nice progress bar
            stdout = iocage.lib.helpers.exec_iter([
                update_script_path,
                "-c",
                update_conf_path,
                "-j",
                jail.identifier,
                "-V",
                "-D",  # nodownload=1
                "-t",
                "/var/db/hbsd-update/updates"
            ], logger=self.logger)

            for stdout_line in stdout:
                self.logger.verbose(stdout_line.strip("\n"), indent=1)

            self.logger.debug(f"Update of release '{self.name}' finished")

        except Exception:

            raise iocage.lib.errors.ReleaseUpdateFailure(
                release_name=self.name,
                reason=(
                    "hbsd-update failed"
                ),
                logger=self.logger
            )

        yield executeReleaseUpdateEvent.end()

        for event in jail.stop():
            yield event

        self.logger.verbose(f"Release '{self.name}' updated")
        yield True  # ToDo: yield False if nothing was updated

    def _update_freebsd_jail(
        self,
        jail: 'iocage.lib.Jail.JailGenerator'
    ) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

        events = iocage.lib.events
        executeReleaseUpdateEvent = events.ExecuteReleaseUpdate(self)

        local_update_mountpoint = f"{self.root_dir}/var/db/freebsd-update"
        if not os.path.isdir(local_update_mountpoint):
            self.logger.spam(
                "Creating mountpoint {local_update_mountpoint}"
            )
            os.makedirs(local_update_mountpoint)

        jail.fstab.new_line(
            source=self.release_updates_dir,
            destination=local_update_mountpoint,
            fs_type="nullfs",
            options="rw"
        )
        jail.fstab.save()

        for event in jail.start():
            yield event

        yield executeReleaseUpdateEvent.begin()
        child, stdout, stderr = jail.exec([
            "/var/db/freebsd-update/freebsd-update.sh",
            "--not-running-from-cron",
            "-d",
            "/var/db/freebsd-update",
            "--currently-running",
            self.name,
            "-r",
            self.name,
            "-f",
            "/var/db/freebsd-update/freebsd-update.conf",
            "install"
        ], ignore_error=True)

        if child.returncode != 0:
            if "No updates are available to install." in stdout:
                yield executeReleaseUpdateEvent.skip(
                    message="already up to date"
                )
                self.logger.debug("Already up to date")
            else:
                yield executeReleaseUpdateEvent.fail()
                raise iocage.lib.errors.ReleaseUpdateFailure(
                    release_name=self.name,
                    reason=(
                        "freebsd-update.sh exited "
                        f"with returncode {child.returncode}"
                    ),
                    logger=self.logger
                )
        else:
            yield executeReleaseUpdateEvent.end()
            self.logger.debug(f"Update of release '{self.name}' finished")

        for event in jail.stop():
            yield event

        self.logger.verbose(f"Release '{self.name}' updated")
        yield True  # ToDo: return False if nothing was updated

    def _append_datetime(self, text: str) -> str:
        now = datetime.datetime.utcnow()
        text += now.strftime("%Y%m%d%H%I%S.%f")
        return text

    def _ensure_dataset_mounted(self) -> None:
        if not self.dataset.mountpoint:
            self.dataset.mount()

    def _fetch_hashes(self) -> None:
        url = f"{self.remote_url}/{self.host.distribution.hash_file}"
        path = self.__get_hashfile_location()
        self.logger.verbose(f"Downloading hashes from {url}")
        urllib.request.urlretrieve(url, path)  # nosec: validated in @setter
        self.logger.debug(f"Hashes downloaded to {path}")

    def _fetch_assets(self) -> None:
        for asset in self.assets:
            url = f"{self.remote_url}/{asset}.txz"
            path = self._get_asset_location(asset)

            if os.path.isfile(path):
                self.logger.verbose(f"{path} already exists - skipping.")
                return
            else:
                self.logger.debug(f"Starting download of {url}")
                urllib.request.urlretrieve(url, path)  # nosec: validated
                self.logger.verbose(f"{url} was saved to {path}")

    def read_hashes(self) -> typing.Dict[str, str]:
        # yes, this can read HardenedBSD and FreeBSD hash files
        path = self.__get_hashfile_location()
        hashes = {}
        with open(path, "r") as f:
            for line in f.read().split("\n"):
                s = set(line.replace("\t", " ").split(" "))
                fingerprint = None
                asset = None
                for x in s:
                    x = x.strip("()")
                    if len(x) == 64:
                        fingerprint = x
                    elif x.endswith(".txz"):
                        asset = x[:-4]
                if asset and fingerprint:
                    hashes[asset] = fingerprint
        count = len(hashes)
        self.logger.spam(f"{count} hashes read from {path}")
        return hashes

    def __get_hashfile_location(self) -> str:
        hash_file = self.host.distribution.hash_file
        return f"{self.download_directory}/{hash_file}"

    def _get_asset_location(self, asset_name) -> str:
        return f"{self.download_directory}/{asset_name}.txz"

    def _extract_assets(self) -> None:

        for asset in self.assets:

            if self.check_hashes:
                self._check_asset_hash(asset)

            with tarfile.open(self._get_asset_location(asset)) as f:

                self.logger.verbose(f"Verifying file structure in {asset}")
                self._check_tar_files(f.getmembers(), asset_name=asset)

                self.logger.debug(f"Extracting {asset}")
                f.extractall(self.root_dir)
                self.logger.verbose(
                    f"Asset {asset} was extracted to {self.root_dir}"
                )

    def _set_default_rc_conf(self) -> bool:

        for key, value in self.DEFAULT_RC_CONF.items():
            self.rc_conf[key] = value

        return self.rc_conf.save() is True

    def _set_default_sysctl_conf(self) -> bool:

        for key, value in self.DEFAULT_SYSCTL_CONF.items():
            self.sysctl_conf[key] = value

        return self.sysctl_conf.save() is True

    def _update_name_from_dataset(self) -> None:
        if self.dataset is not None:
            self.name = self.dataset.name.split("/")[-2:-1]

    def update_base_release(self) -> None:

        base_dataset = self.zfs.get_or_create_dataset(self.base_dataset_name)

        basedirs = iocage.lib.helpers.get_basedir_list(
            distribution_name=self.host.distribution.name
        )

        for folder in basedirs:
            self.zfs.get_or_create_dataset(f"{base_dataset.name}/{folder}")

        self._copy_to_base_release()

        self.logger.debug(f"Base release '{self.name}' updated")

    def _cleanup(self) -> None:
        for asset in self.assets:
            asset_location = self._get_asset_location(asset)
            if os.path.isfile(asset_location):
                os.remove(asset_location)

    def _check_asset_hash(self, asset_name: str) -> None:
        local_file_hash = self._read_asset_hash(asset_name)
        expected_hash = self.hashes[asset_name]

        has_valid_hash = local_file_hash == expected_hash
        if not has_valid_hash:
            self.logger.warn(
                f"Asset {asset_name}.txz has an invalid signature"
                f"(was '{local_file_hash}' but expected '{expected_hash}')"
            )
            raise iocage.lib.errors.InvalidReleaseAssetSignature(
                release_name=self.name,
                asset_name=asset_name,
                logger=self.logger
            )

        self.logger.spam(
            f"Asset {asset_name}.txz has a valid signature ({expected_hash})"
        )

    def _read_asset_hash(self, asset_name: str) -> str:
        asset_location = self._get_asset_location(asset_name)
        sha256 = hashlib.sha256()
        with open(asset_location, 'rb') as f:
            for block in iter(lambda: f.read(65536), b''):
                sha256.update(block)
        return sha256.hexdigest()

    def _check_tar_files(self, tar_infos, asset_name: str) -> None:
        for i in tar_infos:
            self._check_tar_info(i, asset_name)

    def _check_tar_info(self, tar_info: typing.Any, asset_name: str) -> None:
        if tar_info.name == ".":
            return
        if not tar_info.name.startswith("./"):
            reason = "Names in txz files must be relative and begin with './'"
        elif ".." in tar_info.name:
            reason = "Names in txz files must not contain '..'"
        else:
            return

        raise iocage.lib.errors.IllegalReleaseAssetContent(
            release_name=self.name,
            asset_name=asset_name,
            reason=reason,
            logger=self.logger
        )

    def __str__(self) -> str:
        return self.name

    def destroy(self, force: bool=False) -> None:
        self.zfs.delete_dataset_recursive(self.dataset)


class Release(ReleaseGenerator):

    def fetch(  # noqa: T484
        self,
        update: typing.Optional[bool]=None,
        fetch_updates: typing.Optional[bool]=None
    ) -> typing.List['iocage.lib.events.IocageEvent']:

        return list(ReleaseGenerator.fetch(
            self,
            update=update,
            fetch_updates=fetch_updates
        ))

    def update(  # noqa: T484
        self
    ) -> typing.List['iocage.lib.events.IocageEvent']:

        return list(ReleaseGenerator.update(self))
