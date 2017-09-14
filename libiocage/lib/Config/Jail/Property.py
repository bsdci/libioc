import typing
import libiocage.lib.Config.Jail.Properties.Addresses
import libiocage.lib.Config.Jail.Properties.Interfaces
import libiocage.lib.Config.Jail.Properties.Resolver

_Config = libiocage.lib.Config

CLASSES: dict = dict(
    ip4_addr=libiocage.lib.Config.Jail.Properties.Addresses.AddressesProp,
    ip6_addr=libiocage.lib.Config.Jail.Properties.Addresses.AddressesProp,
    interfaces=libiocage.lib.Config.Jail.Properties.Interfaces.InterfaceProp,
    resolver=libiocage.lib.Config.Jail.Properties.Resolver.ResolverProp
)


def init_property(property_name: str, **kwargs) -> typing.Union[
    libiocage.lib.Config.Jail.Properties.Addresses.AddressesProp,
    libiocage.lib.Config.Jail.Properties.Interfaces.InterfaceProp,
    libiocage.lib.Config.Jail.Properties.Resolver.ResolverProp
]:

    target_class = CLASSES[property_name]
    out = target_class(
        property_name=property_name,
        **kwargs
    )
    return out
