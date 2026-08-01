from __future__ import annotations

import ctypes
import pathlib


class BridgeAttachmentError(RuntimeError):
    pass


def attach_observer(snes, library_path: pathlib.Path, ledger_path: pathlib.Path,
                    schema_version: str, build_hash: str, solve_id: str) -> dict[str, object]:
    if ctypes.sizeof(ctypes.c_void_p) != ctypes.sizeof(ctypes.c_size_t):
        raise BridgeAttachmentError("uintptr_t and void* widths differ")
    handle = int(snes.handle)
    if handle <= 0:
        raise BridgeAttachmentError("petsc4py returned a null SNES handle")
    library = ctypes.CDLL(str(library_path))
    function = library.P4dObserverAttach
    function.argtypes = [
        ctypes.c_size_t,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_size_t,
    ]
    function.restype = ctypes.c_int
    error = ctypes.create_string_buffer(512)
    result = function(
        ctypes.c_size_t(handle),
        str(ledger_path).encode("utf-8"),
        schema_version.encode("ascii"),
        build_hash.encode("ascii"),
        solve_id.encode("ascii"),
        error,
        ctypes.sizeof(error),
    )
    if result != 0:
        raise BridgeAttachmentError(f"P4dObserverAttach failed ({result}): {error.value.decode('utf-8', 'replace')}")
    return {
        "handle_integer": handle,
        "pointer_bits": ctypes.sizeof(ctypes.c_void_p) * 8,
        "library_path": str(library_path),
        "ledger_path": str(ledger_path),
        "attach_result": result,
        "attach_message": error.value.decode("ascii"),
        "library_keepalive": library,
    }
