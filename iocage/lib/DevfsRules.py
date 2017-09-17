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
import os.path
import re

import iocage.lib.errors
import iocage.lib.helpers


class DevfsRulesFilter:

    def __init__(self, source, active_filters=[]):
        self.source = source
        self.active_filters = active_filters

    def with_rule(self, rule):
        return DevfsRulesFilter(filter(
            lambda x: x.has_rule(rule),
            self.source
        ), self.active_filters + [rule])

    def with_include(self, rule_name):
        rule = f"add include ${rule_name}"
        return self.with_rule(rule)

    def create_ruleset(self, ruleset_name, ruleset_number):
        """
        Create a ruleset from the provided filters

        Args:

            ruleset_name (string):
                Name of the rule that get's created

            ruleset_number (int):
                Number of the rule that get's created
        """

        ruleset = DevfsRuleset(ruleset_name, ruleset_number)
        for line in self.active_filters:
            ruleset.append(line)
        return ruleset


class DevfsRuleset(list):
    """
    Representation of a devfs ruleset in the devfs.rules file

    DevfsRuleset instances behave like standard lists and can store strings
    that multiple lines (string)
    """

    PATTERN = re.compile(r"""^\[(?P<name>[a-z](?:[a-z0-9\-_]*[a-z0-9])?)=
                (?P<number>[0-9]+)\]\s*(?:\#\s*(?P<comment>.*))?$""", re.X)

    def __init__(self, value=None, number=None, comment=None):
        """
        Initialize DevfsRuleset

        Args:

            value (string): (optional)
                If specified in combination with a number, this parameter is
                interpreted as the ruleset name. Otherwise it is parsed with
                the expectation to find a [<name>=<number>] ruleset definition.

                When value is not specified or None, DevfsRuleset is assumed
                to be new or unspecified (cannot be exported before name and
                number were assigned at a later time)

            number (int): (optional)
                The number of the ruleset. Must be specified to export the
                ruleset, but is like the name not required to compare the
                ruleset with another
        """

        # when only one argument is passed, it's a line that need to be parsed
        if value is None and number is None:
            # name and number will be assigned later
            name = None
        elif number is None:
            name, number, comment = self._parse_line(value)
        else:
            name = int(value)

        self.name = name
        self.number = number
        self.comment = comment
        list.__init__(self)

    def has_rule(self, rule):
        """
        Returns true if the rule is part of the current ruleset

        Args:

            rule (string):
                The rule string to be compared with current rules of the
                ruleset instance
        """
        return rule in self

    def append(self, rule):
        if rule not in self:
            list.append(self, rule)

    def clone(self, source_ruleset):
        """
        Clones the rules from another ruleset

        Args:

            source_ruleset (iocage.lib.DevfsRules.DevfsRuleset):
                Ruleset to copy all rules from
        """
        for rule in source_ruleset:
            self.append(rule)

    def _parse_line(self, line):

        # marks beginning of a new ruleset
        ruleset_match = re.search(DevfsRuleset.PATTERN, line)
        if ruleset_match is not None:
            name = str(ruleset_match.group("name"))
            number = int(ruleset_match.group("number"))
            comment = ruleset_match.group("comment")
            return name, number, comment

        raise SyntaxError("DevfsRuleset line parsing failed")

    def __str__(self):
        ruleset_line = f"[{self.name}={self.number}]"
        if self.comment is not None:
            ruleset_line += f" # {self.comment}"
        output = [ruleset_line] + [str(x) for x in self]
        return "\n".join(output) + "\n"


class DevfsRules(list):
    """
    Abstraction for the hosts /etc/devfs.rules

    Read and edit devfs rules in a programmatic way.
    Restarts devfs service after applying changes.
    """

    def __init__(self, rules_file="/etc/devfs.rules", logger=None):
        """
        Initializes a DevfsRules manager for devfs.rules files

        Args:

            rules_file (string): (default=/etc/devfs.rules)
                Path of the devfs.rules file

            logger (iocage.Logger): (optional)
                Instance of the logger that is passed to occuring errors
        """

        self.logger = logger

        # index rulesets to find duplicated and provide easy access
        self._ruleset_number_index = {}
        self._ruleset_name_index = {}

        # remember all lines that were loaded from defaults (system)
        self._system_rule_lines = []

        list.__init__(self)

        # will automatically read from file - needs to be the last item
        self.rules_file = rules_file

    def append(self, ruleset, is_system_rule=False):
        """
        Add a DevfsRuleset to the list

        The rulesets added become indexed, so that lookups and duplication
        checks are easy and fast

        Args:

            ruleset (iocage.lib.DevfsRules.DevfsRuleset|string):
                The ruleset that gets added if it is not already in the list
        """

        next_line_index = len(self)

        if ruleset is None or isinstance(ruleset, str):
            list.append(self, ruleset)
            if is_system_rule is True:
                self._system_rule_lines.append(next_line_index)
            return ruleset

        if ruleset.name in self._ruleset_name_index.keys():
            raise iocage.lib.errors.DuplicateDevfsRuleset(
                reason=f"Ruleset named '{ruleset.name}' already present",
                devfs_rules_file=self.rules_file,
                logger=self.logger
            )

        if ruleset.number in self._ruleset_number_index.keys():
            raise iocage.lib.errors.DuplicateDevfsRuleset(
                reason=f"Ruleset number '{ruleset.number}' already present",
                devfs_rules_file=self.rules_file,
                logger=self.logger
            )

        # build indexes
        self._ruleset_number_index[ruleset.number] = next_line_index
        self._ruleset_name_index[ruleset.name] = next_line_index
        if is_system_rule is True:
            self._system_rule_lines.append(next_line_index)

        list.append(self, ruleset)
        return ruleset

    def new_ruleset(self, ruleset):
        """
        Append a new ruleset

        Similar to append(), but automatically assigns a new number

        Args:

            ruleset (iocage.lib.DevfsRules.DevfsRuleset):
                The new devfs ruleset that is going to be added

        Returns:

            int: The devfs ruleset number of the created ruleset
        """

        ruleset.number = self.next_number

        if ruleset.name is None:
            ruleset.name = f"iocage_auto_{ruleset.number}"

        self.append(ruleset)
        return ruleset.number

    def find_by_name(self, rule_name):
        return self._find_by_index(rule_name, self._ruleset_name_index)

    def find_by_number(self, rule_number):
        return self._find_by_index(rule_number, self._ruleset_number_index)

    def _find_by_index(self, rule_name, index):
        return self[index[rule_name]]

    @property
    def default_rules_file(self):
        return "/etc/defaults/devfs.rules"

    @property
    def rules_file(self):
        """
        Path of the devfs.rules file
        """
        return self._rules_file

    @rules_file.setter
    def rules_file(self, devfs_rules_path):
        """
        When setting a new devfs.rules source, it is read automatically
        """
        self._rules_file = devfs_rules_path
        try:
            self.read_rules()
        except FileNotFoundError:
            pass

    @property
    def next_number(self):
        """
        The next highest ruleset number that is available

        This counting includes the systems default devfs rulesets
        """
        return len(self._ruleset_name_index.keys()) + 1

    def read_rules(self):
        """
        Read existing devfs.rules file

        Existing devfs rules get reset and read from the rules_file
        """

        if self.logger:
            self.logger.debug(f"Reading devfs.rules from {self.rules_file}")

        self.clear()
        self._read_rules_file(self.default_rules_file, system=True)
        self._read_rules_file(self.rules_file)

    def _read_rules_file(self, file, system=False):

        f = open(file, "r")

        current_ruleset = None

        for line in f.readlines():

            line = line.strip().rstrip("\n")

            # add comments and empty lines as string
            if line.startswith("#") or (line == ""):
                self.append(line, is_system_rule=system)
                continue

            try:
                current_ruleset = DevfsRuleset(line)
                self.append(current_ruleset, is_system_rule=system)
                continue
            except SyntaxError:
                pass

            # the first item must be a ruleset
            if current_ruleset is None:
                raise iocage.lib.errors.InvalidDevfsRulesSyntax(
                    devfs_rules_file=self.rules_file,
                    reason="Rules must follow a ruleset declaration",
                    logger=self.logger
                )

            current_ruleset.append(line)

        f.close()

    def save(self):
        """
        Apply changes to the devfs.rules file

        Automatically restarts devfs service when the file was changed
        """

        content_before = None

        if os.path.isfile(self.rules_file):
            f = open(self.rules_file, "r+")
            content_before = f.read()
            f.seek(0)
        else:
            f = open(self.rules_file, "w")

        new_content = self.__str__()

        if content_before == new_content:
            if self.logger is not None:
                self.logger.verbose(
                    f"devfs.rules file {self.rules_file} unchanged"
                )
        else:
            if self.logger is not None:
                self.logger.verbose(
                    f"Writing devfs.rules to {self.rules_file}"
                )
                self.logger.spam(new_content, indent=1)

            f.write(new_content)
            f.truncate()
            self._restart_devfs_service()

        f.close()

    def _restart_devfs_service(self):
        """
        Restart devfs service after changing devfs.rules
        """
        if self.logger is not None:
            self.logger.debug("Restarting devfs service")
        iocage.lib.helpers.exec(["service", "devfs", "restart"])

    def __str__(self):
        """
        Output the devfs.rules content as string
        """

        out_lines = []
        for i, line in enumerate(self):
            if i not in self._system_rule_lines:
                out_lines.append(str(line))

        return "\n".join(out_lines)
