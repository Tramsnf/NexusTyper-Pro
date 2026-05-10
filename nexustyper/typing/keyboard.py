"""Keyboard input router for the typing engine.

pyautogui on Windows uses the legacy ``keybd_event`` API. That API generates
synthetic key events with a virtual-key code but **no hardware scancode**.
Chrome Remote Desktop, mstsc.exe, AnyDesk, TeamViewer, Parsec, RustDesk, etc.
only forward events to the remote session when they carry a real scancode,
so pyautogui-typed text never reaches the remote application even though the
local remote-desktop window thinks a key was pressed.

This module provides a Windows-only scancode backend (``SendInput`` with
``KEYEVENTF_SCANCODE``) and a small ``KeyboardShim`` that mirrors the subset
of the pyautogui API the typing worker actually uses
(``press``/``keyDown``/``keyUp``/``typewrite``/``hotkey``). The shim selects
between pyautogui and the scancode backend per-call based on the user's
"Remote Desktop compat" setting:

* ``MODE_OFF``  – always use pyautogui (original behavior).
* ``MODE_AUTO`` – use the scancode backend when the focused window's title
  matches a known remote-desktop client.
* ``MODE_ON``   – always use the scancode backend.

On macOS and Linux the scancode backend is ``None`` and every call falls
through to plain pyautogui — behavior on those platforms is unchanged.
"""

from __future__ import annotations
from nexustyper.services.logging_setup import _log_caught

import platform
import time
from typing import Optional

import pyautogui


# Window-title substrings (lowercase) used by the "Auto" mode to detect that
# the focused window belongs to a remote-desktop client. The list is
# intentionally permissive — the worst case for a false positive is that
# scancode input is used locally too, which works fine.
_RDP_TITLE_HINTS = (
    "chrome remote desktop",
    "remote desktop connection",
    "remotedesktop.google.com",
    "anydesk",
    "teamviewer",
    "parsec",
    "rustdesk",
    "nomachine",
    "splashtop",
    "screenconnect",
    "mstsc",
)


if platform.system() == "Windows":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _ULONG_PTR = (
        ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
    )

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", _ULONG_PTR),
        ]

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", _ULONG_PTR),
        ]

    class _HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [
            ("ki", _KEYBDINPUT),
            ("mi", _MOUSEINPUT),
            ("hi", _HARDWAREINPUT),
        ]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    _user32.SendInput.argtypes = [
        wintypes.UINT,
        ctypes.POINTER(_INPUT),
        ctypes.c_int,
    ]
    _user32.SendInput.restype = wintypes.UINT
    _user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
    _user32.VkKeyScanW.restype = ctypes.c_short
    _user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    _user32.MapVirtualKeyW.restype = wintypes.UINT

    _INPUT_KEYBOARD = 1
    _KEYEVENTF_EXTENDEDKEY = 0x0001
    _KEYEVENTF_KEYUP = 0x0002
    _KEYEVENTF_UNICODE = 0x0004
    _KEYEVENTF_SCANCODE = 0x0008
    _MAPVK_VK_TO_VSC = 0

    # Virtual keys that the keyboard reports with the extended-key bit set.
    # Without this bit, arrow keys / nav cluster / numpad-divide / right-
    # modifier keys send the wrong scancode and the OS misinterprets them.
    _EXTENDED_VKS = {
        0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
        0x2C, 0x2D, 0x2E,
        0x90,
        0xA3, 0xA5,
        0x5B, 0x5C, 0x5D,
        0x6F,
    }

    _VK_NAME_MAP = {
        "esc": 0x1B, "escape": 0x1B,
        "tab": 0x09,
        "enter": 0x0D, "return": 0x0D,
        "backspace": 0x08, "back": 0x08,
        "space": 0x20, " ": 0x20,
        "shift": 0xA0, "shiftleft": 0xA0, "shiftright": 0xA1,
        "ctrl": 0xA2, "ctrlleft": 0xA2, "ctrlright": 0xA3, "control": 0xA2,
        "alt": 0xA4, "altleft": 0xA4, "altright": 0xA5, "option": 0xA4,
        "win": 0x5B, "winleft": 0x5B, "winright": 0x5C,
        "command": 0x5B, "cmd": 0x5B, "super": 0x5B,
        "capslock": 0x14,
        "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
        "home": 0x24, "end": 0x23,
        "pageup": 0x21, "pagedown": 0x22, "pgup": 0x21, "pgdn": 0x22,
        "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "ins": 0x2D,
        "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
        "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    }

    def _send_inputs(inputs):
        if not inputs:
            return
        arr = (_INPUT * len(inputs))(*inputs)
        _user32.SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))

    def _vk_input(vk: int, key_up: bool = False) -> "_INPUT":
        """Build a SendInput record for a virtual key.

        Prefers KEYEVENTF_SCANCODE (which CRD/RDP forward to the remote);
        falls back to a plain virtual-key event if the layout lookup fails.
        """
        scan = _user32.MapVirtualKeyW(vk, _MAPVK_VK_TO_VSC)
        if scan == 0:
            flags = _KEYEVENTF_KEYUP if key_up else 0
            ki = _KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
        else:
            flags = _KEYEVENTF_SCANCODE
            if vk in _EXTENDED_VKS:
                flags |= _KEYEVENTF_EXTENDEDKEY
            if key_up:
                flags |= _KEYEVENTF_KEYUP
            ki = _KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
        return _INPUT(type=_INPUT_KEYBOARD, u=_INPUTUNION(ki=ki))

    def _unicode_input(ch: str, key_up: bool = False) -> "_INPUT":
        flags = _KEYEVENTF_UNICODE | (_KEYEVENTF_KEYUP if key_up else 0)
        ki = _KEYBDINPUT(wVk=0, wScan=ord(ch), dwFlags=flags, time=0, dwExtraInfo=0)
        return _INPUT(type=_INPUT_KEYBOARD, u=_INPUTUNION(ki=ki))

    class _WinScancodeBackend:
        """SendInput-based keyboard backend that emits hardware scancodes.

        Mirrors the subset of the pyautogui API used by the typing engine:
        ``press``, ``keyDown``, ``keyUp``, ``typewrite``, ``hotkey``.
        Unknown key names fall through to a Unicode injection for single
        characters; for everything else the call is a no-op (better than
        raising and crashing the worker mid-type).
        """

        def _vk(self, name) -> Optional[int]:
            if name is None:
                return None
            n = str(name).lower()
            if n in _VK_NAME_MAP:
                return _VK_NAME_MAP[n]
            if len(n) == 1:
                res = _user32.VkKeyScanW(ctypes.c_wchar(n))
                if res != -1:
                    return res & 0xFF
            return None

        def _press_vk(self, vk: int, shift: bool = False) -> None:
            inputs = []
            if shift:
                inputs.append(_vk_input(0xA0))
            inputs.append(_vk_input(vk))
            inputs.append(_vk_input(vk, key_up=True))
            if shift:
                inputs.append(_vk_input(0xA0, key_up=True))
            _send_inputs(inputs)

        def press(self, key) -> None:
            vk = self._vk(key)
            if vk is None:
                if isinstance(key, str) and len(key) == 1:
                    self.typewrite(key)
                return
            self._press_vk(vk)

        def keyDown(self, key) -> None:
            vk = self._vk(key)
            if vk is None:
                return
            _send_inputs([_vk_input(vk)])

        def keyUp(self, key) -> None:
            vk = self._vk(key)
            if vk is None:
                return
            _send_inputs([_vk_input(vk, key_up=True)])

        def typewrite(self, text, interval: float = 0.0) -> None:
            for ch in str(text):
                if ch in ("\n", "\r"):
                    self._press_vk(0x0D)
                elif ch == "\t":
                    self._press_vk(0x09)
                elif ch == "\b":
                    self._press_vk(0x08)
                else:
                    res = _user32.VkKeyScanW(ctypes.c_wchar(ch))
                    if res == -1:
                        _send_inputs(
                            [_unicode_input(ch), _unicode_input(ch, key_up=True)]
                        )
                    else:
                        vk = res & 0xFF
                        state = (res >> 8) & 0xFF
                        if state & 0x06:
                            # Char on this layout requires Ctrl or Alt — avoid
                            # those modifiers (could fire app shortcuts) and
                            # inject as Unicode instead.
                            _send_inputs(
                                [_unicode_input(ch), _unicode_input(ch, key_up=True)]
                            )
                        else:
                            self._press_vk(vk, shift=bool(state & 0x01))
                if interval > 0:
                    time.sleep(interval)

        def hotkey(self, *keys) -> None:
            vks = [self._vk(k) for k in keys]
            if any(v is None for v in vks):
                return
            inputs = [_vk_input(v) for v in vks]
            inputs += [_vk_input(v, key_up=True) for v in reversed(vks)]
            _send_inputs(inputs)

else:
    _WinScancodeBackend = None  # type: ignore[assignment]


class KeyboardShim:
    """Routes keyboard events to either pyautogui or the Windows scancode
    backend based on the user's Remote Desktop compatibility mode. On
    non-Windows platforms the scancode backend is None and every call
    transparently delegates to pyautogui."""

    MODE_OFF = "off"
    MODE_AUTO = "auto"
    MODE_ON = "on"

    def __init__(self) -> None:
        self.mode = self.MODE_AUTO
        self._sc = _WinScancodeBackend() if _WinScancodeBackend else None

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in (self.MODE_OFF, self.MODE_AUTO, self.MODE_ON) else self.MODE_OFF

    def scancode_available(self) -> bool:
        return self._sc is not None

    def _looks_like_remote_target(self) -> bool:
        try:
            title = (pyautogui.getActiveWindowTitle() or "").lower()
        except Exception:
            _log_caught('_looks_like_remote_target@L295')
            return False
        return any(h in title for h in _RDP_TITLE_HINTS)

    def _backend(self):
        if self._sc is None:
            return pyautogui
        if self.mode == self.MODE_ON:
            return self._sc
        if self.mode == self.MODE_AUTO and self._looks_like_remote_target():
            return self._sc
        return pyautogui

    def active_backend_name(self) -> str:
        return "scancode" if self._backend() is self._sc else "pyautogui"

    def press(self, key):
        return self._backend().press(key)

    def keyDown(self, key):
        return self._backend().keyDown(key)

    def keyUp(self, key):
        return self._backend().keyUp(key)

    def typewrite(self, text, interval: float = 0.0):
        return self._backend().typewrite(text, interval=interval)

    def hotkey(self, *keys):
        return self._backend().hotkey(*keys)


# Module-level singleton. The typing worker calls ``set_mode`` on this at the
# start of each run; one worker is active at a time so there's no race.
kbd = KeyboardShim()


__all__ = ["kbd", "KeyboardShim"]
