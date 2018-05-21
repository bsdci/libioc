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
"""Collection of iocage helper functions."""
import typing
import json
import random
import re
import subprocess  # nosec: B404
import sys
import ucl

import iocage.lib.errors
import iocage.lib.Datasets
import iocage.lib.Distribution
import iocage.lib.Host
import iocage.lib.Logger
import iocage.lib.ZFS

# MyPy
import iocage.lib.Types
CommandOutput = typing.Tuple[typing.Optional[str], typing.Optional[str], int]


def init_zfs(
    self: typing.Any,
    zfs: typing.Optional['iocage.lib.ZFS.ZFS']=None
) -> 'iocage.lib.ZFS.ZFS':
    """Attach or initialize a ZFS object."""
    try:
        return self.zfs
    except AttributeError:
        pass

    if (zfs is not None) and isinstance(zfs, iocage.lib.ZFS.ZFS):
        object.__setattr__(self, 'zfs', zfs)
    else:
        new_zfs = iocage.lib.ZFS.get_zfs(logger=self.logger)
        object.__setattr__(self, 'zfs', new_zfs)

    return object.__getattribute__(self, 'zfs')


def init_host(
    self: typing.Any,
    host: typing.Optional[iocage.lib.Host.HostGenerator]=None
) -> iocage.lib.Host.HostGenerator:
    """Attach or initialize a Host object."""
    try:
        return self.host
    except AttributeError:
        pass

    if host:
        return host

    return iocage.lib.Host.HostGenerator(
        logger=self.logger,
        zfs=self.zfs
    )


def init_distribution(
    self: typing.Any,
    distribution: typing.Optional[iocage.lib.Distribution.Distribution]=None
) -> iocage.lib.Host.HostGenerator:
    """Attach or initialize a Distribution object."""
    try:
        return self.distribution
    except AttributeError:
        pass

    if distribution:
        return distribution

    return iocage.lib.Distribution.Distribution(
        logger=self.logger,
        zfs=self.zfs
    )


def init_logger(
    self: typing.Any,
    logger: typing.Optional[iocage.lib.Logger.Logger]=None
) -> iocage.lib.Logger.Logger:
    """Attach or initialize a Logger object."""
    try:
        return self.logger
    except AttributeError:
        pass

    if logger is not None:
        object.__setattr__(self, 'logger', logger)
        return logger
    else:
        try:
            return self.logger
        except AttributeError:
            new_logger = iocage.lib.Logger.Logger()
            object.__setattr__(self, 'logger', new_logger)
            return new_logger


def get_userland_version() -> str:
    """Get the hosts userland version."""
    f = open("/bin/freebsd-version", "r", re.MULTILINE, encoding="utf-8")
    # ToDo: move out of the function
    pattern = re.compile("USERLAND_VERSION=\"(\d{2}\.\d)\-([A-z0-9\-]+)\"")
    content = f.read()
    match = pattern.search(content)  # type: typing.Optional[typing.Match[str]]
    if match is None:
        raise iocage.lib.errors.HostUserlandVersionUnknown()
    return match[1]


def exec(
    command: typing.List[str],
    logger: typing.Optional[iocage.lib.Logger.Logger]=None,
    ignore_error: bool=False,
    **subprocess_args: typing.Any
) -> typing.Tuple[
    typing.Optional[str],
    typing.Optional[str],
    int
]:
    """Execute a shell command."""
    if isinstance(command, str):
        command = [command]

    command_str = " ".join(command)

    if logger is not None:
        logger.log(f"Executing: {command_str}", level="spam")

    subprocess_args["stdout"] = subprocess_args.get("stdout", subprocess.PIPE)
    subprocess_args["stderr"] = subprocess_args.get("stderr", subprocess.PIPE)
    subprocess_args["shell"] = subprocess_args.get("shell", False)

    child = subprocess.Popen(  # nosec: TODO: #113
        command,
        **subprocess_args
    )

    stdout, stderr = child.communicate()

    if stderr is not None:
        stderr = stderr.decode("UTF-8").strip()

    if (stdout is not None):
        stdout = stdout.decode("UTF-8").strip()
        if logger:
            logger.spam(_prettify_output(stdout))

    returncode = child.wait()
    if returncode > 0:

        if logger:
            log_level = "spam" if ignore_error else "warn"
            logger.log(
                f"Command exited with {returncode}: {command_str}",
                level=log_level
            )
            if stderr:
                logger.log(_prettify_output(stderr), level=log_level)

        if ignore_error is False:
            raise iocage.lib.errors.CommandFailure(
                returncode=returncode,
                logger=logger
            )

    return stdout, stderr, returncode


def _prettify_output(output: str) -> str:
    return "\n".join(map(
        lambda line: f"    {line}",
        output.strip().splitlines()
    ))


def to_humanreadable_name(name: str) -> str:
    """Return a shorted UUID or the original name."""
    return name[:8] if (is_uuid(name) is True) else name


_UUID_REGEX = re.compile(
    "^[A-z0-9]{8}-[A-z0-9]{4}-[A-z0-9]{4}-[A-z0-9]{4}-[A-z0-9]{12}$"
)


def is_uuid(text: str) -> bool:
    """Return True if the input string is an UUID."""
    return _UUID_REGEX.match(text) is not None


# helper function to validate names
_validate_name = re.compile(r'[a-z0-9][a-z0-9\.\-_]{0,31}', re.I)


def validate_name(name: str) -> bool:
    """Return True if the name matches the naming convention."""
    return _validate_name.fullmatch(name) is not None


def parse_none(
    data: typing.Any,
    none_matches: typing.List[str]=["none", "-", ""]
) -> None:
    """Raise if the input does not translate to None."""
    if (data is None) or (data in none_matches):
        return None
    raise TypeError("Value is not None")


def parse_list(
    data: typing.Optional[typing.Union[str, typing.List[str]]]
) -> typing.List[str]:
    """
    Transform a comma separated string into a list.

    Always returns a list of strings. This list is empty when an empty string
    is provided or the value is None. In any other case the string is split by
    comma and returned as list.
    """
    empty_list: typing.List[str] = []
    try:
        parse_none(data)
        return empty_list
    except TypeError:
        pass
    if data is None:
        return empty_list
    # ToDo: ignore escaped commas
    return data if isinstance(data, list) else data.split(",")


def parse_bool(data: typing.Optional[typing.Union[str, bool]]) -> bool:
    """
    Try to parse booleans from strings.

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


def parse_user_input(
    data: typing.Optional[typing.Union[str, bool]]
) -> typing.Optional[typing.Union[str, bool]]:
    """
    Parse user input.

    uses parse_bool() to partially return Boolean and None values
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
        parse_none(data)
        return None
    except TypeError:
        pass

    return data


def to_json(data: typing.Dict[str, typing.Any]) -> str:
    """Create a JSON string from the input data."""
    output_data = {}
    for key, value in data.items():
        output_data[key] = to_string(
            value,
            true="yes",
            false="no",
            none="none"
        )
    return str(json.dumps(output_data, sort_keys=True, indent=4))


def to_ucl(data: typing.Dict[str, typing.Any]) -> str:
    """Create UCL content from the input data."""
    output_data = {}
    for key, value in data.items():
        output_data[key] = to_string(
            value,
            true="on",
            false="off",
            none="none"
        )
    return str(ucl.dump(output_data))


def to_string(
    data: typing.Union[
        str,
        bool,
        int,
        None,
        typing.List[typing.Union[str, bool, int]]
    ],
    true: str="yes",
    false: str="no",
    none: str="-",
    delimiter: str=","
) -> str:
    """
    Translate complex types into a string.

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


def exec_generator(
    command: typing.List[str],
    logger: typing.Optional[iocage.lib.Logger.Logger]=None,
    **subprocess_args: typing.Any
) -> typing.Generator[
    str,
    None,
    CommandOutput
]:
    """Execute a command in an interactive shell."""
    if isinstance(command, str):
        command = [command]

    command_str = " ".join(command)

    if logger is not None:
        logger.spam(f"Executing (interactive): {command_str}")

    subprocess_args["stdout"] = subprocess_args.get("stdout", subprocess.PIPE)
    subprocess_args["stderr"] = subprocess_args.get(
        "stderr",
        subprocess.STDOUT
    )
    subprocess_args["encoding"] = subprocess_args.get(
        "encoding",
        subprocess.STDOUT
    )
    subprocess_args["universal_newlines"] = subprocess_args.get(
        "universal_newlines",
        subprocess.STDOUT
    )

    try:
        child = subprocess.Popen(  # nosec: TODO: #113
            command,
            **subprocess_args
        )

        stdout = ""
        if child.stdout is not None:
            for line in iter(child.stdout.readline, ""):
                if (line is "") and (child.poll() is not None):
                    continue
                stdout += f"{line}"
                yield line.replace("\r", "").replace("\n", "")
            child.stdout.close()

        if child.stderr is not None:
            stderr = child.stderr.read()
            child.stderr.close()
        else:
            stderr = ""
    except KeyboardInterrupt:
        child.terminate()
        raise

    return stdout, stderr, child.wait()


def exec_passthru(
    command: typing.List[str],
    logger: typing.Optional[iocage.lib.Logger.Logger]=None,
    print_lines: bool=True,
    **subprocess_args: typing.Any
) -> CommandOutput:
    """Execute a command in an interactive shell."""
    lines = exec_generator(
        command,
        logger=logger,
        stdout=sys.stdout,
        **subprocess_args
    )
    try:
        while True:
            line = next(lines)
            if print_lines is True:
                print(line)
                sys.stdout.flush()
    except StopIteration as return_statement:

        output: CommandOutput
        output = return_statement.value
        return output


# ToDo: replace with (u)mount library
def umount_command(
    mountpoint: typing.Optional[typing.Union[
        iocage.lib.Types.AbsolutePath,
        typing.List[iocage.lib.Types.AbsolutePath],
    ]]=None,
    options: typing.Optional[typing.List[str]]=None,
    force: bool=False,
    ignore_error: bool=False,
    logger: typing.Optional[iocage.lib.Logger.Logger]=None
) -> typing.List[str]:
    """Return the command to unmount a mountpoint."""
    cmd = ["/sbin/umount"]

    if force is True:
        cmd.append("-f")

    if options is not None and len(options) != 0:
        cmd + options

    if isinstance(mountpoint, list):
        cmd += mountpoint
    elif isinstance(mountpoint, iocage.lib.Types.AbsolutePath):
        cmd.append(str(mountpoint))

    if ignore_error is True:
        cmd.append(">/dev/null 2>&1 || :")

    return cmd


def umount(
    mountpoint: typing.Optional[typing.Union[
        iocage.lib.Types.AbsolutePath,
        typing.List[iocage.lib.Types.AbsolutePath],
    ]]=None,
    options: typing.Optional[typing.List[str]]=None,
    force: bool=False,
    ignore_error: bool=False,
    logger: typing.Optional[iocage.lib.Logger.Logger]=None
) -> None:
    """Unmount a mountpoint."""
    cmd = umount_command(
        mountpoint=mountpoint,
        options=options,
        force=force
    )

    try:
        iocage.lib.helpers.exec(cmd)
        if logger is not None:
            logger.debug(
                f"Jail mountpoint {mountpoint} umounted"
            )
    except iocage.lib.errors.CommandFailure:
        if logger is not None:
            logger.spam(
                f"Jail mountpoint {mountpoint} not unmounted"
            )
        if ignore_error is False:
            raise iocage.lib.errors.UnmountFailed(
                mountpoint=mountpoint,
                logger=logger
            )


def get_random_uuid() -> str:
    """Generate a random UUID."""
    return "-".join(map(
        lambda x: ('%030x' % random.randrange(16**x))[-x:],  # nosec: B311
        [8, 4, 4, 4, 12]
    ))


def get_basedir_list(distribution_name: str="FreeBSD") -> typing.List[str]:
    """Return the list of basedirs according to the host distribution."""
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
