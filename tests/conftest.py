import sys
import os
# Ensure project root is on sys.path for module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from pathlib import Path
from DataClasses import CaseBriefData, Label, Opinion, Subject


@pytest.fixture
def sample_subjects():
    return [Subject("Torts"), Subject("Contracts")]


@pytest.fixture
def sample_opinions():
    return [Opinion("Judge A", "Agrees with majority"), Opinion("Judge B", "Dissents")]


@pytest.fixture
def sample_brief(sample_subjects, sample_opinions):
    return CaseBriefData(
        plaintiff="Alice & Co.",
        defendant="Bob_Inc",
        citation="123 U.S. 456 (1890)",
        course="1L Torts",
        facts="Alice sued Bob. CITE(AnotherCase).",
        procedure="Trial court granted summary judgment.",
        issue="Whether negligence occurred?",
        holding="Yes, negligence occurred.",
        principle="Duty, breach, causation, damages.",
        reasoning="Because facts show breach...",
        label=Label("Alice_v_Bob"),
        notes="Important case with $symbols$ and %percent%",
        subjects=sample_subjects,
        opinions=sample_opinions,
    )


@pytest.fixture
def tmp_tree(tmp_path: Path):
    # Create a temp directory structure akin to the app layout
    res = tmp_path / "res"
    write = tmp_path / "write"
    for p in (res, write):
        p.mkdir(parents=True, exist_ok=True)
    # also create required sub-dirs for codecs/catalog
    (write / "Cases").mkdir(parents=True, exist_ok=True)
    (write / "Cases" / "Output").mkdir(parents=True, exist_ok=True)
    (write / "tex_src").mkdir(parents=True, exist_ok=True)
    # create a dummy master tex
    master = write / "tex_src" / "CaseBriefs.tex"
    master.write_text("% dummy master", encoding="utf-8")
    return {"res": res, "write": write, "master": master}
