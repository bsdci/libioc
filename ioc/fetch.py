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
"""Fetch releases and updates with the CLI."""
import click
import typing

import iocage.Host
import iocage.Prompts
import iocage.Release
import iocage.errors

from .shared.click import IocageClickContext

__rootcmd__ = True


@click.command(
    # context_settings=dict(max_content_width=400),
    name="fetch",
    help="Fetch and update a Release to create Jails from them."
)
@click.pass_context
@click.option(
    "--url", "-u",
    help="Remote URL with path to the release/snapshot directory"
)
@click.option(  # noqa: T484
    "--file", "-F",  # noqa: T484
    multiple=True,
    help="Specify the files to fetch from the mirror."
)
@click.option(
    "--release", "-r",
    help="The FreeBSD release to fetch."
)
@click.option(
    "--update/--no-update", "-U/-NU",
    default=True,
    help="Update the release to the latest patch level."
)
@click.option(
    "--fetch-updates/--no-fetch-updates",
    default=True,
    help="Skip fetching release updates"
)
@click.option(  # Compatibility
    "--http", "-h",
    default=False,
    is_flag=True,
    help="Have --server define a HTTP server instead."
)
@click.option(  # Basejail Update
    "--copy-basejail-only",
    "-b",
    is_flag=True,
    default=False,
    help="Update basejail after changes"
)
@click.option(  # Compatibility
    "--files",
    multiple=True,
    help=(
        "Specify the files to fetch from the mirror. "
        "(Deprecared: renamed to --file)"
    )
)
def cli(  # noqa: T484
    ctx: IocageClickContext,
    **kwargs
) -> None:
    """Fetch and update releases."""
    logger = ctx.parent.logger
    host = ctx.parent.host
    zfs = ctx.parent.zfs
    prompts = iocage.Prompts.Prompts(host=host, logger=logger)

    release_input = kwargs["release"]
    if release_input is None:
        try:
            release = prompts.release()
        except iocage.errors.DefaultReleaseNotFound:
            exit(1)
    else:
        try:
            release = iocage.Release.ReleaseGenerator(
                name=release_input,
                host=host,
                zfs=zfs,
                logger=logger
            )
        except iocage.errors.IocageException:
            exit(1)

    if kwargs["copy_basejail_only"] is True:
        try:
            release.update_base_release()
            exit(0)
        except iocage.errors.IocageException:
            exit(1)

    url_or_files_selected = False

    if _is_option_enabled(kwargs, "url"):
        release.mirror_url = kwargs["url"]
        url_or_files_selected = True

    if _is_option_enabled(kwargs, "files"):
        release.assets = list(kwargs["files"])
        url_or_files_selected = True

    if (url_or_files_selected is False) and (release.available is False):
        logger.error(f"The release '{release.name}' is not available")
        exit(1)

    fetch_updates = bool(kwargs["fetch_updates"])
    try:
        ctx.parent.print_events(release.fetch(
            update=kwargs["update"],
            fetch_updates=fetch_updates
        ))
    except iocage.errors.IocageException:
        exit(1)

    exit(0)


def _is_option_enabled(args: typing.Dict[str, typing.Any], name: str) -> bool:
    try:
        value = args[name]
        if value:
            return True
    except KeyError:
        pass

    return False
