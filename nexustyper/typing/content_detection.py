"""Content-classification helpers extracted from AutoTyperApp.

Pure functions — no class state, no Qt imports.

Functions
---------
categorize_title      Classify an app window title into a broad category.
detect_content_kind   Heuristic detection of 'code', 'math', or 'prose'.
contains_non_ascii    Return True if any character has ord > 0x7F.
looks_like_code       Return True if text resembles source code.
looks_like_math       Return True if text resembles mathematical notation.
"""

from __future__ import annotations


def categorize_title(title: str) -> str:
    """Return a broad category for an app window *title*.

    Returns one of: 'code', 'chat', 'text', 'browser', 'unknown'.
    """
    t = (title or "").lower()
    if any(k in t for k in [
        "code", "pycharm", "intellij", "webstorm", "clion", "goland",
        "xcode", "sublime", "atom", "notepad++", "vim", "emacs",
    ]):
        return 'code'
    if any(k in t for k in [
        "slack", "teams", "discord", "skype", "telegram", "whatsapp",
        "wechat", "messages", "imessage",
    ]):
        return 'chat'
    if any(k in t for k in ["notepad", "textedit", "notes"]):
        return 'text'
    if any(k in t for k in [
        "safari", "chrome", "chromium", "firefox", "edge", "brave", "opera",
    ]):
        return 'browser'
    return 'unknown'


def detect_content_kind(text: str) -> str:
    """Heuristic content detection: returns 'code', 'math', or 'prose'."""
    t = text.strip()
    if not t:
        return 'prose'
    try:
        if looks_like_code(t):
            return 'code'
        if looks_like_math(t):
            return 'math'
    except Exception:
        pass
    return 'prose'


def contains_non_ascii(text: str) -> bool:
    """Return True if *text* contains any character with ord > 0x7F."""
    try:
        return any(ord(ch) > 0x7F for ch in text)
    except Exception:
        return False


def looks_like_code(text: str) -> bool:
    """Return True if *text* appears to be source code."""
    t = text
    # Fast signals
    if '```' in t or '\t' in t:
        return True
    # Programming keywords across common languages
    code_keywords = [
        'import ', 'from ', 'def ', 'class ', 'return', 'if ', 'elif ',
        'else:', 'while ', 'for ', 'try:', 'except', 'finally:',
        'function ', 'var ', 'let ', 'const ', '=>', 'console.log',
        'export ', 'require(', 'module.exports',
        '#include', 'using ', 'namespace ', 'public ', 'private ',
        'protected ', 'static ', 'void ', 'int ', 'string ', 'std::',
        'fn ', 'match ', 'impl ', 'package ', 'interface ', 'enum ', 'struct ',
    ]
    if any(kw in t for kw in code_keywords):
        return True
    # Symbols and patterns common in code
    code_symbol_hits = sum(1 for ch in t if ch in '{}();<>[]:=#')
    lines = t.splitlines()
    semicolon_lines = sum(1 for ln in lines if ln.strip().endswith(';'))
    brace_lines = sum(
        1 for ln in lines
        if ln.strip().endswith('{') or ln.strip().endswith('}')
    )
    indent_lines = sum(
        1 for ln in lines
        if ln.startswith('    ') or ln.startswith('\t')
    )
    # Heuristic thresholds
    if code_symbol_hits >= max(6, len(t) // 80):
        return True
    if (semicolon_lines + brace_lines + indent_lines) >= max(3, len(lines) // 4):
        return True
    return False


def looks_like_math(text: str) -> bool:
    """Return True if *text* appears to contain mathematical notation."""
    t = text
    # Detect LaTeX math markers or Unicode math symbols
    latex_markers = [
        '\\frac', '\\sum', '\\prod', '\\int', '\\sqrt', '\\lim',
        '\\infty', '\\approx', '\\neq', '\\leq', '\\geq',
        '\\alpha', '\\beta', '\\gamma', '\\delta', '\\theta',
        '\\lambda', '\\mu', '\\pi', '\\sigma', '\\omega', '$',
    ]
    if any(m in t for m in latex_markers):
        return True
    math_chars = set('∑∏√∞≤≥≈≠±°×÷∂∇πθαλµσδΩω∧∨⊂⊆∈∉∪∩∘→←↔·′″≃≡⊥∥∖∫∮∝')
    math_hits = sum(1 for ch in t if ch in math_chars)
    caret_unders = t.count('^') + t.count('_')
    # Equations often have many operators
    operator_hits = sum(1 for ch in t if ch in '+-*/=<>')
    if math_hits >= 1:
        return True
    if caret_unders >= 2 and operator_hits >= 2:
        return True
    # Many short lines with operators suggests laid-out formula
    lines = t.splitlines()
    short_eq_lines = sum(
        1 for ln in lines
        if len(ln.strip()) <= 24 and any(op in ln for op in ['=', '≤', '≥', '≠'])
    )
    if short_eq_lines >= 2:
        return True
    return False
