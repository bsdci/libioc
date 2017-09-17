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
"""start module for the cli."""
import click

import iocage.lib.Jails
import iocage.lib.Logger

__rootcmd__ = True


@click.command(name="start", help="Starts the specified jails or ALL.")
@click.pass_context
@click.option("--rc", default=False, is_flag=True,
              help="Will start all jails with boot=on, in the specified"
                   " order with smaller value for priority starting first.")
@click.argument("jails", nargs=-1)
def cli(ctx, rc, jails):
    """
    Starts Jails
    """

    logger = ctx.parent.logger
    start_args = {
        "logger": logger,
        "print_function": ctx.parent.print_events
    }

    if len(jails) == 0:
        logger.error("No jail selector provided")
        exit(1)

    elif rc is True:
        if len(jails) > 0:
            logger.error("Cannot use --rc and jail selectors simultaniously")
            exit(1)
        autostart(**start_args)
    else:
        normal(jails, **start_args)


def autostart(logger, print_function):

    filters = ("boot=yes",)

    ioc_jails = iocage.lib.Jails.JailsGenerator(
        logger=logger,
        filters=filters
    )

    # sort jails by their priority
    jails = sorted(
        list(ioc_jails),
        key=lambda x: x.config["priority"]
    )

    start_jails(jails, logger=logger, print_function=print_function)


def normal(filters, logger, print_function):

    jails = iocage.lib.Jails.JailsGenerator(
        logger=logger,
        filters=filters
    )

    start_jails(jails, logger=logger, print_function=print_function)


def start_jails(jails, logger, print_function):

    changed_jails = []
    failed_jails = []
    for jail in jails:
        try:
            print_function(jail.start())

        except Exception:
            failed_jails.append(jail)
            raise
            continue

        logger.log(f"{jail.humanreadable_name} running as JID {jail.jid}")
        changed_jails.append(jail)

    if len(failed_jails) > 0:
        exit(1)

    if len(changed_jails) == 0:
        jails_input = " ".join(list(jails))
        logger.error(f"No jailes matches your input: {jails_input}")
        exit(1)
