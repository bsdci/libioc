import os
import platform
import re
import urllib.request

import libiocage.lib.Release
import libiocage.lib.errors
import libiocage.lib.helpers


class Distribution:
    release_name_blacklist = [
        "",
        ".",
        "..",
        "ISO-IMAGES"
    ]

    mirror_link_pattern = r"a href=\"([A-z0-9\-_\.]+)/\""

    def __init__(self, host, zfs=None, logger=None):
        libiocage.lib.helpers.init_logger(self, logger)
        libiocage.lib.helpers.init_zfs(self, zfs)
        libiocage.lib.helpers.init_host(self, host)
        self.available_releases = None
        self.zfs = zfs
        self.logger = logger

    @property
    def name(self):
        if os.uname()[2].endswith("-HBSD"):
            return "HardenedBSD"
        else:
            return platform.system()

    @property
    def mirror_url(self):

        distribution = self.name
        processor = self.host.processor

        if distribution == "FreeBSD":
            release_path = f"/pub/FreeBSD/releases/{processor}/{processor}"
            return f"http://ftp.freebsd.org{release_path}"
        elif distribution == "HardenedBSD":
            return f"http://jenkins.hardenedbsd.org/builds"
        else:
            raise libiocage.lib.errors.DistributionUnknown(distribution)

    @property
    def hash_file(self):
        if self.name == "FreeBSD":
            return "MANIFEST"
        elif self.name == "HardenedBSD":
            return "CHECKSUMS.SHA256"

    def fetch_releases(self):

        self.logger.spam(f"Fetching release list from '{self.mirror_url}'")

        resource = urllib.request.urlopen(self.mirror_url)
        charset = resource.headers.get_content_charset()
        response = resource.read().decode(charset if charset else "UTF-8")

        found_releases = self._parse_links(response)

        available_releases = sorted(
            map(  # map long HardenedBSD release names
                self._map_available_release,
                filter(  # filter out other CPU architectures on HardenedBSD
                    self._filter_available_releases,
                    found_releases
                )
            )
        )

        self.available_releases = list(map(
            lambda x: libiocage.lib.Release.Release(
                name=x,
                host=self.host,
                zfs=self.zfs,
                logger=self.logger
            ),
            available_releases
        ))
        return self.available_releases

    def _map_available_release(self, release_name):
        if self.name == "HardenedBSD":
            # e.g. HardenedBSD-11-STABLE-libressl-amd64-LATEST
            return "-".join(release_name.split("-")[1:-2])
        return release_name

    def _filter_available_releases(self, release_name):
        if self.name != "HardenedBSD":
            return True
        arch = release_name.split("-")[-2:][0]
        return self.host.processor == arch

    def get_release_trunk_file_url(self, release, filename):

        if self.host.distribution.name == "HardenedBSD":

            return "/".join([
                "https://raw.githubusercontent.com/HardenedBSD/hardenedBSD",
                release.hbds_release_branch,
                filename
            ])

        elif self.host.distribution.name == "FreeBSD":

            if release.name == "11.0-RELEASE":
                release_name = "11.0.1"
            else:
                fragments = release.name.split("-", maxsplit=1)
                release_name = f"{fragments[0]}.0"

            base_url = "https://svnweb.freebsd.org/base/release"
            return f"{base_url}/{release_name}/{filename}?view=co"

    @property
    def releases(self):
        if self.available_releases is None:
            self.fetch_releases()
        return self.available_releases

    def _parse_links(self, text):
        blacklisted_releases = Distribution.release_name_blacklist
        matches = filter(lambda y: y not in blacklisted_releases,
                         map(lambda z: z.strip("\"/"),
                             re.findall(
                                 Distribution.mirror_link_pattern,
                                 text,
                                 re.MULTILINE)
                             )
                         )

        return matches
