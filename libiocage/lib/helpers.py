import re
import subprocess
import uuid

import libzfs

import libiocage.lib.Datasets
import libiocage.lib.Host
import libiocage.lib.Logger

from typing import List, Tuple


def init_zfs(self, zfs):
    if isinstance(zfs, libzfs.ZFS):
        self.zfs = zfs
    else:
        self.zfs = get_zfs()


def get_zfs():
    return libzfs.ZFS(history=True, history_prefix="<iocage>")


def init_host(self, host=None):
    if host:
        self.host = host
    else:
        try:
            logger = self.logger
        except:
            logger = None

        try:
            self.host = self._class_host(logger=logger)
        except:
            self.host = libiocage.lib.Host.HostGenerator(logger=logger)


def init_datasets(self, datasets=None):
    if datasets:
        self.datasets = datasets
    else:
        self.datasets = libiocage.lib.Datasets.Datasets()


def init_logger(self, logger=None):
    if logger is not None:
        object.__setattr__(self, 'logger', logger)
    else:
        new_logger = libiocage.lib.Logger.Logger()
        object.__setattr__(self, 'logger', new_logger)


def exec(command, logger=None, ignore_error=False) -> Tuple[
        subprocess.Popen, str, str]:

    command_str = " ".join(list([command]))

    if logger:
        logger.log(f"Executing: {command_str}", level="spam")

    child = subprocess.Popen(
        command,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    stdout, stderr = child.communicate()
    stdout = stdout.decode("UTF-8").strip()
    stderr = stderr.decode("UTF-8").strip()

    if logger and stdout:
        logger.spam(_prettify_output(stdout))

    if child.returncode > 0:

        if logger:
            log_level = "spam" if ignore_error else "warn"
            logger.log(
                f"Command exited with {child.returncode}: {command_str}",
                level=log_level
            )
            if stderr:
                logger.log(_prettify_output(stderr), level=log_level)

        if ignore_error is False:
            raise libiocage.lib.errors.CommandFailure(
                returncode=child.returncode,
                logger=logger
            )

    return child, stdout, stderr


def _prettify_output(output):
    return "\n".join(map(
        lambda line: f"    {line}",
        output.split("\n")
    ))


def to_humanreadable_name(name: str) -> str:
    try:
        uuid.UUID(name)
        return str(name)[:8]
    except (TypeError, ValueError):
        return name


# helper function to validate names
_validate_name = re.compile(r'[a-z0-9][a-z0-9\.\-_]{0,31}', re.I)


def validate_name(name: str):
    return bool(_validate_name.fullmatch(name))


def _parse_none(data):
    if data is None:
        return None

    if data in ["none", "-"]:
        return None

    raise TypeError("Value is not None")


def _parse_bool(data):
    """
    try to parse booleans from strings

    On success, it returns the parsed boolean on failure it raises a TypeError.

    Usage:
        >>> _parse_bool("YES")
        True
        >>> _parse_bool("false")
        False
        >>> _parse_bool("/etc/passwd")
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
        TypeError: Not a boolean value
    """

    if isinstance(data, bool):
        return data
    if isinstance(data, str):
        val = data.lower()
        if val in ["yes", "true", "on"]:
            return True
        elif val in ["no", "false", "off"]:
            return False

    raise TypeError("Value is not a boolean")


def parse_user_input(data):
    """
    uses _parse_bool() to partially return Boolean and NoneType values
    All other types as returned as-is

    >>> parse_user_input("YES")
    True
    >>> parse_user_input("false")
    False
    >>> parse_user_input("notfalse")
    'notfalse'
    >>> parse_user_input(8.4)
    8.4
    """

    try:
        return _parse_bool(data)
    except TypeError:
        pass

    try:
        return _parse_none(data)
    except TypeError:
        pass

    return data


def to_string(data, true="yes", false="no", none="-"):
    """
    return a string boolean value using _parse_bool(), of specified style

    Args:

        true (string):
            The expected return value when data is True

        false (string):
            The expected return value when data is False

        none (string):
            The expected return value when data is None

    Returns:

        string: Map input according to arguments or stringified input

    Usage:

        >>> to_string(True)
        "yes"
        >>> to_string(False)
        "no"

        >>> to_string(True, true="yip", false="nope")
        "yip"
        >>> to_string(False, true="yip", false="nope")
        "nope"

        >>> to_string(None)
        "-"
    """

    data = parse_user_input(data)

    if data is None:
        return none
    elif data is True:
        return true
    elif data is False:
        return false

    return str(data)


def exec_passthru(command: List[str], logger=None):
    command_str = " ".join(command)

    if logger:
        logger.spam(f"Executing (interactive): {command_str}")

    return subprocess.Popen(command_str).communicate()


def exec_raw(command: List[str], logger=None, **kwargs):
    command_str = " ".join(command)
    if logger:
        logger.spam(f"Executing (raw): {command_str}")

    return subprocess.Popen(
        command,
        **kwargs
    )


def exec_iter(command: List[str], logger=None):
    process = exec_raw(
        command,
        logger=logger,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )

    for stdout_line in iter(process.stdout.readline, ""):
        yield stdout_line

    process.stdout.close()

    return_code = process.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, command)


def shell(command, logger=None):
    if not isinstance(command, str):
        command = " ".join(command)

    if logger:
        logger.spam(f"Executing Shell: {command}")

    return subprocess.check_output(
        command,
        shell=True,
        universal_newlines=True,
        stderr=subprocess.DEVNULL
    )


# ToDo: replace with (u)mount library
def umount(mountpoint, force=False, ignore_error=False, logger=None):
    cmd = ["/sbin/umount"]

    if force is True:
        cmd.append("-f")

    cmd.append(mountpoint)

    try:
        exec(cmd)
        if logger is not None:
            logger.debug(
                f"Jail mountpoint {mountpoint} umounted"
            )
    except:
        if logger is not None:
            logger.spam(
                f"Jail mountpoint {mountpoint} not unmounted"
            )
        if ignore_error is False:
            raise libiocage.lib.errors.UnmountFailed(logger=logger)


def get_basedir_list(distribution_name="FreeBSD"):
    basedirs = [
        "bin",
        "boot",
        "lib",
        "libexec",
        "rescue",
        "sbin",
        "usr/bin",
        "usr/include",
        "usr/lib",
        "usr/libexec",
        "usr/sbin",
        "usr/share",
        "usr/libdata",
    ]

    if distribution_name == "FreeBSD":
        basedirs.append("usr/lib32")

    return basedirs
