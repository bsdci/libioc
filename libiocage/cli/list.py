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
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANYw
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""list module for the cli."""
import click
import texttable
import typing

import libiocage.lib.Host
import libiocage.lib.Jails
import libiocage.lib.JailFilter
import libiocage.lib.Logger

supported_output_formats = ['table', 'csv', 'list']


@click.command(name="list", help="List a specified dataset type, by default"
                                 " lists all jails.")
@click.pass_context
@click.option("--release", "--base", "-r", "-b", "dataset_type",
              flag_value="base", help="List all bases.")
@click.option("--template", "-t", "dataset_type", flag_value="template",
              help="List all templates.")
@click.option("--long", "-l", "_long", is_flag=True, default=False,
              help="Show the full uuid and ip4 address.")
@click.option("--remote", "-R", is_flag=True, help="Show remote's available "
                                                   "RELEASEs.")
@click.option("--plugins", "-P", is_flag=True, help="Show available plugins.")
@click.option("--sort", "-s", "_sort", default=None, nargs=1,
              help="Sorts the list by the given type")
@click.option("--quick", "-q", is_flag=True, default=False,
              help="Lists all jails with less processing and fields.")
@click.option("--output", "-o", default=None)
@click.option("--output-format", "-f", default="table",
              type=click.Choice(supported_output_formats))
@click.option("--header/--no-header", "-H/-NH", is_flag=True, default=True,
              help="Show or hide column name heading.")
@click.argument("filters", nargs=-1)
def cli(ctx, dataset_type, header, _long, remote, plugins,
        _sort, quick, output, output_format, filters):
    logger = ctx.parent.logger

    host = libiocage.lib.Host.Host(logger=logger)

    if remote and not plugins:

        available_releases = host.distribution.releases
        for available_release in available_releases:
            logger.screen(available_release.name)
        return

    if plugins and remote:
        raise libiocage.lib.errors.MissingFeature("Plugins", plural=True)

    if output is not None and _long is True:
        logger.error("--output and --long can't be used together")
        exit(1)

    if output_format != "table" and _sort is not None:
        # Sorting destroys the ability to stream generators
        # ToDo: Figure out if we need to sort other output formats as well
        raise Exception("Sorting only allowed for tables")

    # empty filters will match all jails
    if len(filters) == 0:
        filters += ("*",)

    jails = libiocage.lib.Jails.JailsGenerator(
        logger=logger,
        host=host,
        filters=filters  # ToDo: allow quoted whitespaces from user input
    )

    columns = _list_output_comumns(output, _long)

    if output_format == "list":
        _print_list(jails, columns, header, "\t")
    elif output_format == "csv":
        _print_list(jails, columns, header, ";")
    else:
        _print_table(jails, columns, header, _sort)


def _print_table(
    jails: typing.Generator[libiocage.lib.Jails.JailsGenerator, None, None],
    columns: list,
    show_header: bool,
    sort_key: str=None
) -> None:

    table = texttable.Texttable(max_width=0)
    table.set_cols_dtype(["t"] * len(columns))

    table_head = (list(x.upper() for x in columns))
    table_data = []

    try:
        sort_index = columns.index(sort_key)
    except ValueError:
        sort_index = None

    for jail in jails:
        table_data.append(_lookup_jail_values(jail, columns))

    if sort_index is not None:
        table_data.sort(key=lambda x: x[sort_index])

    if show_header:
        table.add_rows([table_head] + table_data)
    else:
        table.add_rows(table_data)

    print(table.draw())


def _print_list(
    jails: typing.Generator[libiocage.lib.Jails.JailsGenerator, None, None],
    columns: list,
    show_header: bool,
    separator: str=";"
) -> None:

    if show_header is True:
        print(separator.join(columns).upper())

    for jail in jails:
        print(separator.join(_lookup_jail_values(jail, columns)))


def _lookup_jail_values(jail, columns) -> typing.List[str]:
    return list(map(
        lambda column: jail.getstring(column),
        columns
    ))


def _list_output_comumns(
    user_input: str="",
    long_mode: bool=False
) -> list:

    if user_input:
        return user_input.strip().split(',')
    else:
        columns = ["jid", "name"]

        if long_mode is True:
            columns += [
                "running",
                "release",
                "ip4.addr",
                "ip6.addr"
            ]
        else:
            columns += [
                "running",
                "release",
                "ip4.addr"
            ]

        return columns
