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
"""Execute commands in jails from the CLI."""
import click
import typing
import shlex

import iocage.Jail
import iocage.Logger

from .shared.click import IocageClickContext

__rootcmd__ = True


@click.command(
    context_settings=dict(ignore_unknown_options=True),
    name="exec"
)
@click.pass_context
@click.option(
    "--user",
    "-u",
    help="The jail user who executes the command."
)
@click.option(
    "--fork",
    "-f",
    is_flag=True,
    default=False,
    help="Spawns a jail to execute the command."
)
@click.argument("jail", required=True, nargs=1)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def cli(
    ctx: IocageClickContext,
    command: typing.List[str],
    jail: str,
    user: typing.Optional[str],
    fork: bool,
) -> None:
    """
    Run the given command inside the specified jail.

    When executing commands with own options or flags the end of ioc options
    can be marked with a double-dash or the full command can be quoted:

        ioc exec myjail -- ps -aux
    """
    logger = ctx.parent.logger

    if jail.startswith("-"):
        logger.error("Please specify a jail first!")
        exit(1)

    command_list = list(command)

    if user is not None:
        user_command = " ".join(command_list)
        command_list = [
            "/usr/bin/su",
            "-m",
            shlex.quote(user),
            "-c",
            shlex.quote(user_command)
        ]

    ioc_jail = iocage.Jail.JailGenerator(
        jail,
        logger=logger,
        zfs=ctx.parent.zfs,
        host=ctx.parent.host
    )
    ioc_jail.state.query()

    if not ioc_jail.exists:
        logger.error(f"The jail {ioc_jail.humanreadable_name} does not exist")
        exit(1)

    if (fork is False) and (ioc_jail.running is False):
        logger.error(f"The jail {ioc_jail.humanreadable_name} is not running")
        exit(1)

    try:
        if fork is True:
            events = ioc_jail.fork_exec(
                " ".join(command_list),
                passthru=True,
                exec_timeout=0
            )
            for event in events:
                continue
        else:
            ioc_jail.passthru(command_list)
    except iocage.errors.IocageException:
        exit(1)
