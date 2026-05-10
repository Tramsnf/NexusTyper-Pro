"""Macro parsing, validation, and execution for the typing engine.

Inline macros are parsed from text segments and look like ``{{PAUSE:1.5}}``,
``{{PRESS:enter}}``, ``{{CLICK:120,240}}``, or ``{{COMMENT:notes}}``.

This module exposes:

- ``MACRO_SPLIT_RE``: split a string into segments where macros are isolated.
- ``MACRO_FULLMATCH_RE``: full-match a single ``{{COMMAND:params}}`` segment.
- ``strip_macros``: remove all macro tokens from a string.
- ``validate_macro``: check a (command, params) pair and normalize it.
- ``execute_macro``: execute a normalized (command, params) tuple. Takes a
  ``sleep_fn(seconds)`` callback so the worker can keep its
  pause/stop-aware sleep semantics.

``validate_macro`` and ``execute_macro`` are pure-ish helpers — they don't
own worker state. The worker still owns the per-keystroke loop and decides
when to call them.
"""

from __future__ import annotations
from nexustyper.services.logging_setup import _log_caught

import re
from typing import Callable, Optional, Set, Tuple


# Regex used to split text into [text, macro, text, macro, ...] segments.
MACRO_SPLIT_RE = re.compile(r'(?i)(\{\{(?:PAUSE|PRESS|CLICK|COMMENT):.*?\}\})')

# Regex used to match a single macro segment exactly.
MACRO_FULLMATCH_RE = re.compile(r'\{\{([A-Za-z]+):(.*)\}\}')

# Used by strip_macros to remove macros wholesale.
_MACRO_STRIP_RE = re.compile(r'(?i)\{\{(?:PAUSE|PRESS|CLICK|COMMENT):.*?\}\}')


def strip_macros(text: str) -> str:
    """Remove every macro token from ``text``. Safe on falsy/non-str input."""
    if not text:
        return text
    try:
        return _MACRO_STRIP_RE.sub('', text)
    except Exception:
        _log_caught('strip_macros@L43')
        return text


def validate_macro(
    command: str,
    params: str,
    *,
    allowed_keys: Optional[Set[str]] = None,
    screen_size: Optional[Tuple[int, int]] = None,
) -> Tuple[bool, Optional[str], Optional[Tuple[str, str]]]:
    """Validate a (command, params) macro pair.

    Returns ``(ok, error_message, normalized)`` where ``normalized`` is a
    ``(COMMAND, params_str)`` tuple suitable for ``execute_macro``.

    - ``allowed_keys`` (optional): the set of pyautogui ``KEYBOARD_KEYS``;
      passed in by the worker so this module stays pyautogui-free.
    - ``screen_size`` (optional): ``(width, height)`` for CLICK bounds checks.
    """
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
            _log_caught('validate_macro@L73')
            return False, f"Invalid PAUSE duration: '{p}'", None
    elif cmd == 'CLICK':
        try:
            x_str, y_str = p.split(',')
            x, y = int(x_str), int(y_str)
            if screen_size is not None:
                try:
                    w, h = screen_size
                    if not (0 <= x < w and 0 <= y < h):
                        return False, f"CLICK coordinates out of bounds: {x},{y}", None
                except Exception:
                    _log_caught('validate_macro@L84')
                    pass
            return True, None, (cmd, f"{x},{y}")
        except Exception:
            _log_caught('validate_macro@L87')
            return False, f"Invalid CLICK params, expected 'x,y' got '{p}'", None
    elif cmd == 'PRESS':
        key = p.lower()
        if not key:
            return False, "PRESS requires a key name", None
        if allowed_keys and key not in allowed_keys:
            return False, f"Unknown key for PRESS: '{key}'", None
        return True, None, (cmd, key)
    elif cmd == 'COMMENT':
        return True, None, (cmd, p)
    else:
        return False, f"Unknown macro: '{cmd}'", None


def execute_macro(
    command: str,
    params: str,
    *,
    sleep_fn: Callable[[float], None],
) -> None:
    """Execute a *validated* macro tuple.

    ``sleep_fn`` is the worker's pause/stop-aware sleep so PAUSE macros can be
    interrupted. Other macros call into pyautogui directly. The caller is
    responsible for catching/reporting exceptions (so it can include
    platform-specific hints, e.g. macOS Accessibility errors).
    """
    import pyautogui  # local import: keeps this module importable in tests
    # Local import: matches the ``import pyautogui`` style above and avoids
    # forcing the keyboard module's ctypes setup at validation time.
    from nexustyper.typing.keyboard import kbd

    if command == 'PAUSE':
        sleep_fn(float(params))
    elif command == 'PRESS':
        # validate_macro already lower()/strip()-ed the key name. Routed
        # through the keyboard shim so PRESS macros also reach the remote
        # session in RDP-compat mode.
        kbd.press(params)
    elif command == 'CLICK':
        x, y = params.split(',')
        pyautogui.click(int(x), int(y))
    # COMMENT is a no-op.


__all__ = [
    "MACRO_SPLIT_RE",
    "MACRO_FULLMATCH_RE",
    "strip_macros",
    "validate_macro",
    "execute_macro",
]
