import io
import json
import logging
from pathlib import Path

from logger import StructuredLogger, JSONFormatter, ColorFormatter, TRACE_LEVEL_NUM, Logged


def test_json_formatter_emits_json_with_fields():
    logger = logging.getLogger("test.json")
    logger.setLevel(logging.DEBUG)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    logger.info("Hello", extra={"kv": {"x": 1}})
    line = stream.getvalue().strip().splitlines()[-1]
    obj = json.loads(line)
    assert obj["message"] == "Hello"
    assert obj["level"] == "INFO"
    assert obj["fields"]["x"] == 1


def test_color_formatter_plain(monkeypatch):
    fmt = ColorFormatter(colorize=False)
    logger = logging.getLogger("test.color")
    logger.setLevel(logging.INFO)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    logger.warning("Warn", extra={"kv": {"a": "b"}})
    out = stream.getvalue()
    assert "WARN" in out or "WARNING" in out
    assert "a=\"b\"" in out


def test_structured_logger_file_and_child_parent(tmp_path: Path):
    logf = tmp_path / "app.log"
    log = StructuredLogger(name="root", level="TRACE", log_file=str(logf), console=False)
    log.trace("trace message", fields={"f": 1})
    log.debug("debug message")
    log.info("info message")

    child = log.getChildLogger("child")
    child.warning("child warning")

    parent = log.getParentLogger("parent")
    parent.error("parent error")

    # ensure file exists and contains JSON lines
    text = logf.read_text(encoding="utf-8").strip()
    assert text
    last = json.loads(text.splitlines()[-1])
    assert last["level"] == "ERROR"

    # test set_level convenience
    child.set_level("INFO")
    assert child.logger.level == logging.INFO


def test_trace_level_number():
    assert TRACE_LEVEL_NUM < logging.DEBUG


def test_logged_creates_file_and_traces(tmp_path: Path):
    out = tmp_path / "logged.log"
    l = Logged("MyClass", str(out))
    # The constructor logs a trace; ensure file is created and contains content
    text = out.read_text(encoding="utf-8").strip()
    assert text
