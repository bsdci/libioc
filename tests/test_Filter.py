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
"""Tests for the resource filter terms."""
import pytest

import libioc.Filter


class TestMatchFilter(object):
    """Run tests for the glob matching primitive."""

    def test_exact_match(self) -> None:
        """Test that equal strings match."""
        assert libioc.Filter.match_filter("webserver", "webserver") is True
        assert libioc.Filter.match_filter("webserver", "database") is False

    def test_asterisk_matches_any_length(self) -> None:
        """Test that * matches any number of characters."""
        assert libioc.Filter.match_filter("webserver", "web*") is True
        assert libioc.Filter.match_filter("webserver", "*server") is True
        assert libioc.Filter.match_filter("webserver", "*") is True
        assert libioc.Filter.match_filter("webserver", "db*") is False

    def test_plus_requires_one_character(self) -> None:
        """Test that + requires at least one character."""
        assert libioc.Filter.match_filter("webserver", "web+") is True
        assert libioc.Filter.match_filter("web", "web+") is False

    def test_special_characters_are_literal(self) -> None:
        """Test that regex characters in filters match literally."""
        assert libioc.Filter.match_filter("a.b", "a.b") is True
        assert libioc.Filter.match_filter("axb", "a.b") is False


class TestTerm(object):
    """Run tests for a single filter term."""

    def test_splits_filter_values(self) -> None:
        """Test that a term string splits its values by comma."""
        term = libioc.Filter.Term("name", "foo,bar")
        assert list(term) == ["foo", "bar"]

    def test_matches_value(self) -> None:
        """Test that a term matches any of its values."""
        term = libioc.Filter.Term("name", "foo,ba*")
        assert term.matches("foo") is True
        assert term.matches("bar") is True
        assert term.matches("baz") is True
        assert term.matches("qux") is False

    def test_matches_boolean_values_as_config_strings(self) -> None:
        """Test that boolean values match their config string form."""
        term = libioc.Filter.Term("basejail", "yes")
        assert term.matches(True) is True
        assert term.matches(False) is False


class TestTerms(object):
    """Run tests for a collection of filter terms."""

    def test_parses_key_value_terms(self) -> None:
        """Test that key=value terms parse into Term objects."""
        terms = libioc.Filter.Terms(["basejail=yes"])
        assert len(terms) == 1
        assert terms[0].key == "basejail"

    def test_unnamed_terms_filter_the_name_key(self) -> None:
        """Test that terms without a key filter by name."""
        terms = libioc.Filter.Terms(["web*"])
        assert terms.match_key("name", "webserver") is True
        assert terms.match_key("name", "database") is False
