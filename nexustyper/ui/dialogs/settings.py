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
from nexustyper.services.logging_setup import _log_caught

import platform

from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QKeySequenceEdit, QVBoxLayout,
)


def _macos_major_version() -> int:
    """Return the macOS major version number, or 0 if not on macOS."""
    if platform.system() != "Darwin":
        return 0
    try:
        ver = platform.mac_ver()[0]
        return int(ver.split(".")[0]) if ver else 0
    except Exception:
        _log_caught('_macos_major_version@L34')
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

        # Remote Desktop / virtual desktop compatibility (Windows-only fix).
        # On Windows, normal keystroke injection doesn't reach apps inside
        # Chrome Remote Desktop, RDP, AnyDesk, TeamViewer, Parsec, etc. —
        # those clients require hardware-level keyboard events. The shim
        # routes keys through that lower-level path when this is on.
        self.rdp_mode_combo = QComboBox(self)
        self.rdp_mode_combo.addItem("Off", "off")
        self.rdp_mode_combo.addItem("Auto", "auto")
        self.rdp_mode_combo.addItem("Always on", "on")
        self.rdp_mode_combo.setToolTip(
            "Lets typing reach apps running inside Chrome Remote Desktop, RDP,\n"
            "AnyDesk, TeamViewer, Parsec, and similar remote-desktop clients.\n"
            "\n"
            "  Off       — never use the remote-desktop path.\n"
            "  Auto      — turn it on automatically when a remote-desktop\n"
            "              window is focused (recommended).\n"
            "  Always on — use the remote-desktop path everywhere.\n"
            "\n"
            "Windows only. macOS / Linux already work with remote desktops."
        )
        if platform.system() != "Windows":
            self.rdp_mode_combo.setEnabled(False)
            self.rdp_mode_combo.setToolTip(
                "Windows-only setting. Not needed on this platform."
            )
        form_layout.addRow("Remote Desktop typing:", self.rdp_mode_combo)

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

        # Remote Desktop compat: Auto on Windows, Off on macOS / Linux.
        rdp_default = "auto" if platform.system() == "Windows" else "off"
        rdp_mode = str(self.settings.value("rdpKeyboardMode", rdp_default))
        idx = self.rdp_mode_combo.findData(rdp_mode)
        self.rdp_mode_combo.setCurrentIndex(idx if idx >= 0 else 1)

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
        self.settings.setValue(
            "rdpKeyboardMode", self.rdp_mode_combo.currentData()
        )
        self.accept()


__all__ = ["SettingsDialog"]


