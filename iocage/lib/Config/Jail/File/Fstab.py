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
import collections
import os.path
import random

import iocage.lib.helpers
import iocage.lib.Config.Jail.File.Prototype


class FstabLine(dict):

    def __init__(self, data: dict) -> None:
        keys = data.keys()
        dict.__init__(self, data)
        if "comment" not in keys:
            self["comment"] = None
        for key in keys:
            self[key] = data[key]

    def __str__(self) -> str:
        output = "\t".join([
            self["source"],
            self["destination"],
            self["type"],
            self["options"],
            self["dump"],
            self["passnum"]
        ])

        if self["comment"] is not None:
            comment = self["comment"]
            output += f" # {comment}"

        return output

    def __hash__(self):
        return hash(self["destination"])


class FstabBasejailLine(FstabLine):
    pass


class FstabCommentLine(dict):

    def __init__(self, data: dict) -> None:
        if "line" not in data:
            raise ValueError("malformed input")
        dict.__init__(self)
        self["line"] = data["line"]

    def __str__(self) -> str:
        return str(self["line"])

    def __hash__(self):
        return hash('%030x' % random.randrange(16**32))  # nosec: B311


class FstabAutoPlaceholderLine(dict):
    """
    A placeholder for auto-created fstab lines
    """

    def __init__(self, data: dict={}) -> None:
        dict.__init__(self)

    def __str__(self) -> str:
        raise NotImplementedError("this is a virtual fstab line")

    def __hash__(self):
        return hash(None)


class Fstab(
    collections.MutableSequence,
    iocage.lib.Config.Jail.File.Prototype.ResourceConfigFile
):
    """

    Fstab configuration file wrapper

    This object allows to read, programatically edit and write fstab files.
    Bound to an iocage resource, the location of the /etc/fstab file is
    relative to the resource's root_dataset `<resource>/root`
    """
    AUTO_COMMENT_IDENTIFIER = "iocage-auto"

    release: typing.Optional['iocage.lib.Release.ReleaseGenerator']
    host: 'iocage.lib.Host.HostGenerator'
    logger: 'iocage.lib.Logger.Logger'
    jail: 'iocage.lib.Jail.JailGenerator'
    _lines: typing.List[typing.Union[
        FstabLine,
        FstabCommentLine,
        FstabAutoPlaceholderLine
    ]] = []

    def __init__(
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        release: typing.Optional['iocage.lib.Release.ReleaseGenerator']=None,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None,
        host: typing.Optional['iocage.lib.Host.HostGenerator']=None,
        file: typing.Optional[str]="fstab"
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.host = iocage.lib.helpers.init_host(self, host)
        self.jail = jail
        self.release = release
        self.file = file

    @property
    def path(self) -> str:
        """
        Absolute fstab file path

        This is the file read from and written to.
        """
        path = f"{self.jail.dataset.mountpoint}/{self.file}"
        self._require_path_relative_to_resource(
            filepath=path,
            resource=self.jail
        )
        return path

    def parse_lines(
        self,
        input_text: str,
        ignore_auto_created: bool=True
    ) -> None:
        """
        Parses the content of a fstab file

        Args:

            input_text:
                The text content of an existing fstab file

            ignore_auto_created:
                Skips reading entries that were created by iocage
        """

        list.clear(self._lines)

        line: str
        comment: typing.Optional[str]
        auto_comment_found: bool = False
        basejail_destinations = map(
            lambda x: str(x['destination']),
            self.basejail_lines
        )

        for line in input_text.rstrip("\n").split("\n"):

            if _is_comment_line(line) or _is_empty_line(line):
                self.add_line(FstabCommentLine({
                    "line": line
                }))
                continue

            try:
                line, comment = line.split("#", maxsplit=1)
                comment = comment.strip("# ")
                ignored_comment = Fstab.AUTO_COMMENT_IDENTIFIER
                if ignore_auto_created and (comment == ignored_comment):
                    if auto_comment_found is False:
                        auto_comment_found = True
                        self.add_line(FstabAutoPlaceholderLine({}))
                    continue
                if comment == "":
                    comment = None

            except ValueError:
                comment = None

            line = line.strip()

            if line == "":
                continue

            fragments = line.split()
            if len(fragments) != 6:
                self.logger.log(
                    f"Invalid line in fstab file {self.path}"
                    " - skipping line"
                )
                continue

            destination = os.path.abspath(fragments[1])

            # skip lines with destinations overlapping self.basejail_lines
            if destination in basejail_destinations:
                continue

            new_line = FstabLine({
                "source": fragments[0],
                "destination": destination,
                "type": fragments[2],
                "options": fragments[3],
                "dump": fragments[4],
                "passnum": fragments[5],
                "comment": comment
            })

            if new_line in self._lines:
                self.logger.error(
                    "Duplicate mountpoint in fstab: "
                    f"{destination} already mounted"
                )

            self.add_line(new_line)

    def read_file(self) -> None:
        if os.path.isfile(self.path):
            with open(self.path, "r") as f:
                self._read_file_handle(f)
                self.logger.debug(f"fstab loaded from {self.path}")

    def save(self) -> None:
        with open(self.path, "w") as f:
            self._save_file_handle(f)
            self.logger.verbose(f"{self.path} written")

    def _save_file_handle(self, f) -> None:
        f.write(self.__str__())
        f.truncate()

    def _read_file_handle(self, f) -> None:
        self.parse_lines(f.read())

    def update_and_save(
        self
    ) -> None:

        if os.path.isfile(self.path):
            f = open(self.path, "r+")
            self._read_file_handle(f)
            f.seek(0)
        else:
            f = open(self.path, "w")

        self._save_file_handle(f)
        f.close()

    def update_release(
        self,
        release: typing.Optional['iocage.lib.Release.ReleaseGenerator'] = None
    ) -> None:
        """
        Set a new release and save the updated file
        """
        self.release = release
        self.update_and_save()

    def new_line(
        self,
        source,
        destination,
        fs_type="nullfs",
        options="ro",
        dump="0",
        passnum="0",
        comment=None
    ) -> None:

        line = FstabLine({
            "source": source,
            "destination": destination,
            "type": fs_type,
            "options": options,
            "dump": dump,
            "passnum": passnum,
            "comment": comment
        })

        self.add_line(line)

    def add_line(
        self,
        line: typing.Union[
            FstabLine,
            FstabCommentLine,
            FstabAutoPlaceholderLine
        ]
    ) -> None:

        if isinstance(line, FstabAutoPlaceholderLine):
            self.logger.debug("Setting fstab auto-creation placeholder")
        else:
            self.logger.debug(f"Adding line to fstab: {line}")

        for existing_line in self.__iter__():
            if hash(existing_line) == hash(line):
                raise iocage.lib.errors.FstabDestinationExists(
                    mountpoint=line["destination"],
                    logger=self.logger
                )

        self._lines.append(line)

    @property
    def basejail_lines(self) -> typing.List[FstabBasejailLine]:

        if self.release is None:
            return []

        if self.jail.config["basejail_type"] != "nullfs":
            return []

        basedirs = iocage.lib.helpers.get_basedir_list(
            distribution_name=self.host.distribution.name
        )

        fstab_basejail_lines = []
        release_root_path = self.release.root_dataset.mountpoint
        for basedir in basedirs:

            source = f"{release_root_path}/{basedir}"
            destination = f"{self.jail.root_dataset.mountpoint}/{basedir}"
            fstab_basejail_lines.append(FstabBasejailLine({
                "source": source,
                "destination": destination,
                "type": "nullfs",
                "options": "ro",
                "dump": "0",
                "passnum": "0",
                "comment": self.AUTO_COMMENT_IDENTIFIER
            }))

        return fstab_basejail_lines

    def __str__(self) -> str:
        return "\n".join(map(
            str,
            list(self)
        ))

    def __len__(self):
        return list.__len__(list(self.__iter__()))

    def __delitem__(self, index):
        real_index = self._get_real_index(index)
        self._lines.__delitem__(real_index)

    def __getitem__(self, index):
        return list(self.__iter__())[index]

    def __setitem__(
        self,
        index,
        value
    ):
        real_index = self._get_real_index(index)
        self._lines.__setitem__(real_index, value)

    def insert(
        self,
        index: int,
        value: typing.Union[
            FstabLine,
            FstabCommentLine,
            FstabAutoPlaceholderLine
        ]
    ) -> None:

        target_line = list(self.__iter__())[index]

        if isinstance(target_line, FstabBasejailLine):
            # find FstabAutoPlaceholderLine instead
            line = list(filter(
                lambda x: isinstance(x, FstabAutoPlaceholderLine),
                self._line
            ))[0]
            real_index = self._lines.index(line)
        else:
            real_index = self._get_real_index(index)

        self._lines.insert(real_index, value)

    def _get_real_index(self, index: int) -> int:
        target_line = list(self.__iter__())[index]
        if isinstance(target_line, FstabBasejailLine):
            raise iocage.lib.errors.VirtualFstabLineHasNoRealIndex(
                logger=self.logger
            )
        return self._lines.index(target_line)

    def __iter__(self) -> typing.Iterator[typing.Union[
        FstabAutoPlaceholderLine,
        FstabBasejailLine,
        FstabCommentLine,
        FstabLine
    ]]:
        """
        Returns an iterator of all printable lines

        The output includes user configured and auto created lines for NullFS
        basejails. The previous position of auto-created entries is preserved.
        """
        basejail_lines_added = False
        output: typing.List[
            typing.Union[
                FstabAutoPlaceholderLine,
                FstabBasejailLine,
                FstabCommentLine,
                FstabLine
            ]
        ] = []

        for line in self._lines:
            if isinstance(line, FstabAutoPlaceholderLine):
                if basejail_lines_added is False:
                    output += self.basejail_lines
                    basejail_lines_added = True
            else:
                output.append(line)

        if basejail_lines_added is False:
            output = self.basejail_lines + self._lines  # noqa: T484

        return iter(output)

    def __contains__(self, value: typing.Any) -> bool:
        for entry in self:
            if value["destination"] == entry["destination"]:
                return True
            else:
                return False
        return False

    def replace_path(self, pattern: typing.Pattern, replacement: str) -> None:
        """
        Replaces a given path in all fstab entries (source or destination)
        """
        for i, line in enumerate(self._lines):
            if not isinstance(line, FstabLine):
                continue
            line["source"] = pattern.sub(replacement, line["source"])
            line["destination"] = pattern.sub(replacement, line["destination"])
            self._lines[i] = line


def _is_comment_line(text: str) -> bool:
    return text.strip().startswith("#") is True


def _is_empty_line(text: str) -> bool:
    return (text.strip() == "") is True
