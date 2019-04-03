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
"""Unit tests for the MacAddress module."""
import typing
import pytest

import libioc.MacAddress

class TestMacAddress(object):

	@pytest.fixture
	def mac_address_string(self) -> str:
		return "02:ab:cd:ef:23:42"

	def test_accepts_mac_with_colons(
		self,
		mac_address_string: str,
		logger: 'libioc.Logger.Logger'
	) -> None:
		mac = libioc.MacAddress.MacAddress(
			mac_address_string.upper(),
			logger=logger
		)
		assert str(mac) == mac_address_string

		mac = libioc.MacAddress.MacAddress(
			mac_address_string.lower(),
			logger=logger
		)
		assert str(mac) == mac_address_string

	def test_accepts_mac_with_dashes(
		self,
		mac_address_string: str,
		logger: 'libioc.Logger.Logger'
	) -> None:
		mac = libioc.MacAddress.MacAddress(
			mac_address_string.replace(":", "-").upper(),
			logger=logger
		)
		assert str(mac) == mac_address_string

		mac = libioc.MacAddress.MacAddress(
			mac_address_string.replace(":", "-").lower(),
			logger=logger
		)
		assert str(mac) == mac_address_string

	def test_accepts_mac_without_delimiter(
		self,
		mac_address_string: str,
		logger: 'libioc.Logger.Logger'
	) -> None:
		mac = libioc.MacAddress.MacAddress(
			mac_address_string.replace(":", "").upper(),
			logger=logger
		)
		assert str(mac) == mac_address_string

		mac = libioc.MacAddress.MacAddress(
			mac_address_string.replace(":", "").lower(),
			logger=logger
		)
		assert str(mac) == mac_address_string

	def test_rejects_invalid_length(
		self,
		mac_address_string: str,
		logger: 'libioc.Logger.Logger'
	) -> None:

		with pytest.raises(ValueError):
			libioc.MacAddress.MacAddress(
				"ABC",
				logger=logger
			)

		with pytest.raises(ValueError):
			libioc.MacAddress.MacAddress(
				"ABC,DEF",
				logger=logger
			)


class TestMacAddressPair(object):

	def test_can_be_created_from_string(
		self,
		logger: 'libioc.Logger.Logger'
	) -> None:

		mac_a = "02:00:00:00:00:01"
		mac_b = "02:00:00:00:00:02"
		mac_pair_string = f"{mac_a},{mac_b}"

		pair = libioc.MacAddress.MacAddressPair(
			mac_pair_string,
			logger=logger
		)

		assert str(pair) == mac_pair_string
		assert str(pair.a) == mac_a
		assert str(pair.b) == mac_b

	def test_can_be_created_from_tuple_of_strings(
		self,
		logger: 'libioc.Logger.Logger'
	) -> None:

		mac_a = "02:00:00:00:00:03"
		mac_b = "02:00:00:00:00:04"
		mac_pair_string = f"{mac_a},{mac_b}"

		pair = libioc.MacAddress.MacAddressPair(
			(mac_a, mac_b),
			logger=logger
		)

		assert str(pair) == mac_pair_string
		assert str(pair.a) == mac_a
		assert str(pair.b) == mac_b

	def test_cannot_be_created_from_string_without_comma(
		self,
		logger: 'libioc.Logger.Logger'
	) -> None:

		with pytest.raises(ValueError):
			libioc.MacAddress.MacAddressPair(
				"NOT_A_MAC_ADDRESS",
				logger=logger
			)

	def test_can_be_created_from_tuple_of_macaddresses(
		self,
		logger: 'libioc.Logger.Logger'
	) -> None:

		mac_a = "02:00:00:00:00:05"
		mac_b = "02:00:00:00:00:06"
		mac_pair_string = f"{mac_a},{mac_b}"

		mac_a_address = libioc.MacAddress.MacAddress(
			mac_a,
			logger=logger
		)
		mac_b_address = libioc.MacAddress.MacAddress(
			mac_b,
			logger=logger
		)

		pair = libioc.MacAddress.MacAddressPair(
			(mac_a_address, mac_b_address),
			logger=logger
		)

		assert str(pair) == mac_pair_string
		assert str(pair.a) == mac_a
		assert str(pair.b) == mac_b

	def test_cannot_be_created_from_tuple_of_more_items(
		self,
		logger: 'libioc.Logger.Logger'
	) -> None:

		mac_a = "02:00:00:00:00:07"
		mac_b = "02:00:00:00:00:08"
		mac_c = "02:00:00:00:00:09"

		with pytest.raises(ValueError):
			libioc.MacAddress.MacAddressPair(
				(mac_a, mac_b, mac_c),
				logger=logger
			)

		with pytest.raises(ValueError):
			libioc.MacAddress.MacAddressPair((
				libioc.MacAddress.MacAddress(
					mac_a,
					logger=logger
				),
				libioc.MacAddress.MacAddress(
					mac_b,
					logger=logger
				),
				libioc.MacAddress.MacAddress(
					mac_c,
					logger=logger
				)
			), logger=logger)
