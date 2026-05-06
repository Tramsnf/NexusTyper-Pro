"""nexustyper.services.installer_downloader — release-asset downloader.

Streams the chosen release asset to disk in a worker thread. Emits
``progress(done_bytes, total_bytes)`` (total may be 0 if the server omits
Content-Length), ``finished(local_path)`` on a clean save, or
``failed(reason)`` on any error or user cancel. Writes to a ``.part`` file
and atomically renames on success so a half-downloaded file is never mistaken
for the real installer.
"""

import os

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from nexustyper.constants import APP_NAME as _APP_NAME, APP_VERSION as _APP_VERSION


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


class InstallerDownloader(QObject):
    """Streams the chosen release asset to disk in a worker thread.

    Emits `progress(done_bytes, total_bytes)` (total may be 0 if the server
    omits Content-Length), `finished(local_path)` on a clean save, or
    `failed(reason)` on any error or user cancel. Writes to a `.part` file
    and atomically renames on success so a half-downloaded file is never
    mistaken for the real installer.
    """

    progress = pyqtSignal(int, int)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, url: str, dest_path: str, parent=None):
        super().__init__(parent)
        self._url = url
        self._dest = dest_path
        self._cancel = False

    def cancel(self):
        self._cancel = True

    @pyqtSlot()
    def run(self):
        tmp = self._dest + ".part"
        try:
            import urllib.request
            req = urllib.request.Request(
                self._url,
                headers={
                    "User-Agent": f"{_APP_NAME}/{_APP_VERSION} (+update-download)",
                },
            )
            with urllib.request.urlopen(req, timeout=15, context=_build_https_context()) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                with open(tmp, "wb") as f:
                    while True:
                        if self._cancel:
                            try:
                                f.close()
                                os.remove(tmp)
                            except OSError:
                                pass
                            self.failed.emit("Download canceled")
                            return
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        self.progress.emit(done, total)
            os.replace(tmp, self._dest)
        except Exception as e:
            try:
                os.remove(tmp)
            except OSError:
                pass
            self.failed.emit(f"Download failed: {e}")
            return
        self.finished.emit(self._dest)
