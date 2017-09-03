# Copyright (c) 2014-2017, iocage
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
from typing import List, Union, Iterable
import re
import libiocage.lib.Jail
import libiocage.lib.errors


def match_filter(value: str, filter_string: str):
    escaped_characters = [".", "$", "^", "(", ")", "?"]
    for character in escaped_characters:
        filter_string = filter_string.replace(character, f"\\{character}")
    filter_string = filter_string.replace("*", ".*")
    filter_string = filter_string.replace("+", ".+")
    pattern = f"^{filter_string}$"
    match = re.match(pattern, value)
    return match is not None


class Term(list):

    glob_characters = ["*", "+"]

    def __init__(self, key, values=list()):
        self.key = key

        if values is None:
            raise TypeError("Values may not be empty")
        elif isinstance(values, str):
            data = self._split_filter_values(values)
        else:
            data = [values]

        list.__init__(self, data)

    def matches_jail(self, jail: libiocage.lib.Jail.JailGenerator) -> bool:
        return self.matches(jail.getstring(self.key))

    def matches(self, value: str) -> bool:
        """
        Returns True if the value matches the term
        """
        for filter_value in self:

            if match_filter(value, filter_value):
                return True

            # match against humanreadable names as well
            has_humanreadble_length = (len(filter_value) == 8)
            has_no_globs = not self._filter_string_has_globs(filter_value)
            if (has_humanreadble_length and has_no_globs) is True:
                shortname = libiocage.lib.helpers.to_humanreadable_name(value)
                if match_filter(shortname, filter_value):
                    return True

        return False

    def _filter_string_has_globs(self, filter_string: str) -> bool:
        for glob in self.glob_characters:
            if glob in filter_string:
                return True
        return False

    def _split_filter_values(self, user_input: str) -> List[str]:
        values = []
        escaped_comma_blocks = map(
            lambda block: block.split(","),
            user_input.split("\\,")
        )
        for block in escaped_comma_blocks:
            n = len(values)
            if n > 0:
                index = n - 1
                values[index] += f",{block[0]}"
            else:
                values.append(block[0])
            if len(block) > 1:
                values += block[1:]
        return values

    def _validate_name_filter_string(self, filter_string: str) -> bool:

        globs = self.glob_characters

        # Allow glob only filters
        if (len(filter_string) == 1) and (filter_string in globs):
            return True

        # replace all glob charaters in user input
        filter_string_without_globs = ""
        for i, char in enumerate(filter_string):
            if char not in globs:
                filter_string_without_globs += char

        return libiocage.lib.helpers.validate_name(filter_string_without_globs)


class Terms(list):
    """
    A group of jail filter terms.

    Each item in this group must match for a jail to pass the filter.
    This can be interpreted as logical AND
    """

    def __init__(self, terms: Iterable[Union[Term, str]]=None):

        data = []

        if terms is not None:

            for term in terms:
                if isinstance(term, str):
                    data += self._parse_term(term)
                elif isinstance(term, Term):
                    data.append(term)

        list.__init__(self, data)

    def match_jail(self, jail: libiocage.lib.Jail.JailGenerator) -> bool:
        """
        Returns True if all Terms match the jail
        """

        for term in self:
            if term.matches_jail(jail) is False:
                return False

        return True

    def match_key(self, key: str, value: str) -> bool:
        """
        Check if a value matches for a given key

        Returns True if the given value matches all terms for the specified key
        Returns Fals if one of the terms does not match
        """
        for term in self:

            if term.key != key:
                continue

            if term.matches(value) is False:
                return False

        return True

    def _parse_term(self, user_input: str) -> List[Term]:

        terms = []

        try:
            prop, value = user_input.split("=", maxsplit=1)
        except:
            prop = "name"
            value = user_input

        terms.append(Term(prop, value))

        return terms
