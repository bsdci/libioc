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
Import-time replacement for the jail package on hosts without FreeBSD.

The real py-jail queries a sysctl while importing, which fails on Linux.
The shim satisfies module-level imports during test collection; every
call into it raises RuntimeError.
"""
import typing

__libioc_test_shim__ = True

JAIL_MAX_AF_IPS = 0


class _ShimDll:

    def __getattr__(self, name: str) -> typing.Any:
        raise RuntimeError(
            "jail shim: this operation requires py-jail on FreeBSD"
        )


dll = _ShimDll()

RawIovecValue = typing.Optional[typing.Union[bytes, int, typing.List]]
IovevValueInput = typing.Union[RawIovecValue, str]


class IovecKey:
    """Replacement of jail.IovecKey."""

    def __init__(self, value: typing.Union[str, bytes]) -> None:
        raise RuntimeError(
            "jail shim: this operation requires py-jail on FreeBSD"
        )


class IovecValue:
    """Replacement of jail.IovecValue."""

    def __init__(self, value: typing.Any) -> None:
        raise RuntimeError(
            "jail shim: this operation requires py-jail on FreeBSD"
        )


class Jiov(dict):
    """Replacement of jail.Jiov."""

    def __init__(self, params: typing.Any) -> None:
        raise RuntimeError(
            "jail shim: this operation requires py-jail on FreeBSD"
        )


def get_jid_by_name(name: typing.Union[str, bytes]) -> int:
    """Raise because jails cannot exist on this platform."""
    raise RuntimeError(
        "jail shim: this operation requires py-jail on FreeBSD"
    )


def is_jid_dying(jid: int) -> bool:
    """Raise because jails cannot exist on this platform."""
    raise RuntimeError(
        "jail shim: this operation requires py-jail on FreeBSD"
    )
