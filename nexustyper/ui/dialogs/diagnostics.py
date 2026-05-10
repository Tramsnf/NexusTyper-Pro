"""Diagnostics dialog — shows environment info, opens log folder/file.

Replaces the original implementation which read from module-level globals
(``APP_NAME``, ``APP_VERSION``, ``LOG_FILE``, ``LOG_DIR``,
``macos_accessibility_trusted``). All of those are now keyword-only
constructor arguments so this module has no hidden coupling to the script.
"""

from __future__ import annotations
from nexustyper.services.logging_setup import _log_caught

import platform
from typing import Callable, Optional

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
)


class DiagnosticsDialog(QDialog):
    """Read-only "what version of everything am I running?" dialog.

    The macOS Accessibility row is appended only if a callable is supplied
    via ``accessibility_trusted_fn``. The callable should return a bool and
    is invoked once at populate-time with no arguments; pass
    ``functools.partial(macos_accessibility_trusted, prompt=False)`` if you
    want to suppress the system permission prompt.
    """

    def __init__(
        self,
        *,
        app_name: str,
        app_version: str,
        log_file: str,
        log_dir: str,
        accessibility_trusted_fn: Optional[Callable[[], bool]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Diagnostics")
        self.resize(640, 420)

        self._app_name = app_name
        self._app_version = app_version
        self._log_file = log_file
        self._log_dir = log_dir
        self._accessibility_trusted_fn = accessibility_trusted_fn

        layout = QVBoxLayout(self)
        self.info = QTextEdit(self)
        self.info.setReadOnly(True)
        layout.addWidget(self.info)

        btns = QHBoxLayout()
        self.copy_btn = QPushButton("Copy Info")
        self.open_logs_btn = QPushButton("Open Logs Folder")
        self.view_log_btn = QPushButton("View Log")
        self.close_btn = QPushButton("Close")
        btns.addWidget(self.copy_btn)
        btns.addWidget(self.open_logs_btn)
        btns.addWidget(self.view_log_btn)
        btns.addStretch()
        btns.addWidget(self.close_btn)
        layout.addLayout(btns)

        self.copy_btn.clicked.connect(self.copy_info)
        self.open_logs_btn.clicked.connect(self.open_logs)
        self.view_log_btn.clicked.connect(self.view_log)
        self.close_btn.clicked.connect(self.accept)

        self.populate()

    def populate(self) -> None:
        try:
            from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
            import pynput
            import pyautogui as pag
            from nexustyper.typing.keyboard import kbd

            lines = [
                f"App: {self._app_name} v{self._app_version}",
                f"OS: {platform.system()} {platform.release()} ({platform.machine()})",
                f"Python: {platform.python_version()}",
                f"Qt: {QT_VERSION_STR}",
                f"PyQt: {PYQT_VERSION_STR}",
                f"pynput: {getattr(pynput, '__version__', 'unknown')}",
                f"pyautogui: {getattr(pag, '__version__', 'unknown')}",
                (
                    f"Scancode keyboard backend: "
                    f"{'available' if kbd.scancode_available() else 'unavailable'} "
                    f"(mode={kbd.mode}, active={kbd.active_backend_name()})"
                ),
                f"Log file: {self._log_file}",
                f"Log dir: {self._log_dir}",
            ]
            if (
                platform.system() == "Darwin"
                and self._accessibility_trusted_fn is not None
            ):
                try:
                    trusted = bool(self._accessibility_trusted_fn())
                except Exception:
                    _log_caught('populate@L104')
                    trusted = False
                lines.append(f"macOS Accessibility trusted: {trusted}")
            self.info.setPlainText("\n".join(lines))
        except Exception as e:
            _log_caught('populate@L108')
            self.info.setPlainText(f"Failed to gather diagnostics: {e}")

    def copy_info(self) -> None:
        self.info.selectAll()
        self.info.copy()

    def open_logs(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._log_dir))

    def view_log(self) -> None:
        try:
            with open(self._log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            viewer = QDialog(self)
            viewer.setWindowTitle("Log Viewer")
            viewer.resize(700, 480)
            vlayout = QVBoxLayout(viewer)
            te = QTextEdit(viewer)
            te.setReadOnly(True)
            te.setPlainText(content)
            vlayout.addWidget(te)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(viewer.accept)
            vlayout.addWidget(close_btn)
            viewer.exec_()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not read log file:\n{e}")


__all__ = ["DiagnosticsDialog"]


