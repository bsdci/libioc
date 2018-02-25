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
"""Restart a jail with the CLI."""
import typing
import click

import iocage.lib.errors
import iocage.lib.events
import iocage.lib.Jails
import iocage.lib.Logger

from .shared.click import IocageClickContext

__rootcmd__ = True


@click.command(name="restart", help="Restarts the specified jails.")
@click.pass_context
@click.option(
    '--shutdown',
    '-s',
    default=False,
    is_flag=True,
    help="Entirely shutdown jail during restart"
)
@click.option(
    '--force',
    '-f',
    default=False,
    is_flag=True,
    help="Force jail shutdown during restart"
)
@click.argument("jails", nargs=-1)
def cli(
    ctx: IocageClickContext,
    shutdown: bool,
    force: bool,
    jails: typing.Tuple[str, ...]
) -> None:
    """Restart a jail."""
    logger = ctx.parent.logger
    print_function = ctx.parent.print_events

    # force implies shutdown
    if force is True:
        shutdown = True

    if len(jails) == 0:
        logger.error("No jail selector provided")
        exit(1)

    ioc_jails = iocage.lib.Jails.JailsGenerator(
        logger=logger,
        filters=jails
    )

    changed_jails = []
    failed_jails = []
    for jail in ioc_jails:

        try:
            print_function(_restart_jail(
                jail,
                shutdown=shutdown,
                force=force
            ))
            changed_jails.append(jail)
        except StopIteration:
            failed_jails.append(jail)

    if len(failed_jails) > 0:
        exit(1)

    if len(changed_jails) == 0:
        jails_input = " ".join(list(jails))
        logger.error(f"No jails matched your input: {jails_input}")
        exit(1)

    exit(0)


def _restart_jail(
    jail: 'iocage.lib.Jail.JailsGenerator',
    shutdown: bool=False,
    force: bool=False
) -> typing.Generator['iocage.lib.events.IocageEvent', None, None]:

    failed: bool = False
    jailRestartEvent = iocage.lib.events.JailRestart(jail=jail)
    jailShutdownEvent = iocage.lib.events.JailShutdown(jail=jail)
    JailSoftShutdownEvent = iocage.lib.events.JailSoftShutdown(jail=jail)
    jailStartEvent = iocage.lib.events.JailStart(jail=jail)

    yield jailRestartEvent.begin()

    if shutdown is False:

        # soft stop
        yield JailSoftShutdownEvent.begin()
        try:
            jail.exec_hook("start")
            yield JailSoftShutdownEvent.end()
        except iocage.lib.errors.IocageException:
            yield JailSoftShutdownEvent.fail(exception=False)

        # service start
        yield jailStartEvent.begin()
        try:
            jail.exec_hook("start")
            yield jailStartEvent.end()
        except iocage.lib.errors.IocageException:
            yield jailStartEvent.fail(exception=False)

    else:

        # full shutdown
        yield jailShutdownEvent.begin()
        try:
            for event in jail.stop():
                yield event
            yield jailShutdownEvent.end()
        except iocage.lib.errors.IocageException:
            failed = True
            yield jailShutdownEvent.fail(exception=False)
            if force is False:
                # only continue when force is enabled
                yield jailRestartEvent.fail(exception=False)
                return

        # start
        yield jailStartEvent.begin()
        try:
            for event in jail.start():
                yield event
            yield jailStartEvent.end()
        except iocage.lib.errors.IocageException:
            failed = True
            yield jailStartEvent.fail(exception=False)

        # respond to failure
        if failed is True:
            yield jailRestartEvent.fail(exception=False)
            return

    yield jailRestartEvent.end()
