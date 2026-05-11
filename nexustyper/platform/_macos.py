"""macOS implementation of the Platform contract.

All AppKit / Quartz / objc imports are deferred to call time so this module
can be imported on Linux/Windows without raising. The module-level imports
below are limited to stdlib and ``pyautogui`` (already a hard dependency of
the app).
"""

from __future__ import annotations

import subprocess
from typing import Optional

from nexustyper.services.logging_setup import _log_caught

from . import Platform
from nexustyper.constants import MACOS_ACCESSIBILITY_SETTINGS_URL


# --- Direct framework symbol resolution via ctypes -----------------------
# The PyObjC `Quartz` / `ApplicationServices` modules don't reliably bridge
# `AXIsProcessTrusted` or `IOHIDCheckAccess` — depending on the PyObjC
# version they may be lazy-bound to nothing and raise AttributeError on
# first access. The frameworks themselves always exist on macOS, so we
# load them with ctypes and call the C symbols directly. This works in
# every Python install (system, venv, PyInstaller bundle) and across
# every PyObjC version.

def _macos_ax_trusted() -> Optional[bool]:
    """Return True/False per AXIsProcessTrusted; None if the framework
    can't be loaded at all (extremely unlikely on a real Mac)."""
    try:
        import ctypes
        appsvcs = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/"
            "ApplicationServices",
        )
        appsvcs.AXIsProcessTrusted.argtypes = []
        appsvcs.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(appsvcs.AXIsProcessTrusted())
    except Exception:
        _log_caught("_macos_ax_trusted: ctypes call failed", level="error")
        return None


# IOKit's IOHIDCheckAccess / IOHIDRequestAccess request types.
_K_IOHID_REQ_TYPE_POSTEVENT = 0  # AX-equivalent for posting events
_K_IOHID_REQ_TYPE_LISTENEVENT = 1  # what the hotkey listener needs


def _iokit():
    """Lazy-load /System/Library/Frameworks/IOKit.framework/IOKit and bind
    the two symbols we need. Cached on the module so repeated calls don't
    re-CDLL the framework."""
    cache = getattr(_iokit, "_cached", None)
    if cache is not None:
        return cache
    try:
        import ctypes
        iokit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
        iokit.IOHIDCheckAccess.argtypes = [ctypes.c_uint32]
        iokit.IOHIDCheckAccess.restype = ctypes.c_uint32
        iokit.IOHIDRequestAccess.argtypes = [ctypes.c_uint32]
        iokit.IOHIDRequestAccess.restype = ctypes.c_bool
        _iokit._cached = iokit  # type: ignore[attr-defined]
        return iokit
    except Exception:
        _log_caught("_iokit: load failed")
        _iokit._cached = False  # type: ignore[attr-defined]
        return None


def _macos_input_monitoring_status() -> Optional[bool]:
    """Return True/False/None per IOHIDCheckAccess(kIOHIDRequestTypeListenEvent).
    None means the framework symbol isn't available."""
    iokit = _iokit()
    if not iokit:
        return None
    try:
        status = int(iokit.IOHIDCheckAccess(_K_IOHID_REQ_TYPE_LISTENEVENT))
    except Exception:
        _log_caught("_macos_input_monitoring_status: probe raised")
        return None
    # kIOHIDAccessTypeGranted = 0, kIOHIDAccessTypeDenied = 1, kIOHIDAccessTypeUnknown = 2
    if status == 0:
        return True
    if status == 1:
        return False
    return None


def _macos_request_input_monitoring() -> None:
    iokit = _iokit()
    if not iokit:
        return
    try:
        iokit.IOHIDRequestAccess(_K_IOHID_REQ_TYPE_LISTENEVENT)
    except Exception:
        _log_caught("_macos_request_input_monitoring: req raised")


class MacOSPlatform(Platform):
    name = "macos"

    def accessibility_trusted(self, prompt: bool = False) -> bool:
        # FAILS CLOSED on macOS. The previous behavior (fail open if the
        # probe raised) caused the worst possible UX: with Accessibility
        # actually denied the .app would say "trusted", start the worker,
        # and the OS would silently drop every keystroke. Returning False
        # routes the caller through _show_macos_permissions_dialog so the
        # user gets an actionable message.
        #
        # The `prompt` parameter is accepted for backward compatibility but
        # ignored — AXIsProcessTrustedWithOptions(prompt=True) requires
        # constructing a CFDictionary (CoreFoundation), which is awkward
        # via ctypes and provides no UX benefit over our own dialog.
        result = _macos_ax_trusted()
        if result is None:
            _log_caught(
                "accessibility_trusted: framework unavailable, failing closed",
                level="error",
            )
            return False
        return result

    def input_monitoring_trusted(self) -> Optional[bool]:
        """Whether the app has macOS Input Monitoring permission.

        Distinct from Accessibility:
          * Accessibility (AX) is required for synthetic key INJECTION via
            CGEventPost — that's the typing path.
          * Input Monitoring is required for LISTENING to system-wide key
            events via Quartz event taps — that's how our pynput global
            hotkey listener works.
        On macOS Sequoia (15.x), Apple split these two clearly: granting
        Accessibility no longer implicitly grants Input Monitoring.

        Returns:
          True   - granted
          False  - explicitly denied
          None   - unknown / not yet asked / framework can't probe
        """
        return _macos_input_monitoring_status()

    def request_input_monitoring(self) -> None:
        """Pop the system Input Monitoring prompt for the running app.

        IOHIDRequestAccess shows the system dialog the first time it's
        called per process; subsequent calls are no-ops. After the user
        grants/denies, the app must restart for the new state to take
        effect (same per-process cache as AX).
        """
        _macos_request_input_monitoring()

    def open_privacy_settings(self) -> None:
        try:
            subprocess.Popen(["open", MACOS_ACCESSIBILITY_SETTINGS_URL])
        except Exception:
            _log_caught('open_privacy_settings@L42')
            pass

    def active_app_identity(self) -> str:
        # Prefer NSWorkspace's frontmost app name (stable across title churn).
        try:
            import AppKit  # type: ignore
            ws = AppKit.NSWorkspace.sharedWorkspace()
            app = ws.frontmostApplication()
            if app is not None:
                name = app.localizedName()
                if name:
                    return str(name)
        except Exception:
            _log_caught('active_app_identity@L55')
            pass
        # Fallback to pyautogui's window title.
        try:
            import pyautogui  # type: ignore
            return pyautogui.getActiveWindowTitle() or "Unknown"
        except Exception:
            _log_caught('active_app_identity@L61')
            return "Unknown"

    def active_window_title(self) -> str:
        """Return the focused window's title via the Accessibility API.

        :meth:`active_app_identity` returns just the app name on macOS
        ("Google Chrome") — same regardless of tab — so it can't drive
        per-tab focus locking. This method reads the actual focused-window
        title via the AX framework. Falls back to (1) pyautogui's window
        title if that version of pyautogui exposes one on macOS, then
        (2) the app's localized name — better to hand back a stable
        identifier than blow up.
        """
        title = self._ax_focused_window_title()
        if title:
            return title
        # pyautogui dropped getActiveWindowTitle on macOS in recent
        # versions; only call it if the attribute actually exists, so
        # the focus-lock poll loop doesn't fire AttributeError on every
        # iteration.
        try:
            import pyautogui  # type: ignore
            getter = getattr(pyautogui, "getActiveWindowTitle", None)
            if getter is not None:
                t = getter()
                if t:
                    return str(t)
        except Exception:
            _log_caught("active_window_title: pyautogui fallback")
        # Last resort: the frontmost app's name. Stable, always
        # available, won't change as titles mutate — better than ""
        # which would leave the focus-lock comparison perpetually
        # mismatched.
        try:
            return self.active_app_identity()
        except Exception:
            _log_caught("active_window_title: app-name fallback")
            return ""

    def _ax_focused_window_title(self) -> str:
        try:
            from ApplicationServices import (  # type: ignore
                AXUIElementCopyAttributeValue,
                AXUIElementCreateSystemWide,
            )
        except Exception:
            _log_caught('_ax_focused_window_title')
            return ""
        try:
            sys_elem = AXUIElementCreateSystemWide()
            err, focused_app = AXUIElementCopyAttributeValue(
                sys_elem, "AXFocusedApplication", None,
            )
            if err != 0 or focused_app is None:
                return ""
            err, focused_window = AXUIElementCopyAttributeValue(
                focused_app, "AXFocusedWindow", None,
            )
            if err != 0 or focused_window is None:
                return ""
            err, title = AXUIElementCopyAttributeValue(
                focused_window, "AXTitle", None,
            )
            if err != 0 or title is None:
                return ""
            return str(title)
        except Exception:
            _log_caught('_ax_focused_window_title')
            return ""

    def release_modifiers_best_effort(self) -> None:
        try:
            import pyautogui  # type: ignore
        except Exception:
            _log_caught('release_modifiers_best_effort@L67')
            return
        for key in ("shift", "ctrl", "alt", "command", "cmd", "option"):
            try:
                pyautogui.keyUp(key)
            except Exception:
                _log_caught('release_modifiers_best_effort@L72')
                pass

    def paste_via_keyboard_shortcut(self) -> None:
        try:
            import pyautogui  # type: ignore
            pyautogui.hotkey("command", "v")
        except Exception:
            _log_caught('paste_via_keyboard_shortcut@L79')
            pass

    def type_unicode_char(self, ch: str) -> bool:
        """Type one char via macOS Unicode Hex Input (Option+Hex).

        Requires the user to have enabled "Unicode Hex Input" in
        System Settings > Keyboard > Input Sources.
        """
        try:
            import pyautogui  # type: ignore
        except Exception:
            _log_caught('type_unicode_char@L90')
            return False
        try:
            cp = ord(ch)
            hexstr = f"{cp:04X}"
            pyautogui.keyDown("option")
            try:
                for d in hexstr:
                    pyautogui.typewrite(d.lower())
            finally:
                pyautogui.keyUp("option")
            return True
        except Exception:
            _log_caught('type_unicode_char@L102')
            return False


