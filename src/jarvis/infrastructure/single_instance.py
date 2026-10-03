"""Windows named-object lifecycle, compatible with the previous C# app."""

import ctypes
import os
import threading
from ctypes import wintypes
from collections.abc import Callable

if os.name != "nt":
    raise OSError("Jarvis currently requires Windows.")

_kernel = ctypes.WinDLL("kernel32", use_last_error=True)
_security = ctypes.WinDLL("advapi32", use_last_error=True)


def _bind(library, name, arguments, result):
    function = getattr(library, name)
    function.argtypes = arguments
    function.restype = result
    return function


_create_mutex = _bind(_kernel, "CreateMutexW", [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE)
_create_event = _bind(_kernel, "CreateEventW", [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE)
_wait = _bind(_kernel, "WaitForSingleObject", [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD)
_wait_many = _bind(_kernel, "WaitForMultipleObjects", [wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE), wintypes.BOOL, wintypes.DWORD], wintypes.DWORD)
_set_event = _bind(_kernel, "SetEvent", [wintypes.HANDLE], wintypes.BOOL)
_release_mutex = _bind(_kernel, "ReleaseMutex", [wintypes.HANDLE], wintypes.BOOL)
_close = _bind(_kernel, "CloseHandle", [wintypes.HANDLE], wintypes.BOOL)
_current_process = _bind(_kernel, "GetCurrentProcess", [], wintypes.HANDLE)
_local_free = _bind(_kernel, "LocalFree", [ctypes.c_void_p], ctypes.c_void_p)
_open_token = _bind(_security, "OpenProcessToken", [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)], wintypes.BOOL)
_token_info = _bind(_security, "GetTokenInformation", [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL)
_sid_text = _bind(_security, "ConvertSidToStringSidW", [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)], wintypes.BOOL)


def _check(value):
    if not value:
        raise ctypes.WinError(ctypes.get_last_error())
    return value


def _user_sid() -> str:
    token = wintypes.HANDLE()
    _check(_open_token(_current_process(), 0x0008, ctypes.byref(token)))  # TOKEN_QUERY
    try:
        size = wintypes.DWORD()
        _token_info(token, 1, None, 0, ctypes.byref(size))  # TokenUser
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(size.value)
        _check(_token_info(token, 1, buffer, size, ctypes.byref(size)))
        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        text = wintypes.LPWSTR()
        _check(_sid_text(sid, ctypes.byref(text)))
        try:
            return text.value
        finally:
            _local_free(ctypes.cast(text, ctypes.c_void_p))
    finally:
        _close(token)


class SingleInstance:
    """Acquire/close on the UI thread. The worker never calls UI code directly."""

    def __init__(self, instance_key: str | None = None) -> None:
        self._mutex = self._activation = self._stop = None
        self._thread: threading.Thread | None = None
        self.is_primary = False
        name = instance_key or f"Jarvis.{_user_sid()}"
        try:
            self._activation = _check(_create_event(None, False, False, f"Local\\{name}.Activate"))
            self._mutex = _check(_create_mutex(None, False, f"Local\\{name}.Instance"))
            result = _wait(self._mutex, 0)
            if result not in (0, 0x80, 0x102):  # owned, abandoned, timeout
                raise ctypes.WinError(ctypes.get_last_error())
            self.is_primary = result in (0, 0x80)
            self._stop = _check(_create_event(None, True, False, None))
        except Exception:
            self.close()
            raise

    def listen(self, activate: Callable[[], None]) -> None:
        if not self.is_primary or self._thread is not None:
            raise RuntimeError("Only the primary instance can listen once.")

        def wait_for_activation() -> None:
            handles = (wintypes.HANDLE * 2)(self._stop, self._activation)
            while _wait_many(2, handles, False, 0xFFFFFFFF) == 1:
                activate()

        self._thread = threading.Thread(target=wait_for_activation, name="JarvisActivation", daemon=True)
        self._thread.start()

    def notify_primary(self) -> None:
        _check(_set_event(self._activation))

    def close(self) -> None:
        if self._thread is not None:
            _set_event(self._stop)
            self._thread.join()
            self._thread = None
        if self.is_primary and self._mutex:
            _release_mutex(self._mutex)
            self.is_primary = False
        for attribute in ("_mutex", "_activation", "_stop"):
            handle = getattr(self, attribute)
            if handle:
                _close(handle)
                setattr(self, attribute, None)
