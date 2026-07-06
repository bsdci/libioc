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
"""Tests for the platform-independent helper functions."""
import json
import pathlib

import pytest

import libioc.helpers


class TestParseNone(object):
    """Run tests for parse_none."""

    def test_translates_none_values(self) -> None:
        """Test that None and none-like strings translate to None."""
        assert libioc.helpers.parse_none(None) is None
        assert libioc.helpers.parse_none("none") is None
        assert libioc.helpers.parse_none("NONE") is None
        assert libioc.helpers.parse_none("-") is None
        assert libioc.helpers.parse_none("") is None

    def test_accepts_custom_none_matches(self) -> None:
        """Test that custom none matches replace the default ones."""
        assert libioc.helpers.parse_none("skip", ["skip"]) is None
        with pytest.raises(TypeError):
            libioc.helpers.parse_none("none", ["skip"])

    def test_raises_on_other_values(self) -> None:
        """Test that values that are not None raise a TypeError."""
        with pytest.raises(TypeError):
            libioc.helpers.parse_none("value")
        with pytest.raises(TypeError):
            libioc.helpers.parse_none(1)


class TestParseList(object):
    """Run tests for parse_list and split_list_string."""

    def test_none_becomes_an_empty_list(self) -> None:
        """Test that none-like input parses to an empty list."""
        assert libioc.helpers.parse_list(None) == []
        assert libioc.helpers.parse_list("") == []
        assert libioc.helpers.parse_list("none") == []

    def test_lists_pass_through(self) -> None:
        """Test that a list input is returned unchanged."""
        data = ["a", "b"]
        assert libioc.helpers.parse_list(data) == ["a", "b"]

    def test_strings_split_by_comma(self) -> None:
        """Test that comma separated strings become lists."""
        assert libioc.helpers.parse_list("a,b,c") == ["a", "b", "c"]
        assert libioc.helpers.parse_list("single") == ["single"]

    def test_escaped_separators_are_kept(self) -> None:
        """Test that escaped separators do not split the string."""
        assert libioc.helpers.split_list_string(
            "foo,bar\\,baz"
        ) == ["foo", "bar,baz"]

    def test_custom_separator(self) -> None:
        """Test that a custom separator splits the string."""
        assert libioc.helpers.split_list_string(
            "a;b,c",
            separator=";"
        ) == ["a", "b,c"]


class TestParseBool(object):
    """Run tests for parse_bool."""

    def test_parses_boolean_strings(self) -> None:
        """Test that boolean strings parse to booleans."""
        for value in ["yes", "YES", "true", "True", "on", "1"]:
            assert libioc.helpers.parse_bool(value) is True
        for value in ["no", "NO", "false", "False", "off", "0"]:
            assert libioc.helpers.parse_bool(value) is False

    def test_booleans_pass_through(self) -> None:
        """Test that booleans are returned unchanged."""
        assert libioc.helpers.parse_bool(True) is True
        assert libioc.helpers.parse_bool(False) is False

    def test_raises_on_other_values(self) -> None:
        """Test that other values raise a TypeError."""
        with pytest.raises(TypeError):
            libioc.helpers.parse_bool("/etc/passwd")
        with pytest.raises(TypeError):
            libioc.helpers.parse_bool(None)


class TestParseInt(object):
    """Run tests for parse_int."""

    def test_parses_integers(self) -> None:
        """Test that integer values and strings parse to int."""
        assert libioc.helpers.parse_int("-1") == -1
        assert libioc.helpers.parse_int(3) == 3
        assert libioc.helpers.parse_int(5.0) == 5

    def test_raises_on_other_values(self) -> None:
        """Test that non-integer values raise a TypeError."""
        with pytest.raises(TypeError):
            libioc.helpers.parse_int(None)
        with pytest.raises(TypeError):
            libioc.helpers.parse_int("invalid")
        with pytest.raises(TypeError):
            libioc.helpers.parse_int(5.1)


class TestParseUserInput(object):
    """Run tests for parse_user_input."""

    def test_booleans_and_none_are_parsed(self) -> None:
        """Test that boolean and none strings are converted."""
        assert libioc.helpers.parse_user_input("YES") is True
        assert libioc.helpers.parse_user_input("false") is False
        assert libioc.helpers.parse_user_input("none") is None
        assert libioc.helpers.parse_user_input(None) is None

    def test_other_values_pass_through(self) -> None:
        """Test that other input is returned as-is."""
        assert libioc.helpers.parse_user_input("notfalse") == "notfalse"
        assert libioc.helpers.parse_user_input(8.4) == 8.4


class TestNameValidation(object):
    """Run tests for jail name and UUID validation."""

    def test_valid_names(self) -> None:
        """Test that names following the convention are accepted."""
        assert libioc.helpers.is_valid_name("myjail") is True
        assert libioc.helpers.is_valid_name("my-jail_2") is True
        assert libioc.helpers.is_valid_name("web01.example") is True

    def test_invalid_names(self) -> None:
        """Test that invalid names are rejected."""
        assert libioc.helpers.is_valid_name("") is False
        assert libioc.helpers.is_valid_name("-leading") is False
        assert libioc.helpers.is_valid_name("has space") is False
        assert libioc.helpers.is_valid_name("a" * 32) is False

    def test_uuid_detection(self) -> None:
        """Test UUID detection."""
        uuid = "0d3ef814-1339-4b7e-bb0e-c10cff5bf514"
        assert libioc.helpers.is_valid_uuid(uuid) is True
        assert libioc.helpers.is_valid_uuid("myjail") is False

    def test_random_uuid_is_valid(self) -> None:
        """Test that generated UUIDs pass the validation."""
        uuid = libioc.helpers.get_random_uuid()
        assert libioc.helpers.is_valid_uuid(uuid) is True

    def test_humanreadable_name_shortens_uuids(self) -> None:
        """Test that UUIDs are shortened and names pass through."""
        uuid = "0d3ef814-1339-4b7e-bb0e-c10cff5bf514"
        assert libioc.helpers.to_humanreadable_name(uuid) == "0d3ef814"
        assert libioc.helpers.to_humanreadable_name("myjail") == "myjail"


class TestToString(object):
    """Run tests for to_string."""

    def test_translates_special_values(self) -> None:
        """Test the documented default translations."""
        assert libioc.helpers.to_string(True) == "yes"
        assert libioc.helpers.to_string(False) == "no"
        assert libioc.helpers.to_string(None) == "-"

    def test_custom_translations(self) -> None:
        """Test custom true/false words."""
        output = libioc.helpers.to_string(True, true="yip", false="nope")
        assert output == "yip"
        output = libioc.helpers.to_string(False, true="yip", false="nope")
        assert output == "nope"

    def test_lists_are_joined(self) -> None:
        """Test that lists join their stringified items."""
        assert libioc.helpers.to_string(["a", "b"]) == "a,b"
        assert libioc.helpers.to_string([]) == "-"


class TestToJson(object):
    """Run tests for the JSON config serialization."""

    def test_normalizes_values(self) -> None:
        """Test that booleans and None normalize to config words."""
        output = json.loads(libioc.helpers.to_json(dict(
            a=True,
            b=False,
            c=None,
            d="text"
        )))
        assert output == dict(a="yes", b="no", c="none", d="text")


class TestGetOsVersion(object):
    """Run tests for get_os_version."""

    def test_parses_userland_version(self, tmp_path: pathlib.Path) -> None:
        """Test that a freebsd-version file is parsed correctly."""
        version_file = tmp_path / "freebsd-version"
        version_file.write_text(
            '#!/bin/sh\nUSERLAND_VERSION="13.5-RELEASE-p2"\n'
        )
        version = libioc.helpers.get_os_version(str(version_file))
        assert version["userland"] == 13.5
        assert version["name"] == "RELEASE"
        assert version["patch"] == 2


class TestGetBasedirList(object):
    """Run tests for get_basedir_list."""

    def test_freebsd_has_lib32(self) -> None:
        """Test that FreeBSD includes the lib32 basedir."""
        basedirs = libioc.helpers.get_basedir_list("FreeBSD")
        assert "usr/lib32" in basedirs
        assert "bin" in basedirs

    def test_hardenedbsd_has_no_lib32(self) -> None:
        """Test that HardenedBSD excludes the lib32 basedir."""
        basedirs = libioc.helpers.get_basedir_list("HardenedBSD")
        assert "usr/lib32" not in basedirs
