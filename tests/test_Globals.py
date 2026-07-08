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
"""Unit tests for the global configuration defaults."""
import ast
import collections
import inspect
import typing

import libioc.Config.Jail.Globals


class TestGlobalDefaults(object):
    """Run tests for the global configuration defaults."""

    def test_defaults_are_free_of_duplicate_keys(self) -> None:
        """Test that no dict literal in the module repeats a key."""
        source = inspect.getsource(libioc.Config.Jail.Globals)
        dict_literals = [
            node for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Dict)
        ]
        assert len(dict_literals) > 0

        for dict_literal in dict_literals:
            keys: typing.List[str] = [
                key.value for key in dict_literal.keys
                if isinstance(key, ast.Constant)
            ]
            duplicate_keys = [
                key
                for (key, count) in collections.Counter(keys).items()
                if count > 1
            ]
            assert duplicate_keys == []
