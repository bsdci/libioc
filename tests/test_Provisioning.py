# Copyright (c) 2017-2019, Stefan Grönke
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
"""Unit tests for Provisioning Plugins."""
import typing
import os.path
import subprocess
import pytest

import libioc.Jail
import libioc.Pkg

class TestPuppetProvisioner(object):
    """Run Puppet Provisioner tests."""

    @pytest.fixture
    def manifest_dir(self) -> str:
        __dirname = os.path.dirname(os.path.realpath(__file__))
        return os.path.join(__dirname, "assets/puppet-offline-repo")

    def test_can_provision_from_local_puppet_manifest(
        self,
        existing_jail: 'libioc.Jail.Jail',
        manifest_dir: str,
        pkg: 'libioc.Pkg.Pkg'
    ) -> None:
        existing_jail.config.set_dict(dict(
            provision=dict(
                method="puppet",
                source=manifest_dir
            )
        ))

        assert existing_jail.config["provision.method"] == "puppet"
        assert existing_jail.config["provision.source"] == manifest_dir

        assert existing_jail.running is False

        for event in existing_jail.provisioner.provision():
            assert isinstance(event, libioc.events.IocEvent) is True

        assert existing_jail.running is False
        assert os.path.exists(
            os.path.join(existing_jail.root_path, "puppet.test")
        )
