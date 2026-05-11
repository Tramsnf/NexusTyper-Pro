"""macOS implementation of the Platform contract.

All AppKit / Quartz / objc imports are deferred to call time so this module
can be imported on Linux/Windows without raising. The module-level imports
below are limited to stdlib and ``pyautogui`` (already a hard dependency of
the app).
"""

from __future__ import annotations
from nexustyper.services.logging_setup import _log_caught

import subprocess

from . import Platform
from nexustyper.constants import MACOS_ACCESSIBILITY_SETTINGS_URL


class MacOSPlatform(Platform):
    name = "macos"

    def accessibility_trusted(self, prompt: bool = False) -> bool:
        # FAILS CLOSED on macOS. The previous behavior (fail open if Quartz
        # couldn't import or the AX probe raised) caused the worst possible
        # user experience: with Accessibility actually denied the bundled
        # .app would say "trusted", start the worker, and the OS would
        # silently drop every keystroke. Returning False instead routes the
        # caller through _show_macos_permissions_dialog so the user gets a
        # clear "grant Accessibility, then restart" message.
        try:
            import Quartz  # type: ignore
        except Exception:
            _log_caught("accessibility_trusted: Quartz unavailable", level="error")
            return False
        try:
            if prompt:
                options = {Quartz.kAXTrustedCheckOptionPrompt: True}
                return bool(Quartz.AXIsProcessTrustedWithOptions(options))
            return bool(Quartz.AXIsProcessTrusted())
        except Exception:
            _log_caught("accessibility_trusted: AX probe failed", level="error")
            return False

    def input_monitoring_trusted(self) -> "Optional[bool]":
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
        try:
            import Quartz  # type: ignore
        except Exception:
            _log_caught("input_monitoring_trusted: Quartz unavailable")
            return None
        # IOHIDCheckAccess(kIOHIDRequestTypeListenEvent=1) returns:
        #   0 = granted, 1 = denied, 2 = unknown.
        try:
            check = getattr(Quartz, "IOHIDCheckAccess", None)
            if check is None:
                return None
            status = int(check(1))
            if status == 0:
                return True
            if status == 1:
                return False
            return None
        except Exception:
            _log_caught("input_monitoring_trusted: IOHIDCheckAccess raised")
            return None

    def request_input_monitoring(self) -> None:
        """Pop the system Input Monitoring prompt for the running app.

        IOHIDRequestAccess shows the system dialog the *first* time it's
        called for a process; subsequent calls are no-ops. After the user
        clicks Allow / Deny in System Settings the app must restart for
        the new state to take effect (same per-process cache as AX).
        """
        try:
            import Quartz  # type: ignore
            req = getattr(Quartz, "IOHIDRequestAccess", None)
            if req is not None:
                req(1)
        except Exception:
            _log_caught("request_input_monitoring")

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
        title via the AX framework, using the same Accessibility permission
        the app already has for synthetic input (no new prompt). Falls back
        to pyautogui's AppleScript path if the AX read fails.
        """
        title = self._ax_focused_window_title()
        if title:
            return title
        try:
            import pyautogui  # type: ignore
            return pyautogui.getActiveWindowTitle() or ""
        except Exception:
            _log_caught('active_window_title')
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


