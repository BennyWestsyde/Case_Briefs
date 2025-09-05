from cleanup import StructuredLogger


import json
import os
import sys
from pathlib import Path
from types import MethodType
from typing import Any

global APP_NAME
APP_NAME = "CaseBriefs"


class Global_Vars:
    """
    Holds and persists application-wide paths and configuration.

    This class centralizes discovery, creation, and persistence of all filesystem
    locations used by the Case Briefs application. On initialization it determines
    resource and bundle locations, chooses an appropriate writable directory, and
    either loads previously saved values from a JSON file or initializes sensible
    defaults. It also ensures required directories exist and configures a platform-
    specific path to the `tinitex` binary.

    Persistence model:
    - After initialization, any attribute assignment on an instance automatically
        triggers a save to JSON (the class replaces `__setattr__` with an internal
        wrapper). This makes changes durable across runs without extra calls.

    Environment awareness:
    - Development vs. bundled (PyInstaller/frozen) runs are detected.
    - The writable data directory is resolved using Qt's QStandardPaths when
        available, with a macOS-friendly fallback under
        ~/Library/Application Support/<APP_NAME>.
    - The `tinitex` binary path is chosen per-platform (.exe on Windows).

    Attributes:
    - self.log: StructuredLogger
            Structured self.logger used for debug/info/warn messages.
    - res_dir: pathlib.Path
            Directory containing read-only application resources (e.g., templates, SQL).
    - bundle_dir: pathlib.Path
            Top-level bundle directory (e.g., .../CaseBriefs.app/Contents) or project
            root during development.
    - write_dir: pathlib.Path
            Root of writable user data; also contains the persistence file.
    - tmp_dir: pathlib.Path
            Temporary working directory under write_dir (default: write_dir/TMP).
    - cases_dir: pathlib.Path
            Root directory for case input files (default: write_dir/Cases).
    - cases_output_dir: pathlib.Path
            Output directory for processed case artifacts (default: write_dir/Cases/Output).
    - tex_src_dir: pathlib.Path
            Read-only LaTeX source directory bundled with the app (default: res_dir/tex_src).
    - tex_dst_dir: pathlib.Path
            Writable LaTeX working directory (default: write_dir/tex_src).
    - master_src_tex: pathlib.Path
            Path to the master LaTeX source file in tex_src_dir (CaseBriefs.tex).
    - master_src_sty: pathlib.Path
            Path to the style file in tex_src_dir (lawbrief.sty).
    - master_dst_tex: pathlib.Path
            Writable copy of the master LaTeX file in tex_dst_dir.
    - master_dst_sty: pathlib.Path
            Writable copy of the style file in tex_dst_dir.
    - sql_src_dir: pathlib.Path
            Read-only SQL resource directory (default: res_dir/SQL).
    - sql_dst_dir: pathlib.Path
            Writable SQL directory (default: write_dir/SQL).
    - sql_src_file: pathlib.Path
            Bundled SQLite database (default: sql_src_dir/Cases.sqlite).
    - sql_dst_file: pathlib.Path
            Writable SQLite database (default: sql_dst_dir/Cases.sqlite).
    - sql_create: pathlib.Path
            SQL schema creation script (default: sql_src_dir/Create_DB.sql).
    - backup_location: pathlib.Path
            Directory for backups (default: write_dir/Backup).
    - tinitex_binary: pathlib.Path
            Path to the tinitex executable under res_dir/bin, with .exe on Windows.

    Methods:
    - app_dirs() -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]
            Resolve (resources_dir, bundle_dir, writable_dir). Creates the writable
            directory if needed and self.logs its decisions.
    - load_from_json() -> dict[str, pathlib.Path] | None
            Load previously saved attributes from write_dir/global_vars.json. Returns a
            mapping of attribute names to Path values, or None if not found. Internal
            and callable attributes are ignored.
    - save_to_json() -> None
            Persist current public attributes to write_dir/global_vars.json. Paths are
            serialized as strings. May raise I/O errors if the file cannot be written.
    - _setattr_(name: str, value: Any) -> None
            Replacement for __setattr__ that self.logs the change, sets the attribute, and
            immediately saves the updated state to JSON.

    Side effects:
    - Creates required directories (write_dir, tmp_dir, cases_dir, cases_output_dir,
        tex_src_dir, tex_dst_dir, sql_src_dir, sql_dst_dir, backup_location).
    - Reads/writes write_dir/global_vars.json during load/save.
    - Emits self.log messages describing decisions and file operations.

    Raises:
    - OSError / IOError from directory creation or JSON file writes/reads.
    - Any exceptions from Qt path resolution are caught; a platform fallback is used.

    Example:
            gv = Global_Vars()
            # Use resolved paths
            print(gv.sql_dst_file)
            # Any change is persisted automatically
            gv.backup_location = gv.write_dir / "MyBackups"
    """

    def __init__(self):
        self.log = StructuredLogger(
            "Globals_Vars", "TRACE", None, True, None, True, True
        )
        self.log.info(f"Initialized logger for {self.__class__.__name__}")
        self.res_dir, self.bundle_dir, self.write_dir = self.app_dirs()
        self.tmp_dir: Path = Path()
        self.cases_dir: Path = Path()
        self.cases_output_dir: Path = Path()
        self.tex_src_dir: Path = Path()
        self.tex_dst_dir: Path = Path()
        self.master_src_tex: Path = Path()
        self.master_src_sty: Path = Path()
        self.master_dst_tex: Path = Path()
        self.master_dst_sty: Path = Path()
        self.sql_src_dir: Path = Path()
        self.sql_dst_dir: Path = Path()
        self.sql_src_file: Path = Path()
        self.sql_dst_file: Path = Path()
        self.sql_create: Path = Path()
        self.backup_location: Path = Path()
        self.tinitex_binary: Path = Path()
        results: dict[str, Path] | None = self.load_from_json()
        if results:
            self.log.info("Loaded global variables from JSON")
            self.res_dir = results.get("res_dir", self.res_dir)
            self.bundle_dir = results.get("bundle_dir", self.bundle_dir)
            self.write_dir = results.get("write_dir", self.write_dir)
            self.tmp_dir = results.get("tmp_dir", self.tmp_dir)
            self.cases_dir = results.get("cases_dir", self.cases_dir)
            self.cases_output_dir = results.get(
                "cases_output_dir", self.cases_output_dir
            )
            self.tex_src_dir = results.get("tex_src_dir", self.tex_src_dir)
            self.tex_dst_dir = results.get("tex_dst_dir", self.tex_dst_dir)
            self.master_src_tex = results.get("master_src_tex", self.master_src_tex)
            self.master_src_sty = results.get("master_src_sty", self.master_src_sty)
            self.master_dst_tex = results.get("master_dst_tex", self.master_dst_tex)
            self.master_dst_sty = results.get("master_dst_sty", self.master_dst_sty)
            self.sql_src_dir = results.get("sql_src_dir", self.sql_src_dir)
            self.sql_dst_dir = results.get("sql_dst_dir", self.sql_dst_dir)
            self.sql_src_file = results.get("sql_src_file", self.sql_src_file)
            self.sql_dst_file = results.get("sql_dst_file", self.sql_dst_file)
            self.sql_create = results.get("sql_create", self.sql_create)
            self.backup_location = results.get("backup_location", self.backup_location)
            self.save_to_json()
        else:
            self.log.warning("No global variables found in JSON")
            self.tmp_dir = self.write_dir / "TMP"
            self.cases_dir = self.write_dir / "Cases"
            self.cases_output_dir = self.write_dir / "Cases" / "Output"
            self.tex_src_dir = self.res_dir / "tex_src"
            self.tex_dst_dir = self.write_dir / "tex_src"
            self.master_src_tex = self.tex_src_dir / "CaseBriefs.tex"
            self.master_src_sty = self.tex_src_dir / "lawbrief.sty"
            self.master_dst_tex = self.tex_dst_dir / "CaseBriefs.tex"
            self.master_dst_sty = self.tex_dst_dir / "lawbrief.sty"
            self.sql_src_dir = self.res_dir / "SQL"
            self.sql_dst_dir = self.write_dir / "SQL"
            self.sql_src_file = self.sql_src_dir / "Cases.sqlite"
            self.sql_dst_file = self.sql_dst_dir / "Cases.sqlite"
            self.sql_create = self.sql_src_dir / "Create_DB.sql"
            self.backup_location = self.write_dir / "Backup"
        self.tinitex_binary = (
            self.res_dir / "bin" / "tinitex"
            if os.name != "nt"
            else self.res_dir / "bin" / "tinitex.exe"
        )
        self.__setattr__ = self._setattr_
        for d in (
            self.write_dir,
            self.tmp_dir,
            self.cases_dir,
            self.cases_output_dir,
            self.tex_src_dir,
            self.tex_dst_dir,
            self.sql_src_dir,
            self.sql_dst_dir,
            self.backup_location,
        ):
            Path(d).mkdir(parents=True, exist_ok=True)

    def _setattr_(self, name: str, value: Any) -> None:
        self.log.debug(f"Setting attribute '{name}' to '{value}'")
        super().__setattr__(name, value)
        self.save_to_json()

    def app_dirs(self):
        # Where to READ bundled resources (inside .app or onefile temp)
        if getattr(sys, "frozen", False):
            self.log.info("Running in a bundled environment")
            resources_dir = Path(sys._MEIPASS)  # type: ignore # PyInstaller unpack dir
            bundle_dir = (
                Path(sys.executable).resolve().parents[2]
            )  # .../CaseBriefs.app/Contents
        else:
            self.log.info("Running in a development environment")
            resources_dir = Path(__file__).resolve().parent
            bundle_dir = resources_dir
        relative_bundle_path = os.path.relpath(bundle_dir, Path.cwd())
        relative_resources_path = os.path.relpath(resources_dir, Path.cwd())
        self.log.debug(f"Resources Directory: {relative_resources_path}")
        self.log.debug(f"Bundle Directory: {relative_bundle_path}")

        # Where to WRITE user data (never write into the .app)
        if resources_dir == bundle_dir:
            self.log.debug("Using local directory for writable data")
            writable_dir = bundle_dir
        else:
            try:
                # macOS Application Support path
                from PyQt6.QtCore import QStandardPaths

                base = (
                    Path(
                        QStandardPaths.writableLocation(
                            QStandardPaths.StandardLocation.AppDataLocation
                        )
                    )
                    / APP_NAME
                )
                writable_dir = (
                    Path(base)
                    if base
                    else Path.home() / "Library" / "Application Support" / APP_NAME
                )  # APP_NAME
            except Exception:
                writable_dir = (
                    Path.home() / "Library" / "Application Support" / APP_NAME
                )  # APP_NAME
            self.log.debug(f"Writable Directory: {writable_dir}")
            writable_dir.mkdir(parents=True, exist_ok=True)
        return resources_dir, bundle_dir, writable_dir

    def load_from_json(self) -> dict[str, Path] | None:
        self.log.debug("Loading global variables from JSON")
        json_path = self.write_dir / "global_vars.json"
        relative_path = os.path.relpath(json_path, Path.cwd())
        if json_path.exists():
            self.log.trace("Found JSON file")
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key in list(data.keys()):
                    if key.startswith("_") or key.startswith("self.log"):
                        del data[key]
                    if isinstance(data[key], MethodType):
                        del data[key]
                    if isinstance(data[key], str):
                        data[key] = Path(data[key])
                self.log.info(f"Loaded global variables from {relative_path}")
                return data
        else:
            self.log.warning(f"JSON file not found: {relative_path}")
            return None

    def save_to_json(self):
        self.log.debug("Saving global variables to JSON")
        json_path = self.write_dir / "global_vars.json"
        relative_path = os.path.relpath(json_path, Path.cwd())
        with open(json_path, "w", encoding="utf-8") as f:
            own_dict = self.__dict__.copy()
            for key in list(own_dict.keys()):
                if key.startswith("_") or key.startswith("log"):
                    del own_dict[key]
                    continue
                if isinstance(own_dict[key], MethodType):
                    del own_dict[key]
                    continue
                if isinstance(own_dict[key], Path):
                    own_dict[key] = str(own_dict[key])
            json.dump(own_dict, f, indent=4)
            self.log.debug(f"Saved global variables to {relative_path}")
