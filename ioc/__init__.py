# Copyright (c) 2014-2018, iocage
# Copyright (c) 2017-2018, Stefan Grönke
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
import locale
import os
import re
import signal
import subprocess  # nosec: B404
import sys

import click

from iocage.Logger import Logger
from iocage.events import IocageEvent
from iocage.errors import (
    InvalidLogLevel,
    IocageNotActivated,
    ZFSSourceMountpoint
)
from iocage.ZFS import get_zfs
from iocage.Datasets import Datasets
from iocage.Host import HostGenerator

logger = Logger()

click.core._verify_python3_env = lambda: None  # type: ignore
user_locale = os.environ.get("LANG", "en_US.UTF-8")
locale.setlocale(locale.LC_ALL, user_locale)

IOCAGE_CMD_FOLDER = os.path.abspath(os.path.dirname(__file__))

# @formatter:off
# Sometimes SIGINT won't be installed.
# http://stackoverflow.com/questions/40775054/capturing-sigint-using-keyboardinterrupt-exception-works-in-terminal-not-in-scr/40785230#40785230
signal.signal(signal.SIGINT, signal.default_int_handler)
# If a utility decides to cut off the pipe, we don't care (IE: head)
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
# @formatter:on

try:
    subprocess.check_call(  # nosec
        ["/sbin/sysctl", "vfs.zfs.version.spa"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
except subprocess.CalledProcessError:
    logger.error(
        "ZFS is required to use iocage.\n"
        "Try calling 'kldload zfs' as root."
    )
    exit(1)


def set_to_dict(data: typing.Set[str]) -> typing.Dict[str, str]:
    """Convert a set of values to a dictionary."""
    keys, values = zip(*[x.split("=", maxsplit=1) for x in data])
    return dict(zip(keys, values))


def print_events(
    generator: typing.Generator[typing.Union[IocageEvent, bool], None, None]
) -> typing.Optional[bool]:

    lines: typing.Dict[str, str] = {}
    for event in generator:

        if isinstance(event, bool):
            # a boolean terminates the event stream
            return event

        if event.identifier is None:
            identifier = "generic"
        else:
            identifier = event.identifier

        if event.type not in lines:
            lines[event.type] = {}

        # output fragments
        running_indicator = "+" if (event.done or event.skipped) else "-"
        name = event.type
        if event.identifier is not None:
            name += f"@{event.identifier}"

        output = f"[{running_indicator}] {name}: "

        if event.message is not None:
            output += event.message
        else:
            output += event.get_state_string(
                done="OK",
                error="FAILED",
                skipped="SKIPPED",
                pending="..."
            )

        if event.duration is not None:
            output += " [" + str(round(event.duration, 3)) + "s]"

        # new line or update of previous
        if identifier not in lines[event.type]:
            # Indent if previous task is not finished
            lines[event.type][identifier] = logger.screen(
                output,
                indent=event.parent_count
            )
        else:
            lines[event.type][identifier].edit(
                output,
                indent=event.parent_count
            )


class IOCageCLI(click.MultiCommand):
    """
    Iterates in the 'cli' directory and will load any module's cli definition.
    """

    def list_commands(self, ctx: click.core.Context):
        rv = []

        for filename in os.listdir(IOCAGE_CMD_FOLDER):
            if filename.endswith('.py') and \
                    not filename.startswith('__init__'):
                rv.append(re.sub(r".py$", "", filename))
        rv.sort()

        return rv

    def get_command(self, ctx, name):
        ctx.print_events = print_events
        try:
            mod = __import__(f"ioc.{name}", None, None, ["ioc"])

            try:
                if mod.__rootcmd__ and "--help" not in sys.argv[1:]:
                    if len(sys.argv) != 1:
                        if os.geteuid() != 0:
                            app_name = mod.__name__.rsplit(".")[-1]
                            logger.error(
                                "You need to have root privileges"
                                f" to run {app_name}"
                            )
                            exit(1)
            except AttributeError:
                # It's not a root required command.
                pass
            return mod.cli
        except (ImportError, AttributeError):
            raise
            return


@click.option(
    "--log-level",
    "-d",
    default=None,
    help=(
        f"Set the CLI log level {Logger.LOG_LEVELS}"
    )
)
@click.option(
    "--source",
    multiple=True,
    type=str,
    help="Globally override the activated iocage dataset(s)"
)
@click.command(cls=IOCageCLI)
@click.version_option(version="0.3.2 2018/12/16", prog_name="ioc")
@click.pass_context
def cli(ctx, log_level: str, source: set) -> None:
    """A jail manager."""
    if log_level is not None:
        try:
            logger.print_level = log_level
        except InvalidLogLevel:
            exit(1)
    ctx.logger = logger

    ctx.zfs = get_zfs(logger=ctx.logger)

    ctx.user_sources = None if (len(source) == 0) else set_to_dict(source)

    if ctx.invoked_subcommand in ["activate", "deactivate"]:
        return

    try:
        datasets = Datasets(
            sources=ctx.user_sources,
            zfs=ctx.zfs,
            logger=ctx.logger
        )
        ctx.host = HostGenerator(
            datasets=datasets,
            logger=ctx.logger,
            zfs=ctx.zfs
        )
    except (IocageNotActivated, ZFSSourceMountpoint):
        exit(1)

