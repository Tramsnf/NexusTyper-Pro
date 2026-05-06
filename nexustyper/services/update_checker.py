"""nexustyper.services.update_checker — GitHub Releases update poller.

Runs in a worker thread so a slow network never blocks startup. Emits
``updateAvailable(version, url, body, asset_info)`` when the latest release
tag is a SemVer greater than the current version. Emits ``checkFailed(reason)``
on transport/parse errors so the UI can stay quiet rather than nagging the user.
Never raises into Qt.
"""

import os
import platform
import re

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from nexustyper.constants import (
    APP_NAME as _APP_NAME,
    APP_VERSION as _APP_VERSION,
    UPDATE_DOWNLOAD_PAGE as _UPDATE_DOWNLOAD_PAGE,
)


def _build_https_context():
    """Use certifi's bundled CA store for packaged update checks/downloads."""
    try:
        import ssl
        try:
            import certifi
            cafile = certifi.where()
            if cafile and os.path.exists(cafile):
                return ssl.create_default_context(cafile=cafile)
        except Exception:
            pass
        return ssl.create_default_context()
    except Exception:
        return None


class UpdateChecker(QObject):
    """Polls the GitHub Releases API for a newer version.

    Runs in a worker thread so a slow network never blocks startup. Emits
    `updateAvailable(version, url, body)` when the latest tag on the feed
    parses to a SemVer greater than ``current_version``. Emits
    `checkFailed(reason)` on transport/parse errors so the UI can stay quiet
    rather than nagging the user. Never raises into Qt.
    """

    # asset_info is a dict {url, name, size} for the OS installer when one is
    # attached to the release, or None if only portable archives / no assets
    # are available. UI uses it to decide whether to offer in-app download.
    updateAvailable = pyqtSignal(str, str, str, object)  # version, html_url, body, asset_info
    upToDate = pyqtSignal(str)
    checkFailed = pyqtSignal(str)

    def __init__(self, feed_url: str, current_version: str, parent=None):
        super().__init__(parent)
        self._feed_url = feed_url or ""
        self._current = current_version

    @staticmethod
    def _parse_semver(s: str):
        """Best-effort tuple from "v3.3", "3.3.1", "3.3-beta.2"; returns None
        if no leading numeric segment exists.
        """
        if not s:
            return None
        m = re.match(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", s.strip())
        if not m:
            return None
        return tuple(int(g or 0) for g in m.groups())

    @staticmethod
    def _pick_installer_asset(assets):
        """Return the asset dict matching the current OS's native installer,
        or None if the release only carries portable archives.

        Match order per platform mirrors the names produced by the release
        workflow (see .github/workflows/release.yml):
          macOS   → *-macOS.pkg
          Windows → *-Windows-Setup.exe
          Linux   → *_amd64.deb
        """
        if not assets:
            return None
        sysname = platform.system()
        # Map machine() to the .deb-style architecture string the release
        # workflow uses. Falls back to 'amd64' on unknown machines so the
        # default still picks up the standard Intel .deb.
        deb_arch = {
            "x86_64": "amd64", "amd64": "amd64",
            "aarch64": "arm64", "arm64": "arm64",
            "armv7l": "armhf",
        }.get(platform.machine().lower(), "amd64")
        for a in assets:
            name = (a.get("name") or "").lower()
            url = a.get("browser_download_url")
            if not url or not name:
                continue
            size = int(a.get("size") or 0)
            if sysname == "Darwin" and name.endswith(".pkg"):
                return {"url": url, "name": a["name"], "size": size}
            if sysname == "Windows" and name.endswith(".exe") and "setup" in name:
                return {"url": url, "name": a["name"], "size": size}
            if sysname == "Linux" and name.endswith(f"_{deb_arch}.deb"):
                return {"url": url, "name": a["name"], "size": size}
        return None

    @pyqtSlot()
    def run(self):
        if not self._feed_url:
            self.checkFailed.emit("Update feed not configured")
            return
        try:
            import urllib.request
            import json as _json
            req = urllib.request.Request(
                self._feed_url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"{_APP_NAME}/{_APP_VERSION} (+update-check)",
                },
            )
            with urllib.request.urlopen(req, timeout=8, context=_build_https_context()) as resp:
                payload = _json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as e:
            self.checkFailed.emit(f"Update check failed: {e}")
            return

        latest_tag = (payload.get("tag_name") or payload.get("name") or "").strip()
        download_url = (payload.get("html_url") or _UPDATE_DOWNLOAD_PAGE).strip()
        body = (payload.get("body") or "").strip()
        latest = self._parse_semver(latest_tag)
        current = self._parse_semver(self._current)
        if not latest or not current:
            self.checkFailed.emit(f"Could not parse versions ({latest_tag!r} vs {self._current!r})")
            return
        if latest > current:
            asset_info = self._pick_installer_asset(payload.get("assets") or [])
            self.updateAvailable.emit(latest_tag.lstrip("v"), download_url, body, asset_info)
        else:
            self.upToDate.emit(latest_tag.lstrip("v"))
