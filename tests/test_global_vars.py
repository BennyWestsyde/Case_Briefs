import importlib
from pathlib import Path

import pytest

import Global_Vars as GVmod
from logger import StructuredLogger


@pytest.fixture
def gv_paths(tmp_path: Path):
    res = tmp_path / "res"
    bundle = tmp_path / "bundle"
    write = tmp_path / "write"
    for p in (res, bundle, write):
        p.mkdir(parents=True, exist_ok=True)
    return res, bundle, write


def test_global_vars_uses_custom_app_dirs(monkeypatch, gv_paths):
    res, bundle, write = gv_paths

    # ensure module-level WRITE_DIR does not write into repo
    monkeypatch.setattr(GVmod, "WRITE_DIR", write, raising=False)

    # monkeypatch app_dirs to return our temp paths
    def fake_app_dirs(self):
        return res, bundle, write

    monkeypatch.setattr(GVmod.Global_Vars, "app_dirs", fake_app_dirs, raising=True)

    log = StructuredLogger("test.gv", console=False)
    gv = GVmod.Global_Vars(logger=log)

    # Paths should be under our temp write
    assert gv.write_dir == write
    assert gv.cases_dir == write / "Cases"
    assert gv.cases_output_dir == write / "Cases" / "Output"
    assert gv.tex_src_dir == res / "tex_src"
    assert gv.tex_dst_dir == write / "tex_src"
    assert gv.master_src_tex == res / "tex_src" / "CaseBriefs.tex"
    assert gv.master_dst_tex == write / "tex_src" / "CaseBriefs.tex"
    # JSON file should be written into write
    assert (write / "global_vars.json").exists()

    # Changing an attribute should persist asynchronously
    new_backup = write / "Backup2"
    gv.backup_location = new_backup

    # give async thread a moment; in unit tests we can force save synchronously
    gv.save_to_json()
    text = (write / "global_vars.json").read_text(encoding="utf-8")
    assert "Backup2" in text


def test_compute_state_hash_changes(monkeypatch, gv_paths):
    res, bundle, write = gv_paths
    monkeypatch.setattr(GVmod, "WRITE_DIR", write, raising=False)

    def fake_app_dirs(self):
        return res, bundle, write

    monkeypatch.setattr(GVmod.Global_Vars, "app_dirs", fake_app_dirs, raising=True)

    log = StructuredLogger("test.gv2", console=False)
    gv = GVmod.Global_Vars(logger=log)
    h1 = gv._compute_state_hash()
    gv.notes = "something"  # add a new attribute
    h2 = gv._compute_state_hash()
    assert h1 != h2
