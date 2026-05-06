"""Function-guide help dialog.

Static, read-only HTML cheat sheet describing personas, humanization knobs,
newline modes, and ancillary features. Pure view — no controller wiring.
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog, QPushButton, QTextEdit, QVBoxLayout,
)


_DEFAULT_HELP_HTML = """
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
"""


class HelpDialog(QDialog):
    """Read-only HTML help cheat sheet."""

    def __init__(
        self,
        *,
        title: str = "Function Guide",
        html: str = _DEFAULT_HELP_HTML,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 400)

        text = QTextEdit(self)
        text.setReadOnly(True)
        text.setHtml(html)

        layout = QVBoxLayout(self)
        layout.addWidget(text)

        btn = QPushButton("OK")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)


__all__ = ["HelpDialog"]
