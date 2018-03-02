# Copyright (c) 2014-2018, iocage
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
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THEz
# POSSIBILITY OF SUCH DAMAGE.
"""Shared code of jail config special properties."""
import typing
import iocage.lib.Config.Jail.Properties.Addresses
import iocage.lib.Config.Jail.Properties.Interfaces
import iocage.lib.Config.Jail.Properties.Resolver

_Config = iocage.lib.Config

CLASSES: dict = dict(
    ip4_addr=iocage.lib.Config.Jail.Properties.Addresses.AddressesProp,
    ip6_addr=iocage.lib.Config.Jail.Properties.Addresses.AddressesProp,
    interfaces=iocage.lib.Config.Jail.Properties.Interfaces.InterfaceProp,
    resolver=iocage.lib.Config.Jail.Properties.Resolver.ResolverProp
)


def init_property(property_name: str, **kwargs) -> typing.Union[  # noqa: T484
    iocage.lib.Config.Jail.Properties.Addresses.AddressesProp,
    iocage.lib.Config.Jail.Properties.Interfaces.InterfaceProp,
    iocage.lib.Config.Jail.Properties.Resolver.ResolverProp
]:
    """
    Instantiate a special jail config property.

    Args:

        property_name:
            The name of the special property that should be instantiated:
                - ip4_addr
                - ip6_addr
                - interfaces
                - resolver

        **kwargs:
            Arguments passed to the special property class
    """
    target_class = CLASSES[property_name]
    out = target_class(
        property_name=property_name,
        **kwargs
    )
    return out
