from pathlib import Path

import pytest

from DataClasses import CaseBriefData, Label, Opinion, Subject
from SQLiteCaseBriefRepository import SQLiteCaseBriefRepository
from logger import StructuredLogger


@pytest.fixture
def schema_path() -> Path:
    # Use project's canonical schema
    here = Path(__file__).resolve().parents[1]
    return here / "SQL" / "Create_DB.sql"


@pytest.fixture
def repo(tmp_path: Path, schema_path: Path):
    db = tmp_path / "cases.sqlite"
    log = StructuredLogger("test.repo", console=False)
    r = SQLiteCaseBriefRepository(db_path=db, schema_sql_path=schema_path, logger=log)
    r.ensure_db()
    # Seed a course referenced by test data to satisfy FK
    r.add_course("1L Torts")
    return r


def make_sample(label: str = "Alice_v_Bob", course: str = "1L Torts") -> CaseBriefData:
    return CaseBriefData(
        plaintiff="Alice",
        defendant="Bob",
        citation="123 U.S. 456 (1890)",
        course=course,
        facts="Alice sued Bob.",
        procedure="Trial court granted SJ.",
        issue="Negligence?",
        holding="Yes",
        principle="Duty-breach-causation-damages",
        reasoning="Because...",
        label=Label(label),
        notes="Important",
        subjects=[Subject("Torts"), Subject("Contracts")],
        opinions=[Opinion("Judge A", "Concurs"), Opinion("Judge B", "Dissents")],
    )


def test_save_and_get_round_trip(repo: SQLiteCaseBriefRepository):
    data = make_sample()
    repo.save(data)
    loaded = repo.get(data.label.text)

    assert loaded.title == data.title
    assert loaded.label == data.label
    assert set(s.name for s in loaded.subjects) == {"Torts", "Contracts"}
    assert any(op.author == "Judge B" for op in loaded.opinions)


def test_listings_and_courses(repo: SQLiteCaseBriefRepository):
    repo.save(make_sample("A_v_B"))
    repo.save(make_sample("C_v_D"))

    labels = repo.list_labels()
    assert labels == sorted(labels)
    assert set(labels) == {"A_v_B", "C_v_D"}

    # list_courses returns distinct non-empty courses from Cases
    courses = repo.list_courses()
    assert "1L Torts" in courses

    # list_subjects pulls from view
    subjects = repo.list_subjects()
    assert "Torts" in subjects and "Contracts" in subjects


def test_export_and_restore(repo: SQLiteCaseBriefRepository, tmp_path: Path):
    repo.save(make_sample("X_v_Y"))

    dump = tmp_path / "dump.sql"
    repo.export_db_file(dump)
    assert dump.exists()
    text = dump.read_text(encoding="utf-8")
    assert "INSERT OR REPLACE INTO" in text

    # Restore into a new repo
    log = StructuredLogger("test.restore", console=False)
    new_db = tmp_path / "new.sqlite"
    new_repo = SQLiteCaseBriefRepository(new_db, repo.schema_sql_path, log)
    new_repo.ensure_db()
    # ensure course exists before restoring rows referencing it
    new_repo.add_course("1L Torts")
    new_repo.restore_db_file(dump)

    assert "X_v_Y" in new_repo.list_labels()


def test_add_remove_course(repo: SQLiteCaseBriefRepository):
    # Adding a course with no referencing cases should be harmless
    repo.add_course("Property")
    assert "Property" not in repo.list_courses()  # not used by any case yet
    # Removing an unused course should succeed
    repo.remove_course("Property")
