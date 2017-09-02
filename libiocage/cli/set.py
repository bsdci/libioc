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
import click

import libiocage.lib.Jails
import libiocage.lib.Logger
import libiocage.lib.helpers

__rootcmd__ = True


@click.command(context_settings=dict(
    max_content_width=400, ), name="set", help="Sets the specified property.")
@click.pass_context
@click.argument("props", nargs=-1)
@click.argument("jail", nargs=1, required=True)
def cli(ctx, props, jail):
    """Get a list of jails and print the property."""

    logger = ctx.parent.logger

    filters = (f"name={jail}",)
    ioc_jails = libiocage.lib.Jails.JailsGenerator(
        filters,
        logger=logger
    )

    for jail in ioc_jails:

        updated_properties = set()

        for prop in props:

            if _is_setter_property(prop):
                key, value = prop.split("=", maxsplit=1)
                changed = jail.config.set(key, value)
                if changed:
                    updated_properties.add(key)
            else:
                key = prop
                del jail.config[key]

        if len(updated_properties) == 0:
            logger.screen(f"Jail '{jail.humanreadable_name}' unchanged")
        else:
            logger.screen(
                f"Jail '{jail.humanreadable_name}' updated: " +
                ", ".join(updated_properties)
            )
            jail.save()


def _is_setter_property(property_string):
    return "=" in property_string
