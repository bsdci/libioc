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
import libioc.Config.Jail
import libioc.Config.Jail.File
import libioc.Storage.Basejail


class FstabFsSpec(libioc.Types.AbsolutePath):
    """Enforces an AbsolutePath or special device name."""

    PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")

    def __init__(self, sequence: str) -> None:
        if self.PATTERN.match(sequence) is not None:
            self = str(sequence)  # type: ignore
        else:
            super().__init__(sequence)


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
            str(self.get("freq", 0)),
            str(self.get("passno", 0))
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
        if key == "source":
            dict.__setitem__(self, key, FstabFsSpec(value))
        elif key == "destination":
            dict.__setitem__(self, key, libioc.Types.AbsolutePath(value))
        elif key in ["type", "options", "freq", "passno", "comment"]:
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


class Fstab(collections.MutableSequence):
    """
    Fstab configuration file wrapper.

    This object allows to read, programatically edit and write fstab files.
    Bound to an iocage resource, the location of the /etc/fstab file is
    relative to the resource's root_dataset `<resource>/root`.
    """

    AUTO_COMMENT_IDENTIFIER = "iocage-auto"  # ToDo: rename to ioc-auto

    release: typing.Optional['libioc.Release.ReleaseGenerator']
    host: 'libioc.Host.HostGenerator'
    logger: 'libioc.Logger.Logger'
    _lines: typing.List[typing.Union[
        FstabLine,
        FstabCommentLine,
        FstabAutoPlaceholderLine
    ]]

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        host: typing.Optional['libioc.Host.HostGenerator']=None,
        file: str="/etc/fstab"
    ) -> None:

        self._lines = []
        self.logger = libioc.helpers_object.init_logger(self, logger)
        self.host = libioc.helpers_object.init_host(self, host)
        self.file = file
        # ToDo: could be lazy-loaded
        self.read_file()

    @property
    def path(self) -> str:
        """
        Absolute fstab file path.

        This is the file read from and written to.
        """
        return self.file

    def parse_lines(
        self,
        input_text: str,
        ignore_auto_created: bool=True,
        skip_destinations: typing.List[str]=[]
    ) -> None:
        """
        Parse the content of a fstab file.

        Args:

            input_text:
                The text content of an existing fstab file

            ignore_auto_created:
                Skips reading entries that were created by iocage

            exclude_destinations:
                List of destination strings that is skipped
        """
        list.clear(self._lines)

        line: str
        comment: typing.Optional[str]
        auto_comment_found: bool = False

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

            if destination in skip_destinations:
                continue

            destination = self.__replace_magic_path(destination)
            source = self.__replace_magic_path(source)

            new_line = FstabLine({
                "source": libioc.Types.Path(source),
                "destination": libioc.Types.AbsolutePath(destination),
                "type": fragments[2],
                "options": fragments[3],
                "freq": int(fragments[4]),
                "passno": int(fragments[5]),
                "comment": comment
            })

            self.add_line(new_line, skip_existing=True, auto_mount_jail=False)

    def __replace_magic_path(self, filepath: str) -> str:
        return filepath

    def read_file(self) -> None:
        """Read the fstab file."""
        if os.path.isfile(self.path):
            with open(self.path, "r", encoding="UTF-8") as f:
                self._read_file_handle(f)
                self.logger.debug(f"fstab loaded from {self.path}")

    def save(self) -> None:
        """Update or create the fstab file."""
        with open(self.path, "w", encoding="UTF-8") as f:
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
            f = open(self.path, "r+", encoding="UTF-8")
            self._read_file_handle(f)
            f.seek(0)
        else:
            f = open(self.path, "w", encoding="UTF-8")

        self._save_file_handle(f)
        f.close()

    def new_line(
        self,
        source: str,
        destination: str,
        type: str="nullfs",
        options: str="ro",
        freq: int=0,
        passno: int=0,
        comment: typing.Optional[str]=None,
        replace: bool=False,
        auto_create_destination: bool=False,
        auto_mount_jail: bool=True
    ) -> typing.Union[FstabLine, FstabCommentLine, FstabAutoPlaceholderLine]:
        """
        Append a new line to the fstab file.

        Use save() to write changes to the fstab file.
        """
        line = FstabLine({
            "source": source,
            "destination": destination,
            "type": type,
            "options": options,
            "freq": freq,
            "passno": passno,
            "comment": comment
        })

        return self.add_line(
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
    ) -> typing.Union[FstabLine, FstabCommentLine, FstabAutoPlaceholderLine]:
        """
        Directly append a FstabLine type.

        Use save() to write changes to the fstab file.
        """
        if any((
            isinstance(line, FstabLine),
            isinstance(line, FstabCommentLine),
            isinstance(line, FstabAutoPlaceholderLine),
        )) is False:
            raise TypeError(
                "line needs to be FstabLine, FstabCommentLine "
                f"or FstabAutoPlaceholderLine, but was {type(line).__name__}"
            )

        self._lines.append(line)
        return line

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
        source = deletion_target_line["source"]
        destination = deletion_target_line["destination"]

        self.logger.verbose(
            f"Deleting fstab entry: {source} -> {destination}"
        )
        real_index = self._get_real_index(index)
        self._lines.__delitem__(real_index)

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
                self._lines
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
        FstabCommentLine,
        FstabLine
    ]]:
        """
        Return an iterator of all printable lines.

        The output includes user configured and auto created lines for NullFS
        basejails. The previous position of auto-created entries is preserved.
        """
        return iter(self._lines)

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


class JailFstab(Fstab):
    """
    Fstab file abstraction of a Jails fstab file.

    The jails fstab file is stored in its main dataset.
    """

    jail: 'libioc.Jail.JailGenerator'

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        logger: typing.Optional['libioc.Logger.Logger']=None,
        host: typing.Optional['libioc.Host.HostGenerator']=None,
        file: str="fstab"
    ) -> None:
        self.jail = jail
        super().__init__(
            logger=logger,
            host=host,
            file=file
        )

    def parse_lines(
        self,
        input_text: str,
        ignore_auto_created: bool=True,
        skip_destinations: typing.List[str]=[]
    ) -> None:
        """
        Parse the content of a fstab file.

        Args:

            input_text:
                The text content of an existing fstab file

            ignore_auto_created:
                Skips reading entries that were created by iocage

            exclude_destinations:
                List of destination strings that is skipped
        """
        BasejailStorage = libioc.Storage.Basejail.BasejailStorage
        if isinstance(self.jail.storage_backend, BasejailStorage) is True:
            skip_destinations += list(map(
                lambda x: str(x[1]),
                self.jail.storage_backend.basejail_mounts
            ))
        Fstab.parse_lines(
            self,
            input_text=input_text,
            ignore_auto_created=ignore_auto_created,
            skip_destinations=skip_destinations
        )

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
        output: typing.List[
            typing.Union[
                FstabAutoPlaceholderLine,
                FstabBasejailLine,
                FstabCommentLine,
                FstabLine
            ]
        ] = []

        for line in self._lines:
            if isinstance(line, FstabAutoPlaceholderLine) is False:
                output.append(line)

        return iter(output)

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
            return self.file
        else:
            path = f"{self.jail.dataset.mountpoint}/{self.file}"
            self.jail.require_relative_path(path)
            return path

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
    ) -> typing.Union[FstabLine, FstabCommentLine, FstabAutoPlaceholderLine]:
        """
        Directly append a FstabLine type.

        Use save() to write changes to the fstab file.
        """
        if type(line) == FstabLine:
            if self.jail.is_path_relative(line["destination"]) is False:
                line = FstabLine(line)  # clone to prevent mutation
                line["destination"] = libioc.Types.AbsolutePath("/".join([
                    self.jail.root_path,
                    line["destination"].lstrip("/")
                ]))

        line_already_exists = self.__contains__(line)
        if line_already_exists:
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
                return line
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
            if self.jail.is_path_relative(line["destination"]) is False:
                _destination = libioc.Types.AbsolutePath("/".join([
                    self.jail.root_path,
                    line["destination"].strip("/")
                ]))
                self.jail.require_relative_path(_destination)
                line["destination"] = _destination

            libioc.helpers.require_no_symlink(str(line["destination"]))

            if auto_create_destination is True:
                _destination = line["destination"]
                if os.path.isdir(_destination) is False:
                    self.logger.verbose(
                        f"Auto-creating fstab destination {_destination}"
                    )
                    os.makedirs(line["destination"], 0o700)

            if (auto_mount_jail and self.jail.running) is True:
                destination = line["destination"]
                self.jail.require_relative_path(destination)
                self.logger.verbose(
                    f"auto-mount {destination}"
                )
                mount_command = [
                    "/sbin/mount",
                    "-o", line["options"],
                    "-t", line["type"],
                    line["source"],
                    destination
                ]
                libioc.helpers.exec(mount_command, logger=self.logger)
                _source = line["source"]
                _jail_name = self.jail.humanreadable_name
                self.logger.verbose(
                    f"{_source} mounted to running jail {_jail_name}"
                )

        self._lines.append(line)
        return line

    def update_release(
        self,
        release: typing.Optional['libioc.Release.ReleaseGenerator'] = None
    ) -> None:
        """Set a new release and save the updated file."""
        self.jail.release = release
        self.update_and_save()

    def __replace_magic_path(self, filepath: str) -> str:
        _backup_prefix = "backup:///"
        if filepath.startswith(_backup_prefix) is False:
            return filepath
        return "".join([
            self.jail.dataset.mountpoint,
            filepath[len(_backup_prefix):]
        ])

    def __delitem__(self, index: int) -> None:  # noqa: T484
        """Delete an FstabLine at the given index of the jails fstab file."""
        deletion_target_line = self.__getitem__(index)
        source = deletion_target_line["source"]
        destination = deletion_target_line["destination"]

        self.logger.verbose(
            f"Deleting fstab entry: {source} -> {destination}"
        )
        real_index = self._get_real_index(index)
        self._lines.__delitem__(real_index)

        if self.jail.running is True:
            self.logger.verbose(
                f"Unmounting {destination}"
            )
            libioc.helpers.umount(
                destination,
                force=True,
                logger=self.logger
            )

    def mount(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.MountFstab', None, None]:
        """Mount all fstab entries to the jail."""
        event = libioc.events.MountFstab(
            jail=self.jail,
            scope=event_scope
        )
        yield event.begin()
        try:
            list(self.unmount())
            for line in [x for x in self if isinstance(x, FstabLine)]:
                libioc.helpers.mount(
                    destination=line["destination"],
                    source=line["source"],
                    fstype=line["type"],
                    opts=[x.strip() for x in line["options"].split(",")]
                )
        except Exception as e:
            yield event.fail(e)
            raise e
        yield event.end()

    def unmount(
        self,
        event_scope: typing.Optional['libioc.events.Scope']=None
    ) -> typing.Generator['libioc.events.MountFstab', None, None]:
        """Unmount all fstab entries from the jail."""
        event = libioc.events.MountFstab(
            jail=self.jail,
            scope=event_scope
        )
        yield event.begin()
        has_unmounted_any = False
        try:
            for line in [x for x in self if isinstance(x, FstabLine)]:
                if os.path.ismount(line["destination"]) is False:
                    continue
                libioc.helpers.umount(line["destination"], force=True)
                has_unmounted_any = True
        except Exception as e:
            yield event.fail(e)
            raise e

        if has_unmounted_any is False:
            yield event.skip()
        else:
            yield event.end()


def _is_comment_line(text: str) -> bool:
    return text.strip().startswith("#") is True


def _is_empty_line(text: str) -> bool:
    return (text.strip() == "") is True


def _replace_path_prefix(text: str, pattern: str, replacement: str) -> str:
    if text.startswith(pattern) is False:
        return text
    return replacement + text[len(pattern):]
