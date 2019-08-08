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
"""ioc release module."""
import typing
import hashlib
import os
import urllib.request
import urllib.error
import urllib.parse
import re

import libzfs

import libioc.ZFS
import libioc.errors
import libioc.helpers
import libioc.helpers_object
import libioc.events
import libioc.LaunchableResource
import libioc.ResourceSelector
import libioc.Jail
import libioc.SecureTarfile

# MyPy
import libioc.Resource
import libioc.Host
import libioc.Logger
import libioc.Config.Host
import libioc.Config.Jail.File.RCConf
import libioc.Config.Jail.File.SysctlConf


class ReleaseResource(libioc.LaunchableResource.LaunchableResource):
    """Resource that represents an iocage release."""

    _release: typing.Optional['ReleaseGenerator']
    _hashes: typing.Optional[typing.Dict[str, str]]
    host: libioc.Host.HostGenerator
    root_datasets_name: typing.Optional[str]

    def __init__(
        self,
        dataset: typing.Optional[libzfs.ZFSDataset]=None,
        dataset_name: typing.Optional[str]=None,
        config_type: str="auto",
        config_file: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        zfs: typing.Optional[libioc.ZFS.ZFS]=None,
        host: typing.Optional['libioc.Host.HostGenerator']=None,
        release: typing.Optional['ReleaseGenerator']=None,
        root_datasets_name: typing.Optional[str]=None,
    ) -> None:

        self.host = libioc.helpers_object.init_host(self, host)
        self.root_datasets_name = root_datasets_name

        libioc.LaunchableResource.LaunchableResource.__init__(
            self,
            dataset=dataset,
            dataset_name=dataset_name,
            config_type=config_type,
            config_file=config_file,
            logger=logger,
            zfs=zfs
        )

        self._release = release
        self._hashes = None

    @property
    def release(self) -> 'ReleaseGenerator':
        """
        Return the release instance that belongs to the resource.

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
    def full_name(self) -> str:
        """
        Return the full identifier of a jail.

        When more than one root dataset is managed by iocage, the full source
        and name are returned. Otherwise just the name.

        For example `mydataset/jailname` or just `jailname`.
        """
        if len(self.host.datasets) > 1:
            return f"{self.source}/{self.name}"
        else:
            return str(self.name)

    @property
    def dataset_name(self) -> str:
        """
        Return the name of the releases ZFS dataset.

        If the resource has no dataset or dataset_name assigned yet,
        the release id is used to find name the dataset
        """
        try:
            return str(self._assigned_dataset_name)
        except AttributeError:
            pass

        return self._dataset_name_from_release_name

    @dataset_name.setter
    def dataset_name(self, value: str) -> None:
        """Set the releases dataset name."""
        self._dataset_name = value

    @property
    def base_dataset(self) -> libzfs.ZFSDataset:
        """
        Return the ZFS basejail dataset belonging to the release.

        base datasets are created from releases. They are required to start
        zfs-basejails.
        """
        ds: libzfs.ZFSDataset = self.zfs.get_dataset(self.base_dataset_name)
        return ds

    @property
    def base_dataset_name(self) -> str:
        """Return the ZFS basejail datasets name belonging to the release."""
        return f"{self._dataset_name_from_base_name}/root"

    @property
    def _dataset_name_from_release_name(self) -> str:
        return f"{self.source_dataset.releases.name}/{self.name}"

    @property
    def _dataset_name_from_base_name(self) -> str:
        return f"{self.source_dataset.base.name}/{self.name}"

    @property
    def source_dataset(self) -> 'libioc.Datasets.RootDatasets':
        """
        Return the releases source root dataset.

        iocage can manage multiple source datasets (on different ZFS pools
        for instance). This property returns the RootDatasets instance that
        belongs to the release.
        """
        try:
            assigned_name = str(self._assigned_dataset_name)
            return self.host.datasets.find_root_datasets(assigned_name)
        except AttributeError:
            pass

        if self.root_datasets_name is None:
            return self.host.datasets.main
        else:
            try:
                return self.host.datasets.__getitem__(self.root_datasets_name)
            except KeyError:
                raise libioc.errors.SourceNotFound(logger=self.logger)

    @property
    def source(self) -> str:
        """Return the name of the releases source root datasets."""
        try:
            assigned_name = str(self._assigned_dataset_name)
            return str(
                self.host.datasets.find_root_datasets_name(assigned_name)
            )
        except AttributeError:
            pass

        if self.root_datasets_name is None:
            return str(self.host.datasets.main_datasets_name)
        else:
            return str(self.root_datasets_name)


class ReleaseGenerator(ReleaseResource):
    """Release with generator interfaces."""

    DEFAULT_RC_CONF: typing.Dict[str, typing.Union[str, bool]] = {
        "netif_enable": False,
        "sendmail_enable": False,
        "sendmail_submit_enable": False,
        "sendmail_msp_queue_enable": False,
        "sendmail_outbound_enable": False,
        "cron_flags": "-m ''",
        "syslogd_flags": "-ss"
    }

    DEFAULT_PERIODIC_CONF: typing.Dict[str, typing.Union[str, bool]] = {
        "daily_clean_hoststat_enable": False,
        "daily_status_mail_rejects_enable": False,
        "daily_status_include_submit_mailq": False,
        "daily_submit_queuerun": False,
    }

    DEFAULT_SYSCTL_CONF: typing.Dict[str, int] = {
        "net.inet.ip.fw.enable": 0
    }

    _name: str
    patchlevel: typing.Optional[int]
    check_eol: bool

    logger: 'libioc.Logger.Logger'
    zfs: libioc.ZFS.ZFS
    host: 'libioc.Host.HostGenerator'
    _resource: libioc.Resource.Resource
    _assets: typing.List[str]
    _mirror_url: typing.Optional[str]

    def __init__(
        self,
        name: str,
        dataset: typing.Optional[libzfs.ZFSDataset]=None,
        dataset_name: typing.Optional[str]=None,
        config_type: str="auto",
        config_file: typing.Optional[str]=None,
        root_datasets_name: typing.Optional[str]=None,
        host: typing.Optional['libioc.Host.HostGenerator']=None,
        zfs: typing.Optional[libioc.ZFS.ZFS]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        check_hashes: bool=True,
        check_eol: bool=True,
    ) -> None:
        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)
        self.host = libioc.helpers_object.init_host(self, host)

        resource_selector = libioc.ResourceSelector.ResourceSelector(
            name,
            logger=self.logger
        )
        if resource_selector.source_name is not None:
            is_different = resource_selector.source_name != root_datasets_name
            if (root_datasets_name is not None) and (is_different is True):
                # ToDo: omit root_datasets_name at all ?
                raise libioc.errors.ConflictingResourceSelection(
                    source_a=resource_selector.source_name,
                    source_b=root_datasets_name,
                    logger=self.logger
                )
            else:
                root_datasets_name = resource_selector.source_name

        if libioc.helpers.validate_name(resource_selector.name) is False:
            raise NameError(f"Invalid 'name' for Release: '{name}'")

        self.name = name
        self._hbsd_release_branch = None
        self._mirror_url = None

        self._hashes = None
        self.check_hashes = check_hashes is True
        self.check_eol = check_eol is True

        ReleaseResource.__init__(
            self,
            host=self.host,
            logger=self.logger,
            zfs=self.zfs,
            root_datasets_name=root_datasets_name,
            dataset_name=dataset_name,
            config_type=config_type,
            config_file=config_file,
            release=self
        )

        self._assets = ["base"]
        if self.host.distribution.name != "HardenedBSD":
            self._assets.append("lib32")

    @property
    def name(self) -> str:
        """Return the releases identifier."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set the releases identifier (optionally including patchlevel)."""
        match = re.match((
            r"^(?:(?P<source_dataset_name>.*)/)?"
            r"(?P<release_name>.*?)"
            r"(?:-p(?P<patchlevel>[0-9]+))?$"
        ), value)
        if match is None:
            raise libioc.errors.InvalidReleaseName(
                name=value,
                logger=self.logger
            )
        self._name = match.group("release_name")
        patchlevel = match.group("patchlevel")
        self.patchlevel = None if (patchlevel is None) else int(patchlevel)
        if match.group("source_dataset_name") is not None:
            self.root_datasets_name = match.group("source_dataset_name")

    @property
    def full_name(self) -> str:
        """Return the release name including the patchlevel."""
        if self.patchlevel is None:
            return self._name

        return f"{self._name}-p{self.current_snapshot_patchlevel}"

    @property
    def resource(self) -> 'libioc.Resource.Resource':
        """Return the releases resource."""
        return self._resource

    @resource.setter
    def resource(self, value: 'libioc.Resource.Resource') -> None:
        """Set the releases resource."""
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
        """Return the mountpoint of the iocage/releases dataset."""
        return str(self.source_dataset.releases.mountpoint)

    @property
    def download_directory(self) -> str:
        """Return the download directory."""
        return str(self.dataset.mountpoint)

    @property
    def root_dir(self) -> str:
        """Return the main directory of the release."""
        try:
            if self.root_dataset.mountpoint:
                return str(self.root_dataset.mountpoint)
        except AttributeError:
            pass

        return f"{self.releases_folder}/{self.name}/root"

    @property
    def assets(self) -> typing.List[str]:
        """Return a list of release assets."""
        return self._assets

    @assets.setter
    def assets(self, value: typing.Union[typing.List[str], str]) -> None:
        """Set the list of release assets."""
        value = [value] if isinstance(value, str) else value
        self._assets = list(map(
            lambda x: x if not x.endswith(".txz") else x[:-4],
            value
        ))

    @property
    def real_name(self) -> str:
        """Map the release name on HardenedBSD."""
        if self.host.distribution.name == "HardenedBSD":
            return f"HardenedBSD-{self.name}-{self.host.processor}-LATEST"
        return self.name

    @property
    def annotated_name(self) -> str:
        """
        Return the release name with annotations.

        Annotations inform whether a release is newer then the host or EOL.
        """
        annotations = set()

        if self.eol is True:
            annotations.add("EOL")

        if self.newer_than_host is True:
            annotations.add("Newer than Host")

        if len(annotations) > 0:
            return f"{self.name} ({', '.join(annotations)})"

        return f"{self.name}"

    @property
    def eol(self) -> typing.Optional[bool]:
        """
        Return whether the release is EOL or checks are disabled.

        When check_eol is disabled, None is returned, True when the release
        name was found in the distributions eol_list.
        """
        if not self.check_eol:
            return None

        if self.host.distribution.name == "FreeBSD":
            return (self.name in self.host.distribution.eol_list) is True
        elif self.host.distribution.name == "HardenedBSD":
            if "STABLE" in self.name:
                # stable releases are explicitly in the EOL list or supported
                return (self.name in self.host.distribution.eol_list) is True
            return (self.version_number in map(
                lambda x: self._parse_release_version(x),
                self.host.distribution.eol_list
            )) is True
        return False

    @property
    def current_snapshot_patchlevel(self) -> int:
        """Return the currently chosen patchlevel number or the latest."""
        current_snapshot_name = self.current_snapshot.snapshot_name
        return int(current_snapshot_name.lstrip('p'))

    @property
    def current_snapshot(self) -> libzfs.ZFSSnapshot:
        """Return the manually configured or the latest release snapshot."""
        if self.patchlevel is not None:
            for snapshot in self.version_snapshots:
                if snapshot.snapshot_name == f"p{self.patchlevel}":
                    return snapshot

        return self.latest_snapshot

    @property
    def latest_snapshot(self) -> libzfs.ZFSSnapshot:
        """
        Return or create the latest version snapshot.

        When no snapshot was taken before `p0` is automatically created.
        """
        version_snapshots = self.version_snapshots
        if len(version_snapshots) == 0:
            self.logger.verbose("No release snapshot found - using @p0")
            return self.snapshot("p0")
        else:
            return version_snapshots[0]

    @property
    def version_snapshots(self) -> typing.List['libzfs.ZFSSnapshot']:
        """Return the sorted list of taken version snapshots (e.g. p3)."""
        versions: typing.List[int] = []
        snapshots: typing.Dict[int, 'libzfs.ZFSSnapshot'] = {}
        pattern = re.compile(r"^p(\d+)$")
        for snapshot in self.root_dataset.snapshots:
            match = pattern.match(snapshot.snapshot_name)
            if match is None:
                continue
            patch_level = int(match[1])
            versions.append(patch_level)
            snapshots[patch_level] = snapshot
        return [snapshots[i] for i in reversed(sorted(versions))]

    def _require_release_supported(self) -> None:
        if self.host.distribution.name == "HardenedBSD":
            version = self.release.version_number
            if (version == 0) or (version >= 10.4):
                return
            raise libioc.errors.UnsupportedRelease(
                version=version,
                logger=self.logger
            )

    @property
    def version_number(self) -> float:
        """Return the numeric release version number or 0 for CURRENT."""
        return self._parse_release_version(self.name)

    def _parse_release_version(self, release_version_string: str) -> float:
        _parts = release_version_string.split("-", maxsplit=1)
        parsed_version = _parts[0]
        try:
            version = float(parsed_version)
            if self.host.distribution.name == "HardenedBSD":
                if (len(_parts) == 2) and (_parts[1].upper() == "STABLE"):
                    if (version == 10.0):
                        return 10.4
                    elif (version == 11.0):
                        return 11.1

            return version
        except ValueError:
            return float(0)

    @property
    def mirror_url(self) -> str:
        """Return the distributions release mirror URL."""
        if self._mirror_url is None:
            return str(self.host.distribution.mirror_url)
        else:
            return self._mirror_url

    @mirror_url.setter
    def mirror_url(self, value: str) -> None:
        """Override the default release mirror URL."""
        url = urllib.parse.urlparse(value)
        if url.scheme not in self._supported_url_schemes:
            raise ValueError(f"Invalid URL scheme '{url.scheme}'")
        self._mirror_url = url.geturl()

    @property
    def remote_url(self) -> str:
        """Return the releases full mirror URL."""
        return f"{self.mirror_url}/{self.real_name}"

    @property
    def available(self) -> bool:
        """Return True if the release is available on the remote mirror."""
        try:
            request = urllib.request.Request(self.remote_url, method="HEAD")
            resource = urllib.request.urlopen(request)  # nosec: trusted URL
            return (resource.getcode() == 200) is True  # noqa: T484
        except urllib.error.URLError:
            pass
        return False

    @property
    def fetched(self) -> bool:
        """Return True if the release is fetched locally."""
        if self.exists is False:
            return False

        try:
            root_dir_index = os.listdir(self.root_dataset.mountpoint)
        except libzfs.ZFSException:
            return False

        for expected_directory in ["dev", "var", "etc"]:
            if expected_directory not in root_dir_index:
                return False

        return True

    @property
    def newer_than_host(self) -> bool:
        """Return True if the release is newer than the host."""
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
        """Pad releases with 0 until it has 4 characters before the first."""
        try:
            major_version = int(release_name.split("-")[0].split(".")[0])
            padding = str("0" * (digits - len(str(major_version))))
            return padding + release_name
        except (KeyError, AttributeError, ValueError):
            return release_name

    @property
    def zfs_pool(self) -> libzfs.ZFSPool:
        """Return the releases ZFS pool."""
        try:
            root_pool = self.root_dataset.pool  # type: libzfs.ZFSPool
            return root_pool
        except AttributeError:
            pool = self.host.datasets.releases.pool  # type: libzfs.ZFSPool
            return pool

    @property
    def hashes(self) -> typing.Dict[str, str]:
        """Return the releases asset hashes."""
        if self._hashes is None:
            if not os.path.isfile(self.__get_hashfile_location()):
                self.logger.spam("hashes have not yet been downloaded")
                self._fetch_hashes()
            self._hashes = self.read_hashes()

        if isinstance(self._hashes, dict):
            return self._hashes

        raise libioc.errors.ReleaseAssetHashesUnavailable(
            logger=self.logger
        )

    @property
    def _supported_url_schemes(self) -> typing.List[str]:
        return ["https", "http", "ftp"]

    @property
    def hbds_release_branch(self) -> str:
        """Translate the release into a HardenedBSD release git branch name."""
        if self._hbsd_release_branch is not None:
            return self._hbsd_release_branch

        if self.fetched is False:
            raise libioc.errors.ReleaseNotFetched(
                name=self.name,
                logger=self.logger
            )

        root_dataset_mountpoint = self.root_dataset.mountpoint
        source_file = f"{root_dataset_mountpoint}/etc/hbsd-update.conf"

        if not os.path.isfile(source_file):
            raise libioc.errors.ReleaseUpdateBranchLookup(
                release_name=self.name,
                reason=f"{source_file} not found",
                logger=self.logger
            )

        libioc.helpers.require_no_symlink(source_file, logger=self.logger)

        with open(source_file, "r", encoding="utf-8") as f:
            import ucl
            hbsd_update_conf = ucl.load(f.read())
            self._hbsd_release_branch = hbsd_update_conf["branch"]
            return str(self._hbsd_release_branch)

    def fetch(
        self,
        update: bool=False,
        fetch_updates: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None,
        update_base: typing.Optional[bool]=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """
        Fetch the release from the remote.

        Args:

            update (bool): (default=False)

                When enabled, updates are applied to the release,
                unless fetching updates was without success.

            fetch_updates (bool): (default=False)

                When enabled, updates are fetched.
                Disabling this option has no impact on applying updates.

            event_scope (libioc.events.Scope): (optional)

                Pass on the IocEvent stack for use in higher order functions.

            update_base (bool): (optional)

                When unset, the sysrc config `ioc_legacy_support` is taken
                into account to determine whether ZFS basejail datasets should
                be updated in case the release was created or modified.
                Those ZFS basejail datasets are required to start basejails
                created with iocage_legacy.
                A boolean value overrides the configuration from /etc/rc.conf.
        """
        release_changed: typing.Optional[bool] = None
        self._require_release_supported()

        events = libioc.events
        fetchReleaseEvent = events.FetchRelease(
            self,
            scope=event_scope
        )
        _scope = fetchReleaseEvent.scope
        releasePrepareStorageEvent = events.ReleasePrepareStorage(
            self,
            scope=_scope
        )
        releaseDownloadEvent = events.ReleaseDownload(
            self,
            scope=_scope
        )
        releaseExtractionEvent = events.ReleaseExtraction(
            self,
            scope=_scope
        )
        releaseConfigurationEvent = events.ReleaseConfiguration(
            self,
            scope=_scope
        )
        releaseCopyBaseEvent = events.ReleaseCopyBase(
            self,
            scope=_scope
        )

        if self.fetched is False:

            release_changed = False

            yield fetchReleaseEvent.begin()
            yield releasePrepareStorageEvent.begin()

            # ToDo: allow to reach this for forced re-fetch
            self.create_resource()
            self.get_or_create_dataset("root")
            self._ensure_dataset_mounted()

            yield releasePrepareStorageEvent.end()
            yield releaseDownloadEvent.begin()
            try:
                yield from self._fetch_assets(releaseDownloadEvent.scope)
            except Exception:
                yield releaseDownloadEvent.fail()
                raise
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
        try:
            if any([
                    self._set_default_periodic_conf(),
                    self._set_default_rc_conf(),
                    self._set_default_sysctl_conf()
            ]):
                release_changed = True
                yield releaseConfigurationEvent.end()
            else:
                yield releaseConfigurationEvent.skip()
        except Exception as e:
            yield releaseConfigurationEvent.fail(e)
            raise e

        self.snapshot("p0")

        if fetch_updates is True:
            try:
                for event in self.updater.fetch(event_scope=_scope):
                    if isinstance(event, libioc.events.ReleaseUpdateDownload):
                        if (event.done and event.skipped) is True:
                            update = False
                    yield event
            except libioc.errors.IocException:
                update = False

        if update is True:
            for event in self.updater.apply():
                if isinstance(event, libioc.events.IocEvent):
                    yield event
                else:
                    # the only non-IocEvent is our return value
                    release_changed = event

        yield releaseCopyBaseEvent.begin()
        if update_base is True:
            _update_base = True
        elif update_base is None:
            # if not specified, lookup global host configuration
            legacy_support_key = "ioc_legacy_support"
            rc_conf = libioc.Config.Host.rc_conf
            if legacy_support_key in rc_conf:
                _update_base = (rc_conf[legacy_support_key] is True)
            else:
                _update_base = False
        else:
            _update_base = False

        if _update_base is True:
            if release_changed is False:
                yield releaseCopyBaseEvent.skip(message="release unchanged")
            self.update_base_release()
            yield releaseCopyBaseEvent.end()
        else:
            yield releaseCopyBaseEvent.skip(
                message="legacy basejal support disabled"
            )

        self._cleanup()

    def _copy_to_base_release(self) -> None:
        libioc.helpers.exec(
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

    def snapshot(
        self,
        identifier: str,
        force: bool=False
    ) -> libzfs.ZFSSnapshot:
        """
        Create a ZFS snapshot of the release.

        Args:
            identifier:
                This string specifies the snapshots name

            force: (default=False)
                Enabling this option forces re-creation of a snapshot in case
                it already exists for the given identifier

        Returns:
            libzfs.ZFSSnapshot: The ZFS snapshot object found or created

        """
        snapshot_name = f"{self.root_dataset.name}@{identifier}"
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

        self.root_dataset.snapshot(snapshot_name)
        snapshot: libzfs.ZFSSnapshot = self.zfs.get_snapshot(snapshot_name)
        return snapshot

    def _ensure_dataset_mounted(self) -> None:
        if not self.dataset.mountpoint:
            self.dataset.mount()

    def _fetch_hashes(self) -> None:
        url = f"{self.remote_url}/{self.host.distribution.hash_file}"
        path = self.__get_hashfile_location()
        self.logger.verbose(f"Downloading hashes from {url}")
        urllib.request.urlretrieve(url, path)  # nosec: validated in @setter
        self.logger.debug(f"Hashes downloaded to {path}")

    def _fetch_assets(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None,
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        for asset in self.assets:

            releaseAssetDownloadEvent = libioc.events.ReleaseAssetDownload(
                release=self,
                scope=event_scope
            )
            yield releaseAssetDownloadEvent.begin()
            url = f"{self.remote_url}/{asset}.txz"
            path = self._get_asset_location(asset)

            if os.path.isfile(path):
                yield releaseAssetDownloadEvent.skip("{path} already exists")
            else:
                try:
                    self.logger.debug(f"Starting download of {url}")
                    urllib.request.urlretrieve(url, path)  # nosec: validated
                    self.logger.verbose(f"{url} was saved to {path}")
                    yield releaseAssetDownloadEvent.end()
                except urllib.error.HTTPError as http_error:
                    yield releaseAssetDownloadEvent.fail()
                    raise libioc.errors.DownloadFailed(
                        url=url,
                        code=http_error.code,
                        logger=self.logger
                    )

    def read_hashes(self) -> typing.Dict[str, str]:
        """Read the release asset hashes."""
        # yes, this can read HardenedBSD and FreeBSD hash files
        path = self.__get_hashfile_location()
        hashes = {}
        with open(path, "r", encoding="utf-8") as f:
            for line in f.read().splitlines():
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

    def _get_asset_location(self, asset_name: str) -> str:
        return f"{self.download_directory}/{asset_name}.txz"

    def _extract_assets(self) -> None:

        for asset in self.assets:

            if self.check_hashes:
                self._check_asset_hash(asset)

            libioc.SecureTarfile.extract(
                file=self._get_asset_location(asset),
                compression_format="xz",
                destination=self.root_dir,
                logger=self.logger
            )

    def _set_default_rc_conf(self) -> bool:

        for key, value in self.DEFAULT_RC_CONF.items():
            self.rc_conf[key] = value

        return self.rc_conf.save() is True

    def _set_default_periodic_conf(self) -> bool:

        for key, value in self.DEFAULT_PERIODIC_CONF.items():
            self.periodic_conf[key] = value

        return self.periodic_conf.save() is True

    def _set_default_sysctl_conf(self) -> bool:

        for key, value in self.DEFAULT_SYSCTL_CONF.items():
            self.sysctl_conf[key] = value

        return self.sysctl_conf.save() is True

    def _update_name_from_dataset(self) -> None:
        if self.dataset is not None:
            self.name = self.dataset.name.split("/")[-2:-1]

    def update_base_release(self) -> None:
        """Update the ZFS basejail release dataset."""
        base_dataset = self.zfs.get_or_create_dataset(self.base_dataset_name)

        basedirs = libioc.helpers.get_basedir_list(
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
            raise libioc.errors.InvalidReleaseAssetSignature(
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
        with open(asset_location, "rb") as f:
            for block in iter(lambda: f.read(65536), b''):
                sha256.update(block)
        return sha256.hexdigest()

    def __str__(self) -> str:
        """Return the release name."""
        if self.patchlevel is None:
            return self.name
        else:
            return f"{self.name}-p{self.patchlevel}"

    def destroy(
        self,
        force: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.IocEvent', None, None]:
        """Delete a release."""
        zfsDatasetDestroyEvent = libioc.events.ZFSDatasetDestroy(
            dataset=self.dataset,
            scope=event_scope
        )
        yield zfsDatasetDestroyEvent.begin()
        try:
            self.zfs.delete_dataset_recursive(self.dataset)
        except Exception as e:
            zfsDatasetDestroyEvent.fail(e)
            raise e
        yield zfsDatasetDestroyEvent.end()


class Release(ReleaseGenerator):
    """Release with synchronous interfaces."""

    def fetch(  # noqa: T484
        self,
        update: bool=False,
        fetch_updates: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.List['libioc.events.IocEvent']:
        """Fetch the release from the remote synchronously."""
        return list(ReleaseGenerator.fetch(
            self,
            update=update,
            fetch_updates=fetch_updates,
            event_scope=event_scope
        ))

    def destroy(  # noqa: T484
        self,
        force: bool=False,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.List['libioc.events.IocEvent']:
        """Delete a release."""
        return list(ReleaseGenerator.destroy(
            self,
            force=force,
            event_scope=event_scope
        ))

