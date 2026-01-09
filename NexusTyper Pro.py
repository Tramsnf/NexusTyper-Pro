import faulthandler; faulthandler.enable()
import sys
import time
import re
import random
import platform
import threading
import os
import subprocess

from PyQt5.QtWidgets import (
    QApplication, QWidget, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QCheckBox, QSlider, QMessageBox, QProgressBar,
    QFileDialog, QAction, QMenuBar, QMenu, QDialog, QLineEdit,
    QDialogButtonBox, QComboBox, QInputDialog, QTabWidget, QKeySequenceEdit,
    QFormLayout, QGroupBox, QRadioButton, QPlainTextEdit, QCompleter,
    QSplitter, QScrollArea, QToolButton, QStyle, QGridLayout, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QSettings, QEvent, QUrl, QStringListModel, pyqtSlot, QTimer, QSize
from PyQt5.QtGui import QKeySequence, QPixmap, QIcon, QTextDocument, QDesktopServices, QFontDatabase, QFontMetrics
import json
import logging
from logging.handlers import RotatingFileHandler

# --- Text Processing Helpers ---
_SMART_BULLET_RE = re.compile(r"^\s*(?:[-*+]|•)\s+")
_SMART_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+")
_SMART_BLOCKQUOTE_RE = re.compile(r"^\s*>+\s+")
_SMART_HEADING_RE = re.compile(r"^\s*#{1,6}\s+")


def apply_smart_newlines(text: str) -> str:
    """Join soft-wrapped single newlines into spaces, preserving semantic breaks.

    Rules:
    - Keep blank lines as paragraph breaks.
    - Preserve list items (e.g., '- ', '* ', '1. ') and blockquotes.
    - Preserve indented/code-like lines.
    """
    if not text:
        return text
    try:
        s = str(text).replace("\r\n", "\n").replace("\r", "\n")
    except Exception:
        return text

    # If the input looks like code overall, do not reflow lines.
    # This prevents "Smart Newlines" from collapsing top-level code (e.g., imports) into one line.
    try:
        t = s.strip()
        markers = (
            "def ",
            "class ",
            "import ",
            "from ",
            "try:",
            "except ",
            "finally:",
            "elif ",
            "else:",
            "return",
            "function ",
            "const ",
            "let ",
            "var ",
            "#include",
            "std::",
            "public ",
            "private ",
        )
        marker_hits = sum(1 for m in markers if m in t)
        symbol_hits = sum(1 for ch in t[:2000] if ch in "{}();<>[]=")
        if marker_hits >= 2 or symbol_hits >= 18:
            return s
    except Exception:
        pass

    lines = s.split("\n")
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        if i >= len(lines) - 1:
            break
        nxt = lines[i + 1]

        # Paragraph breaks.
        if line == "" or nxt == "":
            out.append("\n")
            continue

        # Preserve lists/quotes/headings.
        if (
            _SMART_BULLET_RE.match(line)
            or _SMART_BULLET_RE.match(nxt)
            or _SMART_NUMBERED_RE.match(line)
            or _SMART_NUMBERED_RE.match(nxt)
            or _SMART_BLOCKQUOTE_RE.match(line)
            or _SMART_BLOCKQUOTE_RE.match(nxt)
            or _SMART_HEADING_RE.match(line)
            or _SMART_HEADING_RE.match(nxt)
        ):
            out.append("\n")
            continue

        # Preserve indented/code-like lines.
        if (
            line.startswith("    ")
            or line.startswith("\t")
            or nxt.startswith("    ")
            or nxt.startswith("\t")
        ):
            out.append("\n")
            continue

        out.append(" ")
    return "".join(out)

# Conditional import for platform-specific libraries
try:
    import pyautogui
    from pynput import keyboard
    import pyperclip
    if platform.system() == "Darwin":
        import AppKit
except ImportError as e:
    print(f"Error: A required library is missing (e.g., pyautogui, pynput, pyperclip). Please install it. {e}")
    sys.exit(1)

# --- Constants & App Info ---
APP_NAME = "NexusTyper Pro"
APP_VERSION = "3.3"
APP_AUTHOR = "TramsNF"
APP_COPYRIGHT_YEAR = "2025"
APP_SIGNATURE = "Automate. Create. Elevate."
CONTACT_EMAIL = "smartabayomi@gmail.com"
CONTACT_WEBSITE = "https://tramsnf.com"
DEFAULT_MIN_WPM, DEFAULT_MAX_WPM = 80, 120
MIN_WPM_LIMIT, MAX_WPM_LIMIT = 10, 800
DEFAULT_LAPS, DEFAULT_DELAY = 1, 3
MISTAKE_CHANCE = 0.02

# Platform-specific hotkeys for a native feel
if platform.system() == "Darwin":
    # Use Command (Cmd) key for macOS, which is standard practice
    DEFAULT_START_HOTKEY = "Cmd+Alt+S"
    DEFAULT_STOP_HOTKEY = "Cmd+Alt+X"
    DEFAULT_RESUME_HOTKEY = "Cmd+Alt+R"
else:
    # Use Control (Ctrl) key for Windows and Linux
    DEFAULT_START_HOTKEY = "Ctrl+Alt+S"
    DEFAULT_STOP_HOTKEY = "Ctrl+Alt+X"
    DEFAULT_RESUME_HOTKEY = "Ctrl+Alt+R"

# Keyboard adjacency map for simulating realistic typing mistakes
KEY_ADJACENCY = {
    'q': 'ws', 'w': 'qase', 'e': 'wsdr', 'r': 'edft', 't': 'rfgy',
    'y': 'tghu', 'u': 'yhji', 'i': 'ujko', 'o': 'iklp', 'p': 'ol;',
    'a': 'qwsz', 's': 'qwedzx', 'd': 'werfcx', 'f': 'ertgvc', 'g': 'rtyhbn',
    'h': 'tyujnb', 'j': 'yuihkn', 'k': 'uiojlm', 'l': 'iopk;m',
    'z': 'asx', 'x': 'zsdc', 'c': 'xdfv', 'v': 'cfgb', 'b': 'vghn', 'n': 'bghjm', 'm': 'njk,'
}

# --- App Styling ---
DARK_STYLESHEET = """
QWidget { background-color: #2b2b2b; color: #f0f0f0; border: none; }
QGroupBox { border: 1px solid #444; border-radius: 4px; margin-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }
QTabWidget::pane { border-top: 2px solid #3c3c3c; }
QTabBar::tab { background: #2b2b2b; border: 1px solid #444; border-bottom-color: #3c3c3c;
border-top-left-radius: 4px; border-top-right-radius: 4px; min-width: 8ex; padding: 5px; }
QTabBar::tab:selected, QTabBar::tab:hover { background: #3c3c3c; }
QMenuBar, QMenu { background-color: #3c3c3c; color: #f0f0f0; }
QMenu::item:selected { background-color: #555; }
QPushButton { background-color: #555; border: 1px solid #666; padding: 5px; border-radius: 3px; }
QPushButton:hover { background-color: #666; }
QPushButton:pressed { background-color: #777; }
QPushButton:disabled { background-color: #444; color: #888; }
QTextEdit, QLineEdit, QSpinBox, QComboBox, QKeySequenceEdit { background-color: #3c3c3c; border: 1px solid #555; padding: 3px; border-radius: 3px; }
QPlainTextEdit { background-color: #3c3c3c; border: 1px solid #555; padding: 3px; border-radius: 3px; }
QComboBox QAbstractItemView { background-color: #3c3c3c; border: 1px solid #555; selection-background-color: #555; }
QCheckBox::indicator, QRadioButton::indicator { width: 13px; height: 13px; }
QSlider::groove:horizontal { border: 1px solid #444; height: 8px; background: #3c3c3c; margin: 2px 0; border-radius: 4px; }
QSlider::handle:horizontal { background: #888; border: 1px solid #999; width: 18px; margin: -5px 0; border-radius: 9px; }
QProgressBar { border: 1px solid #555; border-radius: 5px; text-align: center; color: white; }
QProgressBar::chunk { background-color: #05B8CC; border-radius: 4px; }
"""

# --- Logging Setup ---
LOG_DIR = os.path.join(os.path.expanduser('~'), '.nexustyper_pro', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'app.log')
logger = logging.getLogger('nexustyper')
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=512*1024, backupCount=3)
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s'))
    logger.addHandler(handler)

# About dialog with app info and contact
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(480, 250)
        main_layout = QHBoxLayout(self)
        self.image_label = QLabel()
        if hasattr(sys, '_MEIPASS'):
            ico2_path = os.path.join(sys._MEIPASS, 'ico2.png')
        else:
            ico2_path = 'ico2.png'
        if os.path.exists(ico2_path):
            pixmap = QPixmap(ico2_path)
        else:
            pixmap = QPixmap(128, 128)
            pixmap.fill(Qt.gray)
        self.image_label.setPixmap(pixmap.scaled(128, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        main_layout.addWidget(self.image_label)
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel(f"<b>{APP_NAME}</b>"))
        right_layout.addWidget(QLabel(f"Version {APP_VERSION}"))
        right_layout.addWidget(QLabel(f"Copyright © {APP_COPYRIGHT_YEAR} {APP_AUTHOR}"))
        details_text = QTextEdit()
        details_text.setReadOnly(True)
        details_text.setHtml(f"Designed and Developed by <b>{APP_AUTHOR}</b>.<br><br>"
                            f"For more information, contact:<br><a href='mailto:{CONTACT_EMAIL}'>{CONTACT_EMAIL}</a>")
        link_label = QLabel(f"<a href='{CONTACT_WEBSITE}'>{CONTACT_WEBSITE}</a>")
        link_label.setOpenExternalLinks(True)
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        right_layout.addWidget(details_text)
        right_layout.addWidget(link_label, 0, Qt.AlignLeft)
        right_layout.addStretch()
        right_layout.addLayout(button_layout)
        main_layout.addLayout(right_layout)

# --- Help Dialog - Explains app functions ---
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Function Guide")
        self.resize(600, 400)
        text = QTextEdit(self)
        text.setReadOnly(True)
        text.setHtml("""
            <h1>NexusTyper Pro Function Guide</h1>
            
            <h2>Typing Personas</h2>
            <p>Personas are quick presets for common tasks. You can always fine‑tune settings after selecting one.</p>
            <ul>
                <li><b>Careful Coder:</b> Prefers List Mode for code editors, disables mistakes, and uses Esc to dismiss IDE popups (Esc is suppressed for browsers).</li>
                <li><b>Deliberate Writer:</b> Slower prose with Smart Newlines to form paragraphs.</li>
                <li><b>Fast Messenger:</b> Faster chat‑style typing with fewer punctuation pauses.</li>
                <li><b>Custom (Manual Settings):</b> Full control; no auto changes.</li>
            </ul>

            <h2>Humanization</h2>
            <ul>
                <li><b>WPM Sliders:</b> Typing varies smoothly between Min and Max WPM.</li>
                <li><b>Add Mistakes:</b> Occasional adjacent‑key typos with backspace corrections.</li>
                <li><b>Pause on Punctuation:</b> Small natural pauses after punctuation and brackets.</li>
            </ul>

            <h2>Advanced Handling</h2>
            <h4>Newline Modes</h4>
            <ul>
                <li><b>Line Paste:</b> Pastes each line (fastest). Some apps may block paste.</li>
                <li><b>Standard Typing:</b> Types every character, including tabs/spaces.</li>
                <li><b>Smart Newlines:</b> Joins single line breaks into spaces; preserves double breaks.</li>
                <li><b>List Mode:</b> Best for code editors: types the line without leading indentation; editor handles indent. Tabs are intentionally not preserved here.</li>
            </ul>
            <h4>Other Options</h4>
            <ul>
                <li><b>Use Shift+Enter:</b> Insert newline without sending (chat apps).</li>
                <li><b>Preserve Tab Characters:</b> Applies to Standard/Smart; ignored in List Mode.</li>
                <li><b>Press 'Esc' to bypass autocomplete:</b> Dismiss IDE popups before Enter.</li>
                <li><b>Enable Background Mouse Jitter:</b> Tiny background movement to prevent idle.</li>
                <li><b>IME‑friendly:</b> Use paste instead of per‑key typing for IMEs and complex scripts.</li>
                <li><b>Compliance Mode:</b> Automatically pause in blocked apps (e.g., browsers).</li>
            </ul>

            <h2>Loading & Pasting</h2>
            <ul>
                <li><b>Drag & Drop:</b> Drop .txt/.md/.html/.rtf to load.</li>
                <li><b>HTML/RTF:</b> Converted to clean text where possible; clipboard restored after paste.</li>
            </ul>

            <h2>Preview & Diagnostics</h2>
            <ul>
                <li><b>Estimated:</b> Live time estimate based on text, WPM, and mode.</li>
                <li><b>Diagnostics:</b> Help → Diagnostics shows environment info and opens logs.</li>
                <li><b>Dry‑Run Preview:</b> View → Dry Run Preview simulates typing visually, without sending keys.</li>
                <li><b>Profiles:</b> Profiles → Export/Import backups your saved profiles as JSON.</li>
            </ul>
        """)
        layout = QVBoxLayout(self)
        layout.addWidget(text)
        btn = QPushButton("OK")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

# Settings dialog for hotkeys
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = parent.settings
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.start_hotkey_edit = QKeySequenceEdit(self)
        self.stop_hotkey_edit = QKeySequenceEdit(self)
        self.resume_hotkey_edit = QKeySequenceEdit(self)
        form_layout.addRow("Start Typing Hotkey:", self.start_hotkey_edit)
        form_layout.addRow("Stop Typing Hotkey:", self.stop_hotkey_edit)
        form_layout.addRow("Resume Typing Hotkey:", self.resume_hotkey_edit)
        self.enable_hotkeys_checkbox = QCheckBox("Enable Global Hotkeys")
        if platform.system() == "Darwin":
            try:
                major = int(platform.mac_ver()[0].split('.')[0]) if platform.mac_ver()[0] else 0
            except Exception:
                major = 0
            if major >= 15:
                self.enable_hotkeys_checkbox.setToolTip("Disabled by default on macOS 15 due to OS assertions. Use at your own risk.")
        form_layout.addRow(self.enable_hotkeys_checkbox)
        layout.addLayout(form_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.load_settings()

    def load_settings(self):
        self.start_hotkey_edit.setKeySequence(QKeySequence(self.settings.value("startHotkey", DEFAULT_START_HOTKEY)))
        self.stop_hotkey_edit.setKeySequence(QKeySequence(self.settings.value("stopHotkey", DEFAULT_STOP_HOTKEY)))
        self.resume_hotkey_edit.setKeySequence(QKeySequence(self.settings.value("resumeHotkey", DEFAULT_RESUME_HOTKEY)))
        default_enable = True
        if platform.system() == "Darwin":
            try:
                major = int(platform.mac_ver()[0].split('.')[0]) if platform.mac_ver()[0] else 0
            except Exception:
                major = 0
            if major >= 15:
                default_enable = False
        self.enable_hotkeys_checkbox.setChecked(self.settings.value("enableGlobalHotkeys", default_enable, type=bool))

    def save_settings(self):
        # Store hotkeys in PortableText so they round-trip across platforms
        # and are easier to translate for pynput.
        self.settings.setValue("startHotkey", self.start_hotkey_edit.keySequence().toString(QKeySequence.PortableText))
        self.settings.setValue("stopHotkey", self.stop_hotkey_edit.keySequence().toString(QKeySequence.PortableText))
        self.settings.setValue("resumeHotkey", self.resume_hotkey_edit.keySequence().toString(QKeySequence.PortableText))
        self.settings.setValue("enableGlobalHotkeys", self.enable_hotkeys_checkbox.isChecked())
        self.accept()


class DiagnosticsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Diagnostics")
        self.resize(640, 420)
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

    def populate(self):
        try:
            from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
            import pynput
            import pyautogui as pag
            lines = [
                f"App: {APP_NAME} v{APP_VERSION}",
                f"OS: {platform.system()} {platform.release()} ({platform.machine()})",
                f"Python: {platform.python_version()}",
                f"Qt: {QT_VERSION_STR}",
                f"PyQt: {PYQT_VERSION_STR}",
                f"pynput: {getattr(pynput, '__version__', 'unknown')}",
                f"pyautogui: {getattr(pag, '__version__', 'unknown')}",
                f"Log file: {LOG_FILE}",
                f"Log dir: {LOG_DIR}",
            ]
            self.info.setPlainText("\n".join(lines))
        except Exception as e:
            self.info.setPlainText(f"Failed to gather diagnostics: {e}")

    def copy_info(self):
        self.info.selectAll()
        self.info.copy()

    def open_logs(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(LOG_DIR))

    def view_log(self):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
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

# TextEdit subclass to clean pasted text automatically
class PasteCleaningTextEdit(QTextEdit):
    fileDropped = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow richer pasting but normalize to clean plain text
        self.setAcceptRichText(False)
        self.setAcceptDrops(True)

    def insertFromMimeData(self, source):
        try:
            # Prefer HTML conversion when available to preserve logical breaks
            if hasattr(source, 'hasHtml') and source.hasHtml():
                html = source.html()
                doc = QTextDocument()
                doc.setHtml(html)
                text = doc.toPlainText()
            elif source.hasText():
                text = source.text()
            else:
                return super().insertFromMimeData(source)

            # Normalize common whitespace and line endings
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            text = text.replace('\u00A0', ' ').replace('\u202F', ' ')
            # Collapse 3+ blank lines to 2 to avoid huge gaps
            text = re.sub(r'\n{3,}', '\n\n', text)
            self.insertPlainText(text)
        except Exception:
            # Fallback to default behavior on unexpected formats
            super().insertFromMimeData(source)

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            for url in md.urls():
                if url.isLocalFile():
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            for url in md.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    self.fileDropped.emit(path)
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)

# TypingWorker handles the typing automation in a separate thread
class TypingWorker(QObject):
    paused_signal = pyqtSignal()
    resumed_signal = pyqtSignal()
    finished = pyqtSignal()
    update_status = pyqtSignal(str)
    update_speed = pyqtSignal(float)
    update_progress = pyqtSignal(int)
    set_progress_max = pyqtSignal(int)
    update_etr = pyqtSignal(str)
    lap_progress = pyqtSignal(int, int)

    def __init__(self, text, laps, delay, **kwargs):
        super().__init__()
        self._running = True
        self._paused = False
        self.pause_event = threading.Event()
        self.pause_event.set() # Not paused initially
        self._pause_started_at = None
        self._pause_total = 0.0
        self.text_to_type = text
        self.laps = laps
        self.delay = delay
        self.persona = kwargs.get('typing_persona')
        self.initial_window = None # To store the target window title
        self.started_from_gui = kwargs.get('started_from_gui', False)
        self.source_app = (kwargs.get('source_app') or "").strip()

        # --- Get ALL settings directly from the UI ---
        self.newline_mode = kwargs.get('newline_mode')
        self.use_shift_enter = kwargs.get('use_shift_enter', False)
        self.type_tabs = kwargs.get('type_tabs', True)
        self.min_wpm = kwargs.get('min_wpm')
        self.max_wpm = kwargs.get('max_wpm')
        self.add_mistakes = kwargs.get('add_mistakes')
        self.pause_on_punct = kwargs.get('pause_on_punct')
        self.enable_mouse_jitter = kwargs.get('mouse_jitter')
        self.press_esc = kwargs.get('press_esc', False)
        self.mistake_chance = MISTAKE_CHANCE 
        self.thinking_pause_chance = 0.04
        self._last_ui_update = 0.0
        try:
            self._allowed_keys = set(getattr(pyautogui, "KEYBOARD_KEYS", []))
        except Exception:
            self._allowed_keys = set()
        # New modes
        self.ime_friendly = kwargs.get('ime_friendly', False)
        self.unicode_hex_typing = kwargs.get('unicode_hex_typing', False)
        self.compliance_mode = kwargs.get('compliance_mode', False)
        blocked = kwargs.get('blocked_apps', "") or ""
        self.blocked_apps = [b.strip().lower() for b in blocked.split(',') if b.strip()]
        self.auto_detect = kwargs.get('auto_detect', False)
        self.enable_macros = kwargs.get('enable_macros', True)
        self._resume_settle_until = 0.0
        self._esc_on_next_ready = False
        self._target_is_browser = False

    def _is_browser_title(self, title: str) -> bool:
        t = (title or "").lower()
        return any(k in t for k in ("safari", "chrome", "chromium", "firefox", "edge", "brave", "opera"))

    def _looks_like_code_quick(self, t: str) -> bool:
        try:
            t = (t or "").strip()
        except Exception:
            return False
        if not t:
            return False
        if '\t' in t or '```' in t:
            return True
        lines = t.splitlines()
        if len(lines) >= 2:
            indent_lines = sum(1 for ln in lines[:40] if ln.startswith('    ') or ln.startswith('\t'))
            if indent_lines >= 2:
                return True
        hits = sum(1 for ch in t[:500] if ch in '{}();[]<>:=#')
        if hits >= 8:
            return True
        for kw in ('def ', 'class ', 'import ', 'from ', 'return', 'function ', 'const ', 'let ', 'var ', '#include', 'fn ', 'struct ', 'interface '):
            if kw in t:
                return True
        return False

    def _is_title_blocked(self, title: str) -> bool:
        if not self.compliance_mode:
            return False
        tl = (title or "").lower()
        return any(k in tl for k in self.blocked_apps)

    def _await_target_window(self):
        """If started from GUI, wait until focus leaves the source app before locking target."""
        if not (self.started_from_gui and self.source_app):
            return self.get_active_window_title() or "Unknown"

        last_hint = 0.0
        while self._running:
            cur = self.get_active_window_title() or "Unknown"
            if cur != self.source_app:
                if self._is_title_blocked(cur):
                    now = time.time()
                    if now - last_hint >= 1.0:
                        self.update_status.emit("Compliance mode: blocked app active. Focus an allowed app to start typing…")
                        last_hint = now
                else:
                    return cur
            now = time.time()
            if now - last_hint >= 1.0:
                self.update_status.emit("Focus your target app and click the input field… (typing starts when it’s active)")
                last_hint = now
            self._sleep_interruptible(0.1)
        return None

    def stop(self):
        self._running = False
        # Unblock any waits so the thread can exit promptly.
        self.pause_event.set()

    def pause(self, auto_resume_check=False):
        if not self._paused:
            self._paused = True
            self.pause_event.clear()
            self._pause_started_at = time.time()
            self.paused_signal.emit()
            if auto_resume_check and self.initial_window:
                threading.Thread(target=self._auto_resume_checker, daemon=True).start()

    def resume(self):
        if self._paused:
            self._paused = False
            if self._pause_started_at is not None:
                try:
                    self._pause_total += max(0.0, time.time() - self._pause_started_at)
                except Exception:
                    pass
                self._pause_started_at = None
            # Give the OS/app a short moment to settle focus after resume.
            try:
                self._resume_settle_until = time.time() + 0.25
            except Exception:
                self._resume_settle_until = 0.0
            # Dismiss autocomplete popups on resume (for IDEs) when enabled.
            if self.press_esc and not self._target_is_browser:
                self._esc_on_next_ready = True
            self.pause_event.set()
            self.resumed_signal.emit()

    def _current_pause_total(self) -> float:
        try:
            if self._pause_started_at is not None:
                return self._pause_total + max(0.0, time.time() - self._pause_started_at)
        except Exception:
            pass
        return self._pause_total

    def _auto_resume_checker(self):
        """Monitors active window and resumes typing if focus returns."""
        time.sleep(0.5)  # Prevent instant resume on quick window switches
        while self._paused and self._running:
            try:
                if self.get_active_window_title() == self.initial_window:
                    # Grace period to avoid missing text when focus returns.
                    for i in range(4, 0, -1):
                        if not (self._paused and self._running):
                            return
                        if self.get_active_window_title() != self.initial_window:
                            break
                        try:
                            self.update_status.emit(f"Resuming in {i}…")
                        except Exception:
                            pass
                        time.sleep(1)
                    else:
                        if self.get_active_window_title() == self.initial_window:
                            self.resume()
                            break
            except Exception:
                pass  # Ignore errors (e.g., window closed)
            time.sleep(0.2)

    def get_active_window_title(self):
        try:
            if platform.system() == "Darwin":
                return AppKit.NSWorkspace.sharedWorkspace().frontmostApplication().localizedName()
            return pyautogui.getActiveWindowTitle() or "Unknown"
        except Exception:
            return "Unknown"

    def update_speed_range(self, min_wpm, max_wpm):
        self.min_wpm = min_wpm
        self.max_wpm = max_wpm

    def execute_macro(self, command, params):
        try:
            if command == 'PAUSE':
                self._sleep_interruptible(float(params))
            elif command == 'PRESS':
                pyautogui.press(params.lower().strip())
            elif command == 'CLICK':
                x, y = params.split(',')
                pyautogui.click(int(x), int(y))
        except Exception as e:
            # You currently 'pass' here, but it's better to log or emit a status update
            error_message = f"Macro execution failed: {e}"
            if platform.system() == "Darwin" and ("Accessibility" in str(e) or "Input Monitoring" in str(e)):
                error_message += "\n\n(Likely macOS permissions issue)"
            self.update_status.emit(error_message) # Or log this internally for debug

    def validate_macro(self, command, params):
        cmd = (command or '').strip().upper()
        p = (params or '').strip()
        if cmd == 'PAUSE':
            try:
                t = float(p)
                if t < 0:
                    return False, "PAUSE must be non-negative", None
                # Clamp to 60s to avoid accidental long sleeps
                t = min(t, 60.0)
                return True, None, (cmd, str(t))
            except Exception:
                return False, f"Invalid PAUSE duration: '{p}'", None
        elif cmd == 'CLICK':
            try:
                x_str, y_str = p.split(',')
                x, y = int(x_str), int(y_str)
                try:
                    w, h = pyautogui.size()
                    if not (0 <= x < w and 0 <= y < h):
                        return False, f"CLICK coordinates out of bounds: {x},{y}", None
                except Exception:
                    pass
                return True, None, (cmd, f"{x},{y}")
            except Exception:
                return False, f"Invalid CLICK params, expected 'x,y' got '{p}'", None
        elif cmd == 'PRESS':
            key = p.lower()
            if not key:
                return False, "PRESS requires a key name", None
            if self._allowed_keys and key not in self._allowed_keys:
                return False, f"Unknown key for PRESS: '{key}'", None
            return True, None, (cmd, key)
        elif cmd == 'COMMENT':
            return True, None, (cmd, p)
        else:
            return False, f"Unknown macro: '{cmd}'", None

    def _strip_macros(self, text: str) -> str:
        if not self.enable_macros:
            return text
        try:
            return re.sub(r'(?i)\{\{(?:PAUSE|PRESS|CLICK|COMMENT):.*?\}\}', '', text)
        except Exception:
            return text

    def _compute_total_chars_per_lap(self, text_content: str) -> int:
        if not text_content:
            return 0
        mode = self.newline_mode or 'Standard'
        if mode == 'Paste Mode':
            # Paste Mode outputs the text minus macros; tabs are preserved.
            return len(self._strip_macros(text_content))
        if mode == 'List Mode':
            # List Mode: strip leading whitespace per line, do not preserve tab characters,
            # execute macros (so they're not output), and always send an Enter after each line.
            lines = text_content.splitlines()
            total = 0
            for line in lines:
                stripped = line.lstrip(' \t')
                if not self.type_tabs:
                    stripped = stripped.replace('\t', '')
                stripped = self._strip_macros(stripped)
                total += len(stripped)
            total += len(lines)  # Enter after each line
            return total
        # Standard/Smart modes: remove macros; optionally skip tabs.
        processed = apply_smart_newlines(text_content) if mode == 'Smart Newlines' else text_content
        processed = self._strip_macros(processed)
        if not self.type_tabs:
            processed = processed.replace('\t', '')
        return len(processed)

    def _elapsed_active(self, overall_start_time: float) -> float:
        try:
            return max(0.0, (time.time() - overall_start_time) - self._current_pause_total())
        except Exception:
            return max(0.0, time.time() - overall_start_time)

    def _maybe_emit_progress(self, overall_start_time: float, chars_completed: int, total_chars_overall: int):
        now = time.time()
        if (now - self._last_ui_update) < 0.05 and chars_completed < total_chars_overall:
            return
        self.update_progress.emit(chars_completed)
        elapsed = self._elapsed_active(overall_start_time)
        if elapsed > 0 and chars_completed > 0:
            cpm = (chars_completed / elapsed) * 60
            self.update_speed.emit(cpm / 5)
            if total_chars_overall > 0 and cpm > 0:
                etr_seconds = ((total_chars_overall - chars_completed) / cpm) * 60
                self.update_etr.emit(f"ETR: {time.strftime('%M:%S', time.gmtime(max(0.0, etr_seconds)))}")
        self._last_ui_update = now

    def _wait_until_ready(self) -> bool:
        """Blocks while paused or while guardrails require auto-pausing."""
        while self._running:
            # Honor explicit pauses first.
            self.pause_event.wait()
            if not self._running:
                return False

            title = self.get_active_window_title() or ""

            # Compliance guardrail
            if self.compliance_mode:
                tl = title.lower()
                if any(k in tl for k in self.blocked_apps):
                    if not self._paused:
                        self.update_status.emit("Compliance mode: blocked app active. Pausing...")
                        self.pause(auto_resume_check=True)
                    continue

            # Focus lock guardrail
            if self.initial_window and title != self.initial_window:
                if not self._paused:
                    self.pause(auto_resume_check=True)
                continue

            # Post-resume settle delay (prevents dropped keystrokes in some apps).
            try:
                if self._resume_settle_until and time.time() < self._resume_settle_until:
                    self._sleep_interruptible(max(0.0, self._resume_settle_until - time.time()))
                self._resume_settle_until = 0.0
            except Exception:
                self._resume_settle_until = 0.0

            # Optional: close autocomplete popups once after resuming.
            if getattr(self, "_esc_on_next_ready", False):
                if not self._target_is_browser:
                    try:
                        pyautogui.press('esc')
                        self._sleep_interruptible(0.05)
                    except Exception:
                        pass
                self._esc_on_next_ready = False

            return True
        return False

    def _sleep_interruptible(self, duration):
        """Sleep in small chunks while honoring stop/pause."""
        end = time.time() + max(0.0, duration)
        while self._running:
            if not self.pause_event.is_set():
                # Block during pauses without busy-waiting.
                self.pause_event.wait(timeout=0.1)
                continue
            remaining = end - time.time()
            if remaining <= 0:
                break
            time.sleep(0.02 if remaining > 0.02 else max(0.0, remaining))

    def _mouse_jitter_thread(self):
        # Moves mouse slightly at random intervals to simulate activity
        # Respect PyAutoGUI fail-safe (corners) and stop jitter if triggered.
        try:
            screen_w, screen_h = pyautogui.size()
        except Exception:
            screen_w, screen_h = None, None
        corner_guard = 2  # pixels from the edges considered fail-safe zone

        while self._running and self.enable_mouse_jitter:
            try:
                try:
                    x, y = pyautogui.position()
                except Exception:
                    x = y = None
                # If cursor is in a fail-safe corner/edge, stop jitter immediately
                if screen_w and screen_h and x is not None and y is not None:
                    if (x <= corner_guard or y <= corner_guard or
                        x >= screen_w - 1 - corner_guard or y >= screen_h - 1 - corner_guard):
                        try:
                            self.update_status.emit("Mouse jitter stopped: cursor at screen edge (fail-safe zone).")
                        except Exception:
                            pass
                        break

                # Small relative move
                pyautogui.move(random.randint(-1, 1), random.randint(-1, 1), duration=0.1)
            except Exception as e:
                # Stop on PyAutoGUI fail-safe without crashing the app
                if e.__class__.__name__ == 'FailSafeException':
                    try:
                        self.update_status.emit("Mouse jitter stopped due to PyAutoGUI fail-safe.")
                    except Exception:
                        pass
                    break
                # For any other transient error, back off briefly and continue
                time.sleep(0.3)
            time.sleep(random.uniform(0.5, 3))

    def _paste_text(self, text):
        original_clip = None
        try:
            original_clip = pyperclip.paste()
        except Exception:
            original_clip = None
        try:
            pyperclip.copy(text)
            pyautogui.hotkey('command' if platform.system() == "Darwin" else 'ctrl', 'v')
            return True
        except Exception as e:
            # Fallback: type the text if paste/hotkey fails.
            try:
                pyautogui.typewrite(text, interval=0.002)
                try:
                    self.update_status.emit("Paste failed; fell back to typing.")
                except Exception:
                    pass
                return True
            except Exception:
                try:
                    self.update_status.emit(f"Paste/Type failed: {e}")
                except Exception:
                    pass
                return False
        finally:
            if original_clip is not None:
                try:
                    pyperclip.copy(original_clip)
                except Exception:
                    pass

    def _type_unicode_char_macos(self, ch: str):
        """Types a single Unicode character using macOS 'Unicode Hex Input'.
        The user must enable this input source in System Settings > Keyboard > Input Sources.
        """
        try:
            cp = ord(ch)
            hexstr = f"{cp:04X}"
            pyautogui.keyDown('option')
            for d in hexstr:
                pyautogui.typewrite(d.lower())
            pyautogui.keyUp('option')
        except Exception:
            # Fallback to ASCII approximation
            self._type_with_ascii_fallback(ch)

    def _type_with_ascii_fallback(self, ch: str):
        mapping = {
            '∀': 'for all', '∃': 'exists', '∑': 'sum', '∫': 'int', '√': 'sqrt', '∞': 'infty',
            '≤': '<=', '≥': '>=', '≠': '!=', '≈': '~=', '→': '->', '←': '<-', '↔': '<->', '·': '*',
            '×': '*', '÷': '/', '∈': ' in ', '∉': ' notin ', '⊂': ' subset ', '⊆': ' subseteq ', '∪': ' U ', '∩': ' n ',
            'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta', 'ε': 'epsilon', 'θ': 'theta', 'λ': 'lambda', 'µ': 'mu',
            'π': 'pi', 'σ': 'sigma', 'ω': 'omega', 'ℝ': 'R', '′': "'", '″': '"'
        }
        out = mapping.get(ch, '?')
        pyautogui.typewrite(out, interval=0.002)

    def _dismiss_autocomplete_popup(self):
        """Best-effort: close editor autocomplete/popups before sending Enter."""
        if not self.press_esc or self._target_is_browser:
            return
        # Many editors need a tiny delay after Esc so Enter doesn't accept a suggestion.
        for _ in range(2):
            try:
                pyautogui.press('esc')
            except Exception:
                break
            self._sleep_interruptible(0.06)

    def _indent_level_for_list_mode(self, line: str) -> int:
        """Return indentation level (approx, 4 spaces per level) for List Mode."""
        try:
            tab_count = 0
            space_count = 0
            for ch in (line or ""):
                if ch == '\t':
                    tab_count += 1
                    continue
                if ch == ' ':
                    space_count += 1
                    continue
                break
            return max(0, (tab_count * 4 + space_count) // 4)
        except Exception:
            return 0

    def _type_segment(self, segment, overall_start_time, chars_completed, total_chars_overall):
        # Types a segment of text with human-like behavior, preserving code formatting
        prev_char = ''
        for char in segment:
            if char == '\t' and not self.type_tabs:
                continue # Skip this character and go to the next one
            
            if not self._wait_until_ready():
                return chars_completed, False
            
            if self.add_mistakes and random.random() < self.mistake_chance:
                if char.lower() in KEY_ADJACENCY:
                    pyautogui.typewrite(random.choice(KEY_ADJACENCY[char.lower()]))
                    self._sleep_interruptible(random.uniform(0.1, 0.25))
                    pyautogui.press('backspace')
                    self._sleep_interruptible(random.uniform(0.05, 0.15))
            
            if char == '\n':
                self._dismiss_autocomplete_popup()
                if self.use_shift_enter:
                    pyautogui.hotkey('shift', 'enter')
                else:
                    pyautogui.press('enter')
            else:
                # Type non-ASCII via macOS Unicode Hex Input if enabled
                if self.unicode_hex_typing and ord(char) > 0x7F:
                    if platform.system() == 'Darwin':
                        self._type_unicode_char_macos(char)
                    else:
                        self._type_with_ascii_fallback(char)
                else:
                    pyautogui.typewrite(char, interval=0.002)
            
            chars_completed += 1
            self._maybe_emit_progress(overall_start_time, chars_completed, total_chars_overall)
            
            # Smooth human-like delay: bias to mid-range via beta, extra thinking pauses
            min_d = 60 / (self.max_wpm * 5)
            max_d = 60 / (self.min_wpm * 5)
            sf = random.betavariate(2.5, 2.5)
            delay = min_d + sf * (max_d - min_d)
            if self.pause_on_punct:
                if char in '.,?!':
                    delay += random.uniform(0.08, 0.15)
                elif char in '()[]{}':
                    delay += random.uniform(0.1, 0.3)
            # Occasional cognitive pause at word boundaries
            if prev_char and prev_char in ' \t' and random.random() < self.thinking_pause_chance:
                delay += random.uniform(0.12, 0.35)
            self._sleep_interruptible(max(0.01, delay))
            prev_char = char
            
        return chars_completed, True

    @pyqtSlot()
    def run(self):
        try:
            pyautogui.PAUSE = 0
            if self.enable_mouse_jitter:
                threading.Thread(target=self._mouse_jitter_thread, daemon=True).start()

            text_content = self.text_to_type or ""
            # Normalize some curly quotes/dashes to plain ASCII
            text_content = (text_content
                            .replace('“', '"').replace('”', '"')
                            .replace('‘', "'").replace('’', "'")
                            .replace('—', '--').replace('…', '...'))

            if not text_content:
                self.finished.emit()
                return

            for i in range(self.delay, 0, -1):
                if not self._running:
                    self.finished.emit()
                    return
                if self.started_from_gui:
                    self.update_status.emit(f"Starting in {i}… switch to your target app")
                else:
                    self.update_status.emit(f"Starting in {i}...")
                self._sleep_interruptible(1)

            target = self._await_target_window()
            if not target:
                self.finished.emit()
                return
            self.initial_window = target
            self._target_is_browser = self._is_browser_title(self.initial_window)
            self.update_status.emit(f"Typing locked on: {self.initial_window}")
            if self.auto_detect:
                self._auto_optimize_for_window(self.initial_window)
            overall_start_time = time.time()

            total_per_lap = self._compute_total_chars_per_lap(text_content)
            total_chars_overall = max(1, total_per_lap * max(1, self.laps))
            try:
                self.set_progress_max.emit(total_chars_overall)
            except Exception:
                pass
            try:
                self.update_progress.emit(0)
            except Exception:
                pass

            macro_split_re = r'(?i)(\{\{(?:PAUSE|PRESS|CLICK|COMMENT):.*?\}\})'
            def split_segments(s: str):
                # Allow toggling macros on/off while paused (runtime updates).
                if self.enable_macros:
                    return re.split(macro_split_re, s)
                return [s]

            chars_completed = 0
            for lap in range(1, self.laps + 1):
                if not self._running:
                    break
                self.lap_progress.emit(lap, self.laps)

                mode = self.newline_mode or 'Standard'

                if mode == 'Paste Mode':
                    # Paste text fast, but still honor macros and guardrails.
                    segments = split_segments(text_content)
                    for segment in segments:
                        if not self._running:
                            break
                        match = re.fullmatch(r'\{\{([A-Za-z]+):(.*)\}\}', segment) if self.enable_macros else None
                        if self.enable_macros and match:
                            ok, msg, normalized = self.validate_macro(match.group(1), match.group(2))
                            if ok and normalized:
                                cmd = normalized[0]
                                if cmd != 'PAUSE' and not self._wait_until_ready():
                                    break
                                self.execute_macro(*normalized)
                            else:
                                self.update_status.emit(f"Macro ignored: {msg}")
                            continue
                        if not segment:
                            continue
                        for line in segment.splitlines(keepends=True):
                            if not self._running:
                                break
                            if not self._wait_until_ready():
                                break
                            self._paste_text(line)
                            chars_completed += len(line)
                            self._maybe_emit_progress(overall_start_time, chars_completed, total_chars_overall)
                            self._sleep_interruptible(random.uniform(0.05, 0.15))
                    continue

                if mode == 'List Mode':
                    # List Mode: strip leading indentation and always send Enter per line.
                    # Tabs are intentionally not preserved in this mode.
                    lines = text_content.splitlines()
                    virtual_level = 0
                    for line in lines:
                        if not self._running:
                            break
                        desired_level = self._indent_level_for_list_mode(line)
                        # If the next line should be dedented relative to the editor's current level,
                        # outdent before typing to avoid "except/else" being stuck inside a block.
                        if desired_level < virtual_level:
                            steps = max(0, virtual_level - desired_level)
                            for _ in range(steps):
                                if not self._wait_until_ready():
                                    break
                                try:
                                    pyautogui.hotkey('shift', 'tab')
                                except Exception:
                                    try:
                                        pyautogui.keyDown('shift')
                                        pyautogui.press('tab')
                                        pyautogui.keyUp('shift')
                                    except Exception:
                                        break
                                self._sleep_interruptible(0.03)
                            virtual_level = desired_level

                        stripped = line.lstrip(' \t')
                        if not self.type_tabs:
                            stripped = stripped.replace('\t', '')
                        line_segments = split_segments(stripped)
                        for segment in line_segments:
                            if not self._running:
                                break
                            match = re.fullmatch(r'\{\{([A-Za-z]+):(.*)\}\}', segment) if self.enable_macros else None
                            if self.enable_macros and match:
                                ok, msg, normalized = self.validate_macro(match.group(1), match.group(2))
                                if ok and normalized:
                                    cmd = normalized[0]
                                    if cmd != 'PAUSE' and not self._wait_until_ready():
                                        break
                                    self.execute_macro(*normalized)
                                else:
                                    self.update_status.emit(f"Macro ignored: {msg}")
                                continue
                            if not segment:
                                continue

                            should_paste = False
                            if self.ime_friendly and not self.unicode_hex_typing:
                                # In List Mode (code editors), prefer per-key typing unless non-ASCII
                                # would fail without IME/Unicode support.
                                try:
                                    should_paste = any(ord(ch) > 0x7F for ch in segment)
                                except Exception:
                                    should_paste = False

                            if should_paste:
                                if not self._wait_until_ready():
                                    break
                                self._paste_text(segment)
                                chars_completed += len(segment)
                                self._maybe_emit_progress(overall_start_time, chars_completed, total_chars_overall)
                                self._sleep_interruptible(random.uniform(0.02, 0.06))
                            else:
                                chars_completed, still_running = self._type_segment(
                                    segment, overall_start_time, chars_completed, total_chars_overall)
                                if not still_running:
                                    break

                        if not self._running:
                            break
                        if not self._wait_until_ready():
                            break
                        self._dismiss_autocomplete_popup()
                        if self.use_shift_enter:
                            pyautogui.hotkey('shift', 'enter')
                        else:
                            pyautogui.press('enter')
                        chars_completed += 1
                        self._maybe_emit_progress(overall_start_time, chars_completed, total_chars_overall)
                        self._sleep_interruptible(0.1)
                        # Approximate next-line indentation level (common in code editors):
                        # after block starters like ':' or '{', indentation increases.
                        try:
                            s = (stripped or "").rstrip()
                        except Exception:
                            s = ""
                        if s.endswith(':') or s.endswith('{'):
                            virtual_level = desired_level + 1
                        else:
                            virtual_level = desired_level
                else:
                    processed_text = apply_smart_newlines(text_content) if mode == 'Smart Newlines' else text_content
                    segments = split_segments(processed_text)
                    for segment in segments:
                        if not self._running:
                            break
                        match = re.fullmatch(r'\{\{([A-Za-z]+):(.*)\}\}', segment) if self.enable_macros else None
                        if self.enable_macros and match:
                            ok, msg, normalized = self.validate_macro(match.group(1), match.group(2))
                            if ok and normalized:
                                cmd = normalized[0]
                                if cmd != 'PAUSE' and not self._wait_until_ready():
                                    break
                                self.execute_macro(*normalized)
                            else:
                                self.update_status.emit(f"Macro ignored: {msg}")
                            continue
                        if not segment:
                            continue

                        if self.ime_friendly and not self.unicode_hex_typing:
                            if not self.type_tabs:
                                segment = segment.replace('\t', '')
                            if not segment:
                                continue
                            if not self._wait_until_ready():
                                break
                            self._paste_text(segment)
                            chars_completed += len(segment)
                            self._maybe_emit_progress(overall_start_time, chars_completed, total_chars_overall)
                            self._sleep_interruptible(random.uniform(0.02, 0.06))
                        else:
                            chars_completed, still_running = self._type_segment(
                                segment, overall_start_time, chars_completed, total_chars_overall)
                            if not still_running:
                                break

                if not self._running:
                    break
                self._sleep_interruptible(0.5)

            if self._running:
                # Ensure the progress bar reaches 100% for edge cases (e.g., macros-only runs).
                try:
                    self.update_progress.emit(total_chars_overall)
                except Exception:
                    pass
                self.update_status.emit("Typing completed successfully!")
            else:
                self.update_status.emit("Typing stopped by user.")
        except Exception as e:
            error_message = f"Typing Error: {e}"
            if platform.system() == "Darwin" and ("Accessibility" in str(e) or "Input Monitoring" in str(e) or "access for assistive devices" in str(e)):
                error_message += "\n\nThis often means macOS security permissions (Accessibility/Input Monitoring) are not granted. Please check System Settings > Privacy & Security."
            self.update_status.emit(error_message)
            try:
                logger.exception("Typing worker crashed")
            except Exception:
                pass
        finally:
            self.finished.emit()

    def _auto_optimize_for_window(self, title):
        t = (title or "").lower()
        code_keywords = [
            "code", "pycharm", "intellij", "webstorm", "clion", "goland", "xcode", "sublime", "atom", "notepad++", "vim", "emacs"
        ]
        chat_keywords = [
            "slack", "teams", "discord", "skype", "telegram", "whatsapp", "wechat", "messages", "imessage"
        ]
        text_keywords = ["notepad", "textedit", "notes"]
        browser_keywords = ["safari", "chrome", "chromium", "firefox", "edge", "brave", "opera"]
        chosen = None
        try:
            looks_code = self._looks_like_code_quick(self.text_to_type or "")
        except Exception:
            looks_code = False
        current_mode = self.newline_mode or "Standard"
        if any(k in t for k in browser_keywords):
            # Browsers can treat Esc as "cancel" (stop load/close UI). Avoid it.
            self.press_esc = False
            self.use_shift_enter = False
            self.type_tabs = True
            self.add_mistakes = False
            self.pause_on_punct = True
            chosen = "Browser"
        elif any(k in t for k in code_keywords):
            # IDEs often have aggressive autocomplete/auto-closing; use Esc and disable mistakes.
            self.press_esc = True
            self.use_shift_enter = False
            self.type_tabs = True
            self.add_mistakes = False
            self.pause_on_punct = True
            # For code-like content in a code editor, List Mode avoids indentation drift from editor auto-indent.
            # Never force Paste Mode; only adjust away from modes that break code formatting.
            if looks_code and current_mode != "Paste Mode":
                self.newline_mode = "List Mode"
            chosen = "Code editor"
        elif any(k in t for k in chat_keywords):
            self.use_shift_enter = True
            self.press_esc = False
            self.add_mistakes = True
            self.pause_on_punct = True
            chosen = "Chat app"
        elif any(k in t for k in text_keywords):
            self.press_esc = False
            self.use_shift_enter = False
            self.type_tabs = True
            self.add_mistakes = False
            self.pause_on_punct = True
            chosen = "Plain text editor"
        if chosen:
            try:
                self.update_status.emit(f"Auto-optimized for {chosen}: mode={self.newline_mode}")
            except Exception:
                pass


class DryRunWorker(QObject):
    finished = pyqtSignal()
    update_preview = pyqtSignal(str)

    def __init__(self, text, laps, min_wpm, max_wpm, mode, use_shift_enter, type_tabs=True, enable_macros=True):
        super().__init__()
        self.text = text
        self.laps = laps
        self.min_wpm = min_wpm
        self.max_wpm = max_wpm
        self.mode = mode
        self.use_shift_enter = use_shift_enter
        self.type_tabs = type_tabs
        self.enable_macros = enable_macros
        self._running = True

    def stop(self):
        self._running = False

    def _delay(self, prev_char, char):
        min_d = 60 / (self.max_wpm * 5)
        max_d = 60 / (self.min_wpm * 5)
        sf = random.betavariate(2.5, 2.5)
        d = min_d + sf * (max_d - min_d)
        if char in '.,?!':
            d += random.uniform(0.08, 0.15)
        elif char in '()[]{}':
            d += random.uniform(0.1, 0.3)
        if prev_char and prev_char in ' \t' and random.random() < 0.04:
            d += random.uniform(0.12, 0.35)
        return max(0.01, d)

    @pyqtSlot()
    def run(self):
        try:
            content = self.text
            for lap in range(self.laps):
                if not self._running: break
                if self.mode == 'Smart Newlines':
                    content_iter = apply_smart_newlines(content)
                else:
                    content_iter = content
                if self.mode == 'List Mode':
                    lines = content_iter.splitlines()
                    for line in lines:
                        if not self._running: break
                        out = ''
                        prev = ''
                        for ch in line.lstrip().replace('\t', ''):
                            if not self._running: break
                            out += ch
                            self.update_preview.emit(ch)
                            time.sleep(self._delay(prev, ch))
                            prev = ch
                        # simulate enter
                        self.update_preview.emit('\n')
                        time.sleep(0.06)
                else:
                    if not self.type_tabs:
                        content_iter = content_iter.replace('\t', '')
                    # Process macros by stripping them when enabled; otherwise show them as literal text.
                    segments = [content_iter]
                    if self.enable_macros:
                        segments = re.split(r'(?i)(\{\{(?:PAUSE|PRESS|CLICK|COMMENT):.*?\}\})', content_iter)
                    prev = ''
                    for seg in segments:
                        if not self._running: break
                        if self.enable_macros and re.fullmatch(r'\{\{([A-Za-z]+):(.*)\}\}', seg):
                            # show nothing for macros; could display a hint if desired
                            continue
                        for ch in seg:
                            if not self._running: break
                            self.update_preview.emit(ch)
                            time.sleep(self._delay(prev, ch))
                            prev = ch
            self.finished.emit()
        except Exception:
            self.finished.emit()


class DryRunDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dry Run Preview")
        self.resize(700, 500)
        self.setWindowModality(Qt.NonModal)
        v = QVBoxLayout(self)
        # Tabs: Text preview and Code Editor
        self.tabs = QTabWidget(self)
        # Text preview tab
        self.view = QTextEdit(self)
        self.view.setReadOnly(True)
        self.tabs.addTab(self.view, "Preview")
        # Code editor tab with basic autocomplete
        self.code_editor = CodeEditor(self)
        self.tabs.addTab(self.code_editor, "Code Editor")
        v.addWidget(self.tabs)
        h = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.reset_editor_btn = QPushButton("Reset Editor")
        self.close_btn = QPushButton("Close")
        h.addWidget(self.start_btn)
        h.addWidget(self.stop_btn)
        h.addWidget(self.reset_editor_btn)
        h.addStretch()
        h.addWidget(self.close_btn)
        v.addLayout(h)
        self.thread = None
        self.worker = None
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.reset_editor_btn.clicked.connect(self.reset_editor)
        self.close_btn.clicked.connect(self.accept)

    def start(self):
        if self.thread:
            return
        p = self.parent()
        if not p:
            return
        text = p.get_input_text() if hasattr(p, "get_input_text") else ""
        if not text.strip():
            QMessageBox.information(self, "Dry Run", "Please enter some text first.")
            return
        mode = 'Standard'
        if p.smart_radio.isChecked():
            mode = 'Smart Newlines'
        elif p.list_mode_radio.isChecked():
            mode = 'List Mode'
        elif p.paste_mode_radio.isChecked():
            mode = 'Paste Mode'
        self.view.clear()
        self.code_editor.clear()
        self.thread = QThread()
        self.worker = DryRunWorker(
            text,
            p.laps_spin.value(),
            p.min_wpm_slider.value(),
            p.max_wpm_slider.value(),
            mode,
            p.use_shift_enter_checkbox.isChecked(),
            p.type_tabs_checkbox.isChecked(),
            p.enable_macros_checkbox.isChecked() if hasattr(p, "enable_macros_checkbox") else True,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_finished)
        self.worker.update_preview.connect(self.on_char)
        self.thread.start()

    def stop(self):
        if self.worker:
            self.worker.stop()

    def on_finished(self):
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        self.thread = None
        self.worker = None

    def reset_editor(self):
        self.code_editor.clear()

    def on_char(self, ch: str):
        # Send to text preview
        self.view.insertPlainText(ch)
        # Simulate code editor typing with basic autocomplete behaviour
        p = self.parent()
        if ch == '\n':
            # Simulate 'Esc before Enter' if enabled to dismiss autocomplete
            try:
                if p and hasattr(p, 'press_esc_checkbox') and p.press_esc_checkbox.isChecked():
                    self.code_editor.hide_completer()
            except Exception:
                pass
            self.code_editor.insertPlainText('\n')
        else:
            self.code_editor.insertPlainText(ch)
            self.code_editor.maybe_show_completions()


class CodeEditor(QPlainTextEdit):
    fileDropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        # Prefer a fixed-width system font for code.
        try:
            fixed = QFontDatabase.systemFont(QFontDatabase.FixedFont)
            if fixed:
                self.setFont(fixed)
        except Exception:
            pass
        try:
            metrics = QFontMetrics(self.font())
            self.setTabStopDistance(4 * metrics.horizontalAdvance(' '))
        except Exception:
            pass

        # Basic word list for autocomplete (Python-ish + common terms)
        words = [
            'def','class','import','from','as','return','if','elif','else','for','while','try','except','finally','with','yield','lambda',
            'True','False','None','and','or','not','in','is','pass','break','continue','global','nonlocal','assert','raise',
            'print','input','len','range','open','list','dict','set','tuple','str','int','float','bool','sum','min','max','map','filter','zip','enumerate'
        ]
        self._model = QStringListModel(words, self)
        self._completer = QCompleter(self._model, self)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.activated.connect(self.insert_completion)

    def insertFromMimeData(self, source):
        try:
            if hasattr(source, "hasHtml") and source.hasHtml():
                html = source.html()
                doc = QTextDocument()
                doc.setHtml(html)
                text = doc.toPlainText()
            elif source.hasText():
                text = source.text()
            else:
                return super().insertFromMimeData(source)

            text = text.replace('\r\n', '\n').replace('\r', '\n')
            text = text.replace('\u00A0', ' ').replace('\u202F', ' ')
            self.insertPlainText(text)
        except Exception:
            super().insertFromMimeData(source)

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            for url in md.urls():
                if url.isLocalFile():
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            for url in md.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    self.fileDropped.emit(path)
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)

    def current_word(self):
        cursor = self.textCursor()
        cursor.select(cursor.WordUnderCursor)
        return cursor.selectedText()

    def insert_completion(self, completion):
        cursor = self.textCursor()
        cursor.select(cursor.WordUnderCursor)
        cursor.insertText(completion)
        self.setTextCursor(cursor)

    def hide_completer(self):
        try:
            self._completer.popup().hide()
        except Exception:
            pass

    def maybe_show_completions(self):
        prefix = self.current_word()
        if not prefix or len(prefix) < 2 or not (prefix[-1].isalnum() or prefix[-1] == '_'):
            self.hide_completer()
            return
        self._completer.setCompletionPrefix(prefix)
        cr = self.cursorRect()
        cr.setWidth(self._completer.popup().sizeHintForColumn(0) + self._completer.popup().verticalScrollBar().sizeHint().width())
        self._completer.complete(cr)

    # (Removed erroneous TypingWorker methods incorrectly placed here.)


class AutoTyperApp(QWidget):
    start_typing_signal = pyqtSignal()
    stop_typing_signal = pyqtSignal()
    resume_typing_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_AUTHOR, APP_NAME)
        self.worker, self.thread = None, None
        self.is_paused = False
        self._suppress_input_mode_changed = False
        self._suppress_persona_changed = False
        self._last_input_tab_index = 0
        self.hotkey_listener = None
        self.hotkey_listener_thread = None
        self.init_ui()
        self.load_settings()
        self.start_listener()
        self.start_typing_signal.connect(self.start_typing)
        self.stop_typing_signal.connect(self.stop_typing)
        self.resume_typing_signal.connect(self.resume_typing)
        try:
            logger.info(f"App started v{APP_VERSION} on {platform.system()} {platform.release()} | Python {platform.python_version()}")
        except Exception:
            pass

        # --- Trigger Accessibility prompt early ---
        if platform.system() == "Darwin":
            try:
                # Perform a simple pyautogui action that requires Accessibility
                # This will make macOS pop up the Accessibility permission prompt if it hasn't already.
                _ = pyautogui.size() # Or pyautogui.position()
            except Exception as e:
                # This exception likely means permissions are not granted,
                # but the user needs to go to System Settings for the full message.
                print(f"PyAutoGUI check failed (expected if permissions are not set): {e}")

        self.check_macos_permissions() # Your existing informational QMessageBox
    
    def _translate_hotkey_for_pynput(self, hotkey):
        """Translates a Qt hotkey (QKeySequence text) to pynput GlobalHotKeys format."""
        if not hotkey:
            return ""
        # Normalize whatever we stored (NativeText/PortableText) into PortableText.
        try:
            hotkey = QKeySequence(str(hotkey)).toString(QKeySequence.PortableText)
        except Exception:
            hotkey = str(hotkey)

        hotkey = (hotkey or "").strip()
        if not hotkey:
            return ""

        # Only support single-chord hotkeys; ignore additional sequences if present.
        if ',' in hotkey:
            hotkey = hotkey.split(',', 1)[0].strip()

        parts = [p.strip() for p in hotkey.split('+') if p.strip()]
        if not parts:
            return ""

        mod_map = {
            'ctrl': '<ctrl>', 'control': '<ctrl>',
            'alt': '<alt>', 'option': '<alt>', 'opt': '<alt>',
            'shift': '<shift>',
            # Qt uses Meta for Command (macOS) / Windows key.
            'meta': '<cmd>', 'cmd': '<cmd>', 'command': '<cmd>', 'win': '<cmd>', 'windows': '<cmd>', 'super': '<cmd>',
        }
        key_map = {
            'esc': '<esc>', 'escape': '<esc>',
            'enter': '<enter>', 'return': '<enter>',
            'tab': '<tab>',
            'space': '<space>', 'spacebar': '<space>',
            'backspace': '<backspace>',
            'delete': '<delete>',
            'up': '<up>', 'down': '<down>', 'left': '<left>', 'right': '<right>',
            'home': '<home>', 'end': '<end>',
            'pageup': '<page_up>', 'pagedown': '<page_down>',
        }

        out = []
        for part in parts:
            p = part.lower().strip()
            token = mod_map.get(p) or key_map.get(p) or p
            # For non-character keys, pynput expects angle-bracket notation.
            if not token.startswith('<') and len(token) > 1:
                token = f"<{token}>"
            out.append(token)

        return '+'.join(out)

    def _get_active_window_title_main(self):
        try:
            if platform.system() == "Darwin":
                return AppKit.NSWorkspace.sharedWorkspace().frontmostApplication().localizedName()
            return pyautogui.getActiveWindowTitle() or "Unknown"
        except Exception:
            return "Unknown"

    def _categorize_title(self, title):
        t = (title or "").lower()
        if any(k in t for k in ["code", "pycharm", "intellij", "webstorm", "clion", "goland", "xcode", "sublime", "atom", "notepad++", "vim", "emacs"]):
            return 'code'
        if any(k in t for k in ["slack", "teams", "discord", "skype", "telegram", "whatsapp", "wechat", "messages", "imessage"]):
            return 'chat'
        if any(k in t for k in ["notepad", "textedit", "notes"]):
            return 'text'
        if any(k in t for k in ["safari", "chrome", "chromium", "firefox", "edge", "brave", "opera"]):
            return 'browser'
        return 'unknown'

    def _detect_content_kind(self, text: str) -> str:
        """Heuristic content detection: returns 'code', 'math', or 'prose'."""
        t = text.strip()
        if not t:
            return 'prose'
        try:
            if self._looks_like_code(t):
                return 'code'
            if self._looks_like_math(t):
                return 'math'
        except Exception:
            pass
        return 'prose'

    def _contains_non_ascii(self, t: str) -> bool:
        try:
            return any(ord(ch) > 0x7F for ch in t)
        except Exception:
            return False

    def _looks_like_code(self, t: str) -> bool:
        # Fast signals
        if '```' in t or '\t' in t:
            return True
        # Programming keywords across common languages
        code_keywords = [
            'import ', 'from ', 'def ', 'class ', 'return', 'if ', 'elif ', 'else:', 'while ', 'for ', 'try:', 'except', 'finally:',
            'function ', 'var ', 'let ', 'const ', '=>', 'console.log', 'export ', 'require(', 'module.exports',
            '#include', 'using ', 'namespace ', 'public ', 'private ', 'protected ', 'static ', 'void ', 'int ', 'string ', 'std::',
            'fn ', 'match ', 'impl ', 'package ', 'interface ', 'enum ', 'struct '
        ]
        if any(kw in t for kw in code_keywords):
            return True
        # Symbols and patterns common in code
        code_symbol_hits = sum(1 for ch in t if ch in '{}();<>[]:=#')
        lines = t.splitlines()
        semicolon_lines = sum(1 for ln in lines if ln.strip().endswith(';'))
        brace_lines = sum(1 for ln in lines if ln.strip().endswith('{') or ln.strip().endswith('}'))
        indent_lines = sum(1 for ln in lines if ln.startswith('    ') or ln.startswith('\t'))
        # Heuristic thresholds
        if code_symbol_hits >= max(6, len(t) // 80):
            return True
        if (semicolon_lines + brace_lines + indent_lines) >= max(3, len(lines) // 4):
            return True
        return False

    def _looks_like_math(self, t: str) -> bool:
        # Detect LaTeX math markers or Unicode math symbols
        latex_markers = [
            '\\frac', '\\sum', '\\prod', '\\int', '\\sqrt', '\\lim', '\\infty', '\\approx', '\\neq', '\\leq', '\\geq',
            '\\alpha', '\\beta', '\\gamma', '\\delta', '\\theta', '\\lambda', '\\mu', '\\pi', '\\sigma', '\\omega', '$'
        ]
        if any(m in t for m in latex_markers):
            return True
        math_chars = set('∑∏√∞≤≥≈≠±°×÷∂∇πθαλµσδΩω∧∨⊂⊆∈∉∪∩∘→←↔·′″≃≡⊥∥∖∫∮∝')
        math_hits = sum(1 for ch in t if ch in math_chars)
        caret_unders = t.count('^') + t.count('_')
        # Equations often have many operators
        operator_hits = sum(1 for ch in t if ch in '+-*/=<>')
        if math_hits >= 1:
            return True
        if caret_unders >= 2 and operator_hits >= 2:
            return True
        # Many short lines with operators suggests laid-out formula
        lines = t.splitlines()
        short_eq_lines = sum(1 for ln in lines if len(ln.strip()) <= 24 and any(op in ln for op in ['=', '≤', '≥', '≠']))
        if short_eq_lines >= 2:
            return True
        return False

    def check_macos_permissions(self):
        if platform.system() == "Darwin":
            # We cannot programmatically check the _status_ of permissions,
            # but we can remind the user and guide them on demand.
            try:
                logger.info("macOS permissions reminder shown in logs")
            except Exception:
                pass
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
            pass

        main_layout = QVBoxLayout(self)
        main_layout.setMenuBar(self.menu_bar)
        try:
            main_layout.setContentsMargins(12, 12, 12, 12)
            main_layout.setSpacing(10)
        except Exception:
            pass
        try:
            self.setMinimumSize(980, 640)
            self.resize(1240, 780)
        except Exception:
            pass

        # --- Split layout: settings (left) + editor/run (right) ---
        self.splitter = QSplitter(Qt.Horizontal, self)
        main_layout.addWidget(self.splitter, 1)

        # Left: scrollable settings
        settings_scroll = QScrollArea(self)
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QFrame.NoFrame)
        try:
            settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            settings_scroll.setMinimumWidth(420)
        except Exception:
            pass
        settings_container = QWidget(settings_scroll)
        settings_scroll.setWidget(settings_container)
        settings_container_layout = QVBoxLayout(settings_container)
        settings_container_layout.setContentsMargins(0, 0, 0, 0)

        self.settings_group_box = QGroupBox("Configuration")
        try:
            self.settings_group_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        except Exception:
            pass
        settings_container_layout.addWidget(self.settings_group_box, 0)
        settings_container_layout.addStretch(1)
        self.splitter.addWidget(settings_scroll)

        # Settings tabs
        settings_layout = QVBoxLayout()
        self.settings_tabs = QTabWidget(self)
        settings_layout.addWidget(self.settings_tabs)

        # --- Setup tab (Basics + Handling) ---
        setup_tab = QWidget(self)
        setup_layout = QVBoxLayout(setup_tab)
        try:
            setup_layout.setContentsMargins(8, 8, 8, 8)
            setup_layout.setSpacing(10)
        except Exception:
            pass

        basics_box = QGroupBox("Basics")
        basics_form = QFormLayout()
        try:
            basics_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        except Exception:
            pass

        self.laps_spin = QSpinBox()
        self.laps_spin.setRange(1, 1000)
        self.laps_spin.setValue(DEFAULT_LAPS)
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 60)
        self.delay_spin.setValue(DEFAULT_DELAY)
        basics_form.addRow("Laps:", self.laps_spin)
        basics_form.addRow("Start delay (sec):", self.delay_spin)

        self.persona_combo = QComboBox()
        self.persona_combo.addItems(["Custom (Manual Settings)", "Deliberate Writer", "Fast Messenger", "Careful Coder"])
        self.persona_combo.currentIndexChanged.connect(self.on_persona_changed)
        basics_form.addRow("Typing persona:", self.persona_combo)
        basics_box.setLayout(basics_form)
        setup_layout.addWidget(basics_box)

        self.manual_settings_group = QGroupBox("Humanization")
        manual_layout = QVBoxLayout()
        self.min_wpm_slider = QSlider(Qt.Horizontal)
        self.min_wpm_slider.setRange(MIN_WPM_LIMIT, MAX_WPM_LIMIT)
        self.min_wpm_slider.setValue(DEFAULT_MIN_WPM)
        self.max_wpm_slider = QSlider(Qt.Horizontal)
        self.max_wpm_slider.setRange(MIN_WPM_LIMIT, MAX_WPM_LIMIT)
        self.max_wpm_slider.setValue(DEFAULT_MAX_WPM)
        self.min_wpm_label = QLabel(f"Min: {DEFAULT_MIN_WPM} WPM")
        self.max_wpm_label = QLabel(f"Max: {DEFAULT_MAX_WPM} WPM")
        speed1 = QHBoxLayout()
        speed1.addWidget(self.min_wpm_label, 1)
        speed1.addWidget(self.min_wpm_slider, 4)
        speed2 = QHBoxLayout()
        speed2.addWidget(self.max_wpm_label, 1)
        speed2.addWidget(self.max_wpm_slider, 4)
        self.add_mistakes_checkbox = QCheckBox("Add mistakes")
        self.add_mistakes_checkbox.setChecked(True)
        self.pause_on_punct_checkbox = QCheckBox("Pause on punctuation")
        self.pause_on_punct_checkbox.setChecked(True)
        human_layout = QHBoxLayout()
        human_layout.addWidget(self.add_mistakes_checkbox)
        human_layout.addWidget(self.pause_on_punct_checkbox)
        human_layout.addStretch()
        manual_layout.addLayout(speed1)
        manual_layout.addLayout(speed2)
        manual_layout.addLayout(human_layout)
        self.manual_settings_group.setLayout(manual_layout)
        setup_layout.addWidget(self.manual_settings_group)

        self.newline_group_box = QGroupBox("Handling")
        newline_layout = QVBoxLayout()
        self.paste_mode_radio = QRadioButton("Line Paste (fastest)")
        self.paste_mode_radio.setToolTip("Pastes line-by-line using the clipboard (fast). Some apps may block paste.")
        self.standard_radio = QRadioButton("Standard Typing (as-is)")
        self.standard_radio.setToolTip("Types every character exactly as provided.")
        self.smart_radio = QRadioButton("Smart Newlines (prose)")
        self.smart_radio.setToolTip("Turns single line breaks into spaces; double breaks remain paragraphs.")
        self.list_mode_radio = QRadioButton("List Mode (code editors)")
        self.list_mode_radio.setToolTip("Strips leading indentation; your editor controls indentation.")
        self.standard_radio.setChecked(True)
        newline_layout.addWidget(self.paste_mode_radio)
        newline_layout.addWidget(self.standard_radio)
        newline_layout.addWidget(self.smart_radio)
        newline_layout.addWidget(self.list_mode_radio)
        newline_layout.addSpacing(6)
        self.use_shift_enter_checkbox = QCheckBox("Shift+Enter newlines (chat apps)")
        self.use_shift_enter_checkbox.setToolTip("Use Shift+Enter instead of Enter for newlines (prevents sending).")
        newline_layout.addWidget(self.use_shift_enter_checkbox)
        self.type_tabs_checkbox = QCheckBox("Preserve tab characters")
        self.type_tabs_checkbox.setChecked(True)
        newline_layout.addWidget(self.type_tabs_checkbox)
        self.press_esc_checkbox = QCheckBox("Send Esc before Enter (dismiss autocomplete)")
        self.press_esc_checkbox.setChecked(False)
        newline_layout.addWidget(self.press_esc_checkbox)
        self.mouse_jitter_checkbox = QCheckBox("Background mouse jitter")
        self.mouse_jitter_checkbox.setChecked(True)
        self.mouse_jitter_checkbox.setToolTip("Tiny background mouse movement to prevent idle (optional).")
        newline_layout.addWidget(self.mouse_jitter_checkbox)
        self.auto_detect_checkbox = QCheckBox("Auto-optimize for target app")
        self.auto_detect_checkbox.setChecked(True)
        newline_layout.addWidget(self.auto_detect_checkbox)
        self.ime_friendly_checkbox = QCheckBox("IME-friendly (paste typing)")
        newline_layout.addWidget(self.ime_friendly_checkbox)
        self.unicode_hex_checkbox = QCheckBox("Unicode Hex typing (macOS)")
        if platform.system() != 'Darwin':
            self.unicode_hex_checkbox.setEnabled(False)
            self.unicode_hex_checkbox.setToolTip("macOS only. Enable the 'Unicode Hex Input' keyboard layout.")
        else:
            self.unicode_hex_checkbox.setToolTip("Requires 'Unicode Hex Input' input source in System Settings > Keyboard.")
            self.unicode_hex_checkbox.setChecked(True)
        newline_layout.addWidget(self.unicode_hex_checkbox)
        self.compliance_mode_checkbox = QCheckBox("Compliance mode (block apps)")
        self.compliance_mode_checkbox.setToolTip("Auto-pauses when a blocked app becomes active.")
        newline_layout.addWidget(self.compliance_mode_checkbox)
        blocked_layout = QHBoxLayout()
        blocked_lbl = QLabel("Blocked apps:")
        blocked_lbl.setToolTip("Comma-separated list (used when Compliance mode is enabled).")
        blocked_layout.addWidget(blocked_lbl)
        self.blocked_apps_edit = QLineEdit("Chrome,Safari,Firefox,Edge,Brave,Opera")
        blocked_layout.addWidget(self.blocked_apps_edit, 1)
        newline_layout.addLayout(blocked_layout)
        self.newline_group_box.setLayout(newline_layout)
        setup_layout.addWidget(self.newline_group_box)

        setup_layout.addStretch(1)
        self.settings_tabs.addTab(setup_tab, "Setup")

        # --- Safety tab ---
        safety_tab = QWidget(self)
        safety_layout = QVBoxLayout(safety_tab)
        safety_box = QGroupBox("Safety & Macros")
        safety_box_layout = QVBoxLayout()
        self.enable_macros_checkbox = QCheckBox("Enable macro execution ({{PAUSE}}, {{PRESS}}, {{CLICK}})")
        self.enable_macros_checkbox.setChecked(True)
        self.enable_macros_checkbox.setToolTip("When off, macros are typed literally as text.")
        self.confirm_click_checkbox = QCheckBox("Confirm before executing CLICK macros")
        self.confirm_click_checkbox.setChecked(True)
        self.confirm_click_checkbox.setToolTip("Adds a confirmation prompt before any CLICK macro is executed.")
        safety_box_layout.addWidget(self.enable_macros_checkbox)
        safety_box_layout.addWidget(self.confirm_click_checkbox)
        safety_box.setLayout(safety_box_layout)
        safety_layout.addWidget(safety_box)
        self.settings_tabs.addTab(safety_tab, "Safety")

        self.settings_group_box.setLayout(settings_layout)

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
            pass
        self.open_tool_button = QToolButton(self)
        self.open_tool_button.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.open_tool_button.setToolTip("Open…")
        self.open_tool_button.setText("Open")
        self.open_tool_button.clicked.connect(self.open_file)
        tools_layout.addWidget(self.open_tool_button)

        self.save_tool_button = QToolButton(self)
        self.save_tool_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.save_tool_button.setToolTip("Save As…")
        self.save_tool_button.setText("Save")
        self.save_tool_button.clicked.connect(self.save_file)
        tools_layout.addWidget(self.save_tool_button)

        self.format_tool_button = QToolButton(self)
        try:
            fmt_pix = getattr(QStyle, "SP_FileDialogDetailedView", QStyle.SP_FileIcon)
        except Exception:
            fmt_pix = QStyle.SP_FileIcon
        self.format_tool_button.setIcon(self.style().standardIcon(fmt_pix))
        self.format_tool_button.setToolTip("Format tools")
        self.format_tool_button.setText("Format")
        self.format_tool_button.setPopupMode(QToolButton.InstantPopup)
        format_menu_popup = QMenu(self)
        format_menu_popup.addAction("Clean Whitespace", self.clean_whitespace)
        format_menu_popup.addSeparator()
        format_menu_popup.addAction("UPPERCASE", self.to_uppercase)
        format_menu_popup.addAction("lowercase", self.to_lowercase)
        format_menu_popup.addAction("Sentence case", self.to_sentence_case)
        self.format_tool_button.setMenu(format_menu_popup)
        tools_layout.addWidget(self.format_tool_button)

        self.macro_tool_button = QToolButton(self)
        try:
            macro_pix = getattr(QStyle, 'SP_CommandLink', QStyle.SP_DialogApplyButton)
        except Exception:
            macro_pix = QStyle.SP_DialogApplyButton
        self.macro_tool_button.setIcon(self.style().standardIcon(macro_pix))
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
        try:
            clean_pix = getattr(QStyle, "SP_BrowserReload", QStyle.SP_DialogResetButton)
        except Exception:
            clean_pix = QStyle.SP_DialogResetButton
        self.clean_button.setIcon(self.style().standardIcon(clean_pix))
        self.clean_button.setToolTip("Clean whitespace")
        self.clean_button.setText("Clean")
        self.clean_button.clicked.connect(self.clean_whitespace)
        tools_layout.addWidget(self.clean_button)

        self.clear_button = QToolButton(self)
        self.clear_button.setIcon(self.style().standardIcon(QStyle.SP_DialogDiscardButton))
        self.clear_button.setToolTip("Clear text")
        self.clear_button.setText("Clear")
        self.clear_button.clicked.connect(self.clear_text)
        tools_layout.addWidget(self.clear_button)

        for b in (self.open_tool_button, self.save_tool_button, self.format_tool_button,
                  self.macro_tool_button, self.clean_button, self.clear_button):
            try:
                b.setAutoRaise(True)
                b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                b.setIconSize(QSize(18, 18))
                b.setMinimumSize(64, 48)
            except Exception:
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

        # Tabs: Stats + Preview
        self.text_info_tabs = QTabWidget(self)

        stats_tab = QWidget(self)
        stats_grid = QGridLayout(stats_tab)
        stats_grid.setColumnStretch(1, 1)
        self.stats_words_value = QLabel("0")
        self.stats_chars_value = QLabel("0")
        self.stats_lines_value = QLabel("0")
        self.stats_macros_value = QLabel("0")
        self.stats_clicks_value = QLabel("0")
        self.stats_unicode_value = QLabel("0")
        self.stats_pause_value = QLabel("0.0s")
        self.stats_output_value = QLabel("0")
        for v in (
            self.stats_words_value, self.stats_chars_value, self.stats_lines_value, self.stats_macros_value,
            self.stats_clicks_value, self.stats_unicode_value, self.stats_pause_value, self.stats_output_value,
        ):
            try:
                v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            except Exception:
                pass
        stats_grid.addWidget(QLabel("Words:"), 0, 0)
        stats_grid.addWidget(self.stats_words_value, 0, 1)
        stats_grid.addWidget(QLabel("Chars:"), 1, 0)
        stats_grid.addWidget(self.stats_chars_value, 1, 1)
        stats_grid.addWidget(QLabel("Lines:"), 2, 0)
        stats_grid.addWidget(self.stats_lines_value, 2, 1)
        stats_grid.addWidget(QLabel("Macros:"), 3, 0)
        stats_grid.addWidget(self.stats_macros_value, 3, 1)
        stats_grid.addWidget(QLabel("CLICK macros:"), 4, 0)
        stats_grid.addWidget(self.stats_clicks_value, 4, 1)
        stats_grid.addWidget(QLabel("Non-ASCII:"), 5, 0)
        stats_grid.addWidget(self.stats_unicode_value, 5, 1)
        stats_grid.addWidget(QLabel("PAUSE total:"), 6, 0)
        stats_grid.addWidget(self.stats_pause_value, 6, 1)
        stats_grid.addWidget(QLabel("Output chars (all laps):"), 7, 0)
        stats_grid.addWidget(self.stats_output_value, 7, 1)
        self.text_info_tabs.addTab(stats_tab, "Stats")

        preview_tab = QWidget(self)
        preview_layout = QVBoxLayout(preview_tab)
        self.processed_preview = QPlainTextEdit(self)
        self.processed_preview.setReadOnly(True)
        self.processed_preview.setPlaceholderText("Output preview (sample)…")
        preview_layout.addWidget(self.processed_preview, 1)
        self.mode_note_label = QLabel("")
        self.mode_note_label.setWordWrap(True)
        preview_layout.addWidget(self.mode_note_label)
        self.text_info_tabs.addTab(preview_tab, "Preview")

        try:
            # Keep the editor as the primary focus; details stay compact but readable.
            self.text_info_tabs.setMaximumHeight(240)
        except Exception:
            pass
        right_layout.addWidget(self.text_info_tabs)

        # Run group
        self.run_group_box = QGroupBox("Run")
        run_layout = QVBoxLayout()
        run_btns = QHBoxLayout()
        self.start_button = QPushButton()
        self.start_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.pause_button = QPushButton("PAUSE")
        self.pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.pause_button.setEnabled(False)
        self.stop_button = QPushButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        for b in (self.start_button, self.pause_button, self.stop_button):
            try:
                b.setMinimumHeight(38)
            except Exception:
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
        self.status_badge = QLabel()
        self.status_badge.setFixedSize(10, 10)
        self.status_badge.setStyleSheet("background-color: #888; border-radius: 5px;")
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
        self.run_group_box.setLayout(run_layout)
        right_layout.addWidget(self.run_group_box)

        self.splitter.addWidget(right_container)
        try:
            self.splitter.setCollapsible(0, False)
            self.splitter.setCollapsible(1, False)
            self.splitter.setStretchFactor(0, 0)
            self.splitter.setStretchFactor(1, 1)
            # Reasonable defaults; user can resize and it's persisted.
            self.splitter.setSizes([440, 800])
        except Exception:
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
            idx = 0
        return self.code_text_edit if idx == 1 else self.plain_text_edit

    def _all_editors(self):
        return (self.plain_text_edit, self.code_text_edit)

    def input_mode_name(self) -> str:
        try:
            return "Code" if int(self.input_tabs.currentIndex()) == 1 else "Plain Text"
        except Exception:
            return "Plain Text"

    def get_input_text(self) -> str:
        try:
            return self._active_editor().toPlainText()
        except Exception:
            return ""

    def set_input_text(self, text: str):
        try:
            self._active_editor().setPlainText(text or "")
        except Exception:
            pass

    def clear_text(self):
        try:
            self._active_editor().clear()
        except Exception:
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
            return False
        finally:
            try:
                self.settings.endGroup()
            except Exception:
                pass

    def _write_input_mode_preset(self, idx: int, preset: dict):
        try:
            key = self._input_mode_key(idx)
            self.settings.beginGroup(f"ModePresets/{key}")
            for k, v in (preset or {}).items():
                self.settings.setValue(k, v)
        except Exception:
            pass
        finally:
            try:
                self.settings.endGroup()
            except Exception:
                pass

    def _save_input_mode_preset(self, idx: int):
        try:
            key = self._input_mode_key(idx)
            preset = self._capture_input_mode_preset()
            self.settings.beginGroup(f"ModePresets/{key}")
            for k, v in preset.items():
                self.settings.setValue(k, v)
        except Exception:
            pass
        finally:
            try:
                self.settings.endGroup()
            except Exception:
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
            preset = None
        finally:
            try:
                self.settings.endGroup()
            except Exception:
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
            old_index = 0
        try:
            new_index = int(index)
        except Exception:
            new_index = int(self.input_tabs.currentIndex())

        # Save current settings for the mode we're leaving, then restore settings for the mode we're entering.
        try:
            self._save_input_mode_preset(old_index)
        except Exception:
            pass
        try:
            self._load_input_mode_preset(new_index, apply_defaults=True)
        except Exception:
            pass

        self._last_input_tab_index = new_index
        try:
            self.settings.setValue("inputMode", new_index)
        except Exception:
            pass
        self.schedule_text_update()

    def schedule_text_update(self):
        """Debounced refresh for estimate/stats/preview to handle large inputs smoothly."""
        try:
            if hasattr(self, "_text_update_timer") and self._text_update_timer:
                self._text_update_timer.start(150)
                return
        except Exception:
            pass
        self.refresh_text_insights()

    def refresh_text_insights(self):
        try:
            self.update_preview()
        except Exception:
            pass
        try:
            self.update_text_stats()
        except Exception:
            pass
        try:
            self.update_processed_preview()
        except Exception:
            pass
        try:
            self.update_mode_note()
        except Exception:
            pass
        try:
            self._update_start_button_enabled()
        except Exception:
            pass

    def on_macros_toggled(self, checked: bool):
        try:
            self.confirm_click_checkbox.setEnabled(bool(checked))
        except Exception:
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
                pass

    def _set_ui_for_paused(self, paused: bool):
        """While paused, allow editing/tuning settings before resuming."""
        enable = bool(paused)
        try:
            self.settings_group_box.setEnabled(enable)
        except Exception:
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
                pass
        try:
            for ed in self._all_editors():
                ed.setEnabled(enable)
        except Exception:
            pass

    def _apply_runtime_settings_to_worker(self):
        """Apply UI changes to the current worker (best-effort; affects remaining text)."""
        if not self.worker:
            return
        try:
            self.worker.update_speed_range(self.min_wpm_slider.value(), self.max_wpm_slider.value())
        except Exception:
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
            pass
        self.status_label.setText(f"Status: Resuming in {seconds}…")
        try:
            self._resume_countdown_timer.start()
        except Exception:
            pass

    def _cancel_resume_countdown(self, silent: bool = False):
        if not getattr(self, "_resume_countdown_active", False):
            return
        self._resume_countdown_active = False
        self._resume_countdown_remaining = 0
        try:
            self._resume_countdown_timer.stop()
        except Exception:
            pass
        if not silent:
            try:
                self.status_label.setText("Status: Resume canceled.")
            except Exception:
                pass
        # Restore paused UI affordance
        try:
            self.pause_button.setText("RESUME")
            self.pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        except Exception:
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
                pass
            try:
                self.worker.resume()
            except Exception:
                pass
            return
        try:
            self.status_label.setText(f"Status: Resuming in {remaining}…")
        except Exception:
            pass
        try:
            self.pause_button.setText(f"CANCEL ({remaining})")
        except Exception:
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
            self.status_badge.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        except Exception:
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
            return True

    def _strip_macros_ui(self, text: str) -> str:
        if not self._macros_enabled():
            return text
        try:
            return re.sub(r"(?i)\{\{(?:PAUSE|PRESS|CLICK|COMMENT):.*?\}\}", "", text)
        except Exception:
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
                    continue
                if t <= 0:
                    continue
                total += min(t, 60.0)
        except Exception:
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
        words = len(re.findall(r"\b\w+\b", text))
        chars = len(text)
        lines = len(text.splitlines()) if text else 0
        non_ascii = 0
        try:
            non_ascii = sum(1 for ch in text if ord(ch) > 0x7F)
        except Exception:
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
            try:
                editor.insertPlainText(text)
            except Exception:
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
            pass
        for ed in self._all_editors():
            try:
                ed.setEnabled(not is_running)
            except Exception:
                pass
        self.menu_bar.setEnabled(not is_running)
        self.open_tool_button.setEnabled(not is_running)
        self.save_tool_button.setEnabled(not is_running)
        self.format_tool_button.setEnabled(not is_running)
        self.macro_tool_button.setEnabled(not is_running)
        self.clean_button.setEnabled(not is_running)
        self.clear_button.setEnabled(not is_running)
        self.settings_group_box.setEnabled(not is_running)
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
            pass
        self.schedule_text_update()

    def toggle_persona_controls(self):
        persona = self.persona_combo.currentText()
        self.manual_settings_group.setEnabled(True)

        try:
            in_plain = int(self.input_tabs.currentIndex()) == 0
        except Exception:
            in_plain = True

        def _maybe_enable_unicode_hex_default():
            if platform.system() == "Darwin" and getattr(self, "unicode_hex_checkbox", None):
                try:
                    if self.unicode_hex_checkbox.isEnabled():
                        self.unicode_hex_checkbox.setChecked(True)
                except Exception:
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
                pass
            try:
                self.use_shift_enter_checkbox.setChecked(False)
            except Exception:
                pass
            try:
                self.press_esc_checkbox.setChecked(True)
            except Exception:
                pass
            try:
                self.type_tabs_checkbox.setChecked(False)
            except Exception:
                pass
            try:
                self.add_mistakes_checkbox.setChecked(False)
            except Exception:
                pass
            try:
                self.pause_on_punct_checkbox.setChecked(True)
            except Exception:
                pass
            try:
                self.mouse_jitter_checkbox.setChecked(False)
            except Exception:
                pass
            try:
                self.ime_friendly_checkbox.setChecked(False)
            except Exception:
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
                        invalid += 1
            except Exception:
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
                source_app = self._get_active_window_title_main()
        except Exception:
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
                    pass
        except Exception:
            pass

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
        }

        # Log start
        try:
            logger.info(f"Typing start | persona={self.persona_combo.currentText()} mode={newline_mode} min={self.min_wpm_slider.value()} max={self.max_wpm_slider.value()} ime={self.ime_friendly_checkbox.isChecked()} laps={self.laps_spin.value()}")
        except Exception:
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
        self.min_wpm_label.setText(f"Min: {min_wpm} WPM")
        self.max_wpm_label.setText(f"Max: {max_wpm} WPM")
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
            pass
        if self.worker:
            self.worker.stop()
        self.is_paused = False
        try:
            logger.info("Typing stop requested")
        except Exception:
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
            pass
        # Keep START reserved for starting a new run; use PAUSE/RESUME for pausing.
        self.start_button.setEnabled(False)
        try:
            self.pause_button.setText("RESUME")
            self.pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        except Exception:
            pass
        # Allow tuning settings while paused.
        self._set_ui_for_paused(True)
        self._set_status_state("paused")
        self.status_label.setText("Status: Paused. You can adjust settings. Resuming uses a 4s countdown.")

    def on_typing_resumed(self):
        try:
            self._cancel_resume_countdown(silent=True)
        except Exception:
            pass
        self.is_paused = False
        self.set_ui_for_running(True)
        self.update_button_hotkey_text()
        try:
            self.pause_button.setText("PAUSE")
            self.pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        except Exception:
            pass
        self.status_label.setText("Status: Resumed typing...")

    def on_typing_finished(self):
        self.is_paused = False
        try:
            self._cancel_resume_countdown(silent=True)
        except Exception:
            pass
        self.set_ui_for_running(False)
        self.update_button_hotkey_text()
        try:
            self.pause_button.setText("PAUSE")
            self.pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        except Exception:
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
            pass

    def show_about_dialog(self):
        self.stop_listener()
        dialog = AboutDialog(self)
        dialog.exec_()
        self.start_listener()

    def show_settings_dialog(self):
        self.stop_listener()
        dialog = SettingsDialog(self)
        result = dialog.exec_()
        self.start_listener()

        if result == QDialog.Accepted:
            self.update_button_hotkey_text()
            # NOW we can safely show the confirmation message
            self.stop_listener()
            QMessageBox.information(self, "Settings Saved", "Hotkey settings have been updated and the listener was restarted.")
            self.start_listener()

    def show_help_dialog(self):
        self.stop_listener()
        dialog = HelpDialog(self)
        dialog.exec_()
        self.start_listener()

    def show_diagnostics_dialog(self):
        self.stop_listener()
        dialog = DiagnosticsDialog(self)
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
            pass
        self.stop_listener()
        self.dry_run_dialog = DryRunDialog(self)
        self.dry_run_dialog.setWindowModality(Qt.NonModal)
        # When closed, clear reference and restart listener
        def _cleanup():
            try:
                self.start_listener()
            except Exception:
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
            start = str(start_raw)
        try:
            stop = QKeySequence(str(stop_raw)).toString(QKeySequence.NativeText) or str(stop_raw)
        except Exception:
            stop = str(stop_raw)
        self.start_button.setText(f"START ({start})")
        self.stop_button.setText(f"STOP ({stop})")

    def start_listener(self):
        # Respect setting; disable on macOS 15 by default
        default_enable = True
        if platform.system() == "Darwin":
            try:
                major = int(platform.mac_ver()[0].split('.')[0]) if platform.mac_ver()[0] else 0
            except Exception:
                major = 0
            if major >= 15:
                default_enable = False
        if not self.settings.value("enableGlobalHotkeys", default_enable, type=bool):
            self.status_label.setText("Status: Global hotkeys disabled. Use buttons or enable in Settings.")
            return
        # Avoid spawning multiple global listeners.
        if self.hotkey_listener_thread and self.hotkey_listener_thread.is_alive():
            return
        self.hotkey_listener_thread = threading.Thread(target=self._run_listener, daemon=True)
        self.hotkey_listener_thread.start()

    def stop_listener(self):
        listener = getattr(self, 'hotkey_listener', None)
        if listener:
            try:
                listener.stop()
            except Exception:
                pass
        self.hotkey_listener = None
        # Join briefly so restarts are reliable (especially for modeless dialogs).
        if self.hotkey_listener_thread and self.hotkey_listener_thread.is_alive():
            try:
                self.hotkey_listener_thread.join(timeout=0.5)
            except Exception:
                pass
        if self.hotkey_listener_thread and not self.hotkey_listener_thread.is_alive():
            self.hotkey_listener_thread = None
        
    def _run_listener(self):
        """The target function for the listener thread."""
        try:
            # Translate hotkeys before passing them to the listener
            start_key = self._translate_hotkey_for_pynput(self.settings.value("startHotkey", DEFAULT_START_HOTKEY))
            stop_key = self._translate_hotkey_for_pynput(self.settings.value("stopHotkey", DEFAULT_STOP_HOTKEY))
            resume_key = self._translate_hotkey_for_pynput(self.settings.value("resumeHotkey", DEFAULT_RESUME_HOTKEY))

            hotkeys = {}
            if start_key:
                hotkeys[start_key] = self.start_typing_signal.emit
            if stop_key:
                hotkeys[stop_key] = self.stop_typing_signal.emit
            if resume_key:
                hotkeys[resume_key] = self.resume_typing_signal.emit

            if not hotkeys:
                try:
                    logger.warning("Global hotkeys not started: no valid hotkey bindings")
                except Exception:
                    pass
                return
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkeys)
            self.hotkey_listener.run()
        except Exception as e:
            try:
                logger.exception("Hotkey listener error")
            except Exception:
                pass
            print(f"Hotkey listener error: {e}")

    def toggle_dark_mode(self, checked):
        self.setStyleSheet(DARK_STYLESHEET if checked else "")
        self.settings.setValue("darkMode", checked)

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
        # Normalize line endings first.
        text = str(text).replace('\r\n', '\n').replace('\r', '\n')
        # Trim trailing spaces, preserving line structure (including trailing blank lines).
        lines = [line.rstrip() for line in text.split('\n')]
        cleaned = '\n'.join(lines)
        # Plain Text mode: also collapse excessive blank lines and trim outer whitespace.
        if self.input_mode_name() == "Plain Text":
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
        self.set_input_text(cleaned)

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

    def load_text_from_path(self, path):
        try:
            ext = os.path.splitext(path)[1].lower()
            text = None
            if ext in ('.html', '.htm'):
                # Convert HTML to plain text via Qt
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    html = f.read()
                doc = QTextDocument()
                doc.setHtml(html)
                text = doc.toPlainText()
            elif ext == '.rtf' and platform.system() == "Darwin":
                # Leverage macOS textutil if available
                try:
                    out = subprocess.check_output(["textutil", "-convert", "txt", "-stdout", path])
                    text = out.decode('utf-8', errors='ignore')
                except Exception:
                    text = None
            if text is None:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            # Normalize newlines
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            try:
                code_exts = {
                    '.py', '.pyw', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cc', '.cpp', '.h', '.hpp',
                    '.cs', '.go', '.rs', '.swift', '.kt', '.kts', '.m', '.mm', '.php', '.rb', '.sh', '.bash',
                    '.zsh', '.ps1', '.sql', '.toml', '.yaml', '.yml', '.json', '.xml', '.ini', '.cfg', '.gradle',
                }
                prefer_code = ext in code_exts
                if not prefer_code:
                    prefer_code = bool(text and self._looks_like_code(text))
                self.input_tabs.setCurrentIndex(1 if prefer_code else 0)
            except Exception:
                pass
            self.set_input_text(text)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open file: {e}")

    def open_file(self):
        filters = (
            "All Supported (*.txt *.md *.markdown *.html *.htm *.rtf *.py *.js *.ts *.java *.c *.cpp *.h *.hpp *.cs *.go *.rs *.swift *.kt *.json *.yaml *.yml);;"
            "Text/Markdown/HTML/RTF (*.txt *.md *.markdown *.html *.htm *.rtf);;"
            "Code Files (*.py *.js *.ts *.java *.c *.cpp *.h *.hpp *.cs *.go *.rs *.swift *.kt);;"
            "All Files (*)"
        )
        path, _ = QFileDialog.getOpenFileName(self, "Open Text File", "", filters)
        if not path:
            return
        self.load_text_from_path(path)

    def save_file(self):
        default_filter = "Text Files (*.txt)" if self.input_mode_name() == "Plain Text" else "Code Files (*.py *.txt)"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save File As...",
            "",
            "Text Files (*.txt);;Code Files (*.py *.js *.ts *.java *.c *.cpp *.h *.hpp *.cs *.go *.rs *.swift *.kt);;All Files (*)",
            default_filter,
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.get_input_text())
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save file: {e}")

    def load_settings(self):
        if geom := self.settings.value("geometry"):
            self.restoreGeometry(geom)
        if self.settings.value("darkMode", False, type=bool):
            self.dark_mode_action.setChecked(True)
            self.toggle_dark_mode(True)
        
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
                    left = int(sizes[0])
                    right = int(sizes[1])
                    min_left, min_right = 420, 560
                    total = left + right
                    if total <= 0:
                        total = max(1200, self.width())
                    if left < min_left or right < min_right:
                        left = max(min_left, min(480, total - min_right))
                        right = max(min_right, total - left)
                    self.splitter.setSizes([left, right])
        except Exception:
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
            pass
        finally:
            try:
                self.settings.endGroup()
            except Exception:
                pass
        # Seed per-input presets for first-time users (backwards compatible with older "UI" settings),
        # then apply the preset for the active tab.
        try:
            current_idx = int(self.input_tabs.currentIndex())
        except Exception:
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
                    code_mode = ""
                    code_persona = ""
                finally:
                    try:
                        self.settings.endGroup()
                    except Exception:
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
                    plain_mode = ""
                finally:
                    try:
                        self.settings.endGroup()
                    except Exception:
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
                    pass
            self._load_input_mode_preset(current_idx, apply_defaults=True)
            self._last_input_tab_index = current_idx
        except Exception:
            pass
        self.update_speed_labels()
        self.schedule_text_update()

    def save_settings(self):
        try:
            self._save_input_mode_preset(int(self.input_tabs.currentIndex()))
        except Exception:
            pass
        self.settings.setValue("geometry", self.saveGeometry())
        try:
            self.settings.setValue("inputMode", self.input_tabs.currentIndex())
        except Exception:
            pass
        try:
            if hasattr(self, "splitter"):
                self.settings.setValue("splitterSizes", self.splitter.sizes())
        except Exception:
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
            pass
        finally:
            try:
                self.settings.endGroup()
            except Exception:
                pass

    def closeEvent(self, event):
        self.save_settings()
        self.stop_listener()
        self.stop_typing()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Rely on Qt window management for stability across platforms
    window = AutoTyperApp()
    window.show()
    sys.exit(app.exec_())
