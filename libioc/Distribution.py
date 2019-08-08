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
"""ioc Distribution module."""
import typing
import os
import platform
import re
import urllib.request
import html.parser

import libioc.errors
import libioc.helpers_object


class EOLParser(html.parser.HTMLParser):
    """Parser for EOL releases."""

    eol_releases: typing.List[str] = []
    data: typing.List[str] = []
    in_id: bool = False
    td_counter: int = 0
    current_branch: str = ""

    def handle_starttag(  # noqa: T484
        self,
        tag: str,
        attrs: typing.Dict[str, str]
    ) -> None:
        """Handle opening HTML tags."""
        if tag == "td":
            self.in_id = True
            self.td_counter += 1
        elif tag == "tr":
            self.td_counter = 0

    def handle_endtag(self, tag: str) -> None:
        """Handle closing HTML tags."""
        if tag == "td":
            self.in_id = False

    def handle_data(self, data: str) -> None:
        """Handle data in HTML tags."""
        if self.in_id is False:
            return  # skip non-td content
        if (self.td_counter == 1) and data.startswith("stable/"):
            stable_version = data[7:]
            self.eol_releases.append(f"{stable_version}-STABLE")
        elif (self.td_counter == 2) and (data != "n/a"):
            self.eol_releases.append(data)


class DistributionGenerator:
    """Asynchronous representation of the host distribution."""

    release_name_blacklist = [
        "",
        ".",
        "..",
        "ISO-IMAGES"
    ]

    eol_url: str = "https://www.freebsd.org/security/unsupported.html"
    _eol_list: typing.Optional[typing.List[str]]

    __mirror_link_pattern = r"a href=\"([A-z0-9\-_\.]+)/\""
    _available_releases: typing.Optional[
        typing.List['libioc.Release.ReleaseGenerator']
    ]

    host: 'libioc.Host.HostGenerator'
    zfs: 'libioc.ZFS.ZFS'
    logger: 'libioc.Logger.Logger'

    def __init__(
        self,
        host: typing.Optional['libioc.Host.Host']=None,
        zfs: typing.Optional['libioc.ZFS.ZFS']=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.zfs = libioc.helpers_object.init_zfs(self, zfs)
        self.host = libioc.helpers_object.init_host(self, host)
        self._eol_list = None
        self._available_releases = None

    @property
    def _class_release(self) -> typing.Union[
        'libioc.Release.ReleaseGenerator',
        'libioc.Release.Release'
    ]:
        return libioc.Release.ReleaseGenerator

    @property
    def name(self) -> str:
        """
        Return the name of the host distribution.

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
        Return the mirror URL of the distribution.

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
            raise libioc.errors.DistributionUnknown(distribution)

    @property
    def hash_file(self) -> str:
        """Return the name of the checksum file found on the mirror."""
        if self.name == "FreeBSD":
            return "MANIFEST"
        elif self.name == "HardenedBSD":
            return "CHECKSUMS.SHA256"
        raise libioc.errors.DistributionUnknown(
            distribution_name=self.name
        )

    def fetch_releases(self) -> None:
        """Fetch and cache the available releases."""
        self.logger.spam(f"Fetching release list from '{self.mirror_url}'")

        # the mirror_url @property is validated (enforced) @property, so:
        resource = urllib.request.urlopen(self.mirror_url)  # nosec
        charset = resource.headers.get_content_charset()  # noqa: T484
        response = resource.read().decode(charset if charset else "UTF-8")

        found_releases = self._parse_links(response)

        def parse_release_version(release_name: str) -> float:
            release_fragments = release_name.split("-", maxsplit=1)
            try:
                return float(release_fragments[0])
            except ValueError:
                # non-float values indicate a high index
                return float(1024)

        available_releases = sorted(
            map(  # map long HardenedBSD release names
                self._map_available_release,
                filter(  # filter out other CPU architectures on HardenedBSD
                    self._filter_available_releases,
                    found_releases
                )
            ),
            key=parse_release_version  # sort numerically
        )

        self._available_releases = list(map(
            lambda x: self._class_release(  # noqa: T484
                name=x,
                host=self.host,
                zfs=self.zfs,
                logger=self.logger
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

    @property
    def eol_list(self) -> typing.List[str]:
        """Return the (memoized) list of release names listed as EOL."""
        if self._eol_list is None:
            eol_list = self._query_eol_list()
            self._eol_list = eol_list
            return eol_list
        else:
            return self._eol_list

    def _query_eol_list(self) -> typing.List[str]:
        """Scrape the FreeBSD website and return a list of EOL RELEASES."""
        request = urllib.request.Request(
            self.eol_url,
            headers={
                "Accept-Charset": "utf-8"
            }
        )
        self.logger.verbose(f"Downloading EOL info from {self.eol_url}")
        with urllib.request.urlopen(request) as response:  # nosec: B310

            response_code = response.getcode()
            if response_code != 200:  # noqa: T484
                libioc.errors.DownloadFailed(
                    topic="EOL Warnings",
                    code=response_code,
                    logger=self.logger,
                    level="warning"
                )
                return []

            parser = EOLParser()
            data = response.read().decode("utf-8", "ignore")
            parser.feed(data)
            parser.close()

            return parser.eol_releases

    @property
    def releases(self) -> typing.List['libioc.Release.ReleaseGenerator']:
        """
        List of available releases.

        Raises an error when the releases cannot be fetched at the current time
        """
        if self._available_releases is None:
            self.fetch_releases()
        if self._available_releases is not None:
            return self._available_releases
        raise libioc.errors.ReleaseListUnavailable()

    def _parse_links(self, text: str) -> typing.List[str]:
        blacklisted_releases = Distribution.release_name_blacklist
        matches = filter(
            lambda y: y not in blacklisted_releases,
            map(
                lambda z: z.strip("\"/"),  # noqa: T484
                re.findall(
                    Distribution.__mirror_link_pattern,
                    text,
                    re.MULTILINE
                )
            )
        )
        return list(matches)


class Distribution(DistributionGenerator):
    """Synchronous wrapper of the host distribution."""

    @property
    def _class_release(self) -> typing.Union[
        'libioc.Release.ReleaseGenerator',
        'libioc.Release.Release'
    ]:
        return libioc.Release.Release
