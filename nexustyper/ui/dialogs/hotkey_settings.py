"""Compatibility re-export of :class:`SettingsDialog` under the more specific
name ``HotkeySettingsDialog``.

The settings dialog in this app is purely a hotkey-preferences surface, so
some callers may prefer the descriptive name. New code should import from
``nexustyper.ui.dialogs.settings`` directly; this module exists so the package
layout matches the documented public API.
"""

from __future__ import annotations

from .settings import SettingsDialog as HotkeySettingsDialog

__all__ = ["HotkeySettingsDialog"]
