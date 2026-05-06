"""Mistake-injection helpers for human-like typing.

The QWERTY adjacency map is the only piece of state here. ``adjacent_key``
returns a random neighbour for the given lowercase letter so the worker can
type-then-correct to simulate a fat-finger error.
"""

from __future__ import annotations

import random


# Keyboard adjacency map for simulating realistic typing mistakes.
# Keys are lowercase ASCII letters; values are strings of likely-typo
# replacements (a random char is picked at injection time).
KEY_ADJACENCY = {
    'q': 'ws', 'w': 'qase', 'e': 'wsdr', 'r': 'edft', 't': 'rfgy',
    'y': 'tghu', 'u': 'yhji', 'i': 'ujko', 'o': 'iklp', 'p': 'ol;',
    'a': 'qwsz', 's': 'qwedzx', 'd': 'werfcx', 'f': 'ertgvc', 'g': 'rtyhbn',
    'h': 'tyujnb', 'j': 'yuihkn', 'k': 'uiojlm', 'l': 'iopk;m',
    'z': 'asx', 'x': 'zsdc', 'c': 'xdfv', 'v': 'cfgb', 'b': 'vghn',
    'n': 'bghjm', 'm': 'njk,'
}


def has_adjacent(ch: str) -> bool:
    """Return True if ``ch`` (case-insensitive) has an adjacent-key entry."""
    if not ch:
        return False
    return ch.lower() in KEY_ADJACENCY


def adjacent_key(ch: str) -> str | None:
    """Pick a random adjacent key for ``ch`` (lowercase). None if no entry."""
    if not ch:
        return None
    neighbours = KEY_ADJACENCY.get(ch.lower())
    if not neighbours:
        return None
    return random.choice(neighbours)


__all__ = ["KEY_ADJACENCY", "has_adjacent", "adjacent_key"]
