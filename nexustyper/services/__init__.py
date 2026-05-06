"""nexustyper.services — background service helpers.

Modules:
  update_checker        UpdateChecker (QObject) — polls GitHub Releases API
  installer_downloader  InstallerDownloader (QObject) — streams installer to disk
  hotkeys               translate_hotkey_for_pynput helper
"""

from nexustyper.services.update_checker import UpdateChecker
from nexustyper.services.installer_downloader import InstallerDownloader
from nexustyper.services.hotkeys import translate_hotkey_for_pynput

__all__ = [
    "UpdateChecker",
    "InstallerDownloader",
    "translate_hotkey_for_pynput",
]
