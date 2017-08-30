from typing import List, Union, Iterable
import re
import libiocage.lib.Jail


def match_filter(value: str, filter_string: str):
    escaped_characters = [".", "$", "^", "(", ")", "?"]
    for character in escaped_characters:
        filter_string = filter_string.replace(character, f"\\{character}")
    filter_string = filter_string.replace("*", ".*")
    filter_string = filter_string.replace("+", ".+")
    print
    pattern = f"^{filter_string}$"
    match = re.match(pattern, value)
    return match is not None


class Term(list):

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
        jail_value = jail.getstring(self.key)
        return self.matches(jail_value)

    def matches(self, value: str) -> bool:
        """
        Returns True if the value matches the term
        """
        for filter_value in self:
            if match_filter(value, filter_value):
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

    @property
    def only_by_name(self) -> bool:
        """
        True if all terms match by name only
        """
        return all([x.key == "name" for x in self])

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

    def _parse_term(self, user_input: Iterable[str]) -> List[Term]:

        terms = []

        for user_term in user_input:
            try:
                prop, value = user_input.split("=", maxsplit=1)
            except:
                prop = "name"
                value = user_input

            terms.append(Term(prop, value))

        return terms
