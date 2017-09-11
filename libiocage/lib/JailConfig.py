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
import typing
import re
import uuid

import libiocage.lib.ConfigJSON
import libiocage.lib.JailConfigAddresses
import libiocage.lib.JailConfigDefaults
import libiocage.lib.JailConfigInterfaces
import libiocage.lib.JailConfigResolver
import libiocage.lib.errors
import libiocage.lib.helpers

# MyPy
import libiocage.lib.Jail


class JailConfig(dict, object):
    """
    Represents an iocage jail's configuration

    A jail configuration can be loaded from various formats that were used
    by different versions of iocage. Technically it is possible to store
    set properties in deprecated formats, but this might break when using
    newer features than the legacy version of iocage supports. It is
    recommended to use the reading capabilities to migrate to the JSON
    config format.

    Supported Configuration Formats:

        JSON: (current)
            Since the Python 3 implementation iocage stored jail configs in
            a file called `config.json` within the jail's root dataset

        ZFS:
            iocage-legacy written in Bash used to save jail configurations
            as ZFS properties on the jail's root dataset. Due to poor
            performance and easier readability this format later was replaced
            with a file based config storage. Even though it is a deprecated
            format, libiocage is compatible to read a jail config from ZFS.

        UCL:
            Yet another deprecated configuration format, that libiocage also
            supports reading from. A legacy version of iocage used this format.

    Special Properties:

        Special properties are

    """

    special_properties: dict = {}
    data: dict = None
    legacy: bool = None
    jail: 'libiocage.lib.Jail.JailGenerator' = None

    def __init__(
        self,
        data: dict={},
        jail: 'libiocage.lib.Jail.JailGenerator'=None,
        logger: 'libiocage.lib.Logger.Logger'=None,
        host: 'libiocage.lib.Host.HostGenerator'=None,
        new: bool=False
    ) -> None:

        dict.__init__(self)

        if self.data is None:
            self.data = {
                "id": None
            }

        self.logger = libiocage.lib.helpers.init_logger(self, logger)
        self.host = libiocage.lib.helpers.init_host(self, host)

        self.jail = jail

        # the name is used in many other variables and needs to be set first
        for key in ["id", "name", "uuid"]:
            if key in data.keys():
                self["id"] = data[key]
                break

        self.clone(data)

    def clone(
        self,
        data: typing.Dict[str, typing.Any],
        skip_on_error: bool=False
    ) -> None:
        """
        Apply data from a data dictionary to the JailConfig

        Existing jail configuration is not emptied using.

        Args:

            data (dict):
                Dictionary containing the configuration to apply

            skip_on_error (bool):
                Passed to __setitem__

        """
        if data is None:
            return

        current_id = self["id"]
        for key, value in data.items():

            if (key in ["id", "name", "uuid"]) and (current_id is not None):
                value = current_id

            self.__setitem__(key, value, skip_on_error=skip_on_error)

    def read(self) -> None:
        self.clone(self.jail.read_config())

    def update_special_property(self, name: str) -> None:

        try:
            self.data[name] = str(self.special_properties[name])
        except KeyError:
            # pass when there is no handler for the notifying propery
            pass

    def attach_special_property(self, name, special_property):
        self.special_properties[name] = special_property

    def save(self) -> None:
        self.jail.write_config(self.data)

    def _set_legacy(self, value) -> None:
        try:
            self.legacy = libiocage.lib.helpers.parse_bool(value)
        except:
            self.legacy = False

    def _get_id(self) -> str:
        return self.data["id"]

    def _set_id(self, name: str, **kwargs):

        try:
            # We do not want to set the same name twice.
            # This can occur when the Jail is initialized
            # with it's name and the same name is read from
            # the configuration
            if self["id"] == name:
                return
        except:
            pass

        if name is None:
            self.data["id"] = None
            return

        allowed_characters_pattern = "([^A-z0-9\\._\\-]|\\^)"
        invalid_characters = re.findall(allowed_characters_pattern, name)
        if len(invalid_characters) > 0:
            msg = (
                f"Invalid character in name: "
                " ".join(invalid_characters)
            )
            self.logger.error(msg)

        is_valid_name = libiocage.lib.helpers.validate_name(name)
        if is_valid_name is True:
            self.data["id"] = name
        else:
            try:
                self.data["id"] = str(uuid.UUID(name))  # legacy support
            except:
                raise libiocage.lib.errors.InvalidJailName(logger=self.logger)

        self.logger.spam(f"Set jail name to {name}")

    def _get_name(self):
        return self._get_id()

    def _get_uuid(self):
        return self._get_id()

    def _get_type(self):

        if self["basejail"]:
            return "basejail"
        elif self["clonejail"]:
            return "clonejail"
        else:
            return "jail"

    def _set_type(self, value, **kwargs):

        if value == "basejail":
            self["basejail"] = True
            self["clonejail"] = False
            self.data["type"] = "jail"

        elif value == "clonejail":
            self["basejail"] = False
            self["clonejail"] = True
            self.data["type"] = "jail"

        else:
            self.data["type"] = value

    def _get_priority(self) -> int:
        return int(self.data["priority"])

    def _set_priority(self, value: typing.Union[int, str]):
        self.data["priority"] = str(value)

    # legacy support
    def _get_tag(self) -> str:

        if self._has_legacy_tag is True:
            return self.data["tag"]

        try:
            return self["tags"][0]
        except KeyError:
            return None

    def _set_tag(self, value: str, **kwargs):

        if (self._has_legacy_tag is True) or ("tags" not in self.data.keys()):
            # store as deprecated `tag` for downwards compatibility
            # setting `tags` overrides usage of the deprecated `tag` property
            self.data["tag"] = value
            return

        tags = self["tags"]
        if value in tags:
            # remove the tag if it was existing
            del tags[tags.index(value)]

        tags.insert(0, value)
        self.data["tags"] = libiocage.lib.helpers.to_string(tags)

    @property
    def _has_legacy_tag(self):
        return "tag" in self.data.keys()

    def _get_tags(self) -> typing.List[str]:
        return libiocage.lib.helpers.parse_list(self.data["tags"])

    def _set_tags(
        self,
        value: typing.Union[str, typing.List[str]],
        **kwargs
    ) -> None:

        data = libiocage.lib.helpers.to_string(value)
        self.data["tags"] = data

        if self._has_legacy_tag is True:
            del self.data["tag"]

    def _get_basejail(self) -> bool:
        return libiocage.lib.helpers.parse_bool(self.data["basejail"])

    def _default_basejail(self):
        return False

    def _set_basejail(self, value, **kwargs):
        self.data["basejail"] = self.stringify(value)

    def _get_clonejail(self) -> bool:
        return libiocage.lib.helpers.parse_bool(self.data["clonejail"])

    def _default_clonejail(self):
        return True

    def _set_clonejail(self, value, **kwargs):
        self.data["clonejail"] = self.stringify(value)

    def _get_ip4_addr(self):
        try:
            return self.special_properties["ip4_addr"]
        except:
            return None

    def _set_ip4_addr(self, value, **kwargs):
        ip4_addr = libiocage.lib.JailConfigAddresses.JailConfigAddresses(
            value,
            jail_config=self,
            property_name="ip4_addr",
            logger=self.logger
        )
        self.special_properties["ip4_addr"] = ip4_addr
        self.update_special_property("ip4_addr")

    def _get_ip6_addr(self):
        try:
            return self.special_properties["ip6_addr"]
        except:
            return None

    def _set_ip6_addr(self, value, **kwargs):
        ip6_addr = libiocage.lib.JailConfigAddresses.JailConfigAddresses(
            value,
            jail_config=self,
            property_name="ip6_addr",
            logger=self.logger,
            skip_on_error=self._skip_on_error(**kwargs)
        )
        self.special_properties["ip6_addr"] = ip6_addr
        self.update_special_property("ip6_addr")

        rc_conf = self.jail.rc_conf
        rc_conf["rtsold_enable"] = "accept_rtadv" in str(value)

    def _get_interfaces(self):
        return self.special_properties["interfaces"]

    def _set_interfaces(self, value, **kwargs):
        interfaces = libiocage.lib.JailConfigInterfaces.JailConfigInterfaces(
            value,
            jail_config=self
        )
        self.special_properties["interfaces"] = interfaces
        self.update_special_property("interfaces")

    def _get_defaultrouter(self):
        value = self.data['defaultrouter']
        return value if (value != "none" and value is not None) else None

    def _set_defaultrouter(self, value, **kwargs):
        if value is None:
            value = 'none'
        self.data['defaultrouter'] = value

    def _get_defaultrouter6(self):
        value = self.data['defaultrouter6']
        return value if (value != "none" and value is not None) else None

    def _set_defaultrouter6(self, value, **kwargs):
        if value is None:
            value = 'none'
        self.data['defaultrouter6'] = value

    def _get_vnet(self):
        return libiocage.lib.helpers.parse_user_input(self.data["vnet"])

    def _set_vnet(self, value, **kwargs):
        self.data["vnet"] = libiocage.lib.helpers.to_string(
            value,
            true="on",
            false="off"
        )

    def _get_jail_zfs_dataset(self):
        try:
            return self.data["jail_zfs_dataset"].split()
        except KeyError:
            return []

    def _set_jail_zfs_dataset(self, value, **kwargs):
        value = [value] if isinstance(value, str) else value
        self.data["jail_zfs_dataset"] = " ".join(value)

    def _get_jail_zfs(self):
        try:
            return libiocage.lib.helpers.parse_user_input(
                self.data["jail_zfs"]
            )
        except:
            return self._default_jail_zfs()

    def _set_jail_zfs(self, value, **kwargs):
        parsed_value = libiocage.lib.helpers.parse_user_input(value)
        if parsed_value is None:
            del self.data["jail_zfs"]
            return
        self.data["jail_zfs"] = libiocage.lib.helpers.to_string(
            parsed_value,
            true="on",
            false="off"
        )

    def _default_jail_zfs(self):
        # if self.data["jail_zfs"] does not explicitly exist,
        # _get_jail_zfs would raise
        try:
            return len(self["jail_zfs_dataset"]) > 0
        except:
            return False

    def _get_resolver(self):
        return self._create_or_get_special_property_resolver()

    def _set_resolver(self, value, **kwargs):

        resolver = self._create_or_get_special_property_resolver()
        resolver.update(value, notify=True)

    def _get_cloned_release(self):
        try:
            return self.data["cloned_release"]
        except:
            return self["release"]

    def _get_basejail_type(self):

        # first see if basejail_type was explicitly set
        try:
            return self.data["basejail_type"]
        except:
            pass

        # if it was not, the default for is 'nullfs' if the jail is a basejail
        try:
            if self["basejail"]:
                return "nullfs"
        except:
            pass

        # otherwise the jail does not have a basejail_type
        return None

    def _get_login_flags(self):
        try:
            return JailConfigList(self.data["login_flags"].split())
        except KeyError:
            return JailConfigList(["-f", "root"])

    def _set_login_flags(self, value, **kwargs):
        if value is None:
            try:
                del self.data["login_flags"]
            except:
                pass
        else:
            if isinstance(value, list):
                self.data["login_flags"] = " ".join(value)
            elif isinstance(value, str):
                self.data["login_flags"] = value
            else:
                raise libiocage.lib.errors.InvalidJailConfigValue(
                    property_name="login_flags",
                    logger=self.logger
                )

    def _get_host_hostname(self):
        try:
            return self.data["host_hostname"]
        except KeyError:
            return self.jail.humanreadable_name

    def _get_host_hostuuid(self):
        try:
            return self.data["host_hostuuid"]
        except KeyError:
            return self["id"]

    def _create_or_get_special_property_resolver(
        self
    ) -> libiocage.lib.JailConfigResolver.JailConfigResolver:

        try:
            return self.special_properties["resolver"]
        except:
            pass

        resolver = libiocage.lib.JailConfigResolver.JailConfigResolver(
            jail_config=self,
            host=self.host,
            logger=self.logger
        )

        resolver.update(notify=False)
        self.special_properties["resolver"] = resolver

        return self.special_properties["resolver"]

    def get_string(self, key):
        return self.stringify(self.__getitem__(key))

    def _skip_on_error(self, **kwargs):
        """
        A helper to resolve skip_on_error attribute
        """
        try:
            return kwargs["skip_on_error"] is True
        except AttributeError:
            return False

    def __getitem_user(self, key):

        # passthrough existing properties
        try:
            return self.stringify(self.__getattribute__(key))
        except:
            pass

        # data with mappings
        get_method = None
        try:
            get_method = self.__getattribute__(f"_get_{key}")
            return get_method()
        except AttributeError:
            if get_method is not None:
                raise
            pass

        # plain data attribute
        try:
            return self.data[key]
        except:
            pass

        raise KeyError(f"User defined property not found: {key}")

    def __getitem__(self, key):

        try:
            return self.__getitem_user(key)
        except:
            pass

        # fall back to default
        return self.host.defaults[key]

    def __delitem__(self, key):
        del self.data[key]

    def __setitem__(self, key, value, **kwargs):

        parsed_value = libiocage.lib.helpers.parse_user_input(value)

        setter_method = None
        try:
            setter_method = self.__getattribute__(f"_set_{key}")
        except:
            self.data[key] = parsed_value
            pass

        if setter_method is not None:
            return setter_method(parsed_value, **kwargs)

    def set(self, key: str, value, **kwargs) -> bool:
        """
        Set a JailConfig property

        Args:

            key:
                The jail config property name

            value:
                Value to set the property to

            **kwargs:
                Arguments from **kwargs are passed to setter functions

        Returns:

            bool: True if the JailConfig was changed
        """

        try:
            hash_before = str(self.__getitem_user(key)).__hash__()
        except Exception:
            hash_before = None
            pass

        self.__setitem__(key, value, **kwargs)

        try:
            hash_after = str(self.__getitem_user(key)).__hash__()
        except Exception:
            hash_after = None
            pass

        return (hash_before != hash_after)

    def __str__(self) -> str:
        return libiocage.lib.ConfigJSON.to_json(self)

    def __dir__(self) -> list:

        properties = set()
        props = dict.__dir__(self)  # type: ignore
        for prop in props:
            if prop.startswith("_default_"):
                properties.add(prop[9:])
            elif not prop.startswith("_"):
                properties.add(prop)

        for key in self.data.keys():
            properties.add(key)

        return list(properties)

    @property
    def all_properties(self) -> list:

        properties = set()
        props = dict.__dir__(self)  # type: ignore
        for prop in props:
            if prop.startswith("_default_"):
                properties.add(prop[9:])

        for key in self.data.keys():
            properties.add(key)

        return sorted(list(properties | set(self.host.defaults.keys())))

    def stringify(self, value):
        parsed_input = libiocage.lib.helpers.parse_user_input(value)
        return libiocage.lib.helpers.to_string(parsed_input)


class JailConfigList(list):

    def __str__(self) -> str:
        return " ".join(self)
