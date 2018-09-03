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
"""Create jails with the CLI."""
import click
import typing

import iocage.errors
import iocage.Host
import iocage.Jail
import iocage.Logger
import iocage.Release
import iocage.ZFS

from .shared.click import IocageClickContext

__rootcmd__ = True


def validate_count(
    ctx: IocageClickContext,
    param: typing.Union[
        click.Option,
        typing.Union[click.Option, click.Parameter],
        typing.Union[bool, int, str]
    ],
    value: typing.Any
) -> int:
    """Take a string, removes the commas and returns an int."""
    if isinstance(value, str):
        try:
            value = value.replace(",", "")

            return int(value)
        except ValueError:
            logger = iocage.Logger.Logger()
            logger.error(f"{value} is not a valid integer.")
            exit(1)
    else:
        return int(value)


@click.command(
    name="create",
    help="Create a jail."
)
@click.pass_context
@click.option(
    "--count", "-c",
    callback=validate_count,
    default=1,
    help=(
        "Designate a number of jails to create."
        "Jails are numbered sequentially."
    )
)
@click.option(
    "--release", "-r",
    required=False,
    help="Specify the RELEASE to use for the new jail."
)
@click.option(
    "--template", "-t",
    required=False,
    help="Specify the template to use for the new jail instead of a RELEASE."
)
@click.option(
    "--basejail/--no-basejail", "-b/-nb",
    is_flag=True,
    default=True,
    help=(
        "Set the new jail type to a basejail (default). "
        "Basejails mount the specified RELEASE directories over the "
        "jail's directories."
    )
)
@click.option(
    "--empty", "-e",
    is_flag=True,
    default=False,
    help="Create an empty jail used for unsupported or custom jails.")
@click.option(
    "--no-fetch",
    is_flag=True,
    default=False,
    help="Do not automatically fetch releases"
)
@click.argument("name")
@click.argument("props", nargs=-1)
def cli(
    ctx: IocageClickContext,
    release: typing.Optional[str],
    template: typing.Optional[str],
    count: int,
    props: typing.Tuple[str, ...],
    basejail: bool,
    empty: bool,
    name: str,
    no_fetch: bool
) -> None:
    """Create iocage jails."""
    logger = ctx.parent.logger
    zfs: iocage.ZFS.ZFS = ctx.parent.zfs
    host: iocage.Host.Host = ctx.parent.host

    jail_data: typing.Dict[str, typing.Any] = {}

    if (release is None) and (template is None):
        logger.spam(
            "No release selected (-r, --release)."
            f" Selecting host release '{host.release_version}' as default."
        )
        release = host.release_version

    try:
        resource_selector = iocage.ResourceSelector.ResourceSelector(
            name,
            logger=logger
        )
    except iocage.errors.IocageException:
        exit(1)

    jail_data["name"] = resource_selector.name
    root_datasets_name = resource_selector.source_name

    try:
        if release is not None:
            resource = iocage.Release.ReleaseGenerator(
                name=release,
                root_datasets_name=root_datasets_name,
                logger=logger,
                host=host,
                zfs=zfs
            )
            if resource.fetched is False:
                if not resource.available:
                    logger.error(
                        f"The release '{resource.name}' does not exist"
                    )
                    exit(1)

                msg = (
                    f"The release '{resource.name}' is available,"
                    " but not downloaded yet"
                )
                if no_fetch:
                    logger.error(msg)
                    exit(1)
                else:
                    logger.spam(msg)
                    logger.log(
                        f"Automatically fetching release '{resource.name}'"
                    )
                    resource.fetch()
        elif template is not None:
            resource = iocage.Jail.JailGenerator(
                template,
                root_datasets_name=root_datasets_name,
                logger=logger,
                host=host,
                zfs=zfs
            )
        else:
            logger.error("No release or jail selected")
            exit(1)

        if basejail:
            jail_data["basejail"] = True

        if props:
            for prop in props:
                try:
                    key, value = prop.split("=", maxsplit=1)
                    jail_data[key] = value
                except (ValueError, KeyError):
                    logger.error(f"Invalid property {prop}")
                    exit(1)
    except iocage.errors.IocageException:
        exit(1)

    errors = False
    for i in range(count):

        jail = iocage.Jail.JailGenerator(
            jail_data,
            root_datasets_name=root_datasets_name,
            logger=logger,
            host=host,
            zfs=zfs,
            new=True
        )
        suffix = f" ({i}/{count})" if count > 1 else ""
        try:
            jail.create(resource)
            msg_source = f" on {jail.source}" if len(host.datasets) > 1 else ""
            msg = (
                f"{jail.humanreadable_name} successfully created"
                f" from {resource.name}"
                f"{msg_source}!{suffix}"
            )
            logger.log(msg)
        except iocage.errors.IocageException:
            exit(1)

    exit(int(errors))
