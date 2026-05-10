"""nexustyper.services.hotkeys — Qt-to-pynput hotkey translation helpers.

Public API
----------
translate_hotkey_for_pynput(hotkey: str) -> str
    Convert a Qt hotkey string (QKeySequence portable text, e.g. "Ctrl+Alt+S")
    into the angle-bracket notation expected by pynput GlobalHotKeys
    (e.g. "<ctrl>+<alt>+s").  Returns an empty string when the input is empty
    or cannot be parsed.
"""
from nexustyper.services.logging_setup import _log_caught

from PyQt5.QtGui import QKeySequence


def translate_hotkey_for_pynput(hotkey) -> str:
    """Translate a Qt hotkey (QKeySequence text) to pynput GlobalHotKeys format.

    Accepts any representation that QKeySequence understands (NativeText,
    PortableText, or a raw string like "Ctrl+Alt+S") and normalises it to
    PortableText before mapping modifiers and special keys to pynput's
    angle-bracket notation.

    Only single-chord sequences are supported; if a multi-chord sequence is
    given, only the first chord is used.

    Returns:
        A pynput-compatible hotkey string such as ``"<ctrl>+<alt>+s"``, or an
        empty string if the input is empty or contains no valid key parts.
    """
    if not hotkey:
        return ""
    # Normalize whatever we stored (NativeText/PortableText) into PortableText.
    try:
        hotkey = QKeySequence(str(hotkey)).toString(QKeySequence.PortableText)
    except Exception:
        _log_caught('translate_hotkey_for_pynput@L35')
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
        'meta': '<cmd>', 'cmd': '<cmd>', 'command': '<cmd>',
        'win': '<cmd>', 'windows': '<cmd>', 'super': '<cmd>',
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


