"""Windows implementation of the Platform contract.

All ``ctypes``/``wintypes`` access is deferred to call time so the module
imports cleanly on macOS and Linux.
"""

from __future__ import annotations

import os

from . import Platform


def _windows_process_name_for_pid(pid: int):
    """Return the lowercase basename of the executable for a PID, or None."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        process_query_limited_information = 0x1000
        handle = kernel32.OpenProcess(
            process_query_limited_information,
            False,
            int(pid),
        )
        if not handle:
            return None
        try:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(
                handle,
                0,
                buffer,
                ctypes.byref(size),
            ):
                return os.path.basename(buffer.value).lower()
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None
    return None


def _windows_foreground_window_identity():
    """Stable foreground-window identity for Windows focus locking.

    Window titles often mutate while text is being typed (dirty markers,
    browser tab titles, editor state). The top-level HWND stays stable for
    the focused control, so we combine it with the process exe basename.
    Returns None on failure.
    """
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]

        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        hwnd = user32.GetForegroundWindow()
        hwnd_value = int(getattr(hwnd, "value", hwnd) or 0)
        if not hwnd_value:
            return None

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        process_name = None
        if pid.value:
            process_name = _windows_process_name_for_pid(pid.value)

        if process_name:
            return f"{process_name}:{hwnd_value:x}"
        return f"hwnd:{hwnd_value:x}"
    except Exception:
        return None


class WindowsPlatform(Platform):
    name = "windows"

    def accessibility_trusted(self, prompt: bool = False) -> bool:
        # Windows has no equivalent gate for synthetic input.
        return True

    def open_privacy_settings(self) -> None:
        # No direct equivalent; nothing to open.
        return None

    def active_app_identity(self) -> str:
        ident = _windows_foreground_window_identity()
        if ident:
            return ident
        # Fallback to a window-title probe.
        try:
            import pyautogui  # type: ignore
            return pyautogui.getActiveWindowTitle() or "Unknown"
        except Exception:
            return "Unknown"

    def release_modifiers_best_effort(self) -> None:
        try:
            import pyautogui  # type: ignore
        except Exception:
            return
        for key in ("shift", "ctrl", "alt", "command", "cmd", "option"):
            try:
                pyautogui.keyUp(key)
            except Exception:
                pass

    def paste_via_keyboard_shortcut(self) -> None:
        try:
            import pyautogui  # type: ignore
            pyautogui.hotkey("ctrl", "v")
        except Exception:
            pass

    def type_unicode_char(self, ch: str) -> bool:
        # No Unicode-Hex input parity on Windows; caller falls back to ASCII.
        return False
