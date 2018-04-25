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
"""Console subcommand for the CLI."""
import click

import iocage.lib.Jail
import iocage.lib.Logger

__rootcmd__ = True


@click.command(name="console", help="Login to a jail.")
@click.pass_context
@click.argument("jail")
@click.option("--start", "-s", is_flag=True, default=False)
def cli(ctx, jail, start):
    """Run jexec to login into the specified jail."""
    logger = ctx.parent.logger

    try:
        ioc_jail = iocage.lib.Jail.JailGenerator(jail, logger=logger)
        ioc_jail.state.query()
    except iocage.lib.errors.JailNotFound:
        exit(1)

    if not ioc_jail.running:
        if start is True:
            ctx.parent.print_events(ioc_jail.start())
        else:
            logger.error(
                f"The jail {ioc_jail.humanreadable_name} is not running"
            )
            exit(1)

    jail.exec_console()
