import subprocess
import re

import libzfs

import libiocage.lib.Datasets
import libiocage.lib.Host
import libiocage.lib.Logger


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

        self.host = libiocage.lib.Host.Host(logger=logger)


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


def exec(command, logger=None, ignore_error=False):
    if isinstance(command, str):
        command = [command]

    command_str = " ".join(command)

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


# helper function to validate names
def validate_name(name):
    validate = re.compile(r'[a-z0-9][a-z0-9\.\-_]{0,31}', re.I)

    return bool(validate.fullmatch(name))


# data -> bool | default
def parse_bool(data, default=False):
    """
    try to parse booleans from strings

    On success, it returns the parsed boolean
    on failure it returns the `default`.
    By default, `default` is `False`.

    >>> parse_bool("YES")
    True
    >>> parse_bool("false")
    False
    >>> parse_bool("-")
    False
    """

    if isinstance(data, bool):
        return data
    if isinstance(data, str):
        if data.lower() in ["yes", "true", "on", "1"]:
            return True
        elif data.lower() in ["no", "false", "off", "0"]:
            return False
    return default


def try_parse_bool(data):
    """
    like parse_bool(), but returns the input itself if parsing fails

    >>> parse_bool("YES")
    True
    >>> parse_bool("false")
    False
    >>> parse_bool(8.4)
    8.4
    """
    return parse_bool(data, data)


def get_str_bool(data, true="yes", false="no"):
    """
    return a string boolean value using parse_bool(), of specified style

    >>> get_str_bool(True)
    "yes"
    >>> get_str_bool(False)
    "no"

    >>> get_str_bool(True, true="yip", false="nope")
    "yip"
    >>> get_str_bool(False, true="yip", false="nope")
    "nope"
    """
    return true if parse_bool(data) else false


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
        raise subprocess.CalledProcessError(return_code, cmd)

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
