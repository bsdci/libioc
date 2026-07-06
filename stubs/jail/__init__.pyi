import ctypes
import ipaddress
import typing

import jail.types
from jail.libc import dll as dll

NULL_BYTES: bytes
JAIL_MAX_AF_IPS: int

RawIovecValue = typing.Optional[typing.Union[
    bytes,
    int,
    typing.List[ipaddress.IPv4Address],
    typing.List[ipaddress.IPv6Address],
]]
IovevValueInput = typing.Union[RawIovecValue, str]
IovecValueOutput = typing.Union[
    bytes,
    int,
    ctypes.Array[jail.types.in_addr],
    ctypes.Array[jail.types.in6_addr],
]

class Iovec(ctypes.Structure): ...

class IovecKey:
    def __init__(self, value: typing.Union[str, bytes]) -> None: ...
    def __bytes__(self) -> bytes: ...
    def __len__(self) -> int: ...
    def __hash__(self) -> int: ...
    def __eq__(self, other: object) -> bool: ...
    @property
    def iovec(self) -> Iovec: ...

class IovecValue:
    def __init__(self, value: IovevValueInput) -> None: ...
    @property
    def value(self) -> RawIovecValue: ...
    @value.setter
    def value(self, value: RawIovecValue) -> None: ...
    @property
    def raw_value(self) -> RawIovecValue: ...
    def __bytes__(self) -> bytes: ...
    def __int__(self) -> int: ...
    def __len__(self) -> int: ...
    @property
    def iovec(self) -> Iovec: ...

class ByteDict(dict):
    def __init__(
        self,
        data: typing.Dict[typing.Union[bytes, str], typing.Any],
    ) -> None: ...

class JiovData(dict):
    def __init__(
        self,
        data: typing.Dict[
            typing.Union[IovecKey, bytes, str],
            IovecValue,
        ],
    ) -> None: ...
    def __setitem__(
        self,
        key: typing.Union[IovecKey, bytes, str],
        value: typing.Optional[typing.Union[bytes, int, IovecValue]],
    ) -> None: ...
    def __getitem__(
        self,
        key: typing.Union[IovecKey, bytes, str],
    ) -> IovecValue: ...

class Jiov(JiovData):
    errmsg: ctypes.Array[ctypes.c_char]
    def __init__(
        self,
        params: typing.Mapping[typing.Any, typing.Any],
    ) -> None: ...
    def __len__(self) -> int: ...
    @property
    def pointer(self) -> typing.Any: ...

def get_jid_by_name(name: typing.Union[str, bytes]) -> int: ...
def is_jid_dying(jid: int) -> bool: ...
