import os
import sys

import libiocage.lib.errors


class LogEntry:

    def __init__(self, message, level, indent=0, logger=None, **kwargs):
        self.message = message
        self.level = level
        self.indent = indent
        self.logger = logger

        for key in kwargs.keys():
            object.__setattr__(self, key, kwargs[key])

    def edit(self, message=None, indent=None):

        if self.logger is None:
            raise libiocage.lib.errors.CannotRedrawLine(
                reason="No logger available"
            )

        if message is not None:
            self.message = message

        if indent is not None:
            self.indent = indent

        self.logger.redraw(self)


class Logger:

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

    RESET_SEQ = "\033[0m"
    BOLD_SEQ = "\033[1m"
    LINE_UP_SEQ = "\033[F"

    LOG_LEVEL_SETTINGS = {
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

    INDENT_PREFIX = "  "

    PRINT_HISTORY = []

    def __init__(self, print_level=None, log_directory="/var/log/iocage"):
        self._print_level = print_level
        self._set_log_directory(log_directory)

    @property
    def default_print_level(self):
        return "info"

    @property
    def print_level(self):
        if self._print_level is None:
            return self.default_print_level
        else:
            return self._print_level

    @print_level.setter
    def print_level(self, value):
        self._print_level = value

    def _set_log_directory(self, log_directory):
        self.log_directory = os.path.abspath(log_directory)
        if not os.path.isdir(log_directory):
            self._create_log_directory()
        self.log(f"Log directory set to '{log_directory}'", level="spam")

    def log(self, *args, **kwargs):

        args = list(args)

        if ("message" not in kwargs) and (len(args) > 0):
            kwargs["message"] = args.pop(0)

        if ("level" not in kwargs) and (len(args) > 0):
            kwargs["level"] = args.pop(0)

        if "level" not in kwargs:
            kwargs["level"] = "info"

        log_entry = LogEntry(logger=self, **kwargs)

        if self._should_print_log_entry(log_entry):
            self._print_log_entry(log_entry)
            self.PRINT_HISTORY.append(log_entry)

        return log_entry

    def verbose(self, message, indent=0, **kwargs):
        return self.log(message, level="verbose", indent=indent, **kwargs)

    def error(self, message, indent=0, **kwargs):
        return self.log(message, level="error", indent=indent, **kwargs)

    def warn(self, message, indent=0, **kwargs):
        return self.log(message, level="warn", indent=indent, **kwargs)

    def debug(self, message, indent=0, **kwargs):
        return self.log(message, level="debug", indent=indent, **kwargs)

    def spam(self, message, indent=0, **kwargs):
        return self.log(message, level="spam", indent=indent, **kwargs)

    def screen(self, message, indent=0, **kwargs):
        """
        Screen never gets printed to log files
        """
        return self.log(message, level="screen", indent=indent, **kwargs)

    def redraw(self, log_entry):

        if log_entry not in self.PRINT_HISTORY:
            raise libiocage.lib.errors.CannotRedrawLine(
                reason="Log entry not found in history"
            )

        if log_entry.level != "screen":
            raise libiocage.lib.errors.CannotRedrawLine(
                reason=(
                    "Log level 'screen' is required to redraw, "
                    f"but got '{self.level}'"
                )
            )

        line_number = self.PRINT_HISTORY.index(log_entry)
        delta = len(self.PRINT_HISTORY) - line_number

        # ToDo: Handle redrawing of multiline entries with different line count

        output = "".join([
            f"\033[{delta}F",  # CPL - Cursor Previous Line
            "\r",               # CR - Carriage Return
            self._indent(log_entry.message, log_entry.indent),
            "\033[K",           # EL - Erase in Line
            "\n" * delta
        ])

        sys.stdout.write(output)

    def _should_print_log_entry(self, log_entry):

        if log_entry.level == "screen":
            return True

        if self.print_level is False:
            return False

        print_level = Logger.LOG_LEVELS.index(self.print_level)
        return Logger.LOG_LEVELS.index(log_entry.level) <= print_level

    def _beautify_message(self, message, level, indent=0):
        color = self._get_level_color(level)
        message = self._indent(message, indent)
        message = self._colorize(message, color)
        return message

    def _print(self, message, level, indent=0):
        print(self._beautify_message(message, level, indent))

    def _print_log_entry(self, log_entry):
        return self._print(
            log_entry.message,
            log_entry.level,
            log_entry.indent
        )

    def _indent(self, message, level):
        indent = Logger.INDENT_PREFIX * level
        return "\n".join(map(lambda x: f"{indent}{x}", message.split("\n")))

    def _get_log_file_path(self, level, jail=None):
        return self.log_directory

    def _create_log_directory(self):
        if os.geteuid() != 0:
            raise libiocage.lib.errors.MustBeRoot(
                f"create {self.log_directory}")
        os.makedirs(self.log_directory, 0x600)
        self.log(f"Log directory '{self.log_directory}' created", level="info")

    def _get_color_code(self, color_name):
        return Logger.COLORS.index(color_name) + 30

    def _get_level_color(self, log_level):
        try:
            return Logger.LOG_LEVEL_SETTINGS[log_level]["color"]
        except KeyError:
            return "none"

    def _colorize(self, message, color_name=None):
        try:
            color_code = self._get_color_code(color_name)
        except:
            return message

        return f"\033[1;{color_code}m{message}\033[0m"
