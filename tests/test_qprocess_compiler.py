from pathlib import Path

import pytest

from logger import StructuredLogger

pytest.importorskip("PyQt6")

import QProcessTeXCompiler as mod


class FakeQProcessSuccess:
    class ExitStatus:
        NormalExit = 0

    def __init__(self):
        self._wd = None
        self._prog = None
        self._args = []
        self._finished = True
        self._exit_status = 0
        self._exit_code = 0

    def setWorkingDirectory(self, d: str):
        self._wd = Path(d)

    def setProgram(self, p: str):
        self._prog = p

    def setArguments(self, args: list[str]):
        self._args = args

    def start(self):
        # emulate writing a PDF in the outdir based on args
        out_arg = next((a for a in self._args if a.startswith("--output-dir=")), None)
        tex_rel = next((a for a in self._args if a.endswith(".tex")), None)
        assert out_arg and tex_rel and self._wd
        out_rel = out_arg.split("=", 1)[1]
        out_dir = self._wd / out_rel
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf = Path(tex_rel).with_suffix(".pdf").name
        (out_dir / pdf).write_bytes(b"%PDF-1.4\n")

    def waitForFinished(self, msecs: int) -> bool:
        return self._finished

    def exitStatus(self):
        return self.ExitStatus.NormalExit if self._exit_status == 0 else 1

    def exitCode(self):
        return self._exit_code

    def readAllStandardError(self):
        class B:
            def data(self):
                return b""
        return B()

    def readAllStandardOutput(self):
        class B:
            def data(self):
                return b""
        return B()


def make_paths(tmp_path: Path):
    workdir = tmp_path / "Cases"
    outdir = workdir / "Output"
    workdir.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)
    tex = workdir / "Example.tex"
    tex.write_text("% dummy", encoding="utf-8")
    return workdir, outdir, tex


def test_engine_missing_returns_none(tmp_path: Path):
    log = StructuredLogger("test.qproc1", console=False)
    comp = mod.QProcessTeXCompiler(log)
    workdir, outdir, tex = make_paths(tmp_path)
    engine = tmp_path / "bin" / "tinitex"  # does not exist
    result = comp.compile(engine, workdir, outdir, tex)
    assert result is None


def test_success_creates_pdf(tmp_path: Path, monkeypatch):
    log = StructuredLogger("test.qproc2", console=False)
    comp = mod.QProcessTeXCompiler(log)

    # monkeypatch the QProcess class in module
    monkeypatch.setattr(mod, "QProcess", FakeQProcessSuccess)

    workdir, outdir, tex = make_paths(tmp_path)
    engine = tmp_path / "bin" / "tinitex"
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    result = comp.compile(engine, workdir, outdir, tex)
    assert result == outdir / "Example.pdf"
    assert result.exists()


def test_nonzero_exit_returns_none(tmp_path: Path, monkeypatch):
    log = StructuredLogger("test.qproc3", console=False)
    comp = mod.QProcessTeXCompiler(log)

    class Fail(FakeQProcessSuccess):
        def __init__(self):
            super().__init__()
            self._exit_code = 1

    monkeypatch.setattr(mod, "QProcess", Fail)

    workdir, outdir, tex = make_paths(tmp_path)
    engine = tmp_path / "bin" / "tinitex"
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")

    result = comp.compile(engine, workdir, outdir, tex)
    assert result is None


def test_wait_timeout_returns_none(tmp_path: Path, monkeypatch):
    log = StructuredLogger("test.qproc4", console=False)
    comp = mod.QProcessTeXCompiler(log)

    class Timeout(FakeQProcessSuccess):
        def waitForFinished(self, msecs: int) -> bool:
            return False

    monkeypatch.setattr(mod, "QProcess", Timeout)

    workdir, outdir, tex = make_paths(tmp_path)
    engine = tmp_path / "bin" / "tinitex"
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    result = comp.compile(engine, workdir, outdir, tex)
    assert result is None
