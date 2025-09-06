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
    QFileDialog, QAction, QMenuBar, QDialog, QLineEdit,
    QDialogButtonBox, QComboBox, QInputDialog, QTabWidget, QKeySequenceEdit,
    QFormLayout, QGroupBox, QRadioButton, QPlainTextEdit, QCompleter
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QSettings, QEvent, QUrl, QStringListModel, pyqtSlot
from PyQt5.QtGui import QKeySequence, QPixmap, QIcon, QTextDocument, QDesktopServices
import json
import logging
from logging.handlers import RotatingFileHandler

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
                <li><b>Careful Coder:</b> Uses List Mode, disables mistakes, sends Esc before Enter for IDEs.</li>
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
        self.settings.setValue("startHotkey", self.start_hotkey_edit.keySequence().toString())
        self.settings.setValue("stopHotkey", self.stop_hotkey_edit.keySequence().toString())
        self.settings.setValue("resumeHotkey", self.resume_hotkey_edit.keySequence().toString())
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
            import PyQt5
            import pynput
            import pyautogui as pag
            lines = [
                f"App: {APP_NAME} v{APP_VERSION}",
                f"OS: {platform.system()} {platform.release()} ({platform.machine()})",
                f"Python: {platform.python_version()}",
                f"PyQt5: {PyQt5.QtCore.QT_VERSION_STR}",
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
    update_etr = pyqtSignal(str)
    lap_progress = pyqtSignal(int, int)

    def __init__(self, text, laps, delay, **kwargs):
        super().__init__()
        self._running = True
        self._paused = False
        self.pause_event = threading.Event()
        self.pause_event.set() # Not paused initially
        self.text_to_type = text
        self.laps = laps
        self.delay = delay
        self.persona = kwargs.get('typing_persona')
        self.initial_window = None # To store the target window title

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
        self.compliance_mode = kwargs.get('compliance_mode', False)
        blocked = kwargs.get('blocked_apps', "") or ""
        self.blocked_apps = [b.strip().lower() for b in blocked.split(',') if b.strip()]
        self.auto_detect = kwargs.get('auto_detect', False)

    def stop(self):
        self._running = False
        self.resume() # Unpause if paused to allow thread to exit

    def pause(self, auto_resume_check=False):
        if not self._paused:
            self._paused = True
            self.pause_event.clear()
            self.paused_signal.emit()
            if auto_resume_check and self.initial_window:
                threading.Thread(target=self._auto_resume_checker, daemon=True).start()

    def resume(self):
        if self._paused:
            self._paused = False
            self.pause_event.set()
            self.resumed_signal.emit()

    def _auto_resume_checker(self):
        """Monitors active window and resumes typing if focus returns."""
        time.sleep(0.5)  # Prevent instant resume on quick window switches
        while self._paused and self._running:
            try:
                if self.get_active_window_title() == self.initial_window:
                    self.resume()
                    break
            except Exception:
                pass  # Ignore errors (e.g., window closed)
            time.sleep(0.5)

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

    def _sleep_interruptible(self, duration):
        """Sleep in small chunks while honoring stop/pause."""
        end = time.time() + max(0.0, duration)
        while self._running and time.time() < end:
            remaining = end - time.time()
            chunk = 0.02 if remaining > 0.02 else max(0.0, remaining)
            # Wait also respects pause_event
            self.pause_event.wait(timeout=chunk)
            if not self._running:
                break

    def _mouse_jitter_thread(self):
        # Moves mouse slightly at random intervals to simulate activity
        while self._running:
            pyautogui.move(random.randint(-1, 1), random.randint(-1, 1), duration=0.1)
            time.sleep(random.uniform(0.5, 3))

    def _paste_text(self, text):
        original_clip = None
        try:
            original_clip = pyperclip.paste()
        except Exception:
            original_clip = None
        pyperclip.copy(text)
        pyautogui.hotkey('command' if platform.system() == "Darwin" else 'ctrl', 'v')
        if original_clip is not None:
            try:
                pyperclip.copy(original_clip)
            except Exception:
                pass

    def _is_blocked_active(self):
        if not self.compliance_mode:
            return False
        title = self.get_active_window_title() or ""
        tl = title.lower()
        return any(k in tl for k in self.blocked_apps)

    def _type_segment(self, segment, overall_start_time, chars_completed, total_pause_duration, total_chars_overall):
        # Types a segment of text with human-like behavior, preserving code formatting
        prev_char = ''
        for char in segment:
            if char == '\t' and not self.type_tabs:
                continue # Skip this character and go to the next one
            
            if not self._running: 
                return chars_completed, total_pause_duration, False
            self.pause_event.wait()
            if not self._running:
                return chars_completed, total_pause_duration, False
            
            # Compliance guardrail
            if self._is_blocked_active() and not self._paused:
                self.update_status.emit("Compliance mode: blocked app active. Pausing...")
                self.pause(auto_resume_check=True)

            if self.get_active_window_title() != self.initial_window and not self._paused:
                self.pause(auto_resume_check=True)
            
            if self.add_mistakes and random.random() < self.mistake_chance:
                if char.lower() in KEY_ADJACENCY:
                    pyautogui.typewrite(random.choice(KEY_ADJACENCY[char.lower()]))
                    self._sleep_interruptible(random.uniform(0.1, 0.25))
                    pyautogui.press('backspace')
                    self._sleep_interruptible(random.uniform(0.05, 0.15))
            
            if char == '\n':
                if self.use_shift_enter:
                    pyautogui.hotkey('shift', 'enter')
                else:
                    pyautogui.press('enter')
            else:
                pyautogui.typewrite(char, interval=0.002)
            
            chars_completed += 1
            elapsed = (time.time() - overall_start_time) - total_pause_duration
            cpm = (chars_completed / elapsed) * 60 if elapsed > 0 else 0
            now = time.time()
            if (now - self._last_ui_update) >= 0.05 or chars_completed >= total_chars_overall:
                self.update_speed.emit(cpm / 5)
                self.update_progress.emit(chars_completed)
                if cpm > 0:
                    etr_seconds = ((total_chars_overall - chars_completed) / cpm) * 60
                    self.update_etr.emit(f"ETR: {time.strftime('%M:%S', time.gmtime(etr_seconds))}")
                self._last_ui_update = now
            
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
            
        return chars_completed, total_pause_duration, True

    @pyqtSlot()
    def run(self):
        try:
            pyautogui.PAUSE = 0
            if self.enable_mouse_jitter:
                threading.Thread(target=self._mouse_jitter_thread, daemon=True).start()

            text_content = self.text_to_type
            # Normalize some curly quotes/dashes to plain ASCII
            text_content = (text_content
                            .replace('“', '"').replace('”', '"')
                            .replace('‘', "'").replace('’', "'")
                            .replace('—', '--').replace('…', '...'))

            total_chars_overall = len(text_content) * self.laps
            if total_chars_overall == 0:
                self.finished.emit()
                return

            chars_completed, total_pause_duration = 0, 0
            for i in range(self.delay, 0, -1):
                if not self._running:
                    self.finished.emit()
                    return
                self.update_status.emit(f"Starting in {i}...")
                self._sleep_interruptible(1)

            self.initial_window = self.get_active_window_title()
            self.update_status.emit(f"Typing locked on: {self.initial_window}")
            if self.auto_detect:
                self._auto_optimize_for_window(self.initial_window)
            overall_start_time = time.time()

            for lap in range(1, self.laps + 1):
                if not self._running:
                    break
                self.lap_progress.emit(lap, self.laps)

                if self.newline_mode == 'Paste Mode':
                    lines = text_content.splitlines(keepends=True)
                    for line in lines:
                        if not self._running:
                            break
                        # Save/restore clipboard around paste
                        try:
                            original_clip = pyperclip.paste()
                        except Exception:
                            original_clip = None
                        pasted = False
                        try:
                            pyperclip.copy(line)
                            pyautogui.hotkey('command' if platform.system() == "Darwin" else 'ctrl', 'v')
                            pasted = True
                        except Exception as e:
                            # Fallback: type the line if paste/hotkey fails
                            try:
                                pyautogui.typewrite(line)
                                pasted = True
                                self.update_status.emit("Paste failed; fell back to typing.")
                            except Exception:
                                self.update_status.emit(f"Paste/Type failed: {e}")
                        chars_completed += len(line)
                        now = time.time()
                        if (now - self._last_ui_update) >= 0.05 or chars_completed >= total_chars_overall:
                            self.update_progress.emit(chars_completed)
                            self._last_ui_update = now
                        self._sleep_interruptible(random.uniform(0.05, 0.15))
                        if original_clip is not None:
                            try:
                                pyperclip.copy(original_clip)
                            except Exception:
                                pass
                    continue

                if self.newline_mode == 'List Mode':
                    lines = text_content.splitlines()
                    for line in lines:
                        if not self._running:
                            break
                        stripped = line.lstrip()
                        if self.ime_friendly:
                            self._paste_text(stripped)
                            chars_completed += len(stripped)
                            self.update_progress.emit(chars_completed)
                        else:
                            chars_completed, total_pause_duration, still_running = self._type_segment(
                                stripped, overall_start_time, chars_completed, total_pause_duration, total_chars_overall)
                            if not still_running:
                                break
                        if self._running:
                            if self.press_esc:
                                pyautogui.press('esc')
                                self._sleep_interruptible(0.05)
                            if self.use_shift_enter:
                                pyautogui.hotkey('shift', 'enter')
                            else:
                                pyautogui.press('enter')
                            self._sleep_interruptible(0.1)
                else:
                    processed_text = (re.sub(r'(?<!\n)\n(?!\n)', ' ', text_content)
                                      if self.newline_mode == 'Smart Newlines' else text_content)
                    segments = re.split(r'(\{\{(?:PAUSE|PRESS|CLICK|COMMENT):.*?\}\})', processed_text)
                    for segment in segments:
                        if not self._running:
                            break
                        match = re.match(r'\{\{([A-Z]+):(.*)\}\}', segment)
                        if match:
                            ok, msg, normalized = self.validate_macro(match.group(1), match.group(2))
                            if ok and normalized:
                                self.execute_macro(*normalized)
                            else:
                                self.update_status.emit(f"Macro ignored: {msg}")
                            continue
                        if self.ime_friendly and segment:
                            self._paste_text(segment)
                            chars_completed += len(segment)
                            self.update_progress.emit(chars_completed)
                            self._sleep_interruptible(random.uniform(0.02, 0.06))
                        else:
                            chars_completed, total_pause_duration, still_running = self._type_segment(
                                segment, overall_start_time, chars_completed, total_pause_duration, total_chars_overall)
                            if not still_running:
                                break

                if not self._running:
                    break
                self._sleep_interruptible(0.5)

            if self._running:
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
        browser_keywords = ["safari", "chrome", "firefox", "edge", "brave", "opera"]
        chosen = None
        if any(k in t for k in code_keywords):
            self.newline_mode = 'List Mode'
            self.press_esc = True
            self.use_shift_enter = False
            self.type_tabs = False
            self.add_mistakes = False
            self.pause_on_punct = True
            chosen = "Code editor"
        elif any(k in t for k in chat_keywords):
            self.newline_mode = 'Smart Newlines'
            self.use_shift_enter = True
            self.press_esc = False
            self.add_mistakes = True
            self.pause_on_punct = False
            chosen = "Chat app"
        elif any(k in t for k in text_keywords):
            self.newline_mode = 'Standard'
            self.press_esc = False
            self.use_shift_enter = False
            self.type_tabs = True
            self.add_mistakes = False
            self.pause_on_punct = True
            chosen = "Plain text editor"
        elif any(k in t for k in browser_keywords):
            if self.newline_mode == 'Standard':
                self.newline_mode = 'Smart Newlines'
            chosen = "Browser"
        if chosen:
            try:
                self.update_status.emit(f"Auto-optimized for {chosen}: mode={self.newline_mode}")
            except Exception:
                pass


class DryRunWorker(QObject):
    finished = pyqtSignal()
    update_preview = pyqtSignal(str)

    def __init__(self, text, laps, min_wpm, max_wpm, mode, use_shift_enter):
        super().__init__()
        self.text = text
        self.laps = laps
        self.min_wpm = min_wpm
        self.max_wpm = max_wpm
        self.mode = mode
        self.use_shift_enter = use_shift_enter
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
                    content_iter = re.sub(r'(?<!\n)\n(?!\n)', ' ', content)
                else:
                    content_iter = content
                if self.mode == 'List Mode':
                    lines = content_iter.splitlines()
                    for line in lines:
                        if not self._running: break
                        out = ''
                        prev = ''
                        for ch in line.lstrip():
                            if not self._running: break
                            out += ch
                            self.update_preview.emit(ch)
                            time.sleep(self._delay(prev, ch))
                            prev = ch
                        # simulate enter
                        self.update_preview.emit('\n')
                        time.sleep(0.06)
                else:
                    # Process macros by stripping them and just showing text portions
                    segments = re.split(r'(\{\{(?:PAUSE|PRESS|CLICK|COMMENT):.*?\}\})', content_iter)
                    prev = ''
                    for seg in segments:
                        if not self._running: break
                        if re.match(r'\{\{([A-Z]+):(.*)\}\}', seg):
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
        text = p.text_edit.toPlainText()
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
        self.worker = DryRunWorker(text, p.laps_spin.value(), p.min_wpm_slider.value(), p.max_wpm_slider.value(), mode, p.use_shift_enter_checkbox.isChecked())
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
    def __init__(self, parent=None):
        super().__init__(parent)
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
        """Translates a PyQt-style hotkey string to a pynput-compatible one."""
        # pynput expects format like <cmd>+<alt>+s, all lowercase
        hotkey = hotkey.lower()
        parts = hotkey.split('+')
        
        # Translate special key names
        pynput_parts = []
        for part in parts:
            if part == 'cmd':
                pynput_parts.append('<cmd>')
            elif part == 'ctrl':
                pynput_parts.append('<ctrl>')
            elif part == 'alt':
                pynput_parts.append('<alt>')
            elif part == 'shift':
                pynput_parts.append('<shift>')
            else:
                pynput_parts.append(part)
                
        return '+'.join(pynput_parts)

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
        if any(k in t for k in ["safari", "chrome", "firefox", "edge", "brave", "opera"]):
            return 'browser'
        return 'unknown'

    def showEvent(self, event):
        """Ensure window flags are applied on show."""
        super().showEvent(event)
        # Always rely on Qt flags for consistency and stability.
        if self.always_on_top_action.isChecked():
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()
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

        main_layout = QVBoxLayout(self)
        main_layout.setMenuBar(self.menu_bar)

        # --- Unified Settings Layout ---
        self.settings_group_box = QGroupBox("Typing Configuration")
        settings_layout = QVBoxLayout()

        core_controls_layout = QHBoxLayout()
        self.laps_spin = QSpinBox()
        self.laps_spin.setRange(1, 1000)
        self.laps_spin.setValue(DEFAULT_LAPS)
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 60)
        self.delay_spin.setValue(DEFAULT_DELAY)
        core_controls_layout.addWidget(QLabel("Laps:"))
        core_controls_layout.addWidget(self.laps_spin)
        core_controls_layout.addSpacing(20)
        core_controls_layout.addWidget(QLabel("Start Delay (sec):"))
        core_controls_layout.addWidget(self.delay_spin)
        core_controls_layout.addStretch()
        settings_layout.addLayout(core_controls_layout)
        settings_layout.addSpacing(10)

        self.persona_combo = QComboBox()
        self.persona_combo.addItems(["Custom (Manual Settings)", "Deliberate Writer", "Fast Messenger", "Careful Coder"])
        self.persona_combo.currentIndexChanged.connect(self.toggle_persona_controls)
        persona_layout = QHBoxLayout()
        persona_layout.addWidget(QLabel("Typing Persona:"))
        persona_layout.addWidget(self.persona_combo, 1)
        settings_layout.addLayout(persona_layout)

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
        self.add_mistakes_checkbox = QCheckBox("Add Mistakes")
        self.pause_on_punct_checkbox = QCheckBox("Pause on Punctuation")
        self.pause_on_punct_checkbox.setChecked(True)
        human_layout = QHBoxLayout()
        human_layout.addWidget(self.add_mistakes_checkbox)
        human_layout.addWidget(self.pause_on_punct_checkbox)
        human_layout.addStretch()
        manual_layout.addLayout(speed1)
        manual_layout.addLayout(speed2)
        manual_layout.addLayout(human_layout)
        self.manual_settings_group.setLayout(manual_layout)
        settings_layout.addWidget(self.manual_settings_group)
        
        self.newline_group_box = QGroupBox("Advanced Handling")
        newline_layout = QVBoxLayout()
        self.paste_mode_radio = QRadioButton("Line Paste (Fastest; for code)")
        self.standard_radio = QRadioButton("Standard Typing (Types text as-is)")
        self.smart_radio = QRadioButton("Smart Newlines (Best for prose)")
        self.list_mode_radio = QRadioButton("List Mode (Ideal for code editors)")
        self.list_mode_radio.setChecked(True)
        newline_layout.addWidget(self.paste_mode_radio)
        newline_layout.addWidget(self.standard_radio)
        newline_layout.addWidget(self.smart_radio)
        newline_layout.addWidget(self.list_mode_radio)
        newline_layout.addSpacing(5)
        self.use_shift_enter_checkbox = QCheckBox("Use Shift+Enter for Newlines (for chat apps)")
        newline_layout.addWidget(self.use_shift_enter_checkbox)
        self.type_tabs_checkbox = QCheckBox("Preserve Tab Characters")
        self.type_tabs_checkbox.setChecked(True)
        newline_layout.addWidget(self.type_tabs_checkbox)
        self.press_esc_checkbox = QCheckBox("Press 'Esc' to bypass autocomplete")
        self.press_esc_checkbox.setChecked(True) # Default to on
        newline_layout.addWidget(self.press_esc_checkbox)
        self.mouse_jitter_checkbox = QCheckBox("Enable Background Mouse Jitter")
        newline_layout.addWidget(self.mouse_jitter_checkbox)
        self.auto_detect_checkbox = QCheckBox("Auto Detect Target App (optimize settings)")
        self.auto_detect_checkbox.setChecked(True)
        newline_layout.addWidget(self.auto_detect_checkbox)
        # New: IME-friendly typing and compliance guardrails
        self.ime_friendly_checkbox = QCheckBox("IME-friendly (use paste instead of per-key typing)")
        newline_layout.addWidget(self.ime_friendly_checkbox)
        self.compliance_mode_checkbox = QCheckBox("Compliance Mode (block browsers)")
        newline_layout.addWidget(self.compliance_mode_checkbox)
        blocked_layout = QHBoxLayout()
        blocked_layout.addWidget(QLabel("Blocked apps (comma):"))
        self.blocked_apps_edit = QLineEdit("Chrome,Safari,Firefox,Edge,Brave,Opera")
        blocked_layout.addWidget(self.blocked_apps_edit, 1)
        newline_layout.addLayout(blocked_layout)
        self.newline_group_box.setLayout(newline_layout)
        settings_layout.addWidget(self.newline_group_box)
        
        self.settings_group_box.setLayout(settings_layout)
        main_layout.addWidget(self.settings_group_box)

        self.text_edit = PasteCleaningTextEdit()
        self.text_edit.setPlaceholderText("Paste any text (HTML supported) — it will be cleaned.\nMacros like {{PAUSE:1.5}} are supported.")
        self.text_edit.fileDropped.connect(self.load_text_from_path)
        self.text_edit.textChanged.connect(self.update_preview)
        main_layout.addWidget(self.text_edit, 1)

        h_controls = QHBoxLayout()
        self.start_button = QPushButton()
        self.stop_button = QPushButton()
        self.clean_button = QPushButton("Clean")
        self.clear_button = QPushButton("Clear")
        h_controls.addWidget(self.start_button, 2)
        h_controls.addWidget(self.stop_button, 2)
        h_controls.addWidget(self.clean_button, 1)
        h_controls.addWidget(self.clear_button, 1)
        main_layout.addLayout(h_controls)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        self.preview_label = QLabel("Estimated: -- s")
        main_layout.addWidget(self.preview_label)

        h_status = QHBoxLayout()
        self.wpm_display = QLabel("Current: --- WPM")
        self.status_label = QLabel("Status: Idle")
        self.lap_label = QLabel("Lap: 0 / 0")
        self.etr_label = QLabel("ETR: --:--")
        h_status.addWidget(self.wpm_display, 1)
        h_status.addWidget(self.status_label, 2)
        h_status.addWidget(self.lap_label)
        h_status.addStretch()
        h_status.addWidget(self.etr_label)
        main_layout.addLayout(h_status)

        self.start_button.clicked.connect(self.start_typing)
        self.stop_button.clicked.connect(self.stop_typing)
        self.clean_button.clicked.connect(self.clean_whitespace)
        self.clear_button.clicked.connect(self.text_edit.clear)
        self.min_wpm_slider.valueChanged.connect(self.update_speed_labels)
        self.max_wpm_slider.valueChanged.connect(self.update_speed_labels)
        self.min_wpm_slider.valueChanged.connect(self.update_preview)
        self.max_wpm_slider.valueChanged.connect(self.update_preview)
        self.standard_radio.toggled.connect(self.update_preview)
        self.smart_radio.toggled.connect(self.update_preview)
        self.list_mode_radio.toggled.connect(self.update_preview)
        self.paste_mode_radio.toggled.connect(self.update_preview)
        self.ime_friendly_checkbox.toggled.connect(self.update_preview)
        # Initialize preview once UI is wired
        self.update_preview()

    def set_ui_for_running(self, is_running):
        self.start_button.setEnabled(not is_running)
        self.stop_button.setEnabled(is_running)
        self.text_edit.setEnabled(not is_running)
        self.menu_bar.setEnabled(not is_running)
        self.clear_button.setEnabled(not is_running)
        self.settings_group_box.setEnabled(not is_running)
        if not is_running:
            self.toggle_persona_controls()

    def toggle_persona_controls(self):
        persona = self.persona_combo.currentText()
        self.manual_settings_group.setEnabled(True)

        if persona == 'Careful Coder':
            self.min_wpm_slider.setValue(90)
            self.max_wpm_slider.setValue(140)
            self.add_mistakes_checkbox.setChecked(False)
            self.pause_on_punct_checkbox.setChecked(True)
            self.list_mode_radio.setChecked(True)
            self.press_esc_checkbox.setChecked(True)
            self.use_shift_enter_checkbox.setChecked(False)
            self.type_tabs_checkbox.setChecked(False)
            self.ime_friendly_checkbox.setChecked(False)

        elif persona == 'Deliberate Writer':
            self.min_wpm_slider.setValue(70)
            self.max_wpm_slider.setValue(110)
            self.add_mistakes_checkbox.setChecked(True)
            self.pause_on_punct_checkbox.setChecked(True)
            self.smart_radio.setChecked(True)
            self.press_esc_checkbox.setChecked(True)
            self.use_shift_enter_checkbox.setChecked(False)
            self.type_tabs_checkbox.setChecked(True)
            self.ime_friendly_checkbox.setChecked(False)

        elif persona == 'Fast Messenger':
            self.min_wpm_slider.setValue(120)
            self.max_wpm_slider.setValue(180)
            self.add_mistakes_checkbox.setChecked(True)
            self.pause_on_punct_checkbox.setChecked(False)
            self.smart_radio.setChecked(True)
            self.press_esc_checkbox.setChecked(True)
            self.use_shift_enter_checkbox.setChecked(True)
            self.type_tabs_checkbox.setChecked(False)
            self.ime_friendly_checkbox.setChecked(False)
            
    def start_typing(self):
        if self.is_paused:
            self.resume_typing()
            return
        if self.worker:
            return

        text = self.text_edit.toPlainText()
        if not text.strip(): 
            self.status_label.setText("Status: Error - Input text cannot be empty.")
            return

        self.set_ui_for_running(True)
        # Include newlines to match per-character progress updates
        self.progress_bar.setMaximum(len(text) * self.laps_spin.value())
        
        newline_mode = 'Standard'
        if self.smart_radio.isChecked():
            newline_mode = 'Smart Newlines'
        elif self.list_mode_radio.isChecked():
            newline_mode = 'List Mode'
        elif self.paste_mode_radio.isChecked():
            newline_mode = 'Paste Mode'

        # Optional Auto Detect: adjust UI choices before starting
        if self.auto_detect_checkbox.isChecked():
            try:
                title = self._get_active_window_title_main()
                category = self._categorize_title(title)
                if category == 'code':
                    self.list_mode_radio.setChecked(True)
                    self.press_esc_checkbox.setChecked(True)
                    self.use_shift_enter_checkbox.setChecked(False)
                    self.type_tabs_checkbox.setChecked(False)
                    self.add_mistakes_checkbox.setChecked(False)
                    self.pause_on_punct_checkbox.setChecked(True)
                    self.status_label.setText(f"Status: Auto-optimized for code editor ({title})")
                    newline_mode = 'List Mode'
                elif category == 'chat':
                    self.smart_radio.setChecked(True)
                    self.use_shift_enter_checkbox.setChecked(True)
                    self.press_esc_checkbox.setChecked(False)
                    self.add_mistakes_checkbox.setChecked(True)
                    self.pause_on_punct_checkbox.setChecked(False)
                    self.status_label.setText(f"Status: Auto-optimized for chat app ({title})")
                    newline_mode = 'Smart Newlines'
                elif category == 'text':
                    self.standard_radio.setChecked(True)
                    self.press_esc_checkbox.setChecked(False)
                    self.use_shift_enter_checkbox.setChecked(False)
                    self.type_tabs_checkbox.setChecked(True)
                    self.add_mistakes_checkbox.setChecked(False)
                    self.pause_on_punct_checkbox.setChecked(True)
                    self.status_label.setText(f"Status: Auto-optimized for plain text ({title})")
                    newline_mode = 'Standard'
                elif category == 'browser':
                    if newline_mode == 'Standard':
                        self.smart_radio.setChecked(True)
                        newline_mode = 'Smart Newlines'
                    self.status_label.setText(f"Status: Auto-adjusted for browser ({title})")
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
            'compliance_mode': self.compliance_mode_checkbox.isChecked(),
            'blocked_apps': self.blocked_apps_edit.text(),
            'auto_detect': self.auto_detect_checkbox.isChecked()
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
        self.worker.update_status.connect(self.status_label.setText)
        self.worker.update_speed.connect(lambda w: self.wpm_display.setText(f"Current: {w:.0f} WPM"))
        self.worker.update_progress.connect(self.progress_bar.setValue)
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
        # Keep preview in sync with labels
        self.update_preview()

    def estimate_duration_seconds(self):
        text = self.text_edit.toPlainText()
        if not text:
            return 0.0, 0.0
        min_wpm = max(1, self.min_wpm_slider.value())
        max_wpm = max(min_wpm, self.max_wpm_slider.value())
        laps = max(1, self.laps_spin.value())
        delay = max(0, self.delay_spin.value())
        ime = self.ime_friendly_checkbox.isChecked()
        paste = self.paste_mode_radio.isChecked()
        list_mode = self.list_mode_radio.isChecked()
        smart = self.smart_radio.isChecked()
        chars = len(text)
        lines = max(1, len(text.splitlines()))
        # Base estimates
        if paste or (ime and list_mode):
            # Per line paste cost ~0.08-0.15s
            lo_per_line, hi_per_line = 0.08, 0.15
            lo = lines * lo_per_line
            hi = lines * hi_per_line
        elif ime:
            # Bulk paste segments: approximate as fast paste with small overhead
            lo = chars / 2000.0 + 0.2
            hi = chars / 1200.0 + 0.5
        else:
            # Per-key typing
            cps_lo = (max_wpm * 5) / 60.0
            cps_hi = (min_wpm * 5) / 60.0
            lo = chars / cps_lo if cps_lo else 0
            hi = chars / cps_hi if cps_hi else 0
            # Add punctuation pauses approx 5% overhead for prose
            if smart or list_mode:
                lo *= 1.03
                hi *= 1.08
        # Multiply by laps and add start delay
        return (lo * laps + delay, hi * laps + delay)

    def update_preview(self):
        lo, hi = self.estimate_duration_seconds()
        if lo == 0 and hi == 0:
            self.preview_label.setText("Estimated: -- s")
            return
        self.preview_label.setText(f"Estimated: {int(lo)}–{int(hi)} s")

    def stop_typing(self):
        if self.worker:
            self.worker.stop()
        self.is_paused = False
        try:
            logger.info("Typing stop requested")
        except Exception:
            pass

    def resume_typing(self):
        if self.worker and self.is_paused:
            self.worker.resume()
            self.status_label.setText("Status: Resumed typing...")
            self.is_paused = False

    def on_typing_paused(self):
        self.is_paused = True
        self.start_button.setEnabled(True)
        resume_hotkey = self.settings.value("resumeHotkey", DEFAULT_RESUME_HOTKEY)
        self.start_button.setText(f"RESUME ({resume_hotkey})")
        self.status_label.setText("Status: Paused. Refocus target window or press Resume.")

    def on_typing_resumed(self):
        self.is_paused = False
        self.start_button.setEnabled(False)
        self.update_button_hotkey_text()
        self.status_label.setText("Status: Resumed typing...")

    def on_typing_finished(self):
        self.is_paused = False
        self.set_ui_for_running(False)
        self.update_button_hotkey_text()
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
        start = self.settings.value("startHotkey", DEFAULT_START_HOTKEY)
        stop = self.settings.value("stopHotkey", DEFAULT_STOP_HOTKEY)
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
        if hasattr(self, 'hotkey_listener_thread') and self.hotkey_listener_thread and self.hotkey_listener_thread.is_alive():
            return
        self.hotkey_listener_thread = threading.Thread(target=self._run_listener, daemon=True)
        self.hotkey_listener_thread.start()
        # Add a small delay to ensure the listener initializes
        time.sleep(0.1)

    def stop_listener(self):
        if hasattr(self, 'hotkey_listener') and self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
        # no join here to avoid blocking UI
        
    def _run_listener(self):
        """The target function for the listener thread."""
        try:
            # Translate hotkeys before passing them to the listener
            start_key = self._translate_hotkey_for_pynput(self.settings.value("startHotkey", DEFAULT_START_HOTKEY))
            stop_key = self._translate_hotkey_for_pynput(self.settings.value("stopHotkey", DEFAULT_STOP_HOTKEY))
            resume_key = self._translate_hotkey_for_pynput(self.settings.value("resumeHotkey", DEFAULT_RESUME_HOTKEY))

            hotkeys = {
                start_key: self.start_typing_signal.emit,
                stop_key: self.stop_typing_signal.emit,
                resume_key: self.resume_typing_signal.emit
            }
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkeys)
            self.hotkey_listener.run()
        except Exception as e:
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
            "text": self.text_edit, "laps": self.laps_spin, "delay": self.delay_spin,
            "persona": self.persona_combo, "min_wpm": self.min_wpm_slider,
            "max_wpm": self.max_wpm_slider, "add_mistakes": self.add_mistakes_checkbox,
            "pause_on_punct": self.pause_on_punct_checkbox,
            "newline_standard": self.standard_radio, "newline_smart": self.smart_radio,
            "newline_list": self.list_mode_radio, "newline_paste": self.paste_mode_radio,
            "use_shift_enter": self.use_shift_enter_checkbox,
            "type_tabs": self.type_tabs_checkbox,
            "mouse_jitter": self.mouse_jitter_checkbox,
            "auto_detect": self.auto_detect_checkbox,
            "ime_friendly": self.ime_friendly_checkbox,
            "compliance_mode": self.compliance_mode_checkbox,
            "blocked_apps": self.blocked_apps_edit
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
                elif isinstance(widget, QTextEdit):
                    widget.setPlainText(self.settings.value(key))
        self.settings.endGroup()

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
                elif isinstance(widget, QTextEdit):
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
        text = self.text_edit.toPlainText()
        lines = [line.rstrip() for line in text.splitlines()]
        text = '\n'.join(lines)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        self.text_edit.setText(text)

    def to_uppercase(self):
        self.text_edit.setText(self.text_edit.toPlainText().upper())

    def to_lowercase(self):
        self.text_edit.setText(self.text_edit.toPlainText().lower())

    def to_sentence_case(self):
        text = self.text_edit.toPlainText().lower()
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
        self.text_edit.setText(result)

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
            self.text_edit.setPlainText(text)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open file: {e}")

    def open_file(self):
        filters = "Text/Markdown/HTML/RTF (*.txt *.md *.markdown *.html *.htm *.rtf);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Open Text File", "", filters)
        if not path:
            return
        self.load_text_from_path(path)

    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Text File As...", "", "*.txt")
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.text_edit.toPlainText())
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

    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())

    def closeEvent(self, event):
        self.save_settings()
        self.stop_typing()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Rely on Qt window management for stability across platforms

    window = AutoTyperApp()
    window.show()
    sys.exit(app.exec_())
