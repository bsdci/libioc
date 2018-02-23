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
"""Execute commands in jails from the CLI."""
import click
import typing

import iocage.lib.Jail
import iocage.lib.Logger

from .shared.click import IocageClickContext

__rootcmd__ = True


@click.command(
    context_settings=dict(ignore_unknown_options=True),
    name="exec",
    help="Run a command inside a specified jail."
)
@click.pass_context
@click.option(
    "--host_user",
    "-u",
    default="root",
    help="The host user to use."
)
@click.option(
    "--jail_user",
    "-U",
    help="The jail user to use."
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
@click.option("--log-level", "-d", default=None)
def cli(
    ctx: IocageClickContext,
    command: typing.List[str],
    jail: str,
    host_user: str,
    jail_user: typing.Optional[str],
    fork: bool,
    log_level: typing.Optional[str]
) -> None:
    """Run the given command inside the specified jail."""
    logger = ctx.parent.logger
    logger.print_level = log_level

    if jail.startswith("-"):
        logger.error("Please specify a jail first!")
        exit(1)

    user_command = " ".join(list(command))

    if jail_user is not None:
        command = [
            "/bin/su",
            "-m",
            jail_user,
            "-c",
            user_command
        ]
    else:
        command = ["/bin/sh", "-c", user_command]

    ioc_jail = iocage.lib.Jail.Jail(jail, logger=logger)
    ioc_jail.state.query()

    if not ioc_jail.exists:
        logger.error(f"The jail {ioc_jail.humanreadable_name} does not exist")
        exit(1)

    if (fork is False) and (ioc_jail.running is False):
        logger.error(f"The jail {ioc_jail.humanreadable_name} is not running")
        exit(1)
    elif fork is True:
        list(ioc_jail.fork_exec(command, passthru=True))
    else:
        ioc_jail.passthru(command)
