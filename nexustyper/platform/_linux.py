"""Linux implementation of the Platform contract.

Falls back to ``pyautogui`` for window-title introspection and key injection.
No OS-specific imports.
"""

from __future__ import annotations

from . import Platform


class LinuxPlatform(Platform):
    name = "linux"

    def accessibility_trusted(self, prompt: bool = False) -> bool:
        # Linux has no system-wide accessibility-prompt analog.
        return True

    def open_privacy_settings(self) -> None:
        return None

    def active_app_identity(self) -> str:
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
        # Caller falls back to ASCII transliteration.
        return False
