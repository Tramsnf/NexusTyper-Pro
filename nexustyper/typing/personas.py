"""Persona presets for the typing engine.

Each persona is a plain dict of typing-engine settings. The UI layer
(AutoTyperApp) decides which preset to apply and pushes the values onto its
QSpinBox/QSlider/QCheckBox widgets — this module only owns the *data*.

The toggle-controls logic that wires personas onto widgets stays in the UI
layer because it's tightly coupled to the input-mode tabs (Plain Text vs
Code) and to the code-defaults block. ``apply_persona`` here returns a
flat overrides dict so a future refactor of the UI loop can stay simple.
"""

from __future__ import annotations

from typing import Dict


PERSONA_DELIBERATE_WRITER = "Deliberate Writer"
PERSONA_FAST_MESSENGER = "Fast Messenger"
PERSONA_CAREFUL_CODER = "Careful Coder"
PERSONA_CUSTOM = "Custom (Manual Settings)"


PERSONA_NAMES = (
    PERSONA_CUSTOM,
    PERSONA_DELIBERATE_WRITER,
    PERSONA_FAST_MESSENGER,
    PERSONA_CAREFUL_CODER,
)


# WPM ranges per persona. The boolean defaults below are the "Plain Text" ones
# from the source — Code mode overrides several of them (see CODE_DEFAULTS).
PERSONA_PRESETS: Dict[str, Dict[str, object]] = {
    PERSONA_CAREFUL_CODER: {
        "min_wpm": 90,
        "max_wpm": 140,
        "newline_mode": "Standard",
        "use_shift_enter": False,
        "press_esc": False,
        "type_tabs": True,
        "add_mistakes": True,
        "pause_on_punct": True,
        "mouse_jitter": True,
    },
    PERSONA_DELIBERATE_WRITER: {
        "min_wpm": 70,
        "max_wpm": 110,
        "newline_mode": "Standard",
        "use_shift_enter": False,
        "press_esc": False,
        "type_tabs": True,
        "add_mistakes": True,
        "pause_on_punct": True,
        "mouse_jitter": True,
    },
    PERSONA_FAST_MESSENGER: {
        "min_wpm": 120,
        "max_wpm": 180,
        "newline_mode": "Smart Newlines",
        "use_shift_enter": True,
        "press_esc": False,
        "type_tabs": True,
        "add_mistakes": True,
        "pause_on_punct": True,
        # Keep jitter off by default for messenger to avoid suspicion.
        "mouse_jitter": False,
    },
    PERSONA_CUSTOM: {
        # Custom keeps whatever the user last set; emit empty to mean
        # "no overrides" — the caller can fall back to its own defaults.
    },
}


# Code-mode defaults shared across personas (the "Code" input-mode tab in the
# UI applies these regardless of persona; only the WPM range varies).
CODE_DEFAULTS: Dict[str, object] = {
    "newline_mode": "List Mode",
    "use_shift_enter": False,
    "press_esc": True,
    "type_tabs": False,
    "add_mistakes": False,
    "pause_on_punct": True,
    "mouse_jitter": False,
    "ime_friendly": False,
}


def apply_persona(persona_name: str, *, in_code_mode: bool = False) -> Dict[str, object]:
    """Return a flat dict of typing-engine overrides for ``persona_name``.

    If ``in_code_mode`` is True, the code-mode defaults are layered on top of
    the persona's WPM range so the caller gets one merged dict.

    Unknown personas yield an empty dict ("don't change anything").
    """
    base = dict(PERSONA_PRESETS.get(persona_name, {}))
    if in_code_mode:
        merged = {**base, **CODE_DEFAULTS}
        # The persona still owns the WPM range in code mode.
        if "min_wpm" in base:
            merged["min_wpm"] = base["min_wpm"]
        if "max_wpm" in base:
            merged["max_wpm"] = base["max_wpm"]
        return merged
    return base


__all__ = [
    "PERSONA_DELIBERATE_WRITER",
    "PERSONA_FAST_MESSENGER",
    "PERSONA_CAREFUL_CODER",
    "PERSONA_CUSTOM",
    "PERSONA_NAMES",
    "PERSONA_PRESETS",
    "CODE_DEFAULTS",
    "apply_persona",
]
