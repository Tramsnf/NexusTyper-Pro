"""Text sanitization helpers for the typing engine.

These run on every chunk of text before a single keystroke goes out, so they
must be cheap and idempotent. The two main entry points are:

- ``sanitize_ai_text``: strip invisible/bidi chars, exotic spaces, smart
  punctuation, and HTML entities that leak in from AI chats, web pages,
  PDFs, Word, and Google Docs.
- ``apply_smart_newlines``: collapse soft-wrapped single newlines into
  spaces while preserving paragraph breaks, lists, blockquotes, headings,
  and indented/code-like lines.
"""

from __future__ import annotations
from nexustyper.services.logging_setup import _log_caught

import html
import re


# --- Smart-newline regexes ---------------------------------------------------
_SMART_BULLET_RE = re.compile(r"^\s*(?:[-*+]|•)\s+")
_SMART_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+")
_SMART_BLOCKQUOTE_RE = re.compile(r"^\s*>+\s+")
_SMART_HEADING_RE = re.compile(r"^\s*#{1,6}\s+")


# --- Invisible/bidi/punctuation tables --------------------------------------
# Characters that commonly leak in when pasting from AI chat UIs, rich
# editors, PDFs, Google Docs, Word, etc., and either render invisibly or
# confuse target apps. Stripped/replaced by sanitize_ai_text.
_AI_INVISIBLE_CHARS = (
    '​‌‍⁠﻿'   # ZWSP, ZWNJ, ZWJ, WORD JOINER, BOM
    '‎‏'                     # LRM, RLM (bidi marks)
    '‪‫‬‭‮'   # LRE, RLE, PDF, LRO, RLO (bidi embedding)
    '⁦⁧⁨⁩'         # LRI, RLI, FSI, PDI (bidi isolates)
    '­'                           # SOFT HYPHEN
)
_AI_INVISIBLE_TABLE = str.maketrans('', '', _AI_INVISIBLE_CHARS)

_AI_PUNCT_TABLE = str.maketrans({
    ' ': ' ',  # NO-BREAK SPACE
    ' ': ' ',  # NARROW NO-BREAK SPACE
    ' ': ' ',  # FIGURE SPACE
    ' ': ' ',  # PUNCTUATION SPACE
    ' ': ' ',  # THIN SPACE
    ' ': ' ',  # HAIR SPACE
    ' ': ' ',  # MEDIUM MATHEMATICAL SPACE
    '　': ' ',  # IDEOGRAPHIC SPACE
    ' ': '\n',  # LINE SEPARATOR
    ' ': '\n',  # PARAGRAPH SEPARATOR
    '“': '"', '”': '"',  # curly double quotes
    '‘': "'", '’': "'",  # curly single quotes
    '‚': ',', '„': '"',  # low-9 quotes — single low-9 → comma, double low-9 → straight quote
    '′': "'", '″': '"',  # prime, double prime
    '–': '-',                  # en dash
    '—': '--',                 # em dash
    '…': '...',                # ellipsis
    '−': '-',                  # minus sign
    '×': 'x',                  # multiplication sign (pyautogui can't
                                    #   type U+00D7 cleanly)
    '÷': '/',                  # division sign
})


def sanitize_ai_text(text: str) -> str:
    """Normalize text pasted/typed from AI chats, web pages, PDFs, docs.

    Handles: HTML entities (&amp; -> &), zero-width chars, bidi marks, soft
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
        _log_caught('apply_smart_newlines@L97')
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
        _log_caught('apply_smart_newlines@L128')
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


__all__ = [
    "sanitize_ai_text",
    "apply_smart_newlines",
    "_SMART_BULLET_RE",
    "_SMART_NUMBERED_RE",
    "_SMART_BLOCKQUOTE_RE",
    "_SMART_HEADING_RE",
    "_AI_INVISIBLE_CHARS",
    "_AI_INVISIBLE_TABLE",
    "_AI_PUNCT_TABLE",
]


