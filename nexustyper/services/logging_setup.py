"""Centralized logging setup, exception capture, and the ``_log_caught`` helper.

The logger is intentionally created at import time so any module that just
does ``from nexustyper.services.logging_setup import logger`` gets a fully
configured logger without having to call an init function.

Three things are wired up here that didn't exist before:

* A stderr ``StreamHandler`` mirrors WARNING+ records to the terminal so
  operators see real failures live, in addition to the rotating file log.
* :func:`install_global_handlers` installs ``sys.excepthook``,
  ``threading.excepthook`` (3.8+), and a Qt message handler so uncaught
  exceptions in any thread, signal slot, or Qt internals end up in the log
  file with a traceback instead of vanishing.
* :func:`_log_caught` is a tiny helper meant to be called at the top of an
  ``except`` block. It reads ``sys.exc_info()`` so you don't have to add
  ``as e`` to existing handlers, and it never raises — a logging failure
  must not turn into a second exception inside the failing path.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler


def _resolve_log_dir() -> str:
    """Return a writable directory for the rotating log file.

    Prefers ``~/.nexustyper_pro/logs``; falls back to the system temp dir if
    the home directory isn't writable (e.g., a sandboxed install path).
    """
    primary = os.path.join(os.path.expanduser("~"), ".nexustyper_pro", "logs")
    try:
        os.makedirs(primary, exist_ok=True)
        return primary
    except Exception:
        import tempfile
        fallback = os.path.join(tempfile.gettempdir(), "nexustyper_pro_logs")
        try:
            os.makedirs(fallback, exist_ok=True)
        except Exception:
            pass
        return fallback


LOG_DIR = _resolve_log_dir()
LOG_FILE = os.path.join(LOG_DIR, "app.log")

logger = logging.getLogger("nexustyper")

if not logger.handlers:
    # DEBUG so caught-and-swallowed exceptions are recorded; the rotating
    # file caps disk usage. A second handler mirrors WARNING+ to stderr so
    # operators see real problems live.
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    _file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1024 * 1024, backupCount=5
    )
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(_file_handler)

    _stderr_handler = logging.StreamHandler()
    _stderr_handler.setLevel(logging.WARNING)
    _stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(_stderr_handler)


def _log_caught(label: str = "", level: str = "debug") -> None:
    """Log the exception currently being handled.

    Designed to live at the top of an ``except`` block so silent failures
    still leave a breadcrumb in the log file. Reads the live exception via
    ``sys.exc_info()`` so it does not require ``as e`` on the except clause.
    No-ops when called outside an active exception. Never raises — a
    logging failure must not become a second exception in the failing path.
    """
    try:
        _exc_type, _exc, _tb = sys.exc_info()
        if _exc is None:
            return
        msg = (
            f"caught at {label}: {type(_exc).__name__}: {_exc}"
            if label
            else f"caught: {type(_exc).__name__}: {_exc}"
        )
        if level == "info":
            logger.info(msg)
        elif level == "warning":
            logger.warning(msg)
        elif level == "error":
            logger.error(msg, exc_info=True)
        elif level == "exception":
            logger.exception(msg)
        else:
            logger.debug(msg)
    except Exception:
        pass


def install_global_handlers() -> None:
    """Install global exception hooks so nothing escapes the log.

    Idempotent: safe to call more than once. Wraps each hook in a try/except
    so the original behavior (printing to stderr / re-raising) still happens
    even if logging itself fails.
    """
    _install_excepthook()
    _install_threading_excepthook()
    _install_qt_message_handler()


def _install_excepthook() -> None:
    _prev = sys.excepthook

    def _hook(exc_type, exc, tb):
        try:
            logger.error(
                "UNCAUGHT %s: %s",
                exc_type.__name__,
                exc,
                exc_info=(exc_type, exc, tb),
            )
        except Exception:
            pass
        try:
            _prev(exc_type, exc, tb)
        except Exception:
            pass

    sys.excepthook = _hook


def _install_threading_excepthook() -> None:
    if not hasattr(threading, "excepthook"):
        return  # Python < 3.8

    def _thread_hook(args):
        try:
            logger.error(
                "UNCAUGHT thread %s in %r: %s",
                args.exc_type.__name__,
                args.thread,
                args.exc_value,
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
        except Exception:
            pass

    threading.excepthook = _thread_hook


def _install_qt_message_handler() -> None:
    """Mirror Qt's own warnings/errors into the same log file.

    Imported lazily so this module can be loaded in non-Qt contexts (e.g.
    unit tests, the CI smoke-test parser) without pulling in PyQt5.
    """
    try:
        from PyQt5.QtCore import QtMsgType, qInstallMessageHandler
    except Exception:
        return

    _qt_levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def _qt_handler(mode, context, message):
        try:
            level = _qt_levels.get(mode, logging.INFO)
            where = ""
            try:
                if context and context.file:
                    where = f" ({context.file}:{context.line})"
            except Exception:
                pass
            logger.log(level, "Qt: %s%s", message, where)
        except Exception:
            pass

    try:
        qInstallMessageHandler(_qt_handler)
    except Exception:
        pass


__all__ = [
    "logger",
    "LOG_DIR",
    "LOG_FILE",
    "_log_caught",
    "install_global_handlers",
]
