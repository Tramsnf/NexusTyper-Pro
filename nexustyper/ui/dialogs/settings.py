"""Hotkey & global-hotkey-toggle preferences dialog.

This is the only "Settings" surface NexusTyper Pro currently exposes — it
edits the start/stop/resume hotkeys and the "enable global hotkeys" switch.
The original implementation reached into ``parent.settings`` to load and save;
this version takes the QSettings instance and the platform-specific default
hotkey strings as keyword-only ``__init__`` parameters so the dialog has no
hidden coupling to ``AutoTyperApp``.

All values are persisted in PortableText (Qt's portable, cross-platform key
sequence string format) so they round-trip across macOS/Windows/Linux and are
easy to translate for ``pynput``.
"""

from __future__ import annotations

import platform

from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QKeySequenceEdit,
    QVBoxLayout,
)


def _macos_major_version() -> int:
    """Return the macOS major version number, or 0 if not on macOS."""
    if platform.system() != "Darwin":
        return 0
    try:
        ver = platform.mac_ver()[0]
        return int(ver.split(".")[0]) if ver else 0
    except Exception:
        return 0


class SettingsDialog(QDialog):
    """Edit start/stop/resume hotkeys and the global-hotkeys enable toggle.

    The caller passes the QSettings instance (so the dialog doesn't need to
    know the org/app names) and the per-platform default hotkey strings (so
    this module doesn't need to import the script's constants).
    """

    def __init__(
        self,
        *,
        settings: QSettings,
        default_start_hotkey: str,
        default_stop_hotkey: str,
        default_resume_hotkey: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = settings
        self._default_start = default_start_hotkey
        self._default_stop = default_stop_hotkey
        self._default_resume = default_resume_hotkey

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.start_hotkey_edit = QKeySequenceEdit(self)
        self.stop_hotkey_edit = QKeySequenceEdit(self)
        self.resume_hotkey_edit = QKeySequenceEdit(self)
        form_layout.addRow("Start Typing Hotkey:", self.start_hotkey_edit)
        form_layout.addRow("Stop Typing Hotkey:", self.stop_hotkey_edit)
        form_layout.addRow("Resume Typing Hotkey:", self.resume_hotkey_edit)

        self.enable_hotkeys_checkbox = QCheckBox("Enable Global Hotkeys")
        # macOS 15 ships OS-level assertions that interfere with our pynput
        # listener; warn the user before they re-enable it.
        if _macos_major_version() >= 15:
            self.enable_hotkeys_checkbox.setToolTip(
                "Disabled by default on macOS 15 due to OS assertions. "
                "Use at your own risk."
            )
        form_layout.addRow(self.enable_hotkeys_checkbox)

        layout.addLayout(form_layout)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.load_settings()

    def load_settings(self) -> None:
        self.start_hotkey_edit.setKeySequence(
            QKeySequence(self.settings.value("startHotkey", self._default_start))
        )
        self.stop_hotkey_edit.setKeySequence(
            QKeySequence(self.settings.value("stopHotkey", self._default_stop))
        )
        self.resume_hotkey_edit.setKeySequence(
            QKeySequence(self.settings.value("resumeHotkey", self._default_resume))
        )
        # Default off on macOS 15+, on everywhere else.
        default_enable = _macos_major_version() < 15
        self.enable_hotkeys_checkbox.setChecked(
            self.settings.value("enableGlobalHotkeys", default_enable, type=bool)
        )

    def save_settings(self) -> None:
        # Store hotkeys in PortableText so they round-trip across platforms
        # and are easier to translate for pynput.
        self.settings.setValue(
            "startHotkey",
            self.start_hotkey_edit.keySequence().toString(QKeySequence.PortableText),
        )
        self.settings.setValue(
            "stopHotkey",
            self.stop_hotkey_edit.keySequence().toString(QKeySequence.PortableText),
        )
        self.settings.setValue(
            "resumeHotkey",
            self.resume_hotkey_edit.keySequence().toString(QKeySequence.PortableText),
        )
        self.settings.setValue(
            "enableGlobalHotkeys", self.enable_hotkeys_checkbox.isChecked()
        )
        self.accept()


__all__ = ["SettingsDialog"]
