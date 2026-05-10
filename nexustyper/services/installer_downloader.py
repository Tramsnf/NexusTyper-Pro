"""nexustyper.services.installer_downloader — release-asset downloader.

Streams the chosen release asset to disk in a worker thread. Emits
``progress(done_bytes, total_bytes)`` (total may be 0 if the server omits
Content-Length), ``finished(local_path)`` on a clean save, or
``failed(reason)`` on any error or user cancel. Writes to a ``.part`` file
and atomically renames on success so a half-downloaded file is never mistaken
for the real installer.
"""
from nexustyper.services.logging_setup import _log_caught

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
            _log_caught('_build_https_context@L27')
            pass
        return ssl.create_default_context()
    except Exception:
        _log_caught('_build_https_context@L30')
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
            import urllib.error
            import urllib.request

            # Fast path #1: a previous run already finished this exact
            # installer. With the version stripped from asset filenames,
            # we can't trust "file exists" alone — the cached file might
            # be the previous release. Send a HEAD and compare the
            # server's Content-Length against the local file size. Skip
            # only on an exact byte-count match (same version, same build).
            try:
                if os.path.exists(self._dest) and os.path.getsize(self._dest) > 0:
                    local_sz = os.path.getsize(self._dest)
                    head_req = urllib.request.Request(
                        self._url,
                        method="HEAD",
                        headers={
                            "User-Agent": (
                                f"{_APP_NAME}/{_APP_VERSION} (+update-download)"
                            ),
                        },
                    )
                    try:
                        with urllib.request.urlopen(
                            head_req, timeout=10,
                            context=_build_https_context(),
                        ) as head_resp:
                            remote_sz = int(
                                head_resp.headers.get("Content-Length") or 0
                            )
                        if remote_sz > 0 and remote_sz == local_sz:
                            self.progress.emit(local_sz, local_sz)
                            self.finished.emit(self._dest)
                            return
                    except (urllib.error.URLError, urllib.error.HTTPError,
                            TimeoutError, OSError):
                        # HEAD failed (offline, server hiccup) — don't
                        # block the user with a stale cached file we
                        # can't verify, just fall through to a normal
                        # download which will hit its own error path if
                        # the network is truly out.
                        _log_caught("run: HEAD probe")
            except OSError:
                _log_caught("run: dest stat")

            # Fast path #2: a partial download is sitting in .part from a
            # prior interrupted run. Ask the server for a Range starting
            # where we left off so we don't redownload bytes we already
            # have. Server may ignore Range (returns 200) — in that case
            # we start fresh transparently.
            #
            # The sidecar .meta file records which URL the .part bytes
            # came from. Without it, a stale .part from an earlier
            # release could resume into a newer-release download and
            # produce a corrupted Frankenfile, because GitHub asset
            # filenames are reused across versions now (v3.7.4 and
            # v3.7.5 both ship a "NexusTyper-Pro-macOS.pkg").
            meta = tmp + ".meta"
            existing = 0
            try:
                if os.path.exists(tmp):
                    stored_url = ""
                    try:
                        with open(meta, "r", encoding="utf-8") as mf:
                            stored_url = mf.read().strip()
                    except OSError:
                        _log_caught("run: meta read")
                    if stored_url != self._url:
                        # Different URL → bytes belong to a different
                        # build. Wipe and start fresh.
                        try:
                            os.remove(tmp)
                        except OSError:
                            _log_caught("run: prune mismatched .part")
                        try:
                            os.remove(meta)
                        except OSError:
                            pass
                    else:
                        existing = os.path.getsize(tmp)
            except OSError:
                _log_caught("run: tmp stat")
                existing = 0

            headers = {
                "User-Agent": f"{_APP_NAME}/{_APP_VERSION} (+update-download)",
            }
            if existing > 0:
                headers["Range"] = f"bytes={existing}-"

            req = urllib.request.Request(self._url, headers=headers)
            try:
                resp = urllib.request.urlopen(
                    req, timeout=15, context=_build_https_context(),
                )
            except urllib.error.HTTPError as he:
                # 416: range past EOF (the .part is bigger than the
                # server's file — stale .part from a different build with
                # the same filename). Start fresh.
                if he.code == 416:
                    try:
                        os.remove(tmp)
                    except OSError:
                        _log_caught("run: prune stale .part")
                    existing = 0
                    fresh = urllib.request.Request(
                        self._url,
                        headers={
                            "User-Agent": (
                                f"{_APP_NAME}/{_APP_VERSION} (+update-download)"
                            ),
                        },
                    )
                    resp = urllib.request.urlopen(
                        fresh, timeout=15, context=_build_https_context(),
                    )
                else:
                    raise

            with resp:
                status = getattr(resp, "status", 200)
                if status == 206 and existing > 0:
                    # Server is honoring our resume.
                    # Content-Range: "bytes 1234-5678/9012" — total at end.
                    cr = resp.headers.get("Content-Range", "") or ""
                    try:
                        total = int(cr.rsplit("/", 1)[-1]) if "/" in cr else 0
                    except (TypeError, ValueError):
                        total = 0
                    mode = "ab"
                    done = existing
                else:
                    # Server ignored Range, OR we had nothing to resume.
                    total = int(resp.headers.get("Content-Length") or 0)
                    mode = "wb"
                    done = 0

                # Write the sidecar BEFORE we start writing bytes. If we
                # crash mid-download, the meta is already there to mark
                # which URL the partial belongs to.
                try:
                    with open(meta, "w", encoding="utf-8") as mf:
                        mf.write(self._url)
                except OSError:
                    _log_caught("run: meta write")

                with open(tmp, mode) as f:
                    while True:
                        if self._cancel:
                            # Keep the .part file: a future click can
                            # resume from here instead of redownloading.
                            self.failed.emit("Download canceled")
                            return
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        self.progress.emit(done, total)

            os.replace(tmp, self._dest)
            try:
                os.remove(meta)
            except OSError:
                pass
        except Exception as e:
            _log_caught("run")
            # Intentionally do NOT remove the .part file. A network blip
            # mid-download is exactly when resume is most valuable; the
            # next click sees the partial bytes and continues from there
            # via HTTP Range. The 416 path above handles the corrupt-stale
            # case.
            self.failed.emit(f"Download failed: {e}")
            return
        self.finished.emit(self._dest)


