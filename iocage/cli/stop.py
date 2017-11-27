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
"""stop module for the cli."""
import typing
import click

import iocage.lib.errors
import iocage.lib.Jails
import iocage.lib.Logger

from .shared import IocageClickContext

__rootcmd__ = True


@click.command(name="stop", help="Stops the specified jails or ALL.")
@click.pass_context
@click.option("--rc", default=False, is_flag=True,
              help="Will stop all jails with boot=on, in the specified"
                   " order with higher value for priority stopping first.")
@click.option("--log-level", "-d", default=None)
@click.option("--force", "-f", is_flag=True, default=False,
              help="Skip checks and enforce jail shutdown")
@click.argument("jails", nargs=-1)
def cli(
    ctx: IocageClickContext,
    rc: bool,
    log_level: str,
    force: bool,
    jails: typing.Set[str]
) -> None:
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to stop_jail.
    """
    logger = ctx.parent.logger

    if rc is True:
        if len(jails) > 0:
            logger.error("Cannot use --rc and jail selectors simultaniously")
            exit(1)

        autostop(logger=logger, print_function=ctx.parent.print_events)
    else:
        if not normal(
            jails,
            logger=logger,
            print_function=ctx.parent.print_events,
            force=force
        ):
            exit(1)


def stop_jails(
    jails: typing.Iterator[iocage.lib.Jails.JailsGenerator],
    logger: iocage.lib.Logger.Logger,
    print_function: typing.Callable[
        [typing.Generator[iocage.lib.events.IocageEvent, None, None]],
        None
    ],
    force: bool
) -> bool:

    changed_jails = []
    failed_jails = []
    for jail in jails:
        try:
            print_function(jail.stop(force=force))
        except iocage.lib.errors.IocageException:
            failed_jails.append(jail)
            continue

        logger.log(f"{jail.name} stopped")
        changed_jails.append(jail)

    if len(failed_jails) > 0:
        return False

    if len(changed_jails) == 0:
        jails_input = " ".join(list(jails))
        logger.error(f"No jails matched your input: {jails_input}")
        return False

    return False


def normal(
    filters: typing.Set[str],
    logger: iocage.lib.Logger.Logger,
    print_function: typing.Callable[
        [typing.Generator[iocage.lib.events.IocageEvent, None, None]],
        None
    ],
    force: bool
) -> bool:

    jails = iocage.lib.Jails.JailsGenerator(
        logger=logger,
        filters=filters
    )

    if len(jails) == 0:
        logger.error("No jail selector provided")
        return False

    stop_jails(
        jails,
        logger=logger,
        print_function=print_function,
        force=force
    )
    return True


def autostop(
    logger: iocage.lib.Logger.Logger,
    print_function: typing.Callable[
        [typing.Generator[iocage.lib.events.IocageEvent, None, None]],
        None
    ]
) -> None:

    filters = ("boot=yes", "running=yes",)

    ioc_jails = iocage.lib.Jails.JailsGenerator(
        logger=logger,
        filters=filters
    )

    # sort jails by their priority
    jails = reversed(sorted(
        list(ioc_jails),
        key=lambda x: x.config["priority"]
    ))

    stop_jails(
        jails,
        logger=logger,
        print_function=print_function,
        force=False
    )
