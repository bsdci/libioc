# Copyright (c) 2017-2019, Stefan Grönke
# Copyright (c) 2014-2018, iocage
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
"""Manage fstab files."""
import typing
import collections
import os.path
import random
import re

import libioc.helpers
import libioc.helpers_object
import libioc.Types
import libioc.Config.Jail.File


class FstabLine(dict):
    """Model a line of an fstab file."""

    def __init__(self, data: dict) -> None:
        keys = data.keys()
        dict.__init__(self, data)
        if "comment" not in keys:
            self["comment"] = None
        for key in keys:
            self[key] = data[key]

    def _escape(self, key: str) -> str:
        return str(self[key].replace(" ", r"\ "))

    def __str__(self) -> str:
        """Serialize the data into an fstab line string."""
        output = "\t".join([
            self._escape("source"),
            self._escape("destination"),
            self.get("type", "nullfs"),
            self.get("options", "ro"),
            self.get("dump", "0"),
            self.get("passnum", "0")
        ])

        if self["comment"] is not None:
            comment = self["comment"]
            output += f" # {comment}"

        return output

    def __hash__(self) -> int:
        """Compare FstabLine by its destination."""
        return hash(self["destination"])

    def __setitem__(
        self,
        key: str,
        value: typing.Union[str, libioc.Types.AbsolutePath]
    ) -> None:
        """Set an item of the FstabLine."""
        if (key == "source") or (key == "destination"):
            if isinstance(value, str) is True:
                absolute_path = libioc.Types.AbsolutePath(value)
            elif isinstance(value, libioc.Types.AbsolutePath) is True:
                absolute_path = value
            else:
                raise ValueError("String or AbsolutePath expected")
            dict.__setitem__(self, key, absolute_path)
        elif key in ["type", "options", "dump", "passnum", "comment"]:
            dict.__setitem__(self, key, value)
        else:
            raise KeyError(f"Invalid FstabLine key: {key}")


class FstabBasejailLine(FstabLine):
    """Model a fstab line automatically created by a NullFS basejail."""

    pass


class FstabMaintenanceLine(FstabLine):
    """Model a fstab line automatically created for jail launch scripts."""

    pass


class FstabCommentLine(dict):
    """Model a fstab comment line (beginning with #)."""

    def __init__(self, data: dict) -> None:
        if "line" not in data:
            raise ValueError("malformed input")
        dict.__init__(self)
        self["line"] = data["line"]

    def __str__(self) -> str:
        """Return the untouched comment line string."""
        return str(self["line"])

    def __hash__(self) -> int:
        """
        Return a random hash value.

        The same comment might appear twice for a reason.
        """
        return hash('%030x' % random.randrange(16**32))  # nosec: B311


class FstabAutoPlaceholderLine(dict):
    """A placeholder for auto-created fstab lines."""

    def __init__(self, data: dict={}) -> None:
        dict.__init__(self)

    def __str__(self) -> str:
        """Never print virtual lines."""
        raise NotImplementedError("this is a virtual fstab line")

    def __hash__(self) -> int:
        """Do not return a hash because placeholders have none."""
        return hash(None)


class Fstab(
    libioc.Config.Jail.File.ResourceConfig,
    collections.MutableSequence
):
    """
    Fstab configuration file wrapper.

    This object allows to read, programatically edit and write fstab files.
    Bound to an iocage resource, the location of the /etc/fstab file is
    relative to the resource's root_dataset `<resource>/root`.
    """

    AUTO_COMMENT_IDENTIFIER = "iocage-auto"

    release: typing.Optional['libioc.Release.ReleaseGenerator']
    host: 'libioc.Host.HostGenerator'
    logger: 'libioc.Logger.Logger'
    jail: 'libioc.Jail.JailGenerator'
    _lines: typing.List[typing.Union[
        FstabLine,
        FstabCommentLine,
        FstabAutoPlaceholderLine
    ]] = []

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        release: typing.Optional['libioc.Release.ReleaseGenerator']=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        host: typing.Optional['libioc.Host.HostGenerator']=None,
        file: str="fstab"
    ) -> None:

        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.host = libioc.helpers_object.init_host(self, host)
        self.jail = jail
        self.release = release
        self.file = file
        # ToDo: could be lazy-loaded
        self.read_file()

    @property
    def path(self) -> str:
        """
        Absolute fstab file path.

        This is the file read from and written to.

        When the path begins with a / it is assumed to be absolute, so that
        the jails dataset mountpoint is not used as path prefix. This is useful
        when moving around jail backups.
        """
        if self.file.startswith("/") is True:
            path = self.file
        else:
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
        Parse the content of a fstab file.

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

        for line in input_text.rstrip("\n").splitlines():
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

            line = re.sub(r"\s\s*", " ", line)
            line = re.sub(r"([^\\\\])\s", r"\g<1>\n", line)
            line = line.replace("\\ ", " ")

            fragments = line.splitlines()
            if len(fragments) != 6:
                self.logger.log(
                    f"Invalid line in fstab file {self.path}"
                    " - skipping line"
                )
                continue

            source = fragments[0].strip()
            destination = fragments[1].strip()

            # skip lines with destinations overlapping self.basejail_lines
            if destination in basejail_destinations:
                continue

            _backup_prefix = "backup:///"
            if destination.startswith(_backup_prefix) is True:
                destination = "".join([
                    self.jail.dataset.mountpoint,
                    destination[len(_backup_prefix):]
                ])
            if source.startswith(_backup_prefix) is True:
                source = "".join([
                    self.jail.dataset.mountpoint,
                    source[len(_backup_prefix):]
                ])

            new_line = FstabLine({
                "source": libioc.Types.AbsolutePath(source),
                "destination": libioc.Types.AbsolutePath(destination),
                "type": fragments[2],
                "options": fragments[3],
                "dump": fragments[4],
                "passnum": fragments[5],
                "comment": comment
            })

            self.add_line(new_line, skip_existing=True, auto_mount_jail=False)

    def read_file(self) -> None:
        """Read the fstab file."""
        if os.path.isfile(self.path):
            with open(self.path, "r") as f:
                self._read_file_handle(f)
                self.logger.debug(f"fstab loaded from {self.path}")

    def save(self) -> None:
        """Update or create the fstab file."""
        with open(self.path, "w") as f:
            self._save_file_handle(f)
            self.logger.verbose(f"{self.path} written")

    def _save_file_handle(self, f: typing.TextIO) -> None:
        f.write(self.__str__())
        f.truncate()

    def _read_file_handle(self, f: typing.TextIO) -> None:
        self.parse_lines(f.read())

    def update_and_save(
        self
    ) -> None:
        """Read file and then write changes."""
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
        release: typing.Optional['libioc.Release.ReleaseGenerator'] = None
    ) -> None:
        """Set a new release and save the updated file."""
        self.release = release
        self.update_and_save()

    def new_line(
        self,
        source: str,
        destination: str,
        type: str="nullfs",
        options: str="ro",
        dump: str="0",
        passnum: str="0",
        comment: typing.Optional[str]=None,
        replace: bool=False,
        auto_create_destination: bool=False,
        auto_mount_jail: bool=True
    ) -> None:
        """
        Append a new line to the fstab file.

        Use save() to write changes to the fstab file.
        """
        line = FstabLine({
            "source": source,
            "destination": destination,
            "type": type,
            "options": options,
            "dump": dump,
            "passnum": passnum,
            "comment": comment
        })

        self.add_line(
            line=line,
            replace=replace,
            auto_create_destination=auto_create_destination,
            auto_mount_jail=auto_mount_jail
        )

    def add_line(
        self,
        line: typing.Union[
            FstabLine,
            FstabCommentLine,
            FstabAutoPlaceholderLine
        ],
        skip_existing: bool=False,
        replace: bool=False,
        auto_create_destination: bool=False,
        auto_mount_jail: bool=True
    ) -> None:
        """
        Directly append a FstabLine type.

        Use save() to write changes to the fstab file.
        """
        if self.__contains__(line):
            destination = line["destination"]
            if replace is True:
                self.logger.verbose(
                    f"Replacing fstab line with destination {destination}"
                )
                del self[self.index(line)]
            elif skip_existing is True:
                self.logger.verbose(
                    f"Skipping existing fstab line: {line}"
                )
                return
            else:
                raise libioc.errors.FstabDestinationExists(
                    mountpoint=destination,
                    logger=self.logger
                )
        else:
            if isinstance(line, FstabAutoPlaceholderLine):
                self.logger.debug("Setting fstab auto-creation placeholder")
            else:
                self.logger.debug(f"Adding line to fstab: {line}")

        if type(line) == FstabLine:
            # destination is always relative to the jail resource
            if line["destination"].startswith(self.jail.root_path) is False:
                line["destination"] = libioc.Types.AbsolutePath("/".join([
                    self.jail.root_path,
                    line["destination"].strip("/")
                ]))

            libioc.helpers.require_no_symlink(str(line["destination"]))

            if auto_create_destination is True:
                _destination = line["destination"]
                if os.path.isdir(_destination) is False:
                    self.logger.verbose(
                        f"Auto-creating fstab destination {_destination}"
                    )
                    os.makedirs(line["destination"], 0o700)

            if (auto_mount_jail and self.jail.running) is True:
                mount_command = [
                    "/sbin/mount",
                    "-o", line["options"],
                    "-t", line["type"],
                    line["source"],
                    line["destination"]
                ]
                libioc.helpers.exec(mount_command, logger=self.logger)
                _source = line["source"]
                _jail_name = self.jail.humanreadable_name
                self.logger.verbose(
                    f"{_source} mounted to running jail {_jail_name}"
                )

        self._lines.append(line)

    def index(
        self,
        line: typing.Union[
            FstabLine,
            FstabCommentLine,
            FstabAutoPlaceholderLine
        ],
        start: typing.Optional[int]=None,
        end: typing.Optional[int]=None
    ) -> int:
        """Find the index position of a FstabLine in the Fstab instance."""
        i: int = 0
        items = list(self)
        start = 0 if (start is None) else start
        end = (len(items) - 1) if (end is None) else end
        for existing_line in items:
            if (i >= start) and (hash(existing_line) == hash(line)):
                return i
            i += 1
            if (i > end):
                break
        raise ValueError("Fstab line does not exist")

    def __contains__(  # noqa: T484
        self,
        line: typing.Union[
            FstabLine,
            FstabCommentLine,
            FstabAutoPlaceholderLine
        ]
    ) -> bool:
        """Return True when the FstabLine already exists."""
        try:
            self.index(line)
            return True
        except ValueError:
            return False

    @property
    def maintenance_lines(self) -> typing.List[FstabMaintenanceLine]:
        """Auto-generate lines that are required for jail start and stop."""
        return [FstabMaintenanceLine(dict(
            source=libioc.Types.AbsolutePath(self.jail.launch_script_dir),
            destination=libioc.Types.AbsolutePath(
                f"{self.jail.root_dataset.mountpoint}/.iocage"
            ),
            options="ro",
            type="nullfs",
            dump="0",
            passnum="0",
            comment=self.AUTO_COMMENT_IDENTIFIER
        ))]

    @property
    def basejail_lines(self) -> typing.List[FstabBasejailLine]:
        """
        Auto-generate lines of NullFS basejails.

        When a jail is a NullFS basejail, this list represent the corresponding
        fstab lines that mount the release.
        """
        if self.release is None:
            return []

        if self.jail.config["basejail_type"] != "nullfs":
            return []

        basedirs = libioc.helpers.get_basedir_list(
            distribution_name=self.host.distribution.name
        )

        fstab_basejail_lines = []
        release_root_path = "/".join([
            self.release.root_dataset.mountpoint,
            f".zfs/snapshot/{self.jail.release_snapshot.snapshot_name}"
        ])
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
        """Return the entire content of the fstab file as string."""
        return "\n".join(map(
            str,
            list(self)
        ))

    def __len__(self) -> int:
        """Return the number of lines in the fstab file."""
        return list.__len__(list(self.__iter__()))

    def __delitem__(self, index: int) -> None:  # noqa: T484
        """Delete an FstabLine at the given index."""
        deletion_target_line = self.__getitem__(index)
        jail_name = self.jail.humanreadable_name
        source = deletion_target_line["source"]
        destination = deletion_target_line["destination"]

        self.logger.verbose(
            f"Deleting fstab entry from jail {jail_name}: "
            f"{source} -> {destination}"
        )
        real_index = self._get_real_index(index)
        self._lines.__delitem__(real_index)

        if self.jail.running is True:
            self.logger.verbose(
                f"Unmounting {destination} from running jail {jail_name}"
            )
            libioc.helpers.umount(
                destination,
                force=True,
                logger=self.logger
            )

    def __getitem__(self, index: int) -> typing.Union[  # noqa: T484
        FstabLine,
        FstabCommentLine,
        FstabAutoPlaceholderLine
    ]:
        """Get the FstabLine at the given index."""
        return list(self.__iter__())[index]

    def __setitem__(  # noqa: T484
        self,
        index: int,
        value: typing.Union[
            FstabLine,
            FstabCommentLine,
            FstabAutoPlaceholderLine
        ]
    ) -> None:
        """Set or overwrite the FstabLine at the given index."""
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
        """
        Insert a line at a given position.

        Args:

            index:
                The numeric line insertion position

            value:
                A FstabLine, Comment or Placeholder
        """
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
            raise libioc.errors.VirtualFstabLineHasNoRealIndex(
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
        Return an iterator of all printable lines.

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
                    output += self.maintenance_lines
                    basejail_lines_added = True
            else:
                output.append(line)

        if basejail_lines_added is False:
            _basejail = self.basejail_lines
            _maintenance = self.maintenance_lines
            output = _basejail + _maintenance + self._lines  # noqa: T484

        return iter(output)

    def replace_path(self, pattern: str, replacement: str) -> None:
        """Replace a path in all fstab entries (source or destination)."""
        for i, line in enumerate(self._lines):
            if not isinstance(line, FstabLine):
                continue
            line["source"] = _replace_path_prefix(
                line["source"],
                pattern,
                replacement
            )
            line["destination"] = _replace_path_prefix(
                line["destination"],
                pattern,
                replacement
            )
            self._lines[i] = line


def _is_comment_line(text: str) -> bool:
    return text.strip().startswith("#") is True


def _is_empty_line(text: str) -> bool:
    return (text.strip() == "") is True


def _replace_path_prefix(text: str, pattern: str, replacement: str) -> str:
    if text.startswith(pattern) is False:
        return text
    return replacement + text[len(pattern):]
