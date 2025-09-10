from pathlib import Path


from DataClasses import CaseBriefData
from Global_Vars import Global_Vars
from QProcessTeXCompiler import QProcessTeXCompiler
from RegexLatexCodec import RegexLatexCodec
from SQLiteCaseBriefRepository import SQLiteCaseBriefRepository
from logger import StructuredLogger
from protocols import CaseBriefRepository, CitationResolver, LatexCodec, TeXCompiler


class CaseCatalog:
    def __init__(
        self,
        repo: CaseBriefRepository,
        codec: LatexCodec,
        compiler: TeXCompiler,
        global_vars: Global_Vars,
        logger: StructuredLogger,
    ):
        self.repo = repo
        self.codec = codec
        self.compiler = compiler
        self.engine = global_vars.tinitex_binary
        self.workdir = global_vars.tmp_dir
        self.casesdir = global_vars.cases_dir
        self.outdir = global_vars.cases_output_dir
        self.log = logger.getChildLogger("CaseCatalog")

    # citation resolver via the repo (adaptor)
    class _Citer(CitationResolver):
        def __init__(self, repo: CaseBriefRepository):
            self._repo = repo

        def cite_label(self, label: str) -> str:
            # if repo has a direct method, call it; else compute from get()
            try:
                return self._repo.cite_label(label)  # type: ignore[attr-defined]
            except Exception:
                return f"\\hyperref[case:{label}]{{\\textit{{{label}}}}}"

    def save(self, brief: CaseBriefData) -> None:
        self.repo.save(brief)

    def load(self, label: str) -> CaseBriefData:
        return self.repo.get(label)

    def render_to_tex(self, brief: CaseBriefData) -> Path:
        tex = self.codec.to_tex(brief, cite=self._Citer(self.repo))
        tex_file = self.casesdir / f"{brief.filename}.tex"
        tex_file.write_text(tex, encoding="utf-8")
        return tex_file

    def compile_pdf(self, brief: CaseBriefData) -> Path | None:
        tex_file = self.render_to_tex(brief)
        return self.compiler.compile(self.engine, self.casesdir, self.outdir, tex_file)


class CaseBriefs:
    def __init__(self, catalog: CaseCatalog):
        self.catalog = catalog
        self.log = catalog.log.getParentLogger("CaseBriefs")
        self.items: list[CaseBriefData] = []

    def reload_from_sql(self) -> None:
        for label in self.catalog.repo.list_labels():
            data = self.catalog.load(label)
            if data not in self.items:
                self.items.append(data)


if __name__ == "__main__":
    logger = StructuredLogger(__name__)
    global_vars = Global_Vars()
    sqlite_repo = SQLiteCaseBriefRepository(
        global_vars.sql_dst_file, global_vars.sql_create, logger
    )
    regex_latex_codec = RegexLatexCodec()
    qprocess_tex_compiler = QProcessTeXCompiler(logger)
    catalog = CaseCatalog(
        sqlite_repo,
        regex_latex_codec,
        qprocess_tex_compiler,
        global_vars,
        logger,
    )
    briefs = CaseBriefs(catalog)
    briefs.reload_from_sql()
    for b in briefs.items:
        print(b.label, b.plaintiff)
