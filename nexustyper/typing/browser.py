"""Window-title heuristics for auto-optimizing typing settings.

Used by ``TypingWorker`` when the user enables auto-detect: we look at the
focused window title and return a dict of overrides to merge into the
current settings (e.g. browser -> disable Esc, code editor -> List Mode).

This module is Qt-free; it just classifies titles and returns data.
"""

from __future__ import annotations

from typing import Dict


_BROWSER_KEYWORDS = ("safari", "chrome", "chromium", "firefox", "edge", "brave", "opera")
_CODE_KEYWORDS = (
    "code", "pycharm", "intellij", "webstorm", "clion", "goland",
    "xcode", "sublime", "atom", "notepad++", "vim", "emacs",
)
_CHAT_KEYWORDS = (
    "slack", "teams", "discord", "skype", "telegram", "whatsapp",
    "wechat", "messages", "imessage",
)
_TEXT_KEYWORDS = ("notepad", "textedit", "notes")


def is_browser_title(title: str) -> bool:
    """Return True if ``title`` looks like a web browser."""
    t = (title or "").lower()
    return any(k in t for k in _BROWSER_KEYWORDS)


def looks_like_code_quick(text: str) -> bool:
    """Heuristic check: does ``text`` look like source code?"""
    try:
        t = (text or "").strip()
    except Exception:
        return False
    if not t:
        return False
    if '\t' in t or '```' in t:
        return True
    lines = t.splitlines()
    if len(lines) >= 2:
        indent_lines = sum(
            1 for ln in lines[:40]
            if ln.startswith('    ') or ln.startswith('\t')
        )
        if indent_lines >= 2:
            return True
    hits = sum(1 for ch in t[:500] if ch in '{}();[]<>:=#')
    if hits >= 8:
        return True
    for kw in (
        'def ', 'class ', 'import ', 'from ', 'return',
        'function ', 'const ', 'let ', 'var ', '#include',
        'fn ', 'struct ', 'interface ',
    ):
        if kw in t:
            return True
    return False


def auto_optimize_for_window(
    title: str,
    *,
    text_to_type: str = "",
    current_newline_mode: str = "Standard",
) -> Dict[str, object]:
    """Pick a setting bundle for the given focused window title.

    Returns a dict with the keys the worker cares about:

    - ``press_esc`` (bool)
    - ``use_shift_enter`` (bool)
    - ``type_tabs`` (bool)
    - ``add_mistakes`` (bool)
    - ``pause_on_punct`` (bool)
    - ``newline_mode`` (str, optional — only set when we want to override)
    - ``chosen`` (str | None) — human-readable label for status messages

    An empty dict (with ``chosen=None``) means "no rule matched, leave the
    settings alone". Callers should treat unspecified keys as "no change".
    """
    t = (title or "").lower()
    overrides: Dict[str, object] = {"chosen": None}

    if any(k in t for k in _BROWSER_KEYWORDS):
        # Browsers can treat Esc as "cancel" (stop load/close UI). Avoid it.
        overrides.update({
            "press_esc": False,
            "use_shift_enter": False,
            "type_tabs": True,
            "add_mistakes": False,
            "pause_on_punct": True,
            "chosen": "Browser",
        })
        return overrides

    if any(k in t for k in _CODE_KEYWORDS):
        # IDEs often have aggressive autocomplete/auto-closing; use Esc and
        # disable artificial mistakes.
        overrides.update({
            "press_esc": True,
            "use_shift_enter": False,
            "type_tabs": True,
            "add_mistakes": False,
            "pause_on_punct": True,
            "chosen": "Code editor",
        })
        # For code-like content in a code editor, List Mode avoids
        # indentation drift from editor auto-indent. Never force Paste Mode;
        # only adjust away from modes that break code formatting.
        if looks_like_code_quick(text_to_type) and current_newline_mode != "Paste Mode":
            overrides["newline_mode"] = "List Mode"
        return overrides

    if any(k in t for k in _CHAT_KEYWORDS):
        overrides.update({
            "use_shift_enter": True,
            "press_esc": False,
            "add_mistakes": True,
            "pause_on_punct": True,
            "chosen": "Chat app",
        })
        return overrides

    if any(k in t for k in _TEXT_KEYWORDS):
        overrides.update({
            "press_esc": False,
            "use_shift_enter": False,
            "type_tabs": True,
            "add_mistakes": False,
            "pause_on_punct": True,
            "chosen": "Plain text editor",
        })
        return overrides

    return overrides


# Backwards-compatible alias the worker uses internally.
_is_browser_title = is_browser_title


__all__ = [
    "is_browser_title",
    "looks_like_code_quick",
    "auto_optimize_for_window",
    "_is_browser_title",
]
