"""DryRunWorker — emits a character-by-character preview without keystrokes.

A near-verbatim extraction of ``DryRunWorker`` from ``NexusTyper Pro.py``.
The pyqtSignal declarations and constructor signature stay byte-identical so
``DryRunDialog`` keeps working.
"""

from __future__ import annotations
from nexustyper.services.logging_setup import _log_caught

import random
import re
import time

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from nexustyper.typing.macros import MACRO_FULLMATCH_RE, MACRO_SPLIT_RE
from nexustyper.typing.sanitize import apply_smart_newlines


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
            for _lap in range(self.laps):
                if not self._running:
                    break
                if self.mode == 'Smart Newlines':
                    content_iter = apply_smart_newlines(content)
                else:
                    content_iter = content
                if self.mode == 'List Mode':
                    lines = content_iter.splitlines()
                    for line in lines:
                        if not self._running:
                            break
                        out = ''
                        prev = ''
                        for ch in line.lstrip().replace('\t', ''):
                            if not self._running:
                                break
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
                        segments = re.split(MACRO_SPLIT_RE.pattern, content_iter)
                    prev = ''
                    for seg in segments:
                        if not self._running:
                            break
                        if self.enable_macros and MACRO_FULLMATCH_RE.fullmatch(seg):
                            # show nothing for macros; could display a hint if desired
                            continue
                        for ch in seg:
                            if not self._running:
                                break
                            self.update_preview.emit(ch)
                            time.sleep(self._delay(prev, ch))
                            prev = ch
            self.finished.emit()
        except Exception:
            _log_caught('run@L101')
            self.finished.emit()


__all__ = ["DryRunWorker"]
