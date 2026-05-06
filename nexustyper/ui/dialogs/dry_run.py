"""DryRunDialog — preview the typing sequence without sending keystrokes."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QTextEdit,
    QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt, QThread

from nexustyper.typing.dry_run import DryRunWorker
from nexustyper.ui.widgets.text_edit import CodeEditor


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
