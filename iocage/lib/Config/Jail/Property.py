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


def init_property(property_name: str, **kwargs) -> typing.Union[
    iocage.lib.Config.Jail.Properties.Addresses.AddressesProp,
    iocage.lib.Config.Jail.Properties.Interfaces.InterfaceProp,
    iocage.lib.Config.Jail.Properties.Resolver.ResolverProp
]:

    target_class = CLASSES[property_name]
    out = target_class(
        property_name=property_name,
        **kwargs
    )
    return out
