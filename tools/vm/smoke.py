# Copyright (c) 2026, the libioc contributors
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
"""End-to-end smoke test running a complete jail lifecycle.

The script expects a ZFS pool named ioc-test, as created by the guest
setup script, and a fetched release, as downloaded by the test suite.
It creates a jail from the release, starts it, executes a command
inside, stops it and destroys it again.
"""
import os
import sys

import libzfs

import libioc.Datasets
import libioc.Host
import libioc.Jail
import libioc.Logger
import libioc.Release

POOL_NAME = "ioc-test"
MIRROR = os.environ.get(
    "LIBIOC_TEST_MIRROR",
    "http://ftp-archive.freebsd.org/pub/FreeBSD-Archive"
    f"/old-releases/{os.uname().machine}/{os.uname().machine}"
)


def main() -> int:
    """Run the jail lifecycle."""
    logger = libioc.Logger.Logger()
    zfs = libzfs.ZFS(history=True, history_prefix="<libioc-smoke>")

    pool = list(filter(
        lambda pool: (pool.name == POOL_NAME),
        zfs.pools
    ))[0]
    root_dataset_name = f"{pool.name}/libioc-test"
    try:
        pool.create(root_dataset_name, {})
    except libzfs.ZFSException:
        pass
    root_dataset = zfs.get_dataset(root_dataset_name)
    if not root_dataset.mountpoint:
        root_dataset.mount()

    datasets = libioc.Datasets.Datasets(
        sources=dict(test=root_dataset),
        logger=logger,
        zfs=zfs
    )

    class SmokeDistribution(libioc.Distribution.Distribution):

        @property
        def mirror_url(self) -> str:
            """Return the archive mirror URL."""
            return MIRROR

    class SmokeHost(libioc.Host.Host):

        _class_distribution = SmokeDistribution

    host = SmokeHost(datasets=datasets, logger=logger, zfs=zfs)

    release = libioc.Release.Release(
        name=host.release_version,
        host=host,
        logger=logger,
        zfs=zfs
    )
    if not release.fetched:
        print(f"Fetching release {release.name}")
        release.fetch(fetch_updates=False, update=False)

    jail = libioc.Jail.Jail(
        dict(name="smoke-test"),
        new=True,
        host=host,
        logger=logger,
        zfs=zfs
    )
    try:
        print("Creating jail from release")
        jail.create(release)
        print("Starting jail")
        jail.start()
        print("Executing a command inside the jail")
        stdout, _, code = jail.exec(["/bin/sh", "-c", "echo smoke-ok"])
        print(stdout)
        if (code != 0) or ("smoke-ok" not in str(stdout)):
            raise RuntimeError("process inside the jail failed")
        print("Stopping jail")
        jail.stop()
    finally:
        if jail.exists:
            try:
                jail.stop(force=True)
            except Exception:
                pass
            jail.destroy()
            print("Jail destroyed")

    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
