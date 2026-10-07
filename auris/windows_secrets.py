from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes


DPAPI_PREFIX = "DPAPI1:"
CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def dpapi_available() -> bool:
    return os.name == "nt" and hasattr(ctypes, "windll")


def protect_for_current_user(secret: bytes, *, purpose: str) -> str:
    if not secret:
        raise ValueError("A secret is required.")
    protected = _crypt_protect(secret, purpose.encode("utf-8"))
    return DPAPI_PREFIX + base64.b64encode(protected).decode("ascii")


def unprotect_for_current_user(value: str, *, purpose: str) -> bytes:
    if not value.startswith(DPAPI_PREFIX):
        raise ValueError("The protected secret format is invalid.")
    try:
        protected = base64.b64decode(value[len(DPAPI_PREFIX) :], validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError("The protected secret payload is invalid.") from error
    return _crypt_unprotect(protected, purpose.encode("utf-8"))


def _blob(value: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(value)
    blob = _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer


def _crypt_protect(secret: bytes, entropy: bytes) -> bytes:
    if not dpapi_available():
        raise RuntimeError("Windows DPAPI is unavailable.")
    input_blob, input_buffer = _blob(secret)
    entropy_blob, entropy_buffer = _blob(entropy)
    output_blob = _DataBlob()
    success = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "AURIS protected device credential",
        ctypes.byref(entropy_blob),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )
    del input_buffer, entropy_buffer
    if not success:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def _crypt_unprotect(protected: bytes, entropy: bytes) -> bytes:
    if not dpapi_available():
        raise RuntimeError("Windows DPAPI is unavailable.")
    input_blob, input_buffer = _blob(protected)
    entropy_blob, entropy_buffer = _blob(entropy)
    output_blob = _DataBlob()
    success = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )
    del input_buffer, entropy_buffer
    if not success:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)
