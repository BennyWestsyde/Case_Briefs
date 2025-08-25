CREATE TABLE IF NOT EXISTS "Subjects" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS "Opinions" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT NOT NULL,
    opinion_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "Cases" (
    plaintiff TEXT,
    defendant TEXT,
    title TEXT GENERATED ALWAYS AS (plaintiff || ' v. ' || defendant) STORED,
    citation TEXT,
    course TEXT,
    facts TEXT,
    "procedure" TEXT,
    issue TEXT,
    holding TEXT,
    principle TEXT,
    reasoning TEXT,
    label TEXT PRIMARY KEY,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS "CaseSubjects" (
    case_label TEXT REFERENCES "Cases"(label),
    subject_id INTEGER REFERENCES "Subjects"(id),
    PRIMARY KEY (case_label, subject_id)
);

CREATE TABLE IF NOT EXISTS "CaseOpinions" (
    case_label TEXT REFERENCES "Cases"(label),
    opinion_id INTEGER REFERENCES "Opinions"(id),
    PRIMARY KEY (case_label, opinion_id)
);

CREATE VIEW IF NOT EXISTS "CaseSubjectsView" AS
SELECT
    c.label AS case_label,
    s.id AS subject_id,
    s.name AS subject_name
FROM
    CaseSubjects cs
JOIN
    Cases c ON cs.case_label = c.label
JOIN
    Subjects s ON cs.subject_id = s.id;

CREATE VIEW IF NOT EXISTS "CaseOpinionsView" AS
SELECT
    c.label AS case_label,
    o.id AS opinion_id,
    o.author AS opinion_author,
    o.opinion_text AS opinion_text
FROM
    CaseOpinions co
JOIN
    Cases c ON co.case_label = c.label
JOIN
    Opinions o ON co.opinion_id = o.id;

CREATE VIEW IF NOT EXISTS "CaseDetailsView" AS
SELECT
    c.*,
    (
    SELECT GROUP_CONCAT(s.name, ', ')
    FROM CaseSubjects cs
    JOIN Subjects s ON cs.subject_id = s.id
    WHERE cs.case_label = c.label
    ) AS subjects,
    (
    SELECT GROUP_CONCAT(author || ': ' || opinion_text, '\n')
    FROM (
      SELECT DISTINCT o.author AS author, o.opinion_text AS opinion_text
      FROM CaseOpinions co
      JOIN Opinions o ON o.id = co.opinion_id
      WHERE co.case_label = c.label
      ORDER BY o.author, o.opinion_text
    )
  ) AS opinions
FROM
    Cases c
LEFT JOIN
    CaseOpinions co ON c.label = co.case_label
LEFT JOIN
    Opinions o ON co.opinion_id = o.id
LEFT JOIN
    CaseSubjects cs ON c.label = cs.case_label
LEFT JOIN
    Subjects s ON cs.subject_id = s.id
GROUP BY
    c.label;



CREATE TRIGGER IF NOT EXISTS trg_delete_case_opinions
BEFORE DELETE ON "Opinions"
FOR EACH ROW
BEGIN
    IF (SELECT COUNT(*) FROM CaseOpinions WHERE opinion_id = OLD.id) > 0 THEN
        SELECT RAISE(ABORT, 'Cannot delete opinion; it is referenced in CaseOpinions.');
    END IF;
END;

CREATE TRIGGER IF NOT EXISTS trg_delete_case_subjects
BEFORE DELETE ON "Subjects"
FOR EACH ROW
BEGIN
    IF (SELECT COUNT(*) FROM CaseSubjects WHERE subject_id = OLD.id) > 0 THEN
        SELECT RAISE(ABORT, 'Cannot delete subject; it is referenced in CaseSubjects.');
    END IF;
END;

