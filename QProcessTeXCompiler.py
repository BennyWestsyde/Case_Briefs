from logger import StructuredLogger


from PyQt6.QtCore import QProcess


# import os
from pathlib import Path


class QProcessTeXCompiler:
    def __init__(self, logger: StructuredLogger):
        self.log = logger.getChildLogger("QProcessTeXCompiler")

    def compile(
        self, engine: Path, workdir: Path, outdir: Path, tex_file: Path
    ) -> Path | None:
        pdf_path = outdir / (tex_file.stem + ".pdf")
        try:
            if pdf_path.exists():
                pdf_path.unlink()
        except Exception:
            pass

        if not engine.exists():
            self.log.error("TeX engine not found: %s", engine)
            return None

        proc = QProcess()
        proc.setWorkingDirectory(str(workdir))
        proc.setProgram(str(engine))
        proc.setArguments(
            [
                f"--output-dir={outdir.relative_to(workdir)}",
                "--pdf-engine-opt=-shell-escape",
                "--no-auto-install",
                # "--pdf-engine-opt=-interaction=nonstopmode",
                f"{tex_file.relative_to(workdir)}",
            ]
        )
        proc.start()

        if not proc.waitForFinished(-1):
            self.log.error("TeX process did not finish")
            return None

        if proc.exitStatus() != QProcess.ExitStatus.NormalExit or proc.exitCode() != 0:
            stderr = (
                proc.readAllStandardError().data().decode("utf-8", errors="replace")
            )
            stdout = (
                proc.readAllStandardOutput().data().decode("utf-8", errors="replace")
            )
            self.log.error("TeX error: %s", stderr or stdout or "Unknown error")
            return None

        if not pdf_path.exists():
            self.log.error("PDF not found after compile: %s", pdf_path)
            return None
        return pdf_path
