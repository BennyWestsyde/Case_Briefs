from pathlib import Path
from typing import List, TypedDict
import os
from Global_Vars import Global_Vars, global_vars
from cleanup import StructuredLogger, clean_dir
import re
import sqlite3
from PyQt6.QtCore import QProcess

from logger import Logged
from pathlib import Path
from typing import Union

from strict import strict_path


def tex_escape(input: str) -> str:
    """Escape special characters for LaTeX."""
    replacements: dict[str, str | int | None] = {
        "{": "\\{",
        "}": "\\}",
        "$": "\\$",
        "%": "\\%",
        "#": "\\#",
        "_": "\\_",
        "~": "\\textasciitilde{}",
        "^": "\\textasciicircum{}",
        "&": "\\&",
    }
    return (
        str.translate(input, str.maketrans(replacements))
        .replace("\n", r"\\" + "\n")
        .replace(". ", r".\ ")
        .replace("...", r"\ldots")
    )


def tex_unescape(input: str) -> str:
    """Unescape special characters for LaTeX."""
    replacements: dict[str, str | int | None] = {
        "\\{": "{",
        "\\}": "}",
        "\\$": "$",
        "\\%": "%",
        "\\#": "#",
        "\\_": "_",
        "\\textasciitilde{}": "~",
        "\\textasciicircum{}": "^",
        "\\&": "&",
    }
    return (
        str.translate(input, str.maketrans(replacements))
        .replace(r"\\" + "\n", "\n")
        .replace(r".\ ", ". ")
        .replace(r"\ldots", "...")
    )


SQLiteValue = Union[str, int, float, bytes, None]


class SQL(Logged):
    """A class to handle interaction with the database."""

    def __init__(self, config: Global_Vars):
        super().__init__(
            self.__class__.__name__, str(config.write_dir / "CaseBriefs.self.log")
        )
        self.global_vars = config
        self.db_path = self.global_vars.sql_dst_file
        self._ensure_db()
        self.connection = sqlite3.connect(self.db_path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.connection.cursor()

    def exists(self) -> bool:
        """Check if the database exists."""
        self.log.trace("Checking if database exists")
        return Path(self.db_path).exists()

    def _ensure_db(self) -> bool:
        """Ensure the database and tables exist."""
        if not self.exists():
            self.log.warning(f"Database not found, creating at {self.db_path}")
            with sqlite3.connect(str(self.db_path)) as conn:
                with open(
                    strict_path(self.global_vars.sql_create), "r", encoding="utf-8"
                ) as f:
                    conn.executescript(f.read())
            self.log.debug("Database created successfully")
            return True
        else:
            self.log.debug("Database found")
            return True

    @staticmethod
    def ensure_db(log: StructuredLogger, config: Global_Vars) -> bool:
        """Static method to ensure the database and tables exist."""
        relative_db_path = Path(config.sql_dst_file).relative_to(Path.cwd())
        if not Path(config.sql_dst_file).exists():
            log.warning(f"Database not found, creating at {relative_db_path}")
            with sqlite3.connect(config.sql_dst_file) as conn:
                with open(strict_path(config.sql_create), "r", encoding="utf-8") as f:
                    conn.executescript(f.read())
            log.debug("Database created successfully")
            return True
        else:
            log.debug("Database found")
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
        self.log.debug(f"Saving brief for case: {brief.citation}")
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
            self.log.trace("Deleting existing subjects and opinions")
            self.execute(
                "DELETE FROM CaseSubjects WHERE case_label = ?", (brief.label.text,)
            )
            self.execute(
                "DELETE FROM CaseOpinions WHERE case_label = ?", (brief.label.text,)
            )

            # Insert subjects
            for subject in brief.subjects:
                self.log.trace(f"Saving Subject: {subject.name}")
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
                self.log.trace(f"Saving Opinion By: {opinion.author}")
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
            self.log.error(f"Error saving case brief to database: {e}", e.__traceback__)

    def export_db_file(self, export_path: Path) -> None:
        """Export the entire database to a SQL file."""
        self.log.debug(f"Exporting database to {export_path}")
        sql_dump = self._export_db_str()
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(sql_dump)
        self.log.info(f"Database exported successfully to {export_path}")

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
        self.log.debug(f"Restoring database from {backup_path}")
        with open(backup_path, "r", encoding="utf-8") as f:
            db_str = f.read()
        self._restore_db_str(db_str)

    def _restore_db_str(self, db_str: str) -> None:
        """Restore the database from a SQL dump string."""
        self.log.debug(f"Restoring database from SQL dump")
        self.connection.executescript(db_str)
        self.commit()
        self.log.info(f"Database restored successfully")

    def loadBrief(self, case_label: str) -> "CaseBrief":
        """Load a case brief from the database by its label."""
        self.log.debug(f"Loading case brief from SQL with label {case_label}")
        self.execute(
            "SELECT plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, label, notes FROM Cases WHERE label = ?",
            (case_label,),
        )
        cur_case = self.cursor.fetchone()
        if not cur_case:
            self.log.error(
                f"No case brief found with label '{case_label}' in the database."
            )
            raise RuntimeError(
                f"No case brief found with label '{case_label}' in the database."
            )
        else:
            self.log.trace(f"Found case brief: {cur_case[-2]}")
        self.execute(
            "SELECT opinion_author, opinion_text FROM CaseOpinionsView WHERE case_label = ?",
            (case_label,),
        )
        opinions = [
            Opinion(opinion[0], opinion[1], config=self.global_vars)
            for opinion in self.cursor.fetchall()
        ]
        self.execute(
            "SELECT subject_name FROM CaseSubjectsView WHERE case_label = ?",
            (case_label,),
        )
        subjects = [
            Subject(subject[-1], self.global_vars) for subject in self.cursor.fetchall()
        ]
        # Assuming the database schema matches the order of fields in CaseBrief
        case_brief = CaseBrief(
            config=self.global_vars,
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
            label=Label(cur_case[10], self.global_vars),
            notes=cur_case[11],
        )
        return case_brief

    def cite_case_brief(self, label: str) -> str:
        """Generate a citation for a case brief."""
        self.log.debug(f"Citing case brief with label {label}")
        self.execute("SELECT title FROM Cases WHERE label = ?", (label,))
        title = self.cursor.fetchone()
        if not title:
            self.log.error(f"No case brief found with label '{label}' for citation.")
            return f"CITE({label})"
        return f"\\hyperref[case:{label}]{{\\textit{{{title[0]}}}}}"

    def fetchCaseLabels(self) -> list[str]:
        """Fetch all case labels from the database."""
        self.log.debug("Fetching case labels from SQL")
        self.execute("SELECT label FROM Cases")
        labels = [row[0] for row in self.cursor.fetchall()]
        return labels

    def addCaseSubject(self, subject: str, label: str) -> None:
        """Add a subject to a case label."""
        self.log.debug(f"Adding subject '{subject}' to case label {label}")
        # Check if subject exists in Subjects table
        self.execute("SELECT id FROM Subjects WHERE name = ?", (subject,))
        subject_id = self.cursor.fetchone()
        if not subject_id:
            self.log.info(
                f"Subject '{subject}' not found in Subjects table. Adding it."
            )
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
        self.log.debug("Fetching case subjects from SQL")
        self.execute("SELECT name FROM Subjects")
        subjects = [row[0] for row in self.cursor.fetchall()]
        return subjects

    def addCourse(self, course: str) -> None:
        """Add a course to the database."""
        self.log.debug(f"Adding course '{course}' to SQL")
        self.execute("INSERT INTO Courses (name) VALUES (?)", (course,))
        self.commit()

    def removeCourse(self, course: str) -> None:
        """Remove a course from the database."""
        self.log.debug(f"Removing course '{course}' from SQL")
        usage_count = self.execute(
            "SELECT COUNT(*) FROM Cases WHERE course = ?", (course,)
        ).fetchone()[0]
        if usage_count > 0:
            self.log.warning(
                f"Course '{course}' is still in use by {usage_count} cases."
            )
            return
        self.execute("DELETE FROM Courses WHERE name = ?", (course,))
        self.commit()

    def fetchCourses(self) -> list[str]:
        """Fetch all course names from the database."""
        self.log.debug("Fetching course names from SQL")
        self.execute("SELECT name FROM Courses")
        courses = [row[0] for row in self.cursor.fetchall()]
        return courses


class Latex(Logged):
    """A class to handle LaTeX document generation."""

    def __init__(self, config: Global_Vars):
        super().__init__(
            self.__class__.__name__, str(config.write_dir / "CaseBriefs.self.log")
        )
        self.global_vars = config
        self.engine_path: Path = self.global_vars.tinitex_binary
        self.tex_dir: Path = self.global_vars.cases_dir
        self.render_dir: Path = self.global_vars.cases_output_dir

    def _brief2Latex(self, brief: "CaseBrief") -> str:
        """Convert a CaseBrief object to its LaTeX representation."""
        plaintiff_str = tex_escape(brief.plaintiff)
        defendant_str = tex_escape(brief.defendant)
        citation_str = tex_escape(brief.citation)
        subjects_str = ", ".join(str(s) for s in brief.subjects)
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
        holding_str = tex_escape(brief.holding)
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
            plaintiff_str,
            defendant_str,
            citation_str,
            brief.course,
            facts_str,
            procedure_str,
            issue_str,
            holding_str,
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
                Subject(s.strip(), self.global_vars)
                for s in match.group(1).split(",")
                if s.strip()
            ]
            plaintiff = tex_unescape(match.group(2).strip())
            defendant = tex_unescape(match.group(3).strip())
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
            holding = tex_unescape(match.group(9).strip())
            principle = tex_unescape(match.group(10).strip())
            reasoning = tex_unescape(
                match.group(11).strip()
            )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
            opinions = [
                Opinion(
                    o.strip().split(":")[0].strip(),
                    o.strip().split(":")[1].strip(),
                    self.global_vars,
                )
                for o in re.sub(
                    citation_regex, r"CITE(\1)", tex_unescape(match.group(12))
                )
                if o.strip()
            ]
            label = Label(match.group(13).strip(), self.global_vars)
            notes = tex_unescape(
                match.group(14).strip()
            )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
        else:
            raise RuntimeError(
                f"Failed to parse case brief. The file may not be in the correct format."
            )

        return CaseBrief(
            config=self.global_vars,
            subject=subjects,
            plaintiff=plaintiff,
            defendant=defendant,
            citation=citation,
            course=course,
            facts=facts,
            procedure=procedure,
            issue=issue,
            holding=holding,
            principle=principle,
            reasoning=reasoning,
            opinions=opinions,
            label=label,
            notes=notes,
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
                self.log.error(f"Case brief is missing {key}.")
                return False
            if not isinstance(results[key], expected_type):
                self.log.error(
                    f"Case brief {key} is not of type {expected_type.__name__}."
                )
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
                self.log.error(f"Error compiling {tex_file} to PDF: {error_output}")
                raise RuntimeError(
                    f"Failed to compile {tex_file} to PDF. Check the LaTeX file for errors."
                )
            else:
                clean_dir(str(self.tex_dir))
            self.log.info(f"Compiled {tex_file} to {pdf_file}")
            return pdf_file
        except Exception as e:
            self.log.error(f"Error compiling {tex_file} to PDF: {e}")
            raise RuntimeError(
                f"Failed to compile {tex_file} to PDF. Check the LaTeX file for errors."
            )


class Subject(Logged):
    """A class to represent a legal subject."""

    def __init__(self, name: str, config: Global_Vars):
        self.global_vars = config
        super().__init__(
            self.__class__.__name__,
            str(self.global_vars.write_dir / "CaseBriefs.self.log"),
        )
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


class Label(Logged):
    """A class to represent the citable label of a case."""

    def __init__(self, label: str, config: Global_Vars):
        self.global_vars = config
        super().__init__(
            self.__class__.__name__,
            str(self.global_vars.write_dir / "CaseBriefs.self.log"),
        )
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


class Opinion(Logged):
    """A class to represent a court opinion."""

    def __init__(self, author: str, text: str, config: Global_Vars):
        self.global_vars = config
        super().__init__(
            self.__class__.__name__,
            str(self.global_vars.write_dir / "CaseBriefs.self.log"),
        )
        self.author = author
        self.text = text

    def __str__(self) -> str:
        return f"{self.author}: {self.text}\n"


class CaseBrief(Logged):
    """
    A class to manage case briefs.

    Attributes:
        config (Global_Vars): Configuration object containing global variables.
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
        config: Global_Vars,
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
        self.global_vars = config
        super().__init__(
            self.__class__.__name__, str(self.global_vars.write_dir / "CaseBriefs.log")
        )
        self.subjects = subject
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
        self.subjects.append(subject)

    def remove_subject(self, subject: Subject) -> None:
        """Remove a subject from the case brief."""
        self.subjects = [s for s in self.subjects if s != subject]

    def update_subject(self, old_subject: Subject, new_subject: Subject) -> None:
        """Update a subject in the case brief."""
        self.subjects = [new_subject if s == old_subject else s for s in self.subjects]

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
        return str(
            strict_path(self.global_vars.cases_output_dir) / f"{self.filename}.pdf"
        )

    def to_latex(self) -> str:
        """Generate a LaTeX representation of the case brief."""
        citation_str = tex_escape(self.citation)
        subjects_str = ", ".join(str(s) for s in self.subjects)
        opinions_str = ("\n").join(str(op) for op in self.opinions)
        opinions_str = tex_escape(
            opinions_str
        )  # .replace('\n', r'\\'+'\n').replace("$", r"\$")
        opinions_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(str(m.group(1))),
            opinions_str,
        )
        # Replace citations in facts, procedure, and issue with \hyperref[case:self.label]{\textit{self.title}}
        facts_str = tex_escape(
            self.facts
        )  # .replace('\n', r'\\'+'\n').replace("$", r"\$")
        facts_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(str(m.group(1))),
            facts_str,
        )
        procedure_str = tex_escape(self.procedure)
        procedure_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(str(m.group(1))),
            procedure_str,
        )
        issue_str = tex_escape(self.issue)
        issue_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(str(m.group(1))),
            issue_str,
        )
        principle_str = tex_escape(self.principle)
        reasoning_str = tex_escape(self.reasoning)
        notes_str = tex_escape(
            self.notes
        )  # .replace('\n', r'\\'+'\n').replace("$", r"\$")
        notes_str = re.sub(
            r"CITE\((.*?)\)",
            lambda m: case_briefs.sql.cite_case_brief(str(str(m.group(1)))),
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
        self.log.debug(f"Saving case brief '{self.label.text}' to SQL database")
        conn = sqlite3.connect(str(self.global_vars.sql_dst_file))
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
            self.log.debug("Deleting existing subjects and opinions")
            curr.execute(
                "DELETE FROM CaseSubjects WHERE case_label = ?", (self.label.text,)
            )
            curr.execute(
                "DELETE FROM CaseOpinions WHERE case_label = ?", (self.label.text,)
            )

            # Insert subjects
            for subject in self.subjects:
                self.log.trace("Saving Subject: ", subject.name)
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
                self.log.trace("Saving Opinion By: ", opinion.author)
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
            self.log.error(f"Error saving case brief to database: {e}")
        finally:
            conn.close()

    def save_to_file(self, filename: str) -> None:
        """Save the LaTeX representation of the case brief to a file."""
        with open(filename, "w") as f:
            f.write(self.to_latex())
        self.log.info(f"Saved Latex to {filename}")

    def compile_to_pdf(self) -> str | None:
        """Compile the LaTeX file to PDF."""
        tex_file = strict_path(self.global_vars.cases_dir) / f"{self.filename}.tex"
        case_briefs.latex.saveBrief(self)
        pdf_file = self.get_pdf_path()
        if os.path.exists(pdf_file):
            os.remove(pdf_file)
        try:
            process: QProcess = QProcess()
            program = self.global_vars.tinitex_binary
            program_exists = program.exists()
            if not program_exists:
                self.log.error(f"TeX program not found: {program}")
                return None
            # Determine the relative path from self.global_vars.cases_dir to self.global_vars.cases_output_dir
            relative_output_dir = os.path.relpath(
                self.global_vars.cases_output_dir, self.global_vars.cases_dir
            )
            cwd = os.getcwd()
            process.setWorkingDirectory(str(self.global_vars.cases_dir))
            arguments = [f"--output-dir={relative_output_dir}", str(tex_file)]
            process.setProgram(str(self.global_vars.tinitex_binary))
            process.setArguments(arguments)
            process.start()
            # process.start("pdflatex", ["-interaction=nonstopmode", "-output-directory=./Cases", tex_file]) # pyright: ignore[reportUnknownMemberType]
            process.waitForFinished()
            if (
                process.exitStatus() != QProcess.ExitStatus.NormalExit
                or process.exitCode() != 0
            ):
                error_output = process.readAllStandardError().data().decode()
                self.log.error(f"Error compiling {tex_file} to PDF: {error_output}")
                return None
            else:
                clean_dir(str(self.global_vars.cases_dir))
            self.log.info(f"Compiled {tex_file} to {pdf_file}")
            process.setWorkingDirectory(cwd)
            return pdf_file
        except Exception as e:
            self.log.error(f"Error compiling {tex_file} to PDF: {e}")
            raise RuntimeError(
                f"Failed to compile {tex_file} to PDF. Check the LaTeX file for errors."
            )

    # @staticmethod
    # def load_from_file(filename: str) -> "CaseBrief":
    #     """Load a case brief from a LaTeX file."""
    #     log = StructuredLogger("CaseBriefs", "TRACE", None, True, None, True, True)
    #     log.debug(f"Loading case brief from {filename}")
    #     with open(filename, "r") as f:
    #         content = f.read()
    #         # Here you would parse the content to extract the case brief details
    #         # This is a placeholder implementation
    #         regex = r"\\NewBrief{subject=\{(.*?)\},\n\s*plaintiff=\{(.*?)\},\n\s*defendant=\{(.*?)\},\n\s*citation=\{(.*?)\},\n\s*course=\{(.*?)\},\n\s*facts=\{(.*?)\},\n\s*procedure=\{(.*?)\},\n\s*issue=\{(.*?)\},\n\s*holding=\{(.*?)\},\n\s*principle=\{(.*?)\},\n\s*reasoning=\{(.*?)\},\n\s*opinions=\{(.*?)\},\n\s*label=\{case:(.*?)\},\n\s*notes=\{(.*?)\}"
    #         match = re.search(regex, content, re.DOTALL)
    #         if match:
    #             subjects = [
    #                 Subject(s.strip()) for s in match.group(1).split(",") if s.strip()
    #             ]
    #             plaintiff = match.group(2).strip()
    #             defendant = match.group(3).strip()
    #             citation = tex_unescape(match.group(4).strip())
    #             course = match.group(5).strip()
    #             facts = tex_unescape(
    #                 match.group(6).strip()
    #             )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
    #             # Regex replace existing citations with the CITE(\1)
    #             citation_regex = r"\\hyperref\[case:(.*?)\]\{\\textit\{(.*?)\}\}"
    #             facts = re.sub(citation_regex, r"CITE(\1)", facts)
    #             procedure = tex_unescape(
    #                 match.group(7).strip()
    #             )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
    #             # Regex replace existing citations with the CITE(\1)
    #             procedure = re.sub(citation_regex, r"CITE(\1)", procedure)
    #             issue = tex_unescape(
    #                 match.group(8).strip()
    #             )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
    #             # Regex replace existing citations with the CITE(\1)
    #             issue = re.sub(citation_regex, r"CITE(\1)", issue)
    #             holding = match.group(9).strip()
    #             principle = tex_unescape(match.group(10).strip())
    #             reasoning = tex_unescape(
    #                 match.group(11).strip()
    #             )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
    #             opinions = [
    #                 Opinion(
    #                     o.strip().split(":")[0].strip(), o.strip().split(":")[1].strip()
    #                 )
    #                 for o in re.sub(
    #                     citation_regex, r"CITE(\1)", tex_unescape(match.group(12))
    #                 )
    #                 if o.strip()
    #             ]
    #             label = Label(match.group(13).strip())
    #             notes = tex_unescape(
    #                 match.group(14).strip()
    #             )  # .replace(r'\\'+'\n', '\n').replace(r"\$", "$")
    #         else:
    #             log.error(
    #                 f"Failed to parse case brief from {filename}. The file may not be in the correct format."
    #             )
    #             raise RuntimeError(
    #                 f"Failed to parse case brief from {filename}. The file may not be in the correct format."
    #             )

    #         return CaseBrief(
    #             self.global_vars,
    #             subjects,
    #             plaintiff,
    #             defendant,
    #             citation,
    #             course,
    #             facts,
    #             procedure,
    #             issue,
    #             holding,
    #             principle,
    #             reasoning,
    #             opinions,
    #             label,
    #             notes,
    #         )

    # @staticmethod
    # def load_from_sql(case_label: str) -> "CaseBrief":
    #     """Load a case brief from the SQL database by its label."""
    #     log = StructuredLogger("CaseBriefs", "TRACE", None, True, None, True, True)
    #     log.debug(f"Loading case brief from SQL with label {case_label}")
    #     conn = sqlite3.connect(str(global_vars.sql_dst_file))
    #     conn.execute("PRAGMA foreign_keys = ON")
    #     curr = conn.cursor()
    #     curr.execute(
    #         "SELECT plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, label, notes FROM Cases WHERE label = ?",
    #         (case_label,),
    #     )
    #     cur_case = curr.fetchone()
    #     if not cur_case:
    #         log.error(f"No case brief found with label '{case_label}' in the database.")
    #         raise RuntimeError(
    #             f"No case brief found with label '{case_label}' in the database."
    #         )
    #     curr.execute(
    #         "SELECT opinion_author, opinion_text FROM CaseOpinionsView WHERE case_label = ?",
    #         (case_label,),
    #     )
    #     opinions = [Opinion(*opinion) for opinion in curr.fetchall()]
    #     curr.execute(
    #         "SELECT subject_name FROM CaseSubjectsView WHERE case_label = ?",
    #         (case_label,),
    #     )
    #     subjects = [Subject(subject[-1]) for subject in curr.fetchall()]
    #     # Assuming the database schema matches the order of fields in CaseBrief
    #     case_brief = CaseBrief(
    #         self.global_vars,
    #         subject=subjects,
    #         opinions=opinions,
    #         plaintiff=cur_case[0],
    #         defendant=cur_case[1],
    #         citation=cur_case[2],
    #         course=cur_case[3],
    #         facts=cur_case[4],
    #         procedure=cur_case[5],
    #         issue=cur_case[6],
    #         holding=cur_case[7],
    #         principle=cur_case[8],
    #         reasoning=cur_case[9],
    #         label=Label(cur_case[10]),
    #         notes=cur_case[11],
    #     )
    #     return case_brief

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, CaseBrief):
            return False
        return self.label.text == value.label.text


class CaseBriefs(Logged):
    """A class to manage multiple case briefs."""

    def __init__(self, config: Global_Vars):
        """Initialize a CaseBriefs object."""
        super().__init__(
            self.__class__.__name__, str(config.write_dir / "CaseBriefs.self.log")
        )
        self.global_vars: Global_Vars = config
        self.case_briefs: list[CaseBrief] = []
        self.sql = SQL(self.global_vars)
        self.latex = Latex(self.global_vars)

    @property
    def subjects(self) -> list[Subject]:
        """Get all subjects from the case briefs."""
        return [subject for cb in self.case_briefs for subject in cb.subjects]

    def reload_cases_tex(self) -> None:
        """Reload all case briefs from the ./Cases directory."""
        self.log.info("Reloading case briefs from TeX files...")
        case_path = strict_path(self.global_vars.cases_dir)
        for filename in os.listdir(case_path):
            if filename.endswith(".tex"):
                brief = self.latex.loadBrief(os.path.join(case_path, filename))
                if brief not in self.case_briefs:
                    self.log.trace(f"Adding case brief: {brief.title}")
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
        self.log.error(f"Case brief with label '{case_brief.label.text}' not found.")
        raise ValueError(f"Case brief with label '{case_brief.label.text}' not found.")

    def remove_case_brief(self, case_brief: CaseBrief) -> None:
        """Remove a case brief from the collection."""
        self.case_briefs.remove(case_brief)

    def get_case_briefs(self) -> list[CaseBrief]:
        """Get all case briefs in the collection."""
        return sorted(self.case_briefs, key=lambda cb: cb.label.text)


global case_briefs
case_briefs = CaseBriefs(global_vars)
