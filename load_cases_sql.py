from main import CaseBriefs
import sqlite3



if __name__ == "__main__":
    connect = sqlite3.connect("SQL/Cases.sqlite")
    cursor = connect.cursor()
    cases = CaseBriefs()
    cases.load_case_briefs("Cases")
    for case in cases.case_briefs:
        # Load the Subjects into the database
        subject_ids: list[int] = []
        for subject in case.subject:
            cursor.execute("INSERT OR IGNORE INTO Subjects (name) VALUES (?)", (subject.name,))
            connect.commit()
            cursor.execute("SELECT id FROM Subjects WHERE name = ?", (subject.name,))
            subject_id = cursor.fetchone()[0]
            subject_ids.append(subject_id)
        # Load opinions into the database
        opinion_ids: list[int] = []
        for opinion in case.opinions:
            cursor.execute("INSERT OR IGNORE INTO Opinions (author, opinion_text) VALUES (?, ?)", (opinion.author, opinion.text))
            connect.commit()
            cursor.execute("SELECT id FROM Opinions WHERE author = ? AND opinion_text = ?", (opinion.author, opinion.text))
            opinion_id = cursor.fetchone()[0]
            opinion_ids.append(opinion_id)
        # Load case brief into the database
        cursor.execute("""
            INSERT OR REPLACE INTO Cases (
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
                label,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case.plaintiff,
            case.defendant,
            case.citation,
            case.course,
            case.facts,
            case.procedure,
            case.issue,
            case.holding,
            case.principle,
            case.reasoning,
            case.label.text,
            case.notes
        ))
        connect.commit()

        # Load CaseSubjects
        for subject_id in subject_ids:
            cursor.execute("INSERT OR IGNORE INTO CaseSubjects (case_label, subject_id) VALUES (?, ?)", (case.label.text, subject_id))
        connect.commit()

        # Load CaseOpinions
        for opinion_id in opinion_ids:
            cursor.execute("INSERT OR IGNORE INTO CaseOpinions (case_label, opinion_id) VALUES (?, ?)", (case.label.text, opinion_id))
        connect.commit()
