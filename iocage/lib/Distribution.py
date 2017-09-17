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
import os
import platform
import re
import urllib.request
from typing import List

import requests

import iocage.lib.errors
import iocage.lib.helpers


class DistributionGenerator:

    release_name_blacklist = [
        "",
        ".",
        "..",
        "ISO-IMAGES"
    ]

    mirror_link_pattern = r"a href=\"([A-z0-9\-_\.]+)/\""

    def __init__(self, host, zfs=None, logger=None):
        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)
        self.host = iocage.lib.helpers.init_host(self, host)

        self.available_releases = None

    @property
    def _class_release(self):
        return iocage.lib.Release.ReleaseGenerator

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
            raise iocage.lib.errors.DistributionUnknown(distribution)

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
        eol_list = self._get_eol_list()

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
            lambda x: self._class_release(
                name=x,
                host=self.host,
                zfs=self.zfs,
                logger=self.logger,
                eol=self._check_eol(x, eol_list)
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

    def _get_eol_list(self) -> List[str]:
        """Scrapes the FreeBSD website and returns a list of EOL RELEASES"""
        _eol = "https://www.freebsd.org/security/unsupported.html"
        req = requests.get(_eol)
        status = req.status_code == requests.codes.ok
        eol_releases: List[str] = []
        if not status:
            req.raise_for_status()

        for eol in req.content.decode("iso-8859-1").split():
            eol_lines = eol.strip("href=").strip("/").split(">")
            # We want a dynamic EOL
            try:
                if "-RELEASE" in eol_lines[1]:
                    eol_candidate = eol_lines[1].strip('</td')
                    if eol_candidate not in eol_releases:
                        eol_releases.append(eol_candidate)
            except IndexError:
                pass

        return eol_releases

    def _check_eol(self, release: str, eol: List[str]) -> bool:
        if self.host.distribution.name == "FreeBSD":
            if release in eol:
                return True

        return False

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


class Distribution(DistributionGenerator):

    @property
    def _class_release(self):
        return iocage.lib.Release.Release
