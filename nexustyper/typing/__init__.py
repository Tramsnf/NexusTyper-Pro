"""Typing engine package.

Modules:
  sanitize.py          text-cleaning helpers (sanitize_ai_text, apply_smart_newlines)
  macros.py            inline {{PAUSE/PRESS/CLICK/COMMENT}} parsing & execution
  mistakes.py          QWERTY adjacency map for fat-finger error injection
  personas.py          typing persona presets
  browser.py           window-title heuristics for auto-optimize
  worker.py            TypingWorker (Qt thread that drives the typing loop)
  dry_run.py           DryRunWorker (preview-only worker)
  content_detection.py pure content-classification helpers

Public re-exports below mirror the most-used symbols so callers can write
``from nexustyper.typing import TypingWorker`` without reaching into the
submodules.
"""

from __future__ import annotations

from nexustyper.typing.browser import (
    auto_optimize_for_window,
    is_browser_title,
    looks_like_code_quick,
)
from nexustyper.typing.dry_run import DryRunWorker
from nexustyper.typing.macros import (
    MACRO_FULLMATCH_RE,
    MACRO_SPLIT_RE,
    execute_macro,
    strip_macros,
    validate_macro,
)
from nexustyper.typing.mistakes import KEY_ADJACENCY, adjacent_key, has_adjacent
from nexustyper.typing.personas import (
    CODE_DEFAULTS,
    PERSONA_CAREFUL_CODER,
    PERSONA_CUSTOM,
    PERSONA_DELIBERATE_WRITER,
    PERSONA_FAST_MESSENGER,
    PERSONA_NAMES,
    PERSONA_PRESETS,
    apply_persona,
)
from nexustyper.typing.content_detection import (
    categorize_title,
    contains_non_ascii,
    detect_content_kind,
    looks_like_code,
    looks_like_math,
)
from nexustyper.typing.sanitize import apply_smart_newlines, sanitize_ai_text
from nexustyper.typing.worker import MISTAKE_CHANCE, TypingWorker


__all__ = [
    "TypingWorker",
    "DryRunWorker",
    "MISTAKE_CHANCE",
    # sanitize
    "sanitize_ai_text",
    "apply_smart_newlines",
    # macros
    "MACRO_SPLIT_RE",
    "MACRO_FULLMATCH_RE",
    "validate_macro",
    "execute_macro",
    "strip_macros",
    # mistakes
    "KEY_ADJACENCY",
    "adjacent_key",
    "has_adjacent",
    # personas
    "PERSONA_NAMES",
    "PERSONA_PRESETS",
    "PERSONA_CAREFUL_CODER",
    "PERSONA_DELIBERATE_WRITER",
    "PERSONA_FAST_MESSENGER",
    "PERSONA_CUSTOM",
    "CODE_DEFAULTS",
    "apply_persona",
    # browser
    "is_browser_title",
    "looks_like_code_quick",
    "auto_optimize_for_window",
    # content_detection
    "categorize_title",
    "detect_content_kind",
    "contains_non_ascii",
    "looks_like_code",
    "looks_like_math",
]
