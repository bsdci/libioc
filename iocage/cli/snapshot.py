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
"""snapshot module for the cli."""
import typing
import click

import iocage.lib.Jail
import iocage.lib.Logger

from .shared.click import IocageClickContext
from .shared.jail import get_jail

__rootcmd__ = True


@click.command(
    name="list_or_take"
)
@click.pass_context
@click.argument(
    "identifier",
    nargs=1,
    required=False
)
def cli_list_or_take(
    ctx: IocageClickContext,
    identifier: str
) -> None:
    
    if "@" in identifier:
        return cli_take(ctx, identifier)
    else:
        return cli_list(ctx)

@click.command(
    name="take",
    help="Take a snapshot"
)
@click.pass_context
@click.argument("identifier", nargs=1, required=True)
def cli_take(
    ctx: IocageClickContext,
    identifier: str
) -> None:
    jail, snapshot_name = identifier.split("@")
    ioc_jail = get_jail(jail, ctx.parent)
    print(f"TAKING A SNAPSHOT: {snapshot_name}")


@click.command(
    name="list",
    help="List all snapshots"
)
@click.pass_context
@click.argument("jail", nargs=1, required=True)
def cli_list(ctx: IocageClickContext, jail: str) -> None:
    ioc_jail = get_jail(jail, ctx.parent)
    print("LISTING SNAPSHOTS")


@click.command(
    name="remove",
    help="Delete existing snapshots"
)
@click.argument(
    "name",
    nargs=1,
    required=False
)
@click.argument("identifier", nargs=1, required=True)
@click.pass_context
def cli_remove(ctx: IocageClickContext, name: str, identifier: str) -> None:
    jail, snapshot_name = identifier.split("@")
    ioc_jail = get_jail(jail, ctx.parent)
    print("DELETING SNAPSHOT")


class SnapshotCli(click.MultiCommand):

    def list_commands(self, ctx: click.core.Context) -> list:
        return [
            "list",
            "take",
            "rollback",
            "remove"
        ]

    def get_command(
        self,
        ctx: click.core.Context,
        cmd_name: str
    ) -> click.core.Command:

        command: typing.Optional[click.core.Command] = None

        if cmd_name == "list":
            command = cli_list
        elif cmd_name == "take":
            command = cli_take
        elif cmd_name == "remove":
            command = cli_remove
        elif cmd_name == "rollback":
            command = cli_rollback
        else:
            command = cli_list_or_take

        return command


@click.group(
    name="snapshot",
    cls=SnapshotCli,
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.pass_context
def cli(
    ctx: IocageClickContext
) -> None:
    """Take and manage resource snapshots"""

    ctx.logger = ctx.parent.logger
    ctx.host = iocage.lib.Host.HostGenerator(logger=ctx.logger)

