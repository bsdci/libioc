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
"""ioc logging module."""
import os
import sys
import typing

import libioc.errors


class LogEntry:
    """A single log entry."""

    def __init__(
        self,
        message: str,
        level: str,
        indent: int=0,
        logger: 'libioc.Logger.Logger'=None
    ) -> None:
        self.message = message
        self.level = level
        self.indent = indent
        self.logger = logger

    def edit(
        self,
        message: str=None,
        indent: int=None
    ) -> None:
        """Change the log entry."""
        if self.logger is None:
            raise libioc.errors.CannotRedrawLine(
                reason="No logger available"
            )

        if message is not None:
            self.message = message

        if indent is not None:
            self.indent = indent

        self.logger.redraw(self)

    def __len__(self) -> int:
        """Return the number of lines of the log entry."""
        return len(self.message.splitlines())


class Logger:
    """ioc Logger module."""

    COLORS = (
        "black",
        "red",
        "green",
        "yellow",
        "blue",
        "margenta",
        "cyan",
        "white",
    )

    LOG_LEVEL_SETTINGS: typing.Dict[
        str,
        typing.Dict[str, typing.Optional[
            typing.Union[str, bool]]
        ]
    ] = {
        "screen": {"color": None},
        "info": {"color": None},
        "notice": {"color": "magenta"},
        "verbose": {"color": "blue"},
        "spam": {"color": "green"},
        "critical": {"color": "red", "bold": True},
        "error": {"color": "red"},
        "debug": {"color": "green"},
        "warn": {"color": "yellow"}
    }

    LOG_LEVELS = (
        "critical",
        "error",
        "warn",
        "info",
        "notice",
        "verbose",
        "debug",
        "spam",
        "screen"
    )

    __INDENT_PREFIX = "  "

    PRINT_HISTORY: typing.List[LogEntry] = []

    def __init__(
            self,
            print_level: typing.Optional[str]=None,
            log_directory: str="/var/log/iocage"
    ) -> None:
        self._print_level = print_level
        self._set_log_directory(log_directory)

    @property
    def default_print_level(self) -> str:
        """Return the static default print level."""
        return "info"

    @property
    def print_level(self) -> str:
        """Return the configured or default print level."""
        if self._print_level is None:
            return self.default_print_level
        else:
            return self._print_level

    @print_level.setter
    def print_level(self, value: str) -> None:
        """Set a custom print level to override the default."""
        if value not in Logger.LOG_LEVELS:
            raise libioc.errors.InvalidLogLevel(
                log_level=value,
                logger=self
            )
        self._print_level = value

    def _set_log_directory(self, log_directory: str) -> None:
        self.log_directory = os.path.abspath(log_directory)
        if not os.path.isdir(log_directory):
            self._create_log_directory()
        self.log(f"Log directory set to '{log_directory}'", level="spam")

    def log(
        self,
        message: str,
        level: str="info",
        indent: int=0
    ) -> LogEntry:
        """Add a log entry."""
        log_entry = LogEntry(
            message=message,
            level=level,
            indent=indent,
            logger=self
        )

        if self._should_print_log_entry(log_entry):
            self._print_log_entry(log_entry)
            self.PRINT_HISTORY.append(log_entry)

        return log_entry

    def verbose(
        self,
        message: str,
        indent: int=0,
    ) -> LogEntry:
        """Add a verbose log entry."""
        return self.log(message, level="verbose", indent=indent)

    def error(
        self,
        message: str,
        indent: int=0
    ) -> LogEntry:
        """Add an error log entry."""
        return self.log(message, level="error", indent=indent)

    def warn(
        self,
        message: str,
        indent: int=0
    ) -> LogEntry:
        """Add a warning log entry."""
        return self.log(message, level="warn", indent=indent)

    def debug(
        self,
        message: str,
        indent: int=0
    ) -> LogEntry:
        """Add a debug log entry."""
        return self.log(message, level="debug", indent=indent)

    def spam(
        self,
        message: str,
        indent: int=0
    ) -> LogEntry:
        """Add a spam log entry."""
        return self.log(message, level="spam", indent=indent)

    def screen(
        self,
        message: str,
        indent: int=0
    ) -> LogEntry:
        """Screen never gets printed to log files."""
        return self.log(message, level="screen", indent=indent)

    def redraw(self, log_entry: LogEntry) -> None:
        """Redraw and update a log entry that was already printed."""
        if log_entry not in self.PRINT_HISTORY:
            raise libioc.errors.CannotRedrawLine(
                reason="Log entry not found in history"
            )

        if log_entry.level != "screen":
            raise libioc.errors.CannotRedrawLine(
                reason=(
                    "Log level 'screen' is required to redraw, "
                    f"but got '{log_entry.level}'"
                )
            )

        # calculate the delta of messages printed since
        i = self.PRINT_HISTORY.index(log_entry)
        n = len(self.PRINT_HISTORY)
        delta = sum(
            map(lambda i: self.PRINT_HISTORY[i].__len__(), range(i, n))
        )

        output = "".join([
            "\r",
            f"\033[{delta}F",  # CPL - Cursor Previous Line
            "\r",               # CR - Carriage Return
            self._indent(
                log_entry.message,
                log_entry.indent
            ),
            "\033[K",           # EL - Erase in Line
            "\n" * (delta),
            "\r"
        ])

        sys.stdout.write(output)

    def _should_print_log_entry(self, log_entry: LogEntry) -> bool:

        if log_entry.level == "screen":
            return True

        if self.print_level is False:
            return False

        print_level = Logger.LOG_LEVELS.index(self.print_level)
        return Logger.LOG_LEVELS.index(log_entry.level) <= print_level

    def _beautify_message(
        self,
        message: str,
        level: str,
        indent: int=0
    ) -> str:

        color = self._get_level_color(level)
        message = self._indent(message, indent)
        message = self._colorize(message, color)
        return message

    def _print(self, message: str, level: str, indent: int=0) -> None:
        print(self._beautify_message(message, level, indent))

    def _print_log_entry(self, log_entry: LogEntry) -> None:
        self._print(
            log_entry.message,
            log_entry.level,
            log_entry.indent
        )

    def _indent(self, message: str, level: int) -> str:
        indent = Logger.__INDENT_PREFIX * level
        return "\n".join(map(lambda x: f"{indent}{x}", message.splitlines()))

    def _create_log_directory(self) -> None:
        if os.geteuid() != 0:
            raise libioc.errors.MustBeRoot(
                f"create {self.log_directory}")
        os.makedirs(self.log_directory, 0x600)
        self.log(f"Log directory '{self.log_directory}' created", level="info")

    def _get_color_code(self, color_name: str) -> int:
        return Logger.COLORS.index(color_name) + 30

    def _get_level_color(self, log_level: str) -> str:
        try:
            log_level_setting = Logger.LOG_LEVEL_SETTINGS[log_level]
            return str(log_level_setting["color"])
        except KeyError:
            return "none"

    def _colorize(self, message: str, color_name: str) -> str:
        try:
            color_code = self._get_color_code(color_name)
        except ValueError:
            return message

        return f"\033[1;{color_code}m{message}\033[0m"
