from pathlib import Path
import sqlite3


def qident(name: str) -> str:
    # Quote identifiers with double quotes, escape internal quotes
    return '"' + name.replace('"', '""') + '"'


def export_db_file(db_path: Path) -> str:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
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
        for r in cur.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    tables.sort(key=lambda t: table_order_map.get(t, 100))

    parts: list[str] = [
        "-- Exported SQLite data (data only)",
        "PRAGMA foreign_keys=OFF;",
        "BEGIN TRANSACTION;",
    ]

    for table in tables:
        # Skip hidden/generated columns (hidden!=0)
        cols = cur.execute(f"PRAGMA table_xinfo({qident(table)})").fetchall()
        colnames = [c[1] for c in cols if c[-1] == 0]  # hidden flag is last field

        if not colnames:
            continue

        sel_cols = ", ".join(qident(c) for c in colnames)
        qvals = lambda v: cur.execute("SELECT quote(?)", (v,)).fetchone()[  # type: ignore
            0
        ]  # pyright: ignore[reportUnknownArgumentType]

        for row in cur.execute(f"SELECT {sel_cols} FROM {qident(table)}").fetchall():
            values = ", ".join(qvals(row[i]) for i in range(len(colnames)))
            parts.append(f"INSERT INTO {qident(table)} ({sel_cols}) VALUES ({values});")

    parts += ["COMMIT;", "PRAGMA foreign_keys=ON;"]
    con.close()
    return "\n".join(parts)


if __name__ == "__main__":
    db = Path(__file__).parent / "SQL" / "Cases.sqlite"
    out = Path("exported_db.sql")
    out.write_text(export_db_file(db), encoding="utf-8")
