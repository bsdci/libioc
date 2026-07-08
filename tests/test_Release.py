# Copyright (c) 2017-2019, Stefan Grönke, Igor Galić
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
"""Unit tests for the Release module."""
import os.path

import pytest

import libioc.errors
import libioc.Release

class TestRelease(object):
    """Run Release unit tests."""

    def test_periodoc_config_is_applied_to_fetched_releases(
        self,
        local_release: 'libioc.Release.ReleaseGenerator'
    ) -> None:
        periodic_conf_path = f"{local_release.root_path}/etc/periodic.conf"
        assert os.path.exists(periodic_conf_path)

        with open(periodic_conf_path, "r", encoding="UTF-8") as f:
            content = f.read()
            assert "daily_clean_hoststat_enable=\"NO\"" in content
            assert "daily_status_mail_rejects_enable=\"NO\"" in content
            assert "daily_status_include_submit_mailq=\"NO\"" in content
            assert "daily_submit_queuerun=\"NO\"" in content


class TestAssetSignature(object):
    """Run tests for release asset signature verification."""

    def test_hash_mismatch_raises_invalid_release_asset_signature(
        self,
        logger: 'libioc.Logger.Logger'
    ) -> None:

        class ReleaseStub:

            name = "13.5-RELEASE"
            hashes = dict(base="expected-hash")

            def __init__(self, logger: 'libioc.Logger.Logger') -> None:
                self.logger = logger

            def _read_asset_hash(self, asset_name: str) -> str:
                return "mismatching-hash"

        stub = ReleaseStub(logger)

        with pytest.raises(libioc.errors.InvalidReleaseAssetSignature):
            libioc.Release.ReleaseGenerator._check_asset_hash(stub, "base")
