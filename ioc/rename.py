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
"""Rename a jail."""
import click

import iocage.Jail

from .shared.click import IocageClickContext

__rootcmd__ = True


@click.command(name="rename", help="Rename a stopped jail.")
@click.pass_context
@click.argument("jail", nargs=1)
@click.argument("name", nargs=1)
def cli(
    ctx: IocageClickContext,
    jail: str,
    name: str
) -> None:
    """Rename a stopped jail."""
    logger = ctx.parent.logger
    print_function = ctx.parent.print_events

    try:
        ioc_jail = iocage.Jail.Jail(
            jail,
            logger=logger,
            zfs=ctx.parent.zfs,
            host=ctx.parent.host
        )
        print_function(ioc_jail.rename(name))
    except iocage.errors.IocageException:
        exit(1)

