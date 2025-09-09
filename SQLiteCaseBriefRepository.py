from DataClasses import CaseBriefData, Label, Opinion, Subject
from logger import StructuredLogger


import sqlite3
from pathlib import Path


class SQLiteCaseBriefRepository:
    def __init__(self, db_path: Path, schema_sql_path: Path, logger: StructuredLogger):
        self.db_path = db_path
        self.schema_sql_path = schema_sql_path
        self.log = logger.getChildLogger("SQLiteCaseBriefRepository")
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def ensure_db(self) -> None:
        if not self.db_path.exists():
            self.log.warning("Database not found, creating at %s", self.db_path)
            with sqlite3.connect(self.db_path) as c, open(
                self.schema_sql_path, "r", encoding="utf-8"
            ) as f:
                c.executescript(f.read())
            self.log.debug("Database created")

    def list_labels(self) -> list[str]:
        cur = self.conn.execute("SELECT label FROM Cases ORDER BY label ASC")
        return [r[0] for r in cur.fetchall()]

    def list_courses(self) -> list[str]:
        cur = self.conn.execute("SELECT DISTINCT course FROM Cases ORDER BY course ASC")
        return [r[0] for r in cur.fetchall() if r[0]]

    def list_subjects(self) -> list[str]:
        cur = self.conn.execute(
            "SELECT DISTINCT subject_name FROM CaseSubjectsView ORDER BY subject_name ASC"
        )
        return [r[0] for r in cur.fetchall() if r[0]]

    def get(self, label: str) -> CaseBriefData:
        self.log.debug("Loading case brief: %s", label)
        cur = self.conn.execute(
            """
            SELECT plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, notes
            FROM Cases WHERE label = ?
        """,
            (label,),
        )
        row = cur.fetchone()
        if not row:
            raise KeyError(f"Case '{label}' not found")

        cur = self.conn.execute(
            "SELECT subject_name FROM CaseSubjectsView WHERE case_label = ?", (label,)
        )
        subjects = [Subject(r[0]) for r in cur.fetchall()]

        cur = self.conn.execute(
            "SELECT opinion_author, opinion_text FROM CaseOpinionsView WHERE case_label = ?",
            (label,),
        )
        opinions = [Opinion(a, t) for a, t in cur.fetchall()]

        return CaseBriefData(
            label=Label(label),
            plaintiff=row[0],
            defendant=row[1],
            citation=row[2],
            course=row[3],
            facts=row[4],
            procedure=row[5],
            issue=row[6],
            holding=row[7],
            principle=row[8],
            reasoning=row[9],
            notes=row[10],
            subjects=subjects,
            opinions=opinions,
        )

    def save(self, data: CaseBriefData) -> None:
        self.log.debug("Saving case brief: %s", data.label.text)
        c = self.conn
        try:
            c.execute(
                """
                INSERT INTO Cases (label, plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(label) DO UPDATE SET
                  plaintiff=excluded.plaintiff, defendant=excluded.defendant, citation=excluded.citation,
                  course=excluded.course, facts=excluded.facts, procedure=excluded.procedure, issue=excluded.issue,
                  holding=excluded.holding, principle=excluded.principle, reasoning=excluded.reasoning, notes=excluded.notes
            """,
                (
                    data.label.text,
                    data.plaintiff,
                    data.defendant,
                    data.citation,
                    data.course,
                    data.facts,
                    data.procedure,
                    data.issue,
                    data.holding,
                    data.principle,
                    data.reasoning,
                    data.notes,
                ),
            )

            c.execute(
                "DELETE FROM CaseSubjects WHERE case_label = ?", (data.label.text,)
            )
            for s in data.subjects:
                row = c.execute(
                    "SELECT id FROM Subjects WHERE name = ?", (s.name,)
                ).fetchone()
                sid = (
                    row[0]
                    if row
                    else c.execute(
                        "INSERT INTO Subjects (name) VALUES (?) RETURNING id", (s.name,)
                    ).fetchone()[0]
                )
                c.execute(
                    "INSERT INTO CaseSubjects (case_label, subject_id) VALUES (?, ?)",
                    (data.label.text, sid),
                )

            c.execute(
                "DELETE FROM CaseOpinions WHERE case_label = ?", (data.label.text,)
            )
            for op in data.opinions:
                row = c.execute(
                    "SELECT id FROM Opinions WHERE opinion_text = ?", (op.text,)
                ).fetchone()
                oid = (
                    row[0]
                    if row
                    else c.execute(
                        "INSERT INTO Opinions (author, opinion_text) VALUES (?, ?) RETURNING id",
                        (op.author, op.text),
                    ).fetchone()[0]
                )
                c.execute(
                    "INSERT INTO CaseOpinions (case_label, opinion_id) VALUES (?, ?)",
                    (data.label.text, oid),
                )

            c.commit()
        except sqlite3.Error as e:
            c.rollback()
            self.log.error("Error saving case %s: %s", data.label.text, e)
            raise

    # Optional: citation resolver port
    def cite_label(self, label: str) -> str:
        self.log.debug("Resolving citation for label: %s", label)
        cur = self.conn.execute("SELECT title FROM Cases WHERE label = ?", (label,))
        row = cur.fetchone()
        if not row:
            return f"CITE({label})"
        return f"\\hyperref[case:{label}]{{\\textit{{{row[0]}}}}}"

    def export_db_file(self, export_path: Path) -> None:
        """Export the entire database to a SQL file."""
        self.log.debug("Exporting database to %s", export_path)
        sql_dump = self._export_db_str()
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(sql_dump)
        self.log.info("Database exported successfully to %s", export_path)

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
            for r in self.conn.execute(
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
            cols = self.conn.execute(f"PRAGMA table_xinfo({qident(table)})").fetchall()
            colnames = [c[1] for c in cols if c[-1] == 0]  # hidden flag is last field

            if not colnames:
                continue

            sel_cols = ", ".join(qident(c) for c in colnames)

            def qvals(v: object) -> str:
                return str(self.conn.execute("SELECT quote(?)", (v,)).fetchone()[0])

            for row in self.conn.execute(
                f"SELECT {sel_cols} FROM {qident(table)}"
            ).fetchall():
                quoted_values: list[str] = [qvals(row[i]) for i in range(len(colnames))]
                values = ", ".join(quoted_values)
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
        self.conn.executescript(db_str)
        self.conn.commit()
        self.log.info(f"Database restored successfully")

    def add_course(self, course_name: str) -> None:
        """Add a new course to the Courses table."""
        self.log.debug(f"Adding course: {course_name}")
        try:
            self.conn.execute(
                "INSERT INTO Courses (name) VALUES (?) ON CONFLICT(name) DO NOTHING",
                (course_name,),
            )
            self.conn.commit()
            self.log.info(f"Course '{course_name}' added successfully")
        except sqlite3.Error as e:
            self.conn.rollback()
            self.log.error(f"Error adding course '{course_name}': {e}")
            raise

    def remove_course(self, course_name: str) -> None:
        """Remove a course from the Courses table."""
        self.log.debug(f"Removing course: {course_name}")
        try:
            self.conn.execute("DELETE FROM Courses WHERE name = ?", (course_name,))
            self.conn.commit()
            self.log.info(f"Course '{course_name}' removed successfully")
        except sqlite3.Error as e:
            self.conn.rollback()
            self.log.error(f"Error removing course '{course_name}': {e}")
            raise
