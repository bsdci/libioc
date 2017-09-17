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
import json
import texttable
import typing

import iocage.lib.Logger
import iocage.lib.Host
import iocage.lib.Resource
import iocage.lib.Jails
import iocage.lib.Releases


supported_output_formats = ['table', 'csv', 'list', 'json']


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

    host = iocage.lib.Host.Host(logger=logger)

    if remote and not plugins:

        available_releases = host.distribution.releases
        for available_release in available_releases:
            logger.screen(available_release.name)
        return

    if plugins and remote:
        raise iocage.lib.errors.MissingFeature("Plugins", plural=True)

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

    if dataset_type == "base":
        resources_class = iocage.lib.Releases.ReleasesGenerator
        columns = ["name"]
    else:
        resources_class = iocage.lib.Jails.JailsGenerator
        columns = _list_output_comumns(output, _long)

    resources = resources_class(
        logger=logger,
        host=host,
        filters=filters  # ToDo: allow quoted whitespaces from user input
    )

    if output_format == "list":
        _print_list(resources, columns, header, "\t")
    elif output_format == "csv":
        _print_list(resources, columns, header, ";")
    elif output_format == "json":
        _print_json(resources, columns)
    else:
        _print_table(resources, columns, header, _sort)


def _print_table(
    resources: typing.Generator[
        iocage.lib.Resource.ListableResource,
        None,
        None
    ],
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

    for resource in resources:
        table_data.append(_lookup_resource_values(resource, columns))

    if sort_index is not None:
        table_data.sort(key=lambda x: x[sort_index])

    if show_header:
        table.add_rows([table_head] + table_data)
    else:
        table.add_rows(table_data)

    print(table.draw())


def _print_list(
    resources: typing.Generator[
        iocage.lib.Jails.JailsGenerator,
        None,
        None
    ],
    columns: list,
    show_header: bool,
    separator: str=";"
) -> None:

    if show_header is True:
        print(separator.join(columns).upper())

    for resource in resources:
        print(separator.join(_lookup_resource_values(resource, columns)))


def _print_json(
    resources: typing.Generator[
        iocage.lib.Jails.JailsGenerator,
        None,
        None
    ],
    columns: list,
    **json_dumps_args
):

    if "indent" not in json_dumps_args.keys():
        json_dumps_args["indent"] = 2

    if "sort_keys" not in json_dumps_args.keys():
        json_dumps_args["sort_keys"] = True

    output = []

    for resource in resources:
        output.append(dict(zip(
            columns,
            _lookup_resource_values(resource, columns)
        )))

    print(json.dumps(output, **json_dumps_args))


def _lookup_resource_values(resource, columns) -> typing.List[str]:
    return list(map(
        lambda column: resource.getstring(column),
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
