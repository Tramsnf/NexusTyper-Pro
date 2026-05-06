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
    QSplitter, QSplitterHandle, QScrollArea, QToolButton, QStyle, QGridLayout,
    QFrame, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QObject, QThread, QSettings, QEvent, QUrl, QStringListModel,
    pyqtSlot, QTimer, QSize, QPoint, QRect, QPropertyAnimation, QEasingCurve,
    pyqtProperty, QVariantAnimation
)
from PyQt5.QtGui import (
    QKeySequence, QPixmap, QIcon, QTextDocument, QDesktopServices,
    QFontDatabase, QFontMetrics, QPainter, QColor, QPen, QPainterPath
)
import json
import html
import logging
from logging.handlers import RotatingFileHandler

# --- Text Processing Helpers ---
_SMART_BULLET_RE = re.compile(r"^\s*(?:[-*+]|•)\s+")
_SMART_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+")
_SMART_BLOCKQUOTE_RE = re.compile(r"^\s*>+\s+")
_SMART_HEADING_RE = re.compile(r"^\s*#{1,6}\s+")

# Characters that commonly leak in when pasting from AI chat UIs, rich editors,
# PDFs, Google Docs, Word, etc., and either render invisibly or confuse target
# apps. Stripped/replaced by sanitize_ai_text.
_AI_INVISIBLE_CHARS = (
    '​‌‍⁠﻿'    # ZWSP, ZWNJ, ZWJ, WORD JOINER, BOM
    '‎‏'                       # LRM, RLM (bidi marks)
    '‪‫‬‭‮'     # LRE, RLE, PDF, LRO, RLO (bidi embedding)
    '⁦⁧⁨⁩'           # LRI, RLI, FSI, PDI (bidi isolates)
    '­'                             # SOFT HYPHEN
)
_AI_INVISIBLE_TABLE = str.maketrans('', '', _AI_INVISIBLE_CHARS)

_AI_PUNCT_TABLE = str.maketrans({
    ' ': ' ',   # NO-BREAK SPACE
    ' ': ' ',   # NARROW NO-BREAK SPACE
    ' ': ' ',   # FIGURE SPACE
    ' ': ' ',   # PUNCTUATION SPACE
    ' ': ' ',   # THIN SPACE
    ' ': ' ',   # HAIR SPACE
    ' ': ' ',   # MEDIUM MATHEMATICAL SPACE
    '　': ' ',   # IDEOGRAPHIC SPACE
    ' ': '\n',  # LINE SEPARATOR
    ' ': '\n',  # PARAGRAPH SEPARATOR
    '“': '"', '”': '"',    # “ ”
    '‘': "'", '’': "'",    # ‘ ’
    '‚': ',', '„': ',,',   # ‚ „
    '′': "'", '″': '"',    # ′ ″ (prime, double prime)
    '–': '-',                    # – en dash
    '—': '--',                   # — em dash
    '…': '...',                  # … ellipsis
    '−': '-',                    # − minus sign
    '×': 'x',                    # × multiplication sign (AI/math leakage;
                                 #   pyautogui can't type U+00D7 and it
                                 #   corrupts to "." — "x" is what a human
                                 #   would type for "times")
    '÷': '/',                    # ÷ division sign (same story)
})


def sanitize_ai_text(text: str) -> str:
    """Normalize text pasted/typed from AI chats, web pages, PDFs, docs.

    Handles: HTML entities (&amp; → &), zero-width chars, bidi marks, soft
    hyphens, exotic spaces (NBSP/thin/etc.), smart quotes/dashes/ellipsis,
    and line-separator chars. Safe to run repeatedly.
    """
    if not text:
        return text
    # 1. Decode any stray HTML entities ("&amp;" that came across as literal 5 chars)
    text = html.unescape(text)
    # 2. Strip invisible / bidi / soft-hyphen chars that confuse target apps
    text = text.translate(_AI_INVISIBLE_TABLE)
    # 3. Replace exotic spaces, line separators, and smart punctuation
    text = text.translate(_AI_PUNCT_TABLE)
    # 4. Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return text


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
CONTACT_EMAIL = "xx"
CONTACT_WEBSITE = "https://tramsnf.com"
# GitHub release feed for the in-app update checker. Forks should change
# this to point at their own repo or set it to "" to disable the checker.
UPDATE_FEED_URL = "https://api.github.com/repos/Tramsnf/NexusTyper-Pro/releases/latest"
UPDATE_DOWNLOAD_PAGE = "https://github.com/Tramsnf/NexusTyper-Pro/releases/latest"
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
# Polished theme stylesheets. Both themes share the same structure; only colors differ.
# Accent: cyan (primary), green (start), red (stop), amber (pause/warning).

DARK_STYLESHEET = """
QWidget {
    background-color: #0F172A;
    color: #E2E8F0;
    selection-background-color: #06B6D4;
    selection-color: #0F172A;
}
QMainWindow, QDialog, QScrollArea { background-color: #0F172A; }

QMenuBar {
    background-color: #0F172A;
    color: #CBD5E1;
    border-bottom: 1px solid #1E293B;
    padding: 2px 4px;
}
QMenuBar::item { padding: 6px 10px; background: transparent; border-radius: 4px; }
QMenuBar::item:selected { background: #1E293B; color: #F1F5F9; }
QMenu {
    background-color: #1E293B;
    color: #E2E8F0;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item { padding: 6px 22px 6px 14px; border-radius: 4px; }
QMenu::item:selected { background-color: #334155; color: #F8FAFC; }
QMenu::separator { height: 1px; background: #334155; margin: 4px 8px; }

QGroupBox {
    background-color: transparent;
    border: 1px solid #1E293B;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 12px 10px 12px;
    font-weight: 600;
    color: #CBD5E1;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #94A3B8;
    background-color: #0F172A;
}

QTabWidget::pane {
    background: #0F172A;
    border: 1px solid #1E293B;
    border-radius: 8px;
    top: -1px;
}
QTabBar { qproperty-drawBase: 0; background: transparent; }
QTabBar::tab {
    background: transparent;
    color: #94A3B8;
    padding: 8px 16px;
    margin-right: 4px;
    border: none;
    border-bottom: 2px solid transparent;
    min-width: 80px;
}
QTabBar::tab:hover { color: #CBD5E1; }
QTabBar::tab:selected {
    color: #F8FAFC;
    border-bottom: 2px solid #06B6D4;
}

QPushButton {
    background-color: #1E293B;
    color: #E2E8F0;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 7px 14px;
    min-height: 22px;
}
QPushButton:hover { background-color: #334155; border-color: #475569; }
QPushButton:pressed { background-color: #0B1220; }
QPushButton:focus { border-color: #06B6D4; outline: none; }
QPushButton:disabled { background-color: #1E293B; color: #475569; border-color: #1E293B; }

QPushButton#startButton {
    background-color: #16A34A;
    color: #F0FDF4;
    border: 1px solid #15803D;
    font-weight: 600;
}
QPushButton#startButton:hover { background-color: #15803D; border-color: #166534; }
QPushButton#startButton:pressed { background-color: #166534; }
QPushButton#startButton:disabled { background-color: #1E293B; color: #475569; border-color: #1E293B; }

QPushButton#pauseButton {
    background-color: #1E293B;
    color: #CBD5E1;
    border: 1px solid #334155;
    font-weight: 600;
}
QPushButton#pauseButton:hover {
    background-color: #2A3445;
    color: #FDE68A;
    border-color: #D97706;
}
QPushButton#pauseButton:disabled { background-color: #1E293B; color: #475569; border-color: #1E293B; }

QPushButton#stopButton {
    background-color: #1E293B;
    color: #CBD5E1;
    border: 1px solid #334155;
    font-weight: 600;
}
QPushButton#stopButton:hover {
    background-color: #DC2626;
    color: #FEF2F2;
    border-color: #B91C1C;
}
QPushButton#stopButton:pressed { background-color: #991B1B; color: #FFFFFF; }
QPushButton#stopButton:disabled { background-color: #1E293B; color: #475569; border-color: #1E293B; }

QToolButton {
    background-color: transparent;
    color: #CBD5E1;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 8px;
}
QToolButton:hover { background-color: #1E293B; border-color: #334155; }
QToolButton:pressed { background-color: #0B1220; }
QToolButton::menu-indicator { image: none; width: 0; }

QLineEdit, QSpinBox, QComboBox, QKeySequenceEdit, QTextEdit, QPlainTextEdit {
    background-color: #0B1220;
    color: #E2E8F0;
    border: 1px solid #1E293B;
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: #06B6D4;
    selection-color: #0F172A;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QKeySequenceEdit:focus,
QTextEdit:focus, QPlainTextEdit:focus { border-color: #06B6D4; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
    color: #475569; background-color: #0B1220;
}

QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    background: transparent;
    border: none;
    width: 16px;
    margin-right: 2px;
}
QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    background: transparent;
    border: none;
    width: 16px;
    margin-right: 2px;
}
QSpinBox::up-arrow { image: url({chev_up_dark}); width: 10px; height: 9px; }
QSpinBox::down-arrow { image: url({chev_down_dark}); width: 10px; height: 9px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: rgba(51, 65, 85, 0.5); border-radius: 3px; }

QComboBox::drop-down { width: 22px; border: none; background: transparent; }
QComboBox QAbstractItemView {
    background-color: #1E293B;
    color: #E2E8F0;
    border: 1px solid #334155;
    border-radius: 6px;
    selection-background-color: #334155;
    padding: 4px;
    outline: 0;
}

QCheckBox, QRadioButton { spacing: 8px; color: #CBD5E1; padding: 2px; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; }
QCheckBox::indicator {
    border: 1px solid #334155;
    border-radius: 4px;
    background: #0B1220;
}
QCheckBox::indicator:hover { border-color: #06B6D4; }
QCheckBox::indicator:checked {
    background-color: #06B6D4;
    border: 1px solid #06B6D4;
    image: url({check_white});
}
QRadioButton::indicator {
    border: 1px solid #334155;
    border-radius: 8px;
    background: #0B1220;
}
QRadioButton::indicator:hover { border-color: #06B6D4; }
QRadioButton::indicator:checked {
    border: 1.5px solid #06B6D4;
    background: #0B1220;
    image: url({dot_dark});
}

QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #1E293B;
    border-radius: 2px;
}
QSlider::sub-page:horizontal { background: #06B6D4; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #F8FAFC;
    border: 1px solid #94A3B8;
    width: 16px;
    height: 16px;
    margin: -7px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover { border-color: #06B6D4; }

QProgressBar {
    background-color: #1E293B;
    border: 1px solid #1E293B;
    border-radius: 6px;
    text-align: center;
    color: #E2E8F0;
    min-height: 18px;
}
QProgressBar::chunk { background-color: #06B6D4; border-radius: 5px; }

QSplitter { background: #0F172A; }
QSplitter::handle:horizontal { background: transparent; border: none; }
QSplitter::handle:horizontal:hover { background: transparent; }
QSplitter::handle:horizontal:pressed { background: transparent; }

QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 2px 4px 2px; }
QScrollBar::handle:vertical { background: rgba(71, 85, 105, 0.55); border-radius: 2px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: rgba(148, 163, 184, 0.85); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 2px 4px 2px 4px; }
QScrollBar::handle:horizontal { background: rgba(71, 85, 105, 0.55); border-radius: 2px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: rgba(148, 163, 184, 0.85); }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; background: none; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

QToolTip {
    background-color: #1E293B;
    color: #E2E8F0;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 4px 6px;
}

QLabel#statusBadge { border-radius: 6px; }
QFrame#masthead { background-color: #0B1220; border: none; }
QFrame#mastheadDivider { background: #1E293B; border: none; }
QLabel#wordmark {
    color: #F1F5F9;
    font-size: 13pt;
    font-weight: 700;
    letter-spacing: 0.6px;
}
QLabel#wordmarkVersion { color: #64748B; font-size: 9pt; padding-left: 4px; }
QLabel#personaLabel {
    color: #64748B;
    font-size: 9pt;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}
QComboBox#personaPill {
    background-color: #1E293B;
    color: #E2E8F0;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 4px 12px;
    font-weight: 500;
}
QComboBox#personaPill:hover { border-color: #06B6D4; }
QLabel#hotkeyHint { color: #94A3B8; font-size: 9pt; }
QFrame#runDivider { background: #1E293B; border: none; }
QFrame#metricsStrip {
    background-color: #0B1220;
    border: 1px solid #1E293B;
    border-radius: 8px;
}
QLabel#metricLabel {
    color: #64748B;
    font-size: 9pt;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}
QLabel#metricValue {
    color: #F1F5F9;
    font-weight: 600;
    font-size: 11pt;
}
QFrame#metricSep { color: #1E293B; }
QLabel#sectionHeader {
    color: #94A3B8;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 1.2px;
    padding: 0 0 2px 0;
}
QFrame#sectionRule { background: #1E293B; border: none; }
QLabel#fieldLabel { color: #94A3B8; font-size: 9pt; }
QLabel#scaleLabel { color: #475569; font-size: 8pt; }
QLabel#valueChip {
    color: #F1F5F9;
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 2px 8px;
    font-weight: 600;
    font-size: 9pt;
}
QToolButton#previewToggle {
    background: transparent;
    color: #94A3B8;
    border: none;
    padding: 6px 4px;
    text-align: left;
    font-weight: 600;
    letter-spacing: 0.4px;
}
QToolButton#previewToggle:hover { color: #06B6D4; }
QFrame#previewPanel { background: transparent; border: none; }
QLabel#modeNote { color: #94A3B8; font-size: 9pt; }
QLabel { background: transparent; }
"""

LIGHT_STYLESHEET = """
QWidget {
    background-color: #F8FAFC;
    color: #0F172A;
    selection-background-color: #06B6D4;
    selection-color: #FFFFFF;
}
QMainWindow, QDialog, QScrollArea { background-color: #F8FAFC; }

QMenuBar {
    background-color: #FFFFFF;
    color: #334155;
    border-bottom: 1px solid #E2E8F0;
    padding: 2px 4px;
}
QMenuBar::item { padding: 6px 10px; background: transparent; border-radius: 4px; }
QMenuBar::item:selected { background: #F1F5F9; color: #0F172A; }
QMenu {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item { padding: 6px 22px 6px 14px; border-radius: 4px; }
QMenu::item:selected { background-color: #F1F5F9; color: #0F172A; }
QMenu::separator { height: 1px; background: #E2E8F0; margin: 4px 8px; }

QGroupBox {
    background-color: transparent;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 12px 10px 12px;
    font-weight: 600;
    color: #334155;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #64748B;
    background-color: #F8FAFC;
}

QTabWidget::pane {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    top: -1px;
}
QTabBar { qproperty-drawBase: 0; background: transparent; }
QTabBar::tab {
    background: transparent;
    color: #64748B;
    padding: 8px 16px;
    margin-right: 4px;
    border: none;
    border-bottom: 2px solid transparent;
    min-width: 80px;
}
QTabBar::tab:hover { color: #334155; }
QTabBar::tab:selected {
    color: #0F172A;
    border-bottom: 2px solid #0891B2;
}

QPushButton {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 14px;
    min-height: 22px;
}
QPushButton:hover { background-color: #F1F5F9; border-color: #94A3B8; }
QPushButton:pressed { background-color: #E2E8F0; }
QPushButton:focus { border-color: #06B6D4; outline: none; }
QPushButton:disabled { background-color: #F1F5F9; color: #CBD5E1; border-color: #E2E8F0; }

QPushButton#startButton {
    background-color: #16A34A;
    color: #FFFFFF;
    border: 1px solid #15803D;
    font-weight: 600;
}
QPushButton#startButton:hover { background-color: #15803D; border-color: #166534; }
QPushButton#startButton:pressed { background-color: #166534; }
QPushButton#startButton:disabled { background-color: #F1F5F9; color: #CBD5E1; border-color: #E2E8F0; }

QPushButton#pauseButton {
    background-color: #FFFFFF;
    color: #334155;
    border: 1px solid #CBD5E1;
    font-weight: 600;
}
QPushButton#pauseButton:hover {
    background-color: #FEF3C7;
    color: #92400E;
    border-color: #D97706;
}
QPushButton#pauseButton:disabled { background-color: #F1F5F9; color: #CBD5E1; border-color: #E2E8F0; }

QPushButton#stopButton {
    background-color: #FFFFFF;
    color: #334155;
    border: 1px solid #CBD5E1;
    font-weight: 600;
}
QPushButton#stopButton:hover {
    background-color: #DC2626;
    color: #FFFFFF;
    border-color: #B91C1C;
}
QPushButton#stopButton:pressed { background-color: #991B1B; color: #FFFFFF; }
QPushButton#stopButton:disabled { background-color: #F1F5F9; color: #CBD5E1; border-color: #E2E8F0; }

QToolButton {
    background-color: transparent;
    color: #334155;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 8px;
}
QToolButton:hover { background-color: #F1F5F9; border-color: #E2E8F0; }
QToolButton:pressed { background-color: #E2E8F0; }
QToolButton::menu-indicator { image: none; width: 0; }

QLineEdit, QSpinBox, QComboBox, QKeySequenceEdit, QTextEdit, QPlainTextEdit {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: #06B6D4;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QKeySequenceEdit:focus,
QTextEdit:focus, QPlainTextEdit:focus { border-color: #06B6D4; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
    color: #94A3B8; background-color: #F1F5F9;
}

QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    background: transparent;
    border: none;
    width: 16px;
    margin-right: 2px;
}
QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    background: transparent;
    border: none;
    width: 16px;
    margin-right: 2px;
}
QSpinBox::up-arrow { image: url({chev_up_light}); width: 10px; height: 9px; }
QSpinBox::down-arrow { image: url({chev_down_light}); width: 10px; height: 9px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #E2E8F0; border-radius: 3px; }

QComboBox::drop-down { width: 22px; border: none; background: transparent; }
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    selection-background-color: #F1F5F9;
    padding: 4px;
    outline: 0;
}

QCheckBox, QRadioButton { spacing: 8px; color: #334155; padding: 2px; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; }
QCheckBox::indicator {
    border: 1px solid #CBD5E1;
    border-radius: 4px;
    background: #FFFFFF;
}
QCheckBox::indicator:hover { border-color: #06B6D4; }
QCheckBox::indicator:checked {
    background-color: #0891B2;
    border: 1px solid #0891B2;
    image: url({check_white});
}
QRadioButton::indicator {
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    background: #FFFFFF;
}
QRadioButton::indicator:hover { border-color: #0891B2; }
QRadioButton::indicator:checked {
    border: 1.5px solid #0891B2;
    background: #FFFFFF;
    image: url({dot_light});
}

QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #E2E8F0;
    border-radius: 2px;
}
QSlider::sub-page:horizontal { background: #06B6D4; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #FFFFFF;
    border: 1px solid #94A3B8;
    width: 16px;
    height: 16px;
    margin: -7px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover { border-color: #06B6D4; }

QProgressBar {
    background-color: #E2E8F0;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    text-align: center;
    color: #0F172A;
    min-height: 18px;
}
QProgressBar::chunk { background-color: #06B6D4; border-radius: 5px; }

QSplitter { background: #F8FAFC; }
QSplitter::handle:horizontal { background: transparent; border: none; }
QSplitter::handle:horizontal:hover { background: transparent; }
QSplitter::handle:horizontal:pressed { background: transparent; }

QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 2px 4px 2px; }
QScrollBar::handle:vertical { background: rgba(148, 163, 184, 0.45); border-radius: 2px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: rgba(100, 116, 139, 0.85); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 2px 4px 2px 4px; }
QScrollBar::handle:horizontal { background: rgba(148, 163, 184, 0.45); border-radius: 2px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: rgba(100, 116, 139, 0.85); }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; background: none; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

QToolTip {
    background-color: #0F172A;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 4px 6px;
}

QLabel#statusBadge { border-radius: 6px; }
QFrame#masthead { background-color: #FFFFFF; border: none; }
QFrame#mastheadDivider { background: #E2E8F0; border: none; }
QLabel#wordmark {
    color: #0F172A;
    font-size: 13pt;
    font-weight: 700;
    letter-spacing: 0.6px;
}
QLabel#wordmarkVersion { color: #64748B; font-size: 9pt; padding-left: 4px; }
QLabel#personaLabel {
    color: #94A3B8;
    font-size: 9pt;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}
QComboBox#personaPill {
    background-color: #F1F5F9;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 14px;
    padding: 4px 12px;
    font-weight: 500;
}
QComboBox#personaPill:hover { border-color: #06B6D4; }
QLabel#hotkeyHint { color: #64748B; font-size: 9pt; }
QFrame#runDivider { background: #E2E8F0; border: none; }
QFrame#metricsStrip {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
}
QLabel#metricLabel {
    color: #94A3B8;
    font-size: 9pt;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}
QLabel#metricValue {
    color: #0F172A;
    font-weight: 600;
    font-size: 11pt;
}
QFrame#metricSep { color: #E2E8F0; }
QLabel#sectionHeader {
    color: #475569;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 1.2px;
    padding: 0 0 2px 0;
}
QFrame#sectionRule { background: #E2E8F0; border: none; }
QLabel#fieldLabel { color: #64748B; font-size: 9pt; }
QLabel#scaleLabel { color: #94A3B8; font-size: 8pt; }
QLabel#valueChip {
    color: #0F172A;
    background: #F1F5F9;
    border: 1px solid #CBD5E1;
    border-radius: 10px;
    padding: 2px 8px;
    font-weight: 600;
    font-size: 9pt;
}
QToolButton#previewToggle {
    background: transparent;
    color: #64748B;
    border: none;
    padding: 6px 4px;
    text-align: left;
    font-weight: 600;
    letter-spacing: 0.4px;
}
QToolButton#previewToggle:hover { color: #0891B2; }
QFrame#previewPanel { background: transparent; border: none; }
QLabel#modeNote { color: #64748B; font-size: 9pt; }
QLabel { background: transparent; }
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

            # Full AI-paste sanitize: entities, invisibles, exotic spaces,
            # smart punctuation, and line endings.
            text = sanitize_ai_text(text)
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

    _SHIFTED_US_SYMBOLS = {
        '!': '1',
        '@': '2',
        '#': '3',
        '$': '4',
        '%': '5',
        '^': '6',
        '&': '7',
        '*': '8',
        '(': '9',
        ')': '0',
        '_': '-',
        '+': '=',
        '{': '[',
        '}': ']',
        '|': '\\',
        ':': ';',
        '"': "'",
        '<': ',',
        '>': '.',
        '?': '/',
        '~': '`',
    }
    _AUTOCOMPLETE_GUARD_CHARS = set("()[]{}.,;:=#\"'")

    def _dismiss_autocomplete_popup(self, strong: bool = True):
        """Best-effort: close editor autocomplete/popups.

        Use `strong=True` before Enter/newlines; `strong=False` mid-line.
        """
        if not self.press_esc or self._target_is_browser:
            return
        presses = 2 if strong else 1
        delay = 0.06 if strong else 0.02
        # Many editors need a tiny delay after Esc so the next key doesn't accept a suggestion.
        for _ in range(presses):
            try:
                pyautogui.press('esc')
            except Exception:
                break
            self._sleep_interruptible(delay)

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

    def _release_modifiers_best_effort(self):
        # Clear any "stuck" modifiers which can cause shifted symbols to mis-type.
        for key in ("shift", "ctrl", "alt", "command", "cmd", "option"):
            try:
                pyautogui.keyUp(key)
            except Exception:
                pass

    def _type_shifted_symbol_us(self, ch: str) -> bool:
        """Type a shifted symbol via explicit public keyDown/keyUp calls so
        pyautogui.PAUSE fires between each event. pyautogui.hotkey() skips
        PAUSE between its inner keyDowns, which races shift and produces
        ")"→"0", "@"→"2", etc. at high speed."""
        base = self._SHIFTED_US_SYMBOLS.get(ch)
        if not base:
            return False
        return self._press_with_shift(base)

    def _type_shifted_letter(self, ch: str) -> bool:
        """Uppercase A-Z via explicit keyDown/keyUp. pyautogui.typewrite()
        internally fires shift-down/key-down/key-up/shift-up with no PAUSE
        between events, which races at high speed and produces "MAGI"→"mAGI"
        or shift-stuck corruption like "Google"→"GOOGLE"."""
        return self._press_with_shift(ch.lower())

    def _press_with_shift(self, base: str) -> bool:
        """Public keyDown/keyUp so pyautogui.PAUSE applies between each step.
        No manual sleeps, no _release_modifiers_best_effort — those caused
        state desync with macOS Quartz flag tracking."""
        try:
            pyautogui.keyDown("shift")
            pyautogui.keyDown(base)
            pyautogui.keyUp(base)
            pyautogui.keyUp("shift")
            return True
        except Exception:
            try:
                pyautogui.keyUp("shift")
            except Exception:
                pass
            return False

    def _maybe_dismiss_autocomplete_before_char(self, ch: str, prev_char: str):
        if not self.press_esc or self._target_is_browser:
            return
        if not ch:
            return
        # Tab is especially risky in VS Code (can accept suggestions).
        if ch == '\t':
            self._dismiss_autocomplete_popup(strong=False)
            return
        # If we're mid-identifier, punctuation can "commit" a suggestion in editors like VS Code.
        if prev_char and (prev_char.isalnum() or prev_char == '_') and ch in self._AUTOCOMPLETE_GUARD_CHARS:
            self._dismiss_autocomplete_popup(strong=False)

    def _type_character(self, ch: str) -> bool:
        """Type a single character with extra guardrails for code editors."""
        if ch == '\t':
            try:
                pyautogui.press("tab")
                return True
            except Exception:
                try:
                    pyautogui.typewrite('\t', interval=0.0)
                    return True
                except Exception:
                    return False
        if ch in self._SHIFTED_US_SYMBOLS:
            return self._type_shifted_symbol_us(ch)
        # Route uppercase A-Z through explicit shift handling too; typewrite
        # races shift internally the same way hotkey does.
        if len(ch) == 1 and ch.isascii() and ch.isalpha() and ch.isupper():
            return self._type_shifted_letter(ch)
        try:
            pyautogui.typewrite(ch, interval=0.0)
            return True
        except Exception:
            return False

    def _type_segment(self, segment, overall_start_time, chars_completed, total_chars_overall):
        # Types a segment of text with human-like behavior, preserving code formatting
        prev_char = ''
        for char in segment:
            if char == '\t' and not self.type_tabs:
                continue # Skip this character and go to the next one
            
            if not self._wait_until_ready():
                return chars_completed, False
            
            # At high speeds the backspace-and-retype sequence can race the
            # next keystroke and corrupt output, so suppress artificial
            # mistakes when the target WPM is fast. The checkbox still governs
            # slower, human-like ranges.
            if (self.add_mistakes
                    and self.max_wpm < 220
                    and random.random() < self.mistake_chance):
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
                    self._maybe_dismiss_autocomplete_before_char(char, prev_char)
                    if not self._type_character(char):
                        pyautogui.typewrite(char, interval=0.01)
            
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
            # A small global cushion between every pyautogui call. PAUSE=0 races
            # shift-up vs next-char-down on macOS, causing stuck shift state
            # ("Google"→"GOOGLE", ")"→"0"). 5ms is invisible to humans but
            # gives Quartz time to process modifier transitions in order.
            pyautogui.PAUSE = 0.005
            if self.enable_mouse_jitter:
                threading.Thread(target=self._mouse_jitter_thread, daemon=True).start()

            text_content = self.text_to_type or ""
            # Strip HTML entities, invisible/bidi chars, exotic spaces, and
            # normalize smart punctuation before a single keystroke goes out.
            text_content = sanitize_ai_text(text_content)

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
            self._release_modifiers_best_effort()
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
                                try:
                                    pyautogui.keyUp('shift')
                                except Exception:
                                    pass
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


# Lucide-style icon paths (24x24 viewBox). Stroke 2, round caps/joins.
# Render with `make_lucide_icon(name, color, size)` to get a tinted QIcon.
LUCIDE_PATHS = {
    # folder-open
    "open": "M6 14l1.5-2.9A2 2 0 0 1 9.3 10H21l-2.5 6.1A2 2 0 0 1 16.7 17H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.7 1l.8 1a2 2 0 0 0 1.7 1H18a2 2 0 0 1 2 2v2",
    # save (floppy)
    "save": "M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2zM17 21v-8H7v8 M7 3v5h8",
    # wand-sparkles (format)
    "format": "M15 4V2 M15 16v-2 M8 9h2 M20 9h2 M17.8 11.8 19 13 M15 9h0 M17.8 6.2 19 5 M3 21l9-9 M12.2 6.2 11 5",
    # code-2 (macros / code)
    "macros": "m18 16 4-4-4-4 M6 8l-4 4 4 4 M14.5 4l-5 16",
    # eraser (clean)
    "clean": "m7 21-4.3-4.3a1 1 0 0 1 0-1.4l9.6-9.6a1 1 0 0 1 1.4 0l5.6 5.6a1 1 0 0 1 0 1.4L13 21 M22 21H7 M5 11l9 9",
    # x (clear / trash-ish)
    "clear": "M18 6 6 18 M6 6l12 12",
    # play (start)
    "play": "M6 3v18l15-9z",
    # pause (two bars)
    "pause": "M14 4h4v16h-4z M6 4h4v16H6z",
    # square (stop)
    "stop": "M5 5h14v14H5z",
    # info
    "info": "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z M12 8h0 M11 12h1v4h1",
    # settings
    "settings": "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
}


_QSS_ASSETS_CACHE = None


def ensure_qss_assets():
    """Render small SVG indicators (checkmark, radio dot, chevrons) to PNG
    files and return a dict of forward-slash paths suitable for QSS ``url(...)``.

    Qt 5 doesn't accept ``data:`` URLs in stylesheets, so we drop the PNGs
    in a temp dir on first use and reference them by path.
    """
    global _QSS_ASSETS_CACHE
    if _QSS_ASSETS_CACHE:
        return _QSS_ASSETS_CACHE
    import tempfile
    try:
        from PyQt5.QtSvg import QSvgRenderer
    except Exception:
        return {}
    base = os.path.join(tempfile.gettempdir(), "nexustyper_qss_assets")
    os.makedirs(base, exist_ok=True)

    def _render(svg_str, size=16):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        renderer = QSvgRenderer(svg_str.encode("utf-8"))
        p = QPainter(pix)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            renderer.render(p)
        finally:
            p.end()
        return pix

    def _save(name, pix):
        path = os.path.join(base, name)
        pix.save(path, "PNG")
        return path.replace("\\", "/")

    assets = {}
    # Checkmarks. The on-cyan one uses white, the inverted one (used over a
    # transparent surface, currently unused) uses cyan.
    check_white = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
        '<path d="M3.5 8.5l3 3 6-6" fill="none" stroke="#FFFFFF" '
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    assets["check_white"] = _save("check_white.png", _render(check_white))

    # Radio dots — sit centered inside the indicator. Two variants because
    # the dot color contrasts differently in light vs dark themes.
    def _dot(color):
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
            f'<circle cx="8" cy="8" r="3.4" fill="{color}"/></svg>'
        )
    assets["dot_dark"] = _save("dot_dark.png", _render(_dot("#06B6D4")))
    assets["dot_light"] = _save("dot_light.png", _render(_dot("#0891B2")))

    # Spinbox chevrons — paired up + down arrows in dark and light variants.
    def _chev(direction, color):
        # 'up' or 'down'
        if direction == "up":
            d = "M2.5 5.5l2.5-2.5 2.5 2.5"
        else:
            d = "M2.5 4.5l2.5 2.5 2.5-2.5"
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 9">'
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.5" '
            'stroke-linecap="round" stroke-linejoin="round"/></svg>'
        )
    for theme, color in (("dark", "#94A3B8"), ("light", "#475569")):
        for direction in ("up", "down"):
            key = f"chev_{direction}_{theme}"
            assets[key] = _save(f"{key}.png", _render(_chev(direction, color), size=10))

    _QSS_ASSETS_CACHE = assets
    return assets


def make_lucide_icon(name, color="#94A3B8", size=20, stroke_width=1.8):
    """Render a Lucide-style icon to a QIcon, tinted to ``color``.

    Uses QSvgRenderer so SVG arc/bezier commands (which Lucide relies on)
    render correctly.
    """
    path_data = LUCIDE_PATHS.get(name)
    if not path_data:
        return QIcon()
    filled = name in ("play", "stop", "pause")
    if filled:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'<path d="{path_data}" fill="{color}" stroke="none"/></svg>'
        )
    else:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'<path d="{path_data}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke_width}" stroke-linecap="round" '
            f'stroke-linejoin="round"/></svg>'
        )
    try:
        from PyQt5.QtSvg import QSvgRenderer
    except Exception:
        return QIcon()
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    renderer = QSvgRenderer(svg.encode("utf-8"))
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        renderer.render(painter)
    finally:
        painter.end()
    return QIcon(pix)


class ChevronSplitterHandle(QSplitterHandle):
    """A splitter handle that paints a small chevron in the middle.

    The chevron flips direction based on whether the left pane is collapsed,
    giving the user a clear "click here to show/hide" affordance even when the
    sidebar has been dragged to zero width. Clicking the handle (without
    dragging) toggles the sidebar.
    """

    HANDLE_WIDTH = 14

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)
        self._press_pos = None
        self._hovered = False

    def sizeHint(self):
        return QSize(self.HANDLE_WIDTH, super().sizeHint().height())

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._press_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # If the mouse barely moved between press and release, treat it as a
        # click and ask the parent splitter to toggle.
        try:
            moved = (
                self._press_pos is None
                or (event.pos() - self._press_pos).manhattanLength() > 4
            )
        except Exception:
            moved = True
        super().mouseReleaseEvent(event)
        self._press_pos = None
        if not moved:
            sp = self.splitter()
            if hasattr(sp, "request_toggle"):
                sp.request_toggle()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()
        # Determine collapsed state from sibling sizes.
        sp = self.splitter()
        sizes = sp.sizes() if sp else [1, 1]
        collapsed = bool(sizes) and sizes[0] <= 1
        # Theme-aware colors via app palette.
        app = QApplication.instance()
        is_dark = False
        try:
            ss = app.styleSheet() if app else ""
            is_dark = "DARK" in ss[:120].upper() or "#0F172A" in ss[:200]
        except Exception:
            pass
        accent = QColor("#06B6D4")
        rail = QColor("#1E293B" if is_dark else "#E2E8F0")
        chevron = QColor(accent if (self._hovered or collapsed) else
                         QColor("#64748B" if is_dark else "#94A3B8"))
        # Subtle center spine instead of filling the whole 14px handle — keeps
        # the splitter quiet so it doesn't compete with the scrollbar next to it.
        cx = rect.center().x()
        cy = rect.center().y()
        spine_w = 1
        spine_h = max(rect.height() - 24, 0)
        if self._hovered or collapsed:
            spine_color = QColor(accent)
            spine_color.setAlphaF(0.30 if not collapsed else 0.55)
            painter.fillRect(int(cx - spine_w / 2), int(cy - spine_h / 2),
                             spine_w, spine_h, spine_color)
        else:
            spine_color = QColor(rail)
            spine_color.setAlphaF(0.7)
            painter.fillRect(int(cx - spine_w / 2), int(cy - spine_h / 2),
                             spine_w, spine_h, spine_color)
        # Chevron — 5px wide, 10px tall, pointing left when expanded, right when collapsed.
        pen = QPen(chevron)
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        path = QPainterPath()
        if collapsed:
            path.moveTo(cx - 2.5, cy - 5)
            path.lineTo(cx + 2.5, cy)
            path.lineTo(cx - 2.5, cy + 5)
        else:
            path.moveTo(cx + 2.5, cy - 5)
            path.lineTo(cx - 2.5, cy)
            path.lineTo(cx + 2.5, cy + 5)
        painter.drawPath(path)
        # A subtle dot pair above and below the chevron acts as a grip indicator.
        dot = QColor(chevron)
        dot.setAlphaF(0.55)
        painter.setPen(Qt.NoPen)
        painter.setBrush(dot)
        for dy in (-14, 14):
            painter.drawEllipse(QPoint(cx, cy + dy), 1, 1)
        painter.end()


class ChevronSplitter(QSplitter):
    """Horizontal splitter that uses ChevronSplitterHandle and animates toggles."""

    toggleRequested = pyqtSignal()

    def createHandle(self):
        return ChevronSplitterHandle(self.orientation(), self)

    def request_toggle(self):
        self.toggleRequested.emit()


class UpdateChecker(QObject):
    """Polls the GitHub Releases API for a newer version.

    Runs in a worker thread so a slow network never blocks startup. Emits
    `updateAvailable(version, url, body)` when the latest tag on the feed
    parses to a SemVer greater than ``APP_VERSION``. Emits
    `checkFailed(reason)` on transport/parse errors so the UI can stay quiet
    rather than nagging the user. Never raises into Qt.
    """

    updateAvailable = pyqtSignal(str, str, str)  # version, url, body
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
                    "User-Agent": f"{APP_NAME}/{APP_VERSION} (+update-check)",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                payload = _json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as e:
            self.checkFailed.emit(f"Update check failed: {e}")
            return

        latest_tag = (payload.get("tag_name") or payload.get("name") or "").strip()
        download_url = (payload.get("html_url") or UPDATE_DOWNLOAD_PAGE).strip()
        body = (payload.get("body") or "").strip()
        latest = self._parse_semver(latest_tag)
        current = self._parse_semver(self._current)
        if not latest or not current:
            self.checkFailed.emit(f"Could not parse versions ({latest_tag!r} vs {self._current!r})")
            return
        if latest > current:
            self.updateAvailable.emit(latest_tag.lstrip("v"), download_url, body)
        else:
            self.upToDate.emit(latest_tag.lstrip("v"))


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

        # Background update check — fires at most once a day, silent unless
        # an update is available. Delayed a few seconds so we never block
        # the first paint on a slow network.
        try:
            QTimer.singleShot(2500, lambda: self._start_update_check(verbose=False))
        except Exception:
            pass

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
            pass

        main_layout = QVBoxLayout(self)
        main_layout.setMenuBar(self.menu_bar)
        try:
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)
        except Exception:
            pass
        try:
            self.setMinimumSize(980, 640)
            self.resize(1240, 780)
        except Exception:
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
            # Soft minimum so tab labels stay legible, but not so wide that the
            # sidebar can't be shrunk or collapsed via the splitter.
            self.settings_scroll.setMinimumWidth(260)
        except Exception:
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
            pass
        # Track last open width so toggle restores it after a collapse.
        self._sidebar_last_width = 360
        try:
            self.splitter.splitterMoved.connect(self._on_splitter_moved)
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
            self.settings_tabs.setEnabled(enable)
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
            self.status_badge.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
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
        try:
            if hasattr(self, "hotkey_hint_label"):
                self.hotkey_hint_label.setText(f"⌨  {start}  ·  {stop}")
        except Exception:
            pass

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

    # --- In-app update checker ---
    def _start_update_check(self, verbose: bool = False):
        """Spin up a worker thread that pings the GitHub Releases feed.

        Background (verbose=False) checks fire at most once a day and stay
        silent unless an update is available. The Help → Check for Updates
        action passes verbose=True so it always reports status.
        """
        if not UPDATE_FEED_URL:
            if verbose:
                QMessageBox.information(self, "Updates",
                                        "Update checks are not configured for this build.")
            return
        # Throttle background checks. Manual checks bypass the throttle.
        if not verbose:
            try:
                last = float(self.settings.value("updateCheckLastEpoch", 0.0))
            except Exception:
                last = 0.0
            if (time.time() - last) < 86400:
                return
        existing = getattr(self, "_update_thread", None)
        if existing is not None and existing.isRunning():
            return
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
        self._update_thread.finished.connect(self._update_thread.deleteLater)
        self._update_thread.start()
        self.settings.setValue("updateCheckLastEpoch", time.time())

    def _on_update_available(self, version, url, body):
        try:
            logger.info(f"Update available: {version} (current {APP_VERSION})")
        except Exception:
            pass
        msg = QMessageBox(self)
        msg.setWindowTitle("Update available")
        msg.setIcon(QMessageBox.Information)
        msg.setText(f"<b>{APP_NAME} {version}</b> is available. You're on {APP_VERSION}.")
        if body:
            short = body if len(body) < 600 else body[:600] + "…"
            msg.setInformativeText(short)
        download_btn = msg.addButton("Open download page", QMessageBox.AcceptRole)
        msg.addButton("Later", QMessageBox.RejectRole)
        msg.exec_()
        if msg.clickedButton() is download_btn:
            try:
                QDesktopServices.openUrl(QUrl(url or UPDATE_DOWNLOAD_PAGE))
            except Exception:
                pass

    def _on_update_up_to_date(self, version):
        if getattr(self, "_update_verbose", False):
            QMessageBox.information(
                self, "Up to date",
                f"You're running the latest release ({APP_VERSION}).")

    def _on_update_failed(self, reason):
        try:
            logger.info(f"Update check: {reason}")
        except Exception:
            pass
        if getattr(self, "_update_verbose", False):
            QMessageBox.warning(self, "Update check failed", reason)
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
                pass

    def _animate_splitter(self, start, end, total):
        anim = getattr(self, "_sidebar_anim", None)
        if anim is not None:
            try:
                anim.stop()
            except Exception:
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
            mid = size / 2
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
            pass

    def _on_splitter_moved(self, *_):
        try:
            sizes = self.splitter.sizes()
        except Exception:
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
        pass

    # Rely on Qt window management for stability across platforms
    window = AutoTyperApp()
    window.show()
    sys.exit(app.exec_())
