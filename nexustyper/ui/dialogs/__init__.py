"""Dialog windows for NexusTyper Pro.

Each dialog accepts the constants it needs (app name, version, log paths,
hotkey defaults) as keyword-only constructor parameters. This decouples the
view from the script's module-level globals so the dialogs can be reused or
unit-tested without dragging in the rest of the app.
"""

from .about import AboutDialog
from .help import HelpDialog
from .settings import SettingsDialog
from .hotkey_settings import HotkeySettingsDialog
from .diagnostics import DiagnosticsDialog

__all__ = [
    "AboutDialog",
    "HelpDialog",
    "SettingsDialog",
    "HotkeySettingsDialog",
    "DiagnosticsDialog",
]
