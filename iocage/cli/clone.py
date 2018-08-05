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
"""Clone and promote jails."""
import click

import iocage.lib.errors
import iocage.lib.ZFS
import iocage.lib.Jail

from .shared.click import IocageClickContext

__rootcmd__ = True


def _is_dataset_name(name: str) -> bool:
    return "/" in name


@click.command(name="clone")
@click.pass_context
@click.argument(
    "source",
    nargs=1,
    required=True
)
@click.argument(
    "destination",
    nargs=1,
    required=True
)
def cli(
    ctx: IocageClickContext,
    source: str,
    destination: str
) -> None:
    """Clone and promote jails."""
    print_function = ctx.parent.print_events
    logger = ctx.parent.logger

    ioc_source_jail = iocage.lib.Jail.JailGenerator(
        dict(id=source),
        logger=logger,
        zfs=ctx.parent.zfs,
        host=ctx.parent.host
    )

    ioc_destination_jail = iocage.lib.Jail.JailGenerator(
        dict(id=destination),
        new=True,
        logger=logger,
        zfs=ctx.parent.zfs,
        host=ctx.parent.host
    )

    try:
        print_function(ioc_destination_jail.clone_from_jail(ioc_source_jail))
    except iocage.lib.errors.IocageException as e:
        exit(1)
