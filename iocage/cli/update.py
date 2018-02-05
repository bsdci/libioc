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

import iocage.lib.errors
import iocage.lib.Jails
import iocage.lib.Logger
import iocage.lib.Config.Jail.File.Fstab

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
    print_function = ctx.parent.print_events

    if len(jails) == 0:
        logger.error("No jail selector provided")
        exit(1)

    zfs = iocage.lib.ZFS.ZFS(logger=logger)
    host = iocage.lib.Host.Host(logger=logger, zfs=zfs)

    if host.distribution.name == "HardenedBSD":
        update_command = [
            "/usr/sbin/hbsd-update",
            "-B",  # nobase=1
            "-n",  # no_kernel=1
            "-t",
            "-D",  # nodownload=1
            "/var/db/freebsd-update/hbsd-update"
        ]
    else:
        update_command = [
            "/usr/sbin/hbsd-update",
            "-B",  # nobase=1
            "-n"  # no_kernel=1
        ]

    filters = jails + ("template=no",)
    jails = iocage.lib.Jails.JailsGenerator(
        logger=logger,
        host=host,
        zfs=zfs,
        filters=filters
    )

    destination_path = "/var/db/freebsd-update"
    changed_jails = []
    failed_jails = []
    for jail in jails:
        _fstab_written = False
        try:
            jail.require_jail_not_template()

            jail.fstab.read_file()
            jail.fstab.new_line(
                source=f"{jail.release.root_dir}{destination_path}",
                destination=destination_path,
                fs_type="nullfs",
                options="ro",
                dump="0",
                passnum="0",
                comment=None
            )
            jail.fstab.save()
            logger.verbose(
                f"{destination_path} temporarily added to {jail.fstab.path}"
            )
            _fstab_written = True

            print_function(jail.fork_exec(
                command=update_command,
                vnet=False,
                interfaces="",
                ip4_addr=None,
                ip6_addr=None,
                secure_level=0,
                allow_chflags=True
            ))

        except iocage.lib.errors.IocageException:
            failed_jails.append(jail)
            continue

        if _fstab_written is True:
            del jail.fstab[len(jail.fstab) - 1]
            jail.fstab.save()
            logger.verbose(f"{jail.fstab.path} restored")

        changed_jails.append(jail)

    if len(failed_jails) > 0:
        return False

    if len(changed_jails) == 0:
        jails_input = " ".join(list(jails))
        logger.error(
            f"No jail was updated or matched your input: {jails_input}"
        )
        return False

    return True
