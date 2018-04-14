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
"""Export a jail from the CLI."""
import click

import iocage.lib.errors
import iocage.lib.Jail
import iocage.lib.Host
import iocage.lib.ZFS

from .shared.click import IocageClickContext

__rootcmd__ = True


@click.command(name="import", help="Import a jail from a backup archive")
@click.pass_context
@click.argument("jail", required=True)
@click.argument("source", required=True)
def cli(
    ctx: IocageClickContext,
    jail: str,
    source: str
) -> None:
    """Restore a jail from a backup archive."""
    logger = ctx.parent.logger
    zfs = iocage.lib.ZFS.ZFS()
    zfs.logger = logger
    host = iocage.lib.Host.Host(logger=logger, zfs=zfs)
    print_events = ctx.parent.print_events

    ioc_jail = iocage.lib.Jail.JailGenerator(
        dict(name=jail),
        logger=logger,
        zfs=zfs,
        host=host,
        new=True
    )

    if ioc_jail.exists is True:
        logger.error(f"The jail {jail} already exists")
        exit(1)

    try:
        print_events(ioc_jail.backup.restore(source))
    except iocage.lib.errors.IocageException:
        exit(1)
