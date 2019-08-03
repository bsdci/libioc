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
"""Collection of iocage helper functions."""
import typing
import ctypes
import json
import os
import random
import re
import subprocess  # nosec: B404
import sys
import pty
import select

import jail as libjail

import libioc.errors
import libioc.Logger

# MyPy
import libioc.Types
CommandOutput = typing.Tuple[typing.Optional[str], typing.Optional[str], int]


def get_os_version(
    version_file: str="/bin/freebsd-version"
) -> typing.Dict[str, typing.Union[str, int, float]]:
    """Get the hosts userland version."""
    f = open(version_file, "r", re.MULTILINE, encoding="utf-8")
    # ToDo: move out of the function
    pattern = re.compile(
        r"USERLAND_VERSION=\""
        r"(?P<userland>\d{1,2}(?:\.\d)?)"
        r"\-"
        r"(?P<name>[A-z0-9\-]+?)"
        r"(?:-"
        r"p(?P<patch>\d+)"
        r")?\""
    )
    content = f.read()
    match = pattern.search(content)  # type: typing.Optional[typing.Match[str]]
    if match is None:
        raise libioc.errors.HostUserlandVersionUnknown()
    output: typing.Dict[str, typing.Union[str, int, float]] = {
        "userland": float(match["userland"]),
        "name": match["name"],
        "patch": int(match["patch"] if (match["patch"] is not None) else 0)
    }
    return output


def exec(
    command: typing.List[str],
    logger: typing.Optional['libioc.Logger.Logger']=None,
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
            raise libioc.errors.CommandFailure(
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
    r"^[A-z0-9]{8}-[A-z0-9]{4}-[A-z0-9]{4}-[A-z0-9]{4}-[A-z0-9]{12}$"
)


def is_uuid(text: str) -> bool:
    """Return True if the input string is an UUID."""
    return _UUID_REGEX.match(text) is not None


# helper function to validate names
_validate_name = re.compile(r"[a-z0-9][a-z0-9\.\-_]{1,31}", re.I)


def validate_name(name: str) -> bool:
    """Return True if the name matches the naming convention."""
    return _validate_name.fullmatch(name) is not None


def parse_none(
    data: typing.Any,
    none_matches: typing.List[str]=["none", "-", ""]
) -> None:
    """Raise if the input does not translate to None."""
    if data is None:
        return None
    if isinstance(data, str) and (data.lower() in none_matches):
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
    if isinstance(data, list):
        return data
    return split_list_string(data)


def split_list_string(
    data: str,
    separator: str=","
) -> typing.List[str]:
    r"""
    Split by separator but keep escaped ones.

    Args:

        data (str):

            Input data that will be split by the separator.

        separator(str): (optional, default=",")

            Input data is split by this separator.


    Example:

        >> split_strlist("foo,bar\,baz")
        ["foo", "bar,baz"]

    Returns a list of strings from the input data where escaped separators are
    ignored and unescaped.
    """
    output = []
    buf = ""
    escaped = False
    for c in data:
        if (c == separator) and (escaped is False):
            output.append(buf)
            buf = ""
            continue
        escaped = (c == "\\") is True
        if escaped is False:
            buf += c
    output.append(buf)
    return output


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
        if val in ["yes", "true", "on", "1", 1]:
            return True
        elif val in ["no", "false", "off", "0", 0]:
            return False

    raise TypeError("Value is not a boolean")


def parse_int(data: typing.Optional[typing.Union[str, int]]) -> int:
    """
    Try to parse integer from strings.

    On success, it returns the parsed integer on failure it raises a TypeError.

    Usage:
        >>> parse_int("-1")
        -1
        >>> parse_int(3)
        3
        >>> parse_int(None)
        TypeError: None is not a number
        >>> parse_int("invalid")
        TypeError: Value is not an integer: invalid
        >>> parse_int(5.0)
        5
        >>> parse_int(5.1)
        TypeError: Value is not an integer: 5.1
    """
    if data is None:
        raise TypeError("None is not a number")
    try:
        if isinstance(data, float) and (float(data).is_integer() is False):
            raise ValueError
        return int(data)
    except ValueError:
        pass
    raise TypeError(f"Value is not an integer: {data}")


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
    >>> parse_user_input(dict(ioc=123))
    {'ioc': 123}
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


def _normalize_data(
    data: typing.Dict[str, typing.Any]
) -> typing.Dict[str, typing.Any]:
    output_data: typing.Dict[str, typing.Any] = {}
    for key, value in data.items():
        if type(value) == dict:
            output_data[key] = _normalize_data(value)
        else:
            output_data[key] = to_string(
                value,
                true="yes",
                false="no",
                none="none"
            )
    return output_data


def to_json(data: typing.Dict[str, typing.Any]) -> str:
    """Create a JSON string from the input data."""
    output_data = _normalize_data(data)
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
    import ucl
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
    buffer_lines: bool=True,
    summarize: bool=True,
    encoding: str="UTF-8",
    universal_newlines: bool=True,
    stdin: typing.Optional[typing.Union[typing.TextIO, int]]=None,
    stdout: typing.Optional[typing.TextIO]=None,
    env: typing.Optional[typing.Dict[str, typing.Any]]=None,
    logger: typing.Optional['libioc.Logger.Logger']=None
) -> typing.Generator[
    bytes,
    None,
    CommandOutput
]:
    """Execute a command in an interactive shell."""
    if isinstance(command, str):
        command = [command]

    command_str = " ".join(command)

    if logger is not None:
        logger.spam(f"Executing (interactive): {command_str}")

    controller_pts, delegate_pts = pty.openpty()

    if stdin is None:
        stdin = delegate_pts

    stdout_result = b""
    stdout_line_buf = b""
    try:
        child = subprocess.Popen(  # nosec: TODO: #113
            command,
            encoding=encoding,
            stdin=stdin,
            stdout=delegate_pts,
            stderr=subprocess.STDOUT,
            close_fds=False,
            universal_newlines=universal_newlines,
            env=env
        )
        while child.poll() is None:
            read, _, _ = select.select([controller_pts], [], [], 0)
            if read:
                stdout_chunk = os.read(controller_pts, 512)

                if summarize is True:
                    stdout_result += stdout_chunk

                # pipe to stdout if it was set
                if stdout is not None:
                    stdout.write(stdout_chunk.decode("UTF-8"))

                if buffer_lines is False:
                    # unbuffered chunk output
                    yield stdout_chunk
                else:
                    # line buffered output
                    stdout_line_buf += stdout_chunk
                    while b"\n" in stdout_line_buf:
                        lines = stdout_line_buf.split(b"\n", maxsplit=1)
                        stdout_line_buf = lines.pop()
                        yield from lines

    except KeyboardInterrupt:
        child.terminate()
        raise
    finally:
        os.close(controller_pts)
        os.close(delegate_pts)
        # push last line when buffering lines
        if len(stdout_line_buf) > 0:
            yield stdout_line_buf

    _stdout = stdout_result.decode(encoding) if (summarize is True) else None
    return _stdout, None, child.returncode


def exec_passthru(
    command: typing.List[str],
    logger: typing.Optional['libioc.Logger.Logger']=None,
    **subprocess_args: typing.Any
) -> CommandOutput:
    """Execute a command in an interactive shell."""
    child = subprocess.Popen(  # nosec: B603
        command,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        close_fds=True,
        **subprocess_args
    )
    child.wait()
    return None, None, child.returncode


def mount(
    destination: str,
    source: str=None,
    fstype: str="nullfs",
    opts: typing.List[str]=[],
    logger: typing.Optional['libioc.Logger.Logger']=None,
    **iov_data: typing.Any
) -> None:
    """Mount a filesystem using libc."""
    data: typing.Dict[str, typing.Optional[str]] = dict(
        fstype=fstype,
        fspath=destination
    )
    for key, value in iov_data.items():
        data[key] = str(value)
    if source is not None:
        if fstype == "nullfs":
            data["target"] = source
        else:
            data["from"] = source
    for opt in opts:
        data[opt] = None
    jiov = libjail.Jiov(data)
    if libjail.dll.nmount(jiov.pointer, len(jiov), 0) != 0:
        raise libioc.errors.MountFailed(
            mountpoint=destination,
            reason=jiov.errmsg.value.decode("UTF-8"),
            logger=logger
        )


def umount(
    mountpoint: typing.Optional[typing.Union[
        libioc.Types.AbsolutePath,
        typing.List[libioc.Types.AbsolutePath],
    ]]=None,
    options: typing.Optional[typing.List[str]]=None,
    force: bool=False,
    ignore_error: bool=False,
    logger: typing.Optional['libioc.Logger.Logger']=None
) -> None:
    """Unmount a mountpoint using libc."""
    if isinstance(mountpoint, list) is True:
        for entry in typing.cast(
            typing.List[libioc.Types.AbsolutePath],
            mountpoint
        ):
            try:
                umount(
                    mountpoint=entry,
                    options=options,
                    force=force,
                    ignore_error=ignore_error,
                    logger=logger
                )
            except (
                libioc.errors.UnmountFailed,
                libioc.errors.InvalidMountpoint
            ):
                if force is False:
                    raise
        return

    mountpoint_path = libioc.Types.AbsolutePath(mountpoint)

    if force is False:
        umount_flags = ctypes.c_ulonglong(0)
    else:
        umount_flags = ctypes.c_ulonglong(0x80000)

    if os.path.ismount(str(mountpoint_path)) is False:
        raise libioc.errors.InvalidMountpoint(
            mountpoint=mountpoint,
            logger=logger
        )

    _mountpoint = str(mountpoint_path).encode("utf-8")
    if libjail.dll.unmount(_mountpoint, umount_flags) == 0:
        if logger is not None:
            logger.debug(
                f"Jail mountpoint {mountpoint} umounted"
            )
    else:
        if logger is not None:
            logger.spam(
                f"Jail mountpoint {mountpoint} not unmounted"
            )
        if ignore_error is False:
            raise libioc.errors.UnmountFailed(
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


def require_no_symlink(
    path: str,
    logger: typing.Optional['libioc.Logger.Logger']=None
) -> None:
    """Raise when the path contains a symlink."""
    directories = path.split("/")
    while len(directories) > 0:
        current_directory = "/".join(directories)
        if os.path.exists(current_directory):
            if os.path.islink(current_directory):
                raise libioc.errors.SecurityViolation(
                    reason="Path contains a symbolic link.",
                    logger=logger
                )
        directories.pop()


def makedirs_safe(
    target: str,
    mode: int=0o700,
    logger: typing.Optional['libioc.Logger.Logger']=None
) -> None:
    """Create a directory without following symlinks."""
    require_no_symlink(target)
    if logger is not None:
        logger.verbose(f"Safely creating {target} directory")
    os.makedirs(target, mode=mode, exist_ok=True)
