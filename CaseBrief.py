from pathlib import Path
import subprocess
import sys
from typing import List, TypedDict, Union
import os
from extras.cleanup import clean_dir
import re
import sqlite3
from PyQt6.QtCore import QProcess

from extras.logger import StructuredLogger
log = StructuredLogger("CaseBrief","TRACE","CaseBriefs.log",True,None,True,True)

def tex_escape(input: str) -> str:
    """Escape special characters for LaTeX."""
    replacements = {
        '{': '\\{',
        '}': '\\}',
        '$': '\\$',
        '&': '\\&',
        '%': '\\%',
        '#': '\\#',
        '_': '\\_',
        '~': '\\textasciitilde{}',
        '^': '\\textasciicircum{}'
    }
    return str.translate(input, str.maketrans(replacements)).replace('\n', r'\\'+'\n').replace(". ", r'.\ ')

def tex_unescape(input:str) -> str:
    """Unescape special characters for LaTeX."""
    replacements = {
        '\\{': '{',
        '\\}': '}',
        '\\$': '$',
        '\\&': '&',
        '\\%': '%',
        '\\#': '#',
        '\\_': '_',
        '\\textasciitilde{}': '~',
        '\\textasciicircum{}': '^'
    }
    return str.translate(input, str.maketrans(replacements)).replace(r'\\'+'\n', '\n').replace(r'.\ ', ". ")




SQLiteValue = Union[str, int, float, bytes, None]

class SQL:
    """A class to handle interaction with the database."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.ensureDB()
        self.connection = sqlite3.connect(self.db_path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.connection.cursor()

    def ensureDB(self) -> None:
        """Ensure the database and tables exist."""
        log.debug("Ensuring database exists")
        if not os.path.exists(self.db_path):
            log.warning(f"Database not found, creating at {self.db_path}")
            proc: subprocess.CompletedProcess[str] = subprocess.run(
                ["sqlite3", str(self.db_path), " < " + os.path.join(base_dir, 'SQL', 'Create_DB.sql')],
                text=True,                # so input/stdout/stderr are str
                capture_output=True,      # capture stdout/stderr
                check=True,               # raise if returncode != 0
            )
            # If you really need the code, it's here:
            _rc: int = proc.returncode 
            if _rc != 0:
                log.critical(f"Failed to create database: {proc.stderr}")
                sys.exit(1)
            else:
                log.info("Database created successfully")
        else:
            log.info("Database found")

    def execute(self, query: str, params: tuple[SQLiteValue, ...] = ()) -> sqlite3.Cursor:
        """Execute a SQL query and return the cursor."""
        self.cursor.execute(query, params)
        return self.cursor

    def commit(self) -> None:
        """Commit the current transaction."""
        self.connection.commit()

    def close(self) -> None:
        """Close the database connection."""
        self.connection.close()
    
    def saveBrief(self, brief: 'CaseBrief') -> None:
        """Save a case brief to the database."""
        log.debug(f"Saving brief for case: {brief.citation}")
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
            self.execute(cases_table_query, (
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
                brief.notes
            ))

            # Clear existing subjects and opinions
            log.debug("Deleting existing subjects and opinions")
            self.execute("DELETE FROM CaseSubjects WHERE case_label = ?", (brief.label.text,))
            self.execute("DELETE FROM CaseOpinions WHERE case_label = ?", (brief.label.text,))

            # Insert subjects
            for subject in brief.subject:
                log.debug(f"Saving Subject: {subject.name}")
                self.execute("SELECT id FROM Subjects where name = ?", (subject.name,))
                subject_id = self.cursor.fetchone()
                if not subject_id:
                    self.execute("INSERT INTO Subjects (name) VALUES (?)", (subject.name,))
                    self.execute("SELECT id FROM Subjects where name = ?", (subject.name,))
                    subject_id = self.cursor.fetchone()
                subject_id = subject_id[0]
                self.execute("INSERT INTO CaseSubjects (case_label, subject_id) VALUES (?, ?)", (brief.label.text, subject_id,))

            # Insert opinions
            for opinion in brief.opinions:
                log.debug(f"Saving Opinion By: {opinion.author}")
                self.execute("SELECT id FROM Opinions where opinion_text = ?", (opinion.text,))
                opinion_id = self.cursor.fetchone()
                if not opinion_id:
                    self.execute("INSERT INTO Opinions (author, opinion_text) VALUES (?, ?)", (opinion.author, opinion.text,))
                    self.execute("SELECT id FROM Opinions where opinion_text = ?", (opinion.text,))
                    opinion_id = self.cursor.fetchone()
                opinion_id = opinion_id[0]
                self.execute("INSERT INTO CaseOpinions (case_label, opinion_id) VALUES (?, ?)", (brief.label.text, opinion_id))

            self.commit()
        except sqlite3.Error as e:
            self.connection.rollback()
            log.error(f"Error saving case brief to database: {e}")
        

    def loadBrief(self, case_label: str) -> 'CaseBrief':
        """Load a case brief from the database by its label."""
        log.debug(f"Loading case brief from SQL with label {case_label}")
        self.execute("SELECT plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, label, notes FROM Cases WHERE label = ?", (case_label,))
        cur_case = self.cursor.fetchone()
        if not cur_case:
            log.error(f"No case brief found with label '{case_label}' in the database.")
            raise RuntimeError(f"No case brief found with label '{case_label}' in the database.")
        self.execute("SELECT opinion_author, opinion_text FROM CaseOpinionsView WHERE case_label = ?", (case_label,))
        opinions = [Opinion(*opinion) for opinion in self.cursor.fetchall()]
        self.execute("SELECT subject_name FROM CaseSubjectsView WHERE case_label = ?", (case_label,))
        subjects = [Subject(subject[-1]) for subject in self.cursor.fetchall()]
        # Assuming the database schema matches the order of fields in CaseBrief
        case_brief = CaseBrief(subject=subjects,
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
                               label=Label(cur_case[10]),
                               notes=cur_case[11])
        return case_brief
    
    def cite_case_brief(self, label: str) -> str:
        """Generate a citation for a case brief."""
        log.debug(f"Citing case brief with label {label}")
        self.execute("SELECT title FROM Cases WHERE label = ?", (label,))
        title = self.cursor.fetchone()
        if not title:
            log.error(f"No case brief found with label '{label}' for citation.")
            return f"CITE({label})"
        return f"\\hyperref[case:{label}]{{\\textit{{{title[0]}}}}}"

    def fetchCaseLabels(self) -> list[str]:
        """Fetch all case labels from the database."""
        log.debug("Fetching case labels from SQL")
        self.execute("SELECT label FROM Cases")
        labels = [row[0] for row in self.cursor.fetchall()]
        return labels

    def addCaseSubject(self, subject: str, label: str) -> None:
        """Add a subject to a case label."""
        log.debug(f"Adding subject '{subject}' to case label {label}")
        # Check if subject exists in Subjects table
        self.execute("SELECT id FROM Subjects WHERE name = ?", (subject,))
        subject_id = self.cursor.fetchone()
        if not subject_id:
            log.info(f"Subject '{subject}' not found in Subjects table. Adding it.")
            self.execute("INSERT INTO Subjects (name) VALUES (?)", (subject,))
            self.commit()
            self.execute("SELECT id FROM Subjects WHERE name = ?", (subject,))
            subject_id = self.cursor.fetchone()
        self.execute("INSERT INTO CaseSubjects (case_label, subject_id) VALUES (?, ?)", (label, subject_id))
        self.commit()

    def fetchCaseSubjects(self) -> list[str]:
        """Fetch all case subjects from the database."""
        log.debug("Fetching case subjects from SQL")
        self.execute("SELECT name FROM Subjects")
        subjects = [row[0] for row in self.cursor.fetchall()]
        return subjects
    
class Latex:
    """A class to handle LaTeX document generation."""
    def __init__(self):
        self.engine_path: Path = Path(os.path.join(base_dir, "bin", "tinitex"))
        self.tex_dir: Path = Path(os.path.join(base_dir, "Cases"))
        self.render_dir: Path = Path(os.path.join(base_dir, "Render"))

    def _brief2Latex(self, brief: 'CaseBrief') -> str:
        """Convert a CaseBrief object to its LaTeX representation."""
        citation_str = tex_escape(brief.citation)
        subjects_str = ', '.join(str(s) for s in brief.subject)
        opinions_str = ('\n').join(str(op) for op in brief.opinions)
        opinions_str = tex_escape(opinions_str)#.replace('\n', r'\\'+'\n').replace("$", r"\$")
        opinions_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.sql.cite_case_brief(m.group(1)), opinions_str)
        # Replace citations in facts, procedure, and issue with \hyperref[case:self.label]{\textit{self.title}}
        facts_str = tex_escape(brief.facts)#.replace('\n', r'\\'+'\n').replace("$", r"\$")
        facts_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.sql.cite_case_brief(m.group(1)), facts_str)
        procedure_str = tex_escape(brief.procedure)
        procedure_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.sql.cite_case_brief(m.group(1)), procedure_str)
        issue_str = tex_escape(brief.issue)
        issue_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.sql.cite_case_brief(m.group(1)), issue_str)
        principle_str = tex_escape(brief.principle)
        reasoning_str = tex_escape(brief.reasoning)
        notes_str = tex_escape(brief.notes)#.replace('\n', r'\\'+'\n').replace("$", r"\$")
        notes_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.sql.cite_case_brief(m.group(1)), notes_str)

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
        """ % (subjects_str,
               brief.plaintiff,
               brief.defendant,
               citation_str,
               brief.course,
               facts_str,
               procedure_str,
               issue_str,
               brief.holding,
               principle_str,
               reasoning_str,
               opinions_str,
               brief.label,
               notes_str)

    def _latex2Brief(self, tex_content: str) -> 'CaseBrief':
        """Convert LaTeX content back to a CaseBrief object."""
        # Here you would parse the content to extract the case brief details
        # This is a placeholder implementation
        regex = r'\\NewBrief{subject=\{(.*?)\},\n\s*plaintiff=\{(.*?)\},\n\s*defendant=\{(.*?)\},\n\s*citation=\{(.*?)\},\n\s*course=\{(.*?)\},\n\s*facts=\{(.*?)\},\n\s*procedure=\{(.*?)\},\n\s*issue=\{(.*?)\},\n\s*holding=\{(.*?)\},\n\s*principle=\{(.*?)\},\n\s*reasoning=\{(.*?)\},\n\s*opinions=\{(.*?)\},\n\s*label=\{case:(.*?)\},\n\s*notes=\{(.*?)\}'
        match = re.search(regex, tex_content, re.DOTALL)
        if match:
            subjects = [Subject(s.strip()) for s in match.group(1).split(',') if s.strip()]
            plaintiff = match.group(2).strip()
            defendant = match.group(3).strip()
            citation = tex_unescape(match.group(4).strip())
            course = match.group(5).strip()
            facts = tex_unescape(match.group(6).strip())#.replace(r'\\'+'\n', '\n').replace(r"\$", "$")
            # Regex replace existing citations with the CITE(\1)
            citation_regex = r'\\hyperref\[case:(.*?)\]\{\\textit\{(.*?)\}\}'
            facts = re.sub(citation_regex, r'CITE(\1)', facts)
            procedure = tex_unescape(match.group(7).strip())#.replace(r'\\'+'\n', '\n').replace(r"\$", "$")
            # Regex replace existing citations with the CITE(\1)
            procedure = re.sub(citation_regex, r'CITE(\1)', procedure)
            issue = tex_unescape(match.group(8).strip())#.replace(r'\\'+'\n', '\n').replace(r"\$", "$")
            # Regex replace existing citations with the CITE(\1)
            issue = re.sub(citation_regex, r'CITE(\1)', issue)
            holding = match.group(9).strip()
            principle = tex_unescape(match.group(10).strip())
            reasoning = tex_unescape(match.group(11).strip())#.replace(r'\\'+'\n', '\n').replace(r"\$", "$")
            opinions = [Opinion(o.strip().split(":")[0].strip(), o.strip().split(":")[1].strip()) for o in re.sub(citation_regex, r'CITE(\1)', tex_unescape(match.group(12))) if o.strip()]
            label = Label(match.group(13).strip())
            notes = tex_unescape(match.group(14).strip())#.replace(r'\\'+'\n', '\n').replace(r"\$", "$")
        else:
            raise RuntimeError(f"Failed to parse case brief. The file may not be in the correct format.")

        return CaseBrief(subjects, plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, opinions, label, notes)


    def saveBrief(self, brief: 'CaseBrief') -> Path:
        tex_content = self._brief2Latex(brief)
        tex_file = self.tex_dir / f"{brief.filename}.tex"
        with tex_file.open("w") as f:
            f.write(tex_content)
        return tex_file

    def loadBrief(self, filename: str) -> 'CaseBrief':
        tex_file = self.tex_dir / f"{filename}.tex"
        if not tex_file.exists():
            raise FileNotFoundError(f"LaTeX file {tex_file} does not exist.")
        with tex_file.open("r") as f:
            tex_content = f.read()
        return self._latex2Brief(tex_content)

    def validateBrief(self, brief: 'CaseBrief') -> bool:
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
                log.error(f"Case brief is missing {key}.")
                return False
            if not isinstance(results[key], expected_type):
                log.error(f"Case brief {key} is not of type {expected_type.__name__}.")
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
                "--pdf-engine=pdflatex",                 # or xelatex/lualatex
                "--pdf-engine-opt=-shell-escape",        # <-- include the leading dash
                str(pdf_file)
            ]
            process.setProgram(str(self.engine_path))
            process.setArguments(args)
            process.start()
            process.waitForFinished()
            if process.exitStatus() != QProcess.ExitStatus.NormalExit or process.exitCode() != 0:
                error_output = process.readAllStandardError().data().decode()
                log.error(f"Error compiling {tex_file} to PDF: {error_output}")
                raise RuntimeError(f"Failed to compile {tex_file} to PDF. Check the LaTeX file for errors.")
            else:
                clean_dir(str(self.tex_dir))
            log.info(f"Compiled {tex_file} to {pdf_file}")
            return pdf_file
        except Exception as e:
            log.error(f"Error compiling {tex_file} to PDF: {e}")
            raise RuntimeError(f"Failed to compile {tex_file} to PDF. Check the LaTeX file for errors.")




class Subject:
    """A class to represent a legal subject."""
    def __init__(self, name: str):
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
    
class Label:
    """A class to represent the citable label of a case."""
    def __init__(self, label: str):
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
    
class Opinion:
    """A class to represent a court opinion."""
    def __init__(self, author: str, text: str):
        self.author = author
        self.text = text

    def __str__(self) -> str:
        return f"{self.author}: {self.text}\n"

class CaseBrief:
    """
    A class to manage case briefs.

    Attributes:
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
    def __init__(self, 
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
                 notes: str):
        """
        Initialize a CaseBrief object.

        Args:
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
        self.subject = subject
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
        self.subject.append(subject)

    def remove_subject(self, subject: Subject) -> None:
        """Remove a subject from the case brief."""
        self.subject = [s for s in self.subject if s != subject]

    def update_subject(self, old_subject: Subject, new_subject: Subject) -> None:
        """Update a subject in the case brief."""
        self.subject = [new_subject if s == old_subject else s for s in self.subject]

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
        return os.path.join(base_dir, "Cases", f"{self.filename}.pdf")

    
    def to_latex(self) -> str:
        """Generate a LaTeX representation of the case brief."""
        citation_str = tex_escape(self.citation)
        subjects_str = ', '.join(str(s) for s in self.subject)
        opinions_str = ('\n').join(str(op) for op in self.opinions)
        opinions_str = tex_escape(opinions_str)#.replace('\n', r'\\'+'\n').replace("$", r"\$")
        opinions_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.sql.cite_case_brief(m.group(1)), opinions_str)
        # Replace citations in facts, procedure, and issue with \hyperref[case:self.label]{\textit{self.title}}
        facts_str = tex_escape(self.facts)#.replace('\n', r'\\'+'\n').replace("$", r"\$")
        facts_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.sql.cite_case_brief(m.group(1)), facts_str)
        procedure_str = tex_escape(self.procedure)
        procedure_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.sql.cite_case_brief(m.group(1)), procedure_str)
        issue_str = tex_escape(self.issue)
        issue_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.sql.cite_case_brief(m.group(1)), issue_str)
        principle_str = tex_escape(self.principle)
        reasoning_str = tex_escape(self.reasoning)
        notes_str = tex_escape(self.notes)#.replace('\n', r'\\'+'\n').replace("$", r"\$")
        notes_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.sql.cite_case_brief(m.group(1)), notes_str)

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
        """ % (subjects_str,
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
               notes_str)
    
    def to_sql(self) -> None:
        log.debug(f"Saving case brief '{self.label.text}' to SQL database")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        curr = conn.cursor()
        try:
            # Insert or update the main case brief information
            curr.execute("""
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
            """, (
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
                self.notes
            ))

            # Clear existing subjects and opinions
            log.debug("Deleting existing subjects and opinions")
            curr.execute("DELETE FROM CaseSubjects WHERE case_label = ?", (self.label.text,))
            curr.execute("DELETE FROM CaseOpinions WHERE case_label = ?", (self.label.text,))

            # Insert subjects
            for subject in self.subject:
                log.trace("Saving Subject: ", subject.name)
                curr.execute("SELECT id FROM Subjects where name = ?", (subject.name,))
                subject_id = curr.fetchone()
                if not subject_id:
                    curr.execute("INSERT INTO Subjects (name) VALUES (?)", (subject.name,))
                    curr.execute("SELECT id FROM Subjects where name = ?", (subject.name,))
                    subject_id = curr.fetchone()
                subject_id = subject_id[0]
                curr.execute("INSERT INTO CaseSubjects (case_label, subject_id) VALUES (?, ?)", (self.label.text, subject_id,))

            # Insert opinions
            for opinion in self.opinions:
                log.trace("Saving Opinion By: ", opinion.author)
                curr.execute("SELECT id FROM Opinions where opinion_text = ?", (opinion.text,))
                opinion_id = curr.fetchone()
                if not opinion_id:
                    curr.execute("INSERT INTO Opinions (author, opinion_text) VALUES (?, ?)", (opinion.author, opinion.text,))
                    curr.execute("SELECT id FROM Opinions where opinion_text = ?", (opinion.text,))
                    opinion_id = curr.fetchone()
                opinion_id = opinion_id[0]
                curr.execute("INSERT INTO CaseOpinions (case_label, opinion_id) VALUES (?, ?)", (self.label.text, opinion_id))

            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            log.error(f"Error saving case brief to database: {e}")
        finally:
            conn.close()

    def save_to_file(self, filename: str) -> None:
        """Save the LaTeX representation of the case brief to a file."""
        with open(filename, 'w') as f:
            f.write(self.to_latex())
        log.info(f"Saved Latex to {filename}")

    def compile_to_pdf(self) -> str|None:
        """Compile the LaTeX file to PDF."""
        tex_file = os.path.join(base_dir, "Cases", f"{self.filename}.tex")
        self.save_to_file(tex_file)
        pdf_file = self.get_pdf_path()
        if os.path.exists(pdf_file):
            os.remove(pdf_file)
        try:
            process: QProcess = QProcess()
            process.start(os.path.join(base_dir, "bin", "tinitex"), [tex_file])
            #process.start("pdflatex", ["-interaction=nonstopmode", "-output-directory=./Cases", tex_file]) # pyright: ignore[reportUnknownMemberType]
            process.waitForFinished()
            if process.exitStatus() != QProcess.ExitStatus.NormalExit or process.exitCode() != 0:
                error_output = process.readAllStandardError().data().decode()
                log.error(f"Error compiling {tex_file} to PDF: {error_output}")
                return
            else:
                clean_dir(os.path.join(base_dir, "Cases"))
            log.info(f"Compiled {tex_file} to {pdf_file}")
            return pdf_file
        except Exception as e:
            log.error(f"Error compiling {tex_file} to PDF: {e}")
            raise RuntimeError(f"Failed to compile {tex_file} to PDF. Check the LaTeX file for errors.")
        

    @staticmethod
    def load_from_file(filename: str) -> 'CaseBrief':
        """Load a case brief from a LaTeX file."""
        log.debug(f"Loading case brief from {filename}")
        with open(filename, 'r') as f:
            content = f.read()
            # Here you would parse the content to extract the case brief details
            # This is a placeholder implementation
            regex = r'\\NewBrief{subject=\{(.*?)\},\n\s*plaintiff=\{(.*?)\},\n\s*defendant=\{(.*?)\},\n\s*citation=\{(.*?)\},\n\s*course=\{(.*?)\},\n\s*facts=\{(.*?)\},\n\s*procedure=\{(.*?)\},\n\s*issue=\{(.*?)\},\n\s*holding=\{(.*?)\},\n\s*principle=\{(.*?)\},\n\s*reasoning=\{(.*?)\},\n\s*opinions=\{(.*?)\},\n\s*label=\{case:(.*?)\},\n\s*notes=\{(.*?)\}'
            match = re.search(regex, content, re.DOTALL)
            if match:
                subjects = [Subject(s.strip()) for s in match.group(1).split(',') if s.strip()]
                plaintiff = match.group(2).strip()
                defendant = match.group(3).strip()
                citation = tex_unescape(match.group(4).strip())
                course = match.group(5).strip()
                facts = tex_unescape(match.group(6).strip())#.replace(r'\\'+'\n', '\n').replace(r"\$", "$")
                # Regex replace existing citations with the CITE(\1)
                citation_regex = r'\\hyperref\[case:(.*?)\]\{\\textit\{(.*?)\}\}'
                facts = re.sub(citation_regex, r'CITE(\1)', facts)
                procedure = tex_unescape(match.group(7).strip())#.replace(r'\\'+'\n', '\n').replace(r"\$", "$")
                # Regex replace existing citations with the CITE(\1)
                procedure = re.sub(citation_regex, r'CITE(\1)', procedure)
                issue = tex_unescape(match.group(8).strip())#.replace(r'\\'+'\n', '\n').replace(r"\$", "$")
                # Regex replace existing citations with the CITE(\1)
                issue = re.sub(citation_regex, r'CITE(\1)', issue)
                holding = match.group(9).strip()
                principle = tex_unescape(match.group(10).strip())
                reasoning = tex_unescape(match.group(11).strip())#.replace(r'\\'+'\n', '\n').replace(r"\$", "$")
                opinions = [Opinion(o.strip().split(":")[0].strip(), o.strip().split(":")[1].strip()) for o in re.sub(citation_regex, r'CITE(\1)', tex_unescape(match.group(12))) if o.strip()]
                label = Label(match.group(13).strip())
                notes = tex_unescape(match.group(14).strip())#.replace(r'\\'+'\n', '\n').replace(r"\$", "$")
            else:
                log.error(f"Failed to parse case brief from {filename}. The file may not be in the correct format.")
                raise RuntimeError(f"Failed to parse case brief from {filename}. The file may not be in the correct format.")

            return CaseBrief(subjects, plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, opinions, label, notes)

    @staticmethod
    def load_from_sql(case_label: str) -> 'CaseBrief':
        """Load a case brief from the SQL database by its label."""
        log.debug(f"Loading case brief from SQL with label {case_label}")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        curr = conn.cursor()
        curr.execute("SELECT plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, label, notes FROM Cases WHERE label = ?", (case_label,))
        cur_case = curr.fetchone()
        if not cur_case:
            log.error(f"No case brief found with label '{case_label}' in the database.")
            raise RuntimeError(f"No case brief found with label '{case_label}' in the database.")
        curr.execute("SELECT opinion_author, opinion_text FROM CaseOpinionsView WHERE case_label = ?", (case_label,))
        opinions = [Opinion(*opinion) for opinion in curr.fetchall()]
        curr.execute("SELECT subject_name FROM CaseSubjectsView WHERE case_label = ?", (case_label,))
        subjects = [Subject(subject[-1]) for subject in curr.fetchall()]
        # Assuming the database schema matches the order of fields in CaseBrief
        case_brief = CaseBrief(subject=subjects,
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
                               label=Label(cur_case[10]),
                               notes=cur_case[11])
        return case_brief
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, CaseBrief):
            return False
        return self.label.text == value.label.text
    
class CaseBriefs:
    """A class to manage multiple case briefs."""
    def __init__(self):
        self.case_briefs: list[CaseBrief] = []
        self.sql = SQL(db_path="SQL/Cases.sqlite")
        self.latex = Latex()

    def reload_cases_tex(self) -> None:
        """Reload all case briefs from the ./Cases directory."""
        log.info("Reloading case briefs from TeX files...")
        case_path = os.path.join(base_dir, "Cases")
        for filename in os.listdir(case_path):
            if filename.endswith(".tex"):
                brief = self.latex.loadBrief(os.path.join(case_path, filename))
                if brief not in self.case_briefs:
                    log.trace(f"Adding case brief: {brief.title}")
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
        log.error(f"Case brief with label '{case_brief.label.text}' not found.")
        raise ValueError(f"Case brief with label '{case_brief.label.text}' not found.")

    def remove_case_brief(self, case_brief: CaseBrief) -> None:
        """Remove a case brief from the collection."""
        self.case_briefs.remove(case_brief)

    def get_case_briefs(self) -> list[CaseBrief]:
        """Get all case briefs in the collection."""
        return sorted(self.case_briefs, key=lambda cb: cb.label.text)
    """
    def reload_cases_tex(self) -> None:
        \"""Reload all case briefs from the ./Cases directory.""\"
        log.info("Reloading case briefs from TeX files...")
        for filename in os.listdir(os.path.join(base_dir, "Cases")):
            if filename.endswith(".tex"):
                brief = CaseBrief.load_from_file(os.path.join(base_dir, "Cases", filename))
                if brief not in self.case_briefs:
                    log.trace(f"Adding case brief: {brief.title}")
                    self.case_briefs.append(brief)"""

    """
    def reload_cases_sql(self) -> None:
        \"""Reload all case briefs from the SQL database.""\"
        log.info("Reloading case briefs from SQL database...")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        curr = conn.cursor()
        curr.execute("SELECT label FROM Cases")
        labels = [Label(row[0]) for row in curr.fetchall()]
        for label in labels:
            case_brief = CaseBrief.load_from_sql(label.text)
            if case_brief not in self.case_briefs:
                self.add_case_brief(case_brief)
        conn.close()"""

    
    """
    def cite_case_brief(self, case_brief_label: str) -> str:
        \"""Cite a case brief by its label.""\"
        log.debug(f"Citing case brief with label: {case_brief_label}")
        for case_brief in self.case_briefs:
            log.trace(f"Checking case brief: {case_brief.label.text} against {case_brief_label}")
            if case_brief.label == case_brief_label:
                return f"\\hyperref[case:{case_brief.label.text}]{{\\textit{{{case_brief.title}}}}}"
        return f"CITE({case_brief_label})"  # Fallback if case brief not found
    
    def load_cases_tex(self, path: str) -> None:
        "\""Load all case briefs from the specified directory."\""
        log.info(f"Loading case briefs from TeX files in {path}...")
        for filename in os.listdir(path):
            if filename.endswith(".tex"):
                full_path = os.path.join(path, filename)
                brief = CaseBrief.load_from_file(full_path)
                if brief not in self.case_briefs:
                    log.trace(f"Adding case brief: {brief.title}")
                    self.case_briefs.append(brief)

    
    def load_cases_sql(self) -> None:
        ""\"Load all case briefs from the SQL database.""\"
        log.info("Loading case briefs from SQL database...")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        curr = conn.cursor()
        curr.execute("SELECT label FROM Cases")
        labels = [Label(row[0]) for row in curr.fetchall()]
        for label in labels:
            log.trace(f"Loading case brief for label: {label.text}")
            self.add_case_brief(CaseBrief.load_from_sql(label.text))
        conn.close()

    def save_cases_sql(self) -> None:
        log.info("Saving all case briefs to SQL database")
        for case in self.case_briefs:
            case.to_sql()"""


def reload_subjects(case_briefs: list[CaseBrief]) -> list[Subject]:
        log.debug("Reloading subjects from case briefs")
        subjects: list[Subject] = []    
        for case_brief in case_briefs:
            for subject in case_brief.subject:
                if subject not in subjects:
                    subjects.append(subject)
        return subjects

def reload_labels(case_briefs: list[CaseBrief]) -> list[Label]:
    log.debug("Reloading labels from case briefs")
    labels: list[Label] = []
    for case_brief in case_briefs:
        if case_brief.label not in labels:
            labels.append(case_brief.label)
    return labels

global master_file
master_file: Path = Path("CaseBriefs")

global base_dir
base_dir: str = "."


global db_path
log.debug(f"Base Directory: {base_dir}")
db_path: str = os.path.join(base_dir, 'SQL', 'Cases.sqlite')

global case_briefs, subjects, labels
case_briefs = CaseBriefs()
subjects = reload_subjects(case_briefs.get_case_briefs())
labels = reload_labels(case_briefs.get_case_briefs())



