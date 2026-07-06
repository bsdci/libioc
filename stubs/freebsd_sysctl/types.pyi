import ctypes
import typing

class CtlType:
    min_size: int
    data: bytes
    ctype: type | None
    unpack_format: str | None
    size: int
    def __init__(self, data: bytes, size: int) -> None: ...
    @property
    def amount(self) -> int: ...
    @property
    def value(self) -> typing.Any: ...

class NODE(CtlType):
    ctype: type[ctypes.c_uint]

class INT(CtlType):
    ctype: type[ctypes.c_int]

class STRING(CtlType):
    @property
    def value(self) -> str: ...

class S64(CtlType):
    ctype: type[ctypes.c_int64]

class STRUCT(CtlType): ...
class OPAQUE(CtlType): ...

class UINT(CtlType):
    ctype: type[ctypes.c_uint]

class LONG(CtlType):
    ctype: type[ctypes.c_long]

class ULONG(CtlType):
    ctype: type[ctypes.c_ulong]

class U64(CtlType):
    ctype: type[ctypes.c_uint64]

class U8(CtlType):
    ctype: type[ctypes.c_uint8]

class U16(CtlType):
    ctype: type[ctypes.c_uint16]

class S8(CtlType):
    ctype: type[ctypes.c_int8]

class S16(CtlType):
    ctype: type[ctypes.c_int16]

class S32(CtlType):
    ctype: type[ctypes.c_int32]

class U32(CtlType):
    ctype: type[ctypes.c_uint32]

def identify_type(kind: int, fmt: bytes) -> type[CtlType]: ...
