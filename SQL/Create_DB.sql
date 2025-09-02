-- === TABLES ===
DROP TABLE IF EXISTS "Courses";
CREATE TABLE "Courses" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL UNIQUE
);
INSERT INTO "Courses" (name) VALUES
    ('Contracts'),
    ('Torts'),
    ('Civil Procedure'),
    ('Legal Practice');

DROP TABLE IF EXISTS "Subjects";
CREATE TABLE "Subjects" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL UNIQUE
);

DROP TABLE IF EXISTS "Opinions";
CREATE TABLE "Opinions" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT NOT NULL,
    opinion_text TEXT NOT NULL
);

DROP TABLE IF EXISTS "Cases";
CREATE TABLE "Cases" (
    plaintiff TEXT,
    defendant TEXT,
    title TEXT GENERATED ALWAYS AS (plaintiff || ' v. ' || defendant) STORED,
    citation TEXT,
    course TEXT REFERENCES "Courses"(name),
    facts TEXT,
    "procedure" TEXT,
    issue TEXT,
    holding TEXT,
    principle TEXT,
    reasoning TEXT,
    label TEXT PRIMARY KEY,
    notes TEXT
);

DROP TABLE IF EXISTS "CaseSubjects";
CREATE TABLE "CaseSubjects" (
    case_label TEXT REFERENCES "Cases"(label),
    subject_id INTEGER REFERENCES "Subjects"(id),
    PRIMARY KEY (case_label, subject_id)
);

DROP TABLE IF EXISTS "CaseOpinions";
CREATE TABLE "CaseOpinions" (
    case_label TEXT REFERENCES "Cases"(label),
    opinion_id INTEGER REFERENCES "Opinions"(id),
    PRIMARY KEY (case_label, opinion_id)
);

-- === VIEWS ===
DROP VIEW IF EXISTS "CaseSubjectsView";
CREATE VIEW "CaseSubjectsView" AS
SELECT
    c.label AS case_label,
    s.id    AS subject_id,
    s.name  AS subject_name
FROM CaseSubjects cs
JOIN Cases    c ON cs.case_label = c.label
JOIN Subjects s ON cs.subject_id = s.id;

DROP VIEW IF EXISTS "CaseOpinionsView";
CREATE VIEW "CaseOpinionsView" AS
SELECT
    c.label      AS case_label,
    o.id         AS opinion_id,
    o.author     AS opinion_author,
    o.opinion_text
FROM CaseOpinions co
JOIN Cases    c ON co.case_label = c.label
JOIN Opinions o ON co.opinion_id = o.id;

DROP VIEW IF EXISTS "CaseDetailsView";
CREATE VIEW "CaseDetailsView" AS
SELECT
    c.*,
    (
      SELECT GROUP_CONCAT(s.name, ', ')
      FROM CaseSubjects cs
      JOIN Subjects s ON s.id = cs.subject_id
      WHERE cs.case_label = c.label
    ) AS subjects,
    (
      SELECT GROUP_CONCAT(author || ': ' || opinion_text, CHAR(10))
      FROM (
        SELECT DISTINCT o.author AS author, o.opinion_text AS opinion_text
        FROM CaseOpinions co
        JOIN Opinions o ON o.id = co.opinion_id
        WHERE co.case_label = c.label
        ORDER BY o.author, o.opinion_text
      )
    ) AS opinions
FROM Cases c;

-- === TRIGGERS ===
-- Use WHEN + RAISE(); no IF blocks; no IF NOT EXISTS
DROP TRIGGER IF EXISTS trg_delete_case_opinions;
CREATE TRIGGER trg_delete_case_opinions
BEFORE DELETE ON "Opinions"
FOR EACH ROW
WHEN (SELECT COUNT(*) FROM CaseOpinions WHERE opinion_id = OLD.id) > 0
BEGIN
    SELECT RAISE(ABORT, 'Cannot delete opinion; it is referenced in CaseOpinions.');
END;

DROP TRIGGER IF EXISTS trg_delete_case_subjects;
CREATE TRIGGER trg_delete_case_subjects
BEFORE DELETE ON "Subjects"
FOR EACH ROW
WHEN (SELECT COUNT(*) FROM CaseSubjects WHERE subject_id = OLD.id) > 0
BEGIN
    SELECT RAISE(ABORT, 'Cannot delete subject; it is referenced in CaseSubjects.');
END;
