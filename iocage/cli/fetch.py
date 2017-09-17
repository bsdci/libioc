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
"""fetch module for the cli."""
import click

import iocage.lib.Host
import iocage.lib.Prompts
import iocage.lib.Release
import iocage.lib.errors


__rootcmd__ = True


@click.command(context_settings=dict(
    max_content_width=400, ),
    name="fetch", help="Fetch a version of FreeBSD for jail usage or a"
                       " preconfigured plugin.")
@click.pass_context
@click.option("--url", "-u",
              help="Remote URL with path to the release/snapshot directory")
@click.option("--file", "-F", multiple=True,
              help="Specify the files to fetch from the mirror.")
@click.option("--release", "-r",
              # type=release_choice(),
              help="The FreeBSD release to fetch.")
@click.option("--update/--no-update", "-U/-NU", default=True,
              help="Update the release to the latest patch level.")
@click.option("--fetch-updates/--no-fetch-updates", default=True,
              help="Skip fetching release updates")
# Compat
@click.option("--http", "-h", default=False,
              help="Have --server define a HTTP server instead.", is_flag=True)
# Compat files
@click.option("--files", multiple=True,
              help="Specify the files to fetch from the mirror. "
                   "(Deprecared: renamed to --file)")
def cli(ctx, **kwargs):
    logger = ctx.parent.logger
    host = iocage.lib.Host.HostGenerator(logger=logger)
    prompts = iocage.lib.Prompts.Prompts(host=host, logger=logger)

    release_input = kwargs["release"]
    if release_input is None:
        try:
            release = prompts.release()
        except iocage.lib.errors.DefaultReleaseNotFound:
            exit(1)
    else:
        try:
            release = iocage.lib.Release.ReleaseGenerator(
                name=release_input,
                host=host,
                logger=logger
            )
        except:
            logger.error(f"Invalid Release '{release_input}'")
            exit(1)

    url_or_files_selected = False

    if is_option_enabled(kwargs, "url"):
        release.mirror_url = kwargs["url"]
        url_or_files_selected = True

    if is_option_enabled(kwargs, "files"):
        release.assets = list(kwargs["files"])
        url_or_files_selected = True

    if (url_or_files_selected is False) and (release.available is False):
        logger.error(f"The release '{release.name}' is not available")
        exit(1)

    fetch_updates = bool(kwargs["fetch_updates"])
    ctx.parent.print_events(release.fetch(
        update=kwargs["update"],
        fetch_updates=fetch_updates
    ))

    exit(0)


def is_option_enabled(args, name):
    try:
        value = args[name]
        if value:
            return True
    except KeyError:
        pass

    return False
