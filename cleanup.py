import os
from logger import StructuredLogger

log = StructuredLogger("Cleanup", "TRACE", "CaseBriefs.log", True, None, True, True)


def clean_dir(path: str):
    log.info(f"Cleaning directory: {path}")
    for file in os.listdir(path):
        curr_path = os.path.join(path, file)
        if os.path.isfile(curr_path):
            log.trace(f"Found file: {curr_path}")
            if file.endswith(
                (
                    "aux",
                    "fdb_latexmk",
                    "fls",
                    "idx",
                    "ilg",
                    "ind",
                    "log",
                    "out",
                    "synctex.gz",
                    "synctex(busy)",
                    "toc",
                )
            ):
                log.trace(f"File in glob for deletion")
                log.debug(f"Removing file: {curr_path}")
                os.remove(curr_path)
        elif os.path.isdir(curr_path):
            log.debug(f"Pivoting to directory: {curr_path}")
            clean_dir(curr_path)


if __name__ == "__main__":
    curr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    clean_dir(curr_path)
