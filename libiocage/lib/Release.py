import datetime
import hashlib
import os
import shutil
import tarfile
import urllib.request
import uuid
from urllib.parse import urlparse

import libzfs
import ucl

import libiocage.lib.Jail
import libiocage.lib.errors
import libiocage.lib.helpers
import libiocage.lib.events


class ReleaseGenerator:
    DEFAULT_RC_CONF_SERVICES = {
        "netif"             : False,
        "sendmail"          : False,
        "sendmail_submit"   : False,
        "sendmail_msp_queue": False,
        "sendmail_outbound" : False
    }

    def __init__(self, name=None,
                 dataset=None,
                 host=None,
                 zfs=None,
                 logger=None,
                 check_hashes=True,
                 eol=False):

        libiocage.lib.helpers.init_logger(self, logger)
        libiocage.lib.helpers.init_zfs(self, zfs)
        libiocage.lib.helpers.init_host(self, host)

        if not libiocage.lib.helpers.validate_name(name):
            raise NameError(f"Invalid 'name' for Release: '{name}'")

        self.name = name
        self.eol = eol
        self._hashes = None
        self._dataset = None
        self._root_dataset = None
        self.dataset = dataset
        self.check_hashes = check_hashes is True
        self._hbsd_release_branch = None

        self._assets = ["base"]
        if self.host.distribution.name != "HardenedBSD":
            self._assets.append("lib32")

    @property
    def dataset(self):
        if self._dataset is None:
            self._dataset = self.zfs.get_dataset(self.dataset_name)
        return self._dataset

    @dataset.setter
    def dataset(self, value):
        if isinstance(value, libzfs.ZFSDataset):
            try:
                value.mountpoint
            except:
                value.mount()

            self._dataset = value
            self._update_name_from_dataset()

        else:
            self._zfs = None

    @property
    def root_dataset(self):
        if self._root_dataset is None:
            try:
                ds = self.zfs.get_dataset(self.root_dataset_name)
            except:
                self.host.datasets.releases.pool.create(
                    self.root_dataset_name,
                    {},
                    create_ancestors=True
                )
                ds = self.zfs.get_dataset(self.root_dataset_name)
                ds.mount()
            self._root_dataset = ds

        return self._root_dataset

    @property
    def dataset_name(self):
        return f"{self.host.datasets.releases.name}/{self.name}"

    @property
    def root_dataset_name(self):
        return f"{self.host.datasets.releases.name}/{self.name}/root"

    @property
    def releases_folder(self):
        return self.host.datasets.releases.mountpoint

    @property
    def base_dataset(self):
        # base datasets are created from releases. required to start
        # zfs-basejails
        return self.zfs.get_dataset(self.base_dataset_name)

    @property
    def base_dataset_name(self):
        return f"{self.host.datasets.base.name}/{self.name}/root"

    @property
    def download_directory(self):
        return f"{self.releases_folder}/{self.name}"

    @property
    def root_dir(self):
        try:
            if self.root_dataset.mountpoint:
                return self.root_dataset.mountpoint
        except:
            pass

        return f"{self.releases_folder}/{self.name}/root"

    @property
    def assets(self):
        return self._assets

    @assets.setter
    def assets(self, value):
        value = [value] if isinstance(value, str) else value
        self._assets = map(
            lambda x: x if not x.endswith(".txz") else x[:-4],
            value
        )

    @property
    def real_name(self):
        if self.host.distribution.name == "HardenedBSD":
            return f"HardenedBSD-{self.name}-{self.host.processor}-LATEST"
        return self.name

    @property
    def annotated_name(self):
        annotations = set()

        if self.eol is True:
            annotations.add("EOL")

        if len(annotations) > 0:
            return f"{self.name} ({', ('.join(annotations)})"

        return f"{self.name}"

    @property
    def mirror_url(self):
        try:
            if self._mirror_url:
                return self._mirror_url
        except:
            pass
        return self.host.distribution.mirror_url

    @mirror_url.setter
    def mirror_url(self, value):
        url = urlparse(value)
        if url.scheme not in self._supported_url_schemes:
            raise ValueError(f"Invalid URL scheme '{url.scheme}'")
        self._mirror_url = url.geturl()

    @property
    def remote_url(self):
        return f"{self.mirror_url}/{self.real_name}"

    @property
    def available(self):
        try:
            request = urllib.request.Request(self.remote_url, method="HEAD")
            resource = urllib.request.urlopen(request)
            return resource.getcode() == 200
        except:
            return False

    @property
    def fetched(self):
        if not os.path.isdir(self.root_dir):
            return False

        root_dir_index = os.listdir(self.root_dir)

        for expected_directory in ["dev", "var", "etc"]:
            if expected_directory not in root_dir_index:
                return False

        return True

    @property
    def zfs_pool(self):
        try:
            return self.root_dataset.pool
        except:
            pass

        try:
            return self.host.datasets.releases.pool
        except:
            pass

        raise libiocage.lib.errors.UnknownReleasePool()

    @property
    def hashes(self):
        if not self._hashes:
            if not os.path.isfile(self.__get_hashfile_location()):
                self.logger.spam("hashes have not yet been downloaded")
                self._fetch_hashes()
            self._hashes = self.read_hashes()

        return self._hashes

    @property
    def _supported_url_schemes(self):
        return ["https", "http", "ftp"]

    @property
    def release_updates_dir(self):
        return f"{self.dataset.mountpoint}/updates"

    @property
    def hbds_release_branch(self):

        if self._hbsd_release_branch is not None:
            return self._hbsd_release_branch

        if self.fetched is False:
            raise libiocage.lib.errors.ReleaseNotFetched(
                name=self.name,
                logger=self.logger
            )

        source_file = f"{self.root_dataset.mountpoint}/etc/hbsd-update.conf"

        if not os.path.isfile(source_file):
            raise libiocage.lib.errors.ReleaseUpdateBranchLookup(
                release_name=self.name,
                reason=f"{source_file} not found",
                logger=self.logger
            )

        with open(source_file, "r") as f:
            hbsd_update_conf = ucl.load(f.read())
            self._hbsd_release_branch = hbsd_update_conf["branch"]
            return self._hbsd_release_branch

    def fetch(self, update=None, fetch_updates=None):

        release_changed = False

        events = libiocage.lib.events
        fetchReleaseEvent = events.FetchRelease(self)
        releasePrepareStorageEvent = events.ReleasePrepareStorage(self)
        releaseDownloadEvent = events.ReleaseDownload(self)
        releaseExtractionEvent = events.ReleaseExtraction(self)
        releaseConfigurationEvent = events.ReleaseConfiguration(self)

        if not self.fetched:

            yield fetchReleaseEvent.begin()
            yield releasePrepareStorageEvent.begin()

            self._clean_dataset()
            self._create_dataset()
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
            yield releaseConfigurationEvent.begin()

            self._create_default_rcconf()

            yield releaseConfigurationEvent.end()

            release_changed = True

            yield fetchReleaseEvent.end()

        else:

            yield fetchReleaseEvent.skip(
                message="already downloaded"
            )

            self.logger.verbose(
                "Release was already downloaded. Skipping download."
            )

        if fetch_updates is True:
            for event in ReleaseGenerator.fetch_updates(self):
                yield event

        if update is True:
            for event in ReleaseGenerator.update(self):
                if isinstance(event, libiocage.lib.events.IocageEvent):
                    yield event
                else:
                    # the only non-IocageEvent is our return value
                    release_changed = event

        if release_changed:
            self._update_zfs_base()

        self._cleanup()

    def fetch_updates(self):

        events = libiocage.lib.events
        releaseUpdateDownloadEvent = events.ReleaseUpdateDownload(self)
        yield releaseUpdateDownloadEvent.begin()

        release_updates_dir = self.release_updates_dir
        release_update_download_dir = f"{release_updates_dir}"

        if os.path.isdir(release_update_download_dir):
            self.logger.verbose(
                f"Deleting existing updates in {release_update_download_dir}"
            )
            shutil.rmtree(release_update_download_dir)

        os.makedirs(release_update_download_dir)

        if self.host.distribution.name == "HardenedBSD":
            update_name = "hbsd-update"
            update_script_name = "hbsd-update"
            update_conf_name = "hbsd-update.conf"
        else:
            update_name = "freebsd-update"
            update_script_name = "freebsd-update.sh"
            update_conf_name = "freebsd-update.conf"

        files = {
            update_script_name: f"usr.sbin/{update_name}/{update_script_name}",
            update_conf_name  : f"etc/{update_conf_name}",
        }

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
            urllib.request.urlretrieve(url, local_path)

            if key == update_script_name:
                os.chmod(local_path, 0o755)

            elif key == update_conf_name:

                if self.host.distribution.name == "FreeBSD":
                    with open(local_path, "r+") as f:
                        content = f.read()
                        f.seek(0)
                        f.write(content.replace(
                            "Components src",
                            "Components"
                        ))
                        f.truncate()

                os.chmod(local_path, 0o644)

            self.logger.debug(
                f"Update-asset {key} for release '{self.name}'"
                f" saved to {local_path}"
            )

        if self.host.distribution.name == "HardenedBSD":
            """
            Updates in Hardened BSD are directly executed in a jail, so that we
            do not need to pre-fetch the updates
            """
            self.logger.debug(
                "No pre-fetching of HardenedBSD updates required - skipping"
            )
            yield releaseUpdateDownloadEvent.skip(
                message="pre-fetching not supported on HardenedBSD"
            )
        
        else:
            self.logger.verbose(f"Fetching updates for release '{self.name}'")
            libiocage.lib.helpers.exec([
                f"{self.release_updates_dir}/{update_script_name}",
                "-d",
                release_update_download_dir,
                "-f",
                f"{self.release_updates_dir}/{update_conf_name}",
                "--not-running-from-cron",
                "fetch"
            ], logger=self.logger)

            yield releaseUpdateDownloadEvent.end()

    def update(self):
        dataset = self.dataset
        snapshot_name = self._append_datetime(f"{dataset.name}@pre-update")

        runReleaseUpdateEvent = libiocage.lib.events.RunReleaseUpdate(self)
        yield runReleaseUpdateEvent.begin()

        # create snapshot before the changes
        dataset.snapshot(snapshot_name, recursive=True)

        jail = libiocage.lib.Jail.JailGenerator({
                "uuid"              : str(uuid.uuid4()),
                "basejail"          : False,
                "allow_mount_nullfs": "1",
                "release"           : self.name,
                "securelevel"       : "0"
            },
            new=True,
            logger=self.logger,
            zfs=self.zfs,
            host=self.host
        )

        jail.dataset_name = self.dataset_name

        changed = False

        try:
            if self.host.distribution.name == "HardenedBSD":
                for event in self._update_hbsd_jail(jail):
                    if isinstance(event, libiocage.lib.events.IocageEvent):
                        yield event
                    else:
                        changed = event
            else:
                for event in self._update_freebsd_jail(jail):
                    if isinstance(event, libiocage.lib.events.IocageEvent):
                        yield event
                    else:
                        changed = event
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

        return changed

    def _update_hbsd_jail(self, jail):

        events = libiocage.lib.events
        executeReleaseUpdateEvent = events.ExecuteReleaseUpdate(self)

        for event in jail.start():
            yield event

        yield executeReleaseUpdateEvent.begin()

        update_script_path = f"{self.release_updates_dir}/hbsd-update"
        update_conf_path = f"{self.release_updates_dir}/hbsd-update.conf"

        try:

            # ToDo: as bad as print() replace passthru with a nice progress bar
            stdout = libiocage.lib.helpers.exec_iter([
                update_script_path,
                "-c",
                update_conf_path,
                "-j",
                jail.identifier,
                "-V"
            ], logger=self.logger)

            for stdout_line in stdout:
                self.logger.verbose(stdout_line.strip("\n"), indent=1)

            self.logger.debug(f"Update of release '{self.name}' finished")

        except:

            raise libiocage.lib.errors.ReleaseUpdateFailure(
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
        return True  # ToDo: return False if nothing was updated

    def _update_freebsd_jail(self, jail):

        events = libiocage.lib.events
        executeReleaseUpdateEvent = events.ExecuteReleaseUpdate(self)

        local_update_mountpoint = f"{self.root_dir}/var/db/freebsd-update"
        if not os.path.isdir(local_update_mountpoint):
            self.logger.spam(
                "Creating mountpoint {local_update_mountpoint}"
            )
            os.makedirs(local_update_mountpoint)

        jail.config.fstab.add(
            self.release_updates_dir,
            local_update_mountpoint,
            "nullfs",
            "rw"
        )
        jail.config.fstab.save()

        for event in jail.start():
            yield event

        yield executeReleaseUpdateEvent.begin()
        child, stdout, stderr = jail.exec([
            "/var/db/freebsd-update/freebsd-update.sh",
            "-d",
            "/var/db/freebsd-update",
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
                yield executeReleaseUpdateEvent.failed()
                raise libiocage.lib.errors.ReleaseUpdateFailure(
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

    def _append_datetime(self, text):
        now = datetime.datetime.utcnow()
        text += now.strftime("%Y%m%d%H%I%S.%f")
        return text

    def _basejail_datasets_already_exists(self, release_name):
        base_dataset = self.host.datasets.base
        for dataset in base_dataset.children:
            if dataset.name == f"{base_dataset.name}/release_name":
                return True
        return False

    def _create_dataset(self, name=None):

        if name is None:
            name = self.dataset_name

        try:
            if isinstance(self.dataset, libzfs.ZFSDataset):
                return
        except:
            pass

        options = {
            "compression": "lz4"
        }
        self.zfs_pool.create(name, options, create_ancestors=True)
        self._dataset = self.zfs.get_dataset(name)

    def _ensure_dataset_mounted(self):
        if not self.dataset.mountpoint:
            self.dataset.mount()

    def _fetch_hashes(self):
        url = f"{self.remote_url}/{self.host.distribution.hash_file}"
        path = self.__get_hashfile_location()
        self.logger.verbose(f"Downloading hashes from {url}")
        urllib.request.urlretrieve(url, path)
        self.logger.debug(f"Hashes downloaded to {path}")

    def _fetch_assets(self):
        for asset in self.assets:
            url = f"{self.remote_url}/{asset}.txz"
            path = self._get_asset_location(asset)

            if os.path.isfile(path):
                self.logger.verbose(f"{path} already exists - skipping.")
                return
            else:
                self.logger.debug(f"Starting download of {url}")
                urllib.request.urlretrieve(url, path)
                self.logger.verbose(f"{url} was saved to {path}")

    def _clean_dataset(self):

        if not os.path.isdir(self.root_dir):
            return

        root_dir_index = os.listdir(self.root_dir)
        if not len(root_dir_index) > 0:
            return

        self.logger.verbose(
            f"Remove existing fragments from {self.root_dir}"
        )
        for directory in root_dir_index:
            asset_path = os.path.join(self.root_dir, directory)
            self.logger.spam(f"Purging {asset_path}")
            self._rmtree(asset_path)

    def read_hashes(self):
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

    def __get_hashfile_location(self):
        hash_file = self.host.distribution.hash_file
        return f"{self.download_directory}/{hash_file}"

    def _get_asset_location(self, asset_name):
        return f"{self.download_directory}/{asset_name}.txz"

    def _extract_assets(self):

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

    def _create_default_rcconf(self):
        file = f"{self.root_dir}/etc/rc.conf"

        content = "\n".join(map(
            lambda key: self._generate_default_rcconf_line(key),
            Release.DEFAULT_RC_CONF_SERVICES.keys()
        )) + "\n"

        with open(file, "w") as f:
            f.write(content)
            f.truncate()

    def _generate_default_rcconf_line(self, service_name):
        if Release.DEFAULT_RC_CONF_SERVICES[service_name] is True:
            state = "YES"
        else:
            state = "NO"
        return f"{service_name}_enable=\"{state}\""

    def _update_name_from_dataset(self):
        if self.dataset:
            self.name = self.dataset.name.split("/")[-2:-1]

    def _update_zfs_base(self):

        try:
            self.host.datasets.base.pool.create(
                self.base_dataset_name, {}, create_ancestors=True)
            self.base_dataset.mount()
        except:
            pass

        base_dataset = self.base_dataset
        pool = self.host.datasets.base.pool

        basedirs = libiocage.lib.helpers.get_basedir_list(
            distribution_name=self.host.distribution.name
        )

        for folder in basedirs:
            try:
                pool.create(
                    f"{base_dataset.name}/{folder}",
                    {},
                    create_ancestors=True
                )
                self.zfs.get_dataset(f"{base_dataset.name}/{folder}").mount()
            except:
                # dataset was already existing
                pass

            src = self.root_dataset.mountpoint
            dst = f"{base_dataset.mountpoint}/{folder}"

            self.logger.verbose(f"Copying {folder} from {src} to {dst}")
            self._copytree(src, dst)

        self.logger.debug(f"Updated release base datasets for {self.name}")

    def _copytree(self, src_path, dst_path, delete=False):

        src_dir = set(os.listdir(src_path))
        dst_dir = set(os.listdir(dst_path))

        if delete is True:
            for item in dst_dir - src_dir:
                self._rmtree("f{dst_dir}/{item}")

        for item in os.listdir(src_path):
            src = os.path.join(src_path, item)
            dst = os.path.join(dst_path, item)
            if os.path.islink(src) or os.path.isfile(src):
                self._copyfile(src, dst)
            else:
                if not os.path.isdir(dst):
                    src_stat = os.stat(src)
                    os.makedirs(dst, src_stat.st_mode)
                self._copytree(src, dst)

    def _copyfile(self, src_path, dst_path):

        dst_flags = None

        if os.path.islink(dst_path):
            os.unlink(dst_path)
        elif os.path.isfile(dst_path) or os.path.isdir(dst_path):
            dst_stat = os.stat(dst_path)
            dst_flags = dst_stat.st_flags
            self._rmtree(dst_path)

        if os.path.islink(src_path):
            linkto = os.readlink(src_path)
            os.symlink(linkto, dst_path)
        else:
            shutil.copy2(src_path, dst_path)
            if dst_flags is not None:
                os.chflags(dst_path, dst_flags)

    def _rmtree(self, path):
        if os.path.islink(path):
            os.unlink(path)
            return
        elif os.path.isdir(path):
            for item in os.listdir(path):
                self._rmtree(f"{path}/{item}")
            os.chflags(path, 2048)
            os.rmdir(path)
        else:
            os.chflags(path, 2048)
            os.remove(path)

    def _cleanup(self):
        for asset in self.assets:
            asset_location = self._get_asset_location(asset)
            if os.path.isfile(asset_location):
                os.remove(asset_location)

    def _check_asset_hash(self, asset_name):
        local_file_hash = self._read_asset_hash(asset_name)
        expected_hash = self.hashes[asset_name]

        has_valid_hash = local_file_hash == expected_hash
        if not has_valid_hash:
            self.logger.warn(
                f"Asset {asset_name}.txz has an invalid signature"
                f"(was '{local_file_hash}' but expected '{expected_hash}')"
            )
            raise libiocage.lib.errors.InvalidReleaseAssetSignature(
                release_name=self.name,
                asset_name=asset_name,
                logger=self.logger
            )

        self.logger.spam(
            f"Asset {asset_name}.txz has a valid signature ({expected_hash})"
        )

    def _read_asset_hash(self, asset_name):
        asset_location = self._get_asset_location(asset_name)
        sha256 = hashlib.sha256()
        with open(asset_location, 'rb') as f:
            for block in iter(lambda: f.read(65536), b''):
                sha256.update(block)
        return sha256.hexdigest()

    def _check_tar_files(self, tar_infos, asset_name):
        for i in tar_infos:
            self._check_tar_info(i, asset_name)

    def _check_tar_info(self, tar_info, asset_name):
        if tar_info.name == ".":
            return
        if not tar_info.name.startswith("./"):
            reason = "Names in txz files must be relative and begin with './'"
        elif ".." in tar_info.name:
            reason = "Names in txz files must not contain '..'"
        else:
            return

        raise libiocage.lib.errors.IllegalReleaseAssetContent(
            release_name=self.name,
            asset_name=asset_name,
            reason=reason,
            logger=self.logger
        )

    def __str__(self):
        return self.name


class Release(ReleaseGenerator):

    def fetch(self, *args, **kwargs):
        return list(ReleaseGenerator.fetch(self, *args, **kwargs))

    def update(self, *args, **kwargs):
        return list(ReleaseGenerator.update(self, *args, **kwargs))

