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
"""set module for the cli."""
import typing
import click
import os.path

import iocage.lib.errors
import iocage.lib.Logger
import iocage.lib.Host
import iocage.lib.helpers
import iocage.lib.Jail
import iocage.lib.Config.Jail.File.Fstab


__rootcmd__ = True
FstabLine = iocage.lib.Config.Jail.File.Fstab.FstabLine


@click.command(
    name="add"
)
@click.pass_context
@click.argument(
    "source",
    nargs=1,
    required=False
)
@click.argument(
    "destination",
    nargs=1,
    required=False
)
@click.option("--read-write", "-rw", is_flag=True, default=False)
def cli_add(
    ctx: click.core.Context,
    source: str,
    destination: str,
    read_write: bool
) -> None:

    if destination is None:
        destination = source

    if os.path.exists(source) is False:
        ctx.parent.logger.error(
            f"The mount source {source} is does not exist"
        )
        exit(1)

    if os.path.isdir(source) is False:
        ctx.parent.logger.error(
            f"The mount source {source} is not a directory"
        )
        exit(1)

    mount_options = "rw" if read_write is True else "ro"

    try:
        fstab = ctx.parent.jail.fstab
        fstab.read_file()
        fstab.new_line(
            source=source,
            destination=destination,
            fs_type="nullfs",
            options=mount_options,
            dump="0",
            passnum="0",
            comment=None
        )
        fstab.save()
        ctx.parent.logger.log(
            f"fstab mount added: {source} -> {destination} ({mount_options})"
        )
        exit(0)
    except iocage.lib.errors.IocageException:
        exit(1)


@click.command(
    name="show"
)
@click.pass_context
def cli_show(ctx):
    parent: typing.Any = ctx.parent

    if os.path.isfile(ctx.parent.jail.fstab.path):
        with open(ctx.parent.jail.fstab.path, "r") as f:
            print(f.read())


@click.command(
    name="rm"
)
@click.argument(
    "source",
    nargs=1,
    required=False
)
@click.pass_context
def cli_rm(ctx, source):

    fstab = ctx.parent.jail.fstab

    deleted_destination = None
    i = 0

    try:
        fstab.read_file()
        for existing_line in fstab:
            i += 1
            if isinstance(existing_line, FstabLine) is False:
                continue
            if existing_line["source"] == source:
                deleted_destination = fstab[i-1]["destination"]
                del fstab[i-1]
                fstab.save()
                break
    except iocage.lib.errors.IocageException:
        exit(1)

    if deleted_destination is None:
        ctx.parent.logger.error("no matching fstab line found")
        exit(1)

    ctx.parent.logger.log(
        f"fstab mount removed: {source} -> {deleted_destination}"
    )


class FstabCli(click.MultiCommand):

    def list_commands(self, ctx: click.core.Context) -> typing.List[str]:
        return [
            "show",
            "add",
            "rm"
        ]

    def get_command(
        self,
        ctx: click.core.Context,
        action: str
    ):

        if action == "show":
            return cli_show
        elif action == "add":
            return cli_add
        elif action == "rm":
            return cli_rm

        raise NotImplementedException("action does not exist")


@click.group(
    name="fstab",
    cls=FstabCli,
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.pass_context
@click.argument(
    "jail",
    nargs=1,
    required=True
)
def cli(
    ctx: click.core.Context,
    jail: str
) -> None:
    """Manage a jails fstab file"""

    ctx.logger: iocage.lib.Logger.Logger = ctx.parent.logger
    ctx.host = iocage.lib.Host.HostGenerator(logger=ctx.logger)

    filters = (f"name={jail}",)
    try:
        ctx.jail = iocage.lib.Jail.JailGenerator(
            jail,
            host=ctx.host,
            logger=ctx.logger
        )
    except iocage.lib.errors.IocageException:
        exit(1)
