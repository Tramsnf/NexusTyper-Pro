import os
import sys
import atexit
import faulthandler

# faulthandler defaults to writing crash tracebacks to sys.stderr, which is
# None in a --windowed PyInstaller .exe on Windows (no console attached) and
# raises RuntimeError on enable(). Route it to a file under the app's log dir
# so packaged builds still capture native crashes.
_FAULTHANDLER_LOG = os.path.join(
    os.path.expanduser('~'), '.nexustyper_pro', 'logs', 'faulthandler.log',
)
try:
    os.makedirs(os.path.dirname(_FAULTHANDLER_LOG), exist_ok=True)
    _FAULTHANDLER_FILE = open(_FAULTHANDLER_LOG, 'a', buffering=1)
    faulthandler.enable(file=_FAULTHANDLER_FILE)
    # Close the handle on clean exit so Windows can rotate the log file.
    atexit.register(_FAULTHANDLER_FILE.close)
except OSError:
    _log_caught('module@L19')
    pass

import time
import re
import platform
import subprocess

from PyQt5.QtWidgets import (
    QApplication, QWidget, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QCheckBox, QSlider, QMessageBox, QProgressBar,
    QFileDialog, QAction, QMenuBar, QMenu, QDialog, QLineEdit,
    QComboBox, QInputDialog, QTabWidget,
    QRadioButton, QPlainTextEdit,
    QScrollArea, QToolButton, QStyle,
    QFrame, QProgressDialog,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QThread, QSettings, QUrl,
    QTimer, QSize, QEasingCurve, QVariantAnimation,
)
from PyQt5.QtGui import (
    QKeySequence, QPixmap, QIcon, QDesktopServices,
    QFontDatabase, QPainter, QColor, QPen, QPainterPath,
)
import json
import html

# --- Modular nexustyper package imports (refactor v3.6) -------------------
from nexustyper.constants import (
    APP_NAME, APP_VERSION, APP_AUTHOR, APP_COPYRIGHT_YEAR, APP_SIGNATURE,
    CONTACT_EMAIL, CONTACT_WEBSITE,
    UPDATE_FEED_URL, UPDATE_DOWNLOAD_PAGE,
    DEFAULT_MIN_WPM, DEFAULT_MAX_WPM, MIN_WPM_LIMIT, MAX_WPM_LIMIT,
    DEFAULT_LAPS, DEFAULT_DELAY, MISTAKE_CHANCE,
    MACOS_ACCESSIBILITY_SETTINGS_URL,
    MACOS_INPUT_MONITORING_SETTINGS_URL,
    DEFAULT_START_HOTKEY, DEFAULT_STOP_HOTKEY, DEFAULT_RESUME_HOTKEY,
)
from nexustyper.platform import current as _platform_current
from nexustyper.ui.theming import (
    DARK_STYLESHEET, LIGHT_STYLESHEET, ensure_qss_assets,
)
from nexustyper.ui.widgets.splitter import (
    ChevronSplitterHandle, ToggleSplitter as ChevronSplitter,
)
from nexustyper.ui.dialogs.about import AboutDialog
from nexustyper.ui.dialogs.help import HelpDialog
from nexustyper.ui.dialogs.settings import SettingsDialog
from nexustyper.ui.dialogs.diagnostics import DiagnosticsDialog
from nexustyper.typing import (
    sanitize_ai_text, apply_smart_newlines, KEY_ADJACENCY,
    TypingWorker,
)
from nexustyper.typing.content_detection import (
    categorize_title, detect_content_kind, contains_non_ascii,
    looks_like_code, looks_like_math,
)
from nexustyper.services.update_checker import UpdateChecker
from nexustyper.services.installer_downloader import InstallerDownloader
from nexustyper.services.hotkey_listener import HotkeyListener
from nexustyper.services.file_ingestion import (
    load_text_from_path as _fi_load,
    save_text_to_path as _fi_save,
    supported_open_filter,
    supported_save_filter,
    FileIngestionError,
)
from nexustyper.services.logging_setup import (
    LOG_DIR, LOG_FILE, _log_caught, install_global_handlers, logger,
)
from nexustyper.ui.widgets.text_edit import PasteCleaningTextEdit, CodeEditor
from nexustyper.ui.dialogs.dry_run import DryRunDialog
from nexustyper.ui.icons import make_lucide_icon


# Conditional import for platform-specific libraries
try:
    import pyautogui
    import pynput  # noqa: F401 — startup presence check; HotkeyListener does the real import
    import pyperclip  # noqa: F401 — startup presence check; nexustyper.typing.worker uses it
except ImportError as e:
    print(f"Error: A required library is missing (e.g., pyautogui, pynput, pyperclip). Please install it. {e}")
    sys.exit(1)

# --- Constants & App Info ---


# --- App Styling ---
# Polished theme stylesheets. Both themes share the same structure; only colors differ.
# Accent: cyan (primary), green (start), red (stop), amber (pause/warning).


# --- Logging Setup ---
# Logger, LOG_DIR, LOG_FILE, and the _log_caught helper are configured in
# nexustyper.services.logging_setup so all modules share one logger and one
# rotating file. Global hooks (sys.excepthook / threading.excepthook /
# qInstallMessageHandler) are installed below in the __main__ block, after
# QApplication is built but before the main window is shown.


# TypingWorker handles the typing automation in a separate thread


class AutoTyperApp(QWidget):
    start_typing_signal = pyqtSignal()
    stop_typing_signal = pyqtSignal()
    resume_typing_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._platform = _platform_current()
        self.settings = QSettings(APP_AUTHOR, APP_NAME)
        self.worker, self.thread = None, None
        self.is_paused = False
        self._suppress_input_mode_changed = False
        self._suppress_persona_changed = False
        self._last_input_tab_index = 0
        self.hotkey_listener: HotkeyListener | None = None
        self.init_ui()
        self.load_settings()
        self.start_listener()
        self.start_typing_signal.connect(self.start_typing)
        self.stop_typing_signal.connect(self.stop_typing)
        self.resume_typing_signal.connect(self.resume_typing)
        try:
            logger.info(f"App started v{APP_VERSION} on {platform.system()} {platform.release()} | Python {platform.python_version()}")
        except Exception:
            _log_caught('__init__@L145')
            pass

        # Defer the macOS Accessibility probe until after the main window
        # paints so the system permission prompt doesn't fight with the
        # splash, AND so any modal we show appears in front of an already-
        # visible app instead of behind a not-yet-shown one.
        # show_dialog=True so denial is loud (modal) instead of silent.
        try:
            QTimer.singleShot(
                400,
                lambda: self.check_macos_permissions(prompt=True, show_dialog=True),
            )
        except Exception:
            _log_caught("__init__: schedule permission check")
            self.check_macos_permissions(prompt=True, show_dialog=True)

        # Re-check on window-focus return so a user who granted permission
        # while switched away (in System Settings) sees the in-app warning
        # clear next time they refocus, instead of having to restart.
        try:
            QApplication.instance().applicationStateChanged.connect(
                self._on_app_state_changed,
            )
        except Exception:
            _log_caught("__init__: hook applicationStateChanged")

        # Launch check — bypasses the 1-hour throttle so a user opening
        # the app right now always gets a fresh answer to "is there an
        # update?". Without force=True, a user who relaunched 30 min after
        # closing wouldn't see a new release that dropped in between,
        # which is exactly the case people most expect to be told about.
        # Delayed a few seconds so we never block the first paint on a
        # slow network.
        try:
            QTimer.singleShot(
                2500,
                lambda: self._start_update_check(verbose=False, force=True),
            )
        except Exception:
            _log_caught('__init__@L155')
            pass

        # Periodic update poll while the app is open so a release published
        # while the user is mid-session shows up in the banner within an
        # hour without them having to click Help → Check for Updates.
        # The _start_update_check call itself honors a 1-hour throttle, so
        # firing every 30 minutes is safe — the second of two back-to-back
        # ticks will no-op.
        try:
            self._update_poll_timer = QTimer(self)
            self._update_poll_timer.setInterval(30 * 60 * 1000)  # 30 min
            self._update_poll_timer.timeout.connect(
                lambda: self._start_update_check(verbose=False)
            )
            self._update_poll_timer.start()
        except Exception:
            _log_caught("__init__: schedule update poll timer")

        # Cleanup pass: remove stale partial downloads and old installer
        # files from ~/Downloads so they don't accumulate or confuse the
        # downloader's cache logic. Runs once at startup, idempotent.
        try:
            QTimer.singleShot(1500, self._sweep_stale_downloads)
        except Exception:
            _log_caught("__init__: schedule download sweep")


    def _get_active_window_title_main(self):
        return self._platform.active_app_identity()

    def _get_active_window_identity_main(self):
        return self._platform.active_app_identity()

    def _categorize_title(self, title):
        return categorize_title(title)

    def _detect_content_kind(self, text: str) -> str:
        return detect_content_kind(text)

    def _contains_non_ascii(self, t: str) -> bool:
        return contains_non_ascii(t)

    def _looks_like_code(self, t: str) -> bool:
        return looks_like_code(t)

    def _looks_like_math(self, t: str) -> bool:
        return looks_like_math(t)

    def _open_macos_settings_url(self, url: str) -> None:
        try:
            if QDesktopServices.openUrl(QUrl(url)):
                return
        except Exception:
            _log_caught('_open_macos_settings_url: openUrl')
        try:
            subprocess.Popen(["open", url])
        except Exception:
            _log_caught('_open_macos_settings_url: open')

    def _open_macos_accessibility_settings(self):
        self._open_macos_settings_url(MACOS_ACCESSIBILITY_SETTINGS_URL)

    def _open_macos_input_monitoring_settings(self):
        self._open_macos_settings_url(MACOS_INPUT_MONITORING_SETTINGS_URL)

    def _running_bundle_identifier(self):
        """Return the running .app's CFBundleIdentifier, or None.

        Empty / None when run from a dev venv (no bundle wraps the
        Python process), in which case the tccutil reset path doesn't
        apply — we'd be resetting permission entries for whatever
        terminal launched us, not for ourselves.
        """
        try:
            from AppKit import NSBundle  # type: ignore
            bid = NSBundle.mainBundle().bundleIdentifier()
            if not bid:
                return None
            s = str(bid)
            # Trust only well-formed reverse-DNS strings — Python's own
            # bundle ID is "org.python.python" or similar, which we
            # don't want to reset accidentally.
            if not s.startswith("com.tramsnf."):
                return None
            return s
        except Exception:
            _log_caught("_running_bundle_identifier")
            return None

    def _reset_macos_tcc_for_self(self) -> bool:
        """Run `tccutil reset` for our bundle's Accessibility + Input
        Monitoring permissions. The OS deletes the existing trust entries,
        then asks the user fresh on the next call into either subsystem.

        This is the workaround for the "toggle is on in System Settings
        but the app still reads False" case, which happens when the
        bundle's signature has changed across releases (every ad-hoc
        signed build has a different signature, so TCC's stored trust
        record stops matching). Permanent fix is Developer-ID code
        signing every release with the same identity — see the workflow
        secrets in `.github/workflows/release.yml`.

        Returns True if we attempted the reset, False if we couldn't
        (no bundle ID — dev mode, where this path doesn't apply).
        """
        bid = self._running_bundle_identifier()
        if not bid:
            try:
                self.status_label.setText(
                    "Status: Reset only available in the installed .app "
                    "— in dev mode, restart your terminal/VS Code instead."
                )
            except Exception:
                _log_caught("_reset_macos_tcc_for_self: status set")
            return False
        ok_any = False
        for service in ("Accessibility", "ListenEvent"):
            try:
                subprocess.run(
                    ["tccutil", "reset", service, bid],
                    check=False,
                    capture_output=True,
                    timeout=10,
                )
                ok_any = True
            except Exception:
                _log_caught(f"_reset_macos_tcc_for_self: {service}")
        try:
            logger.info(f"tccutil reset Accessibility/ListenEvent for {bid}")
        except Exception:
            _log_caught("_reset_macos_tcc_for_self: log")
        return ok_any

    def _macos_permission_summary(self):
        """Return (ax_trusted, im_trusted, missing_list) for the dialog/banner.

        ``im_trusted`` is True / False / None per the three-state IOHID
        probe; we treat None as "assume granted" so we don't hassle users
        on builds where the framework can't introspect the state.
        """
        ax = self._platform.accessibility_trusted(prompt=False)
        im = self._platform.input_monitoring_trusted()
        missing = []
        if not ax:
            missing.append("Accessibility")
        if im is False:  # explicit denial only; None means "unknown"
            missing.append("Input Monitoring")
        return ax, im, missing

    def _show_macos_permissions_dialog(self, title, blocking=False):
        ax, im, missing = self._macos_permission_summary()

        # If the user just toggled the permission ON in Settings, macOS may
        # still cache the old "untrusted" state for this process. We surface
        # a Restart button regardless of detection so the user always has
        # an escape hatch.
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning if missing else QMessageBox.Information)
        msg.setWindowTitle(title)

        ax_mark = "✅" if ax else "❌"
        if im is True:
            im_mark = "✅"
        elif im is False:
            im_mark = "❌"
        else:
            im_mark = "❓"

        msg.setText(
            f"NexusTyper Pro needs two macOS permissions:\n\n"
            f"  {ax_mark}  Accessibility — required to type into other apps\n"
            f"  {im_mark}  Input Monitoring — required for global hotkeys\n"
        )

        info_lines = []
        if missing:
            info_lines.append(
                "Open Privacy & Security, enable NexusTyper Pro for the "
                "missing item(s), then click Restart below. If the app is "
                "already listed but the toggle looks on, toggle it OFF and "
                "back ON to force macOS to re-verify the binary."
            )
        else:
            info_lines.append(
                "Both permissions look granted. If typing still doesn't "
                "work, click Restart — macOS sometimes caches the previous "
                "untrusted state inside this process and needs a fresh "
                "launch to pick up the new state."
            )
        msg.setInformativeText("\n\n".join(info_lines))

        ax_btn = im_btn = reset_btn = None
        if not ax:
            ax_btn = msg.addButton("Open Accessibility settings", QMessageBox.ActionRole)
        if im is False:
            im_btn = msg.addButton("Open Input Monitoring settings", QMessageBox.ActionRole)
        # Reset trust state — bundle-scoped tccutil reset for the
        # AX + ListenEvent services. ONLY clears entries for THIS app
        # (com.tramsnf.nexustyperpro), never any other app you've granted.
        # Helps when System Settings shows the toggle ON but the app
        # still reads the permission as denied — typically caused by a
        # signature mismatch across releases for ad-hoc-signed builds.
        if self._running_bundle_identifier():
            reset_btn = msg.addButton(
                "Reset NexusTyper trust", QMessageBox.ActionRole,
            )
            reset_btn.setToolTip(
                "Removes only NexusTyper Pro's entries from the macOS "
                "Privacy lists, then reopens System Settings so you can "
                "re-grant. Other apps' permissions are not touched."
            )
        restart_btn = msg.addButton("Restart NexusTyper Pro", QMessageBox.AcceptRole)
        msg.addButton("Later", QMessageBox.RejectRole)
        msg.setDefaultButton(restart_btn)
        msg.exec_()

        clicked = msg.clickedButton()
        if ax_btn is not None and clicked is ax_btn:
            self._open_macos_accessibility_settings()
            try:
                self._platform.request_input_monitoring()
            except Exception:
                _log_caught("_show_macos_permissions_dialog: req IM")
        elif im_btn is not None and clicked is im_btn:
            try:
                self._platform.request_input_monitoring()
            except Exception:
                _log_caught("_show_macos_permissions_dialog: req IM")
            self._open_macos_input_monitoring_settings()
        elif reset_btn is not None and clicked is reset_btn:
            # Bundle-scoped reset: only NexusTyper's entries are removed.
            # Then guide the user back through grant + restart.
            self._reset_macos_tcc_for_self()
            follow = QMessageBox(self)
            follow.setIcon(QMessageBox.Information)
            follow.setWindowTitle("Trust state reset")
            follow.setText(
                "Cleared NexusTyper Pro's macOS permission entries.\n"
                "Re-grant in the panel that just opened, then click Restart."
            )
            follow.setInformativeText(
                "Only NexusTyper Pro was reset — every other app you've "
                "granted Accessibility / Input Monitoring to is untouched."
            )
            settings_btn = follow.addButton(
                "Open Privacy & Security", QMessageBox.AcceptRole,
            )
            follow.addButton("Later", QMessageBox.RejectRole)
            follow.exec_()
            if follow.clickedButton() is settings_btn:
                self._open_macos_accessibility_settings()
        elif clicked is restart_btn:
            self._restart_app()

        if blocking and missing:
            try:
                self.status_label.setText(
                    f"Status: macOS permission required: {', '.join(missing)}."
                )
            except Exception:
                _log_caught('_show_macos_permissions_dialog: status set')

    def check_macos_permissions(self, prompt=False, show_dialog=True):
        if self._platform.name != "macos":
            return True
        ax = self._platform.accessibility_trusted(prompt=prompt)
        im = self._platform.input_monitoring_trusted()
        # We require Accessibility (typing). Input Monitoring is required
        # for the global hotkey listener; we treat IM == None ("unknown")
        # as "assume granted" so unbuilt-against-IOKit installations don't
        # nag the user about something we can't actually verify.
        ok = bool(ax) and (im is not False)

        # Auto-recover from TCC signature mismatch after an upgrade. If
        # the previous session's app version is different from the current
        # one AND we previously had trust AND we don't anymore, the
        # overwhelming likelihood is that macOS revoked trust because the
        # new build's binary signature doesn't match the stored TCC entry
        # (every ad-hoc-signed release has a different signature). We
        # bundle-scoped reset and notify the user — saves them clicking
        # "Reset NexusTyper trust" by hand.
        if not ok and not getattr(self, "_auto_reset_done_this_session", False):
            self._maybe_auto_reset_after_upgrade(ax, im)

        # Only log when the *combined* state changes, otherwise focus-driven
        # re-checks would spam the log every time the user Cmd-Tabs back.
        if getattr(self, "_last_trust_state", None) != ok:
            try:
                logger.info(
                    f"macOS permissions: AX={ax} InputMonitoring={im} ok={ok}"
                )
            except Exception:
                _log_caught("check_macos_permissions: log trust state")
            self._last_trust_state = ok

        # Persist the *good* state so the next launch can detect a regression.
        # Don't persist after an auto-reset run (the False values would mask
        # the next session's recovery signal).
        if not getattr(self, "_auto_reset_done_this_session", False):
            try:
                self.settings.setValue("macosLastSeenAppVersion", APP_VERSION)
                self.settings.setValue("macosLastAxTrusted", bool(ax))
                self.settings.setValue("macosLastImTrusted", im is True)
            except Exception:
                _log_caught("check_macos_permissions: persist trust state")

        self._update_permission_status(ok, ax=ax, im=im)
        if not ok and show_dialog:
            self._show_macos_permissions_dialog("macOS permission required")
        return ok

    def _maybe_auto_reset_after_upgrade(self, ax: bool, im) -> None:
        """Auto-reset bundle-scoped TCC if the app was just upgraded and
        previously-granted permissions look revoked. Targeted enough to
        avoid false positives:

          * Only fires when the running bundle has a real CFBundleIdentifier
            (so dev mode never triggers — we'd be resetting whatever
            launched python).
          * Only fires when the persisted "last seen app version" differs
            from APP_VERSION — a user who genuinely revoked permission
            on the *same* version is left alone.
          * Only fires when at least one of the two permissions was
            previously True — a fresh install where the user hasn't yet
            granted anything is left alone.
          * Only fires once per session (`_auto_reset_done_this_session`
            guard) so we don't loop on the next focus-return check.
        """
        bid = self._running_bundle_identifier()
        if not bid:
            return
        try:
            last_version = str(self.settings.value("macosLastSeenAppVersion", "") or "")
            last_ax = bool(self.settings.value("macosLastAxTrusted", False, type=bool))
            last_im = bool(self.settings.value("macosLastImTrusted", False, type=bool))
        except Exception:
            _log_caught("_maybe_auto_reset_after_upgrade: read settings")
            return

        # Need a recorded prior version to know this is an upgrade.
        if not last_version or last_version == APP_VERSION:
            return
        # Need at least one prior True so we know there's a stale entry to
        # reset. Without that, the user may simply have not granted yet.
        if not (last_ax or last_im):
            return
        # Need an actual regression now.
        ax_regressed = (last_ax and not ax)
        im_regressed = (last_im and im is False)
        if not (ax_regressed or im_regressed):
            return

        try:
            logger.info(
                f"Auto-resetting macOS TCC after upgrade {last_version} → "
                f"{APP_VERSION} (last trusted AX={last_ax} IM={last_im}, "
                f"now AX={ax} IM={im})"
            )
        except Exception:
            _log_caught("_maybe_auto_reset_after_upgrade: log")

        self._auto_reset_done_this_session = True
        if not self._reset_macos_tcc_for_self():
            return

        # Best-effort prompt the user to re-grant. Non-blocking via QTimer
        # so we don't fight the existing in-flight permission dialog or
        # the launch flow.
        try:
            QTimer.singleShot(800, self._notify_after_auto_reset)
        except Exception:
            _log_caught("_maybe_auto_reset_after_upgrade: schedule notify")

    def _notify_after_auto_reset(self) -> None:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Permissions refreshed after upgrade")
        msg.setText(
            "macOS lost trust in NexusTyper Pro after the version upgrade "
            "(common for unsigned / ad-hoc-signed builds — the new binary's "
            "signature doesn't match the trust record from the previous "
            "version)."
        )
        msg.setInformativeText(
            "Cleared NexusTyper Pro's macOS permission entries automatically. "
            "Re-grant Accessibility (and Input Monitoring if you use global "
            "hotkeys) in System Settings, then click Restart.\n\n"
            "Other apps' permissions were not touched."
        )
        ax_btn = msg.addButton("Open Accessibility settings", QMessageBox.ActionRole)
        im_btn = msg.addButton("Open Input Monitoring settings", QMessageBox.ActionRole)
        restart_btn = msg.addButton("Restart NexusTyper Pro", QMessageBox.AcceptRole)
        msg.addButton("Later", QMessageBox.RejectRole)
        msg.setDefaultButton(restart_btn)
        msg.exec_()
        clicked = msg.clickedButton()
        if clicked is ax_btn:
            self._open_macos_accessibility_settings()
        elif clicked is im_btn:
            try:
                self._platform.request_input_monitoring()
            except Exception:
                _log_caught("_notify_after_auto_reset: req IM")
            self._open_macos_input_monitoring_settings()
        elif clicked is restart_btn:
            self._restart_app()

    def _update_permission_status(self, ok: bool, ax=None, im=None) -> None:
        if self._platform.name != "macos":
            return
        try:
            label = getattr(self, "status_label", None)
            if label is None:
                return
            current = label.text() or ""
            if ok:
                # Clear our previous warning if it's still showing; don't
                # stomp on an unrelated status the worker may have set.
                if "macOS permission" in current or "Accessibility" in current:
                    label.setText("Status: Ready.")
                return
            missing = []
            if ax is False:
                missing.append("Accessibility")
            if im is False:
                missing.append("Input Monitoring")
            if not missing:
                missing.append("Accessibility")
            label.setText(
                "Status: ⚠ macOS permission required — "
                f"{' + '.join(missing)}. Click Help → Diagnostics for "
                "details, or grant in System Settings → Privacy & "
                "Security and restart the app."
            )
        except Exception:
            _log_caught("_update_permission_status")

    def _on_app_state_changed(self, state) -> None:
        """Re-check permissions when the user switches back to the app.

        macOS caches the Accessibility trust per-process for some calls,
        but the AX probe itself returns fresh data — so a user who granted
        permission in System Settings and then refocused the app will see
        the warning clear. If the trust state flips from False to True
        we also offer to restart the app, because synthetic-input APIs
        (CGEventPost / pyautogui's underlying calls) can keep using the
        cached "untrusted" state for the lifetime of this process even
        after AXIsProcessTrusted starts returning True. A restart
        guarantees every API picks up the new permission.
        """
        try:
            if int(state) != int(Qt.ApplicationActive):
                return
            # Also opportunistically check for a new release on every
            # refocus. The throttle inside _start_update_check guarantees
            # we won't spam GitHub (max once per hour); on the other
            # hand a user who Cmd-Tabs back after lunch immediately sees
            # any release published while they were away.
            try:
                self._start_update_check(verbose=False)
            except Exception:
                _log_caught("_on_app_state_changed: update check")
            prev = getattr(self, "_last_trust_state", None)
            trusted = self.check_macos_permissions(prompt=False, show_dialog=False)
            if prev is False and trusted is True:
                # Don't pile up restart prompts if the user refocuses
                # several times before deciding.
                if getattr(self, "_restart_prompt_open", False):
                    return
                self._restart_prompt_open = True
                try:
                    self._prompt_restart_after_permission_grant()
                finally:
                    self._restart_prompt_open = False
        except Exception:
            _log_caught("_on_app_state_changed")

    def _prompt_restart_after_permission_grant(self) -> None:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Accessibility granted")
        msg.setText("Restart NexusTyper Pro to apply the new permission.")
        msg.setInformativeText(
            "macOS caches the permission state per process, so a quick "
            "restart guarantees typing works correctly. Your settings "
            "are preserved across the restart."
        )
        restart_btn = msg.addButton("Restart now", QMessageBox.AcceptRole)
        msg.addButton("Later", QMessageBox.RejectRole)
        msg.setDefaultButton(restart_btn)
        msg.exec_()
        if msg.clickedButton() is restart_btn:
            self._restart_app()

    def _restart_app(self) -> None:
        """Quit and relaunch the app.

        On macOS the running process is inside a .app bundle whose path
        is reachable by walking up from ``sys.executable``. ``open -n``
        starts a fresh instance even though the current one is still
        tearing down — the new instance is the one that sees the
        refreshed Accessibility trust state. Outside a bundle (dev
        mode), ``os.execv`` re-runs the current Python invocation in
        place; dev runs inherit permission from the launching terminal
        so the restart there isn't strictly necessary but keeps the
        UX consistent.
        """
        try:
            self.save_settings()
        except Exception:
            _log_caught("_restart_app: save_settings")
        try:
            self.stop_listener()
        except Exception:
            _log_caught("_restart_app: stop_listener")
        try:
            self.stop_typing()
        except Exception:
            _log_caught("_restart_app: stop_typing")

        try:
            if self._platform.name == "macos":
                # In a PyInstaller --windowed bundle the executable lives at
                #   /Applications/NexusTyper Pro.app/Contents/MacOS/NexusTyper Pro
                # so the .app dir is 3 levels up. Walk up cautiously.
                candidate = os.path.abspath(sys.executable)
                app_path = None
                for _ in range(5):
                    candidate = os.path.dirname(candidate)
                    if candidate.endswith(".app"):
                        app_path = candidate
                        break
                if app_path:
                    subprocess.Popen(["open", "-n", app_path])
                else:
                    # Dev run: re-exec the current Python invocation.
                    os.execv(sys.executable, [sys.executable, *sys.argv])
            else:
                os.execv(sys.executable, [sys.executable, *sys.argv])
        except Exception:
            _log_caught("_restart_app: launch new instance")
            return

        try:
            QApplication.instance().quit()
        except Exception:
            _log_caught("_restart_app: quit")

    def _ensure_macos_typing_permissions(self):
        if self._platform.name != "macos":
            return True
        if self.check_macos_permissions(prompt=True, show_dialog=False):
            return True
        self._show_macos_permissions_dialog("Typing blocked", blocking=True)
        return False

    def apply_macos_float_behavior(self, checked):
        """No-op; using Qt WindowStaysOnTopHint for cross-platform stability."""
        return

    def init_ui(self):
        self.setWindowTitle(f"{APP_NAME} - v{APP_VERSION}")
        if hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, 'icon.icns')
        else:
            icon_path = 'icon.icns'
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.menu_bar = QMenuBar(self)
        file_menu = self.menu_bar.addMenu('&File')
        format_menu = self.menu_bar.addMenu('F&ormat')
        profiles_menu = self.menu_bar.addMenu('&Profiles')
        view_menu = self.menu_bar.addMenu('&View')
        help_menu = self.menu_bar.addMenu('&Help')

        # Create and add the help action
        show_help_action = QAction('&View Help Guide', self)
        show_help_action.triggered.connect(self.show_help_dialog)
        help_menu.addAction(show_help_action)
        diagnostics_action = QAction('&Diagnostics...', self)
        diagnostics_action.triggered.connect(self.show_diagnostics_dialog)
        help_menu.addAction(diagnostics_action)
        check_update_action = QAction('Check for &Updates…', self)
        check_update_action.triggered.connect(lambda: self._start_update_check(verbose=True))
        help_menu.addAction(check_update_action)
        
        open_action = QAction('&Open...', self)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        save_action = QAction('&Save As...', self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        settings_action = QAction('&Settings...', self)
        settings_action.triggered.connect(self.show_settings_dialog)
        try:
            settings_action.setShortcut(QKeySequence.Preferences)
        except Exception:
            _log_caught('init_ui@L273')
            pass
        file_menu.addAction(settings_action)
        about_action = QAction('&About...', self)
        about_action.triggered.connect(self.show_about_dialog)
        file_menu.addAction(about_action)
        file_menu.addSeparator()
        exit_action = QAction('&Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        clean_action = QAction('Clean Whitespace', self)
        clean_action.triggered.connect(self.clean_whitespace)
        format_menu.addAction(clean_action)
        decode_entities_action = QAction('Decode HTML Entities', self)
        decode_entities_action.triggered.connect(self.decode_html_entities)
        format_menu.addAction(decode_entities_action)
        fix_ai_action = QAction('Fix AI Paste Artifacts', self)
        fix_ai_action.triggered.connect(self.fix_ai_paste_artifacts)
        format_menu.addAction(fix_ai_action)
        format_menu.addSeparator()
        upper_action = QAction('UPPERCASE', self)
        upper_action.triggered.connect(self.to_uppercase)
        format_menu.addAction(upper_action)
        lower_action = QAction('lowercase', self)
        lower_action.triggered.connect(self.to_lowercase)
        format_menu.addAction(lower_action)
        sentence_action = QAction('Sentence case', self)
        sentence_action.triggered.connect(self.to_sentence_case)
        format_menu.addAction(sentence_action)

        save_profile_action = QAction('Save Profile...', self)
        save_profile_action.triggered.connect(self.save_profile)
        profiles_menu.addAction(save_profile_action)
        delete_profile_action = QAction('Delete Profile...', self)
        delete_profile_action.triggered.connect(self.delete_profile_prompt)
        profiles_menu.addAction(delete_profile_action)
        export_profiles_action = QAction('Export Profiles...', self)
        export_profiles_action.triggered.connect(self.export_profiles)
        profiles_menu.addAction(export_profiles_action)
        import_profiles_action = QAction('Import Profiles...', self)
        import_profiles_action.triggered.connect(self.import_profiles)
        profiles_menu.addAction(import_profiles_action)
        self.load_profile_menu = profiles_menu.addMenu('Load Profile')
        self.populate_profiles_menu()

        self.dark_mode_action = QAction('Dark Mode', self, checkable=True)
        self.dark_mode_action.triggered.connect(self.toggle_dark_mode)
        view_menu.addAction(self.dark_mode_action)
        view_menu.addSeparator()
        self.toggle_sidebar_action = QAction('Hide Sidebar', self, checkable=True)
        try:
            self.toggle_sidebar_action.setShortcut(QKeySequence("Ctrl+\\"))
        except Exception:
            _log_caught('init_ui@L326')
            pass
        self.toggle_sidebar_action.triggered.connect(self._toggle_sidebar)
        view_menu.addAction(self.toggle_sidebar_action)
        view_menu.addSeparator()
        self.always_on_top_action = QAction('Always on Top', self, checkable=True)
        self.always_on_top_action.triggered.connect(self.toggle_always_on_top)
        view_menu.addAction(self.always_on_top_action)
        dry_run_action = QAction('Dry Run Preview...', self)
        dry_run_action.triggered.connect(self.show_dry_run_preview)
        view_menu.addAction(dry_run_action)

        # Shortcuts + icons for common actions
        try:
            open_action.setShortcut(QKeySequence.Open)
            save_action.setShortcut(QKeySequence.SaveAs)
            exit_action.setShortcut(QKeySequence.Quit)
            open_action.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
            save_action.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        except Exception:
            _log_caught('init_ui@L345')
            pass

        main_layout = QVBoxLayout(self)
        main_layout.setMenuBar(self.menu_bar)
        try:
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)
        except Exception:
            _log_caught('init_ui@L353')
            pass
        try:
            self.setMinimumSize(980, 640)
            self.resize(1240, 780)
        except Exception:
            _log_caught('init_ui@L358')
            pass

        # --- Masthead: wordmark + persona pill + global hotkey hint ---
        masthead = QFrame(self)
        masthead.setObjectName("masthead")
        mast_layout = QHBoxLayout(masthead)
        mast_layout.setContentsMargins(16, 10, 16, 10)
        mast_layout.setSpacing(12)

        wordmark_wrap = QWidget(masthead)
        wordmark_layout = QHBoxLayout(wordmark_wrap)
        wordmark_layout.setContentsMargins(0, 0, 0, 0)
        wordmark_layout.setSpacing(8)
        self.wordmark_logo = QLabel(masthead)
        self.wordmark_logo.setObjectName("wordmarkLogo")
        self.wordmark_logo.setFixedSize(22, 22)
        self.wordmark_logo.setPixmap(self._build_wordmark_logo(22))
        wordmark_layout.addWidget(self.wordmark_logo)
        self.wordmark_label = QLabel(APP_NAME, masthead)
        self.wordmark_label.setObjectName("wordmark")
        wordmark_layout.addWidget(self.wordmark_label)
        version_label = QLabel(f"v{APP_VERSION}", masthead)
        version_label.setObjectName("wordmarkVersion")
        wordmark_layout.addWidget(version_label)
        mast_layout.addWidget(wordmark_wrap)
        mast_layout.addStretch(1)

        persona_label = QLabel("Persona", masthead)
        persona_label.setObjectName("personaLabel")
        mast_layout.addWidget(persona_label)
        self.masthead_persona = QComboBox(masthead)
        self.masthead_persona.setObjectName("personaPill")
        self.masthead_persona.addItems([
            "Custom (Manual Settings)",
            "Deliberate Writer",
            "Fast Messenger",
            "Careful Coder",
        ])
        self.masthead_persona.setMinimumWidth(180)
        mast_layout.addWidget(self.masthead_persona)

        self.hotkey_hint_label = QLabel("", masthead)
        self.hotkey_hint_label.setObjectName("hotkeyHint")
        mast_layout.addSpacing(12)
        mast_layout.addWidget(self.hotkey_hint_label)

        main_layout.addWidget(masthead)

        masthead_divider = QFrame(self)
        masthead_divider.setObjectName("mastheadDivider")
        masthead_divider.setFrameShape(QFrame.HLine)
        masthead_divider.setFixedHeight(1)
        main_layout.addWidget(masthead_divider)

        # Update-available banner. Hidden by default; revealed by
        # _show_update_banner when the background check finds a newer
        # release. Sits directly under the masthead so it's the first
        # thing the user sees on next launch, without overlaying any
        # work-in-progress dialogs.
        self._build_update_banner(main_layout)

        body_wrap = QWidget(self)
        body_layout = QVBoxLayout(body_wrap)
        body_layout.setContentsMargins(12, 10, 12, 12)
        body_layout.setSpacing(8)
        main_layout.addWidget(body_wrap, 1)

        # --- Split layout: settings (left) + editor/run (right) ---
        self.splitter = ChevronSplitter(Qt.Horizontal, self)
        self.splitter.toggleRequested.connect(
            lambda: self._toggle_sidebar(self.splitter.sizes()[0] > 1)
        )
        body_layout.addWidget(self.splitter, 1)

        # Left: scrollable settings
        self.settings_scroll = QScrollArea(self)
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QFrame.NoFrame)
        try:
            self.settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.settings_scroll.setMinimumWidth(260)
        except Exception:
            _log_caught('init_ui@L433')
            pass
        settings_container = QWidget(self.settings_scroll)
        self.settings_scroll.setWidget(settings_container)
        settings_container_layout = QVBoxLayout(settings_container)
        settings_container_layout.setContentsMargins(2, 2, 2, 2)
        settings_container_layout.setSpacing(0)

        # Sidebar is a single scrollable column of clearly-titled sections —
        # no nested QGroupBoxes, no Setup/Safety tabs (Safety only had two
        # checkboxes which now sit at the bottom of this list).
        self.settings_panel = QWidget(self)
        settings_panel_layout = QVBoxLayout(self.settings_panel)
        settings_panel_layout.setContentsMargins(14, 10, 14, 10)
        settings_panel_layout.setSpacing(10)
        settings_container_layout.addWidget(self.settings_panel, 1)
        self.splitter.addWidget(self.settings_scroll)
        # Back-compat: code paths refer to settings_tabs.setEnabled(...). Point
        # the alias at the same panel so those paths still work.
        self.settings_tabs = self.settings_panel

        def _section(title):
            head = QLabel(title.upper())
            head.setObjectName("sectionHeader")
            settings_panel_layout.addWidget(head)
            rule = QFrame()
            rule.setObjectName("sectionRule")
            rule.setFrameShape(QFrame.HLine)
            rule.setFixedHeight(1)
            settings_panel_layout.addWidget(rule)
            body = QWidget()
            body_lay = QVBoxLayout(body)
            body_lay.setContentsMargins(0, 4, 0, 0)
            body_lay.setSpacing(6)
            settings_panel_layout.addWidget(body)
            return body, body_lay

        # ---- Pacing ----
        pacing_body, pacing_lay = _section("Pacing")
        pacing_row = QHBoxLayout()
        pacing_row.setSpacing(10)
        self.laps_spin = QSpinBox()
        self.laps_spin.setRange(1, 1000)
        self.laps_spin.setValue(DEFAULT_LAPS)
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 60)
        self.delay_spin.setValue(DEFAULT_DELAY)
        for spin in (self.laps_spin, self.delay_spin):
            spin.setMinimumWidth(56)
            spin.setMaximumWidth(80)
        laps_lbl = QLabel("Laps")
        laps_lbl.setObjectName("fieldLabel")
        delay_lbl = QLabel("Delay (s)")
        delay_lbl.setObjectName("fieldLabel")
        pacing_row.addWidget(laps_lbl)
        pacing_row.addWidget(self.laps_spin, 1)
        pacing_row.addSpacing(12)
        pacing_row.addWidget(delay_lbl)
        pacing_row.addWidget(self.delay_spin, 1)
        pacing_lay.addLayout(pacing_row)

        # Persona is already the highlighted control in the masthead — alias the
        # legacy `persona_combo` name there so existing code keeps working
        # without rendering a second copy in the sidebar.
        self.persona_combo = self.masthead_persona
        self.persona_combo.currentIndexChanged.connect(self.on_persona_changed)

        # ---- Speed ----
        self.manual_settings_group, speed_lay = _section("Speed")
        self.min_wpm_slider = QSlider(Qt.Horizontal)
        self.min_wpm_slider.setRange(MIN_WPM_LIMIT, MAX_WPM_LIMIT)
        self.min_wpm_slider.setValue(DEFAULT_MIN_WPM)
        self.max_wpm_slider = QSlider(Qt.Horizontal)
        self.max_wpm_slider.setRange(MIN_WPM_LIMIT, MAX_WPM_LIMIT)
        self.max_wpm_slider.setValue(DEFAULT_MAX_WPM)
        self.min_wpm_label = QLabel(f"{DEFAULT_MIN_WPM} WPM")
        self.max_wpm_label = QLabel(f"{DEFAULT_MAX_WPM} WPM")
        for chip in (self.min_wpm_label, self.max_wpm_label):
            chip.setObjectName("valueChip")
            chip.setMinimumWidth(86)
            chip.setAlignment(Qt.AlignCenter)

        def _speed_row(name, slider, value_chip):
            row = QHBoxLayout()
            row.setSpacing(8)
            label = QLabel(name)
            label.setObjectName("fieldLabel")
            label.setMinimumWidth(36)
            row.addWidget(label)
            row.addWidget(slider, 1)
            row.addWidget(value_chip)
            return row

        speed_lay.addLayout(_speed_row("Min", self.min_wpm_slider, self.min_wpm_label))
        speed_lay.addLayout(_speed_row("Max", self.max_wpm_slider, self.max_wpm_label))

        self.add_mistakes_checkbox = QCheckBox("Add mistakes")
        self.add_mistakes_checkbox.setChecked(True)
        self.pause_on_punct_checkbox = QCheckBox("Pause on punctuation")
        self.pause_on_punct_checkbox.setChecked(True)
        speed_lay.addWidget(self.add_mistakes_checkbox)
        speed_lay.addWidget(self.pause_on_punct_checkbox)

        # ---- Newlines ----
        self.newline_group_box, newline_lay = _section("Newlines")
        self.paste_mode_radio = QRadioButton("Line Paste (fastest)")
        self.paste_mode_radio.setToolTip("Pastes line-by-line using the clipboard (fast). Some apps may block paste.")
        self.standard_radio = QRadioButton("Standard typing")
        self.standard_radio.setToolTip("Types every character exactly as provided.")
        self.smart_radio = QRadioButton("Smart newlines (prose)")
        self.smart_radio.setToolTip("Turns single line breaks into spaces; double breaks remain paragraphs.")
        self.list_mode_radio = QRadioButton("List mode (code)")
        self.list_mode_radio.setToolTip("Strips leading indentation; your editor controls indentation.")
        self.standard_radio.setChecked(True)
        for radio in (self.paste_mode_radio, self.standard_radio,
                      self.smart_radio, self.list_mode_radio):
            newline_lay.addWidget(radio)

        # ---- Behavior ----
        behavior_body, behavior_lay = _section("Behavior")
        self.use_shift_enter_checkbox = QCheckBox("Shift+Enter for newlines")
        self.use_shift_enter_checkbox.setToolTip("Use Shift+Enter instead of Enter for newlines (prevents sending in chat apps).")
        self.type_tabs_checkbox = QCheckBox("Preserve tab characters")
        self.type_tabs_checkbox.setChecked(True)
        self.press_esc_checkbox = QCheckBox("Press Esc before Enter")
        self.press_esc_checkbox.setToolTip("Sends Esc before Enter to dismiss IDE autocomplete popups.")
        self.press_esc_checkbox.setChecked(False)
        self.mouse_jitter_checkbox = QCheckBox("Background mouse jitter")
        self.mouse_jitter_checkbox.setChecked(True)
        self.mouse_jitter_checkbox.setToolTip("Tiny background mouse movement to prevent idle (optional).")
        self.auto_detect_checkbox = QCheckBox("Auto-optimize for target app")
        self.auto_detect_checkbox.setChecked(True)
        self.ime_friendly_checkbox = QCheckBox("IME-friendly paste typing")
        self.unicode_hex_checkbox = QCheckBox("Unicode Hex typing (macOS)")
        if platform.system() != 'Darwin':
            self.unicode_hex_checkbox.setEnabled(False)
            self.unicode_hex_checkbox.setToolTip("macOS only. Enable the 'Unicode Hex Input' keyboard layout.")
        else:
            self.unicode_hex_checkbox.setToolTip("Requires 'Unicode Hex Input' input source in System Settings > Keyboard.")
            self.unicode_hex_checkbox.setChecked(True)

        for cb in (
            self.use_shift_enter_checkbox, self.type_tabs_checkbox,
            self.press_esc_checkbox, self.mouse_jitter_checkbox,
            self.auto_detect_checkbox, self.ime_friendly_checkbox,
            self.unicode_hex_checkbox,
        ):
            behavior_lay.addWidget(cb)

        # ---- Compliance ----
        compliance_body, compliance_lay = _section("Compliance")
        self.compliance_mode_checkbox = QCheckBox("Pause on blocked apps")
        self.compliance_mode_checkbox.setToolTip("Auto-pauses when one of the blocked apps below becomes the active window.")
        compliance_lay.addWidget(self.compliance_mode_checkbox)
        blocked_row = QHBoxLayout()
        blocked_row.setSpacing(8)
        blocked_lbl = QLabel("Blocked apps")
        blocked_lbl.setObjectName("fieldLabel")
        blocked_lbl.setToolTip("Comma-separated list of app names.")
        blocked_row.addWidget(blocked_lbl)
        self.blocked_apps_edit = QLineEdit("Chrome,Safari,Firefox,Edge,Brave,Opera")
        blocked_row.addWidget(self.blocked_apps_edit, 1)
        compliance_lay.addLayout(blocked_row)

        # ---- Macros ----
        macros_body, macros_lay = _section("Macros")
        self.enable_macros_checkbox = QCheckBox("Enable macro execution")
        self.enable_macros_checkbox.setChecked(True)
        self.enable_macros_checkbox.setToolTip("When off, {{PAUSE}}, {{PRESS}}, {{CLICK}} are typed literally as text.")
        self.confirm_click_checkbox = QCheckBox("Confirm before CLICK macros")
        self.confirm_click_checkbox.setChecked(True)
        self.confirm_click_checkbox.setToolTip("Adds a confirmation prompt before any CLICK macro is executed.")
        macros_lay.addWidget(self.enable_macros_checkbox)
        macros_lay.addWidget(self.confirm_click_checkbox)

        settings_panel_layout.addStretch(1)

        # Right: editor + run controls
        right_container = QWidget(self)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Editor toolbar (quick access)
        tools_layout = QHBoxLayout()
        try:
            tools_layout.setContentsMargins(0, 0, 0, 0)
            tools_layout.setSpacing(6)
        except Exception:
            _log_caught('init_ui@L620')
            pass

        self.open_tool_button = QToolButton(self)
        self.open_tool_button.setIcon(make_lucide_icon("open"))
        self.open_tool_button.setToolTip("Open…")
        self.open_tool_button.setText("Open")
        self.open_tool_button.clicked.connect(self.open_file)
        tools_layout.addWidget(self.open_tool_button)

        self.save_tool_button = QToolButton(self)
        self.save_tool_button.setIcon(make_lucide_icon("save"))
        self.save_tool_button.setToolTip("Save As…")
        self.save_tool_button.setText("Save")
        self.save_tool_button.clicked.connect(self.save_file)
        tools_layout.addWidget(self.save_tool_button)

        self.format_tool_button = QToolButton(self)
        self.format_tool_button.setIcon(make_lucide_icon("format"))
        self.format_tool_button.setToolTip("Format tools")
        self.format_tool_button.setText("Format")
        self.format_tool_button.setPopupMode(QToolButton.InstantPopup)
        format_menu_popup = QMenu(self)
        format_menu_popup.addAction("Clean Whitespace", self.clean_whitespace)
        format_menu_popup.addAction("Decode HTML Entities", self.decode_html_entities)
        format_menu_popup.addAction("Fix AI Paste Artifacts", self.fix_ai_paste_artifacts)
        format_menu_popup.addSeparator()
        format_menu_popup.addAction("UPPERCASE", self.to_uppercase)
        format_menu_popup.addAction("lowercase", self.to_lowercase)
        format_menu_popup.addAction("Sentence case", self.to_sentence_case)
        self.format_tool_button.setMenu(format_menu_popup)
        tools_layout.addWidget(self.format_tool_button)

        self.macro_tool_button = QToolButton(self)
        self.macro_tool_button.setIcon(make_lucide_icon("macros"))
        self.macro_tool_button.setToolTip("Insert a macro at the cursor")
        self.macro_tool_button.setText("Macros")
        self.macro_tool_button.setPopupMode(QToolButton.InstantPopup)
        macro_menu_popup = QMenu(self)
        macro_menu_popup.addAction("Insert PAUSE…", self.insert_pause_macro)
        macro_menu_popup.addAction("Insert PRESS…", self.insert_press_macro)
        macro_menu_popup.addAction("Insert CLICK…", self.insert_click_macro)
        macro_menu_popup.addAction("Insert COMMENT…", self.insert_comment_macro)
        self.macro_tool_button.setMenu(macro_menu_popup)
        tools_layout.addWidget(self.macro_tool_button)

        tools_layout.addStretch(1)

        self.clean_button = QToolButton(self)
        self.clean_button.setIcon(make_lucide_icon("clean"))
        self.clean_button.setToolTip("Clean whitespace and decode HTML entities (&amp; → &)")
        self.clean_button.setText("Clean")
        self.clean_button.clicked.connect(self.clean_whitespace)
        tools_layout.addWidget(self.clean_button)

        self.clear_button = QToolButton(self)
        self.clear_button.setIcon(make_lucide_icon("clear"))
        self.clear_button.setToolTip("Clear text")
        self.clear_button.setText("Clear")
        self.clear_button.clicked.connect(self.clear_text)
        tools_layout.addWidget(self.clear_button)

        for b in (self.open_tool_button, self.save_tool_button,
                  self.format_tool_button, self.macro_tool_button, self.clean_button, self.clear_button):
            try:
                b.setAutoRaise(True)
                b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                b.setIconSize(QSize(18, 18))
                b.setMinimumSize(64, 48)
            except Exception:
                _log_caught('init_ui@L689')
                pass

        right_layout.addLayout(tools_layout)

        # Input editor tabs: Plain Text vs Code
        self.input_tabs = QTabWidget(self)

        self.plain_text_edit = PasteCleaningTextEdit()
        self.plain_text_edit.setPlaceholderText(
            "Plain Text mode: paste prose/chat/text — it will be cleaned.\n"
            "Macros: {{PAUSE:1.5}} / {{PRESS:enter}} / {{CLICK:x,y}}"
        )
        self.plain_text_edit.fileDropped.connect(self.load_text_from_path)

        self.code_text_edit = CodeEditor()
        try:
            self.code_text_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        except Exception:
            _log_caught('init_ui@L707')
            pass
        self.code_text_edit.setPlaceholderText(
            "Code mode: paste code/snippets — whitespace is preserved.\n"
            "Tip: Use Paste Mode or Standard to preserve indentation."
        )
        self.code_text_edit.fileDropped.connect(self.load_text_from_path)

        self.input_tabs.addTab(self.plain_text_edit, "Plain Text")
        self.input_tabs.addTab(self.code_text_edit, "Code")
        self.input_tabs.currentChanged.connect(self.on_input_mode_changed)
        self._last_input_tab_index = self.input_tabs.currentIndex()
        right_layout.addWidget(self.input_tabs, 1)

        # Inline metrics strip — replaces the old Stats tab. A single horizontal
        # row of "Label  value" chips kept legible and glanceable.
        self.metrics_strip = QFrame(self)
        self.metrics_strip.setObjectName("metricsStrip")
        metrics_layout = QHBoxLayout(self.metrics_strip)
        metrics_layout.setContentsMargins(12, 6, 12, 6)
        metrics_layout.setSpacing(0)

        def _make_metric(label_text, value_widget):
            wrap = QWidget(self.metrics_strip)
            row = QHBoxLayout(wrap)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            lbl = QLabel(label_text)
            lbl.setObjectName("metricLabel")
            value_widget.setObjectName("metricValue")
            row.addWidget(lbl)
            row.addWidget(value_widget)
            return wrap

        self.stats_words_value = QLabel("0")
        self.stats_chars_value = QLabel("0")
        self.stats_lines_value = QLabel("0")
        self.stats_macros_value = QLabel("0")
        self.stats_clicks_value = QLabel("0")
        self.stats_unicode_value = QLabel("0")
        self.stats_pause_value = QLabel("0.0s")
        self.stats_output_value = QLabel("0")

        metric_items = [
            ("Words", self.stats_words_value),
            ("Chars", self.stats_chars_value),
            ("Lines", self.stats_lines_value),
            ("Macros", self.stats_macros_value),
            ("Clicks", self.stats_clicks_value),
            ("Non-ASCII", self.stats_unicode_value),
            ("Pause", self.stats_pause_value),
            ("Output", self.stats_output_value),
        ]
        for idx, (label_text, val) in enumerate(metric_items):
            if idx > 0:
                sep = QFrame(self.metrics_strip)
                sep.setObjectName("metricSep")
                sep.setFrameShape(QFrame.VLine)
                sep.setFixedHeight(14)
                metrics_layout.addSpacing(10)
                metrics_layout.addWidget(sep)
                metrics_layout.addSpacing(10)
            metrics_layout.addWidget(_make_metric(label_text, val))
        metrics_layout.addStretch(1)
        right_layout.addWidget(self.metrics_strip)

        # Preview panel — collapsed by default, expandable via a header toggle.
        # Far less visual noise than the old Stats/Preview tab pair.
        self.preview_toggle = QToolButton(self)
        self.preview_toggle.setObjectName("previewToggle")
        self.preview_toggle.setText("▸  Output preview")
        self.preview_toggle.setCheckable(True)
        self.preview_toggle.setChecked(False)
        self.preview_toggle.setCursor(Qt.PointingHandCursor)
        self.preview_toggle.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.preview_toggle.setAutoRaise(True)
        self.preview_toggle.toggled.connect(self._on_preview_toggle)
        right_layout.addWidget(self.preview_toggle)

        self.preview_panel = QFrame(self)
        self.preview_panel.setObjectName("previewPanel")
        preview_layout = QVBoxLayout(self.preview_panel)
        preview_layout.setContentsMargins(0, 4, 0, 4)
        preview_layout.setSpacing(4)
        self.processed_preview = QPlainTextEdit(self)
        self.processed_preview.setReadOnly(True)
        self.processed_preview.setPlaceholderText("Output preview (sample)…")
        self.processed_preview.setMaximumHeight(140)
        preview_layout.addWidget(self.processed_preview, 1)
        self.mode_note_label = QLabel("")
        self.mode_note_label.setWordWrap(True)
        self.mode_note_label.setObjectName("modeNote")
        preview_layout.addWidget(self.mode_note_label)
        self.preview_panel.setVisible(False)
        right_layout.addWidget(self.preview_panel)

        # Run controls — no outer group box. A thin top divider separates it
        # from the editor area; the buttons themselves are the visual anchor.
        run_divider = QFrame(self)
        run_divider.setObjectName("runDivider")
        run_divider.setFrameShape(QFrame.HLine)
        run_divider.setFixedHeight(1)
        right_layout.addWidget(run_divider)

        run_container = QWidget(self)
        run_layout = QVBoxLayout(run_container)
        run_layout.setContentsMargins(0, 8, 0, 0)
        run_layout.setSpacing(8)
        run_btns = QHBoxLayout()
        run_btns.setSpacing(10)
        self.start_button = QPushButton()
        self.start_button.setObjectName("startButton")
        self.start_button.setIcon(make_lucide_icon("play", color="#F0FDF4", size=18))
        self.pause_button = QPushButton("PAUSE")
        self.pause_button.setObjectName("pauseButton")
        self.pause_button.setIcon(make_lucide_icon("pause", color="#94A3B8", size=16))
        self.pause_button.setEnabled(False)
        self.stop_button = QPushButton()
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setIcon(make_lucide_icon("stop", color="#94A3B8", size=14))
        for b in (self.start_button, self.pause_button, self.stop_button):
            try:
                b.setMinimumHeight(40)
                b.setCursor(Qt.PointingHandCursor)
            except Exception:
                _log_caught('init_ui@L831')
                pass
        run_btns.addWidget(self.start_button, 2)
        run_btns.addWidget(self.pause_button, 2)
        run_btns.addWidget(self.stop_button, 2)
        run_layout.addLayout(run_btns)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.preview_label = QLabel("Estimated: -- s")
        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.preview_label)
        run_layout.addLayout(progress_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.status_badge = QLabel()
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setFixedSize(12, 12)
        self.status_badge.setStyleSheet("background-color: #94A3B8; border-radius: 6px;")
        self.wpm_display = QLabel("Current: --- WPM")
        self.status_label = QLabel("Status: Idle")
        self.lap_label = QLabel("Lap: 0 / 0")
        self.etr_label = QLabel("ETR: --:--")
        status_row.addWidget(self.status_badge)
        status_row.addWidget(self.status_label, 3)
        status_row.addWidget(self.wpm_display, 1)
        status_row.addWidget(self.lap_label)
        status_row.addWidget(self.etr_label)
        run_layout.addLayout(status_row)
        right_layout.addWidget(run_container)

        self.splitter.addWidget(right_container)
        try:
            # Sidebar can be collapsed by dragging fully to the left or via the
            # "Toggle Sidebar" action; the editor side stays anchored.
            self.splitter.setChildrenCollapsible(True)
            self.splitter.setCollapsible(0, True)
            self.splitter.setCollapsible(1, False)
            self.splitter.setStretchFactor(0, 0)
            self.splitter.setStretchFactor(1, 1)
            self.splitter.setHandleWidth(ChevronSplitterHandle.HANDLE_WIDTH)
            # Reasonable defaults; user can resize and it's persisted.
            self.splitter.setSizes([360, 880])
        except Exception:
            _log_caught('init_ui@L877')
            pass
        # Track last open width so toggle restores it after a collapse.
        self._sidebar_last_width = 360
        try:
            self.splitter.splitterMoved.connect(self._on_splitter_moved)
        except Exception:
            _log_caught('init_ui@L883')
            pass

        # Text update debounce for large inputs
        self._text_update_timer = QTimer(self)
        self._text_update_timer.setSingleShot(True)
        self._text_update_timer.timeout.connect(self.refresh_text_insights)
        
        # Resume countdown (grace period so you don't miss text after resuming).
        self._resume_countdown_timer = QTimer(self)
        self._resume_countdown_timer.setInterval(1000)
        self._resume_countdown_timer.timeout.connect(self._on_resume_countdown_tick)
        self._resume_countdown_active = False
        self._resume_countdown_remaining = 0

        # Wiring
        self.start_button.clicked.connect(self.start_typing)
        self.pause_button.clicked.connect(self.pause_or_resume)
        self.stop_button.clicked.connect(self.stop_typing)
        self.min_wpm_slider.valueChanged.connect(self.update_speed_labels)
        self.max_wpm_slider.valueChanged.connect(self.update_speed_labels)

        # Schedule updates rather than recalculating on every keystroke immediately
        self.plain_text_edit.textChanged.connect(self.schedule_text_update)
        self.code_text_edit.textChanged.connect(self.schedule_text_update)
        self.laps_spin.valueChanged.connect(self.schedule_text_update)
        self.delay_spin.valueChanged.connect(self.schedule_text_update)
        self.standard_radio.toggled.connect(self.schedule_text_update)
        self.smart_radio.toggled.connect(self.schedule_text_update)
        self.list_mode_radio.toggled.connect(self.schedule_text_update)
        self.paste_mode_radio.toggled.connect(self.schedule_text_update)
        self.use_shift_enter_checkbox.toggled.connect(self.schedule_text_update)
        self.type_tabs_checkbox.toggled.connect(self.schedule_text_update)
        self.add_mistakes_checkbox.toggled.connect(self.schedule_text_update)
        self.pause_on_punct_checkbox.toggled.connect(self.schedule_text_update)
        self.press_esc_checkbox.toggled.connect(self.schedule_text_update)
        self.mouse_jitter_checkbox.toggled.connect(self.schedule_text_update)
        self.auto_detect_checkbox.toggled.connect(self.schedule_text_update)
        self.ime_friendly_checkbox.toggled.connect(self.schedule_text_update)
        self.unicode_hex_checkbox.toggled.connect(self.schedule_text_update)
        self.compliance_mode_checkbox.toggled.connect(self.schedule_text_update)
        self.enable_macros_checkbox.toggled.connect(self.on_macros_toggled)

        # Initialize text/estimate panels once UI is wired
        self.update_speed_labels()
        self.schedule_text_update()

    def _active_editor(self):
        try:
            idx = int(self.input_tabs.currentIndex())
        except Exception:
            _log_caught('_active_editor@L933')
            idx = 0
        return self.code_text_edit if idx == 1 else self.plain_text_edit

    def _all_editors(self):
        return (self.plain_text_edit, self.code_text_edit)

    def input_mode_name(self) -> str:
        try:
            return "Code" if int(self.input_tabs.currentIndex()) == 1 else "Plain Text"
        except Exception:
            _log_caught('input_mode_name@L943')
            return "Plain Text"

    def get_input_text(self) -> str:
        try:
            return self._active_editor().toPlainText()
        except Exception:
            _log_caught('get_input_text@L949')
            return ""

    def set_input_text(self, text: str):
        try:
            self._active_editor().setPlainText(text or "")
        except Exception:
            _log_caught('set_input_text@L955')
            pass

    def clear_text(self):
        try:
            self._active_editor().clear()
        except Exception:
            _log_caught('clear_text@L961')
            pass

    def _input_mode_key(self, idx: int) -> str:
        return "code" if int(idx) == 1 else "plain"

    def _capture_input_mode_preset(self) -> dict:
        return {
            "persona": str(self.persona_combo.currentText()),
            "newline_mode": self._get_selected_newline_mode(),
            "use_shift_enter": bool(self.use_shift_enter_checkbox.isChecked()),
            "type_tabs": bool(self.type_tabs_checkbox.isChecked()),
            "press_esc": bool(self.press_esc_checkbox.isChecked()),
            "add_mistakes": bool(self.add_mistakes_checkbox.isChecked()),
            "pause_on_punct": bool(self.pause_on_punct_checkbox.isChecked()),
            "mouse_jitter": bool(self.mouse_jitter_checkbox.isChecked()),
            "unicode_hex": bool(self.unicode_hex_checkbox.isChecked()),
            "auto_detect": bool(self.auto_detect_checkbox.isChecked()),
            "min_wpm": int(self.min_wpm_slider.value()),
            "max_wpm": int(self.max_wpm_slider.value()),
        }

    def _apply_input_mode_preset(self, preset: dict):
        persona = (preset or {}).get("persona")
        if persona:
            try:
                self._suppress_persona_changed = True
                self.persona_combo.setCurrentText(str(persona))
            except Exception:
                _log_caught('_apply_input_mode_preset@L989')
                pass
            finally:
                self._suppress_persona_changed = False

        mode = (preset or {}).get("newline_mode") or "Standard"
        if mode == "Paste Mode":
            self.paste_mode_radio.setChecked(True)
        elif mode == "Smart Newlines":
            self.smart_radio.setChecked(True)
        elif mode == "List Mode":
            self.list_mode_radio.setChecked(True)
        else:
            self.standard_radio.setChecked(True)

        def _set(cb, key, default):
            try:
                cb.setChecked(bool((preset or {}).get(key, default)))
            except Exception:
                _log_caught('_set@L1007')
                pass

        _set(self.use_shift_enter_checkbox, "use_shift_enter", False)
        _set(self.type_tabs_checkbox, "type_tabs", True)
        _set(self.press_esc_checkbox, "press_esc", False)
        _set(self.add_mistakes_checkbox, "add_mistakes", False)
        _set(self.pause_on_punct_checkbox, "pause_on_punct", True)
        _set(self.mouse_jitter_checkbox, "mouse_jitter", False)
        _set(self.unicode_hex_checkbox, "unicode_hex", bool(platform.system() == "Darwin"))
        _set(self.auto_detect_checkbox, "auto_detect", True)
        try:
            self.min_wpm_slider.setValue(int((preset or {}).get("min_wpm", self.min_wpm_slider.value())))
            self.max_wpm_slider.setValue(int((preset or {}).get("max_wpm", self.max_wpm_slider.value())))
        except Exception:
            _log_caught('_apply_input_mode_preset@L1021')
            pass
        self.update_speed_labels()

    def _default_input_mode_preset(self, idx: int) -> dict:
        unicode_default = bool(platform.system() == "Darwin")
        if int(idx) == 1:  # Code
            return {
                "persona": "Careful Coder",
                "newline_mode": "List Mode",
                "use_shift_enter": False,
                "type_tabs": False,
                "press_esc": True,
                "add_mistakes": False,
                "pause_on_punct": True,
                "mouse_jitter": False,
                "unicode_hex": unicode_default,
                "auto_detect": True,
                "min_wpm": 90,
                "max_wpm": 140,
            }
        # Plain Text
        return {
            "persona": "Custom (Manual Settings)",
            "newline_mode": "Standard",
            "use_shift_enter": False,
            "type_tabs": True,
            "press_esc": False,
            "add_mistakes": True,
            "pause_on_punct": True,
            "mouse_jitter": True,
            "unicode_hex": unicode_default,
            "auto_detect": True,
            "min_wpm": DEFAULT_MIN_WPM,
            "max_wpm": DEFAULT_MAX_WPM,
        }

    def _has_input_mode_preset(self, idx: int) -> bool:
        key = self._input_mode_key(idx)
        try:
            self.settings.beginGroup(f"ModePresets/{key}")
            return bool(self.settings.childKeys())
        except Exception:
            _log_caught('_has_input_mode_preset@L1063')
            return False
        finally:
            try:
                self.settings.endGroup()
            except Exception:
                _log_caught('_has_input_mode_preset@L1068')
                pass

    def _write_input_mode_preset(self, idx: int, preset: dict):
        try:
            key = self._input_mode_key(idx)
            self.settings.beginGroup(f"ModePresets/{key}")
            for k, v in (preset or {}).items():
                self.settings.setValue(k, v)
        except Exception:
            _log_caught('_write_input_mode_preset@L1077')
            pass
        finally:
            try:
                self.settings.endGroup()
            except Exception:
                _log_caught('_write_input_mode_preset@L1082')
                pass

    def _save_input_mode_preset(self, idx: int):
        try:
            key = self._input_mode_key(idx)
            preset = self._capture_input_mode_preset()
            self.settings.beginGroup(f"ModePresets/{key}")
            for k, v in preset.items():
                self.settings.setValue(k, v)
        except Exception:
            _log_caught('_save_input_mode_preset@L1092')
            pass
        finally:
            try:
                self.settings.endGroup()
            except Exception:
                _log_caught('_save_input_mode_preset@L1097')
                pass

    def _load_input_mode_preset(self, idx: int, apply_defaults: bool = True):
        key = self._input_mode_key(idx)
        preset = None
        try:
            self.settings.beginGroup(f"ModePresets/{key}")
            keys = self.settings.childKeys()
            if keys:
                preset = {
                    "persona": self.settings.value("persona", "", type=str),
                    "newline_mode": self.settings.value("newline_mode", "Standard", type=str),
                    "use_shift_enter": self.settings.value("use_shift_enter", False, type=bool),
                    "type_tabs": self.settings.value("type_tabs", True, type=bool),
                    "press_esc": self.settings.value("press_esc", False, type=bool),
                    "add_mistakes": self.settings.value("add_mistakes", False, type=bool),
                    "pause_on_punct": self.settings.value("pause_on_punct", True, type=bool),
                    "mouse_jitter": self.settings.value("mouse_jitter", False, type=bool),
                    "unicode_hex": self.settings.value("unicode_hex", bool(platform.system() == "Darwin"), type=bool),
                    "auto_detect": self.settings.value("auto_detect", True, type=bool),
                    "min_wpm": self.settings.value("min_wpm", self.min_wpm_slider.value(), type=int),
                    "max_wpm": self.settings.value("max_wpm", self.max_wpm_slider.value(), type=int),
                }
        except Exception:
            _log_caught('_load_input_mode_preset@L1121')
            preset = None
        finally:
            try:
                self.settings.endGroup()
            except Exception:
                _log_caught('_load_input_mode_preset@L1126')
                pass

        if preset is None and apply_defaults:
            preset = self._default_input_mode_preset(idx)
        if preset:
            self._apply_input_mode_preset(preset)

    def on_input_mode_changed(self, index: int):
        if self._suppress_input_mode_changed:
            return
        try:
            old_index = int(getattr(self, "_last_input_tab_index", 0))
        except Exception:
            _log_caught('on_input_mode_changed@L1139')
            old_index = 0
        try:
            new_index = int(index)
        except Exception:
            _log_caught('on_input_mode_changed@L1143')
            new_index = int(self.input_tabs.currentIndex())

        # Save current settings for the mode we're leaving, then restore settings for the mode we're entering.
        try:
            self._save_input_mode_preset(old_index)
        except Exception:
            _log_caught('on_input_mode_changed@L1149')
            pass
        try:
            self._load_input_mode_preset(new_index, apply_defaults=True)
        except Exception:
            _log_caught('on_input_mode_changed@L1153')
            pass

        self._last_input_tab_index = new_index
        try:
            self.settings.setValue("inputMode", new_index)
        except Exception:
            _log_caught('on_input_mode_changed@L1159')
            pass
        self.schedule_text_update()

    def schedule_text_update(self):
        """Debounced refresh for estimate/stats/preview to handle large inputs smoothly."""
        try:
            if hasattr(self, "_text_update_timer") and self._text_update_timer:
                self._text_update_timer.start(150)
                return
        except Exception:
            _log_caught('schedule_text_update@L1169')
            pass
        self.refresh_text_insights()

    def refresh_text_insights(self):
        try:
            self.update_preview()
        except Exception:
            _log_caught('refresh_text_insights@L1176')
            pass
        try:
            self.update_text_stats()
        except Exception:
            _log_caught('refresh_text_insights@L1180')
            pass
        try:
            self.update_processed_preview()
        except Exception:
            _log_caught('refresh_text_insights@L1184')
            pass
        try:
            self.update_mode_note()
        except Exception:
            _log_caught('refresh_text_insights@L1188')
            pass
        try:
            self._update_start_button_enabled()
        except Exception:
            _log_caught('refresh_text_insights@L1192')
            pass

    def on_macros_toggled(self, checked: bool):
        try:
            self.confirm_click_checkbox.setEnabled(bool(checked))
        except Exception:
            _log_caught('on_macros_toggled@L1198')
            pass
        self.schedule_text_update()

    def pause_or_resume(self):
        if not self.worker:
            return
        if self.is_paused:
            self.resume_typing()
        else:
            try:
                self.worker.pause()
            except Exception:
                _log_caught('pause_or_resume@L1210')
                pass

    def _set_ui_for_paused(self, paused: bool):
        """While paused, allow editing/tuning settings before resuming."""
        enable = bool(paused)
        try:
            self.settings_tabs.setEnabled(enable)
        except Exception:
            _log_caught('_set_ui_for_paused@L1218')
            pass
        for w in (
            getattr(self, "menu_bar", None),
            getattr(self, "open_tool_button", None),
            getattr(self, "save_tool_button", None),
            getattr(self, "format_tool_button", None),
            getattr(self, "macro_tool_button", None),
            getattr(self, "clean_button", None),
            getattr(self, "clear_button", None),
            getattr(self, "input_tabs", None),
        ):
            if not w:
                continue
            try:
                w.setEnabled(enable)
            except Exception:
                _log_caught('_set_ui_for_paused@L1234')
                pass
        try:
            for ed in self._all_editors():
                ed.setEnabled(enable)
        except Exception:
            _log_caught('_set_ui_for_paused@L1239')
            pass

    def _apply_runtime_settings_to_worker(self):
        """Apply UI changes to the current worker (best-effort; affects remaining text)."""
        if not self.worker:
            return
        try:
            self.worker.update_speed_range(self.min_wpm_slider.value(), self.max_wpm_slider.value())
        except Exception:
            _log_caught('_apply_runtime_settings_to_worker@L1248')
            pass
        try:
            self.worker.add_mistakes = bool(self.add_mistakes_checkbox.isChecked())
            self.worker.pause_on_punct = bool(self.pause_on_punct_checkbox.isChecked())
            self.worker.newline_mode = self._get_selected_newline_mode()
            self.worker.use_shift_enter = bool(self.use_shift_enter_checkbox.isChecked())
            self.worker.type_tabs = bool(self.type_tabs_checkbox.isChecked())
            self.worker.press_esc = bool(self.press_esc_checkbox.isChecked())
            self.worker.enable_mouse_jitter = bool(self.mouse_jitter_checkbox.isChecked())
            self.worker.ime_friendly = bool(self.ime_friendly_checkbox.isChecked())
            self.worker.unicode_hex_typing = bool(self.unicode_hex_checkbox.isChecked())
            self.worker.compliance_mode = bool(self.compliance_mode_checkbox.isChecked())
            self.worker.auto_detect = bool(self.auto_detect_checkbox.isChecked())
            self.worker.enable_macros = bool(self._macros_enabled())
            blocked = (self.blocked_apps_edit.text() or "").strip()
            self.worker.blocked_apps = [b.strip().lower() for b in blocked.split(",") if b.strip()]
        except Exception:
            _log_caught('_apply_runtime_settings_to_worker@L1265')
            pass

    def _start_resume_countdown(self, seconds: int = 4):
        if not (self.worker and self.is_paused):
            return
        seconds = int(seconds) if seconds is not None else 4
        seconds = max(1, min(60, seconds))
        self._resume_countdown_active = True
        self._resume_countdown_remaining = seconds
        try:
            self.pause_button.setEnabled(True)
            self.pause_button.setText(f"CANCEL ({seconds})")
            self.pause_button.setIcon(self.style().standardIcon(QStyle.SP_DialogCancelButton))
        except Exception:
            _log_caught('_start_resume_countdown@L1279')
            pass
        self.status_label.setText(f"Status: Resuming in {seconds}…")
        try:
            self._resume_countdown_timer.start()
        except Exception:
            _log_caught('_start_resume_countdown@L1284')
            pass

    def _cancel_resume_countdown(self, silent: bool = False):
        if not getattr(self, "_resume_countdown_active", False):
            return
        self._resume_countdown_active = False
        self._resume_countdown_remaining = 0
        try:
            self._resume_countdown_timer.stop()
        except Exception:
            _log_caught('_cancel_resume_countdown@L1294')
            pass
        if not silent:
            try:
                self.status_label.setText("Status: Resume canceled.")
            except Exception:
                _log_caught('_cancel_resume_countdown@L1299')
                pass
        # Restore paused UI affordance
        try:
            self.pause_button.setText("RESUME")
            self.pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        except Exception:
            _log_caught('_cancel_resume_countdown@L1305')
            pass

    def _on_resume_countdown_tick(self):
        if not getattr(self, "_resume_countdown_active", False):
            return
        if not (self.worker and self.is_paused):
            self._cancel_resume_countdown(silent=True)
            return
        try:
            remaining = int(self._resume_countdown_remaining) - 1
        except Exception:
            _log_caught('_on_resume_countdown_tick@L1316')
            remaining = 0
        self._resume_countdown_remaining = remaining
        if remaining <= 0:
            self._cancel_resume_countdown(silent=True)
            # Apply any changes made while paused before resuming.
            self._apply_runtime_settings_to_worker()
            # Lock UI back down for the live run.
            self.set_ui_for_running(True)
            try:
                self.status_label.setText("Status: Resuming…")
            except Exception:
                _log_caught('_on_resume_countdown_tick@L1327')
                pass
            try:
                self.worker.resume()
            except Exception:
                _log_caught('_on_resume_countdown_tick@L1331')
                pass
            return
        try:
            self.status_label.setText(f"Status: Resuming in {remaining}…")
        except Exception:
            _log_caught('_on_resume_countdown_tick@L1336')
            pass
        try:
            self.pause_button.setText(f"CANCEL ({remaining})")
        except Exception:
            _log_caught('_on_resume_countdown_tick@L1340')
            pass

    def _update_start_button_enabled(self):
        """Disable START when there's no text (while idle)."""
        if self.worker:
            return
        if self.is_paused:
            self.start_button.setEnabled(True)
            return
        has_text = bool(self.get_input_text().strip())
        self.start_button.setEnabled(has_text)

    def _set_status_state(self, state: str):
        colors = {
            "idle": "#888888",
            "running": "#2ecc71",
            "paused": "#f39c12",
            "error": "#e74c3c",
        }
        color = colors.get(state or "idle", "#888888")
        try:
            self.status_badge.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
        except Exception:
            _log_caught('_set_status_state@L1363')
            pass

    def on_worker_status(self, text: str):
        raw = text if isinstance(text, str) else str(text)
        display = raw if raw.startswith("Status:") else f"Status: {raw}"
        self.status_label.setText(display)
        tl = raw.lower()
        if "error" in tl or "failed" in tl:
            self._set_status_state("error")

    def _get_selected_newline_mode(self) -> str:
        if self.paste_mode_radio.isChecked():
            return "Paste Mode"
        if self.list_mode_radio.isChecked():
            return "List Mode"
        if self.smart_radio.isChecked():
            return "Smart Newlines"
        return "Standard"

    def _macros_enabled(self) -> bool:
        try:
            return bool(self.enable_macros_checkbox.isChecked())
        except Exception:
            _log_caught('_macros_enabled@L1386')
            return True

    def _strip_macros_ui(self, text: str) -> str:
        if not self._macros_enabled():
            return text
        try:
            return re.sub(r"(?i)\{\{(?:PAUSE|PRESS|CLICK|COMMENT):.*?\}\}", "", text)
        except Exception:
            _log_caught('_strip_macros_ui@L1394')
            return text

    def _extract_pause_seconds(self, text: str) -> float:
        if not self._macros_enabled():
            return 0.0
        total = 0.0
        try:
            for m in re.finditer(r"(?i)\{\{PAUSE:(.*?)\}\}", text):
                try:
                    t = float((m.group(1) or "").strip())
                except Exception:
                    _log_caught('_extract_pause_seconds@L1405')
                    continue
                if t <= 0:
                    continue
                total += min(t, 60.0)
        except Exception:
            _log_caught('_extract_pause_seconds@L1410')
            pass
        return total

    def _count_macros(self, text: str) -> dict:
        counts = {"total": 0, "pause": 0, "press": 0, "click": 0, "comment": 0}
        try:
            for m in re.finditer(r"\{\{([A-Za-z]+):(.*?)\}\}", text):
                cmd = (m.group(1) or "").strip().upper()
                counts["total"] += 1
                key = cmd.lower()
                if key in counts:
                    counts[key] += 1
        except Exception:
            _log_caught('_count_macros@L1423')
            pass
        return counts

    def _compute_output_chars_per_lap_ui(self, text: str) -> int:
        if not text:
            return 0
        mode = self._get_selected_newline_mode()
        macros_enabled = self._macros_enabled()
        type_tabs = bool(self.type_tabs_checkbox.isChecked()) if hasattr(self, "type_tabs_checkbox") else True

        if mode == "Paste Mode":
            return len(self._strip_macros_ui(text)) if macros_enabled else len(text)

        if mode == "List Mode":
            lines = text.splitlines()
            total = 0
            for line in lines:
                stripped = line.lstrip(" \t")
                if not type_tabs:
                    stripped = stripped.replace("\t", "")
                if macros_enabled:
                    stripped = self._strip_macros_ui(stripped)
                total += len(stripped)
            total += len(lines)  # Enter after each line
            return total

        processed = apply_smart_newlines(text) if mode == "Smart Newlines" else text
        if macros_enabled:
            processed = self._strip_macros_ui(processed)
        if not type_tabs:
            processed = processed.replace("\t", "")
        return len(processed)

    def update_text_stats(self):
        text = self.get_input_text()
        # Whitespace-split count, matching MS Word / Google Docs / Pages.
        # The previous \b\w+\b regex over-counted contractions ("don't" -> 2),
        # email addresses ("foo@bar.com" -> 3), and similar punctuation-mixed
        # tokens because non-word characters split words.
        words = len(text.split())
        chars = len(text)
        lines = len(text.splitlines()) if text else 0
        non_ascii = 0
        try:
            non_ascii = sum(1 for ch in text if ord(ch) > 0x7F)
        except Exception:
            _log_caught('update_text_stats@L1465')
            non_ascii = 0
        macro_counts = self._count_macros(text)
        pause_total = self._extract_pause_seconds(text)
        out_per_lap = self._compute_output_chars_per_lap_ui(text)
        out_total = out_per_lap * max(1, self.laps_spin.value())

        self.stats_words_value.setText(str(words))
        self.stats_chars_value.setText(str(chars))
        self.stats_lines_value.setText(str(lines))
        self.stats_macros_value.setText(str(macro_counts.get("total", 0)))
        self.stats_clicks_value.setText(str(macro_counts.get("click", 0)))
        self.stats_unicode_value.setText(str(non_ascii))
        self.stats_pause_value.setText(f"{pause_total:.1f}s" if self._macros_enabled() else "—")
        self.stats_output_value.setText(str(out_total))

    def update_processed_preview(self):
        text = self.get_input_text()
        if not text.strip():
            self.processed_preview.setPlainText("")
            return
        mode = self._get_selected_newline_mode()
        macros_enabled = self._macros_enabled()
        type_tabs = bool(self.type_tabs_checkbox.isChecked()) if hasattr(self, "type_tabs_checkbox") else True

        try:
            code_input = int(self.input_tabs.currentIndex()) == 1
        except Exception:
            _log_caught('update_processed_preview@L1492')
            code_input = False

        sample_lines = []
        if mode == "Paste Mode":
            # Paste Mode outputs the text as-is (minus macros); tabs are preserved.
            preview = self._strip_macros_ui(text) if macros_enabled else text
        elif mode == "List Mode":
            # For Plain Text input, show what List Mode actually sends (leading indentation removed).
            # For Code input, show the expected end result in editors (indentation preserved).
            for ln in text.splitlines()[:60]:
                if code_input:
                    s = self._strip_macros_ui(ln) if macros_enabled else ln
                    if not type_tabs:
                        s = s.replace("\t", "")
                else:
                    s = ln.lstrip(" \t")
                    if not type_tabs:
                        s = s.replace("\t", "")
                    s = self._strip_macros_ui(s) if macros_enabled else s
                sample_lines.append(s)
            preview = "\n".join(sample_lines) + ("\n" if sample_lines else "")
        else:
            processed = apply_smart_newlines(text) if mode == "Smart Newlines" else text
            processed = self._strip_macros_ui(processed) if macros_enabled else processed
            if not type_tabs:
                processed = processed.replace("\t", "")
            preview = processed
        if len(preview) > 4000:
            preview = preview[:4000] + "\n…"
        self.processed_preview.setPlainText(preview)

    def update_mode_note(self):
        mode = self._get_selected_newline_mode()
        macros_enabled = self._macros_enabled()
        notes = []
        notes.append(f"Input: {self.input_mode_name()}")
        if mode == "List Mode":
            notes.append("List Mode strips leading indentation; your editor controls indentation.")
        elif mode == "Paste Mode":
            notes.append("Paste Mode uses the clipboard; some apps may block paste or alter formatting.")
        elif mode == "Smart Newlines":
            notes.append("Smart Newlines joins single line breaks into spaces; double breaks remain paragraph breaks.")
        if macros_enabled:
            notes.append("Macros are enabled: {{PAUSE}}, {{PRESS}}, {{CLICK}}, {{COMMENT}} will execute.")
        else:
            notes.append("Macros are disabled: macro patterns will be typed as literal text.")
        try:
            if self.ime_friendly_checkbox.isChecked() and not self.unicode_hex_checkbox.isChecked():
                notes.append("IME-friendly is on: uses paste instead of per-key typing.")
        except Exception:
            _log_caught('update_mode_note@L1542')
            pass
        if hasattr(self, "compliance_mode_checkbox") and self.compliance_mode_checkbox.isChecked():
            notes.append("Compliance Mode is on: typing auto-pauses in blocked apps.")
        self.mode_note_label.setText(" • ".join(notes))

    def _insert_at_cursor(self, text: str):
        editor = self._active_editor()
        try:
            cursor = editor.textCursor()
            cursor.insertText(text)
            editor.setTextCursor(cursor)
            editor.setFocus()
        except Exception:
            _log_caught('_insert_at_cursor@L1555')
            try:
                editor.insertPlainText(text)
            except Exception:
                _log_caught('_insert_at_cursor@L1558')
                pass

    def insert_pause_macro(self):
        val, ok = QInputDialog.getDouble(self, "Insert PAUSE", "Seconds (0–60):", 1.0, 0.0, 60.0, 2)
        if not ok:
            return
        self._insert_at_cursor(f"{{{{PAUSE:{val}}}}}")

    def insert_press_macro(self):
        common = ["enter", "tab", "esc", "backspace", "delete", "up", "down", "left", "right", "home", "end", "pageup", "pagedown"]
        key, ok = QInputDialog.getItem(self, "Insert PRESS", "Key name:", common, 0, True)
        if not ok or not str(key).strip():
            return
        self._insert_at_cursor(f"{{{{PRESS:{str(key).strip()}}}}}")

    def insert_click_macro(self):
        choice = QMessageBox.question(
            self,
            "Insert CLICK",
            "Use current mouse position?\n\nYes: capture current cursor position\nNo: enter coordinates manually",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if choice == QMessageBox.Cancel:
            return
        if choice == QMessageBox.Yes:
            try:
                x, y = pyautogui.position()
                self._insert_at_cursor(f"{{{{CLICK:{int(x)},{int(y)}}}}}")
                return
            except Exception as e:
                QMessageBox.warning(self, "Insert CLICK", f"Could not read mouse position:\n{e}")
                return
        coords, ok = QInputDialog.getText(self, "Insert CLICK", "Enter coordinates as x,y:")
        if not ok or not coords.strip():
            return
        self._insert_at_cursor(f"{{{{CLICK:{coords.strip()}}}}}")

    def insert_comment_macro(self):
        txt, ok = QInputDialog.getText(self, "Insert COMMENT", "Comment text:")
        if not ok:
            return
        self._insert_at_cursor(f"{{{{COMMENT:{txt}}}}}")

    def set_ui_for_running(self, is_running):
        self.start_button.setEnabled(not is_running)
        self.pause_button.setEnabled(is_running)
        self.stop_button.setEnabled(is_running)
        try:
            self.input_tabs.setEnabled(not is_running)
        except Exception:
            _log_caught('set_ui_for_running@L1609')
            pass
        for ed in self._all_editors():
            try:
                ed.setEnabled(not is_running)
            except Exception:
                _log_caught('set_ui_for_running@L1614')
                pass
        self.menu_bar.setEnabled(not is_running)
        self.open_tool_button.setEnabled(not is_running)
        self.save_tool_button.setEnabled(not is_running)
        self.format_tool_button.setEnabled(not is_running)
        self.macro_tool_button.setEnabled(not is_running)
        self.clean_button.setEnabled(not is_running)
        self.clear_button.setEnabled(not is_running)
        self.settings_tabs.setEnabled(not is_running)
        if not is_running:
            self._set_status_state("idle")
            self._update_start_button_enabled()
        else:
            self._set_status_state("running")

    def on_persona_changed(self, index: int = 0):
        if getattr(self, "_suppress_persona_changed", False):
            return
        # During init_ui the editor tabs may not exist yet.
        if not hasattr(self, "input_tabs"):
            return
        try:
            self.toggle_persona_controls()
        except Exception:
            _log_caught('on_persona_changed@L1638')
            pass
        self.schedule_text_update()

    def toggle_persona_controls(self):
        persona = self.persona_combo.currentText()
        self.manual_settings_group.setEnabled(True)

        try:
            in_plain = int(self.input_tabs.currentIndex()) == 0
        except Exception:
            _log_caught('toggle_persona_controls@L1648')
            in_plain = True

        def _maybe_enable_unicode_hex_default():
            if platform.system() == "Darwin" and getattr(self, "unicode_hex_checkbox", None):
                try:
                    if self.unicode_hex_checkbox.isEnabled():
                        self.unicode_hex_checkbox.setChecked(True)
                except Exception:
                    _log_caught('_maybe_enable_unicode_hex_default@L1656')
                    pass

        def _apply_plain_defaults(is_fast_messenger: bool):
            if is_fast_messenger:
                self.smart_radio.setChecked(True)
                self.use_shift_enter_checkbox.setChecked(True)
                self.press_esc_checkbox.setChecked(False)
                self.type_tabs_checkbox.setChecked(True)
                self.add_mistakes_checkbox.setChecked(True)
                self.pause_on_punct_checkbox.setChecked(True)
                # Keep jitter off by default for messenger to avoid suspicion.
                self.mouse_jitter_checkbox.setChecked(False)
                _maybe_enable_unicode_hex_default()
                return

            self.standard_radio.setChecked(True)
            self.use_shift_enter_checkbox.setChecked(False)
            self.press_esc_checkbox.setChecked(False)
            self.type_tabs_checkbox.setChecked(True)
            self.mouse_jitter_checkbox.setChecked(True)
            _maybe_enable_unicode_hex_default()
            self.add_mistakes_checkbox.setChecked(True)
            self.pause_on_punct_checkbox.setChecked(True)

        def _apply_code_defaults():
            # Code editor mode: keep typing stable and code-safe regardless of persona.
            # (App-level browser guardrails still suppress Esc where unsafe.)
            try:
                self.list_mode_radio.setChecked(True)
            except Exception:
                _log_caught('_apply_code_defaults@L1686')
                pass
            try:
                self.use_shift_enter_checkbox.setChecked(False)
            except Exception:
                _log_caught('_apply_code_defaults@L1690')
                pass
            try:
                self.press_esc_checkbox.setChecked(True)
            except Exception:
                _log_caught('_apply_code_defaults@L1694')
                pass
            try:
                self.type_tabs_checkbox.setChecked(False)
            except Exception:
                _log_caught('_apply_code_defaults@L1698')
                pass
            try:
                self.add_mistakes_checkbox.setChecked(False)
            except Exception:
                _log_caught('_apply_code_defaults@L1702')
                pass
            try:
                self.pause_on_punct_checkbox.setChecked(True)
            except Exception:
                _log_caught('_apply_code_defaults@L1706')
                pass
            try:
                self.mouse_jitter_checkbox.setChecked(False)
            except Exception:
                _log_caught('_apply_code_defaults@L1710')
                pass
            try:
                self.ime_friendly_checkbox.setChecked(False)
            except Exception:
                _log_caught('_apply_code_defaults@L1714')
                pass

        if not in_plain:
            _apply_code_defaults()
            if persona == 'Careful Coder':
                self.min_wpm_slider.setValue(90)
                self.max_wpm_slider.setValue(140)
            elif persona == 'Deliberate Writer':
                self.min_wpm_slider.setValue(70)
                self.max_wpm_slider.setValue(110)
            elif persona == 'Fast Messenger':
                self.min_wpm_slider.setValue(120)
                self.max_wpm_slider.setValue(180)
            # Custom (Manual Settings): keep current WPM sliders.
            return

        if persona == 'Careful Coder':
            self.min_wpm_slider.setValue(90)
            self.max_wpm_slider.setValue(140)
            if in_plain:
                _apply_plain_defaults(is_fast_messenger=False)

        elif persona == 'Deliberate Writer':
            self.min_wpm_slider.setValue(70)
            self.max_wpm_slider.setValue(110)
            if in_plain:
                _apply_plain_defaults(is_fast_messenger=False)

        elif persona == 'Fast Messenger':
            self.min_wpm_slider.setValue(120)
            self.max_wpm_slider.setValue(180)
            if in_plain:
                _apply_plain_defaults(is_fast_messenger=True)
        else:
            # Custom (Manual Settings): use the standard Plain Text defaults (unless user edits further).
            _apply_plain_defaults(is_fast_messenger=False)
            
    def start_typing(self):
        if self.is_paused:
            self.resume_typing()
            return
        if self.worker:
            return

        text = self.get_input_text()
        if not text.strip(): 
            self.status_label.setText("Status: Error - Input text cannot be empty.")
            return

        if not self._ensure_macos_typing_permissions():
            return

        # Safety: confirm CLICK macros before starting (if enabled).
        enable_macros = self._macros_enabled()
        if enable_macros and self.confirm_click_checkbox.isChecked():
            coords = []
            invalid = 0
            try:
                for m in re.finditer(r"(?i)\{\{CLICK:(.*?)\}\}", text):
                    p = (m.group(1) or "").strip()
                    try:
                        xs, ys = p.split(",", 1)
                        x, y = int(xs.strip()), int(ys.strip())
                        coords.append((x, y))
                    except Exception:
                        _log_caught('start_typing@L1779')
                        invalid += 1
            except Exception:
                _log_caught('start_typing@L1781')
                coords = []
                invalid = 0
            if coords:
                preview = "\n".join([f"• {x},{y}" for x, y in coords[:10]])
                extra = f"\n… and {len(coords) - 10} more" if len(coords) > 10 else ""
                warn_invalid = f"\n\nNote: {invalid} CLICK macro(s) look invalid and will be ignored." if invalid else ""
                lap_note = ""
                try:
                    laps = int(self.laps_spin.value())
                    if laps > 1:
                        lap_note = f"\n\nThese CLICK macros will repeat each lap (laps: {laps})."
                except Exception:
                    _log_caught('start_typing@L1793')
                    pass
                msg = (
                    "This run contains CLICK macros, which will move/click your mouse.\n\n"
                    f"{preview}{extra}{warn_invalid}{lap_note}\n\n"
                    "Continue?"
                )
                choice = QMessageBox.warning(self, "Confirm CLICK macros", msg, QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel)
                if choice != QMessageBox.Ok:
                    return

        started_from_gui = False
        source_app = ""
        try:
            started_from_gui = bool(self.isActiveWindow())
            if started_from_gui:
                source_app = self._get_active_window_identity_main()
        except Exception:
            _log_caught('start_typing@L1810')
            started_from_gui = False
            source_app = ""

        self.set_ui_for_running(True)
        self.pause_button.setText("PAUSE")
        self.pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.progress_bar.setValue(0)
        # Fallback max until worker emits an accurate value.
        try:
            self.progress_bar.setMaximum(max(1, self._compute_output_chars_per_lap_ui(text) * self.laps_spin.value()))
        except Exception:
            _log_caught('start_typing@L1821')
            self.progress_bar.setMaximum(len(text) * self.laps_spin.value())
        
        newline_mode = self._get_selected_newline_mode()

        # Optional: hint when the content contains Unicode/math and IME-friendly might be required.
        # Auto-detect itself runs inside the worker (and does not mutate UI selections).
        try:
            content_kind = self._detect_content_kind(text)
            needs_ime = (content_kind == "math") or self._contains_non_ascii(text)
            if needs_ime and not self.ime_friendly_checkbox.isChecked():
                try:
                    self.status_label.setText("Status: Tip — enable IME-friendly for Unicode/math if characters drop.")
                except Exception:
                    _log_caught('start_typing@L1834')
                    pass
        except Exception:
            _log_caught('start_typing@L1836')
            pass

        rdp_default = "auto" if platform.system() == "Windows" else "off"
        kbd_rdp_mode = str(self.settings.value("rdpKeyboardMode", rdp_default))

        worker_opts = {
            'min_wpm': self.min_wpm_slider.value(),
            'max_wpm': self.max_wpm_slider.value(),
            'type_tabs': self.type_tabs_checkbox.isChecked(),
            'typing_persona': self.persona_combo.currentText(),
            'add_mistakes': self.add_mistakes_checkbox.isChecked(),
            'pause_on_punct': self.pause_on_punct_checkbox.isChecked(),
            'newline_mode': newline_mode,
            'use_shift_enter': self.use_shift_enter_checkbox.isChecked(),
            'mouse_jitter': self.mouse_jitter_checkbox.isChecked(),
            'press_esc': self.press_esc_checkbox.isChecked(),
            'ime_friendly': self.ime_friendly_checkbox.isChecked(),
            'unicode_hex_typing': self.unicode_hex_checkbox.isChecked(),
            'compliance_mode': self.compliance_mode_checkbox.isChecked(),
            'blocked_apps': self.blocked_apps_edit.text(),
            'auto_detect': self.auto_detect_checkbox.isChecked(),
            'enable_macros': enable_macros,
            'started_from_gui': started_from_gui,
            'source_app': source_app,
            'kbd_rdp_mode': kbd_rdp_mode,
        }

        # Log start
        try:
            logger.info(f"Typing start | persona={self.persona_combo.currentText()} mode={newline_mode} min={self.min_wpm_slider.value()} max={self.max_wpm_slider.value()} ime={self.ime_friendly_checkbox.isChecked()} laps={self.laps_spin.value()} rdp_kbd={kbd_rdp_mode}")
        except Exception:
            _log_caught('start_typing@L1867')
            pass
        self.thread = QThread()
        self.worker = TypingWorker(text, self.laps_spin.value(), self.delay_spin.value(), **worker_opts)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_typing_finished)
        self.worker.paused_signal.connect(self.on_typing_paused)
        self.worker.resumed_signal.connect(self.on_typing_resumed)
        self.worker.update_status.connect(self.on_worker_status)
        self.worker.update_speed.connect(lambda w: self.wpm_display.setText(f"Current: {w:.0f} WPM"))
        self.worker.update_progress.connect(self.progress_bar.setValue)
        self.worker.set_progress_max.connect(self.progress_bar.setMaximum)
        self.worker.lap_progress.connect(lambda cl, tl: self.lap_label.setText(f"Lap: {cl}/{tl}"))
        self.worker.update_etr.connect(self.etr_label.setText)
        self.thread.start()
        
    def toggle_always_on_top(self, checked):
        # Use Qt flags on all platforms for stability
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.settings.setValue("alwaysOnTop", checked)
        self.show() # Re-show to apply flag changes

    def update_speed_labels(self):
        min_wpm, max_wpm = self.min_wpm_slider.value(), self.max_wpm_slider.value()
        if min_wpm > max_wpm:
            max_wpm = min_wpm
            self.max_wpm_slider.setValue(min_wpm)
        self.min_wpm_label.setText(f"{min_wpm} WPM")
        self.max_wpm_label.setText(f"{max_wpm} WPM")
        if self.worker:
            self.worker.update_speed_range(min_wpm, max_wpm)
        # Keep estimate/stats/preview in sync with labels
        self.schedule_text_update()

    def estimate_duration_seconds(self):
        text = self.get_input_text()
        if not text:
            return 0.0, 0.0
        min_wpm = max(1, self.min_wpm_slider.value())
        max_wpm = max(min_wpm, self.max_wpm_slider.value())
        laps = max(1, self.laps_spin.value())
        delay = max(0, self.delay_spin.value())
        mode = self._get_selected_newline_mode()
        macros_enabled = self._macros_enabled()
        type_tabs = bool(self.type_tabs_checkbox.isChecked()) if hasattr(self, "type_tabs_checkbox") else True
        pause_on_punct = bool(self.pause_on_punct_checkbox.isChecked()) if hasattr(self, "pause_on_punct_checkbox") else False
        add_mistakes = bool(self.add_mistakes_checkbox.isChecked()) if hasattr(self, "add_mistakes_checkbox") else False
        press_esc = bool(self.press_esc_checkbox.isChecked()) if hasattr(self, "press_esc_checkbox") else False
        ime = bool(self.ime_friendly_checkbox.isChecked()) if hasattr(self, "ime_friendly_checkbox") else False
        unicode_hex = bool(self.unicode_hex_checkbox.isChecked()) if hasattr(self, "unicode_hex_checkbox") else False

        pause_per_lap = self._extract_pause_seconds(text) if macros_enabled else 0.0
        macro_counts = self._count_macros(text) if macros_enabled else {"press": 0, "click": 0}

        out_per_lap = self._compute_output_chars_per_lap_ui(text)
        # Approximate macro overhead for PRESS/CLICK (PAUSE already accounted separately).
        macro_overhead_per_lap = (macro_counts.get("press", 0) * 0.02) + (macro_counts.get("click", 0) * 0.10)

        effective = self._strip_macros_ui(text) if macros_enabled else text
        try:
            effective = str(effective).replace("\r\n", "\n").replace("\r", "\n")
        except Exception:
            _log_caught('estimate_duration_seconds@L1932')
            effective = text

        typed_text_for_counts = effective
        list_lines_count = 0
        list_enter_overhead = 0.0
        list_enter_overhead_hi = 0.0

        if mode == "Smart Newlines":
            effective = apply_smart_newlines(effective)
        if mode in ("Standard", "Smart Newlines") and not type_tabs:
            effective = effective.replace("\t", "")

        if mode == "List Mode":
            try:
                raw_lines = str(text).replace("\r\n", "\n").replace("\r", "\n").splitlines()
            except Exception:
                _log_caught('estimate_duration_seconds@L1948')
                raw_lines = (text or "").splitlines()
            list_lines_count = len(raw_lines)
            stripped_lines = []
            for ln in raw_lines:
                s = (ln or "").lstrip().replace("\t", "")
                if macros_enabled:
                    s = self._strip_macros_ui(s)
                stripped_lines.append(s)
            typed_text_for_counts = "".join(stripped_lines)
            # List Mode sends an Enter after each line (fixed 0.1s) and an optional Esc pause (0.05s).
            if list_lines_count:
                base_list_overhead = 0.10 * list_lines_count
                base_list_overhead_hi = 0.10 * list_lines_count
                if press_esc:
                    base_list_overhead += 0.05 * list_lines_count
                    base_list_overhead_hi += 0.05 * list_lines_count
                list_enter_overhead = base_list_overhead
                list_enter_overhead_hi = base_list_overhead_hi

        # Base estimates
        if mode == "Paste Mode":
            # Pastes line-by-line; dominated by per-line sleeps + clipboard/hotkey overhead.
            line_ops = 1
            try:
                line_ops = max(1, len(effective.splitlines(True)))
            except Exception:
                _log_caught('estimate_duration_seconds@L1974')
                line_ops = 1
            lo = line_ops * 0.06
            hi = line_ops * 0.18
        elif ime and not unicode_hex:
            # IME-friendly uses paste instead of per-key typing (fast).
            if mode == "List Mode":
                lines = max(1, list_lines_count or len(effective.splitlines()))
                lo = (out_per_lap / 2500.0) + (0.10 * lines) + (0.05 * lines if press_esc else 0.0) + 0.2
                hi = (out_per_lap / 1500.0) + (0.10 * lines) + (0.05 * lines if press_esc else 0.0) + 0.5
            else:
                lo = out_per_lap / 2000.0 + 0.2
                hi = out_per_lap / 1200.0 + 0.5
        else:
            # Per-key typing (humanized).
            cps_fast = (max_wpm * 5) / 60.0
            cps_slow = (min_wpm * 5) / 60.0

            if mode == "List Mode":
                typed_chars = len(typed_text_for_counts)
                lo = (typed_chars / cps_fast) if cps_fast else 0.0
                hi = (typed_chars / cps_slow) if cps_slow else 0.0
                lo += list_enter_overhead
                hi += list_enter_overhead_hi
            else:
                lo = (out_per_lap / cps_fast) if cps_fast else 0.0
                hi = (out_per_lap / cps_slow) if cps_slow else 0.0

                if press_esc:
                    try:
                        newline_count = effective.count("\n")
                    except Exception:
                        _log_caught('estimate_duration_seconds@L2005')
                        newline_count = 0
                    lo += 0.03 * newline_count
                    hi += 0.03 * newline_count

            # Extra humanization overheads (only apply to per-key typing).
            try:
                punct_a = sum(1 for ch in typed_text_for_counts if ch in ".,?!")
                punct_b = sum(1 for ch in typed_text_for_counts if ch in "()[]{}")
                boundaries = sum(1 for ch in typed_text_for_counts if ch in " \t")
                eligible = sum(1 for ch in typed_text_for_counts if (ch.lower() in KEY_ADJACENCY))
            except Exception:
                _log_caught('estimate_duration_seconds@L2016')
                punct_a = punct_b = boundaries = eligible = 0

            if pause_on_punct:
                lo += (punct_a * 0.08) + (punct_b * 0.10)
                hi += (punct_a * 0.15) + (punct_b * 0.30)

            # Expected "thinking" pauses at word boundaries (~4% chance).
            lo += boundaries * 0.04 * 0.12
            hi += boundaries * 0.04 * 0.35

            if add_mistakes:
                expected_mistakes = eligible * MISTAKE_CHANCE
                lo += expected_mistakes * 0.15
                hi += expected_mistakes * 0.40
        # Multiply by laps and add start delay + macro timing
        pause_total = pause_per_lap * laps
        macro_overhead_total = macro_overhead_per_lap * laps
        return (lo * laps + delay + pause_total + macro_overhead_total, hi * laps + delay + pause_total + macro_overhead_total)

    def update_preview(self):
        lo, hi = self.estimate_duration_seconds()
        if lo == 0 and hi == 0:
            self.preview_label.setText("Estimated: -- s")
            return
        def _fmt(sec: float) -> str:
            s = int(round(max(0.0, sec)))
            h, rem = divmod(s, 3600)
            m, s2 = divmod(rem, 60)
            return f"{h}:{m:02d}:{s2:02d}" if h else f"{m}:{s2:02d}"
        self.preview_label.setText(f"Estimated: {_fmt(lo)}–{_fmt(hi)}")

    def stop_typing(self):
        try:
            self._cancel_resume_countdown(silent=True)
        except Exception:
            _log_caught('stop_typing@L2051')
            pass
        if self.worker:
            self.worker.stop()
        self.is_paused = False
        try:
            logger.info("Typing stop requested")
        except Exception:
            _log_caught('stop_typing@L2058')
            pass

    def resume_typing(self):
        if not (self.worker and self.is_paused):
            return
        # If a resume countdown is already running, clicking again cancels it.
        if getattr(self, "_resume_countdown_active", False):
            self._cancel_resume_countdown()
            return
        self._start_resume_countdown(4)

    def on_typing_paused(self):
        self.is_paused = True
        try:
            self._cancel_resume_countdown(silent=True)
        except Exception:
            _log_caught('on_typing_paused@L2074')
            pass
        # Keep START reserved for starting a new run; use PAUSE/RESUME for pausing.
        self.start_button.setEnabled(False)
        try:
            self.pause_button.setText("RESUME")
            self.pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        except Exception:
            _log_caught('on_typing_paused@L2081')
            pass
        # Allow tuning settings while paused.
        self._set_ui_for_paused(True)
        self._set_status_state("paused")
        self.status_label.setText("Status: Paused. You can adjust settings. Resuming uses a 4s countdown.")

    def on_typing_resumed(self):
        try:
            self._cancel_resume_countdown(silent=True)
        except Exception:
            _log_caught('on_typing_resumed@L2091')
            pass
        self.is_paused = False
        self.set_ui_for_running(True)
        self.update_button_hotkey_text()
        try:
            self.pause_button.setText("PAUSE")
            self.pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        except Exception:
            _log_caught('on_typing_resumed@L2099')
            pass
        self.status_label.setText("Status: Resumed typing...")

    def on_typing_finished(self):
        self.is_paused = False
        try:
            self._cancel_resume_countdown(silent=True)
        except Exception:
            _log_caught('on_typing_finished@L2107')
            pass
        self.set_ui_for_running(False)
        self.update_button_hotkey_text()
        try:
            self.pause_button.setText("PAUSE")
            self.pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        except Exception:
            _log_caught('on_typing_finished@L2114')
            pass
        self.wpm_display.setText("Current: --- WPM")
        self.etr_label.setText("ETR: --:--")
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        self.thread, self.worker = None, None
        try:
            logger.info("Typing finished")
        except Exception:
            _log_caught('on_typing_finished@L2124')
            pass

    def show_about_dialog(self):
        self.stop_listener()
        dialog = AboutDialog(
            app_name=APP_NAME,
            app_version=APP_VERSION,
            app_author=APP_AUTHOR,
            contact_email=CONTACT_EMAIL,
            app_copyright_year=APP_COPYRIGHT_YEAR,
            app_signature=APP_SIGNATURE,
            contact_website=CONTACT_WEBSITE,
            parent=self,
        )
        dialog.exec_()
        self.start_listener()

    def show_settings_dialog(self):
        # Stop the listener before the dialog so user-typed shortcuts in the
        # capture widget aren't intercepted as global hotkeys.
        self.stop_listener()
        dialog = SettingsDialog(
            settings=self.settings,
            default_start_hotkey=DEFAULT_START_HOTKEY,
            default_stop_hotkey=DEFAULT_STOP_HOTKEY,
            default_resume_hotkey=DEFAULT_RESUME_HOTKEY,
            parent=self,
        )
        accepted = dialog.exec_() == QDialog.Accepted
        if accepted:
            self.update_button_hotkey_text()
            QMessageBox.information(
                self, "Settings Saved",
                "Hotkey settings have been updated and the listener was restarted.",
            )
        # start_listener() always rebuilds from the current QSettings, so a
        # single call after the dialog correctly binds whichever hotkeys are
        # now in effect (saved on Accept, unchanged on Cancel).
        self.start_listener()

    def show_help_dialog(self):
        self.stop_listener()
        dialog = HelpDialog(parent=self)
        dialog.exec_()
        self.start_listener()

    def show_diagnostics_dialog(self):
        self.stop_listener()
        platform_ref = self._platform
        dialog = DiagnosticsDialog(
            app_name=APP_NAME,
            app_version=APP_VERSION,
            log_file=LOG_FILE,
            log_dir=LOG_DIR,
            accessibility_trusted_fn=(
                (lambda: platform_ref.accessibility_trusted(prompt=False))
                if platform_ref.name == "macos" else None
            ),
            parent=self,
        )
        dialog.exec_()
        self.start_listener()

    def show_dry_run_preview(self):
        # Non-modal so the main input stays accessible while preview runs
        try:
            if hasattr(self, 'dry_run_dialog') and self.dry_run_dialog and self.dry_run_dialog.isVisible():
                self.dry_run_dialog.activateWindow()
                self.dry_run_dialog.raise_()
                return
        except Exception:
            _log_caught('show_dry_run_preview@L2195')
            pass
        self.stop_listener()
        self.dry_run_dialog = DryRunDialog(self)
        self.dry_run_dialog.setWindowModality(Qt.NonModal)
        # When closed, clear reference and restart listener
        def _cleanup():
            try:
                self.start_listener()
            except Exception:
                _log_caught('_cleanup@L2204')
                pass
            self.dry_run_dialog = None
        self.dry_run_dialog.finished.connect(lambda _=0: _cleanup())
        self.dry_run_dialog.rejected.connect(lambda: _cleanup())
        self.dry_run_dialog.show()
        # Re-enable listener immediately since dialog is modeless
        self.start_listener()

    def export_profiles(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Profiles to JSON", "profiles.json", "*.json")
        if not path:
            return
        try:
            data = {}
            self.settings.beginGroup("Profiles")
            for name in self.settings.childGroups():
                self.settings.beginGroup(name)
                prof = {}
                for key in self.settings.childKeys():
                    prof[key] = self.settings.value(key)
                data[name] = prof
                self.settings.endGroup()
            self.settings.endGroup()
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Export Complete", f"Exported {len(data)} profiles to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Could not export profiles:\n{e}")

    def import_profiles(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Profiles from JSON", "", "*.json")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            count = 0
            self.settings.beginGroup("Profiles")
            for name, prof in data.items():
                self.settings.beginGroup(name)
                for key, val in prof.items():
                    self.settings.setValue(key, val)
                self.settings.endGroup()
                count += 1
            self.settings.endGroup()
            self.settings.sync()
            self.populate_profiles_menu()
            QMessageBox.information(self, "Import Complete", f"Imported {count} profiles from:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Could not import profiles:\n{e}")

    def update_button_hotkey_text(self):
        start_raw = self.settings.value("startHotkey", DEFAULT_START_HOTKEY)
        stop_raw = self.settings.value("stopHotkey", DEFAULT_STOP_HOTKEY)
        try:
            start = QKeySequence(str(start_raw)).toString(QKeySequence.NativeText) or str(start_raw)
        except Exception:
            _log_caught('update_button_hotkey_text@L2261')
            start = str(start_raw)
        try:
            stop = QKeySequence(str(stop_raw)).toString(QKeySequence.NativeText) or str(stop_raw)
        except Exception:
            _log_caught('update_button_hotkey_text@L2265')
            stop = str(stop_raw)
        self.start_button.setText(f"START ({start})")
        self.stop_button.setText(f"STOP ({stop})")
        try:
            if hasattr(self, "hotkey_hint_label"):
                self.hotkey_hint_label.setText(f"⌨  {start}  ·  {stop}")
        except Exception:
            _log_caught('update_button_hotkey_text@L2272')
            pass

    def _build_hotkey_listener(self) -> HotkeyListener:
        return HotkeyListener({
            self.settings.value("startHotkey",  DEFAULT_START_HOTKEY):  self.start_typing_signal.emit,
            self.settings.value("stopHotkey",   DEFAULT_STOP_HOTKEY):   self.stop_typing_signal.emit,
            self.settings.value("resumeHotkey", DEFAULT_RESUME_HOTKEY): self.resume_typing_signal.emit,
        })

    def start_listener(self):
        # Respect setting; disable on macOS 15 by default
        default_enable = True
        if platform.system() == "Darwin":
            try:
                major = int(platform.mac_ver()[0].split('.')[0]) if platform.mac_ver()[0] else 0
            except Exception:
                _log_caught('start_listener@L2288')
                major = 0
            if major >= 15:
                default_enable = False
        if not self.settings.value("enableGlobalHotkeys", default_enable, type=bool):
            self.status_label.setText("Status: Global hotkeys disabled. Use buttons or enable in Settings.")
            return
        if self.hotkey_listener and self.hotkey_listener.is_running():
            return
        # Rebuild each start so a settings-edit picks up new hotkey strings.
        self.hotkey_listener = self._build_hotkey_listener()
        self.hotkey_listener.start()

    def stop_listener(self):
        if self.hotkey_listener:
            self.hotkey_listener.stop()

    # --- In-app update checker ---
    def _start_update_check(self, verbose: bool = False, force: bool = False):
        """Spin up a worker thread that pings the GitHub Releases feed.

        Background (verbose=False) checks fire at most once an hour and
        stay silent unless an update is available. The Help → Check for
        Updates action passes verbose=True so it always reports status.

        ``force=True`` bypasses the 1-hour throttle. Used by the launch
        check, where the user just opened the app and "is there an
        update?" is the single most expected answer they came for.
        """
        # Remember whether this check was user-initiated so _on_update_available
        # can decide whether to also pop the modal (verbose) or just the
        # non-modal banner (background sweep).
        self._update_check_was_verbose = bool(verbose)
        if not UPDATE_FEED_URL:
            if verbose:
                QMessageBox.information(self, "Updates",
                                        "Update checks are not configured for this build.")
            return
        # Throttle background checks. Manual + forced checks bypass it.
        # 1 hour for periodic / focus-return checks — the banner should
        # appear within a reasonable window of a new release going live,
        # not the next day.
        if not verbose and not force:
            try:
                last = float(self.settings.value("updateCheckLastEpoch", 0.0))
            except Exception:
                _log_caught('_start_update_check@L2322')
                last = 0.0
            if (time.time() - last) < 3600:
                return
        existing = getattr(self, "_update_thread", None)
        if existing is not None:
            try:
                if existing.isRunning():
                    return
            except RuntimeError:
                # Wrapper survives but the C++ QThread was deleteLater'd
                # after the previous check; treat the slot as free.
                _log_caught('_start_update_check@L2331')
                pass
        self._update_verbose = bool(verbose)
        self._update_worker = UpdateChecker(UPDATE_FEED_URL, APP_VERSION)
        self._update_thread = QThread(self)
        self._update_worker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.updateAvailable.connect(self._on_update_available)
        self._update_worker.upToDate.connect(self._on_update_up_to_date)
        self._update_worker.checkFailed.connect(self._on_update_failed)
        for sig in (self._update_worker.updateAvailable,
                    self._update_worker.upToDate,
                    self._update_worker.checkFailed):
            sig.connect(self._update_thread.quit)
            sig.connect(self._update_worker.deleteLater)
        # Clear our Python refs first so the next click sees None and builds
        # a fresh worker/thread; deleteLater fires after.
        self._update_thread.finished.connect(self._on_update_thread_finished)
        self._update_thread.finished.connect(self._update_thread.deleteLater)
        self._update_thread.start()
        self.settings.setValue("updateCheckLastEpoch", time.time())

    def _on_update_thread_finished(self):
        self._update_thread = None
        self._update_worker = None

    def _on_update_available(self, version, url, body, asset_info):
        try:
            logger.info(f"Update available: {version} (current {APP_VERSION})")
        except Exception:
            _log_caught('_on_update_available@L2362')

        # Background (silent) check: show the non-modal banner only.
        # Foreground (Help → Check for Updates, verbose=True) check:
        # also show the modal, since the user explicitly clicked
        # "check" and expects a response.
        self._show_update_banner(version, url, body, asset_info)

        if not getattr(self, "_update_check_was_verbose", False):
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("Update available")
        msg.setIcon(QMessageBox.Information)
        msg.setText(f"<b>{APP_NAME} {version}</b> is available. You're on {APP_VERSION}.")
        if body:
            short = body if len(body) < 600 else body[:600] + "…"
            msg.setInformativeText(short)
        install_btn = None
        if asset_info:
            size_mb = (asset_info.get("size") or 0) / (1024 * 1024)
            label = "Download && install"
            if size_mb >= 1:
                label = f"Download && install ({size_mb:.0f} MB)"
            install_btn = msg.addButton(label, QMessageBox.AcceptRole)
            msg.setDefaultButton(install_btn)
        page_btn = msg.addButton("Open download page", QMessageBox.ActionRole)
        msg.addButton("Later", QMessageBox.RejectRole)
        msg.exec_()
        clicked = msg.clickedButton()
        if install_btn is not None and clicked is install_btn:
            self._start_installer_download(asset_info["url"], asset_info["name"])
        elif clicked is page_btn:
            try:
                QDesktopServices.openUrl(QUrl(url or UPDATE_DOWNLOAD_PAGE))
            except Exception:
                _log_caught('_on_update_available@L2388')

    def _sweep_stale_downloads(self) -> None:
        """Remove leftover NexusTyper download artifacts from ~/Downloads.

        Cleans up:
          - `*.part` files older than 14 days (interrupted downloads
            that the user clearly isn't coming back to resume)
          - matching `*.part.meta` sidecars (always paired with .part;
            if the .part is gone, the meta is useless)
          - older versioned installer artifacts that pre-date the
            unversioned-filename switch (e.g.
            "NexusTyper-Pro-v3.7.3-macOS.pkg" left over from before
            v3.7.4 — they'd otherwise sit in Downloads forever)

        Conservative: only touches files whose names start with
        "NexusTyper-Pro-" or "nexustyper-pro_" so we can't accidentally
        delete an unrelated download.
        """
        try:
            downloads = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.isdir(downloads):
                return
            now = time.time()
            stale_after = 14 * 24 * 60 * 60  # 14 days in seconds
            for name in os.listdir(downloads):
                low = name.lower()
                if not (low.startswith("nexustyper-pro-") or low.startswith("nexustyper-pro_")):
                    continue
                path = os.path.join(downloads, name)
                try:
                    if not os.path.isfile(path):
                        continue
                    age = now - os.path.getmtime(path)
                except OSError:
                    continue
                drop = False
                # Always drop stale partials. The downloader's resume
                # path keeps recent ones; a .part this old means the
                # user gave up on that download.
                if name.endswith(".part") or name.endswith(".part.meta"):
                    if age > stale_after:
                        drop = True
                # Drop *versioned* installer leftovers (the new naming
                # is unversioned). The "v" or digit before "-macOS" /
                # "-Windows" / "-Linux" / "_amd64" is the giveaway.
                elif name.endswith((".pkg", ".dmg", ".exe", ".tar.gz", ".deb", ".zip")):
                    import re as _re
                    if _re.search(r"-v?\d", name):
                        drop = True
                if drop:
                    try:
                        os.remove(path)
                        logger.info(f"Swept stale download: {name}")
                    except OSError:
                        _log_caught("_sweep_stale_downloads: remove")
        except Exception:
            _log_caught("_sweep_stale_downloads")

    def _build_update_banner(self, parent_layout):
        """Insert a hidden update-available banner under the masthead.

        Stays hidden until ``_show_update_banner`` is called from the
        update-check signal handler. Replaces the previous modal-only
        flow so users notice updates without the dialog popping over
        whatever they were doing.
        """
        self.update_banner = QFrame(self)
        self.update_banner.setObjectName("updateBanner")
        self.update_banner.setVisible(False)
        bl = QHBoxLayout(self.update_banner)
        bl.setContentsMargins(12, 8, 12, 8)
        bl.setSpacing(10)
        self.update_banner_label = QLabel("", self.update_banner)
        self.update_banner_label.setObjectName("updateBannerLabel")
        self.update_banner_label.setWordWrap(True)
        bl.addWidget(self.update_banner_label, 1)
        self.update_banner_button = QPushButton("Update", self.update_banner)
        self.update_banner_button.setObjectName("updateBannerButton")
        self.update_banner_button.clicked.connect(self._on_update_banner_clicked)
        bl.addWidget(self.update_banner_button, 0)
        self.update_banner_dismiss = QToolButton(self.update_banner)
        self.update_banner_dismiss.setText("×")
        self.update_banner_dismiss.setObjectName("updateBannerDismiss")
        self.update_banner_dismiss.setToolTip("Dismiss until next launch")
        self.update_banner_dismiss.clicked.connect(self._on_update_banner_dismissed)
        bl.addWidget(self.update_banner_dismiss, 0)
        parent_layout.addWidget(self.update_banner)
        self._pending_update = None
        self._update_banner_dismissed_this_session = False

    def _show_update_banner(self, version, url, body, asset_info):
        """Populate and reveal the in-window update banner."""
        self._pending_update = (version, url, body, asset_info)
        if getattr(self, "_update_banner_dismissed_this_session", False):
            # User clicked the × in this session; respect that until next
            # launch (where __init__ rebuilds the banner state).
            return
        if not hasattr(self, "update_banner"):
            return
        size_text = ""
        if asset_info:
            size_mb = (asset_info.get("size") or 0) / (1024 * 1024)
            if size_mb >= 1:
                size_text = f" ({size_mb:.0f} MB)"
        self.update_banner_label.setText(
            f"<b>{APP_NAME} {version}</b> is available — you're on "
            f"{APP_VERSION}.{size_text}"
        )
        # If we have a downloadable asset for this platform, the button
        # downloads + opens it. If not, it just opens the release page.
        if asset_info:
            self.update_banner_button.setText("Update")
        else:
            self.update_banner_button.setText("Open release page")
        self.update_banner.setVisible(True)

    def _on_update_banner_clicked(self):
        pending = getattr(self, "_pending_update", None)
        if not pending:
            return
        version, url, _body, asset_info = pending
        if asset_info:
            self._start_installer_download(asset_info["url"], asset_info["name"])
        else:
            try:
                QDesktopServices.openUrl(QUrl(url or UPDATE_DOWNLOAD_PAGE))
            except Exception:
                _log_caught("_on_update_banner_clicked: openUrl")

    def _on_update_banner_dismissed(self):
        self._update_banner_dismissed_this_session = True
        try:
            self.update_banner.setVisible(False)
        except Exception:
            _log_caught("_on_update_banner_dismissed")

    def _start_installer_download(self, url: str, filename: str):
        """Stream the installer to ~/Downloads with a progress dialog, then
        hand it to the OS so the native installer can launch (Apple
        Installer for .pkg, Inno Setup wizard for Setup.exe, the system
        package viewer for .deb).
        """
        existing = getattr(self, "_installer_thread", None)
        if existing is not None:
            try:
                if existing.isRunning():
                    return
            except RuntimeError:
                # Wrapper survives but the C++ QThread was deleteLater'd
                # after the previous download; treat the slot as free.
                _log_caught('_start_installer_download@L2402')
                pass

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.isdir(downloads):
            try:
                import tempfile
                downloads = tempfile.gettempdir()
            except Exception:
                _log_caught('_start_installer_download@L2412')
                downloads = os.path.expanduser("~")
        dest = os.path.join(downloads, filename)

        progress = QProgressDialog(
            f"Downloading {filename}…", "Cancel", 0, 0, self
        )
        progress.setWindowTitle("Downloading update")
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setWindowModality(Qt.WindowModal)

        worker = InstallerDownloader(url, dest)
        thread = QThread(self)
        worker.moveToThread(thread)
        self._installer_worker = worker
        self._installer_thread = thread

        def on_progress(done, total):
            mb_done = done / (1024 * 1024)
            if total > 0:
                progress.setMaximum(total)
                progress.setValue(done)
                mb_total = total / (1024 * 1024)
                progress.setLabelText(
                    f"Downloading {filename}\n{mb_done:.1f} / {mb_total:.1f} MB"
                )
            else:
                progress.setLabelText(
                    f"Downloading {filename}\n{mb_done:.1f} MB"
                )

        def on_finished(path):
            progress.reset()
            progress.close()
            thread.quit()
            try:
                logger.info(f"Update installer downloaded: {path}")
            except Exception:
                _log_caught('on_finished@L2451')
                pass
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            except Exception:
                _log_caught('on_finished@L2455')
                pass
            QMessageBox.information(
                self,
                "Update downloaded",
                f"Saved to:\n{path}\n\nThe installer should now launch — "
                f"follow its prompts to finish updating.",
            )

        def on_failed(reason):
            progress.reset()
            progress.close()
            thread.quit()
            try:
                logger.info(f"Update download: {reason}")
            except Exception:
                _log_caught('on_failed@L2470')
                pass
            if "canceled" not in reason.lower():
                QMessageBox.warning(self, "Download failed", reason)

        def _on_installer_thread_finished():
            self._installer_thread = None
            self._installer_worker = None

        thread.started.connect(worker.run)
        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        progress.canceled.connect(worker.cancel)
        thread.finished.connect(_on_installer_thread_finished)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_update_up_to_date(self, version):
        if getattr(self, "_update_verbose", False):
            QMessageBox.information(
                self, "Up to date",
                f"You're running the latest release ({APP_VERSION}).")

    def _on_update_failed(self, reason):
        try:
            logger.info(f"Update check: {reason}")
        except Exception:
            _log_caught('_on_update_failed@L2499')
            pass
        if getattr(self, "_update_verbose", False):
            QMessageBox.warning(self, "Update check failed", reason)

    def toggle_dark_mode(self, checked):
        assets = ensure_qss_assets()
        sheet = DARK_STYLESHEET if checked else LIGHT_STYLESHEET
        # Replace `{token}` placeholders with asset URLs without going through
        # str.format() (which would also try to parse the QSS `{...}` blocks).
        for token in ("check_white", "dot_dark", "dot_light",
                      "chev_up_dark", "chev_down_dark",
                      "chev_up_light", "chev_down_light"):
            sheet = sheet.replace("{" + token + "}", assets.get(token, ""))
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(sheet)
        else:
            self.setStyleSheet(sheet)
        self.settings.setValue("darkMode", checked)

    def _toggle_sidebar(self, hide):
        """Hide/show the settings sidebar with a short animation.

        Remembers the previous open width so toggling restores it.
        """
        try:
            sizes = self.splitter.sizes()
            total = sum(sizes) if sizes else self.width()
        except Exception:
            _log_caught('_toggle_sidebar@L2528')
            sizes, total = [0, 0], self.width()
        if hide:
            if sizes and sizes[0] > 1:
                self._sidebar_last_width = sizes[0]
            target_left = 0
        else:
            target = max(getattr(self, "_sidebar_last_width", 360), 260)
            target_left = min(target, max(total - 400, 260))
        self._animate_splitter(sizes[0] if sizes else 0, target_left, total)
        # Keep the menu action in sync.
        try:
            self.toggle_sidebar_action.blockSignals(True)
            self.toggle_sidebar_action.setChecked(hide)
        finally:
            try:
                self.toggle_sidebar_action.blockSignals(False)
            except Exception:
                _log_caught('_toggle_sidebar@L2545')
                pass

    def _animate_splitter(self, start, end, total):
        anim = getattr(self, "_sidebar_anim", None)
        if anim is not None:
            try:
                anim.stop()
            except Exception:
                _log_caught('_animate_splitter@L2553')
                pass
        anim = QVariantAnimation(self)
        anim.setStartValue(int(start))
        anim.setEndValue(int(end))
        anim.setDuration(180)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def on_value(v):
            try:
                left = int(v)
                self.splitter.setSizes([left, max(total - left, 1)])
            except Exception:
                _log_caught('on_value@L2565')
                pass

        anim.valueChanged.connect(on_value)
        self._sidebar_anim = anim
        anim.start()

    def _build_wordmark_logo(self, size=22):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            # Rounded square in accent cyan, with a stroked "caret" mark inside.
            painter.setBrush(QColor("#06B6D4"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(0, 0, size, size, 6, 6)
            pen = QPen(QColor("#0F172A"))
            pen.setWidthF(max(1.6, size * 0.10))
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            inset = size * 0.27
            path = QPainterPath()
            path.moveTo(inset, inset)
            path.lineTo(inset, size - inset)
            path.moveTo(inset, inset)
            path.lineTo(size - inset, size - inset)
            path.moveTo(size - inset, inset)
            path.lineTo(size - inset, size - inset)
            painter.drawPath(path)
        finally:
            painter.end()
        return pix

    def _on_preview_toggle(self, checked):
        try:
            self.preview_panel.setVisible(bool(checked))
            self.preview_toggle.setText(
                ("▾  Output preview" if checked else "▸  Output preview")
            )
        except Exception:
            _log_caught('_on_preview_toggle@L2607')
            pass

    def _on_splitter_moved(self, *_):
        try:
            sizes = self.splitter.sizes()
        except Exception:
            _log_caught('_on_splitter_moved@L2613')
            return
        if not sizes:
            return
        is_hidden = sizes[0] <= 1
        if not is_hidden:
            self._sidebar_last_width = sizes[0]
        ctrl = getattr(self, "toggle_sidebar_action", None)
        if ctrl is None or ctrl.isChecked() == is_hidden:
            return
        try:
            ctrl.blockSignals(True)
            ctrl.setChecked(is_hidden)
        finally:
            try:
                ctrl.blockSignals(False)
            except Exception:
                _log_caught('_on_splitter_moved@L2629')
                pass

    def populate_profiles_menu(self):
        self.load_profile_menu.clear()
        self.settings.beginGroup("Profiles")
        for name in self.settings.childGroups():
            action = QAction(name, self)
            action.triggered.connect(lambda ch, n=name: self.load_profile(n))
            self.load_profile_menu.addAction(action)
        self.settings.endGroup()

    def get_savable_widgets(self):
        return {
            "input_mode": self.input_tabs,
            "plain_text": self.plain_text_edit,
            "code_text": self.code_text_edit,
            "laps": self.laps_spin,
            "delay": self.delay_spin,
            "persona": self.persona_combo, "min_wpm": self.min_wpm_slider,
            "max_wpm": self.max_wpm_slider, "add_mistakes": self.add_mistakes_checkbox,
            "pause_on_punct": self.pause_on_punct_checkbox,
            "newline_standard": self.standard_radio, "newline_smart": self.smart_radio,
            "newline_list": self.list_mode_radio, "newline_paste": self.paste_mode_radio,
            "use_shift_enter": self.use_shift_enter_checkbox,
            "type_tabs": self.type_tabs_checkbox,
            "press_esc": self.press_esc_checkbox,
            "mouse_jitter": self.mouse_jitter_checkbox,
            "auto_detect": self.auto_detect_checkbox,
            "ime_friendly": self.ime_friendly_checkbox,
            "unicode_hex": self.unicode_hex_checkbox,
            "compliance_mode": self.compliance_mode_checkbox,
            "blocked_apps": self.blocked_apps_edit,
            "enable_macros": self.enable_macros_checkbox,
            "confirm_click": self.confirm_click_checkbox,
        }

    def load_profile(self, name):
        path = f"Profiles/{name}"
        self.settings.beginGroup(path)
        for key, widget in self.get_savable_widgets().items():
            if self.settings.contains(key):
                if isinstance(widget, (QCheckBox, QRadioButton)):
                    widget.setChecked(self.settings.value(key, type=bool))
                elif isinstance(widget, (QSlider, QSpinBox)):
                    widget.setValue(self.settings.value(key, type=int))
                elif isinstance(widget, QComboBox):
                    widget.setCurrentText(self.settings.value(key))
                elif isinstance(widget, QLineEdit):
                    widget.setText(self.settings.value(key))
                elif isinstance(widget, QTabWidget):
                    widget.setCurrentIndex(self.settings.value(key, 0, type=int))
                elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
                    widget.setPlainText(self.settings.value(key))
        self.settings.endGroup()
        self.update_speed_labels()
        self.schedule_text_update()

    def save_profile(self):
        name, ok = QInputDialog.getText(self, "Save Profile", "Enter profile name:")
        if not ok or not name.strip():
            return
        try:
            path = f"Profiles/{name}"
            self.settings.beginGroup(path)
            for key, widget in self.get_savable_widgets().items():
                if isinstance(widget, (QCheckBox, QRadioButton)):
                    self.settings.setValue(key, widget.isChecked())
                elif isinstance(widget, (QSlider, QSpinBox)):
                    self.settings.setValue(key, widget.value())
                elif isinstance(widget, QComboBox):
                    self.settings.setValue(key, widget.currentText())
                elif isinstance(widget, QLineEdit):
                    self.settings.setValue(key, widget.text())
                elif isinstance(widget, QTabWidget):
                    self.settings.setValue(key, widget.currentIndex())
                elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
                    self.settings.setValue(key, widget.toPlainText())
            self.settings.endGroup()
            self.populate_profiles_menu()
        except Exception as e:
            QMessageBox.critical(self, "Error saving profile", f"Could not save profile:\n{e}")
    
    def delete_profile(self, name):
        # remove the entire group for that profile
        path = f"Profiles/{name}"
        self.settings.beginGroup(path)
        self.settings.remove("")      # remove all keys under this group
        self.settings.endGroup()
        self.settings.sync()
        self.populate_profiles_menu()

    def delete_profile_prompt(self):
        self.settings.beginGroup("Profiles")
        names = self.settings.childGroups()
        self.settings.endGroup()
        if not names:
            QMessageBox.information(self, "Delete Profile", "No saved profiles to delete.")
            return
        name, ok = QInputDialog.getItem(self, "Delete Profile", "Select a profile to delete:", names, 0, False)
        if not ok or not name:
            return
        confirm = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete profile '{name}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm == QMessageBox.Yes:
            try:
                self.delete_profile(name)
                QMessageBox.information(self, "Profile Deleted", f"Profile '{name}' was deleted.")
            except Exception as e:
                QMessageBox.critical(self, "Delete Failed", f"Could not delete profile:\n{e}")


    def clean_whitespace(self):
        text = self.get_input_text()
        if text is None:
            return
        # Run the full AI-paste sanitizer first so &amp;, zero-width chars,
        # smart quotes, and exotic spaces all get fixed alongside whitespace.
        text = sanitize_ai_text(str(text))
        # Trim trailing spaces, preserving line structure (including trailing blank lines).
        lines = [line.rstrip() for line in text.split('\n')]
        cleaned = '\n'.join(lines)
        # Plain Text mode: also collapse excessive blank lines and trim outer whitespace.
        if self.input_mode_name() == "Plain Text":
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
        self.set_input_text(cleaned)

    def decode_html_entities(self):
        text = self.get_input_text()
        if text is None:
            return
        self.set_input_text(html.unescape(str(text)))

    def fix_ai_paste_artifacts(self):
        text = self.get_input_text()
        if text is None:
            return
        self.set_input_text(sanitize_ai_text(str(text)))

    def to_uppercase(self):
        self.set_input_text(self.get_input_text().upper())

    def to_lowercase(self):
        self.set_input_text(self.get_input_text().lower())

    def to_sentence_case(self):
        text = self.get_input_text().lower()
        sentences = re.split(r'([.!?]\s+)', text)
        result = ''
        for i in range(len(sentences)):
            sentence_part = sentences[i]
            if i % 2 == 0 and sentence_part.strip():
                for j, char in enumerate(sentence_part):
                    if char.isalpha():
                        sentence_part = sentence_part[:j] + char.upper() + sentence_part[j+1:]
                        break
            result += sentence_part
        self.set_input_text(result)

    _CODE_EXTENSIONS = frozenset({
        '.py', '.pyw', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cc', '.cpp', '.h', '.hpp',
        '.cs', '.go', '.rs', '.swift', '.kt', '.kts', '.m', '.mm', '.php', '.rb', '.sh', '.bash',
        '.zsh', '.ps1', '.sql', '.toml', '.yaml', '.yml', '.json', '.xml', '.ini', '.cfg', '.gradle',
    })

    def load_text_from_path(self, path):
        try:
            text = _fi_load(path)
        except FileIngestionError as exc:
            QMessageBox.warning(self, "Error", f"Could not open file: {exc}")
            return
        try:
            ext = os.path.splitext(path)[1].lower()
            prefer_code = ext in self._CODE_EXTENSIONS or bool(text and looks_like_code(text))
            self.input_tabs.setCurrentIndex(1 if prefer_code else 0)
        except Exception:
            _log_caught('load_text_from_path@L2803')
            pass
        self.set_input_text(text)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Text File", "", supported_open_filter())
        if path:
            self.load_text_from_path(path)

    def save_file(self):
        default_filter = "Text Files (*.txt)" if self.input_mode_name() == "Plain Text" else "Code Files (*.py *.txt)"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save File As...", "", supported_save_filter(), default_filter,
        )
        if not path:
            return
        try:
            _fi_save(self.get_input_text(), path)
        except FileIngestionError as exc:
            QMessageBox.warning(self, "Error", f"Could not save file: {exc}")

    def load_settings(self):
        if geom := self.settings.value("geometry"):
            self.restoreGeometry(geom)
        dark = self.settings.value("darkMode", False, type=bool)
        self.dark_mode_action.setChecked(dark)
        self.toggle_dark_mode(dark)
        
        always_on_top = self.settings.value("alwaysOnTop", False, type=bool)
        self.always_on_top_action.setChecked(always_on_top)
        
        if always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.update_button_hotkey_text()
        try:
            self._suppress_input_mode_changed = True
            idx = self.settings.value("inputMode", 0, type=int)
            self.input_tabs.setCurrentIndex(1 if int(idx) == 1 else 0)
            self._last_input_tab_index = int(self.input_tabs.currentIndex())
        except Exception:
            _log_caught('load_settings@L2843')
            pass
        finally:
            self._suppress_input_mode_changed = False
        # Restore last UI state (without restoring the text field content).
        try:
            sizes = self.settings.value("splitterSizes")
            if sizes and hasattr(self, "splitter"):
                if isinstance(sizes, str):
                    nums = re.findall(r"\d+", sizes)
                    sizes = [int(n) for n in nums]
                if isinstance(sizes, (list, tuple)) and len(sizes) >= 2:
                    left = max(0, int(sizes[0]))
                    right = max(0, int(sizes[1]))
                    # Collapsed sidebar (left == 0) is a valid state — preserve it.
                    if left + right <= 0:
                        left, right = 360, max(560, self.width() - 360)
                    self.splitter.setSizes([left, right])
                    if left > 0:
                        self._sidebar_last_width = left
                    self._on_splitter_moved()
        except Exception:
            _log_caught('load_settings@L2864')
            pass
        try:
            self.settings.beginGroup("UI")
            persona = self.settings.value("persona", "", type=str)
            if persona:
                self.persona_combo.setCurrentText(persona)
            self.laps_spin.setValue(self.settings.value("laps", DEFAULT_LAPS, type=int))
            self.delay_spin.setValue(self.settings.value("delay", DEFAULT_DELAY, type=int))
            self.min_wpm_slider.setValue(self.settings.value("min_wpm", DEFAULT_MIN_WPM, type=int))
            self.max_wpm_slider.setValue(self.settings.value("max_wpm", DEFAULT_MAX_WPM, type=int))
            self.add_mistakes_checkbox.setChecked(self.settings.value("add_mistakes", False, type=bool))
            self.pause_on_punct_checkbox.setChecked(self.settings.value("pause_on_punct", True, type=bool))
            mode = self.settings.value("newline_mode", "List Mode", type=str)
            if mode == "Paste Mode":
                self.paste_mode_radio.setChecked(True)
            elif mode == "Smart Newlines":
                self.smart_radio.setChecked(True)
            elif mode == "Standard":
                self.standard_radio.setChecked(True)
            else:
                self.list_mode_radio.setChecked(True)
            self.use_shift_enter_checkbox.setChecked(self.settings.value("use_shift_enter", False, type=bool))
            self.type_tabs_checkbox.setChecked(self.settings.value("type_tabs", True, type=bool))
            self.press_esc_checkbox.setChecked(self.settings.value("press_esc", True, type=bool))
            self.mouse_jitter_checkbox.setChecked(self.settings.value("mouse_jitter", False, type=bool))
            self.auto_detect_checkbox.setChecked(self.settings.value("auto_detect", True, type=bool))
            self.ime_friendly_checkbox.setChecked(self.settings.value("ime_friendly", False, type=bool))
            self.unicode_hex_checkbox.setChecked(self.settings.value("unicode_hex", False, type=bool))
            self.compliance_mode_checkbox.setChecked(self.settings.value("compliance_mode", False, type=bool))
            self.blocked_apps_edit.setText(self.settings.value("blocked_apps", self.blocked_apps_edit.text(), type=str))
            self.enable_macros_checkbox.setChecked(self.settings.value("enable_macros", True, type=bool))
            self.confirm_click_checkbox.setChecked(self.settings.value("confirm_click", True, type=bool))
        except Exception:
            _log_caught('load_settings@L2897')
            pass
        finally:
            try:
                self.settings.endGroup()
            except Exception:
                _log_caught('load_settings@L2902')
                pass
        # Seed per-input presets for first-time users (backwards compatible with older "UI" settings),
        # then apply the preset for the active tab.
        try:
            current_idx = int(self.input_tabs.currentIndex())
        except Exception:
            _log_caught('load_settings@L2908')
            current_idx = 0
        try:
            if not self._has_input_mode_preset(current_idx):
                self._save_input_mode_preset(current_idx)
            other_idx = 1 if current_idx == 0 else 0
            if not self._has_input_mode_preset(other_idx):
                self._write_input_mode_preset(other_idx, self._default_input_mode_preset(other_idx))
            # One-time migration: normalize older presets to current defaults.
            try:
                preset_schema = self.settings.value("ModePresets/schemaVersion", 0, type=int)
            except Exception:
                _log_caught('load_settings@L2919')
                preset_schema = 0
            if int(preset_schema or 0) < 3:
                # Code preset: undo forced Paste Mode, ensure default persona.
                code_mode = ""
                code_persona = ""
                try:
                    self.settings.beginGroup("ModePresets/code")
                    code_mode = self.settings.value("newline_mode", "", type=str)
                    code_persona = self.settings.value("persona", "", type=str)
                except Exception:
                    _log_caught('load_settings@L2929')
                    code_mode = ""
                    code_persona = ""
                finally:
                    try:
                        self.settings.endGroup()
                    except Exception:
                        _log_caught('load_settings@L2935')
                        pass
                if code_mode == "Paste Mode":
                    self._write_input_mode_preset(1, {"newline_mode": "List Mode"})
                if not code_persona:
                    self._write_input_mode_preset(1, {"persona": "Careful Coder"})

                # Plain preset: preserve bullets by default (Standard), enable humanization defaults.
                plain_mode = ""
                try:
                    self.settings.beginGroup("ModePresets/plain")
                    plain_mode = self.settings.value("newline_mode", "", type=str)
                except Exception:
                    _log_caught('load_settings@L2947')
                    plain_mode = ""
                finally:
                    try:
                        self.settings.endGroup()
                    except Exception:
                        _log_caught('load_settings@L2952')
                        pass
                if plain_mode == "Smart Newlines":
                    self._write_input_mode_preset(
                        0,
                        {
                            "newline_mode": "Standard",
                            "press_esc": False,
                            "type_tabs": True,
                            "mouse_jitter": True,
                            "add_mistakes": True,
                            "pause_on_punct": True,
                        },
                    )
                try:
                    self.settings.setValue("ModePresets/schemaVersion", 3)
                except Exception:
                    _log_caught('load_settings@L2968')
                    pass
            self._load_input_mode_preset(current_idx, apply_defaults=True)
            self._last_input_tab_index = current_idx
        except Exception:
            _log_caught('load_settings@L2972')
            pass
        self.update_speed_labels()
        self.schedule_text_update()

    def save_settings(self):
        try:
            self._save_input_mode_preset(int(self.input_tabs.currentIndex()))
        except Exception:
            _log_caught('save_settings@L2980')
            pass
        self.settings.setValue("geometry", self.saveGeometry())
        try:
            self.settings.setValue("inputMode", self.input_tabs.currentIndex())
        except Exception:
            _log_caught('save_settings@L2985')
            pass
        try:
            if hasattr(self, "splitter"):
                self.settings.setValue("splitterSizes", self.splitter.sizes())
        except Exception:
            _log_caught('save_settings@L2990')
            pass
        try:
            self.settings.beginGroup("UI")
            self.settings.setValue("persona", self.persona_combo.currentText())
            self.settings.setValue("laps", self.laps_spin.value())
            self.settings.setValue("delay", self.delay_spin.value())
            self.settings.setValue("min_wpm", self.min_wpm_slider.value())
            self.settings.setValue("max_wpm", self.max_wpm_slider.value())
            self.settings.setValue("add_mistakes", self.add_mistakes_checkbox.isChecked())
            self.settings.setValue("pause_on_punct", self.pause_on_punct_checkbox.isChecked())
            self.settings.setValue("newline_mode", self._get_selected_newline_mode())
            self.settings.setValue("use_shift_enter", self.use_shift_enter_checkbox.isChecked())
            self.settings.setValue("type_tabs", self.type_tabs_checkbox.isChecked())
            self.settings.setValue("press_esc", self.press_esc_checkbox.isChecked())
            self.settings.setValue("mouse_jitter", self.mouse_jitter_checkbox.isChecked())
            self.settings.setValue("auto_detect", self.auto_detect_checkbox.isChecked())
            self.settings.setValue("ime_friendly", self.ime_friendly_checkbox.isChecked())
            self.settings.setValue("unicode_hex", self.unicode_hex_checkbox.isChecked())
            self.settings.setValue("compliance_mode", self.compliance_mode_checkbox.isChecked())
            self.settings.setValue("blocked_apps", self.blocked_apps_edit.text())
            self.settings.setValue("enable_macros", self.enable_macros_checkbox.isChecked())
            self.settings.setValue("confirm_click", self.confirm_click_checkbox.isChecked())
        except Exception:
            _log_caught('save_settings@L3013')
            pass
        finally:
            try:
                self.settings.endGroup()
            except Exception:
                _log_caught('save_settings@L3018')
                pass

    def closeEvent(self, event):
        self.save_settings()
        self.stop_listener()
        self.stop_typing()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Install sys.excepthook / threading.excepthook / Qt message handler so
    # uncaught exceptions in any thread or Qt internals end up in the log
    # file. Must run after QApplication exists so qInstallMessageHandler is
    # in place before any Qt warnings fire.
    install_global_handlers()

    try:
        from PyQt5.QtGui import QFont
        if platform.system() == "Darwin":
            family = "SF Pro Text"
        elif platform.system() == "Windows":
            family = "Segoe UI"
        else:
            family = "Inter"
        families = QFontDatabase().families()
        if family not in families:
            for fb in ("SF Pro Text", "Segoe UI", "Inter", "Helvetica Neue", "Arial"):
                if fb in families:
                    family = fb
                    break
        app.setFont(QFont(family, 10))
    except Exception:
        _log_caught('module@L3050')
        pass

    # Rely on Qt window management for stability across platforms
    window = AutoTyperApp()
    window.show()
    sys.exit(app.exec_())
