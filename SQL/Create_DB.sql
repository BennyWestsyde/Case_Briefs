CREATE TABLE IF NOT EXISTS "Subject" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS "Opinion" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT NOT NULL,
    opinion_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "Case" (
    subject_ids INTEGER[] REFERENCES "Subjects"(id),
    plaintiff TEXT,
    defendant TEXT,
    title TEXT GENERATED ALWAYS AS (plaintiff || ' v. ' || defendant) STORED,
    citation TEXT,
    course TEXT,
    facts TEXT,
    procedure TEXT,
    issue TEXT,
    holding TEXT,
    principle TEXT,
    reasoning TEXT,
    opinions INTEGER[] REFERENCES "Opinion"(id),
    label TEXT PRIMARY KEY,
    notes TEXT
);

