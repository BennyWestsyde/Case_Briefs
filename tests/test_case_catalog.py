from pathlib import Path

from DataClasses import CaseBriefData, Label, Opinion, Subject
from CaseCatalog import CaseCatalog, CaseBriefs
from logger import StructuredLogger


class FakeRepo:
    def __init__(self):
        self.store: dict[str, CaseBriefData] = {}
        self.saved: list[CaseBriefData] = []

    def save(self, data: CaseBriefData) -> None:
        self.store[data.label.text] = data
        self.saved.append(data)

    def get(self, label: str) -> CaseBriefData:
        return self.store[label]

    def list_labels(self) -> list[str]:
        return list(self.store.keys())


class FakeRepoNoCite(FakeRepo):
    # no cite_label method to trigger fallback
    pass


class FakeRepoWithCite(FakeRepo):
    def cite_label(self, label: str) -> str:
        return f"CITED:{label}"


class FakeCodec:
    def __init__(self):
        self.master_tex_path = None
        # Attribute to trigger the output_file_path branch
        self._get_master_tex_reference = True
        self.last_output_path: Path | None = None

    def to_tex(self, data: CaseBriefData, cite, output_file_path: Path | None = None) -> str:
        self.last_output_path = output_file_path
        return f"% TEX for {data.label.text} -> cite:{cite.cite_label(data.label.text)}"


class FakeCompiler:
    def __init__(self):
        self.calls: list[tuple[Path, Path, Path, Path]] = []

    def compile(self, engine: Path, workdir: Path, outdir: Path, tex_file: Path):
        self.calls.append((engine, workdir, outdir, tex_file))
        return outdir / (tex_file.stem + ".pdf")


class FakeGV:
    def __init__(self, root: Path):
        self.tinitex_binary = root / "bin" / "tinitex"
        self.tmp_dir = root / "TMP"
        self.cases_dir = root / "Cases"
        self.cases_output_dir = root / "Cases" / "Output"
        self.master_dst_tex = root / "tex_src" / "CaseBriefs.tex"
        # ensure dirs exist
        for p in (self.tmp_dir, self.cases_dir, self.cases_output_dir, self.master_dst_tex.parent):
            p.mkdir(parents=True, exist_ok=True)
        self.master_dst_tex.write_text("% master", encoding="utf-8")


def make_brief(label: str = "Alice_v_Bob") -> CaseBriefData:
    return CaseBriefData(
        plaintiff="Alice",
        defendant="Bob",
        citation="123 U.S. 456 (1890)",
        course="Torts",
        facts="Facts",
        procedure="Procedure",
        issue="Issue",
        holding="Holding",
        principle="Principle",
        reasoning="Reasoning",
        label=Label(label),
        notes="Notes",
        subjects=[Subject("Torts")],
        opinions=[Opinion("Judge", "Opinion")],
    )


def test_catalog_initializes_master_tex_in_codec(tmp_path: Path):
    repo = FakeRepo()
    codec = FakeCodec()
    comp = FakeCompiler()
    gv = FakeGV(tmp_path)
    log = StructuredLogger("test.catalog", console=False)

    cat = CaseCatalog(repo, codec, comp, gv, log)
    assert codec.master_tex_path == gv.master_dst_tex


def test_render_to_tex_writes_file_and_passes_output_path(tmp_path: Path):
    repo = FakeRepo()
    codec = FakeCodec()
    comp = FakeCompiler()
    gv = FakeGV(tmp_path)
    log = StructuredLogger("test.catalog2", console=False)

    cat = CaseCatalog(repo, codec, comp, gv, log)
    brief = make_brief()
    tex_path = cat.render_to_tex(brief)

    assert tex_path == gv.cases_dir / f"{brief.filename}.tex"
    assert tex_path.exists()
    assert codec.last_output_path == tex_path
    assert tex_path.read_text(encoding="utf-8").startswith("% TEX for Alice_v_Bob")


def test_compile_pdf_calls_compiler_and_returns_pdf(tmp_path: Path):
    repo = FakeRepo()
    codec = FakeCodec()
    comp = FakeCompiler()
    gv = FakeGV(tmp_path)
    log = StructuredLogger("test.catalog3", console=False)

    cat = CaseCatalog(repo, codec, comp, gv, log)
    brief = make_brief()
    pdf = cat.compile_pdf(brief)

    assert pdf == gv.cases_output_dir / (brief.filename + ".pdf")
    assert comp.calls and comp.calls[-1][1] == gv.cases_dir  # workdir


def test_casebriefs_reload_from_sql_no_duplicates(tmp_path: Path):
    repo = FakeRepo()
    codec = FakeCodec()
    comp = FakeCompiler()
    gv = FakeGV(tmp_path)
    log = StructuredLogger("test.catalog4", console=False)
    cat = CaseCatalog(repo, codec, comp, gv, log)

    # prepopulate repo
    for label in ("A_v_B", "C_v_D"):
        repo.save(make_brief(label))

    briefs = CaseBriefs(cat)
    briefs.reload_from_sql()
    assert {b.label.text for b in briefs.items} == {"A_v_B", "C_v_D"}

    # calling again should not duplicate
    briefs.reload_from_sql()
    assert len(briefs.items) == 2


def test_citer_uses_repo_cite_or_fallback(tmp_path: Path):
    gv = FakeGV(tmp_path)
    log = StructuredLogger("test.catalog5", console=False)

    repo1 = FakeRepoWithCite()
    codec = FakeCodec()
    comp = FakeCompiler()
    cat1 = CaseCatalog(repo1, codec, comp, gv, log)
    citer1 = cat1._Citer(repo1)
    assert citer1.cite_label("L1") == "CITED:L1"

    repo2 = FakeRepoNoCite()
    cat2 = CaseCatalog(repo2, codec, comp, gv, log)
    citer2 = cat2._Citer(repo2)
    assert citer2.cite_label("L2").startswith("\\hyperref[case:L2]")
