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
"""The common base of jail configurations."""
import typing
import re

import iocage.lib.Config.Jail.Properties
import iocage.lib.errors
import iocage.lib.helpers

# mypy
import iocage.lib.Logger


class BaseConfig(dict):
    """
    Model a plain iocage jail configuration.

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

    data: typing.Dict[str, typing.Any]
    special_properties: 'iocage.lib.Config.Jail.Properties.Properties'

    def __init__(
        self,
        logger: typing.Optional[iocage.lib.Logger.Logger]=None
    ) -> None:

        self.data = {}
        dict.__init__(self)

        self.logger = iocage.lib.helpers.init_logger(self, logger)

        Properties = iocage.lib.Config.Jail.Properties.JailConfigProperties
        self.special_properties = Properties(
            config=self,
            logger=self.logger
        )

    def clone(
        self,
        data: typing.Dict[str, typing.Any],
        skip_on_error: bool=False
    ) -> None:
        """
        Apply data from a data dictionary to the JailConfig.

        Existing jail configuration is not emptied using.

        Args:

            data (dict):
                Dictionary containing the configuration to apply

            skip_on_error (bool):
                Passed to __setitem__

        """
        if len(data.keys()) == 0:
            return

        current_id = self["id"]
        for key, value in data.items():

            if (key in ["id", "name", "uuid"]) and (current_id is not None):
                value = current_id

            self.__setitem__(  # noqa: T484
                key,
                value,
                skip_on_error=skip_on_error
            )

    def read(self, data: dict, skip_on_error: bool=False) -> None:
        """
        Read the input data.

        Various versions of iocage had a different understanding of a jail
        identifier. This method removes all identifiers from the input data
        when a normalized id is already set.
        """
        if self["id"] is not None:
            data_keys = data.keys()
            if "name" in data_keys:
                del data["name"]
            if "id" in data_keys:
                del data["id"]
            if "uuid" in data_keys:
                del data["uuid"]

        self.clone(data, skip_on_error=skip_on_error)

    def _set_legacy(  # noqa: T484
        self,
        value: typing.Union[bool, str],
        **kwargs
    ) -> None:
        try:
            self.legacy = iocage.lib.helpers.parse_bool(value)
        except TypeError:
            self.legacy = False

    def _get_id(self) -> str:
        return str(self.data["id"])

    def _set_id(self, name: str, **kwargs) -> None:  # noqa: T484

        if ("id" in self.data.keys()) and (self.data["id"] == name):
            # We do not want to set the same name twice.
            # This can occur when the Jail is initialized
            # with it's name and the same name is read from
            # the configuration
            return

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
            raise iocage.lib.errors.InvalidJailName(logger=self.logger)

        is_valid_name = iocage.lib.helpers.validate_name(name)
        if is_valid_name is True:
            self.data["id"] = name
        else:
            if iocage.lib.helpers.is_uuid(name) is True:
                self.data["id"] = name
            else:
                raise iocage.lib.errors.InvalidJailName(logger=self.logger)

    def _get_name(self) -> str:
        return self._get_id()

    def _get_uuid(self) -> str:
        return self._get_id()

    def _get_type(self) -> str:

        if self["basejail"]:
            return "basejail"
        elif self["clonejail"]:
            return "clonejail"
        else:
            return "jail"

    def _set_type(  # noqa: T484
        self,
        value: typing.Optional[str],
        **kwargs
    ) -> None:

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

    def _set_priority(  # noqa: T484
        self,
        value: typing.Union[int, str],
        **kwargs
    ) -> None:
        self.data["priority"] = str(value)

    # legacy support
    def _get_tag(self) -> typing.Optional[str]:

        if self._has_legacy_tag is True:
            return str(self.data["tag"])

        try:
            return str(self["tags"][0])
        except (KeyError, IndexError):
            return None

    def _set_tag(self, value: str, **kwargs) -> None:  # noqa: T484

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
        self.data["tags"] = iocage.lib.helpers.to_string(tags)

    @property
    def _has_legacy_tag(self) -> bool:
        return "tag" in self.data.keys()

    def _get_vnet_interfaces(self) -> typing.List[str]:
        return list(
            iocage.lib.helpers.parse_list(self.data["vnet_interfaces"])
        )

    def _set_vnet_interfaces(  # noqa: T484
        self,
        value: typing.Optional[typing.Union[str, typing.List[str]]],
        **kwargs
    ) -> None:
        try:
            iocage.lib.helpers.parse_none(value)
            self.data["vnet_interfaces"] = []
            return
        except TypeError:
            pass

        if isinstance(value, str) is True:
            self.data["vnet_interfaces"] = value
        else:
            self.data["vnet_interfaces"] = iocage.lib.helpers.to_string(value)

    def _get_exec_clean(self) -> bool:
        return (self.data["exec_clean"] == 1) is True

    def _set_exec_clean(  # noqa: T484
        self,
        value: typing.Union[str, int, bool],
        **kwargs
    ) -> None:
        if isinstance(value, str):
            value = int(value)
        self.data["exec_clean"] = 1 if ((value is True) or (value == 1)) else 0

    def _get_tags(self) -> typing.List[str]:

        data_keys = self.data.keys()

        if "tags" in data_keys:
            tags = set(list(iocage.lib.helpers.parse_list(self.data["tags"])))
        else:
            tags = set()

        if (self._has_legacy_tag is True):
            tags.add(self.data["tag"])

        return list(tags)

    def _set_tags(  # noqa: T484
        self,
        value: typing.Union[
            str,
            bool,
            int,
            typing.List[typing.Union[str, bool, int]]
        ],
        **kwargs
    ) -> None:

        data = iocage.lib.helpers.to_string(value)
        self.data["tags"] = data

        if self._has_legacy_tag is True:
            del self.data["tag"]

    def _get_basejail(self) -> bool:
        return iocage.lib.helpers.parse_bool(self.data["basejail"]) is True

    def _set_basejail(self, value: typing.Any, **kwargs) -> None:  # noqa: T484
        self.data["basejail"] = self.stringify(value)

    def _get_clonejail(self) -> bool:
        return iocage.lib.helpers.parse_bool(self.data["clonejail"]) is True

    def _set_clonejail(  # noqa: T484
        self,
        value: typing.Optional[typing.Union[str, bool]],
        **kwargs
    ) -> None:
        self.data["clonejail"] = self.stringify(value)

    def _get_defaultrouter(self) -> typing.Optional[str]:
        value = self.data['defaultrouter']
        return str(value) if (value != "none" and value is not None) else None

    def _set_defaultrouter(  # noqa: T484
        self,
        value: typing.Optional[str],
        **kwargs
    ) -> None:
        if value is None:
            value = 'none'
        self.data['defaultrouter'] = value

    def _get_defaultrouter6(self) -> typing.Optional[str]:
        value = self.data['defaultrouter6']
        return str(value) if (value != "none" and value is not None) else None

    def _set_defaultrouter6(  # noqa: T484
        self,
        value: typing.Optional[str],
        **kwargs
    ) -> None:
        if value is None:
            value = 'none'
        self.data['defaultrouter6'] = value

    def _get_vnet(self) -> bool:
        return iocage.lib.helpers.parse_user_input(self.data["vnet"]) is True

    def _set_vnet(  # noqa: T484
        self,
        value: typing.Union[str, bool],
        **kwargs
    ) -> None:
        self.data["vnet"] = iocage.lib.helpers.to_string(
            value,
            true="on",
            false="off"
        )

    def _get_jail_zfs_dataset(self) -> typing.List[str]:
        try:
            jail_zfs_dataset = str(self.data["jail_zfs_dataset"])
            return jail_zfs_dataset.split()
        except KeyError:
            return []

    def _set_jail_zfs_dataset(  # noqa: T484
        self,
        value: typing.Optional[typing.Union[typing.List[str], str]],
        **kwargs
    ) -> None:
        value = [value] if isinstance(value, str) else value
        if value is None:
            self.data["jail_zfs_dataset"] = ""
        else:
            self.data["jail_zfs_dataset"] = " ".join(value)

    def _get_jail_zfs(self) -> bool:
        return iocage.lib.helpers.parse_bool(
            self.data["jail_zfs"]
        ) is True

    def _set_jail_zfs(  # noqa: T484
        self,
        value: typing.Optional[typing.Union[bool, str]],
        **kwargs
    ) -> None:
        parsed_value = iocage.lib.helpers.parse_user_input(value)
        if parsed_value is None:
            del self.data["jail_zfs"]
            return
        self.data["jail_zfs"] = iocage.lib.helpers.to_string(
            parsed_value,
            true="on",
            false="off"
        )

    def _get_cloned_release(self) -> typing.Optional[str]:
        try:
            return str(self.data["cloned_release"])
        except KeyError:
            release = self["release"]
            if isinstance(release, str):
                return str(self["release"])
            return None

    def _get_basejail_type(self) -> typing.Optional[str]:

        # first see if basejail_type was explicitly set
        if "basejail_type" in self.data.keys():
            return str(self.data["basejail_type"])

        # if it was not, the default for is 'nullfs' if the jail is a basejail
        try:
            if self["basejail"]:
                return "nullfs"
        except KeyError:
            pass

        # otherwise the jail does not have a basejail_type
        return None

    def _get_login_flags(self) -> 'JailConfigList':
        try:
            return JailConfigList(self.data["login_flags"].split())
        except KeyError:
            return JailConfigList(["-f", "root"])

    def _set_login_flags(  # noqa: T484
        self,
        value: typing.Optional[typing.Union[str, typing.List[str]]],
        **kwargs
    ) -> None:
        if value is None:
            try:
                del self.data["login_flags"]
            except KeyError:
                pass
        else:
            if isinstance(value, list):
                self.data["login_flags"] = " ".join(value)
            elif isinstance(value, str):
                self.data["login_flags"] = value
            else:
                raise iocage.lib.errors.InvalidJailConfigValue(
                    property_name="login_flags",
                    logger=self.logger
                )

    def _get_host_hostuuid(self) -> str:
        try:
            return str(self.data["host_hostuuid"])
        except KeyError:
            return str(self["id"])

    def get_string(self, key: str) -> str:
        """Get the stringified value of a configuration property."""
        return self.stringify(self.__getitem__(key))

    def _skip_on_error(self, **kwargs) -> bool:  # noqa: T484
        """Resolve the skip_on_error attribute with this helper function."""
        try:
            return kwargs["skip_on_error"] is True
        except AttributeError:
            return False

    def _getitem_user(self, key: str) -> typing.Any:
        try:
            # passthrough existing properties
            return self.__getattribute__(key)
        except AttributeError:
            pass

        # special property
        is_special_property = self.special_properties.is_special_property(key)
        is_existing = key in self.data.keys()
        if (is_special_property and is_existing) is True:
            return self.special_properties.get_or_create(key)

        # data with mappings
        method_name = f"_get_{key}"
        if method_name in dict.__dir__(self):
            get_method = self.__getattribute__(method_name)
            return get_method()

        # plain data attribute
        if key in self.data.keys():
            return self.data[key]

        raise KeyError(f"User defined property not found: {key}")

    def get(
        self,
        key: str,
        *args: typing.Any
    ) -> typing.Any:
        """Return the config value or its given default."""
        if len(args) > 1:
            raise TypeError(
                f"get() takes 1 positional argument but {len(args)} were given"
            )
        try:
            return self.__getitem__(key)
        except KeyError:
            if len(args) == 0:
                raise
            return args[0]

    def __getitem__(self, key: str) -> typing.Any:
        """
        Get the user configured value of a jail configuration property.

        The lookup order of such values is:
            - native attributes
            - special properties
            - _get_{key} methods
            - plain data keys (without special processing)

        A KeyError is raised when no criteria applies.
        """
        try:
            return self._getitem_user(key)
        except KeyError:
            pass

        raise KeyError(f"Item not found: {key}")

    def __delitem__(self, key: str) -> None:
        """Delete a setting from the configuration."""
        del self.data[key]

    def __setitem__(  # noqa: T400
        self,
        key: str,
        value: typing.Any,
        skip_on_error: bool=False
    ) -> None:
        """Set a configuration value."""
        try:
            if self.special_properties.is_special_property(key):
                special_property = self.special_properties.get_or_create(key)
                special_property.set(value)
                self.update_special_property(key)
                return

            parsed_value = iocage.lib.helpers.parse_user_input(value)
            setter_method_name = f"_set_{key}"
            if setter_method_name in object.__dir__(self):
                setter_method = self.__getattribute__(setter_method_name)
                setter_method(
                    parsed_value,
                    skip_on_error=skip_on_error
                )
                return

            self.data[key] = parsed_value
        except ValueError as err:
            error = iocage.lib.errors.InvalidJailConfigValue(
                reason=str(err),
                property_name=key,
                logger=self.logger,
                level=("warn" if (skip_on_error is True) else "error")
            )
            if skip_on_error is False:
                raise error

    def update_special_property(self, name: str) -> None:
        """Triggered when a special property was updated."""
        self.data[name] = str(self.special_properties[name])

    def attach_special_property(
        self,
        name: str,
        special_property: 'iocage.lib.Config.Jail.Properties.Property'
    ) -> None:
        """Attach a special property to the configuration."""
        self.special_properties[name] = special_property

    def set(  # noqa: T484
        self,
        key: str,
        value: typing.Any,
        skip_on_error: bool=False
    ) -> bool:
        """
        Set a JailConfig property.

        Args:

            key (str):
                The jail config property name

            value:
                Value to set the property to

            skip_on_error (bool):
                This argument is passed through to __setitem__

        Returns:
            bool: True if the JailConfig was changed

        """
        hash_before: typing.Any
        hash_after: typing.Any

        existed_before = key in self.user_data

        try:
            hash_before = str(self._getitem_user(key)).__hash__()
        except Exception:
            hash_before = None

        self.__setitem__(key, value, skip_on_error=skip_on_error)  # noqa: T484

        exists_after = key in self.user_data

        try:
            hash_after = str(self._getitem_user(key)).__hash__()
        except Exception:
            hash_after = None

        if existed_before != exists_after:
            return True

        return (hash_before != hash_after) is True

    @property
    def user_data(self) -> typing.Dict[str, typing.Any]:
        """Return the raw dictionary of user configured settings."""
        return self.data

    def __str__(self) -> str:
        """Return the JSON object with all user configured settings."""
        return str(iocage.lib.helpers.to_json(self.data))

    def __dir__(self) -> typing.List[str]:
        """Return a list of config object attributes."""
        properties = set()
        props = dict.__dir__(self)
        for prop in props:
            if not prop.startswith("_"):
                properties.add(prop)

        for key in self.data.keys():
            properties.add(key)

        return list(properties)

    def keys(self) -> typing.KeysView:
        """Return the available configuration keys."""
        return self.data.keys()

    def items(self) -> typing.List[typing.Tuple[str, typing.Any]]:
        """Return the combined config properties."""
        return [(key, self[key],) for key in self.all_properties

    def __iter__(self) -> typing.Iterator[str]:
        """Return the combined config properties."""
        return self.data.__iter__()

    def values(self) -> typing.List[str]:
        """Return all config values."""
        return [self[key] for key in self._sorted_user_properties]

    def __len__(self) -> typing.Any:
        return len(self._sorted_user_properties)

    @property
    def all_properties(self) -> typing.List[str]:
        """Return a list of all user configured settings."""
        return self._sorted_user_properties

    @property
    def _sorted_user_properties(self) -> typing.List[str]:
        return sorted(self.data.keys())

    def stringify(self, value: typing.Any) -> str:
        """Stringify user supplied values."""
        parsed_input = iocage.lib.helpers.parse_user_input(value)
        return str(iocage.lib.helpers.to_string(parsed_input))


class JailConfigList(list):
    """Jail configuration property in form of a list."""

    def __init__(  # noqa: T484
        self,
        *args,
        delimiter: str=" ",
        **kwargs
    ) -> None:
        self.delimiter = delimiter
        list.__init__(self, *args, **kwargs)

    def __str__(self) -> str:
        """Return the string representation in iocage format."""
        return str(self.delimiter.join(self))
