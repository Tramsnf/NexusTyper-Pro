"""TypingWorker — runs the human-like typing loop on a QThread.

This is a near-verbatim extraction of the ``TypingWorker`` class from
``NexusTyper Pro.py``. The pyqtSignal declarations and the
``__init__(text, laps, delay, **kwargs)`` signature are byte-identical to
the original so AutoTyperApp's existing ``connect()`` / construction
callsites keep working.

Platform-specific calls (Quartz/AppKit/Win32) are routed through
``nexustyper.platform.current()`` instead of ``platform.system() == "Darwin"``
branches scattered through the worker.
"""

from __future__ import annotations

import platform as _stdlib_platform
import random
import re
import threading
import time

import pyautogui
import pyperclip
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from nexustyper.platform import current as _current_platform
from nexustyper.services.logging_setup import _log_caught, logger
from nexustyper.typing.browser import (
    auto_optimize_for_window as _auto_optimize_for_window_helper,
    is_browser_title as _is_browser_title_helper,
    looks_like_code_quick as _looks_like_code_quick_helper,
    normalize_browser_tab_prefix as _normalize_browser_tab_prefix_helper,
)
from nexustyper.typing.keyboard import kbd
from nexustyper.typing.macros import (
    MACRO_FULLMATCH_RE,
    MACRO_SPLIT_RE,
    execute_macro as _execute_macro_helper,
    strip_macros as _strip_macros_helper,
    validate_macro as _validate_macro_helper,
)
from nexustyper.typing.mistakes import KEY_ADJACENCY
from nexustyper.typing.sanitize import apply_smart_newlines, sanitize_ai_text


# Mirrors the constant in NexusTyper Pro.py — the worker reads it as a class
# default so the original behavior is preserved.
MISTAKE_CHANCE = 0.02


# Module-level Windows foreground-window helper kept here so the worker can
# fall back when ``PLATFORM.active_app_identity()`` doesn't return a stable
# HWND-flavored identity. The platform layer's ``active_app_identity`` is the
# preferred path; this is just defensive belt-and-suspenders for now.


class TypingWorker(QObject):
    paused_signal = pyqtSignal()
    resumed_signal = pyqtSignal()
    finished = pyqtSignal()
    update_status = pyqtSignal(str)
    update_speed = pyqtSignal(float)
    update_progress = pyqtSignal(int)
    set_progress_max = pyqtSignal(int)
    update_etr = pyqtSignal(str)
    lap_progress = pyqtSignal(int, int)

    def __init__(self, text, laps, delay, **kwargs):
        super().__init__()
        self._platform = _current_platform()
        self._running = True
        self._paused = False
        self.pause_event = threading.Event()
        self.pause_event.set()  # Not paused initially
        self._pause_started_at = None
        self._pause_total = 0.0
        self.text_to_type = text
        self.laps = laps
        self.delay = delay
        self.persona = kwargs.get('typing_persona')
        self.initial_window = None  # To store the target window title
        self.started_from_gui = kwargs.get('started_from_gui', False)
        self.source_app = (kwargs.get('source_app') or "").strip()

        # --- Get ALL settings directly from the UI ---
        self.newline_mode = kwargs.get('newline_mode')
        self.use_shift_enter = kwargs.get('use_shift_enter', False)
        self.type_tabs = kwargs.get('type_tabs', True)
        self.min_wpm = kwargs.get('min_wpm')
        self.max_wpm = kwargs.get('max_wpm')
        self.add_mistakes = kwargs.get('add_mistakes')
        self.pause_on_punct = kwargs.get('pause_on_punct')
        self.enable_mouse_jitter = kwargs.get('mouse_jitter')
        self.initial_window_identity = None
        self.press_esc = kwargs.get('press_esc', False)
        self.mistake_chance = MISTAKE_CHANCE
        self.thinking_pause_chance = 0.04
        self._last_ui_update = 0.0
        try:
            self._allowed_keys = set(getattr(pyautogui, "KEYBOARD_KEYS", []))
        except Exception:
            _log_caught('__init__@L101')
            self._allowed_keys = set()
        # New modes
        self.ime_friendly = kwargs.get('ime_friendly', False)
        self.unicode_hex_typing = kwargs.get('unicode_hex_typing', False)
        self.compliance_mode = kwargs.get('compliance_mode', False)
        blocked = kwargs.get('blocked_apps', "") or ""
        self.blocked_apps = [b.strip().lower() for b in blocked.split(',') if b.strip()]
        self.auto_detect = kwargs.get('auto_detect', False)
        self.enable_macros = kwargs.get('enable_macros', True)
        # Remote Desktop / virtual desktop keyboard compatibility mode:
        # 'off', 'auto', or 'on'. Auto is the safe default on Windows; other
        # OSes ignore this and always use pyautogui (their backends already
        # propagate through CRD/RDP).
        self.kbd_rdp_mode = kwargs.get(
            'kbd_rdp_mode',
            'auto' if _stdlib_platform.system() == 'Windows' else 'off',
        )
        self._resume_settle_until = 0.0
        self._esc_on_next_ready = False
        self._target_is_browser = False
        self._initial_tab_prefix = ""
        # Tracks the last live-lock state we emitted to the status bar so we
        # only emit on transitions (locked <-> lost-focus) instead of every
        # cycle.
        self._lock_state_emitted = None  # type: ignore[assignment]

    def _is_browser_title(self, title: str) -> bool:
        return _is_browser_title_helper(title)

    def _looks_like_code_quick(self, t: str) -> bool:
        return _looks_like_code_quick_helper(t)

    def _is_title_blocked(self, title: str) -> bool:
        if not self.compliance_mode:
            return False
        tl = (title or "").lower()
        return any(k in tl for k in self.blocked_apps)

    def _await_target_window(self):
        """If started from GUI, wait until focus leaves the source app before locking target."""
        if not (self.started_from_gui and self.source_app):
            return (
                self.get_active_window_title() or "Unknown",
                self.get_active_window_identity() or "Unknown",
            )

        last_hint = 0.0
        while self._running:
            cur_title = self.get_active_window_title() or "Unknown"
            cur_identity = self.get_active_window_identity() or cur_title
            if cur_identity != self.source_app:
                if self._is_title_blocked(cur_title) or self._is_title_blocked(cur_identity):
                    now = time.time()
                    if now - last_hint >= 1.0:
                        self.update_status.emit("Compliance mode: blocked app active. Focus an allowed app to start typing…")
                        last_hint = now
                else:
                    return cur_title, cur_identity
            now = time.time()
            if now - last_hint >= 1.0:
                self.update_status.emit("Focus your target app and click the input field… (typing starts when it’s active)")
                last_hint = now
            self._sleep_interruptible(0.1)
        return None, None

    def stop(self):
        self._running = False
        # Unblock any waits so the thread can exit promptly.
        self.pause_event.set()

    def pause(self, auto_resume_check=False):
        if not self._paused:
            self._paused = True
            self.pause_event.clear()
            self._pause_started_at = time.time()
            self.paused_signal.emit()
            if auto_resume_check and self.initial_window_identity:
                threading.Thread(target=self._auto_resume_checker, daemon=True).start()

    def resume(self):
        if self._paused:
            self._paused = False
            if self._pause_started_at is not None:
                try:
                    self._pause_total += max(0.0, time.time() - self._pause_started_at)
                except Exception:
                    _log_caught('resume@L187')
                    pass
                self._pause_started_at = None
            # Give the OS/app a short moment to settle focus after resume.
            try:
                self._resume_settle_until = time.time() + 0.25
            except Exception:
                _log_caught('resume@L193')
                self._resume_settle_until = 0.0
            # Dismiss autocomplete popups on resume (for IDEs) when enabled.
            if self.press_esc and not self._target_is_browser:
                self._esc_on_next_ready = True
            self.pause_event.set()
            self.resumed_signal.emit()

    def _current_pause_total(self) -> float:
        try:
            if self._pause_started_at is not None:
                return self._pause_total + max(0.0, time.time() - self._pause_started_at)
        except Exception:
            _log_caught('_current_pause_total@L205')
            pass
        return self._pause_total

    def _auto_resume_checker(self):
        """Monitors active window and resumes typing if focus returns.

        Sleeps in short slices and rechecks ``self._running`` between each
        slice so a stop signal lands within ~50 ms instead of up to a full
        second. Prevents the checker from calling ``self.resume()`` after
        the worker has already been torn down.
        """
        def _short_sleep(total: float) -> bool:
            """Sleep up to ``total`` seconds, breaking early if stopped or unpaused.
            Returns True if the loop should continue, False to exit."""
            end = time.time() + max(0.0, total)
            while time.time() < end:
                if not (self._paused and self._running):
                    return False
                time.sleep(0.05)
            return True

        if not _short_sleep(0.5):  # Prevent instant resume on quick window switches
            return
        while self._paused and self._running:
            try:
                if self._lock_matches(
                    self.get_active_window_identity(),
                    self.get_active_window_title(),
                ):
                    # Grace period to avoid missing text when focus returns.
                    for i in range(4, 0, -1):
                        if not (self._paused and self._running):
                            return
                        if not self._lock_matches(
                            self.get_active_window_identity(),
                            self.get_active_window_title(),
                        ):
                            break
                        try:
                            self.update_status.emit(f"Resuming in {i}…")
                        except Exception:
                            _log_caught('_auto_resume_checker@L246')
                            pass
                        if not _short_sleep(1.0):
                            return
                    else:
                        if self._lock_matches(
                            self.get_active_window_identity(),
                            self.get_active_window_title(),
                        ):
                            self.resume()
                            break
            except Exception:
                _log_caught('_auto_resume_checker@L257')
                pass  # Ignore errors (e.g., window closed)
            if not _short_sleep(0.2):
                return

    def get_active_window_title(self):
        # Use the platform's per-window title (changes on tab/window switch)
        # rather than active_app_identity (just the app name, identical across
        # tabs of the same app — that broke tab-switch detection on macOS).
        try:
            title = self._platform.active_window_title()
            return title or "Unknown"
        except Exception:
            _log_caught('get_active_window_title@L267')
            return "Unknown"

    def get_active_window_identity(self):
        # Platform layer returns the most stable identifier available
        # (HWND-based on Windows, app name on macOS, title elsewhere).
        try:
            return self._platform.active_app_identity() or self.get_active_window_title()
        except Exception:
            _log_caught('get_active_window_identity@L275')
            return self.get_active_window_title()

    def _lock_matches(self, identity, title) -> bool:
        """True when the current foreground matches the locked target.

        Combines the HWND/app identity (resilient to title mutations) with a
        browser-tab title prefix check so that switching Chrome tabs (which
        keeps the same HWND on Windows) still trips the lock.
        """
        if not self.initial_window_identity:
            return True
        if (identity or "") != self.initial_window_identity:
            return False
        if self._target_is_browser and self._initial_tab_prefix:
            cur_prefix = _normalize_browser_tab_prefix_helper(title or "")
            if cur_prefix and cur_prefix != self._initial_tab_prefix:
                return False
        return True

    def _emit_lock_state(self, locked: bool, current_title: str = "") -> None:
        """Push a live status update when the lock state changes.

        The original ``Typing locked on: ...`` message is emitted once at
        start and never refreshed, which made it impossible to tell from the
        status bar whether keys were actually reaching the target. We emit
        on transitions: a green "Typing into" message when focus is held and
        a "Lost focus" warning when it isn't.
        """
        try:
            if self._lock_state_emitted == locked:
                return
            self._lock_state_emitted = locked
            if locked:
                self.update_status.emit(f"Typing into: {self.initial_window}")
            else:
                cur = (current_title or "").strip() or "another window"
                self.update_status.emit(
                    f"Lost focus on '{self.initial_window}' (now: {cur}) — paused"
                )
        except Exception:
            _log_caught('_emit_lock_state@L315')
            pass

    def update_speed_range(self, min_wpm, max_wpm):
        self.min_wpm = min_wpm
        self.max_wpm = max_wpm

    def execute_macro(self, command, params):
        try:
            _execute_macro_helper(
                command,
                params,
                sleep_fn=self._sleep_interruptible,
            )
        except Exception as e:
            error_message = f"Macro execution failed: {e}"
            if self._platform.name == "macos" and (
                "Accessibility" in str(e) or "Input Monitoring" in str(e)
            ):
                error_message += "\n\n(Likely macOS permissions issue)"
            self.update_status.emit(error_message)

    def validate_macro(self, command, params):
        try:
            screen_size = pyautogui.size()
        except Exception:
            _log_caught('validate_macro@L340')
            screen_size = None
        return _validate_macro_helper(
            command,
            params,
            allowed_keys=self._allowed_keys,
            screen_size=screen_size,
        )

    def _strip_macros(self, text: str) -> str:
        if not self.enable_macros:
            return text
        return _strip_macros_helper(text)

    def _compute_total_chars_per_lap(self, text_content: str) -> int:
        if not text_content:
            return 0
        mode = self.newline_mode or 'Standard'
        if mode == 'Paste Mode':
            # Paste Mode outputs the text minus macros; tabs are preserved.
            return len(self._strip_macros(text_content))
        if mode == 'List Mode':
            # List Mode: strip leading whitespace per line, do not preserve tab characters,
            # execute macros (so they're not output), and always send an Enter after each line.
            lines = text_content.splitlines()
            total = 0
            for line in lines:
                stripped = line.lstrip(' \t')
                if not self.type_tabs:
                    stripped = stripped.replace('\t', '')
                stripped = self._strip_macros(stripped)
                total += len(stripped)
            total += len(lines)  # Enter after each line
            return total
        # Standard/Smart modes: remove macros; optionally skip tabs.
        processed = apply_smart_newlines(text_content) if mode == 'Smart Newlines' else text_content
        processed = self._strip_macros(processed)
        if not self.type_tabs:
            processed = processed.replace('\t', '')
        return len(processed)

    def _elapsed_active(self, overall_start_time: float) -> float:
        try:
            return max(0.0, (time.time() - overall_start_time) - self._current_pause_total())
        except Exception:
            _log_caught('_elapsed_active@L384')
            return max(0.0, time.time() - overall_start_time)

    def _maybe_emit_progress(self, overall_start_time: float, chars_completed: int, total_chars_overall: int):
        now = time.time()
        if (now - self._last_ui_update) < 0.05 and chars_completed < total_chars_overall:
            return
        self.update_progress.emit(chars_completed)
        elapsed = self._elapsed_active(overall_start_time)
        if elapsed > 0 and chars_completed > 0:
            cpm = (chars_completed / elapsed) * 60
            self.update_speed.emit(cpm / 5)
            if total_chars_overall > 0 and cpm > 0:
                etr_seconds = ((total_chars_overall - chars_completed) / cpm) * 60
                self.update_etr.emit(f"ETR: {time.strftime('%M:%S', time.gmtime(max(0.0, etr_seconds)))}")
        self._last_ui_update = now

    def _wait_until_ready(self) -> bool:
        """Blocks while paused or while guardrails require auto-pausing."""
        while self._running:
            # Honor explicit pauses first.
            self.pause_event.wait()
            if not self._running:
                return False

            title = self.get_active_window_title() or ""
            identity = self.get_active_window_identity() or title

            # Compliance guardrail
            if self.compliance_mode:
                tl = title.lower()
                il = identity.lower()
                if any(k in tl or k in il for k in self.blocked_apps):
                    if not self._paused:
                        self.update_status.emit("Compliance mode: blocked app active. Pausing...")
                        self.pause(auto_resume_check=True)
                    continue

            # Focus lock guardrail (HWND identity + browser tab-prefix).
            if self.initial_window_identity and not self._lock_matches(identity, title):
                self._emit_lock_state(False, title)
                if not self._paused:
                    self.pause(auto_resume_check=True)
                continue
            # Focus is held — refresh the live status if it just returned.
            self._emit_lock_state(True, title)

            # Post-resume settle delay (prevents dropped keystrokes in some apps).
            try:
                if self._resume_settle_until and time.time() < self._resume_settle_until:
                    self._sleep_interruptible(max(0.0, self._resume_settle_until - time.time()))
                self._resume_settle_until = 0.0
            except Exception:
                _log_caught('_wait_until_ready@L436')
                self._resume_settle_until = 0.0

            # Optional: close autocomplete popups once after resuming.
            if getattr(self, "_esc_on_next_ready", False):
                if not self._target_is_browser:
                    try:
                        kbd.press('esc')
                        self._sleep_interruptible(0.05)
                    except Exception:
                        _log_caught('_wait_until_ready@L445')
                        pass
                self._esc_on_next_ready = False

            return True
        return False

    def _sleep_interruptible(self, duration):
        """Sleep in small chunks while honoring stop/pause.

        Tracks remaining time *as duration*, not as an absolute deadline,
        so a long pause doesn't make the function return immediately on
        resume (which would drop the inter-keystroke delay).
        """
        remaining = max(0.0, duration)
        last_tick = time.time()
        while self._running and remaining > 0:
            if not self.pause_event.is_set():
                # Block during pauses without busy-waiting; don't bill the
                # paused interval against the remaining budget.
                self.pause_event.wait(timeout=0.1)
                last_tick = time.time()
                continue
            slice_ = min(0.02, remaining)
            time.sleep(max(0.0, slice_))
            remaining -= time.time() - last_tick
            last_tick = time.time()

    def _mouse_jitter_thread(self):
        # Moves mouse slightly at random intervals to simulate activity
        # Respect PyAutoGUI fail-safe (corners) and stop jitter if triggered.
        try:
            screen_w, screen_h = pyautogui.size()
        except Exception:
            _log_caught('_mouse_jitter_thread@L478')
            screen_w, screen_h = None, None
        corner_guard = 2  # pixels from the edges considered fail-safe zone

        while self._running and self.enable_mouse_jitter:
            try:
                try:
                    x, y = pyautogui.position()
                except Exception:
                    _log_caught('_mouse_jitter_thread@L486')
                    x = y = None
                # If cursor is in a fail-safe corner/edge, stop jitter immediately
                if screen_w and screen_h and x is not None and y is not None:
                    if (x <= corner_guard or y <= corner_guard or
                        x >= screen_w - 1 - corner_guard or y >= screen_h - 1 - corner_guard):
                        try:
                            self.update_status.emit("Mouse jitter stopped: cursor at screen edge (fail-safe zone).")
                        except Exception:
                            _log_caught('_mouse_jitter_thread@L494')
                            pass
                        break

                # Small relative move
                pyautogui.move(random.randint(-1, 1), random.randint(-1, 1), duration=0.1)
            except Exception as e:
                # Stop on PyAutoGUI fail-safe without crashing the app
                if e.__class__.__name__ == 'FailSafeException':
                    try:
                        self.update_status.emit("Mouse jitter stopped due to PyAutoGUI fail-safe.")
                    except Exception:
                        _log_caught('_mouse_jitter_thread@L505')
                        pass
                    break
                # For any other transient error, back off briefly and continue
                time.sleep(0.3)
            time.sleep(random.uniform(0.5, 3))

    def _paste_text(self, text):
        original_clip = None
        try:
            original_clip = pyperclip.paste()
        except Exception:
            _log_caught('_paste_text@L516')
            original_clip = None
        try:
            pyperclip.copy(text)
            # Route the paste shortcut through the keyboard shim so it
            # propagates through Chrome Remote Desktop / RDP / AnyDesk in
            # RDP-compat mode. macOS uses Cmd+V, everything else Ctrl+V.
            modifier = 'command' if self._platform.name == 'macos' else 'ctrl'
            kbd.hotkey(modifier, 'v')
            return True
        except Exception as e:
            # Fallback: type the text if paste/hotkey fails.
            try:
                kbd.typewrite(text, interval=0.002)
                try:
                    self.update_status.emit("Paste failed; fell back to typing.")
                except Exception:
                    _log_caught('_paste_text@L532')
                    pass
                return True
            except Exception:
                try:
                    self.update_status.emit(f"Paste/Type failed: {e}")
                except Exception:
                    _log_caught('_paste_text@L538')
                    pass
                return False
        finally:
            if original_clip is not None:
                try:
                    pyperclip.copy(original_clip)
                except Exception:
                    _log_caught('_paste_text@L545')
                    pass

    def _type_unicode_char_macos(self, ch: str):
        """Types a single Unicode character via the platform layer.

        On macOS this routes through Unicode Hex Input (Option+Hex) — the user
        must enable that input source in System Settings. Other OSes return
        False and we fall back to the ASCII transliteration table.
        """
        if not self._platform.type_unicode_char(ch):
            self._type_with_ascii_fallback(ch)

    def _type_with_ascii_fallback(self, ch: str):
        mapping = {
            '∀': 'for all', '∃': 'exists', '∑': 'sum', '∫': 'int', '√': 'sqrt', '∞': 'infty',
            '≤': '<=', '≥': '>=', '≠': '!=', '≈': '~=', '→': '->', '←': '<-', '↔': '<->', '·': '*',
            '×': '*', '÷': '/', '∈': ' in ', '∉': ' notin ', '⊂': ' subset ', '⊆': ' subseteq ', '∪': ' U ', '∩': ' n ',
            'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta', 'ε': 'epsilon', 'θ': 'theta', 'λ': 'lambda', 'µ': 'mu',
            'π': 'pi', 'σ': 'sigma', 'ω': 'omega', 'ℝ': 'R', '′': "'", '″': '"'
        }
        out = mapping.get(ch, '?')
        kbd.typewrite(out, interval=0.002)

    _SHIFTED_US_SYMBOLS = {
        '!': '1',
        '@': '2',
        '#': '3',
        '$': '4',
        '%': '5',
        '^': '6',
        '&': '7',
        '*': '8',
        '(': '9',
        ')': '0',
        '_': '-',
        '+': '=',
        '{': '[',
        '}': ']',
        '|': '\\',
        ':': ';',
        '"': "'",
        '<': ',',
        '>': '.',
        '?': '/',
        '~': '`',
    }
    _AUTOCOMPLETE_GUARD_CHARS = set("()[]{}.,;:=#\"'")

    def _dismiss_autocomplete_popup(self, strong: bool = True):
        """Best-effort: close editor autocomplete/popups.

        Use `strong=True` before Enter/newlines; `strong=False` mid-line.
        """
        if not self.press_esc or self._target_is_browser:
            return
        presses = 2 if strong else 1
        delay = 0.06 if strong else 0.02
        # Many editors need a tiny delay after Esc so the next key doesn't accept a suggestion.
        for _ in range(presses):
            try:
                kbd.press('esc')
            except Exception:
                _log_caught('_dismiss_autocomplete_popup@L607')
                break
            self._sleep_interruptible(delay)

    def _indent_level_for_list_mode(self, line: str) -> int:
        """Return indentation level (approx, 4 spaces per level) for List Mode."""
        try:
            tab_count = 0
            space_count = 0
            for ch in (line or ""):
                if ch == '\t':
                    tab_count += 1
                    continue
                if ch == ' ':
                    space_count += 1
                    continue
                break
            return max(0, (tab_count * 4 + space_count) // 4)
        except Exception:
            _log_caught('_indent_level_for_list_mode@L625')
            return 0

    def _release_modifiers_best_effort(self):
        # Clear any "stuck" modifiers which can cause shifted symbols to mis-type.
        # Routed through the keyboard shim so it works in RDP-compat mode too;
        # the platform layer's release path uses pyautogui directly and would
        # not propagate through Chrome Remote Desktop / RDP.
        for key in ("shift", "ctrl", "alt", "command", "cmd", "option"):
            try:
                kbd.keyUp(key)
            except Exception:
                _log_caught('_release_modifiers_best_effort@L636')
                pass

    def _type_shifted_symbol_us(self, ch: str) -> bool:
        """Type a shifted symbol via explicit public keyDown/keyUp calls so
        pyautogui.PAUSE fires between each event. kbd.hotkey() skips
        PAUSE between its inner keyDowns, which races shift and produces
        ")"->"0", "@"->"2", etc. at high speed."""
        base = self._SHIFTED_US_SYMBOLS.get(ch)
        if not base:
            return False
        return self._press_with_shift(base)

    def _type_shifted_letter(self, ch: str) -> bool:
        """Uppercase A-Z via explicit keyDown/keyUp. kbd.typewrite()
        internally fires shift-down/key-down/key-up/shift-up with no PAUSE
        between events, which races at high speed and produces "MAGI"->"mAGI"
        or shift-stuck corruption like "Google"->"GOOGLE"."""
        return self._press_with_shift(ch.lower())

    def _press_with_shift(self, base: str) -> bool:
        """Public keyDown/keyUp so pyautogui.PAUSE applies between each step.
        No manual sleeps, no _release_modifiers_best_effort — those caused
        state desync with macOS Quartz flag tracking."""
        try:
            kbd.keyDown("shift")
            kbd.keyDown(base)
            kbd.keyUp(base)
            kbd.keyUp("shift")
            return True
        except Exception:
            _log_caught('_press_with_shift@L666')
            try:
                kbd.keyUp("shift")
            except Exception:
                _log_caught('_press_with_shift@L669')
                pass
            return False

    def _maybe_dismiss_autocomplete_before_char(self, ch: str, prev_char: str):
        if not self.press_esc or self._target_is_browser:
            return
        if not ch:
            return
        # Tab is especially risky in VS Code (can accept suggestions).
        if ch == '\t':
            self._dismiss_autocomplete_popup(strong=False)
            return
        # If we're mid-identifier, punctuation can "commit" a suggestion in editors like VS Code.
        if prev_char and (prev_char.isalnum() or prev_char == '_') and ch in self._AUTOCOMPLETE_GUARD_CHARS:
            self._dismiss_autocomplete_popup(strong=False)

    def _type_character(self, ch: str) -> bool:
        """Type a single character with extra guardrails for code editors."""
        if ch == '\t':
            try:
                kbd.press("tab")
                return True
            except Exception:
                _log_caught('_type_character@L692')
                try:
                    kbd.typewrite('\t', interval=0.0)
                    return True
                except Exception:
                    _log_caught('_type_character@L696')
                    return False
        if ch in self._SHIFTED_US_SYMBOLS:
            return self._type_shifted_symbol_us(ch)
        # Route uppercase A-Z through explicit shift handling too; typewrite
        # races shift internally the same way hotkey does.
        if len(ch) == 1 and ch.isascii() and ch.isalpha() and ch.isupper():
            return self._type_shifted_letter(ch)
        try:
            kbd.typewrite(ch, interval=0.0)
            return True
        except Exception:
            _log_caught('_type_character@L707')
            return False

    def _type_segment(self, segment, overall_start_time, chars_completed, total_chars_overall):
        # Types a segment of text with human-like behavior, preserving code formatting
        prev_char = ''
        for char in segment:
            if char == '\t' and not self.type_tabs:
                continue  # Skip this character and go to the next one

            if not self._wait_until_ready():
                return chars_completed, False

            # At high speeds the backspace-and-retype sequence can race the
            # next keystroke and corrupt output, so suppress artificial
            # mistakes when the target WPM is fast. The checkbox still governs
            # slower, human-like ranges.
            if (self.add_mistakes
                    and self.max_wpm < 220
                    and random.random() < self.mistake_chance):
                if char.lower() in KEY_ADJACENCY:
                    kbd.typewrite(random.choice(KEY_ADJACENCY[char.lower()]))
                    self._sleep_interruptible(random.uniform(0.1, 0.25))
                    kbd.press('backspace')
                    self._sleep_interruptible(random.uniform(0.05, 0.15))

            if char == '\n':
                self._dismiss_autocomplete_popup()
                if self.use_shift_enter:
                    kbd.hotkey('shift', 'enter')
                else:
                    kbd.press('enter')
            else:
                # Type non-ASCII via macOS Unicode Hex Input if enabled
                if self.unicode_hex_typing and ord(char) > 0x7F:
                    if self._platform.name == 'macos':
                        self._type_unicode_char_macos(char)
                    else:
                        self._type_with_ascii_fallback(char)
                else:
                    self._maybe_dismiss_autocomplete_before_char(char, prev_char)
                    if not self._type_character(char):
                        kbd.typewrite(char, interval=0.01)

            chars_completed += 1
            self._maybe_emit_progress(overall_start_time, chars_completed, total_chars_overall)

            # Smooth human-like delay: bias to mid-range via beta, extra thinking pauses
            min_d = 60 / (self.max_wpm * 5)
            max_d = 60 / (self.min_wpm * 5)
            sf = random.betavariate(2.5, 2.5)
            delay = min_d + sf * (max_d - min_d)
            if self.pause_on_punct:
                if char in '.,?!':
                    delay += random.uniform(0.08, 0.15)
                elif char in '()[]{}':
                    delay += random.uniform(0.1, 0.3)
            # Occasional cognitive pause at word boundaries
            if prev_char and prev_char in ' \t' and random.random() < self.thinking_pause_chance:
                delay += random.uniform(0.12, 0.35)
            self._sleep_interruptible(max(0.01, delay))
            prev_char = char

        return chars_completed, True

    @pyqtSlot()
    def run(self):
        try:
            # A small global cushion between every pyautogui call. PAUSE=0 races
            # shift-up vs next-char-down on macOS, causing stuck shift state
            # ("Google"->"GOOGLE", ")"->"0"). 5ms is invisible to humans but
            # gives Quartz time to process modifier transitions in order.
            pyautogui.PAUSE = 0.005
            # Tell the keyboard shim which backend to use for this run.
            kbd.set_mode(self.kbd_rdp_mode)
            if self.enable_mouse_jitter:
                threading.Thread(target=self._mouse_jitter_thread, daemon=True).start()

            text_content = self.text_to_type or ""
            # Strip HTML entities, invisible/bidi chars, exotic spaces, and
            # normalize smart punctuation before a single keystroke goes out.
            text_content = sanitize_ai_text(text_content)

            if not text_content:
                self.finished.emit()
                return

            for i in range(self.delay, 0, -1):
                if not self._running:
                    self.finished.emit()
                    return
                if self.started_from_gui:
                    self.update_status.emit(f"Starting in {i}… switch to your target app")
                else:
                    self.update_status.emit(f"Starting in {i}...")
                self._sleep_interruptible(1)

            target, target_identity = self._await_target_window()
            if not target or not target_identity:
                self.finished.emit()
                return
            self.initial_window = target
            self.initial_window_identity = target_identity
            self._target_is_browser = self._is_browser_title(self.initial_window)
            self._initial_tab_prefix = (
                _normalize_browser_tab_prefix_helper(self.initial_window)
                if self._target_is_browser else ""
            )
            self._lock_state_emitted = True  # Already on-target; suppress duplicate emit.
            self._release_modifiers_best_effort()
            self.update_status.emit(f"Typing locked on: {self.initial_window}")
            if self.auto_detect:
                self._auto_optimize_for_window(self.initial_window)
            overall_start_time = time.time()

            total_per_lap = self._compute_total_chars_per_lap(text_content)
            total_chars_overall = max(1, total_per_lap * max(1, self.laps))
            try:
                self.set_progress_max.emit(total_chars_overall)
            except Exception:
                _log_caught('run@L826')
                pass
            try:
                self.update_progress.emit(0)
            except Exception:
                _log_caught('run@L830')
                pass

            macro_split_re = MACRO_SPLIT_RE.pattern

            def split_segments(s: str):
                # Allow toggling macros on/off while paused (runtime updates).
                if self.enable_macros:
                    return re.split(macro_split_re, s)
                return [s]

            chars_completed = 0
            for lap in range(1, self.laps + 1):
                if not self._running:
                    break
                self.lap_progress.emit(lap, self.laps)

                mode = self.newline_mode or 'Standard'

                if mode == 'Paste Mode':
                    # Paste text fast, but still honor macros and guardrails.
                    segments = split_segments(text_content)
                    for segment in segments:
                        if not self._running:
                            break
                        match = MACRO_FULLMATCH_RE.fullmatch(segment) if self.enable_macros else None
                        if self.enable_macros and match:
                            ok, msg, normalized = self.validate_macro(match.group(1), match.group(2))
                            if ok and normalized:
                                cmd = normalized[0]
                                if cmd != 'PAUSE' and not self._wait_until_ready():
                                    break
                                self.execute_macro(*normalized)
                            else:
                                self.update_status.emit(f"Macro ignored: {msg}")
                            continue
                        if not segment:
                            continue
                        for line in segment.splitlines(keepends=True):
                            if not self._running:
                                break
                            if not self._wait_until_ready():
                                break
                            self._paste_text(line)
                            chars_completed += len(line)
                            self._maybe_emit_progress(overall_start_time, chars_completed, total_chars_overall)
                            self._sleep_interruptible(random.uniform(0.05, 0.15))
                    continue

                if mode == 'List Mode':
                    # List Mode: strip leading indentation and always send Enter per line.
                    # Tabs are intentionally not preserved in this mode.
                    lines = text_content.splitlines()
                    virtual_level = 0
                    for line in lines:
                        if not self._running:
                            break
                        desired_level = self._indent_level_for_list_mode(line)
                        # If the next line should be dedented relative to the editor's current level,
                        # outdent before typing to avoid "except/else" being stuck inside a block.
                        if desired_level < virtual_level:
                            steps = max(0, virtual_level - desired_level)
                            for _ in range(steps):
                                if not self._wait_until_ready():
                                    break
                                try:
                                    kbd.hotkey('shift', 'tab')
                                except Exception:
                                    # Fallback: explicit down/up so a hotkey
                                    # incompatibility doesn't kill the dedent.
                                    # try/finally guarantees shift is released
                                    # even if press('tab') raises mid-flight,
                                    # which otherwise leaves shift latched and
                                    # corrupts every subsequent keystroke.
                                    _log_caught('run@L897')
                                    try:
                                        kbd.keyDown('shift')
                                        try:
                                            kbd.press('tab')
                                        finally:
                                            kbd.keyUp('shift')
                                    except Exception:
                                        _log_caught('run@L910')
                                        break
                                self._sleep_interruptible(0.03)
                            virtual_level = desired_level

                        stripped = line.lstrip(' \t')
                        if not self.type_tabs:
                            stripped = stripped.replace('\t', '')
                        line_segments = split_segments(stripped)
                        for segment in line_segments:
                            if not self._running:
                                break
                            match = MACRO_FULLMATCH_RE.fullmatch(segment) if self.enable_macros else None
                            if self.enable_macros and match:
                                ok, msg, normalized = self.validate_macro(match.group(1), match.group(2))
                                if ok and normalized:
                                    cmd = normalized[0]
                                    if cmd != 'PAUSE' and not self._wait_until_ready():
                                        break
                                    self.execute_macro(*normalized)
                                else:
                                    self.update_status.emit(f"Macro ignored: {msg}")
                                continue
                            if not segment:
                                continue

                            should_paste = False
                            if self.ime_friendly and not self.unicode_hex_typing:
                                # In List Mode (code editors), prefer per-key typing unless non-ASCII
                                # would fail without IME/Unicode support.
                                try:
                                    should_paste = any(ord(ch) > 0x7F for ch in segment)
                                except Exception:
                                    _log_caught('run@L942')
                                    should_paste = False

                            if should_paste:
                                if not self._wait_until_ready():
                                    break
                                self._paste_text(segment)
                                chars_completed += len(segment)
                                self._maybe_emit_progress(overall_start_time, chars_completed, total_chars_overall)
                                self._sleep_interruptible(random.uniform(0.02, 0.06))
                            else:
                                chars_completed, still_running = self._type_segment(
                                    segment, overall_start_time, chars_completed, total_chars_overall)
                                if not still_running:
                                    break

                        if not self._running:
                            break
                        if not self._wait_until_ready():
                            break
                        self._dismiss_autocomplete_popup()
                        if self.use_shift_enter:
                            kbd.hotkey('shift', 'enter')
                        else:
                            kbd.press('enter')
                        chars_completed += 1
                        self._maybe_emit_progress(overall_start_time, chars_completed, total_chars_overall)
                        self._sleep_interruptible(0.1)
                        # Approximate next-line indentation level (common in code editors):
                        # after block starters like ':' or '{', indentation increases.
                        try:
                            s = (stripped or "").rstrip()
                        except Exception:
                            _log_caught('run@L974')
                            s = ""
                        if s.endswith(':') or s.endswith('{'):
                            virtual_level = desired_level + 1
                        else:
                            virtual_level = desired_level
                else:
                    processed_text = apply_smart_newlines(text_content) if mode == 'Smart Newlines' else text_content
                    segments = split_segments(processed_text)
                    for segment in segments:
                        if not self._running:
                            break
                        match = MACRO_FULLMATCH_RE.fullmatch(segment) if self.enable_macros else None
                        if self.enable_macros and match:
                            ok, msg, normalized = self.validate_macro(match.group(1), match.group(2))
                            if ok and normalized:
                                cmd = normalized[0]
                                if cmd != 'PAUSE' and not self._wait_until_ready():
                                    break
                                self.execute_macro(*normalized)
                            else:
                                self.update_status.emit(f"Macro ignored: {msg}")
                            continue
                        if not segment:
                            continue

                        if self.ime_friendly and not self.unicode_hex_typing:
                            if not self.type_tabs:
                                segment = segment.replace('\t', '')
                            if not segment:
                                continue
                            if not self._wait_until_ready():
                                break
                            self._paste_text(segment)
                            chars_completed += len(segment)
                            self._maybe_emit_progress(overall_start_time, chars_completed, total_chars_overall)
                            self._sleep_interruptible(random.uniform(0.02, 0.06))
                        else:
                            chars_completed, still_running = self._type_segment(
                                segment, overall_start_time, chars_completed, total_chars_overall)
                            if not still_running:
                                break

                if not self._running:
                    break
                self._sleep_interruptible(0.5)

            if self._running:
                # Ensure the progress bar reaches 100% for edge cases (e.g., macros-only runs).
                try:
                    self.update_progress.emit(total_chars_overall)
                except Exception:
                    _log_caught('run@L1025')
                    pass
                self.update_status.emit("Typing completed successfully!")
            else:
                self.update_status.emit("Typing stopped by user.")
        except Exception as e:
            error_message = f"Typing Error: {e}"
            if self._platform.name == "macos" and (
                "Accessibility" in str(e)
                or "Input Monitoring" in str(e)
                or "access for assistive devices" in str(e)
            ):
                error_message += "\n\nThis often means macOS security permissions (Accessibility/Input Monitoring) are not granted. Please check System Settings > Privacy & Security."
            self.update_status.emit(error_message)
            try:
                logger.exception("Typing worker crashed")
            except Exception:
                _log_caught('run@L1041')
                pass
        finally:
            self.finished.emit()

    def _auto_optimize_for_window(self, title):
        overrides = _auto_optimize_for_window_helper(
            title,
            text_to_type=self.text_to_type or "",
            current_newline_mode=self.newline_mode or "Standard",
        )
        chosen = overrides.get("chosen")
        if not chosen:
            return
        # Apply the bundle on the worker (only the keys present in overrides).
        if "press_esc" in overrides:
            self.press_esc = bool(overrides["press_esc"])
        if "use_shift_enter" in overrides:
            self.use_shift_enter = bool(overrides["use_shift_enter"])
        if "type_tabs" in overrides:
            self.type_tabs = bool(overrides["type_tabs"])
        if "add_mistakes" in overrides:
            self.add_mistakes = bool(overrides["add_mistakes"])
        if "pause_on_punct" in overrides:
            self.pause_on_punct = bool(overrides["pause_on_punct"])
        if "newline_mode" in overrides:
            self.newline_mode = overrides["newline_mode"]
        try:
            self.update_status.emit(
                f"Auto-optimized for {chosen}: mode={self.newline_mode}"
            )
        except Exception:
            _log_caught('_auto_optimize_for_window@L1072')
            pass


__all__ = ["TypingWorker", "MISTAKE_CHANCE"]

