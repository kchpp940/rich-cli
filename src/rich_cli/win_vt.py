"""
Windows virtual terminal processing support.

Encapsulates Windows console mode management (handle acquisition, mode reading,
VT enabling, and original mode restoration) in a state object. External callers
only use the `enable_windows_virtual_terminal_processing` context manager.

"""

__all__ = ["enable_windows_virtual_terminal_processing"]

from contextlib import contextmanager
import ctypes
from ctypes import byref
from typing import Optional

import platform

WINDOWS = platform.system() == "Windows"

if WINDOWS:
    from ctypes.wintypes import DWORD, HANDLE

    _STD_OUTPUT_HANDLE = -11
    _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    _KERNEL32.GetStdHandle.argtypes = [DWORD]
    _KERNEL32.GetStdHandle.restype = HANDLE
    _KERNEL32.GetConsoleMode.argtypes = [HANDLE, ctypes.POINTER(DWORD)]
    _KERNEL32.GetConsoleMode.restype = ctypes.c_bool
    _KERNEL32.SetConsoleMode.argtypes = [HANDLE, DWORD]
    _KERNEL32.SetConsoleMode.restype = ctypes.c_bool

    class WindowsConsoleVT:
        """Manages Windows console virtual terminal processing state.

        Encapsulates all Windows API interactions for enabling/disabling
        ANSI color support. External code should not use this class
        directly; use `enable_windows_virtual_terminal_processing` instead.

        State semantics:
        - ``original_mode``: Console mode before entering the context, or None
        - ``enabled_by_context``: True only if this context manager actually
          enabled VT processing (i.e., VT was off before and we turned it on).
          When False, we must not modify the console mode on exit.

        """

        def __init__(self) -> None:
            self._handle: Optional[HANDLE] = None
            self.original_mode: Optional[int] = None
            self.enabled_by_context: bool = False
            self._invalid_handle_value = HANDLE(-1).value

        def _get_std_output_handle(self) -> HANDLE:
            """Get the standard output handle from Windows API."""
            return _KERNEL32.GetStdHandle(_STD_OUTPUT_HANDLE)

        def _get_console_mode(self, handle: HANDLE) -> Optional[int]:
            """Read the current console mode."""
            mode = DWORD()
            if _KERNEL32.GetConsoleMode(handle, byref(mode)):
                return mode.value
            return None

        def _set_console_mode(self, handle: HANDLE, mode: int) -> bool:
            """Set the console mode."""
            return bool(_KERNEL32.SetConsoleMode(handle, mode))

        def __enter__(self) -> "WindowsConsoleVT":
            """Enable virtual terminal processing only if not already enabled."""
            self._handle = self._get_std_output_handle()
            if self._handle.value == self._invalid_handle_value:
                return self

            self.original_mode = self._get_console_mode(self._handle)
            if self.original_mode is None:
                return self

            if not (self.original_mode & _ENABLE_VIRTUAL_TERMINAL_PROCESSING):
                new_mode = self.original_mode | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
                self.enabled_by_context = self._set_console_mode(self._handle, new_mode)

            return self

        def __exit__(
            self,
            exc_type: Optional[type],
            exc_val: Optional[BaseException],
            exc_tb: Optional[object],
        ) -> None:
            """Restore original mode only if this context enabled VT processing."""
            if self.enabled_by_context and self._handle is not None and self.original_mode is not None:
                self._set_console_mode(self._handle, self.original_mode)
                self.enabled_by_context = False

    @contextmanager
    def enable_windows_virtual_terminal_processing():
        """Context manager to enable virtual terminal processing on enter,
        and restore the previous setting on exit. Does nothing if run on
        a non-Windows platform or if not attached to a console.

        """
        with WindowsConsoleVT():
            yield

else:

    class WindowsConsoleVT:
        """No-op placeholder for non-Windows platforms.

        State semantics match the Windows implementation:
        - ``original_mode``: Always None on non-Windows
        - ``enabled_by_context``: Always False on non-Windows

        """

        def __init__(self) -> None:
            self.original_mode: Optional[int] = None
            self.enabled_by_context: bool = False

        def __enter__(self) -> "WindowsConsoleVT":
            return self

        def __exit__(
            self,
            exc_type: Optional[type],
            exc_val: Optional[BaseException],
            exc_tb: Optional[object],
        ) -> None:
            return None

    @contextmanager
    def enable_windows_virtual_terminal_processing():
        """Context manager to enable virtual terminal processing on enter,
        and restore the previous setting on exit. Does nothing if run on
        a non-Windows platform.

        """
        with WindowsConsoleVT():
            yield
