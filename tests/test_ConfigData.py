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
"""Tests for the nested configuration data dictionary."""
import pytest

import libioc.Config.Data


class TestConfigData(object):
    """Run tests for the Config Data dict."""

    def test_flat_keys_behave_like_a_dict(self) -> None:
        """Test that flat keys can be set and read."""
        data = libioc.Config.Data.Data()
        data["key"] = "value"
        assert data["key"] == "value"
        assert ("key" in data) is True

    def test_nested_keys_resolve(self) -> None:
        """Test that delimited keys resolve to nested items."""
        data = libioc.Config.Data.Data()
        data["user.comment"] = "hello"
        assert data["user.comment"] == "hello"
        assert data["user"]["comment"] == "hello"

    def test_nested_input_dicts_are_converted(self) -> None:
        """Test that plain dict input is wrapped into Data."""
        data = libioc.Config.Data.Data(dict(
            user=dict(comment="hello")
        ))
        assert data["user.comment"] == "hello"
        assert isinstance(data["user"], libioc.Config.Data.Data) is True

    def test_keys_flatten_nested_structures(self) -> None:
        """Test that keys() returns the flattened key paths."""
        data = libioc.Config.Data.Data()
        data["a"] = "1"
        data["b.c"] = "2"
        data["b.d"] = "3"
        assert sorted(data.keys()) == ["a", "b.c", "b.d"]
        assert len(data) == 3

    def test_contains_nested_keys(self) -> None:
        """Test __contains__ with flat and nested keys."""
        data = libioc.Config.Data.Data()
        data["a.b.c"] = "x"
        assert ("a.b.c" in data) is True
        assert ("a.b" in data) is True
        assert ("a.nope" in data) is False
        assert (0 in data) is False

    def test_missing_keys_raise(self) -> None:
        """Test that unknown keys raise a KeyError."""
        data = libioc.Config.Data.Data()
        data["a"] = "1"
        with pytest.raises(KeyError):
            data["unknown"]
        with pytest.raises(KeyError):
            data["a.b"]

    def test_items_iterate_flattened(self) -> None:
        """Test that items() yields flattened pairs."""
        data = libioc.Config.Data.Data()
        data["x.y"] = "1"
        items = dict(data.items())
        assert items == {"x.y": "1"}

    def test_nested_returns_plain_structure(self) -> None:
        """Test that the nested property returns the tree structure."""
        data = libioc.Config.Data.Data()
        data["a.b"] = "1"
        nested = data.nested
        assert nested["a"]["b"] == "1"
