"""nexustyper.services.hotkey_listener — daemon-thread global hotkey listener.

Wraps :class:`pynput.keyboard.GlobalHotKeys` in a background daemon thread so
the rest of the app can register Qt-style hotkey strings (``"Cmd+Alt+S"``) and
zero-arg callbacks without dealing with translation, thread lifetime, or
exception handling itself.

Public API
----------
HotkeyListener(callbacks)
    callbacks maps Qt-style hotkey strings to zero-arg callables.
HotkeyListener.start()
    Spawn the listener thread (no-op if already running, warns when no
    hotkeys bind successfully).
HotkeyListener.stop(join_timeout=0.5)
    Best-effort idempotent shutdown.
HotkeyListener.is_running()
    Whether the listener thread is currently alive.

The class is deliberately Qt-free so it can be exercised in headless tests.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Dict, Mapping, Optional

from pynput import keyboard

from nexustyper.services.hotkeys import translate_hotkey_for_pynput

logger = logging.getLogger("nexustyper")


class HotkeyListener:
    """Owns a daemon thread running a :class:`pynput.keyboard.GlobalHotKeys`.

    Parameters
    ----------
    callbacks:
        Mapping from Qt-style hotkey strings (e.g. ``"Cmd+Alt+S"``) to
        zero-argument callables. Each key is translated to pynput's
        angle-bracket notation via
        :func:`nexustyper.services.hotkeys.translate_hotkey_for_pynput`.
        Keys that translate to an empty string are skipped silently. If no
        keys translate successfully, :meth:`start` logs a warning and
        returns without spawning a thread.
    """

    def __init__(self, callbacks: Mapping[str, Callable[[], None]]) -> None:
        # Defensive copy so callers can mutate their dict without surprising us.
        self._callbacks: Dict[str, Callable[[], None]] = dict(callbacks or {})
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ start
    def start(self) -> None:
        """Spawn the daemon listener thread.

        Idempotent: a no-op when the thread is already alive. When no
        callbacks translate to a valid pynput hotkey, logs a warning and
        returns without starting (to mirror the original
        ``AutoTyperApp._run_listener`` behavior).
        """
        if self._thread is not None and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------- stop
    def stop(self, join_timeout: float = 0.5) -> None:
        """Best-effort stop. Safe to call multiple times.

        Tells the underlying pynput listener to stop, then joins the daemon
        thread for at most ``join_timeout`` seconds. All errors during
        shutdown are swallowed so callers can safely call this from
        cleanup paths.
        """
        listener = self._listener
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
        self._listener = None

        thread = self._thread
        if thread is not None and thread.is_alive():
            try:
                thread.join(timeout=join_timeout)
            except Exception:
                pass
        if thread is not None and not thread.is_alive():
            self._thread = None

    # -------------------------------------------------------------- is_running
    def is_running(self) -> bool:
        """Return True iff the listener thread is currently alive."""
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    # =====================================================================
    # internals
    # =====================================================================
    def _run(self) -> None:
        """Thread target: build the pynput map and pump events.

        Mirrors the behavior of the original ``AutoTyperApp._run_listener``:
        translate every Qt-style hotkey, drop empty translations, warn and
        bail out if nothing binds, and swallow any exception thrown by the
        listener thread (logging via ``logger.exception``).
        """
        try:
            hotkeys: Dict[str, Callable[[], None]] = {}
            for qt_hotkey, callback in self._callbacks.items():
                translated = translate_hotkey_for_pynput(qt_hotkey)
                if not translated:
                    continue
                hotkeys[translated] = callback

            if not hotkeys:
                try:
                    logger.warning(
                        "Global hotkeys not started: no valid hotkey bindings"
                    )
                except Exception:
                    pass
                return

            self._listener = keyboard.GlobalHotKeys(hotkeys)
            self._listener.run()
        except Exception as exc:
            try:
                logger.exception("Hotkey listener error")
            except Exception:
                pass
            # Match the original print so terminal users still see the failure
            # even if logging is misconfigured.
            print(f"Hotkey listener error: {exc}")
