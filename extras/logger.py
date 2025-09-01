#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Structured logging helpers with:
- Custom TRACE level (numeric 5)
- JSON and colorized console formatters
- A small wrapper (StructuredLogger) for ergonomic, typed logging with
  optional structured key/value fields.

Usage:
    log = StructuredLogger(
        name="case_briefs",
        level="TRACE",
        log_file="app.log",
        console=True,
        color=None,          # auto-detect TTY
        json_in_file=True,   # JSON lines in file
    )
    log.info("Service started", fields={"port": 8080})
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, MutableMapping, Optional, Union, Final
global log

__all__ = [
    "TRACE_LEVEL_NUM",
    "JSONFormatter",
    "ColorFormatter",
    "StructuredLogger",
]

# ----- Custom TRACE level -----
TRACE_LEVEL_NUM: Final[int] = 5
logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")


def _logger_trace(self: logging.Logger, msg: str, *args: object, **kwargs: object) -> None:
    """
    Add a `.trace()` method to `logging.Logger`.

    Parameters
    ----------
    self
        The logger instance.
    msg
        Message format string.
    *args
        Positional args passed to the underlying logger.
    **kwargs
        Keyword args passed to the underlying logger.
    """
    if self.isEnabledFor(TRACE_LEVEL_NUM):
        # _log is part of Logger's public implementation (used internally by all std methods).
        self._log(TRACE_LEVEL_NUM, msg, args, **kwargs)  # type: ignore[arg-type]


# Monkey-patch method on the Logger class
logging.Logger.trace = _logger_trace  # type: ignore[attr-defined]


# ----- Type aliases -----
LevelLike = Union[int, str]
Fields = Mapping[str, Any]


# ----- Utilities -----
def _iso_utc(ts: float) -> str:
    """
    Convert a POSIX timestamp to an ISO-8601 UTC string (Z-terminated).

    Parameters
    ----------
    ts
        POSIX timestamp (seconds since epoch).

    Returns
    -------
    str
        ISO-8601 formatted timestamp in UTC, e.g. '2025-08-28T14:03:12Z'.
    """
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_dir_for(file_path: str) -> None:
    """
    Ensure the directory for `file_path` exists.

    Parameters
    ----------
    file_path
        Target file path whose parent directory should exist.
    """
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)


def _level_from(value: LevelLike) -> int:
    """
    Normalize log level input (int or name) to an int.

    Parameters
    ----------
    value
        Either an integer logging level or a string such as 'INFO', 'DEBUG', or 'TRACE'.

    Returns
    -------
    int
        The numeric logging level. Defaults to logging.INFO for unknown names.
    """
    if isinstance(value, int):
        return value
    name = value.upper()
    if name == "TRACE":
        return TRACE_LEVEL_NUM
    if name in logging._nameToLevel:  # type: ignore[attr-defined]
        return logging._nameToLevel[name]  # type: ignore[attr-defined]
    return logging.INFO


# ----- Formatters -----
class JSONFormatter(logging.Formatter):
    """
    A logging.Formatter that emits one JSON object per log record.

    Extra fields:
        If a record carries `extra={"kv": {...}}` (or StructuredLogger `fields=...`),
        that mapping is emitted under `"fields"`.
    """

    def format(self, record: logging.LogRecord) -> str:
        obj: Dict[str, Any] = {
            "timestamp": _iso_utc(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "filename": record.filename,
            "func": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.threadName,
        }

        # Attach user-provided structured fields if present
        kv: Any = getattr(record, "kv", None)
        if isinstance(kv, dict):
            obj["fields"] = kv

        if record.exc_info:
            obj["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            # record.stack_info is a string when provided
            obj["stack"] = record.stack_info
        return json.dumps(obj, ensure_ascii=False, default=str)


class ColorFormatter(logging.Formatter):
    """
    A human-friendly, colorized console formatter.

    Colorization applies only if `colorize=True` (or auto-detected via TTY).
    Structured key/values (record.kv) are rendered as `key=value` pairs.
    """

    # ANSI codes
    RESET: Final[str] = "\x1b[0m"
    BOLD: Final[str] = "\x1b[1m"
    DIM: Final[str] = "\x1b[2m"
    COLORS: Final[Mapping[str, str]] = {
        "CRITICAL": "\x1b[97;41m",  # bright white on red background
        "ERROR": "\x1b[91m",
        "WARNING": "\x1b[93m",
        "INFO": "\x1b[92m",
        "DEBUG": "\x1b[94m",
        "TRACE": "\x1b[96m",
    }

    def __init__(self, colorize: bool = True) -> None:
        """
        Parameters
        ----------
        colorize
            Whether to apply ANSI colors. If False, plain text is emitted.
        """
        super().__init__()
        self.colorize: bool = colorize

    def format(self, record: logging.LogRecord) -> str:
        ts = _iso_utc(record.created)
        level = record.levelname
        logger_name = record.name
        message = record.getMessage()

        # Build kv string if present
        kv_str = ""
        kv: Any = getattr(record, "kv", None)
        if isinstance(kv, dict) and kv:
            parts = []
            for k, v in kv.items():
                try:
                    val = json.dumps(v, ensure_ascii=False, default=str)
                except Exception:
                    val = repr(v)
                parts.append(f"{k}={val}")
            kv_str = " " + " ".join(parts)

        base = f"{ts} {level:8s} {logger_name} - {message}{kv_str}"

        # Append exception/stack if present
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        if record.stack_info:
            base += "\n" + str(record.stack_info)

        if not self.colorize:
            return base

        # Colorize level and dim timestamp
        color = self.COLORS.get(level, "")
        ts_col = f"{self.DIM}{ts}{self.RESET}"
        lvl_col = f"{color}{level:8s}{self.RESET}"
        return f"{ts_col} {lvl_col} {logger_name} - {message}{kv_str}"


# ----- Structured Logger -----
class StructuredLogger:
    """
    A thin, typed wrapper around `logging.Logger` with:

    - Custom TRACE support (numeric level 5).
    - Easy per-message structured fields via `fields={...}`.
    - Optional colorized console handler and JSON-lines file handler.
    - Handler de-duping for safe re-instantiation.

    Notes
    -----
    The wrapper is non-invasive: it delegates to a real `logging.Logger`
    underneath, so it plays nicely with existing logging setup.

    Parameters
    ----------
    name
        Logger name (e.g., module or service name).
    level
        Logging level as int or name ('TRACE'/'DEBUG'/'INFO'/...).
    log_file
        Optional path to append logs. Directory will be created if needed.
    console
        If True, attach a StreamHandler to stdout.
    color
        Force-enable/disable colorized console output. If None, auto-detect
        based on whether stdout is a TTY.
    json_in_file
        If True, file handler writes JSON lines; otherwise simple text.
    propagate
        Whether this logger should propagate to ancestor loggers.
    """

    def __init__(
        self,
        name: str,
        level: LevelLike = "INFO",
        log_file: Optional[str] = None,
        console: bool = True,
        color: Optional[bool] = None,
        json_in_file: bool = True,
        propagate: bool = False,
    ) -> None:
        self.logger: logging.Logger = logging.getLogger(name)
        self.logger.setLevel(_level_from(level))
        self.logger.propagate = propagate

        # Avoid duplicate handlers if re-instantiated
        self._remove_our_handlers()

        if console:
            self._add_console_handler(color)

        if log_file:
            self._add_file_handler(log_file, json_in_file=json_in_file)

    # ---------------- Public API ----------------
    def set_level(self, level: LevelLike) -> None:
        """
        Set the logger and its handlers to the given level.

        Parameters
        ----------
        level
            Level as int or name (e.g., 'DEBUG', 'TRACE').
        """
        lvl = _level_from(level)
        self.logger.setLevel(lvl)
        for h in self.logger.handlers:
            h.setLevel(lvl)

    def trace(
        self,
        msg: str,
        *args: object,
        fields: Optional[Fields] = None,
        **kwargs: object,
    ) -> None:
        """Log a message at TRACE level."""
        self._log(TRACE_LEVEL_NUM, msg, *args, fields=fields, **kwargs)

    def debug(
        self,
        msg: str,
        *args: object,
        fields: Optional[Fields] = None,
        **kwargs: object,
    ) -> None:
        """Log a message at DEBUG level."""
        self._log(logging.DEBUG, msg, *args, fields=fields, **kwargs)

    def info(
        self,
        msg: str,
        *args: object,
        fields: Optional[Fields] = None,
        **kwargs: object,
    ) -> None:
        """Log a message at INFO level."""
        self._log(logging.INFO, msg, *args, fields=fields, **kwargs)

    def warning(
        self,
        msg: str,
        *args: object,
        fields: Optional[Fields] = None,
        **kwargs: object,
    ) -> None:
        """Log a message at WARNING level."""
        self._log(logging.WARNING, msg, *args, fields=fields, **kwargs)

    def error(
        self,
        msg: str,
        *args: object,
        fields: Optional[Fields] = None,
        **kwargs: object,
    ) -> None:
        """Log a message at ERROR level."""
        self._log(logging.ERROR, msg, *args, fields=fields, **kwargs)

    def critical(
        self,
        msg: str,
        *args: object,
        fields: Optional[Fields] = None,
        **kwargs: object,
    ) -> None:
        """Log a message at CRITICAL level."""
        self._log(logging.CRITICAL, msg, *args, fields=fields, **kwargs)

    # ---------------- Internal helpers ----------------
    def _log(
        self,
        level: int,
        msg: str,
        *args: object,
        fields: Optional[Fields] = None,
        **kwargs: object,
    ) -> None:
        """
        Internal helper that merges `fields` into `extra={"kv": ...}` for
        consumption by our formatters, then delegates to the underlying logger.
        """
        extra_obj: MutableMapping[str, Any]
        extra_any: Any = kwargs.pop("extra", None)
        extra_obj = dict(extra_any) if isinstance(extra_any, dict) else {}

        # Merge fields under "kv" (used by our formatters)
        kv_current: Dict[str, Any] = {}
        if isinstance(extra_obj.get("kv"), dict):
            # Copy to avoid mutating caller-provided dict
            kv_current.update(extra_obj["kv"])  # type: ignore[arg-type]
        if fields:
            kv_current.update(dict(fields))
        if kv_current:
            extra_obj["kv"] = kv_current

        self.logger.log(level, msg, *args, extra=extra_obj, **kwargs)

    def _add_console_handler(self, force_color: Optional[bool]) -> None:
        """
        Attach a stdout StreamHandler with ColorFormatter.

        Parameters
        ----------
        force_color
            If None, auto-detect based on TTY; otherwise force True/False.
        """
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setLevel(self.logger.level)
        setattr(handler, "_structured_from", "console")  # marker to avoid dupes

        # Auto-detect color if not forced
        colorize = force_color
        if colorize is None:
            stream = getattr(handler, "stream", None)
            colorize = bool(getattr(stream, "isatty", lambda: False)())

        handler.setFormatter(ColorFormatter(colorize=bool(colorize)))
        self.logger.addHandler(handler)

    def _add_file_handler(self, file_path: str, json_in_file: bool = True) -> None:
        """
        Attach a file handler to `file_path`. JSON lines by default.

        Parameters
        ----------
        file_path
            Target log file (will be created if missing).
        json_in_file
            If True, use JSONFormatter; otherwise a simple text formatter.
        """
        _ensure_dir_for(file_path)
        handler = logging.FileHandler(file_path, mode="a", encoding="utf-8", delay=True)
        handler.setLevel(self.logger.level)
        setattr(handler, "_structured_from", "file")  # marker to avoid dupes

        if json_in_file:
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s %(levelname)s %(name)s - %(message)s",
                    datefmt="%Y-%m-%dT%H:%M:%S%z",
                )
            )
        self.logger.addHandler(handler)

    def _remove_our_handlers(self) -> None:
        """
        Remove only handlers that this module previously attached
        (those marked with `._structured_from`).
        """
        to_remove: list[logging.Handler] = []
        for h in self.logger.handlers:
            if hasattr(h, "_structured_from"):
                to_remove.append(h)
        for h in to_remove:
            try:
                self.logger.removeHandler(h)
                h.close()
            except Exception:
                # Swallow to avoid interfering with caller environments.
                pass


# ----- Minimal demo -----
if __name__ == "__main__":
    log = StructuredLogger(
        name="logger",
        level="TRACE",
        log_file="app.log",
        console=True,
        color=None,  # auto
        json_in_file=True,
    )

    log.trace("Starting trace-level diagnostics", fields={"phase": "init"})
    log.debug("Debug detail", fields={"config_loaded": True})
    log.info("Service started", fields={"port": 8080})
    log.warning("Cache miss", fields={"key": "user:42"})
    try:
        print(1 / 0)
    except ZeroDivisionError:
        log.error("Computation failed", exc_info=True, fields={"operation": "division"})
    log.critical("Shutting down", fields={"reason": "fatal"})