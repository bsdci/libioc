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
import json
import re
import subprocess
import uuid

import libiocage.lib.Datasets
import libiocage.lib.Host
import libiocage.lib.Logger
import libiocage.lib.ZFS


def init_zfs(
        self,
        zfs: 'libiocage.lib.ZFS.ZFS'=None
) -> 'libiocage.lib.ZFS.ZFS':

    try:
        return self.zfs
    except:
        pass

    if (zfs is not None) and isinstance(zfs, libiocage.lib.ZFS.ZFS):
        object.__setattr__(self, 'zfs', zfs)
        return zfs

    try:
        return self.zfs
    except AttributeError:
        pass

    zfs = libiocage.lib.ZFS.get_zfs(logger=self.logger)
    object.__setattr__(self, 'zfs', zfs)
    return zfs


def init_host(
        self,
        host: 'libiocage.lib.Host.HostGenerator'=None
) -> 'libiocage.lib.Host.HostGenerator':

    try:
        return self.host
    except:
        pass

    if host:
        return host

    return libiocage.lib.Host.HostGenerator(
        logger=self.logger,
        zfs=self.zfs
    )


def init_logger(
        self,
        logger: 'libiocage.lib.Logger.Logger'=None
) -> 'libiocage.lib.Logger.Logger':

    try:
        return self.logger
    except:
        pass

    if logger is not None:
        object.__setattr__(self, 'logger', logger)
        return logger
    else:
        try:
            return self.logger
        except:
            new_logger = libiocage.lib.Logger.Logger()
            object.__setattr__(self, 'logger', new_logger)
            return new_logger


def exec(command, logger=None, ignore_error=False, **subprocess_args):
    if isinstance(command, str):
        command = [command]

    command_str = " ".join(command)

    if logger:
        logger.log(f"Executing: {command_str}", level="spam")

    subprocess_args["stdout"] = subprocess_args.get("stdout", subprocess.PIPE)
    subprocess_args["stderr"] = subprocess_args.get("stderr", subprocess.PIPE)

    child = subprocess.Popen(
        command,
        shell=False,
        **subprocess_args
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


def _prettify_output(output: str) -> str:
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


def validate_name(name: str) -> bool:
    return bool(_validate_name.fullmatch(name))


def parse_none(data) -> str:
    if data is None:
        return None

    if data in ["none", "-", ""]:
        return None

    raise TypeError("Value is not None")


def parse_list(data: typing.Union[str, typing.List[str]]) -> list:
    """
    Transforms a comma separated string into a list
    """
    # ToDo: escaped commas
    return data if isinstance(data, list) else data.split(",")


def parse_bool(data) -> bool:
    """
    try to parse booleans from strings

    On success, it returns the parsed boolean on failure it raises a TypeError.

    Usage:
        >>> parse_bool("YES")
        True
        >>> parse_bool("false")
        False
        >>> parse_bool("/etc/passwd")
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
    uses parse_bool() to partially return Boolean and NoneType values
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
        return parse_bool(data)
    except TypeError:
        pass

    try:
        return parse_none(data)
    except TypeError:
        pass

    return data


def to_json(data: dict) -> str:
    output_data = {}
    for key, value in data.items():
        output_data[key] = to_string(
            value,
            true="yes",
            false="no",
            none="none"
        )
    return json.dumps(output_data, sort_keys=True, indent=4)


def to_string(
    data: typing.Union[
        str,
        bool,
        int,
        typing.List[typing.Union[str, bool, int]]
    ],
    true: str="yes",
    false: str="no",
    none: str="-",
    delimiter: str=","
) -> str:
    """
    return a string boolean value using parse_bool(), of specified style

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

    if data is None:
        return none

    elif isinstance(data, list) is True:
        children = [
            to_string(x, true, false, none, delimiter)
            for x in list(data)  # type: ignore
            if x is not None
        ]
        if len(children) == 0:
            return none
        normalized_data = ",".join(children)
    else:
        normalized_data = data  # type: ignore

    parsed_data = parse_user_input(normalized_data)

    if parsed_data is True:
        return true
    elif parsed_data is False:
        return false
    elif parsed_data is None:
        return none

    return str(parsed_data)


def exec_passthru(command, logger=None):
    if isinstance(command, str):
        command = [command]

    command_str = " ".join(command)
    if logger:
        logger.spam(f"Executing (interactive): {command_str}")

    return subprocess.Popen(command).communicate()


def exec_raw(command, logger=None, **kwargs):
    if isinstance(command, str):
        command = [command]

    command_str = " ".join(command)
    if logger:
        logger.spam(f"Executing (raw): {command_str}")

    return subprocess.Popen(
        command,
        **kwargs
    )


def exec_iter(command, logger=None):
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
