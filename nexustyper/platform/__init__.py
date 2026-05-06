"""Platform abstraction layer for NexusTyper Pro.

This package isolates OS-specific behavior (accessibility checks, foreground
window identity, paste shortcuts, Unicode-Hex typing) behind a single
``Platform`` interface so the rest of the app can stay platform-agnostic.

Use :func:`current` to obtain the right implementation for the running OS.
Each implementation module compiles standalone on any OS — all OS-specific
imports (AppKit, Quartz, ctypes/wintypes, etc.) are deferred until call time.
"""

from __future__ import annotations

import platform as _platform


class Platform:
    """Base class describing the platform contract.

    Subclasses override the methods below. All public methods must be safe to
    call on any OS — they degrade silently rather than raising. See the
    docstrings on each method for the expected fall-back behavior.
    """

    name: str = "unknown"

    def accessibility_trusted(self, prompt: bool = False) -> bool:
        """Return True if the OS allows synthetic key injection.

        On Windows/Linux this is always True. On macOS it queries
        ``AXIsProcessTrustedWithOptions`` (when ``prompt=True``) or
        ``AXIsProcessTrusted`` (when ``prompt=False``). Fails open: if the
        probe itself raises, returns True so a flaky framework call can't
        block typing.
        """
        return True

    def open_privacy_settings(self) -> None:
        """Open the OS settings pane for accessibility, if any.

        macOS opens the Privacy_Accessibility pref pane. No-op on other OSes.
        """
        return None

    def active_app_identity(self) -> str:
        """Return a stable identifier for the frontmost app.

        Used for focus-lock comparison. Must NOT change as window titles
        mutate (e.g. "Untitled - Notepad" -> "*Untitled - Notepad").
        """
        return "Unknown"

    def release_modifiers_best_effort(self) -> None:
        """Best-effort release of stuck shift/ctrl/alt/cmd modifiers."""
        return None

    def paste_via_keyboard_shortcut(self) -> None:
        """Send the OS paste shortcut: Cmd-V on macOS, Ctrl-V elsewhere."""
        return None

    def type_unicode_char(self, ch: str) -> bool:
        """Type a single Unicode char via OS-specific Unicode input.

        macOS: implements Option+Hex via Unicode Hex Input. Returns True on
        success. Windows/Linux: returns False so the caller falls back to
        ASCII transliteration.
        """
        return False


def current() -> Platform:
    """Return the Platform implementation for the running OS."""
    sysname = _platform.system()
    if sysname == "Darwin":
        from . import _macos
        return _macos.MacOSPlatform()
    if sysname == "Windows":
        from . import _windows
        return _windows.WindowsPlatform()
    from . import _linux
    return _linux.LinuxPlatform()


__all__ = ["Platform", "current"]
