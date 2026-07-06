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
"""
Import-time replacement for py-libzfs on hosts without FreeBSD.

The shim lets the test suite collect and run the platform-independent
tests on Linux.
Every class can be imported and subclassed, but instantiating one raises
RuntimeError, so any test that would touch ZFS fails loudly instead of
silently doing nothing.
"""
import enum

__libioc_test_shim__ = True


class ZFSException(Exception):
    """Replacement of the libzfs exception type."""

    def __init__(self, code: int=0, message: str="") -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class Error(enum.IntEnum):
    """Replacement of the libzfs error codes."""

    SUCCESS = 0
    NOENT = 2009


class DatasetType(enum.IntEnum):
    """Replacement of the libzfs dataset types."""

    FILESYSTEM = 1
    SNAPSHOT = 2
    VOLUME = 3
    POOL = 8


class SendFlag(enum.IntEnum):
    """Replacement of the libzfs send flags."""

    VERBOSE = 0
    REPLICATE = 1
    DEDUP = 2
    PROPS = 3
    NOOP = 4
    RECURSIVE = 5
    DRYRUN = 6
    PARSABLE = 7
    PROGRESS = 8
    LARGEBLOCK = 9
    EMBED_DATA = 10
    COMPRESS = 11
    RAW = 12
    BACKUP = 13
    HOLDS = 14
    SAVED = 15


class _ShimBase:

    def __init__(self, *args, **kwargs) -> None:
        raise RuntimeError(
            "libzfs shim: this operation requires py-libzfs on FreeBSD"
        )


class ZFS(_ShimBase):
    """Replacement of libzfs.ZFS."""


class ZFSObject(_ShimBase):
    """Replacement of libzfs.ZFSObject."""


class ZFSPool(_ShimBase):
    """Replacement of libzfs.ZFSPool."""


class ZFSDataset(_ShimBase):
    """Replacement of libzfs.ZFSDataset."""


class ZFSSnapshot(_ShimBase):
    """Replacement of libzfs.ZFSSnapshot."""


class ZFSUserProperty(_ShimBase):
    """Replacement of libzfs.ZFSUserProperty."""


class ZFSProperty(_ShimBase):
    """Replacement of libzfs.ZFSProperty."""
