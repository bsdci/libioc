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
import os
import platform
import re
import urllib.request
import html.parser

import iocage.lib.errors
import iocage.lib.helpers


class EOLParser(html.parser.HTMLParser):

    eol_releases: typing.List[str] = []
    data: typing.List[str] = []
    in_id: bool = False
    td_counter: int = 0
    current_branch: str = ""

    def handle_starttag(self, tag, attrs) -> None:
        if tag == "td":
            self.in_id = True
            self.td_counter += 1
        elif tag == "tr":
            self.td_counter = 0

    def handle_endtag(self, tag: str) -> None:
        if tag == "td":
            self.in_id = False

    def handle_data(self, data: str) -> None:
        if self.in_id is False:
            return  # skip non-td content
        if (self.td_counter == 1) and data.startswith("stable/"):
            stable_version = data[7:]
            self.eol_releases.append(f"{stable_version}-STABLE")
        elif (self.td_counter == 2) and (data != "n/a"):
            self.eol_releases.append(data)


class DistributionGenerator:

    release_name_blacklist = [
        "",
        ".",
        "..",
        "ISO-IMAGES"
    ]

    eol_url: str = "https://www.freebsd.org/security/unsupported.html"

    mirror_link_pattern = r"a href=\"([A-z0-9\-_\.]+)/\""
    available_releases: typing.Optional[
        typing.List['iocage.lib.Release.ReleaseGenerator']
    ] = None

    def __init__(
        self,
        host: typing.Optional['iocage.lib.Host.Host']=None,
        zfs: typing.Optional['iocage.lib.ZFS.ZFS']=None,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None
    ) -> None:
        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)
        self.host = iocage.lib.helpers.init_host(self, host)

    @property
    def _class_release(self) -> typing.Union[
        'iocage.lib.Release.ReleaseGenerator',
        'iocage.lib.Release.Release'
    ]:
        return iocage.lib.Release.ReleaseGenerator

    @property
    def name(self) -> str:
        """
        Name of the host distribution

        Often used to differentiate between operations for HardenedBSD or
        standard FreeBSD.
        """
        if os.path.exists("/usr/sbin/hbsd-update"):
            return "HardenedBSD"
        else:
            return platform.system()

    @property
    def mirror_url(self) -> str:
        """
        URL that points to the top level directory of a distributions release
        asset HTTP server.
        """

        distribution = self.name
        processor = self.host.processor

        if distribution == "FreeBSD":
            release_path = f"/ftp/releases/{processor}/{processor}"
            return f"https://download.freebsd.org{release_path}"
        elif distribution == "HardenedBSD":
            return f"https://jenkins.hardenedbsd.org/builds"
        else:
            raise iocage.lib.errors.DistributionUnknown(distribution)

    @property
    def hash_file(self) -> str:
        """
        The filename of the checksum file that can be found in the mirror_url
        """
        if self.name == "FreeBSD":
            return "MANIFEST"
        elif self.name == "HardenedBSD":
            return "CHECKSUMS.SHA256"
        raise iocage.lib.errors.DistributionUnknown(
            distribution_name=self.name
        )

    def fetch_releases(self) -> None:
        """
        Fetches and caches the available releases of the current distribution
        """

        self.logger.spam(f"Fetching release list from '{self.mirror_url}'")

        # the mirror_url @property is validated (enforced) @property, so:
        resource = urllib.request.urlopen(self.mirror_url)  # nosec
        charset = resource.headers.get_content_charset()  # noqa: T484
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
            filter(
                lambda y: len(y) > 0,
                available_releases
            )
        ))

    def _map_available_release(self, release_name: str) -> str:
        if self.name == "HardenedBSD":
            # e.g. HardenedBSD-11-STABLE-libressl-amd64-LATEST
            return "-".join(release_name.split("-")[1:-2])
        return release_name

    def _filter_available_releases(self, release_name: str) -> bool:
        if self.name != "HardenedBSD":
            return True
        arch = release_name.split("-")[-2:][0]
        return (self.host.processor == arch) is True

    def _get_eol_list(self) -> typing.List[str]:
        """Scrapes the FreeBSD website and returns a list of EOL RELEASES"""
        request = urllib.request.Request(
            self.eol_url,
            headers={
                "Accept-Charset": "utf-8"
            }
        )
        self.logger.verbose(f"Downloading EOL info from {self.eol_url}")
        with urllib.request.urlopen(request) as response:  # nosec: B310

            if response.getcode() != 200:  # noqa: T484
                iocage.lib.errors.DistributionEOLWarningDownloadFailed(
                    logger=self.logger,
                    level="warning"
                )
                return []

            parser = EOLParser()
            data = response.read().decode("utf-8", "ignore")
            parser.feed(data)
            parser.close()

            return parser.eol_releases

    def _parse_release_version(self, release_version_string: str) -> str:
        parsed_version = release_version_string.split("-", maxsplit=1)[0]
        if "." not in parsed_version:
            parsed_version += ".0"
        return parsed_version

    def _check_eol(self, release_name: str, eol: typing.List[str]) -> bool:
        if self.host.distribution.name == "FreeBSD":
            return release_name in eol
        elif self.host.distribution.name == "HardenedBSD":
            if "STABLE" in release_name:
                # stable releases are explicitly in the EOL list or supported
                return release_name in eol
            return self._parse_release_version(release_name) in map(
                lambda x: self._parse_release_version(x),
                eol
            )
        return False

    @property
    def releases(self) -> typing.List['iocage.lib.Release.ReleaseGenerator']:
        """
        List of available releases

        Raises an error when the releases cannot be fetched at the current time
        """
        if self.available_releases is None:
            self.fetch_releases()
        if self.available_releases is not None:
            return self.available_releases
        raise iocage.lib.errors.ReleaseListUnavailable()

    def _parse_links(self, text: str) -> typing.List[str]:
        blacklisted_releases = Distribution.release_name_blacklist
        matches = filter(
            lambda y: y not in blacklisted_releases,
            map(
                lambda z: z.strip("\"/"),
                re.findall(
                    Distribution.mirror_link_pattern,
                    text,
                    re.MULTILINE
                )
            )
        )
        return list(matches)


class Distribution(DistributionGenerator):

    @property
    def _class_release(self) -> typing.Union[
        'iocage.lib.Release.ReleaseGenerator',
        'iocage.lib.Release.Release'
    ]:
        return iocage.lib.Release.Release
