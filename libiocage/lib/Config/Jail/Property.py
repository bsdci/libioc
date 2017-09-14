import typing
import libiocage.lib.Config.Jail.Properties.Addresses
import libiocage.lib.Config.Jail.Properties.Interfaces
import libiocage.lib.Config.Jail.Properties.Resolver

CLASSES: dict = {
    "ip4_addr": libiocage.lib.Config.Jail.Properties.Addresses.JailConfigPropertyAddresses,
    "ip6_addr": libiocage.lib.Config.Jail.Properties.Addresses.JailConfigPropertyAddresses,
    "interfaces": libiocage.lib.Config.Jail.Properties.Interfaces.JailConfigPropertyInterfaces,
    "resolver": libiocage.lib.Config.Jail.Properties.Resolver.JailConfigPropertyResolver
}

def init_property(property_name: str,**kwargs) -> typing.Union[
    libiocage.lib.Config.Jail.Properties.Addresses.JailConfigPropertyAddresses,
    libiocage.lib.Config.Jail.Properties.Interfaces.JailConfigPropertyInterfaces,
    libiocage.lib.Config.Jail.Properties.Resolver.JailConfigPropertyResolver
]:

    target_class = CLASSES[property_name]
    out = target_class(
        property_name=property_name,
        **kwargs
    )
    return out
