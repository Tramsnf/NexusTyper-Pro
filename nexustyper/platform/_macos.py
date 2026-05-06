"""macOS implementation of the Platform contract.

All AppKit / Quartz / objc imports are deferred to call time so this module
can be imported on Linux/Windows without raising. The module-level imports
below are limited to stdlib and ``pyautogui`` (already a hard dependency of
the app).
"""

from __future__ import annotations

import subprocess

from . import Platform
from nexustyper.constants import MACOS_ACCESSIBILITY_SETTINGS_URL


class MacOSPlatform(Platform):
    name = "macos"

    def accessibility_trusted(self, prompt: bool = False) -> bool:
        try:
            # Lazy import: ApplicationServices is only present on macOS.
            try:
                import Quartz  # type: ignore
            except Exception:
                # Framework unavailable — fail open.
                return True
            try:
                if prompt:
                    options = {Quartz.kAXTrustedCheckOptionPrompt: True}
                    return bool(Quartz.AXIsProcessTrustedWithOptions(options))
                return bool(Quartz.AXIsProcessTrusted())
            except Exception:
                # Probe failure: fail open so typing isn't blocked.
                return True
        except Exception:
            return True

    def open_privacy_settings(self) -> None:
        try:
            subprocess.Popen(["open", MACOS_ACCESSIBILITY_SETTINGS_URL])
        except Exception:
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
            pass
        # Fallback to pyautogui's window title.
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
            pyautogui.hotkey("command", "v")
        except Exception:
            pass

    def type_unicode_char(self, ch: str) -> bool:
        """Type one char via macOS Unicode Hex Input (Option+Hex).

        Requires the user to have enabled "Unicode Hex Input" in
        System Settings > Keyboard > Input Sources.
        """
        try:
            import pyautogui  # type: ignore
        except Exception:
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
            return False
