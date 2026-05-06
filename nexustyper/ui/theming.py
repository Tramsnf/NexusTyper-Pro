"""QSS stylesheets and on-disk QSS asset rendering for NexusTyper Pro.

Qt 5 doesn't accept ``data:`` URLs in stylesheets, so we render small SVG
indicators (checkmark, radio dot, chevrons) to PNG files in a temp dir on
first use and reference them by path. ``ensure_qss_assets`` returns a dict of
forward-slash paths suitable for QSS ``url(...)`` substitution, e.g.::

    assets = ensure_qss_assets()
    sheet = DARK_STYLESHEET.format(**assets)

The returned dict is module-level cached so repeated calls are cheap.
"""

from __future__ import annotations

import os
from typing import Dict

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPixmap


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


# Module-level cache so repeated calls don't re-render the SVGs.
_QSS_ASSETS_CACHE: Dict[str, str] = {}


def ensure_qss_assets() -> Dict[str, str]:
    """Render small SVG indicators (checkmark, radio dot, chevrons) to PNG
    files and return a dict of forward-slash paths suitable for QSS ``url(...)``.

    Qt 5 doesn't accept ``data:`` URLs in stylesheets, so we drop the PNGs in
    a temp dir on first use and reference them by path. Returns an empty dict
    if ``PyQt5.QtSvg`` isn't available (e.g. headless Linux without the SVG
    plugin) — callers should treat the resulting QSS substitutions as
    best-effort.
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

    assets: Dict[str, str] = {}
    # Checkmark — white stroke, sits on cyan checkbox fill.
    check_white = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
        '<path d="M3.5 8.5l3 3 6-6" fill="none" stroke="#FFFFFF" '
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    assets["check_white"] = _save("check_white.png", _render(check_white))

    # Radio dots — sit centered inside the indicator. Two variants because the
    # dot color contrasts differently in light vs dark themes.
    def _dot(color):
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
            f'<circle cx="8" cy="8" r="3.4" fill="{color}"/></svg>'
        )

    assets["dot_dark"] = _save("dot_dark.png", _render(_dot("#06B6D4")))
    assets["dot_light"] = _save("dot_light.png", _render(_dot("#0891B2")))

    # Spinbox chevrons — paired up + down arrows in dark and light variants.
    def _chev(direction, color):
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


__all__ = ["DARK_STYLESHEET", "LIGHT_STYLESHEET", "ensure_qss_assets"]
