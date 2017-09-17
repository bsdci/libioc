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
import click

import iocage.lib.Jail
import iocage.lib.Jails
import iocage.lib.Releases
import iocage.lib.Logger
import iocage.lib.Resource

__rootcmd__ = True


@click.command(name="destroy", help="Destroy specified resource")
@click.pass_context
@click.option("--force", "-f", default=False, is_flag=True,
              help="Destroy the jail without warnings or more user input.")
@click.option("--release", "-r", default=False, is_flag=True,
              help="Destroy a specified RELEASE dataset.")
@click.option("--recursive", "-R", default=False, is_flag=True,
              help="Bypass the children prompt, best used with --force (-f).")
@click.option("--download", "-d", default=False, is_flag=True,
              help="Destroy the download dataset of the specified RELEASE as"
                   " well.")
@click.argument("filters", nargs=-1)
def cli(ctx, force, release, recursive, download, filters):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to stop_jail.
    """
    logger = ctx.parent.logger
    host = iocage.lib.Host.Host(logger=logger)

    if len(filters) == 0:
        logger.error("No filter specified - cannot select a target to delete")
        exit(1)

    if release is True:
        resources_class = iocage.lib.Releases.ReleasesGenerator
    else:
        resources_class = iocage.lib.Jails.JailsGenerator

    resources = resources_class(
        filters=filters,
        host=host,
        logger=logger
    )

    if len(list(resources)) == 0:
        print(filters)
        logger.error("No target matched your input")
        exit(1)

    failed_items = []

    for item in resources:

        old_mountpoint = item.dataset.mountpoint

        # ToDo: generalize and move this Method from Jail to LaunchableResource
        if isinstance(item, iocage.lib.Jail.JailGenerator):
            try:
                item.require_jail_stopped()
            except:
                logger.log(
                    "Jail '{item.name}' needs to be stopped before destruction"
                )
                failed_items.append(item)
                continue

        item.destroy()
        logger.screen(f"{old_mountpoint} destroyed")

    if len(failed_items) > 0:
        exit(1)
