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
"""Unit tests for Jail and Default Config."""
import typing
import pytest
import json
import os

import libzfs

import libioc.Jail
import libioc.Config.Type.JSON
import libioc.Config.Jail.Properties.Interfaces

class TestJailConfig(object):

	def test_default_config_type_is_json(
		self,
		existing_jail: 'libioc.Jail.Jail'
	) -> None:
		ConfigJSON = libioc.Config.Type.JSON.ConfigJSON
		assert existing_jail.config_type == "json"
		assert isinstance(existing_jail.config_handler, ConfigJSON)

	def test_cannot_set_unknown_config_property(
		self,
		existing_jail: 'libioc.Jail.Jail'
	) -> None:
		key = "doesnotexist"
		with pytest.raises(libioc.errors.UnknownConfigProperty):
			existing_jail.config[key]
		assert key not in existing_jail.config.keys()

	def test_can_set_arbitrary_user_config_properties(
		self,
		existing_jail: 'libioc.Jail.Jail'
	) -> None:

		existing_jail.config["user.foobar"] = "baz"
		existing_jail.save()

		assert "user.foobar" in existing_jail.config.keys()
		assert isinstance(existing_jail.config["user"], dict)
		assert "foobar" in existing_jail.config["user"].keys()
		assert existing_jail.config["user"]["foobar"] == "baz"

		with open(existing_jail.config_json.file, "r", encoding="UTF-8") as f:
			data = json.load(f)

		assert "user" in data.keys()
		assert isinstance(data["user"], dict)
		assert "foobar" in data["user"].keys()
		assert isinstance(data["user"]["foobar"], str)

	def test_name_may_not_contain_dots(
		self,
		existing_jail: 'libioc.Jail.Jail'
	) -> None:
		with pytest.raises(libioc.errors.InvalidJailName):
			existing_jail.config["name"] = "jail.with.dots"

	def test_cannot_clone_from_dict_with_invalid_values(
		self,
		new_jail: 'libioc.Jail.Jail'
	) -> None:
		invalid_data = dict(
			name="name.with.dots"
		)
		del new_jail.config["id"]
		with pytest.raises(libioc.errors.InvalidJailName):
			new_jail.config.clone(invalid_data)

	def test_can_only_set_vnet_mac_when_the_interface_exists(
		self,
		new_jail: 'libioc.Jail.Jail'
	) -> None:
		with pytest.raises(libioc.errors.UnknownConfigProperty):
			new_jail.config["vnet0_mac"] = "63ECAC12D0F5"

		new_jail.config["vnet"] = True
		new_jail.config["interfaces"] = "vnet0:bridge0"
		new_jail.config["vnet0_mac"] = "63ECAC12D0F6"
		assert new_jail.config.data["vnet0_mac"] == "63ECAC12D0F6"

	def test_order_of_mac_and_interfaces_does_not_matter(
		self,
		new_jail: 'libioc.Jail.Jail'
	) -> None:
		new_jail.config.set_dict(dict(
			vnet0_mac="63ECAC12D0F7",
			interfaces="vnet0:bridge0"
		))
		assert new_jail.config.data["vnet0_mac"] == "63ECAC12D0F7"

	def test_jails_with_already_existing_unknown_macs_can_be_loaded(
		self,
		existing_jail: 'libioc.Jail.Jail',
		host: 'libioc.Host.Host',
	    logger: 'libioc.Logger.Logger',
	    zfs: libzfs.ZFS
	) -> None:
		config_file = existing_jail.config_handler.file
		with open(config_file, "w", encoding="UTF-8") as f:
			json.dump(dict(
				name=existing_jail.config["name"],
				release=existing_jail.config["release"],
				vnet="yes",
				vnet0_mac="63ECAC12D0F8",
				vnet1_mac="63ECAC12D0F9"
			), f)

		jail = libioc.Jail.Jail(
			existing_jail.name,
			host=host,
			logger=logger,
			zfs=zfs
		)
		assert jail.config["vnet0_mac"] == "63ECAC12D0F8"
		assert jail.config["vnet1_mac"] == "63ECAC12D0F9"
		assert "interfaces" not in jail.config.data
		assert len(jail.config["interfaces"]) == 0

		# can start, although config is not explicitly valid
		jail.start()
		assert jail.running


class TestUserDefaultConfig(object):

	@pytest.fixture(scope="function")
	def default_config_file_handler(
		self,
		root_dataset: libzfs.ZFSDataset
	) -> typing.IO[str]:
		defaults_config_file = f"{root_dataset.mountpoint}/defaults.json"
		f = open(defaults_config_file, "w", encoding="UTF-8")
		yield f

		with open(defaults_config_file, "r") as x:
			print(x.read())

		f.close()
		os.remove(defaults_config_file)

	@pytest.fixture(scope="function")
	def default_resource(
		self,
		logger: 'libioc.Logger.Logger',
		root_dataset: libzfs.ZFSDataset,
		zfs: libzfs.ZFS,
	) -> 'libioc.Resource.DefaultResource':
		return libioc.Resource.DefaultResource(
			dataset=root_dataset,
			logger=logger,
			zfs=zfs
		)

	def test_default_config_path(
		self,
		host: 'libioc.Host.HostGenerator',
		root_dataset: libzfs.ZFSDataset
	) -> None:
		assert isinstance(host.defaults, libioc.Resource.DefaultResource)
		assert "config" in dir(host.defaults)

		host_config_file = host.defaults.config_handler.file
		assert host_config_file == f"{root_dataset.mountpoint}/defaults.json"

	def test_read_default_config_file(
		self,
		default_resource: 'libioc.Resource.DefaultResource',
		default_config_file_handler: typing.IO[str]
	) -> None:
		test_data = dict(vnet="yes", interfaces="vnet5:bridge8")
		test_data_json = json.dumps(test_data)
		default_config_file_handler.write(test_data_json)
		default_config_file_handler.flush()

		default_resource.read_config()
		assert default_resource.config["vnet"] == True
		assert isinstance(
			default_resource.config["interfaces"],
			libioc.Config.Jail.Properties.Interfaces.InterfaceProp
		)
		assert len(default_resource.config["interfaces"]) == 1
		assert "vnet5" in default_resource.config["interfaces"]
		assert isinstance(
			default_resource.config["interfaces"]["vnet5"],
			libioc.BridgeInterface.BridgeInterface
		)
		assert str(default_resource.config["interfaces"]["vnet5"]) == "bridge8"

	def test_falls_back_to_globals_if_unconfigured(
		self,
		default_resource: 'libioc.Resource.DefaultResource',
	) -> None:
		assert default_resource.config["vnet"] == False

	def test_fail_to_read_unknown_property(
		self,
		default_resource: 'libioc.Resource.DefaultResource',
	) -> None:
		with pytest.raises(libioc.errors.UnknownConfigProperty):
			default_resource.config["not-available"]
		with pytest.raises(libioc.errors.UnknownConfigProperty):
			default_resource.config["not-available"] = "foobar"

		# check that valid properties still can be set
		default_resource.config["user.valid-property"] = "ok"
		assert default_resource.config.data["user.valid-property"] == "ok"
