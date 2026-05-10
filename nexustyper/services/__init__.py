"""nexustyper.services — background service helpers.

Modules:
  update_checker        UpdateChecker (QObject) — polls GitHub Releases API
  installer_downloader  InstallerDownloader (QObject) — streams installer to disk
  hotkeys               translate_hotkey_for_pynput helper
  logging_setup         configured logger, _log_caught helper, install_global_handlers
"""

from nexustyper.services.update_checker import UpdateChecker
from nexustyper.services.installer_downloader import InstallerDownloader
from nexustyper.services.hotkeys import translate_hotkey_for_pynput
from nexustyper.services.logging_setup import (
    LOG_DIR,
    LOG_FILE,
    _log_caught,
    install_global_handlers,
    logger,
)

__all__ = [
    "UpdateChecker",
    "InstallerDownloader",
    "translate_hotkey_for_pynput",
    "logger",
    "LOG_DIR",
    "LOG_FILE",
    "_log_caught",
    "install_global_handlers",
]
