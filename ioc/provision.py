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
"""Provision jails from the CLI.."""
import typing
import click

import iocage.errors
import iocage.Jails
import iocage.Logger

from .shared.click import IocageClickContext
from .shared.jail import set_properties

__rootcmd__ = True


@click.command(name="start", help="Trigger provisioning of jails.")
@click.pass_context
@click.argument("jails", nargs=-1)
@click.option(
    "--option", "-o",
    "temporary_config_override",
    multiple=True,
    help="Temporarily override jail config options"
)
def cli(
    ctx: IocageClickContext,
    jails: typing.Tuple[str, ...],
    temporary_config_override: typing.Tuple[str, ...]
) -> None:
    """Run jail provisioner as defined in jail config."""
    logger = ctx.parent.logger
    start_args = {
        "zfs": ctx.parent.zfs,
        "host": ctx.parent.host,
        "logger": logger,
        "print_function": ctx.parent.print_events
    }

    if not _provision(
        filters=jails,
        temporary_config_override=temporary_config_override,
        **start_args
    ):
        exit(1)


def _provision(
    filters: typing.Tuple[str, ...],
    temporary_config_override: typing.Tuple[str, ...],
    zfs: iocage.ZFS.ZFS,
    host: iocage.Host.HostGenerator,
    logger: iocage.Logger.Logger,
    print_function: typing.Callable[
        [typing.Generator[iocage.events.IocageEvent, None, None]],
        None
    ]
) -> bool:

    jails = iocage.Jails.JailsGenerator(
        logger=logger,
        zfs=zfs,
        host=host,
        filters=filters
    )

    changed_jails = []
    failed_jails = []
    for jail in jails:
        try:
            set_properties(
                properties=temporary_config_override,
                target=jail
            )
        except iocage.errors.IocageException:
            exit(1)

        try:
            print_function(_execute_provisioner(jail))
        except iocage.errors.IocageException:
            failed_jails.append(jail)
            continue

        changed_jails.append(jail)

    if len(failed_jails) > 0:
        return False

    if len(changed_jails) == 0:
        jails_input = " ".join(list(jails))
        logger.error(f"No jails started your input: {jails_input}")
        return False

    return True


def _execute_provisioner(
    jail: 'iocage.Jail.JailsGenerator'
) -> typing.Generator['iocage.events.IocageEvent', None, None]:
    for event in jail.provisioner.provision():
        yield event
        if isinstance(event, iocage.events.JailCommandExecution):
            if event.done is True:
                print(event.stdout)
