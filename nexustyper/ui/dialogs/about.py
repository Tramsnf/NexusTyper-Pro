"""About dialog for NexusTyper Pro.

Pure view: receives all branding strings (app name, version, author, copyright
year, signature, contact email/website) as keyword-only ``__init__`` arguments
so the script in ``NexusTyper Pro.py`` can pass its module-level constants
without this module importing them.
"""

from __future__ import annotations

import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)


def _resolve_ico2_path() -> str:
    """Locate ``ico2.png`` whether running from source or a PyInstaller bundle.

    PyInstaller's onefile mode unpacks data files under ``sys._MEIPASS``; in a
    dev checkout the file sits next to the script's CWD.
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "ico2.png")
    return "ico2.png"


class AboutDialog(QDialog):
    """Modal "About" window with logo, version line, contact info, OK button."""

    def __init__(
        self,
        *,
        app_name: str,
        app_version: str,
        app_author: str,
        contact_email: str,
        app_copyright_year: str = "",
        app_signature: str = "",
        contact_website: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {app_name}")
        # Use a minimum size, not a fixed one — Windows and high-DPI displays
        # render the same text wider than macOS, and setFixedSize was clipping
        # the rich-text body and the contact link.
        self.setMinimumSize(540, 320)

        main_layout = QHBoxLayout(self)

        self.image_label = QLabel()
        ico2_path = _resolve_ico2_path()
        if os.path.exists(ico2_path):
            pixmap = QPixmap(ico2_path)
        else:
            pixmap = QPixmap(128, 128)
            pixmap.fill(Qt.gray)
        self.image_label.setPixmap(
            pixmap.scaled(128, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self.image_label.setAlignment(Qt.AlignTop)
        main_layout.addWidget(self.image_label)

        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel(f"<b>{app_name}</b>"))
        right_layout.addWidget(QLabel(f"Version {app_version}"))
        if app_copyright_year:
            right_layout.addWidget(
                QLabel(f"Copyright © {app_copyright_year} {app_author}")
            )
        else:
            right_layout.addWidget(QLabel(f"Copyright © {app_author}"))

        if app_signature:
            sig = QLabel(f"<i>{app_signature}</i>")
            sig.setWordWrap(True)
            right_layout.addWidget(sig)

        # QLabel auto-sizes to its rich-text content. The previous QTextEdit
        # forced an internal scroll region that clipped the short body text.
        details = QLabel(
            f"Designed and Developed by <b>{app_author}</b>.<br><br>"
            f"For more information, contact:<br>"
            f"<a href='mailto:{contact_email}'>{contact_email}</a>"
        )
        details.setWordWrap(True)
        details.setOpenExternalLinks(True)
        details.setTextInteractionFlags(Qt.TextBrowserInteraction)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_button)

        right_layout.addWidget(details)
        if contact_website:
            link_label = QLabel(
                f"<a href='{contact_website}'>{contact_website}</a>"
            )
            link_label.setOpenExternalLinks(True)
            right_layout.addWidget(link_label, 0, Qt.AlignLeft)
        right_layout.addStretch()
        right_layout.addLayout(button_layout)
        main_layout.addLayout(right_layout)


__all__ = ["AboutDialog"]
