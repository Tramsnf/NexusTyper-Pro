"""Custom QTextEdit / QPlainTextEdit widgets for NexusTyper Pro."""

import re

from PyQt5.QtWidgets import QTextEdit, QPlainTextEdit, QCompleter
from PyQt5.QtCore import Qt, pyqtSignal, QStringListModel
from PyQt5.QtGui import QTextDocument, QFontDatabase, QFontMetrics

from nexustyper.typing.sanitize import sanitize_ai_text


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
                html_payload = source.html()
                doc = QTextDocument()
                doc.setHtml(html_payload)
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
                html_payload = source.html()
                doc = QTextDocument()
                doc.setHtml(html_payload)
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
