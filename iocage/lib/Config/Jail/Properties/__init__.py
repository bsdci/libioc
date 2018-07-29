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
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""Dictionary of jail configuration properties."""
import typing
import iocage.lib.Config.Jail.Properties.Addresses
import iocage.lib.Config.Jail.Properties.Interfaces
import iocage.lib.Config.Jail.Properties.Resolver
import iocage.lib.Config.Jail.Properties.ResourceLimit
import iocage.lib.Config.Jail.Properties.Defaultrouter

Property = typing.Union[
    'iocage.lib.Config.Jail.Properties.Addresses.AddressesProp',
    'iocage.lib.Config.Jail.Properties.Interfaces.InterfaceProp',
    'iocage.lib.Config.Jail.Properties.Resolver.ResolverProp'
]

properties: typing.List[str] = [
    "ip4_addr",
    "ip6_addr",
    "interfaces",
    "defaultrouter",
    "defaultrouter6",
    "resolver"
] + ResourceLimit.properties

def _get_class(property_name: str) -> Property:

    ResourceLimit = iocage.lib.Config.Jail.Properties.ResourceLimit
    DefaultrouterModule = iocage.lib.Config.Jail.Properties.Defaultrouter

    if (property_name == "ip4_addr"):
        return iocage.lib.Config.Jail.Properties.Addresses.IPv4AddressesProp
    elif (property_name == "ip6_addr"):
        return iocage.lib.Config.Jail.Properties.Addresses.IPv6AddressesProp
    elif property_name == "interfaces":
        return iocage.lib.Config.Jail.Properties.Interfaces.InterfaceProp
    elif property_name == "resolver":
        return iocage.lib.Config.Jail.Properties.Resolver.ResolverProp
    elif property_name == "defaultrouter":
        return DefaultrouterModule.DefaultrouterProp
    elif property_name == "defaultrouter6":
        return DefaultrouterModule.Defaultrouter6Prop
    elif property_name in ResourceLimit.properties:
        return ResourceLimit.ResourceLimitProp

    raise ValueError("A special property class with this name was not found")


def init_property(property_name: str, **kwargs) -> Property:  # noqa: T484
    """
    Instantiate a special jail config property.

    Args:

        property_name:
            The name of the special property that should be instantiated:
                - ip4_addr
                - ip6_addr
                - interfaces
                - resolver
                - defaultrouter
                - defaultrouter6

        **kwargs:
            Arguments passed to the special property class
    """
    target_class = _get_class(property_name)
    out = target_class(
        property_name=property_name,
        **kwargs
    )
    return out


class JailConfigProperties(dict):
    """Dictionary of jail configuration properties."""

    def __init__(
        self,
        config: 'iocage.lib.Config.Jail.BaseConfig.BaseConfig',
        logger: 'iocage.lib.Logger.Logger'
    ) -> None:

        self.logger = logger
        self.config = config

    def is_special_property(self, property_name: str) -> bool:
        """Signal if the property is a special property."""
        try:
            _get_class(property_name)
            return True
        except ValueError:
            return False

        return (property_name in CLASSES.keys()) is True

    def get_or_create(
        self,
        property_name: str
    ) -> typing.Any:
        """Get a property and initialize it if it did not exist."""
        if property_name not in self.keys():
            self[property_name] = init_property(
                property_name=property_name,
                config=self.config,
                logger=self.logger
            )

        return self[property_name]
