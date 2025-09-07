import os
from logger import StructuredLogger
from pathlib import Path

log = StructuredLogger("Cleanup", "TRACE", "CaseBriefs.log", True, None, True, True)


def clean_dir(path: Path):
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
            log.debug(f"Pivoting to directory: {curr_relative_print_path}")
            clean_dir(curr_path)


if __name__ == "__main__":
    curr_path = Path(__file__).absolute().parent
    clean_dir(curr_path)
