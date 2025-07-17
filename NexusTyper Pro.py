import faulthandler; faulthandler.enable()
import sys
import time
import re
import random
import numpy as np
import platform
import threading
import os

from PyQt5.QtWidgets import (
    QApplication, QWidget, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QCheckBox, QSlider, QMessageBox, QProgressBar,
    QFileDialog, QAction, QMenuBar, QDialog, QLineEdit,
    QDialogButtonBox, QComboBox, QInputDialog, QTabWidget, QKeySequenceEdit,
    QFormLayout, QGroupBox, QRadioButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QSettings, QEvent
from PyQt5.QtGui import QKeySequence, QPixmap, QIcon

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
APP_VERSION = "3.2"
APP_AUTHOR = "TramsNF"
APP_COPYRIGHT_YEAR = "2025"
APP_SIGNATURE = "Automate. Create. Elevate."
CONTACT_EMAIL = "smartabayomi@gmail.com"
CONTACT_WEBSITE = "https://tramsnf.com"
DEFAULT_MIN_WPM, DEFAULT_MAX_WPM = 180, 220
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

# About dialog with app info and contact
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(480, 250)
        main_layout = QHBoxLayout(self)
        self.image_label = QLabel()
        # Load icon or placeholder
        if os.path.exists("ico2.png"):
            pixmap = QPixmap("ico2.png")
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
            <p>Personas are quick presets that configure settings for a specific task. You can always adjust the settings manually after selecting a persona.</p>
            <ul>
                <li><b>Careful Coder:</b> Optimized for writing code into an IDE. It enables <b>List Mode</b>, disables mistakes, and uses other smart features to ensure code is typed accurately.</li>
                <li><b>Deliberate Writer:</b> Simulates a person writing prose thoughtfully. It uses a slower speed and enables <b>Smart Newlines</b> to correctly format paragraphs.</li>
                <li><b>Fast Messenger:</b> Simulates rapid, chat-style typing with a high WPM and fewer pauses.</li>
                <li><b>Custom (Manual Settings):</b> Does not change any settings, giving you full manual control.</li>
            </ul>
            
            <h2>Humanization</h2>
            <ul>
                <li><b>WPM Sliders:</b> Control the minimum and maximum words per minute.</li>
                <li><b>Add Mistakes:</b> Simulates human-like typing errors and corrects them.</li>
                <li><b>Pause on Punctuation:</b> Adds a slight, natural delay after typing punctuation like commas and periods.</li>
            </ul>

            <h2>Advanced Handling</h2>
            <h4>Newline Modes (How 'Enter' is handled)</h4>
            <ul>
                <li><b>Line Paste:</b> The fastest mode. Copies and pastes each line. May be blocked by some applications.</li>
                <li><b>Standard Typing:</b> Types every character exactly as-is, including all spaces and tabs. <b>Use this for simple text editors that do not auto-indent</b> (like Notepad).</li>
                <li><b>Smart Newlines:</b> Best for prose. Joins single line breaks into a space to form paragraphs but preserves double line breaks.</li>
                <li><b>List Mode:</b> The best mode for modern code editors (IDEs). It types the code on each line but lets the editor handle indentation, preventing formatting conflicts.</li>
            </ul>
            <h4>Other Options</h4>
            <ul>
                <li><b>Use Shift+Enter:</b> Check this if you need to create a newline without "sending" a message, common in chat apps like Slack or Teams. The default is a normal 'Enter' press.</li>
                <li><b>Preserve Tab Characters:</b> If checked, it will type any tabs from your source text. If unchecked, it will ignore them, which can help with indentation in some editors.</li>
                <li><b>Press 'Esc' to bypass autocomplete:</b> A smart feature that presses the 'Esc' key before typing a line to close any annoying autocomplete pop-ups in code editors.</li>
                <li><b>Enable Background Mouse Jitter:</b> Gently moves the mouse cursor by a tiny amount to simulate user activity and prevent systems from going idle.</li>
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

    def save_settings(self):
        self.settings.setValue("startHotkey", self.start_hotkey_edit.keySequence().toString())
        self.settings.setValue("stopHotkey", self.stop_hotkey_edit.keySequence().toString())
        self.settings.setValue("resumeHotkey", self.resume_hotkey_edit.keySequence().toString())
        self.accept()

# TextEdit subclass to clean pasted text automatically
class PasteCleaningTextEdit(QTextEdit):
    def insertFromMimeData(self, source):
        if source.hasText():
            text = source.text()
            # Make cleaning less aggressive to preserve code/math formatting.
            # Only normalize line endings and excessive newlines.
            text = text.replace('\r\n', '\n')
            text = re.sub(r'\n{3,}', '\n\n', text)
            self.insertPlainText(text)
        else:
            super().insertFromMimeData(source)

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
                time.sleep(float(params))
            elif command == 'PRESS':
                pyautogui.press(params.lower().strip())
            elif command == 'CLICK':
                x, y = params.split(',')
                pyautogui.click(int(x), int(y))
        except:
            pass

    def _mouse_jitter_thread(self):
        # Moves mouse slightly at random intervals to simulate activity
        while self._running:
            pyautogui.move(random.randint(-1, 1), random.randint(-1, 1), duration=0.1)
            time.sleep(random.uniform(0.5, 3))

    def _type_segment(self, segment, overall_start_time, chars_completed, total_pause_duration, total_chars_overall):
        # Types a segment of text with human-like behavior, preserving code formatting
        for char in segment:
            if char == '\t' and not self.type_tabs:
                continue # Skip this character and go to the next one
            
            if not self._running: 
                return chars_completed, total_pause_duration, False
            self.pause_event.wait()
            if not self._running:
                return chars_completed, total_pause_duration, False
            
            if self.get_active_window_title() != self.initial_window and not self._paused:
                self.pause(auto_resume_check=True)
            
            if self.add_mistakes and random.random() < self.mistake_chance:
                if char.lower() in KEY_ADJACENCY:
                    pyautogui.typewrite(random.choice(KEY_ADJACENCY[char.lower()]))
                    time.sleep(random.uniform(0.1, 0.25))
                    pyautogui.press('backspace')
                    time.sleep(random.uniform(0.05, 0.15))
            
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
            self.update_speed.emit(cpm / 5)
            self.update_progress.emit(chars_completed)
            
            if cpm > 0:
                etr_seconds = ((total_chars_overall - chars_completed) / cpm) * 60
                self.update_etr.emit(f"ETR: {time.strftime('%M:%S', time.gmtime(etr_seconds))}")
            
            delay = random.uniform(60 / (self.max_wpm * 5), 60 / (self.min_wpm * 5))
            if self.pause_on_punct:
                if char in '.,?!':
                    delay += random.uniform(0.08, 0.15)
                elif char in '()[]{}':
                    delay += random.uniform(0.1, 0.3)
            time.sleep(max(0.01, delay))
            
        return chars_completed, total_pause_duration, True

    def run(self):
        try:
            pyautogui.PAUSE = 0
            if self.enable_mouse_jitter:
                threading.Thread(target=self._mouse_jitter_thread, daemon=True).start()
            
            text_content = self.text_to_type

            # Normalize special characters to basic ASCII before typing
            text_content = text_content.replace('“', '"').replace('”', '"')
            text_content = text_content.replace('‘', "'").replace('’', "'")
            text_content = text_content.replace('—', '--').replace('…', '...')

            total_chars_overall = len(text_content.replace('\n', '')) * self.laps
            if total_chars_overall == 0:
                self.finished.emit()
                return

            chars_completed, total_pause_duration = 0, 0
            for i in range(self.delay, 0, -1):
                if not self._running:
                    self.finished.emit()
                    return
                self.update_status.emit(f"Starting in {i}...")
                time.sleep(1)
            
            self.initial_window = self.get_active_window_title()
            self.update_status.emit(f"Typing locked on: {self.initial_window}")
            overall_start_time = time.time()
            
            for lap in range(1, self.laps + 1):
                if not self._running: break
                self.lap_progress.emit(lap, self.laps)

                if self.newline_mode == 'Paste Mode':
                    lines = text_content.splitlines(keepends=True)
                    for line in lines:
                        if not self._running: break
                        pyperclip.copy(line)
                        pyautogui.hotkey('command' if platform.system() == "Darwin" else 'ctrl', 'v')
                        chars_completed += len(line)
                        self.update_progress.emit(chars_completed)
                        time.sleep(random.uniform(0.05, 0.15))
                    continue

                if self.newline_mode == 'List Mode':
                    lines = text_content.splitlines()
                    for line in lines:
                        if not self._running: break
                        
                        # Type the line first
                        chars_completed, total_pause_duration, still_running = self._type_segment(line.lstrip(), overall_start_time, chars_completed, total_pause_duration, total_chars_overall)
                        if not still_running: break

                        if self._running:
                            # NOW, press 'Esc' right before 'Enter'
                            if self.press_esc:
                                pyautogui.press('esc')
                                time.sleep(0.05)
                            
                            if self.use_shift_enter:
                                pyautogui.hotkey('shift', 'enter')
                            else:
                                pyautogui.press('enter')
                            time.sleep(0.1) # Restored a small delay for stability
                else:
                    processed_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text_content) if self.newline_mode == 'Smart Newlines' else text_content
                    segments = re.split(r'(\{\{(?:PAUSE|PRESS|CLICK|COMMENT):.*?\}\})', processed_text)
                    for segment in segments:
                        if not self._running: break
                        match = re.match(r'\{\{([A-Z]+):(.*)\}\}', segment)
                        if match:
                            self.execute_macro(*match.groups())
                            continue
                        chars_completed, total_pause_duration, still_running = self._type_segment(segment, overall_start_time, chars_completed, total_pause_duration, total_chars_overall)
                        if not still_running: break
                
                if not self._running: break
                time.sleep(0.5)
            
            if self._running:
                self.update_status.emit("Typing completed successfully!")
            else:
                self.update_status.emit("Typing stopped by user.")
        except Exception as e:
            self.update_status.emit(f"Error: {e}")
        finally:
            self.finished.emit()


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

    def showEvent(self, event):
        """Apply macOS specific window flags when the window is shown."""
        super().showEvent(event)
        if platform.system() == "Darwin":
            self.apply_macos_float_behavior(self.always_on_top_action.isChecked())

    def apply_macos_float_behavior(self, checked):
        """Helper to set native window behavior on macOS for floating over all apps and spaces."""
        try:
            ns_app = AppKit.NSApplication.sharedApplication()
            for win in ns_app.windows():
                if win.title() == self.windowTitle():
                    if checked:
                        behavior = (AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
                                    AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)
                        win.setCollectionBehavior_(behavior)
                        win.setLevel_(AppKit.NSStatusWindowLevel)
                    else:
                        win.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorDefault)
                        win.setLevel_(AppKit.NSNormalWindowLevel)
                    break
        except Exception as e:
            print(f"Could not set macOS float behavior: {e}")

    def init_ui(self):
        self.setWindowTitle(f"{APP_NAME} - v{APP_VERSION}")
        if os.path.exists("icon.icns"):
            self.setWindowIcon(QIcon("icon.icns"))

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
        self.load_profile_menu = profiles_menu.addMenu('Load Profile')
        self.populate_profiles_menu()

        self.dark_mode_action = QAction('Dark Mode', self, checkable=True)
        self.dark_mode_action.triggered.connect(self.toggle_dark_mode)
        view_menu.addAction(self.dark_mode_action)
        view_menu.addSeparator()
        self.always_on_top_action = QAction('Always on Top', self, checkable=True)
        self.always_on_top_action.triggered.connect(self.toggle_always_on_top)
        view_menu.addAction(self.always_on_top_action)

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
        self.newline_group_box.setLayout(newline_layout)
        settings_layout.addWidget(self.newline_group_box)
        
        self.settings_group_box.setLayout(settings_layout)
        main_layout.addWidget(self.settings_group_box)

        self.text_edit = PasteCleaningTextEdit()
        self.text_edit.setPlaceholderText("Paste text here - it will be automatically cleaned.\nMacros like {{PAUSE:1.5}} are supported.")
        self.text_edit.installEventFilter(self)
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

        elif persona == 'Deliberate Writer':
            self.min_wpm_slider.setValue(70)
            self.max_wpm_slider.setValue(110)
            self.add_mistakes_checkbox.setChecked(True)
            self.pause_on_punct_checkbox.setChecked(True)
            self.smart_radio.setChecked(True)
            self.press_esc_checkbox.setChecked(True)

        elif persona == 'Fast Messenger':
            self.min_wpm_slider.setValue(150)
            self.max_wpm_slider.setValue(250)
            self.add_mistakes_checkbox.setChecked(True)
            self.pause_on_punct_checkbox.setChecked(False)
            self.smart_radio.setChecked(True)
            self.press_esc_checkbox.setChecked(True)
            
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
        self.progress_bar.setMaximum(len(text.replace('\n', '')) * self.laps_spin.value())
        
        newline_mode = 'Standard'
        if self.smart_radio.isChecked():
            newline_mode = 'Smart Newlines'
        elif self.list_mode_radio.isChecked():
            newline_mode = 'List Mode'
        elif self.paste_mode_radio.isChecked():
            newline_mode = 'Paste Mode'

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
            'press_esc': self.press_esc_checkbox.isChecked()
        }

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
        # For macOS, we handle flags natively. For others, use the Qt hint.
        if platform.system() == "Darwin":
            self.apply_macos_float_behavior(checked)
        else:
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

    def stop_typing(self):
        if self.worker:
            self.worker.stop()
        self.is_paused = False

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

    def show_about_dialog(self):
        self.stop_listener()
        is_on_top = self.always_on_top_action.isChecked()
        if platform.system() == "Darwin" and is_on_top:
            self.apply_macos_float_behavior(False)
        
        dialog = AboutDialog(self)
        dialog.exec_()
        
        if platform.system() == "Darwin" and is_on_top:
            self.apply_macos_float_behavior(True)
        self.start_listener()

    def show_settings_dialog(self):
        self.stop_listener()
        is_on_top = self.always_on_top_action.isChecked()
        if platform.system() == "Darwin" and is_on_top:
            self.apply_macos_float_behavior(False)
            
        dialog = SettingsDialog(self)
        result = dialog.exec_()

        # We must restore the window and listener BEFORE showing the next message box
        if platform.system() == "Darwin" and is_on_top:
            self.apply_macos_float_behavior(True)
        self.start_listener()

        if result == QDialog.Accepted:
            self.update_button_hotkey_text()
            # NOW we can safely show the confirmation message
            self.stop_listener()
            QMessageBox.information(self, "Settings Saved", "Hotkey settings have been updated. Please restart the application for them to take effect.")
            self.start_listener()
            
    def show_help_dialog(self):
        self.stop_listener()
        is_on_top = self.always_on_top_action.isChecked()
        if platform.system() == "Darwin" and is_on_top:
            self.apply_macos_float_behavior(False)
            
        dialog = HelpDialog(self)
        dialog.exec_()
        
        if platform.system() == "Darwin" and is_on_top:
            self.apply_macos_float_behavior(True)
        self.start_listener()

    def update_button_hotkey_text(self):
        start = self.settings.value("startHotkey", DEFAULT_START_HOTKEY)
        stop = self.settings.value("stopHotkey", DEFAULT_STOP_HOTKEY)
        self.start_button.setText(f"START ({start})")
        self.stop_button.setText(f"STOP ({stop})")

    def start_listener(self):
        """Starts the global hotkey listener in a separate thread."""
        if hasattr(self, 'hotkey_listener_thread') and self.hotkey_listener_thread and self.hotkey_listener_thread.is_alive():
            return # Listener is already running

        self.hotkey_listener_thread = threading.Thread(target=self._run_listener, daemon=True)
        self.hotkey_listener_thread.start()

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
            "mouse_jitter": self.mouse_jitter_checkbox
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

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Text File", "", "*.txt")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.text_edit.setPlainText(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open file: {e}")

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
        
        if always_on_top and platform.system() != "Darwin":
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
    window = AutoTyperApp()
    window.show()
    sys.exit(app.exec_())