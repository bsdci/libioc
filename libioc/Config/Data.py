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
"""Internal data storage for BaseConfig objects."""
import typing
import collections.abc

InputData = typing.Dict[str, typing.Any]


class Data(dict):
    """Internal data storage for BaseConfig objects."""

    delimiter: str = "."

    def __init__(
        self,
        data: typing.Optional[InputData]=None
    ) -> None:
        dict.__init__(self)
        if data is not None:
            for key, value in data.items():
                self.__setitem__(key, value)

    def __getitem__(
        self,
        key: str
    ) -> typing.Any:
        """Return the item while resolving nested keys."""
        data = self
        while True:
            keys = dict.keys(data)
            if self.delimiter not in key:
                if key in keys:
                    return dict.__getitem__(data, key)
                else:
                    raise KeyError(f"User property not found: {key}")
            else:
                current, key = key.split(self.delimiter, maxsplit=1)
                if current not in keys:
                    raise KeyError(f"User property not found: {current}")
                data = data[current]
                if isinstance(data, dict) is False:
                    raise KeyError(f"User property is not nested: {current}")

    def __setitem__(
        self,
        key: str,
        value: typing.Any
    ) -> None:
        """Set an item in the Data dict structure and resolve nested items."""
        data = self
        while True:
            if self.delimiter not in key:
                if isinstance(value, dict) and not isinstance(value, Data):
                    value = Data(value)
                dict.__setitem__(data, key, value)
                return
            else:
                keys = dict.keys(data)
                current, key = key.split(self.delimiter, maxsplit=1)
                if current not in keys:
                    dict.__setitem__(data, current, Data())
                data = data[current]

    def __contains__(self, key: typing.Any) -> bool:
        """Return whether a (nested) key is included in the dict."""
        if isinstance(key, str) is False:
            return False
        data = self
        while True:
            keys = dict.keys(data)
            try:
                i = key.index(self.delimiter)
            except ValueError:
                return any((
                    (key in keys) is True,
                    (key in dict.keys(data)) is True
                ))

            current = key[0:i]
            if current not in keys:
                return False
            key = key[(i + 1):]
            data = dict.__getitem__(data, current)

    def __len__(self) -> int:
        """Return the number of items in the flattened structure."""
        return len(self.keys())

    def __delitem__(self, key: str) -> None:
        """Delete the key from the (nested) structure."""
        data = self
        original_key = key
        marked_data = None
        marked_key = None
        while len(key) > 0:
            if self.delimiter not in key:
                dict.__delitem__(data, key)
                if (marked_data is not None) and (marked_key is not None):
                    # delete empty parent dictionary afterwards
                    dict.__delitem__(marked_data, marked_key)

                return
            else:
                i = key.index(self.delimiter)
                current = key[0:i]
                if current in dict.keys(data):
                    next_data = data[current]
                    if len(dict.keys(next_data)) == 1:
                        # mark for deletion of last remaining item
                        marked_data = data
                        marked_key = current
                    else:
                        # revoke deletion mark because a subitem has siblings
                        marked_data = None
                        marked_key = None
                    data = next_data
                    key = key[(i + 1):]
                else:
                    raise KeyError(original_key[:-(len(key) - 1)])

    def keys(self) -> typing.KeysView[str]:
        """Return the available configuration keys."""
        return collections.abc.KeysView(list(self.__iter__()))  # noqa: T484

    def values(self) -> typing.ValuesView[typing.Any]:
        """Return all config values."""
        return typing.cast(typing.ValuesView[typing.Any], self.__values())

    def __values(self) -> typing.Iterator[typing.Any]:
        yield from (value for _, value in self.__iter__())

    def items(self) -> typing.ItemsView[str, typing.Any]:
        """Iterate over the flattened keys and values."""
        return typing.cast(
            typing.ItemsView[str, typing.Any],
            ((x, self.__getitem__(x)) for x in self.__iter__())
        )

    def __iter__(self) -> typing.Iterator[str]:
        """Return the flattened dict iterator."""
        for key in dict.__iter__(self):
            value = dict.__getitem__(self, key)
            if isinstance(value, Data) is True:
                for subkey in value.__iter__():
                    yield f"{key}.{subkey}"
            else:
                yield key

    @property
    def nested(self) -> dict:
        """Return the data as nested dict structure."""
        out = dict()
        for key in dict.__iter__(self):
            value = dict.__getitem__(self, key)
            if isinstance(value, self.__class__):
                value = value.nested
            out[key] = value
        return out
