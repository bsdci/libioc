# Copyright (c) 2026, the libioc contributors
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
"""Unit tests for the Distribution module."""
import typing
import unittest.mock

import libioc.Distribution
import libioc.Host
import libioc.Logger
import libioc.ZFS


class TestEOLList(object):
    """Run tests for the end-of-life release list."""

    def test_failed_eol_download_warns_instead_of_crashing(
        self,
        logger: 'libioc.Logger.Logger',
        mocker: typing.Any
    ) -> None:
        distribution = libioc.Distribution.Distribution(
            host=unittest.mock.Mock(spec=libioc.Host.HostGenerator),
            zfs=unittest.mock.Mock(spec=libioc.ZFS.ZFS),
            logger=logger
        )

        response = unittest.mock.MagicMock()
        response.getcode.return_value = 503
        urlopen = mocker.patch("urllib.request.urlopen")
        urlopen.return_value.__enter__.return_value = response
        warn = mocker.spy(logger, "warn")

        assert distribution._query_eol_list() == []
        assert warn.call_count == 1
