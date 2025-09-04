import json
from pathlib import Path
import sys
from types import MethodType
from typing import Any, List, TypedDict, Union
import os
from cleanup import clean_dir
import re
import sqlite3
from PyQt6.QtCore import QProcess

from logger import StructuredLogger
from pathlib import Path

global APP_NAME
APP_NAME = "CaseBriefs"


def strict_path(value: Path | None) -> Path:
    if value is None:
        raise ValueError("Expected non-None value")
    return value


class Global_Vars:
    def __init__(self):
        self.log = StructuredLogger("Globals", "TRACE", None, True, None, True, True)
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

        self.log.debug(f"Resources Directory: {resources_dir}")
        self.log.debug(f"Bundle Directory: {bundle_dir}")

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
        json_path = self.write_dir / "global_vars.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key in list(data.keys()):
                    if key.startswith("_") or key.startswith("log"):
                        del data[key]
                    if isinstance(data[key], MethodType):
                        del data[key]
                    if isinstance(data[key], str):
                        data[key] = Path(data[key])
                self.log.info(f"Loaded global variables from {json_path}")
                return data
        self.log.warning(f"JSON file not found: {json_path}")
        return None

    def save_to_json(self):
        json_path = self.write_dir / "global_vars.json"
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
            self.log.info(f"Saved global variables to {json_path}")


global global_vars
global_vars = Global_Vars()


log = StructuredLogger(
    "CaseBrief",
    "TRACE",
    str(global_vars.write_dir / "CaseBriefs.log"),
    True,
    None,
    True,
    True,
)

log.debug(f"Base Directory: {global_vars.write_dir}")


def tex_escape(input: str) -> str:
    """Escape special characters for LaTeX."""
    replacements = {
        "{": "\\{",
        "}": "\\}",
        "$": "\\$",
        "&": "\\&",
        "%": "\\%",
        "#": "\\#",
        "_": "\\_",
        "~": "\\textasciitilde{}",
        "^": "\\textasciicircum{}",
    }
    return (
        str.translate(input, str.maketrans(replacements))
        .replace("\n", r"\\" + "\n")
        .replace(". ", r".\ ")
    )


def tex_unescape(input: str) -> str:
    """Unescape special characters for LaTeX."""
    replacements = {
        "\\{": "{",
        "\\}": "}",
        "\\$": "$",
        "\\&": "&",
        "\\%": "%",
        "\\#": "#",
        "\\_": "_",
        "\\textasciitilde{}": "~",
        "\\textasciicircum{}": "^",
    }
    return (
        str.translate(input, str.maketrans(replacements))
        .replace(r"\\" + "\n", "\n")
        .replace(r".\ ", ". ")
    )


SQLiteValue = Union[str, int, float, bytes, None]


class SQL:
    """A class to handle interaction with the database."""

    def __init__(self, db_path: str = str(global_vars.sql_dst_file)):
        self.db_path = db_path
        self.ensureDB()
        self.connection = sqlite3.connect(self.db_path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.connection.cursor()

    def exists(self) -> bool:
        """Check if the database exists."""
        log.debug("Checking if database exists")
        return Path(self.db_path).exists()

    def ensureDB(self) -> bool:
        """Ensure the database and tables exist."""
        log.debug("Ensuring database exists")
        if not self.exists():
            log.warning(f"Database not found, creating at {self.db_path}")
            with sqlite3.connect(str(self.db_path)) as conn:
                with open(
                    strict_path(global_vars.sql_create), "r", encoding="utf-8"
                ) as f:
                    conn.executescript(f.read())
            log.info("Database created successfully")
            return True
        else:
            log.info("Database found")
            return True

    def execute(
        self, query: str, params: tuple[SQLiteValue, ...] = ()
    ) -> sqlite3.Cursor:
        """Execute a SQL query and return the cursor."""
        self.cursor.execute(query, params)
        return self.cursor

    def commit(self) -> None:
        """Commit the current transaction."""
        self.connection.commit()

    def close(self) -> None:
        """Close the database connection."""
        self.connection.close()

    def saveBrief(self, brief: "CaseBrief") -> None:
        """Save a case brief to the database."""
        log.debug(f"Saving brief for case: {brief.citation}")
        cases_table_query = """
                INSERT INTO Cases (label, plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(label) DO UPDATE SET
                    plaintiff=excluded.plaintiff,
                    defendant=excluded.defendant,
                    citation=excluded.citation,
                    course=excluded.course,
                    facts=excluded.facts,
                    procedure=excluded.procedure,
                    issue=excluded.issue,
                    holding=excluded.holding,
                    principle=excluded.principle,
                    reasoning=excluded.reasoning,
                    notes=excluded.notes
            """
        try:
            # Insert or update the main case brief information
            self.execute(
                cases_table_query,
                (
                    brief.label.text,
                    brief.plaintiff,
                    brief.defendant,
                    brief.citation,
                    brief.course,
                    brief.facts,
                    brief.procedure,
                    brief.issue,
                    brief.holding,
                    brief.principle,
                    brief.reasoning,
                    brief.notes,
                ),
            )

            # Clear existing subjects and opinions
            log.trace("Deleting existing subjects and opinions")
            self.execute(
                "DELETE FROM CaseSubjects WHERE case_label = ?", (brief.label.text,)
            )
            self.execute(
                "DELETE FROM CaseOpinions WHERE case_label = ?", (brief.label.text,)
            )

            # Insert subjects
            for subject in brief.subject:
                log.trace(f"Saving Subject: {subject.name}")
                self.execute("SELECT id FROM Subjects where name = ?", (subject.name,))
                subject_id = self.cursor.fetchone()
                if not subject_id:
                    self.execute(
                        "INSERT INTO Subjects (name) VALUES (?)", (subject.name,)
                    )
                    self.execute(
                        "SELECT id FROM Subjects where name = ?", (subject.name,)
                    )
                    subject_id = self.cursor.fetchone()
                subject_id = subject_id[0]
                self.execute(
                    "INSERT INTO CaseSubjects (case_label, subject_id) VALUES (?, ?)",
                    (
                        brief.label.text,
                        subject_id,
                    ),
                )

            # Insert opinions
            for opinion in brief.opinions:
                log.trace(f"Saving Opinion By: {opinion.author}")
                self.execute(
                    "SELECT id FROM Opinions where opinion_text = ?", (opinion.text,)
                )
                opinion_id = self.cursor.fetchone()
                if not opinion_id:
                    self.execute(
                        "INSERT INTO Opinions (author, opinion_text) VALUES (?, ?)",
                        (
                            opinion.author,
                            opinion.text,
                        ),
                    )
                    self.execute(
                        "SELECT id FROM Opinions where opinion_text = ?",
                        (opinion.text,),
                    )
                    opinion_id = self.cursor.fetchone()
                opinion_id = opinion_id[0]
                self.execute(
                    "INSERT INTO CaseOpinions (case_label, opinion_id) VALUES (?, ?)",
                    (brief.label.text, opinion_id),
                )

            self.commit()
        except sqlite3.Error as e:
            self.connection.rollback()
            log.error(f"Error saving case brief to database: {e}", e.__traceback__)

    def export_db_file(self, export_path: Path) -> None:
        """Export the entire database to a SQL file."""
        log.debug(f"Exporting database to {export_path}")
        sql_dump = self._export_db_str()
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(sql_dump)
        log.info(f"Database exported successfully to {export_path}")

    def _export_db_str(self) -> str:
        def qident(name: str) -> str:
            # Quote identifiers with double quotes, escape internal quotes
            return '"' + name.replace('"', '""') + '"'

        table_order_map = {
            "Courses": 1,
            "Subjects": 2,
            "Opinions": 3,
            "Cases": 4,
            "CaseSubjects": 5,
            "CaseOpinions": 6,
        }

        # All user tables, skip sqlite_* internals
        tables = [
            r[0]
            for r in self.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        tables.sort(key=lambda t: table_order_map.get(t, 100))

        parts: list[str] = [
            "-- Exported SQLite data (data only)",
            "PRAGMA foreign_keys=OFF;",
            "BEGIN TRANSACTION;",
        ]

        for table in tables:
            # Skip hidden/generated columns (hidden!=0)
            cols = self.execute(f"PRAGMA table_xinfo({qident(table)})").fetchall()
            colnames = [c[1] for c in cols if c[-1] == 0]  # hidden flag is last field

            if not colnames:
                continue

            sel_cols = ", ".join(qident(c) for c in colnames)
            qvals = lambda v: self.execute("SELECT quote(?)", (v,)).fetchone()[  # type: ignore
                0
            ]  # pyright: ignore[reportUnknownArgumentType]

            for row in self.execute(
                f"SELECT {sel_cols} FROM {qident(table)}"
            ).fetchall():
                values = ", ".join(qvals(row[i]) for i in range(len(colnames)))
                parts.append(
                    f"INSERT OR REPLACE INTO {qident(table)} ({sel_cols}) VALUES ({values});"
                )

        parts += ["COMMIT;", "PRAGMA foreign_keys=ON;"]
        return "\n".join(parts)

    def restore_db_file(self, backup_path: Path) -> None:
        """Restore the database from a SQL dump file."""
        log.debug(f"Restoring database from {backup_path}")
        with open(backup_path, "r", encoding="utf-8") as f:
            db_str = f.read()
        self._restore_db_str(db_str)

    def _restore_db_str(self, db_str: str) -> None:
        """Restore the database from a SQL dump string."""
        log.debug(f"Restoring database from SQL dump")
        self.connection.executescript(db_str)
        self.commit()
        log.info(f"Database restored successfully")

    def loadBrief(self, case_label: str) -> "CaseBrief":
        """Load a case brief from the database by its label."""
        log.debug(f"Loading case brief from SQL with label {case_label}")
        self.execute(
            "SELECT plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, label, notes FROM Cases WHERE label = ?",
            (case_label,),
        )
        cur_case = self.cursor.fetchone()
        if not cur_case:
            log.error(f"No case brief found with label '{case_label}' in the database.")
            raise RuntimeError(
                f"No case brief found with label '{case_label}' in the database."
            )
        else:
            log.trace(f"Found case brief: {cur_case[-2]}")
        self.execute(
            "SELECT opinion_author, opinion_text FROM CaseOpinionsView WHERE case_label = ?",
            (case_label,),
        )
        opinions = [Opinion(*opinion) for opinion in self.cursor.fetchall()]
        self.execute(
            "SELECT subject_name FROM CaseSubjectsView WHERE case_label = ?",
            (case_label,),
        )
        subjects = [Subject(subject[-1]) for subject in self.cursor.fetchall()]
        # Assuming the database schema matches the order of fields in CaseBrief
        case_brief = CaseBrief(
            subject=subjects,
            opinions=opinions,
            plaintiff=cur_case[0],
            defendant=cur_case[1],
            citation=cur_case[2],
            course=cur_case[3],
            facts=cur_case[4],
            procedure=cur_case[5],
            issue=cur_case[6],
            holding=cur_case[7],
            principle=cur_case[8],
            reasoning=cur_case[9],
            label=Label(cur_case[10]),
            notes=cur_case[11],
        )
        return case_brief

    def cite_case_brief(self, label: str) -> str:
        """Generate a citation for a case brief."""
        log.debug(f"Citing case brief with label {label}")
        self.execute("SELECT title FROM Cases WHERE label = ?", (label,))
        title = self.cursor.fetchone()
        if not title:
            log.error(f"No case brief found with label '{label}' for citation.")
            return f"CITE({label})"
        return f"\\hyperref[case:{label}]{{\\textit{{{title[0]}}}}}"

    def fetchCaseLabels(self) -> list[str]:
        """Fetch all case labels from the database."""
        log.debug("Fetching case labels from SQL")
        self.execute("SELECT label FROM Cases")
        labels = [row[0] for row in self.cursor.fetchall()]
        return labels

    def addCaseSubject(self, subject: str, label: str) -> None:
        """Add a subject to a case label."""
        log.debug(f"Adding subject '{subject}' to case label {label}")
        # Check if subject exists in Subjects table
        self.execute("SELECT id FROM Subjects WHERE name = ?", (subject,))
        subject_id = self.cursor.fetchone()
        if not subject_id:
            log.info(f"Subject '{subject}' not found in Subjects table. Adding it.")
            self.execute("INSERT INTO Subjects (name) VALUES (?)", (subject,))
            self.commit()
            self.execute("SELECT id FROM Subjects WHERE name = ?", (subject,))
            subject_id = self.cursor.fetchone()
        self.execute(
            "INSERT INTO CaseSubjects (case_label, subject_id) VALUES (?, ?)",
            (label, subject_id),
        )
        self.commit()

    def fetchCaseSubjects(self) -> list[str]:
        """Fetch all case subjects from the database."""
        log.debug("Fetching case subjects from SQL")
        self.execute("SELECT name FROM Subjects")
        subjects = [row[0] for row in self.cursor.fetchall()]
        return subjects

    def addCourse(self, course: str) -> None:
        """Add a course to the database."""
        log.debug(f"Adding course '{course}' to SQL")
        self.execute("INSERT INTO Courses (name) VALUES (?)", (course,))
        self.commit()

    def removeCourse(self, course: str) -> None:
        """Remove a course from the database."""
        log.debug(f"Removing course '{course}' from SQL")
        usage_count = self.execute(
            "SELECT COUNT(*) FROM Cases WHERE course = ?", (course,)
        ).fetchone()[0]
        if usage_count > 0:
            log.warning(f"Course '{course}' is still in use by {usage_count} cases.")
            return
        self.execute("DELETE FROM Courses WHERE name = ?", (course,))
        self.commit()

    def fetchCourses(self) -> list[str]:
        """Fetch all course names from the database."""
        log.debug("Fetching course names from SQL")
        self.execute("SELECT name FROM Courses")
        courses = [row[0] for row in self.cursor.fetchall()]
        return courses


class Latex:
    """A class to handle LaTeX document generation."""

    def __init__(self):
        self.engine_path: Path = global_vars.write_dir / "bin" / "tinitex"
        self.tex_dir: Path = global_vars.cases_dir
        self.render_dir: Path = global_vars.cases_output_dir

    def _brief2Latex(self, brief: "CaseBrief") -> str:
        """Convert a CaseBrief object to its LaTeX representation."""
        citation_str = tex_escape(brief.citation)
        subjects_str = ", ".join(str(s) for s in brief.subject)
        opinions_str = ("\n").join(str(op) for op in brief.opinions)
        opinions_str = tex_escape(
            opinions_str
        )  # .replace('\n', r'\\'+'\n').replace("$", r"\$")
        opinions_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(m.group(1)),
            opinions_str,
        )
        # Replace citations in facts, procedure, and issue with \hyperref[case:self.label]{\textit{self.title}}
        facts_str = tex_escape(
            brief.facts
        )  # .replace('\n', r'\\'+'\n').replace("$", r"\$")
        facts_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(m.group(1)),
            facts_str,
        )
        procedure_str = tex_escape(brief.procedure)
        procedure_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(m.group(1)),
            procedure_str,
        )
        issue_str = tex_escape(brief.issue)
        issue_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(m.group(1)),
            issue_str,
        )
        principle_str = tex_escape(brief.principle)
        reasoning_str = tex_escape(brief.reasoning)
        notes_str = tex_escape(
            brief.notes
        )  # .replace('\n', r'\\'+'\n').replace("$", r"\$")
        notes_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(m.group(1)),
            notes_str,
        )

        return """
            \\documentclass[../tex_src/CaseBriefs.tex]{subfiles}
            \\usepackage{lawbrief}
            \\begin{document}
            \\NewBrief{subject={%s},
                    plaintiff={%s},
                    defendant={%s},
                    citation={%s},
                    course={%s},
                    facts={%s},
                    procedure={%s},
                    issue={%s},
                    holding={%s},
                    principle={%s},
                    reasoning={%s},
                    opinions={%s},
                    label={case:%s},
                    notes={%s}
            }
            \\end{document}
        """ % (
            subjects_str,
            brief.plaintiff,
            brief.defendant,
            citation_str,
            brief.course,
            facts_str,
            procedure_str,
            issue_str,
            brief.holding,
            principle_str,
            reasoning_str,
            opinions_str,
            brief.label,
            notes_str,
        )

    def _latex2Brief(self, tex_content: str) -> "CaseBrief":
        """Convert LaTeX content back to a CaseBrief object."""
        # Here you would parse the content to extract the case brief details
        # This is a placeholder implementation
        regex = r"\\NewBrief{subject=\{(.*?)\},\n\s*plaintiff=\{(.*?)\},\n\s*defendant=\{(.*?)\},\n\s*citation=\{(.*?)\},\n\s*course=\{(.*?)\},\n\s*facts=\{(.*?)\},\n\s*procedure=\{(.*?)\},\n\s*issue=\{(.*?)\},\n\s*holding=\{(.*?)\},\n\s*principle=\{(.*?)\},\n\s*reasoning=\{(.*?)\},\n\s*opinions=\{(.*?)\},\n\s*label=\{case:(.*?)\},\n\s*notes=\{(.*?)\}"
        match = re.search(regex, tex_content, re.DOTALL)
        if match:
            subjects = [
                Subject(s.strip()) for s in match.group(1).split(",") if s.strip()
            ]
            plaintiff = match.group(2).strip()
            defendant = match.group(3).strip()
            citation = tex_unescape(match.group(4).strip())
            course = match.group(5).strip()
            facts = tex_unescape(
                match.group(6).strip()
            )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
            # Regex replace existing citations with the CITE(\1)
            citation_regex = r"\\hyperref\[case:(.*?)\]\{\\textit\{(.*?)\}\}"
            facts = re.sub(citation_regex, r"CITE(\1)", facts)
            procedure = tex_unescape(
                match.group(7).strip()
            )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
            # Regex replace existing citations with the CITE(\1)
            procedure = re.sub(citation_regex, r"CITE(\1)", procedure)
            issue = tex_unescape(
                match.group(8).strip()
            )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
            # Regex replace existing citations with the CITE(\1)
            issue = re.sub(citation_regex, r"CITE(\1)", issue)
            holding = match.group(9).strip()
            principle = tex_unescape(match.group(10).strip())
            reasoning = tex_unescape(
                match.group(11).strip()
            )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
            opinions = [
                Opinion(
                    o.strip().split(":")[0].strip(), o.strip().split(":")[1].strip()
                )
                for o in re.sub(
                    citation_regex, r"CITE(\1)", tex_unescape(match.group(12))
                )
                if o.strip()
            ]
            label = Label(match.group(13).strip())
            notes = tex_unescape(
                match.group(14).strip()
            )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
        else:
            raise RuntimeError(
                f"Failed to parse case brief. The file may not be in the correct format."
            )

        return CaseBrief(
            subjects,
            plaintiff,
            defendant,
            citation,
            course,
            facts,
            procedure,
            issue,
            holding,
            principle,
            reasoning,
            opinions,
            label,
            notes,
        )

    def saveBrief(self, brief: "CaseBrief") -> Path:
        tex_content = self._brief2Latex(brief)
        tex_file = self.tex_dir / f"{brief.filename}.tex"
        with tex_file.open("w") as f:
            f.write(tex_content)
        return tex_file

    def loadBrief(self, filename: str) -> "CaseBrief":
        tex_file = self.tex_dir / f"{filename}.tex"
        if not tex_file.exists():
            raise FileNotFoundError(f"LaTeX file {tex_file} does not exist.")
        with tex_file.open("r") as f:
            tex_content = f.read()
        return self._latex2Brief(tex_content)

    def validateBrief(self, brief: "CaseBrief") -> bool:
        """Validate the case brief."""
        results = brief.__dict__

        class ResultsExpected(TypedDict):
            subject: List[Subject]
            plaintiff: str
            defendant: str
            citation: str
            course: str
            facts: str
            procedure: str
            issue: str
            holding: str
            principle: str
            reasoning: str
            opinions: List[Opinion]
            label: Label
            notes: str

        for key, expected_type in ResultsExpected.__annotations__.items():
            if key not in results:
                log.error(f"Case brief is missing {key}.")
                return False
            if not isinstance(results[key], expected_type):
                log.error(f"Case brief {key} is not of type {expected_type.__name__}.")
                return False
        return True

    def compile(self, tex_file: Path) -> Path:
        """Compile a LaTeX file to PDF and return the path to the PDF."""
        if not tex_file.exists():
            raise FileNotFoundError(f"LaTeX file {tex_file} does not exist.")
        pdf_file = self.tex_dir / f"{tex_file.stem}.pdf"
        if pdf_file.exists():
            pdf_file.unlink()
        try:
            process = QProcess()
            args: list[str] = [
                "--output-dir=./TMP",
                "--pdf-engine=pdflatex",  # or xelatex/lualatex
                "--pdf-engine-opt=-shell-escape",  # <-- include the leading dash
                str(pdf_file),
            ]
            process.setProgram(str(self.engine_path))
            process.setArguments(args)
            process.start()
            process.waitForFinished()
            if (
                process.exitStatus() != QProcess.ExitStatus.NormalExit
                or process.exitCode() != 0
            ):
                error_output = process.readAllStandardError().data().decode()
                log.error(f"Error compiling {tex_file} to PDF: {error_output}")
                raise RuntimeError(
                    f"Failed to compile {tex_file} to PDF. Check the LaTeX file for errors."
                )
            else:
                clean_dir(str(self.tex_dir))
            log.info(f"Compiled {tex_file} to {pdf_file}")
            return pdf_file
        except Exception as e:
            log.error(f"Error compiling {tex_file} to PDF: {e}")
            raise RuntimeError(
                f"Failed to compile {tex_file} to PDF. Check the LaTeX file for errors."
            )


class Subject:
    """A class to represent a legal subject."""

    def __init__(self, name: str):
        self.name = name

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Subject):
            return self.name == other.name
        elif isinstance(other, str):
            return self.name == other
        else:
            return False

    def __repr__(self) -> str:
        return f"Subject(name={self.name})"


class Label:
    """A class to represent the citable label of a case."""

    def __init__(self, label: str):
        self.text = label

    def __str__(self) -> str:
        return self.text

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Label):
            return self.text == other.text
        elif isinstance(other, str):
            return self.text == other
        else:
            return False

    def __repr__(self) -> str:
        return f"Label(label={self.text})"


class Opinion:
    """A class to represent a court opinion."""

    def __init__(self, author: str, text: str):
        self.author = author
        self.text = text

    def __str__(self) -> str:
        return f"{self.author}: {self.text}\n"


class CaseBrief:
    """
    A class to manage case briefs.

    Attributes:
        subject (list[Subject]): A list of Subject objects representing the legal subjects of the case.
        plaintiff (str): The name of the plaintiff in the case.
        defendant (str): The name of the defendant in the case.
        citation (str): The citation of the case, including the year.
        course (str): The name of the course for which the case brief is being prepared.
        facts (str): A string containing the relevant facts of the case.
        procedure (str): A string describing the procedural history of the case.
        issue (str): A string stating the legal issue(s) presented in the case.
        holding (str): A string containing the court's holding or decision.
        principle (str): A string stating the legal principle established by the case.
        reasoning (str): A string containing the court's reasoning or rationale for its decision.
        opinions (list[Opinion]): A list of Opinion objects containing any concurring or dissenting opinions.
        label (Label): A Label object representing the citable label of the case.
        notes (str): A string containing any additional notes about the case.
    """

    def __init__(
        self,
        subject: list[Subject],
        plaintiff: str,
        defendant: str,
        citation: str,
        course: str,
        facts: str,
        procedure: str,
        issue: str,
        holding: str,
        principle: str,
        reasoning: str,
        opinions: list[Opinion],
        label: Label,
        notes: str,
    ):
        """
        Initialize a CaseBrief object.

        Args:
            subject (list[Subject]): A list of Subject objects representing the legal subjects of the case.
            plaintiff (str): The name of the plaintiff in the case.
            defendant (str): The name of the defendant in the case.
            citation (str): The citation of the case, including the year.
            course (str): The name of the course for which the case brief is being prepared.
            facts (str): A string containing the relevant facts of the case.
            procedure (str): A string describing the procedural history of the case.
            issue (str): A string stating the legal issue(s) presented in the case.
            holding (str): A string containing the court's holding or decision.
            principle (str): A string stating the legal principle established by the case.
            reasoning (str): A string containing the court's reasoning or rationale for its decision.
            opinions (list[Opinion]): A list of Opinion objects containing any concurring or dissenting opinions.
            label (Label): A Label object representing the citable label of the case.
            notes (str): A string containing any additional notes about the case.
        """
        self.subject = subject
        self.plaintiff = plaintiff
        self.defendant = defendant
        self.course = course
        self.citation = citation
        self.facts = facts
        self.procedure = procedure
        self.issue = issue
        self.holding = holding
        self.principle = principle
        self.reasoning = reasoning
        self.opinions = opinions
        self.label = label
        self.notes = notes

    @property
    def title(self) -> str:
        return f"{self.plaintiff} v. {self.defendant}"

    @property
    def filename(self) -> str:
        return f"{self.plaintiff}_V_{self.defendant}".replace(" ", "_")

    def add_subject(self, subject: Subject) -> None:
        """Add a subject to the case brief."""
        self.subject.append(subject)

    def remove_subject(self, subject: Subject) -> None:
        """Remove a subject from the case brief."""
        self.subject = [s for s in self.subject if s != subject]

    def update_subject(self, old_subject: Subject, new_subject: Subject) -> None:
        """Update a subject in the case brief."""
        self.subject = [new_subject if s == old_subject else s for s in self.subject]

    def update_plaintiff(self, plaintiff: str) -> None:
        """Update the plaintiff in the case brief."""
        self.plaintiff = plaintiff

    def update_defendant(self, defendant: str) -> None:
        """Update the defendant in the case brief."""
        self.defendant = defendant

    def update_citation(self, citation: str) -> None:
        """Update the citation in the case brief."""
        self.citation = citation

    def update_facts(self, facts: str) -> None:
        """Update the facts in the case brief."""
        self.facts = facts

    def update_procedure(self, procedure: str) -> None:
        """Update the procedure in the case brief."""
        self.procedure = procedure

    def update_issue(self, issue: str) -> None:
        """Update the issue in the case brief."""
        self.issue = issue

    def update_holding(self, holding: str) -> None:
        """Update the holding in the case brief."""
        self.holding = holding

    def update_principle(self, principle: str) -> None:
        """Update the principle in the case brief."""
        self.principle = principle

    def update_reasoning(self, reasoning: str) -> None:
        """Update the reasoning in the case brief."""
        self.reasoning = reasoning

    def add_opinion(self, opinion: Opinion) -> None:
        """Add an opinion to the case brief."""
        self.opinions.append(opinion)

    def remove_opinion(self, opinion: Opinion) -> None:
        """Remove an opinion from the case brief."""
        self.opinions = [op for op in self.opinions if op != opinion]

    def update_label(self, label: Label) -> None:
        """Update the label in the case brief."""
        self.label = label

    def update_notes(self, notes: str) -> None:
        """Update the notes in the case brief."""
        self.notes = notes

    def get_pdf_path(self) -> str:
        """Get the path to the PDF file for this case brief."""
        return str(strict_path(global_vars.cases_output_dir) / f"{self.filename}.pdf")

    def to_latex(self) -> str:
        """Generate a LaTeX representation of the case brief."""
        citation_str = tex_escape(self.citation)
        subjects_str = ", ".join(str(s) for s in self.subject)
        opinions_str = ("\n").join(str(op) for op in self.opinions)
        opinions_str = tex_escape(
            opinions_str
        )  # .replace('\n', r'\\'+'\n').replace("$", r"\$")
        opinions_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(m.group(1)),
            opinions_str,
        )
        # Replace citations in facts, procedure, and issue with \hyperref[case:self.label]{\textit{self.title}}
        facts_str = tex_escape(
            self.facts
        )  # .replace('\n', r'\\'+'\n').replace("$", r"\$")
        facts_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(m.group(1)),
            facts_str,
        )
        procedure_str = tex_escape(self.procedure)
        procedure_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(m.group(1)),
            procedure_str,
        )
        issue_str = tex_escape(self.issue)
        issue_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(m.group(1)),
            issue_str,
        )
        principle_str = tex_escape(self.principle)
        reasoning_str = tex_escape(self.reasoning)
        notes_str = tex_escape(
            self.notes
        )  # .replace('\n', r'\\'+'\n').replace("$", r"\$")
        notes_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(m.group(1)),
            notes_str,
        )

        return """
            \\documentclass[../tex_src/CaseBriefs.tex]{subfiles}
            \\usepackage{lawbrief}
            \\begin{document}
            \\NewBrief{subject={%s},
                    plaintiff={%s},
                    defendant={%s},
                    citation={%s},
                    course={%s},
                    facts={%s},
                    procedure={%s},
                    issue={%s},
                    holding={%s},
                    principle={%s},
                    reasoning={%s},
                    opinions={%s},
                    label={case:%s},
                    notes={%s}
            }
            \\end{document}
        """ % (
            subjects_str,
            self.plaintiff,
            self.defendant,
            citation_str,
            self.course,
            facts_str,
            procedure_str,
            issue_str,
            self.holding,
            principle_str,
            reasoning_str,
            opinions_str,
            self.label,
            notes_str,
        )

    def to_sql(self) -> None:
        log.debug(f"Saving case brief '{self.label.text}' to SQL database")
        conn = sqlite3.connect(str(global_vars.sql_dst_file))
        conn.execute("PRAGMA foreign_keys = ON")
        curr = conn.cursor()
        try:
            # Insert or update the main case brief information
            curr.execute(
                """
                INSERT INTO Cases (label, plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(label) DO UPDATE SET
                    plaintiff=excluded.plaintiff,
                    defendant=excluded.defendant,
                    citation=excluded.citation,
                    course=excluded.course,
                    facts=excluded.facts,
                    procedure=excluded.procedure,
                    issue=excluded.issue,
                    holding=excluded.holding,
                    principle=excluded.principle,
                    reasoning=excluded.reasoning,
                    notes=excluded.notes
            """,
                (
                    self.label.text,
                    self.plaintiff,
                    self.defendant,
                    self.citation,
                    self.course,
                    self.facts,
                    self.procedure,
                    self.issue,
                    self.holding,
                    self.principle,
                    self.reasoning,
                    self.notes,
                ),
            )

            # Clear existing subjects and opinions
            log.debug("Deleting existing subjects and opinions")
            curr.execute(
                "DELETE FROM CaseSubjects WHERE case_label = ?", (self.label.text,)
            )
            curr.execute(
                "DELETE FROM CaseOpinions WHERE case_label = ?", (self.label.text,)
            )

            # Insert subjects
            for subject in self.subject:
                log.trace("Saving Subject: ", subject.name)
                curr.execute("SELECT id FROM Subjects where name = ?", (subject.name,))
                subject_id = curr.fetchone()
                if not subject_id:
                    curr.execute(
                        "INSERT INTO Subjects (name) VALUES (?)", (subject.name,)
                    )
                    curr.execute(
                        "SELECT id FROM Subjects where name = ?", (subject.name,)
                    )
                    subject_id = curr.fetchone()
                subject_id = subject_id[0]
                curr.execute(
                    "INSERT INTO CaseSubjects (case_label, subject_id) VALUES (?, ?)",
                    (
                        self.label.text,
                        subject_id,
                    ),
                )

            # Insert opinions
            for opinion in self.opinions:
                log.trace("Saving Opinion By: ", opinion.author)
                curr.execute(
                    "SELECT id FROM Opinions where opinion_text = ?", (opinion.text,)
                )
                opinion_id = curr.fetchone()
                if not opinion_id:
                    curr.execute(
                        "INSERT INTO Opinions (author, opinion_text) VALUES (?, ?)",
                        (
                            opinion.author,
                            opinion.text,
                        ),
                    )
                    curr.execute(
                        "SELECT id FROM Opinions where opinion_text = ?",
                        (opinion.text,),
                    )
                    opinion_id = curr.fetchone()
                opinion_id = opinion_id[0]
                curr.execute(
                    "INSERT INTO CaseOpinions (case_label, opinion_id) VALUES (?, ?)",
                    (self.label.text, opinion_id),
                )

            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            log.error(f"Error saving case brief to database: {e}")
        finally:
            conn.close()

    def save_to_file(self, filename: str) -> None:
        """Save the LaTeX representation of the case brief to a file."""
        with open(filename, "w") as f:
            f.write(self.to_latex())
        log.info(f"Saved Latex to {filename}")

    def compile_to_pdf(self) -> str | None:
        """Compile the LaTeX file to PDF."""
        tex_file = strict_path(global_vars.cases_dir) / f"{self.filename}.tex"
        self.save_to_file(str(tex_file))
        pdf_file = self.get_pdf_path()
        if os.path.exists(pdf_file):
            os.remove(pdf_file)
        try:
            process: QProcess = QProcess()
            process.start(str(global_vars.res_dir / "bin" / "tinitex"), [str(tex_file)])
            # process.start("pdflatex", ["-interaction=nonstopmode", "-output-directory=./Cases", tex_file]) # pyright: ignore[reportUnknownMemberType]
            process.waitForFinished()
            if (
                process.exitStatus() != QProcess.ExitStatus.NormalExit
                or process.exitCode() != 0
            ):
                error_output = process.readAllStandardError().data().decode()
                log.error(f"Error compiling {tex_file} to PDF: {error_output}")
                return
            else:
                clean_dir(str(global_vars.cases_dir))
            log.info(f"Compiled {tex_file} to {pdf_file}")
            return pdf_file
        except Exception as e:
            log.error(f"Error compiling {tex_file} to PDF: {e}")
            raise RuntimeError(
                f"Failed to compile {tex_file} to PDF. Check the LaTeX file for errors."
            )

    @staticmethod
    def load_from_file(filename: str) -> "CaseBrief":
        """Load a case brief from a LaTeX file."""
        log.debug(f"Loading case brief from {filename}")
        with open(filename, "r") as f:
            content = f.read()
            # Here you would parse the content to extract the case brief details
            # This is a placeholder implementation
            regex = r"\\NewBrief{subject=\{(.*?)\},\n\s*plaintiff=\{(.*?)\},\n\s*defendant=\{(.*?)\},\n\s*citation=\{(.*?)\},\n\s*course=\{(.*?)\},\n\s*facts=\{(.*?)\},\n\s*procedure=\{(.*?)\},\n\s*issue=\{(.*?)\},\n\s*holding=\{(.*?)\},\n\s*principle=\{(.*?)\},\n\s*reasoning=\{(.*?)\},\n\s*opinions=\{(.*?)\},\n\s*label=\{case:(.*?)\},\n\s*notes=\{(.*?)\}"
            match = re.search(regex, content, re.DOTALL)
            if match:
                subjects = [
                    Subject(s.strip()) for s in match.group(1).split(",") if s.strip()
                ]
                plaintiff = match.group(2).strip()
                defendant = match.group(3).strip()
                citation = tex_unescape(match.group(4).strip())
                course = match.group(5).strip()
                facts = tex_unescape(
                    match.group(6).strip()
                )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
                # Regex replace existing citations with the CITE(\1)
                citation_regex = r"\\hyperref\[case:(.*?)\]\{\\textit\{(.*?)\}\}"
                facts = re.sub(citation_regex, r"CITE(\1)", facts)
                procedure = tex_unescape(
                    match.group(7).strip()
                )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
                # Regex replace existing citations with the CITE(\1)
                procedure = re.sub(citation_regex, r"CITE(\1)", procedure)
                issue = tex_unescape(
                    match.group(8).strip()
                )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
                # Regex replace existing citations with the CITE(\1)
                issue = re.sub(citation_regex, r"CITE(\1)", issue)
                holding = match.group(9).strip()
                principle = tex_unescape(match.group(10).strip())
                reasoning = tex_unescape(
                    match.group(11).strip()
                )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
                opinions = [
                    Opinion(
                        o.strip().split(":")[0].strip(), o.strip().split(":")[1].strip()
                    )
                    for o in re.sub(
                        citation_regex, r"CITE(\1)", tex_unescape(match.group(12))
                    )
                    if o.strip()
                ]
                label = Label(match.group(13).strip())
                notes = tex_unescape(
                    match.group(14).strip()
                )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
            else:
                log.error(
                    f"Failed to parse case brief from {filename}. The file may not be in the correct format."
                )
                raise RuntimeError(
                    f"Failed to parse case brief from {filename}. The file may not be in the correct format."
                )

            return CaseBrief(
                subjects,
                plaintiff,
                defendant,
                citation,
                course,
                facts,
                procedure,
                issue,
                holding,
                principle,
                reasoning,
                opinions,
                label,
                notes,
            )

    @staticmethod
    def load_from_sql(case_label: str) -> "CaseBrief":
        """Load a case brief from the SQL database by its label."""
        log.debug(f"Loading case brief from SQL with label {case_label}")
        conn = sqlite3.connect(str(global_vars.sql_dst_file))
        conn.execute("PRAGMA foreign_keys = ON")
        curr = conn.cursor()
        curr.execute(
            "SELECT plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, label, notes FROM Cases WHERE label = ?",
            (case_label,),
        )
        cur_case = curr.fetchone()
        if not cur_case:
            log.error(f"No case brief found with label '{case_label}' in the database.")
            raise RuntimeError(
                f"No case brief found with label '{case_label}' in the database."
            )
        curr.execute(
            "SELECT opinion_author, opinion_text FROM CaseOpinionsView WHERE case_label = ?",
            (case_label,),
        )
        opinions = [Opinion(*opinion) for opinion in curr.fetchall()]
        curr.execute(
            "SELECT subject_name FROM CaseSubjectsView WHERE case_label = ?",
            (case_label,),
        )
        subjects = [Subject(subject[-1]) for subject in curr.fetchall()]
        # Assuming the database schema matches the order of fields in CaseBrief
        case_brief = CaseBrief(
            subject=subjects,
            opinions=opinions,
            plaintiff=cur_case[0],
            defendant=cur_case[1],
            citation=cur_case[2],
            course=cur_case[3],
            facts=cur_case[4],
            procedure=cur_case[5],
            issue=cur_case[6],
            holding=cur_case[7],
            principle=cur_case[8],
            reasoning=cur_case[9],
            label=Label(cur_case[10]),
            notes=cur_case[11],
        )
        return case_brief

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, CaseBrief):
            return False
        return self.label.text == value.label.text


class CaseBriefs:
    """A class to manage multiple case briefs."""

    def __init__(self):
        self.case_briefs: list[CaseBrief] = []
        self.sql = SQL(db_path=str(global_vars.sql_dst_file))
        self.latex = Latex()

    def reload_cases_tex(self) -> None:
        """Reload all case briefs from the ./Cases directory."""
        log.info("Reloading case briefs from TeX files...")
        case_path = strict_path(global_vars.cases_dir)
        for filename in os.listdir(case_path):
            if filename.endswith(".tex"):
                brief = self.latex.loadBrief(os.path.join(case_path, filename))
                if brief not in self.case_briefs:
                    log.trace(f"Adding case brief: {brief.title}")
                    self.case_briefs.append(brief)

    def reload_cases_sql(self) -> None:
        labels: list[str] = self.sql.fetchCaseLabels()
        for label in labels:
            case_brief = self.sql.loadBrief(label)
            if case_brief not in self.case_briefs:
                self.add_case_brief(case_brief)

    def add_case_brief(self, case_brief: CaseBrief) -> None:
        """Add a case brief to the collection."""
        self.case_briefs.append(case_brief)

    def update_case_brief(self, case_brief: CaseBrief) -> None:
        """Update an existing case brief in the collection."""
        for index, cb in enumerate(self.case_briefs):
            if cb.label == case_brief.label:
                self.case_briefs[index] = case_brief
                return
        log.error(f"Case brief with label '{case_brief.label.text}' not found.")
        raise ValueError(f"Case brief with label '{case_brief.label.text}' not found.")

    def remove_case_brief(self, case_brief: CaseBrief) -> None:
        """Remove a case brief from the collection."""
        self.case_briefs.remove(case_brief)

    def get_case_briefs(self) -> list[CaseBrief]:
        """Get all case briefs in the collection."""
        return sorted(self.case_briefs, key=lambda cb: cb.label.text)

    """
    def reload_cases_tex(self) -> None:
        \"""Reload all case briefs from the ./Cases directory.""\"
        log.info("Reloading case briefs from TeX files...")
        for filename in os.listdir(os.path.join(base_dir, "Cases")):
            if filename.endswith(".tex"):
                brief = CaseBrief.load_from_file(os.path.join(base_dir, "Cases", filename))
                if brief not in self.case_briefs:
                    log.trace(f"Adding case brief: {brief.title}")
                    self.case_briefs.append(brief)"""

    """
    def reload_cases_sql(self) -> None:
        \"""Reload all case briefs from the SQL database.""\"
        log.info("Reloading case briefs from SQL database...")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        curr = conn.cursor()
        curr.execute("SELECT label FROM Cases")
        labels = [Label(row[0]) for row in curr.fetchall()]
        for label in labels:
            case_brief = CaseBrief.load_from_sql(label.text)
            if case_brief not in self.case_briefs:
                self.add_case_brief(case_brief)
        conn.close()"""

    """
    def cite_case_brief(self, case_brief_label: str) -> str:
        \"""Cite a case brief by its label.""\"
        log.debug(f"Citing case brief with label: {case_brief_label}")
        for case_brief in self.case_briefs:
            log.trace(f"Checking case brief: {case_brief.label.text} against {case_brief_label}")
            if case_brief.label == case_brief_label:
                return f"\\hyperref[case:{case_brief.label.text}]{{\\textit{{{case_brief.title}}}}}"
        return f"CITE({case_brief_label})"  # Fallback if case brief not found
    
    def load_cases_tex(self, path: str) -> None:
        "\""Load all case briefs from the specified directory."\""
        log.info(f"Loading case briefs from TeX files in {path}...")
        for filename in os.listdir(path):
            if filename.endswith(".tex"):
                full_path = os.path.join(path, filename)
                brief = CaseBrief.load_from_file(full_path)
                if brief not in self.case_briefs:
                    log.trace(f"Adding case brief: {brief.title}")
                    self.case_briefs.append(brief)

    
    def load_cases_sql(self) -> None:
        ""\"Load all case briefs from the SQL database.""\"
        log.info("Loading case briefs from SQL database...")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        curr = conn.cursor()
        curr.execute("SELECT label FROM Cases")
        labels = [Label(row[0]) for row in curr.fetchall()]
        for label in labels:
            log.trace(f"Loading case brief for label: {label.text}")
            self.add_case_brief(CaseBrief.load_from_sql(label.text))
        conn.close()

    def save_cases_sql(self) -> None:
        log.info("Saving all case briefs to SQL database")
        for case in self.case_briefs:
            case.to_sql()"""


def reload_subjects(case_briefs: list[CaseBrief]) -> list[Subject]:
    log.debug("Reloading subjects from case briefs")
    subjects: list[Subject] = []
    for case_brief in case_briefs:
        for subject in case_brief.subject:
            if subject not in subjects:
                subjects.append(subject)
    return subjects


def reload_labels(case_briefs: list[CaseBrief]) -> list[Label]:
    log.debug("Reloading labels from case briefs")
    labels: list[Label] = []
    for case_brief in case_briefs:
        if case_brief.label not in labels:
            labels.append(case_brief.label)
    return labels


global case_briefs, subjects, labels
case_briefs = CaseBriefs()
subjects = reload_subjects(case_briefs.get_case_briefs())
labels = reload_labels(case_briefs.get_case_briefs())
