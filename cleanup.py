import os
from logger import StructuredLogger
from pathlib import Path

log = StructuredLogger("Cleanup", "TRACE", "CaseBriefs.log", True, None, True, True)


def clean_dir(path: Path, ignore_dirs: list[Path] = []):
    relative_print_path = path.relative_to(Path(__file__).absolute().parent)
    log.info(f"Cleaning directory: {relative_print_path}")
    for file in path.iterdir():
        curr_path = file.absolute()
        curr_relative_print_path = curr_path.relative_to(
            Path(__file__).absolute().parent
        )
        if os.path.isfile(curr_path):
            log.trace(f"Found file: {curr_relative_print_path}")
            if file.suffix in (
                ".aux",
                ".fdb_latexmk",
                ".fls",
                ".idx",
                ".ilg",
                ".ind",
                ".log",
                ".out",
                ".synctex.gz",
                ".synctex(busy)",
                ".toc",
            ):
                log.trace(f"File in glob for deletion")
                log.debug(f"Removing file: {curr_relative_print_path}")
                os.remove(curr_path)
        elif os.path.isdir(curr_path):
            if curr_path in ignore_dirs:
                log.trace(
                    f"Directory in ignore list, skipping: {curr_relative_print_path}"
                )
                ignore_dirs = [d for d in ignore_dirs if d != curr_path]
                continue
            log.debug(f"Pivoting to directory: {curr_relative_print_path}")
            clean_dir(curr_path, ignore_dirs=ignore_dirs)


if __name__ == "__main__":
    curr_path = Path(__file__).absolute().parent
    clean_dir(
        curr_path,
        ignore_dirs=[
            curr_path / ".venv",
            curr_path / "__pycache__",
            curr_path / ".git",
            curr_path / ".mypy_cache",
            curr_path / "dist",
            curr_path / "build",
        ],
    )
