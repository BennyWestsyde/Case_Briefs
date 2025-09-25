from DataClasses import Subject, Label, Opinion, CaseBriefData


def test_subject_str_eq_repr():
    s1 = Subject("Torts")
    s2 = Subject("Torts")
    s3 = Subject("Contracts")
    assert str(s1) == "Torts"
    assert s1 == s2
    assert s1 != s3
    assert s1 == "Torts"
    assert repr(s1) == "Subject(name=Torts)"


def test_label_str_eq_repr():
    l1 = Label("Alice_v_Bob")
    l2 = Label("Alice_v_Bob")
    l3 = Label("Carol_v_Dave")
    assert str(l1) == "Alice_v_Bob"
    assert l1 == l2
    assert l1 != l3
    assert l1 == "Alice_v_Bob"
    assert repr(l1) == "Label(label=Alice_v_Bob)"


def test_opinion_str_eq_repr():
    o1 = Opinion("Judge A", "Concurs")
    o2 = Opinion("Judge A", "Concurs")
    o3 = Opinion("Judge B", "Dissents")
    assert str(o1) == "Judge A: Concurs\n"
    assert o1 == o2
    assert o1 != o3
    assert o1 == "Judge A: Concurs\n"
    assert repr(o1) == "Opinion(author=Judge A, text=Concurs)"


def test_casebrief_properties_and_asdict():
    data = CaseBriefData(
        plaintiff="Alice",
        defendant="Bob",
        citation="123 U.S. 456 (1890)",
        course="Torts",
        facts="Facts",
        procedure="Procedure",
        issue="Issue",
        holding="Holding",
        principle="Principle",
        reasoning="Reasoning",
        label=Label("Alice_v_Bob"),
        notes="Notes",
        subjects=[Subject("Torts")],
        opinions=[Opinion("Judge A", "Concurs")],
    )
    assert data.title == "Alice v. Bob"
    assert data.filename == "Alice_V_Bob"
    d = data.asdict()
    assert d["plaintiff"] == "Alice"
    assert d["label"] == data.label
    assert d["subjects"] == data.subjects
    assert d["opinions"] == data.opinions
