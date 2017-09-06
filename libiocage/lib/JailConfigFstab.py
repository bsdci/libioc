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
import typing
import os

import libiocage.lib.helpers


class FstabLine(dict):
    def __init__(self, data: dict) -> None:
        keys = data.keys()
        if "comment" not in keys:
            data["comment"] = None
        dict.__init__(self, data)

    def __str__(self) -> str:
        return _line_to_string(self)

    def __hash__(self):
        return hash(self["destination"])


class JailConfigFstab(set):
    """

    Fstab configuration file wrapper

    This object allows to read, programatically edit and write fstab files.
    Bound to an iocage resource, the location of the /etc/fstab file is
    relative to the resource's root_dataset `<resource>/root`
    """
    AUTO_COMMENT_IDENTIFIER = "iocage-auto"

    def __init__(
        self,
        jail: 'libiocage.lib.Jail.JailGenerator',
        release: 'libiocage.lib.Release.ReleaseGenerator'=None,
        logger: 'libiocage.lib.Logger.Logger'=None,
        host: 'libiocage.lib.Host.HostGenerator'=None
    ) -> None:

        self.logger = libiocage.lib.helpers.init_logger(self, logger)
        self.host = libiocage.lib.helpers.init_host(self, host)
        self.jail = jail
        self.release = release
        set.__init__(self)

    @property
    def file_path(self) -> str:
        """
        Absolute fstab file path

        This is the file read from and written to.
        """

        return f"{self.jail.dataset.mountpoint}/fstab"

    def parse_lines(
        self,
        input: str,
        ignore_auto_created: bool=True
    ):
        """
        Parses the content of a fstab file

        Args:

            input:
                The text content of an existing fstab file

            ignore_auto_created:
                Skips reading entries that were created by iocage
        """

        set.clear(self)

        for line in input.split("\n"):

            try:
                line, comment = line.split("#", maxsplit=1)
                comment = comment.strip("# ")
                ignored_comment = JailConfigFstab.AUTO_COMMENT_IDENTIFIER
                if ignore_auto_created and (comment == ignored_comment):
                    continue
            except:
                comment = None

            line = line.strip()

            if line == "":
                continue

            fragments = line.split()
            if len(fragments) != 6:
                self.logger.log(
                    f"Invalid line in fstab file {self.file_path}"
                    " - skipping line"
                )
                continue

            destination = os.path.abspath(fragments[1])

            new_line = FstabLine({
                "source"     : fragments[0],
                "destination": fragments[1],
                "type"       : fragments[2],
                "options"    : fragments[3],
                "dump"       : fragments[4],
                "passnum"    : fragments[5],
                "comment"    : comment
            })

            if new_line in self:
                self.logger.error(
                    "Duplicate mountpoint in fstab: "
                    f"{destination} already mounted"
                )

            self.add_line(new_line)

    def read_file(self):
        if os.path.isfile(self.file_path):
            with open(self.file_path, "r") as f:
                self.parse_lines(f.read())
                f.close()
                self.logger.debug(f"fstab loaded from {self.file_path}")

    def save(self):
        self.logger.verbose(f"Writing fstab to {self.file_path}")
        with open(self.file_path, "w") as f:
            f.write(self.__str__())
            f.truncate()
            f.close()

        self.logger.verbose(
            f"{self.jail.dataset.mountpoint}/fstab written"
        )

    def add(self,
            source,
            destination,
            type="nullfs",
            options="ro",
            dump="0",
            passnum="0",
            comment=None):

        line = FstabLine({
            "source"     : source,
            "destination": destination,
            "type"       : type,
            "options"    : options,
            "dump"       : dump,
            "passnum"    : passnum,
            "comment"    : comment
        })

        return self.add_line(line)

    def add_line(self, line):

        self.logger.debug(f"Adding line to fstab: {line}")
        set.add(self, line)

    @property
    def basejail_lines(self) -> typing.List[dict]:

        if self.jail.config["basejail_type"] != "nullfs":
            return []

        basedirs = libiocage.lib.helpers.get_basedir_list(
            distribution_name=self.host.distribution.name
        )

        fstab_basejail_lines = []
        release_root_path = self.release.root_dataset.mountpoint
        for basedir in basedirs:

            source = f"{release_root_path}/{basedir}"
            destination = f"{self.jail.root_dataset.mountpoint}/{basedir}"
            fstab_basejail_lines.append({
                "source"     : source,
                "destination": destination,
                "type"       : "nullfs",
                "options"    : "ro",
                "dump"       : "0",
                "passnum"    : "0",
                "comment"    : "iocage-auto"
            })

        return fstab_basejail_lines

    def __str__(self):
        return "\n".join(map(
            _line_to_string,
            list(self)
        )) + "\n"

    def __iter__(self):
        fstab_lines = list(set.__iter__(self))
        fstab_lines += self.basejail_lines
        return iter(fstab_lines)

    def __contains__(self, value):
        for entry in self:
            if value["destination"] == entry["destination"]:
                return True
            else:
                return False


def _line_to_string(line):
    output = "\t".join([
        line["source"],
        line["destination"],
        line["type"],
        line["options"],
        line["dump"],
        line["passnum"]
    ])

    if line["comment"] is not None:
        comment = line["comment"]
        output += f" # {comment}"

    return output
