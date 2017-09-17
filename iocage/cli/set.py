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

import iocage.lib.Logger
import iocage.lib.helpers
import iocage.lib.Resource
import iocage.lib.Jails

__rootcmd__ = True


@click.command(
    context_settings=dict(max_content_width=400,),
    name="set",
    help="Sets the specified property."
)
@click.pass_context
@click.argument("props", nargs=-1)
@click.argument("jail", nargs=1, required=True)
def cli(ctx, props, jail):
    """Get a list of jails and print the property."""

    logger = ctx.parent.logger
    host = iocage.lib.Host.HostGenerator(logger=logger)

    # Defaults
    if jail == "defaults":
        updated_properties = set_properties(props, host.defaults)
        if len(updated_properties) > 0:
            logger.screen("Defaults updated: " + ", ".join(updated_properties))
        else:
            logger.screen("Defaults unchanged")
        return

    # Jail Properties
    filters = (f"name={jail}",)
    ioc_jails = iocage.lib.Jails.JailsGenerator(
        filters,
        host=host,
        logger=logger
    )

    updated_jail_count = 0

    for jail in ioc_jails:

        updated_properties = set_properties(props, jail)

        if len(updated_properties) == 0:
            logger.screen(f"Jail '{jail.humanreadable_name}' unchanged")
        else:
            logger.screen(
                f"Jail '{jail.humanreadable_name}' updated: " +
                ", ".join(updated_properties)
            )

        updated_jail_count += 1

    if updated_jail_count == 0:
        logger.error("No jails to update")
        exit(1)

    exit(0)


def set_properties(
    properties: typing.List[str],
    target: 'iocage.lib.LaunchableResource.LaunchableResource'
) -> set:

    updated_properties = set()

    for prop in properties:

        if _is_setter_property(prop):
            key, value = prop.split("=", maxsplit=1)
            changed = target.config.set(key, value)
            if changed:
                updated_properties.add(key)
        else:
            key = prop
            try:
                del target.config[key]
                updated_properties.add(key)
            except:
                pass

    if len(updated_properties) > 0:
        target.save()

    return updated_properties


def _is_setter_property(property_string):
    return "=" in property_string
