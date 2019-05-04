# Copyright (c) 2017-2019, Stefan Grönke
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

import libioc.Config.Data
import libioc.Config.Jail.Globals
import libioc.Config.Jail.Properties
import libioc.Config.Jail.Defaults
import libioc.errors
import libioc.helpers
import libioc.helpers_object
import libioc.JailParams

# mypy
import libioc.Logger
InputData = typing.Dict[str, typing.Union[
    libioc.Config.Jail.Properties.Property,
    str,
    int,
    bool,
    typing.Dict[str, typing.Union[str, int, bool]]
]]
Data = libioc.Config.Data.Data


class BaseConfig(dict):
    """
    Model a plain iocage jail configuration.

    A jail configuration can be loaded from various formats that were used
    by different versions of libioc. Technically it is possible to store
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

    _data: libioc.Config.Data.Data
    special_properties: 'libioc.Config.Jail.Properties.Properties'

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        if hasattr(self, "_data") is False:
            self._data = libioc.Config.Data.Data()
        self.logger = libioc.helpers_object.init_logger(self, logger)

        Properties = libioc.Config.Jail.Properties.JailConfigProperties
        self.special_properties = Properties(
            config=self,
            logger=self.logger
        )

    @property
    def data(self) -> libioc.Config.Data.Data:
        """Return the data object."""
        return self._data

    @data.setter
    def data(self, new_data: libioc.Config.Data.Data) -> None:
        """Validate and set the data object."""
        if isinstance(new_data, libioc.Config.Data.Data) is False:
            raise TypeError("data needs to be a flat dict structure")
        new_data_keys = new_data.keys()
        old_data = self._data
        try:
            self._data = dict()
            identifier_keys = ["id", "name", "uuid"]
            for key in identifier_keys:
                if key in new_data_keys:
                    self["id"] = new_data[key]
                    break
            for key in new_data_keys:
                if key in identifier_keys:
                    continue
                self[key] = new_data[key]
        except Exception:
            self.logger.verbose("Configuration was not modified")
            self._data = old_data
            raise

    def clone(
        self,
        data: InputData,
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
        if isinstance(data, dict) and not isinstance(data, Data):
            data = libioc.Config.Data.Data(dict(data))
        keys = data.keys()
        if len(keys) == 0:
            return

        # the name is used in many other variables and needs to be set first
        for key in ["id", "name", "uuid"]:
            if key in data.keys():
                data["id"] = data[key]
                break

        try:
            current_id = self.data["id"]
        except KeyError:
            current_id = None

        # overwrite different identifiers with the detected current_id
        if current_id is not None:
            for key in ["id", "name", "uuid"]:
                if key in keys:
                    data[key] = current_id

        new_data = libioc.Config.Data.Data(data)
        if current_id is not None:
            new_data["id"] = current_id

        self.set_dict(
            new_data,
            explicit=False,
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

    def _set_legacy(
        self,
        value: typing.Union[bool, str]
    ) -> None:
        try:
            self.legacy = libioc.helpers.parse_bool(value)
        except TypeError:
            self.legacy = False

    def _get_id(self) -> str:
        return str(self.data["id"])

    def _set_id(self, name: str) -> None:

        if ("id" in self.data.keys()) and (self.data["id"] == name):
            # We do not want to set the same name twice.
            # This can occur when the Jail is initialized
            # with it's name and the same name is read from
            # the configuration
            return

        if name is None:
            self.data["id"] = None
            return

        disallowed_characters_pattern = "([^A-Za-z0-9_\\-]|\\^)"
        invalid_characters = re.findall(disallowed_characters_pattern, name)
        if len(invalid_characters) > 0:
            raise libioc.errors.InvalidJailName(
                name=name,
                invalid_characters=invalid_characters,
                logger=self.logger
            )

        is_valid_name = libioc.helpers.validate_name(name)
        if is_valid_name is True:
            self.data["id"] = name
        else:
            if libioc.helpers.is_uuid(name) is True:
                self.data["id"] = name
            else:
                raise libioc.errors.InvalidJailName(
                    name=name,
                    logger=self.logger
                )

    def _get_name(self) -> str:
        return self._get_id()

    def _set_name(self, name: str) -> None:
        return self._set_id(name=name)

    def _get_uuid(self) -> str:
        return self._get_id()

    def _get_type(self) -> str:

        if self["basejail"]:
            return "basejail"
        elif self["clonejail"]:
            return "clonejail"
        else:
            return "jail"

    def _set_type(self, value: typing.Optional[str]) -> None:

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

    def _set_priority(self, value: typing.Union[int, str]) -> None:
        self.data["priority"] = str(libioc.helpers.parse_int(value))

    # legacy support
    def _get_tag(self) -> typing.Optional[str]:

        if self._has_legacy_tag is True:
            return str(self.data["tag"])

        try:
            return str(self["tags"][0])
        except (KeyError, IndexError):
            return None

    def _set_tag(self, value: str) -> None:

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
        self.data["tags"] = libioc.helpers.to_string(tags)

    @property
    def _has_legacy_tag(self) -> bool:
        return ("tag" in self.data.keys()) is True

    def _get_vnet_interfaces(self) -> typing.List[str]:
        return list(
            libioc.helpers.parse_list(self.data["vnet_interfaces"])
        )

    def _set_vnet_interfaces(
        self,
        value: typing.Optional[typing.Union[str, typing.List[str]]]
    ) -> None:
        try:
            libioc.helpers.parse_none(value)
            self.data["vnet_interfaces"] = []
            return
        except TypeError:
            pass

        if isinstance(value, str) is True:
            self.data["vnet_interfaces"] = value
        else:
            self.data["vnet_interfaces"] = libioc.helpers.to_string(value)

    def _get_exec_clean(self) -> bool:
        return (self.data["exec_clean"] == 1) is True

    def _set_exec_clean(self, value: typing.Union[str, int, bool]) -> None:
        if isinstance(value, str):
            value = int(value)
        self.data["exec_clean"] = 1 if ((value is True) or (value == 1)) else 0

    def _get_tags(self) -> typing.List[str]:

        data_keys = self.data.keys()

        if "tags" in data_keys:
            tags = list(libioc.helpers.parse_list(self.data["tags"]))
        else:
            tags = list()

        if (self._has_legacy_tag is True):
            tags.append(self.data["tag"])

        return self.__unique_list(tags)

    @property
    def __has_mounts_enabled(self) -> bool:
        prefix = "allow_mount_"
        return any((self[x] == 1) for x in self.keys() if x.startswith(prefix))

    def _get_enforce_statfs(self) -> int:
        key = "enforce_statfs"
        if key in self.data.keys():
            return int(self.data[key])

        if self.__has_mounts_enabled:
            self.logger.verbose(
                "setting enforce_statfs=1 to support allowed mounts"
            )
            return 1

        raise KeyError(f"{key} unconfigured")

    def _get_allow_mount(self) -> int:
        key = "allow_mount"
        if key in self.data.keys():
            return int(self.data[key])

        if self.__has_mounts_enabled:
            self.logger.verbose(
                "inheriting allow_mount=1 from allowed mounts"
            )
            return 1

        raise KeyError(f"{key} unconfigured")

    def __unique_list(self, seq: typing.List[str]) -> typing.List[str]:
        seen: typing.Set[str] = set()
        seen_add = seen.add
        return [x for x in seq if not (x in seen or seen_add(x))]  # noqa

    def _set_tags(
        self,
        value: typing.Union[
            str,
            bool,
            int,
            typing.List[typing.Union[str, bool, int]]
        ]
    ) -> None:

        data = libioc.helpers.to_string(value)
        self.data["tags"] = data

        if self._has_legacy_tag is True:
            del self.data["tag"]

    def _get_basejail(self) -> bool:
        return libioc.helpers.parse_bool(self.data["basejail"]) is True

    def _set_basejail(self, value: typing.Any) -> None:
        self.data["basejail"] = self.stringify(value)

    def _get_clonejail(self) -> bool:
        return libioc.helpers.parse_bool(self.data["clonejail"]) is True

    def _set_clonejail(
        self,
        value: typing.Optional[typing.Union[str, bool]]
    ) -> None:
        self.data["clonejail"] = self.stringify(value)

    def _get_template(self) -> bool:
        return libioc.helpers.parse_bool(
            self.data.get("template", False)
        ) is True

    def _set_template(
        self,
        value: typing.Union[str, bool]
    ) -> None:
        try:
            self.data["template"] = libioc.helpers.parse_bool(value)
        except (ValueError, TypeError) as e:
            raise ValueError(str(e))

    def _get_vnet(self) -> bool:
        return libioc.helpers.parse_bool(self.data["vnet"]) is True

    def _set_vnet(self, value: typing.Union[str, bool]) -> None:
        self.data["vnet"] = libioc.helpers.to_string(
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

    def _set_jail_zfs_dataset(
        self,
        value: typing.Optional[typing.Union[typing.List[str], str]]
    ) -> None:
        value = [value] if isinstance(value, str) else value
        if value is None:
            self.data["jail_zfs_dataset"] = ""
        else:
            self.data["jail_zfs_dataset"] = " ".join(value)

    def _get_jail_zfs(self) -> bool:
        return libioc.helpers.parse_bool(
            self.data["jail_zfs"]
        ) is True

    def _set_jail_zfs(
        self,
        value: typing.Optional[typing.Union[bool, str]],
    ) -> None:
        try:
            libioc.helpers.parse_none(value)
            del self.data["jail_zfs"]
            return
        except TypeError:
            pass
        self.data["jail_zfs"] = libioc.helpers.to_string(
            libioc.helpers.parse_bool(value),
            true="on",
            false="off"
        )

    def _set_cloned_release(
        self,
        value: typing.Optional[str]
    ) -> None:
        if (value is None) and "cloned_release" in self.data.keys():
            del self.data["cloned_release"]
        self["release"] = value
        self.data["cloned_release"] = value

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

    def _set_login_flags(
        self,
        value: typing.Optional[typing.Union[str, typing.List[str]]]
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
                raise libioc.errors.InvalidJailConfigValue(
                    property_name="login_flags",
                    logger=self.logger
                )

    def _get_host_hostuuid(self) -> str:
        try:
            hostuuid = self.data["host_hostuuid"]
            if hostuuid is None:
                raise ValueError
            return str(hostuuid)
        except (KeyError, ValueError):
            return str(self["id"])

    def _get_host_hostname(self) -> str:
        try:
            hostname = self.data["host_hostname"]
            if hostname is None:
                raise ValueError
            return str(hostname)
        except (KeyError, ValueError):
            return str(self["id"])

    def _get_host_domainname(self) -> str:
        try:
            return str(self.data["host_domainname"])
        except KeyError:
            return "local"

    def get_string(self, key: str) -> str:
        """Get the stringified value of a configuration property."""
        return self.stringify(self.__getitem__(key))

    def update_special_property(self, name: str) -> None:
        """Triggered when a special property was updated."""
        self.data[name] = str(self.special_properties[name])

    def attach_special_property(
        self,
        name: str,
        special_property: 'libioc.Config.Jail.Properties.Property'
    ) -> None:
        """Attach a special property to the configuration."""
        self.special_properties[name] = special_property

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

    def get_raw(self, key: str) -> typing.Any:
        """Return the raw data value."""
        return self.data[key]

    def _getitem_special_property(
        self,
        key: str,
        data: libioc.Config.Data.Data
    ) -> libioc.Config.Jail.Properties.Property:
        if key in self:
            special_property = self.special_properties.get_or_create(key)
            special_property.set(data[key], skip_on_error=False)
            return special_property
        elif key in libioc.Config.Jail.Properties.ResourceLimit.properties:
            raise KeyError(f"Resource-Limit unconfigured: {key}")
        else:
            raise KeyError(f"Special Property unconfigured: {key}")

    def __getitem__(self, key: str) -> typing.Any:
        """
        Get the user configured value of a jail configuration property.

        The lookup order of such values is:
            - special properties
            - _get_{key} methods
            - plain data keys (without special processing)

        A KeyError is raised when no criteria applies.
        """
        if key not in self.data.keys():
            self._require_known_config_property(key, explicit=False)

        # special property
        if self.special_properties.is_special_property(key) is True:
            return self._getitem_special_property(key, self.data)

        # data with mappings
        method_name = f"_get_{key}"
        if method_name in dict.__dir__(self):
            get_method = self.__getattribute__(method_name)
            return get_method()

        # plain data attribute
        return libioc.helpers.parse_user_input(self.data[key])

    @property
    def unknown_config_parameters(self) -> typing.Iterator[str]:
        """Yield unknown config parameters already stored in the config."""
        for key in self.data.keys():
            if self.is_known_property(key, explicit=True) is False:
                yield key

    def __delitem__(self, key: str) -> None:
        """Delete a setting from the configuration."""
        self.data.__delitem__(key)

    def __setitem__(  # noqa: T400
        self,
        key: str,
        value: typing.Any,
        skip_on_error: bool=False,
        explicit: bool=True
    ) -> None:
        """Set a configuration value."""
        if self.is_known_property(key, explicit=explicit) is False:
            if "jail" in dir(self):
                _jail = self.jail  # noqa: T484
            else:
                _jail = None
            err = libioc.errors.UnknownConfigProperty(
                key=key,
                logger=self.logger,
                level=("warn" if skip_on_error else "error"),
                jail=_jail
            )
            if skip_on_error is False:
                raise err

        try:
            if self.special_properties.is_special_property(key):
                special_property = self.special_properties.get_or_create(key)
                special_property.set(value, skip_on_error=skip_on_error)
                self.update_special_property(key)
                return

            parsed_value = libioc.helpers.parse_user_input(value)

            setter_method_name = f"_set_{key}"
            if setter_method_name in object.__dir__(self):
                setter_method = self.__getattribute__(setter_method_name)
                setter_method(parsed_value)
                return

            self.data[key] = self.__sanitize_value(key, parsed_value)
            error = None
        except ValueError as err:
            if isinstance(err, libioc.errors.IocException) is True:
                error = err
            else:
                error = libioc.errors.InvalidJailConfigValue(
                    reason=str(err),
                    property_name=key,
                    logger=self.logger,
                    level=("warn" if (skip_on_error is True) else "error")
                )

        if (error is not None) and (skip_on_error is False):
            raise error

    def __sanitize_value(self, key: str, value: typing.Any) -> typing.Any:
        """Sanitize the value type to the same found in hardcoded defaults."""
        try:
            default_type = self.__get_default_type(key)
        except KeyError:
            return value

        try:
            # allow any time to be None
            return libioc.helpers.parse_none(value)
        except TypeError:
            pass

        if default_type == list:
            return libioc.helpers.parse_list(value)
        elif default_type == str:
            return str(value)
        elif default_type == bool:
            return libioc.helpers.parse_bool(value)
        elif default_type == int:
            return libioc.helpers.parse_int(value)

        return value

    def __get_default_type(self, key: str) -> typing.Optional[type]:
        return type(libioc.Config.Jail.Globals.DEFAULTS[key])

    def set(  # noqa: T484
        self,
        key: str,
        value: typing.Any,
        skip_on_error: bool=False,
        explicit: bool=False
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
        existed_before = (key in self.keys()) is True

        try:
            if existed_before is False:
                hash_before = False
            elif isinstance(
                self,
                libioc.Config.Jail.Defaults.JailConfigDefaults
            ) is True:
                hash_before = str(self.__getitem__(key)).__hash__()
            else:
                hash_before = str(BaseConfig.__getitem__(self, key)).__hash__()
        except Exception:
            if existed_before is True:
                raise
            hash_before = None

        self.__setitem__(  # noqa: T484
            key,
            value,
            skip_on_error=skip_on_error,
            explicit=explicit
        )

        exists_after = (key in self.keys()) is True

        try:
            hash_after = str(self.__getitem__(key)).__hash__()
        except Exception:
            hash_after = None

        if existed_before != exists_after:
            return True

        return (hash_before != hash_after) is True

    def set_dict(
        self,
        data: typing.Dict[str, typing.Any],
        skip_on_error: bool=False,
        explicit: bool=True
    ) -> typing.Set[str]:
        """
        Set a dict of jail config properties.

        Returns a list of updated properties.
        """
        setter_args = dict(skip_on_error=skip_on_error, explicit=explicit)
        updated_properties = set()
        for key in sorted(data.keys(), key=self.__sort_config_keys):
            if self.set(key, data[key], **setter_args) is True:
                updated_properties.add(key)
        return updated_properties

    @staticmethod
    def __sort_config_keys(key: str) -> int:
        """Penalizes certain config keys, so that they are always set later."""
        return 1 if key.endswith("_mac") else 0

    def __str__(self) -> str:
        """Return the JSON object with all user configured settings."""
        return str(libioc.helpers.to_json(self.data.nested))

    def __repr__(self) -> str:
        """Return the confgured settings in human and robot friendly format."""
        return self.__str__()

    def __dir__(self) -> typing.List[str]:
        """Return a list of config object attributes."""
        properties = set()
        props = dict.__dir__(self)
        for prop in props:
            if not prop.startswith("_"):
                properties.add(prop)

        return list(properties)

    def keys(self) -> typing.KeysView[str]:
        """Return the available configuration keys."""
        return typing.cast(typing.KeysView[typing.Any], self.data.keys())

    def values(self) -> typing.ValuesView[typing.Any]:
        """Return all config values."""
        return typing.cast(typing.ValuesView[typing.Any], self.data.values())

    def items(self) -> typing.ItemsView[str, typing.Any]:
        """Return the combined config properties."""
        return typing.cast(
            typing.ItemsView[str, typing.Any],
            self.data.items()
        )

    def __contains__(self, key: typing.Any) -> bool:
        """Return whether a (nested) key is included in the dict."""
        return (self.data.__contains__(key) is True)

    def __iter__(self) -> typing.Iterator[str]:
        """Return the combined config properties."""
        return typing.cast(
            typing.Iterator[str],
            self.data.__iter__()
        )

    def __len__(self) -> int:
        """Return the number of user configuration properties."""
        return len(self._sorted_user_properties)

    @property
    def all_properties(self) -> typing.List[str]:
        """Return a list of config object attributes."""
        properties: typing.Set[str] = set(self.keys())
        special_properties = libioc.Config.Jail.Properties.properties
        return list(properties.union(special_properties))

    def _key_is_mac_config(self, key: str, explicit: bool) -> bool:
        fragments = key.rsplit("_", maxsplit=1)
        if len(fragments) < 2:
            return False
        elif fragments[1].lower() != "mac":
            return False
        elif explicit is False:
            # do not explicitly check if the interface exists
            return True
        return (fragments[0] in self["interfaces"].keys()) is True

    @staticmethod
    def is_user_property(key: str) -> bool:
        """Return whether the given key belongs to a custom user property."""
        return (key == "user") or (key.startswith("user.") is True)

    def is_known_property(self, key: str, explicit: bool) -> bool:
        """Return True when the key is a known config property."""
        if self._is_known_jail_param(key):
            return True
        if key in libioc.Config.Jail.Globals.DEFAULTS.keys():
            return True  # key is default
        elif key in dict.keys(libioc.Config.Jail.Globals.DEFAULTS):
            # key could be a dict key
            return isinstance(libioc.Config.Jail.Globals.DEFAULTS[key], dict)
        if f"_set_{key}" in dict.__dir__(self):
            return True  # key is setter
        if f"_get_{key}" in dict.__dir__(self):
            return True  # key is getter
        if key in libioc.Config.Jail.Properties.properties:
            return True  # key is special property
        if self._key_is_mac_config(key, explicit=explicit) is True:
            return True  # nic mac config property
        if self.is_user_property(key) is True:
            return True  # user.* property
        return False

    def _is_known_jail_param(self, key: str) -> bool:
        return (key in libioc.JailParams.HostJailParams()) is True

    @property
    def _sorted_user_properties(self) -> typing.List[str]:
        return sorted(self.keys())

    def stringify(self, value: typing.Any) -> str:
        """Stringify user supplied values."""
        parsed_input = libioc.helpers.parse_user_input(value)
        return str(libioc.helpers.to_string(parsed_input))

    def _require_known_config_property(
        self,
        key: str,
        explicit: bool=True
    ) -> None:
        if self.is_known_property(key, explicit=explicit) is False:
            raise libioc.errors.UnknownConfigProperty(
                key=key,
                logger=self.logger
            )


class JailConfigList(list):
    """Jail configuration property in form of a list."""

    def __init__(
        self,
        data: typing.List[str]=[],
        delimiter: str=" ",
    ) -> None:
        self.delimiter = delimiter
        list.__init__(self, data)

    def __str__(self) -> str:
        """Return the string representation in iocage format."""
        return str(self.delimiter.join(self))
