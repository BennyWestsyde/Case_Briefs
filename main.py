"""_summary_
    This module provides a Python application that helps users create and manage case briefs.
    It allows users to input case details and generate a structured PDF document summarizing the case.

The resulting Latex document will be assembled as such:

\\documentclass[../CaseBriefs.tex]{subfiles}
\\usepackage{lawbrief}
\\begin{document}
\\NewBrief{subject={Subject1, Subject2},
        plaintiff={Plaintiff Name},
        defendant={Defendant Name},
        citation={Citation of the case (year)},
        facts={A list of all relevant facts of the case, formatted as a list, paragraph, or outline},
        procedure={A description of the procedural history of the case},
        issue={The legal issue(s) presented in the case},
        holding={The court's holding or decision},
        principle={The legal principle established by the case},
        reasoning={The court's reasoning or rationale for its decision},
        opinions={Any concurring or dissenting opinions},
        label={case:unique_label}
}
\\end{document}
"""
import os
import shutil
import sys
import re
from PyQt6.QtWidgets import (
    QScrollArea, QGridLayout, QLayoutItem, QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QListWidget, QLineEdit, QLabel, QMessageBox, QComboBox, QTextEdit
)
from PyQt6.QtCore import QUrl, QProcess
from PyQt6.QtGui import QDesktopServices
import sqlite3

global master_file
master_file = "CaseBriefs"

def tex_escape(input:str) -> str:
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
        '^': '\\textasciicircum{}',
        '. ': '.\\ ',
        '"': '\"'
    }
    return str.translate(input, str.maketrans(replacements)).replace('\n', r'\\')

class Subject:
    """A class to represent a legal subject."""
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return self.name
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Subject):
            return self.name == other.name
        elif isinstance(other, str):
            return self.name == other
        else:
            return False

    def __repr__(self):
        return f"Subject(name={self.name})"
    
class Label:
    """A class to represent the citable label of a case."""
    def __init__(self, label: str):
        self.text = label

    def __str__(self):
        return self.text

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Label):
            return self.text == other.text
        elif isinstance(other, str):
            return self.text == other
        else:
            return False

    def __repr__(self):
        return f"Label(label={self.text})"
    
class Opinion:
    """A class to represent a court opinion."""
    def __init__(self, author: str, text: str):
        self.author = author
        self.text = text
        
    def __str__(self):
        return f"{self.author}: {self.text}\n"

class CaseBrief:
    """
    A class to manage case briefs.
    
    :param subject: A list of Subject objects representing the legal subjects of the case.
    :param plaintiff: The name of the plaintiff in the case.
    :param defendant: The name of the defendant in the case.
    :param citation: The citation of the case, including the year.
    :param course: The name of the course for which the case brief is being prepared.
    :param facts: A string containing the relevant facts of the case.
    :param procedure: A string describing the procedural history of the case.
    :param issue: A string stating the legal issue(s) presented in the case.
    :param holding: A string containing the court's holding or decision.
    :param principle: A string stating the legal principle established by the case.
    :param reasoning: A string containing the court's reasoning or rationale for its decision.
    :param opinions: A list of strings containing any concurring or dissenting opinions.
    :param label: A Label object representing the citable label of the case.
    :param notes: A string containing any additional notes about the case.
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
    def title(self):
        return f"{self.plaintiff} v. {self.defendant}"

    @property
    def filename(self):
        return f"{self.plaintiff}_V_{self.defendant}".replace(" ", "_")

    def add_subject(self, subject: Subject):
        """Add a subject to the case brief."""
        self.subject.append(subject)

    def remove_subject(self, subject: Subject):
        """Remove a subject from the case brief."""
        self.subject = [s for s in self.subject if s != subject]

    def update_subject(self, old_subject: Subject, new_subject: Subject):
        """Update a subject in the case brief."""
        self.subject = [new_subject if s == old_subject else s for s in self.subject]

    def update_plaintiff(self, plaintiff: str):
        """Update the plaintiff in the case brief."""
        self.plaintiff = plaintiff
        
    def update_defendant(self, defendant: str):
        """Update the defendant in the case brief."""
        self.defendant = defendant
        
    def update_citation(self, citation: str):
        """Update the citation in the case brief."""
        self.citation = citation
        
    def update_facts(self, facts: str):
        """Update the facts in the case brief."""
        self.facts = facts
        
    def update_procedure(self, procedure: str):
        """Update the procedure in the case brief."""
        self.procedure = procedure
        
    def update_issue(self, issue: str):
        """Update the issue in the case brief."""
        self.issue = issue
        
    def update_holding(self, holding: str):
        """Update the holding in the case brief."""
        self.holding = holding
        
    def update_principle(self, principle: str):
        """Update the principle in the case brief."""
        self.principle = principle
        
    def update_reasoning(self, reasoning: str):
        """Update the reasoning in the case brief."""
        self.reasoning = reasoning
        
    def add_opinion(self, opinion: Opinion):
        """Add an opinion to the case brief."""
        self.opinions.append(opinion)
        
    def remove_opinion(self, opinion: Opinion):
        """Remove an opinion from the case brief."""
        self.opinions = [op for op in self.opinions if op != opinion]
        
    def update_label(self, label: Label):
        """Update the label in the case brief."""
        self.label = label

    def update_notes(self, notes: str):
        """Update the notes in the case brief."""
        self.notes = notes

    def get_pdf_path(self) -> str:
        """Get the path to the PDF file for this case brief."""
        return os.path.join("./Cases", f"{self.filename}.pdf")
        
    def to_latex(self) -> str:
        """Generate a LaTeX representation of the case brief."""
        subjects_str = ', '.join(str(s) for s in self.subject)
        opinions_str = ('\n').join(str(op) for op in self.opinions)
        opinions_str = tex_escape(opinions_str)#.replace('\n', r'\\'+'\n').replace("$", r"\$")
        opinions_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.cite_case_brief(m.group(1)), opinions_str)
        # Replace citations in facts, procedure, and issue with \hyperref[case:self.label]{\textit{self.title}}
        facts_str = tex_escape(self.facts)#.replace('\n', r'\\'+'\n').replace("$", r"\$")
        facts_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.cite_case_brief(m.group(1)), facts_str)
        procedure_str = tex_escape(self.procedure)#.replace('\n', r'\\'+'\n').replace("$", r"\$")
        procedure_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.cite_case_brief(m.group(1)), procedure_str)
        issue_str = tex_escape(self.issue)#.replace('\n', r'\\'+'\n').replace("$", r"\$")
        issue_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.cite_case_brief(m.group(1)), issue_str)
        notes_str = tex_escape(self.notes)#.replace('\n', r'\\'+'\n').replace("$", r"\$")
        notes_str = re.sub(r'CITE\((.*?)\)', lambda m: case_briefs.cite_case_brief(m.group(1)), notes_str)

        return """
            \\documentclass[../CaseBriefs.tex]{subfiles}
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
               self.citation,
               self.course,
               facts_str,
               procedure_str,
               issue_str,
               self.holding,
               self.principle,
               self.reasoning,
               opinions_str,
               self.label,
               notes_str)
    
    def to_sql(self):
        conn = sqlite3.connect('SQL/Cases.sqlite')
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
            print("Deleting existing subjects and opinions")
            curr.execute("DELETE FROM CaseSubjects WHERE case_label = ?", (self.label.text,))
            curr.execute("DELETE FROM CaseOpinions WHERE case_label = ?", (self.label.text,))

            # Insert subjects
            for subject in self.subject:
                print("Saving Subject: ", subject.name)
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
                print("Saving Opinion By: ", opinion.author)
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
            print(f"Error saving case brief to database: {e}")
        finally:
            conn.close()

    def save_to_file(self, filename: str):
        """Save the LaTeX representation of the case brief to a file."""
        with open(filename, 'w') as f:
            f.write(self.to_latex())
    
    def compile_to_pdf(self):
        """Compile the LaTeX file to PDF."""
        tex_file = f"./Cases/{self.filename}.tex"
        self.save_to_file(tex_file)
        pdf_file = self.get_pdf_path()
        if os.path.exists(pdf_file):
            os.remove(pdf_file)
        try:
            process: QProcess = QProcess()
            process.start("pdflatex", ["-interaction=nonstopmode", "-output-directory=./Cases", tex_file]) # pyright: ignore[reportUnknownMemberType]
            process.waitForFinished()
            if process.exitStatus() != QProcess.ExitStatus.NormalExit or process.exitCode() != 0:
                error_output = process.readAllStandardError().data().decode()
                print(f"Error compiling {tex_file} to PDF: {error_output}")
                return
            print(f"Compiled {tex_file} to {pdf_file}")
            return pdf_file
        except Exception as e:
            print(f"Error compiling {tex_file} to PDF: {e}")
            raise RuntimeError(f"Failed to compile {tex_file} to PDF. Check the LaTeX file for errors.")
        
    
    @staticmethod      
    def load_from_file(filename: str):
        """Load a case brief from a LaTeX file."""
        print(f"Loading case brief from {filename}")
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
                citation = match.group(4).strip()
                course = match.group(5).strip()
                facts = match.group(6).strip().replace(r'\\'+'\n', '\n').replace(r"\$", "$")
                # Regex replace existing citations with the CITE(\1)
                citation_regex = r'\\hyperref\[case:(.*?)\]\{\\textit\{(.*?)\}\}'
                facts = re.sub(citation_regex, r'CITE(\1)', facts)
                procedure = match.group(7).strip().replace(r'\\'+'\n', '\n').replace(r"\$", "$")
                # Regex replace existing citations with the CITE(\1)
                procedure = re.sub(citation_regex, r'CITE(\1)', procedure)
                issue = match.group(8).strip().replace(r'\\'+'\n', '\n').replace(r"\$", "$")
                # Regex replace existing citations with the CITE(\1)
                issue = re.sub(citation_regex, r'CITE(\1)', issue)
                holding = match.group(9).strip()
                principle = match.group(10).strip()
                reasoning = match.group(11).strip().replace(r'\\'+'\n', '\n').replace(r"\$", "$")
                opinions = [Opinion(o.strip().split(":")[0].strip(), o.strip().split(":")[1].strip()) for o in re.sub(citation_regex, r'CITE(\1)', match.group(12).replace(r'\\'+'\n', '\n')).split('\n') if o.strip()]
                label = Label(match.group(13).strip())
                notes = match.group(14).strip().replace(r'\\'+'\n', '\n').replace(r"\$", "$")
            else:
                raise RuntimeError(f"Failed to parse case brief from {filename}. The file may not be in the correct format.")

            return CaseBrief(subjects, plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, opinions, label, notes)

    @staticmethod
    def load_from_sql(case_label: str):
        conn = sqlite3.connect('SQL/Cases.sqlite')
        conn.execute("PRAGMA foreign_keys = ON")
        curr = conn.cursor()
        curr.execute("SELECT plaintiff, defendant, citation, course, facts, procedure, issue, holding, principle, reasoning, label, notes FROM Cases WHERE label = ?", (case_label,))
        cur_case = curr.fetchone()
        if not cur_case:
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

    def render_pdf(self):
        pass
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, CaseBrief):
            return False
        return self.label.text == value.label.text
    
class CaseBriefs:
    """A class to manage multiple case briefs."""
    def __init__(self):
        self.case_briefs: list[CaseBrief] = []

    def reload_cases_tex(self):
        """Reload all case briefs from the ./Cases directory."""
        for filename in os.listdir("./Cases"):
            if filename.endswith(".tex"):
                brief = CaseBrief.load_from_file(os.path.join("./Cases", filename))
                if brief not in self.case_briefs:
                    print(f"Adding case brief: {brief.title}")
                    self.case_briefs.append(brief)

    def reload_cases_sql(self):
        """Reload all case briefs from the SQL database."""
        conn = sqlite3.connect('SQL/Cases.sqlite')
        conn.execute("PRAGMA foreign_keys = ON")
        curr = conn.cursor()
        curr.execute("SELECT label FROM Cases")
        labels = [Label(row[0]) for row in curr.fetchall()]
        for label in labels:
            case_brief = CaseBrief.load_from_sql(label.text)
            if case_brief not in self.case_briefs:
                self.add_case_brief(case_brief)
        conn.close()

    def add_case_brief(self, case_brief: CaseBrief):
        """Add a case brief to the collection."""
        self.case_briefs.append(case_brief)
    
    def update_case_brief(self, CaseBrief: CaseBrief):
        """Update an existing case brief in the collection."""
        for index, cb in enumerate(self.case_briefs):
            if cb.label == CaseBrief.label:
                self.case_briefs[index] = CaseBrief
                return
        raise ValueError(f"Case brief with label '{CaseBrief.label.text}' not found.")

    def remove_case_brief(self, case_brief: CaseBrief):
        """Remove a case brief from the collection."""
        self.case_briefs.remove(case_brief)

    def get_case_briefs(self):
        """Get all case briefs in the collection."""
        return sorted(self.case_briefs, key=lambda cb: cb.label.text)
    
    def cite_case_brief(self, case_brief_label: str) -> str:
        """Cite a case brief by its label."""
        for case_brief in self.case_briefs:
            print(f"Checking case brief: {case_brief.label.text} against {case_brief_label}")
            if case_brief.label == case_brief_label:
                return f"\\hyperref[case:{case_brief.label.text}]"+ "{\\textit{" + case_brief.title + "}}"
        return f"CITE({case_brief_label})"  # Fallback if case brief not found
    
    def load_cases_tex(self, path: str):
        """Load all case briefs from the specified directory."""
        for filename in os.listdir(path):
            if filename.endswith(".tex"):
                full_path = os.path.join(path, filename)
                brief = CaseBrief.load_from_file(full_path)
                if brief not in self.case_briefs:
                    print(f"Adding case brief: {brief.title}")
                    self.case_briefs.append(brief)

    def load_cases_sql(self):
        conn = sqlite3.connect('SQL/Cases.sqlite')
        conn.execute("PRAGMA foreign_keys = ON")
        curr = conn.cursor()
        curr.execute("SELECT label FROM Cases")
        labels = [Label(row[0]) for row in curr.fetchall()]
        for label in labels:
            self.add_case_brief(CaseBrief.load_from_sql(label.text))
        conn.close()
    
    def save_cases_sql(self):
        for case in self.case_briefs:
            case.to_sql()

def reload_subjects(case_briefs: list[CaseBrief]) -> list[Subject]:
        subjects: list[Subject] = []    
        for case_brief in case_briefs:
            for subject in case_brief.subject:
                if subject not in subjects:
                    subjects.append(subject)
        return subjects

def reload_labels(case_briefs: list[CaseBrief]) -> list[Label]:
    labels: list[Label] = []
    for case_brief in case_briefs:
        if case_brief.label not in labels:
            labels.append(case_brief.label)
    return labels
# Start by finding and loading all of the case brief files in ./Cases

class CaseBriefCreator(QWidget):
        def __init__(self):
            super().__init__()
            case_briefs.reload_cases_sql()

            subjects = reload_subjects(case_briefs.get_case_briefs())

            # labels = reload_labels(case_briefs.get_case_briefs())
            self.setWindowTitle("Case Brief Creator")
            self.setGeometry(100, 100, 600, 500)
            
            self.content_layout = QGridLayout() # pyright: ignore[reportAttributeAccessIssue]
            self.content_layout.addWidget(QLabel("Create a new case brief"), 0, 0, 1, 2) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.plaintiff_entry = QLineEdit()
            self.plaintiff_entry.setPlaceholderText("Plaintiff Name")
            vs_label = QLabel("v.")
            self.defendant_entry = QLineEdit()
            self.defendant_entry.setPlaceholderText("Defendant Name")
            self.content_layout.addWidget(self.plaintiff_entry, 1, 0) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.content_layout.addWidget(vs_label, 1, 1) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.content_layout.addWidget(self.defendant_entry, 1, 2) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.citation_entry = QLineEdit()
            self.citation_entry.setPlaceholderText("Citation (Year)")
            self.content_layout.addWidget(self.citation_entry, 2, 0, 1, 3) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            # Subject box entry: a text box to enter subjects. When the user presses enter, the subject is added to a list of subjects.
            self.class_selector = QComboBox()
            self.class_selector.setPlaceholderText("Select a class")
            subjects_str_list = ["Contracts","Torts", "Civil Procedure","Legal Practice"]
            self.class_selector.addItems(subjects_str_list) # pyright: ignore[reportUnknownMemberType]
            self.content_layout.addWidget(self.class_selector, 2, 4, 1, 4) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            subject_entry_box = QLineEdit()
            subject_entry_box.setPlaceholderText("Enter a subject (press Enter to add)")
            self.content_layout.addWidget(subject_entry_box, 3, 0, 1, 4) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            # A dropdown list of existing subjects that can be selected by clicking them and then pressing enter to add them
            subject_existing_combo = QComboBox()
            self.existing_subjects_str_list: list[str] = []
            for subject in subjects:
                if subject.name not in self.existing_subjects_str_list:
                    self.existing_subjects_str_list.append(subject.name)
            self.existing_subjects_str_list.sort()
            self.current_subjects_str_list: list[str] = []
            subject_existing_combo.addItem("Select an existing subject")
            subject_existing_combo.addItems(self.existing_subjects_str_list) # pyright: ignore[reportUnknownMemberType]
            subject_existing_combo.currentIndexChanged.connect(lambda: subject_entry_box.setText(subject_existing_combo.currentText()) if subject_existing_combo.currentText() != "Select an existing subject" else subject_entry_box.setText("")) # pyright: ignore[reportUnknownMemberType]
            # When the user presses enter in the subject entry box, the subject is added to the existing subjects combo box if it is not already present
            subject_entry_box.returnPressed.connect(lambda: self.add_subject(subject_entry_box.text())) # pyright: ignore[reportUnknownMemberType]
            self.content_layout.addWidget(subject_existing_combo, 3, 4, 1, 5) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            subjects_list = QListWidget()
            # Remove a subject when it is selected and the user presses delete
            subjects_list.itemDoubleClicked.connect(lambda: self.remove_subject(subjects_list.currentItem().text()) if subjects_list.currentItem() else None) # pyright: ignore[reportOptionalMemberAccess, reportUnknownMemberType]
            self.content_layout.addWidget(subjects_list, 4, 0, 1, 5) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.facts_entry = QTextEdit()
            self.facts_entry.setPlaceholderText("Enter relevant facts of the case")
            self.content_layout.addWidget(self.facts_entry, 5, 0, 1, 5) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.procedure_entry = QTextEdit()
            self.procedure_entry.setPlaceholderText("Enter the procedural history of the case")
            self.content_layout.addWidget(self.procedure_entry, 6, 0, 1, 5) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.issue_entry = QTextEdit()
            self.issue_entry.setPlaceholderText("Enter the legal issue(s) presented in the case")
            self.content_layout.addWidget(self.issue_entry, 7, 0, 1, 5) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.holding_entry = QLineEdit()
            self.holding_entry.setPlaceholderText("Enter the court's holding or decision")
            self.content_layout.addWidget(self.holding_entry, 8, 0, 1, 5) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.principle_entry = QLineEdit()
            self.principle_entry.setPlaceholderText("Enter the legal principle established by the case")
            self.content_layout.addWidget(self.principle_entry, 9, 0, 1, 5) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.reasoning_entry = QTextEdit()
            self.reasoning_entry.setPlaceholderText("Enter the court's reasoning or rationale for its decision")
            self.content_layout.addWidget(self.reasoning_entry, 10, 0, 1, 5) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.opinions_entry = QTextEdit()
            self.opinions_entry.setPlaceholderText("Enter any concurring or dissenting opinions (format: Person: Opinion)")
            self.content_layout.addWidget(self.opinions_entry, 11, 0, 1, 5) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.label_entry = QLineEdit()
            self.label_entry.setPlaceholderText("Enter a unique label for the case")
            self.content_layout.addWidget(self.label_entry, 12, 0, 1, 5) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.notes_entry = QTextEdit()
            self.notes_entry.setPlaceholderText("Enter any case notes")
            self.content_layout.addWidget(self.notes_entry, 4, 5, 9, 4) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.create_button = QPushButton("Create Case Brief")
            self.create_button.clicked.connect(lambda: self.create_case_brief( # pyright: ignore[reportUnknownMemberType]
                self.plaintiff_entry.text(),
                self.defendant_entry.text(),
                self.citation_entry.text(),
                self.class_selector.currentText(),
                self.current_subjects_str_list,
                self.facts_entry.toPlainText(),
                self.procedure_entry.toPlainText(),
                self.issue_entry.toPlainText(),
                self.holding_entry.text(),
                self.principle_entry.text(),
                self.reasoning_entry.toPlainText(),
                self.opinions_entry.toPlainText(),
                self.label_entry.text(),
                self.notes_entry.toPlainText()
            ) if self.verify_label(self.label_entry.text()) else None)
            self.content_layout.addWidget(self.create_button, 13, 0, 1, 3) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.setLayout(self.content_layout) # pyright: ignore[reportArgumentType]
            
        def add_subject(self, subject: str):
            """Add a subject to the case brief."""
            if not subject:
                QMessageBox.warning(self, "Warning", "Subject cannot be empty.")
                return
            if Subject(subject) not in subjects:
                subjects.append(Subject(subject))
            if subject not in self.current_subjects_str_list:
                self.current_subjects_str_list.append(subject)
            self.current_subjects_str_list.sort()
            self.rerender_subjects_list()
            
        def remove_subject(self, subject: str):
            """Remove a subject from the case brief."""
            if not subject:
                QMessageBox.warning(self, "Warning", "Subject cannot be empty.")
                return
            if subject in self.current_subjects_str_list:
                self.current_subjects_str_list.remove(subject)
            self.rerender_subjects_list()
            
        def rerender_subjects_list(self):
            """Rerender the subjects list in the GUI."""
            subjects_list = self.content_layout.itemAtPosition(4, 0).widget() # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
            if subjects_list is not None:
                subjects_list.clear() # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
                for subject in self.current_subjects_str_list:
                    subjects_list.addItem(subject) # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]

        def verify_label(self, label: str) -> bool:
            """Verify if the label is unique."""
            if any(cb.label.text == label for cb in case_briefs.get_case_briefs()):
                QMessageBox.warning(self, "Warning", "Label must be unique.")
                return False
            return True
        
        def create_case_brief(self, 
                              plaintiff: str, 
                              defendant: str, 
                              citation: str, 
                              course: str,
                              subjects: list[str], 
                              facts: str, 
                              procedure: str, 
                              issue: str, 
                              holding: str, 
                              principle: str, 
                              reasoning: str, 
                              opinions_str: str, 
                              label: str,
                              notes: str):
            """Create a new case brief and save it to a file."""
            if not plaintiff or not defendant or not citation or not label or not course:
                QMessageBox.warning(self, "Warning", "Plaintiff, Defendant, Citation, Label and Course cannot be empty.")
                return

            opinions: list[Opinion] = []
            if opinions_str:
                for line in opinions_str.splitlines():
                    if ':' in line:
                        person, text = line.split(':', 1)
                        opinions.append(Opinion(person.strip(), text.strip()))

            
            case_brief = CaseBrief(
                subject=[Subject(s) for s in subjects],
                plaintiff=plaintiff,
                defendant=defendant,
                citation=citation,
                course=course,
                facts=facts,
                procedure=procedure,
                issue=issue,
                holding=holding,
                principle=principle,
                reasoning=reasoning,
                opinions=opinions,
                label=Label(label),
                notes=notes
            )

            filename = f"./Cases/{case_brief.filename}.tex"
            case_brief.save_to_file(filename)
            case_briefs.add_case_brief(case_brief)
            case_brief.to_sql()
            QMessageBox.information(self, "Success", f"Case brief '{case_brief.title}' created successfully!")
            self.close()

        def show(self):
            super().show()
            print("Case brief creation window opened")

class CaseBriefManager(QWidget):
    """A window for managing existing case briefs.
    This window should bring up a list of the existing case briefs, 
    and allow the user to select one and search existing case briefs then edit them.
    """
    def __init__(self):
        super().__init__()
        case_briefs.reload_cases_sql()

        self.setWindowTitle("Case Brief Manager")
        self.setGeometry(100, 100, 600, 400)

        scrollable_area = QScrollArea(self)
        scrollable_area.setWidgetResizable(True)

        content_widget = QWidget()
        content_layout = QGridLayout(content_widget)
        scrollable_area.setWidget(content_widget)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scrollable_area)
        
        
        # Add a search bar to search for case briefs
        search_entry = QLineEdit()
        search_entry.setPlaceholderText("Search case briefs...")
        content_layout.addWidget(search_entry, 0, 0)
        search_entry.textChanged.connect(self.filter_case_briefs) # pyright: ignore[reportUnknownMemberType]
        class_dropdown = QComboBox()
        class_dropdown.setPlaceholderText("Select a class...")
        class_dropdown.addItems(["All", "Torts", "Contracts", "Civil Procedure"]) # pyright: ignore[reportUnknownMemberType]
        class_dropdown.currentIndexChanged.connect(lambda: self.filter_case_briefs(class_dropdown.currentText() if class_dropdown.currentText() != "All" else "")) # pyright: ignore[reportUnknownMemberType]
        content_layout.addWidget(class_dropdown, 0, 1, 1, 2) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

        for index, case_brief in enumerate(case_briefs.get_case_briefs()):
            case_brief_item = QLabel(case_brief.title)
            case_brief_edit_button = QPushButton("Edit")
            case_brief_edit_button.clicked.connect(lambda _, cb=case_brief: self.edit_case_brief(cb)) # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
            case_brief_view_button = QPushButton("View")
            case_brief_view_button.clicked.connect(lambda _, cb=case_brief: self.view_case_brief(cb)) # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
            case_brief_item.setToolTip(f"Course: {case_brief.course}\nCitation: {case_brief.citation}\nSubjects: {', '.join(str(s) for s in case_brief.subject)}\nLabel: {case_brief.label.text}")
            content_layout.addWidget(case_brief_item, index + 1, 0)
            content_layout.addWidget(case_brief_edit_button, index + 1, 1)
            content_layout.addWidget(case_brief_view_button, index + 1, 2)

        #self.setLayout(layout)
        self.content_layout = content_layout # pyright: ignore[reportAttributeAccessIssue]
        
        # CaseBriefManager.__init__
        self._pdf_windows = []  # keep viewers alive

    def view_case_brief(self, case_brief: CaseBrief):
        pdf_path = case_brief.compile_to_pdf()
        if not pdf_path or not os.path.exists(pdf_path):
            QMessageBox.critical(self, "Error", "Failed to compile PDF. Check LaTeX output.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(pdf_path)))


    def filter_case_briefs(self, text: str):
        """Filter the case briefs based on the search text."""
        for i in range(self.content_layout.rowCount()): # pyright: ignore[reportUnknownArgumentType, reportAttributeAccessIssue, reportUnknownMemberType]
            item: QLayoutItem = self.content_layout.itemAtPosition(i, 0) # pyright: ignore[reportAssignmentType, reportUnknownVariableType, reportAttributeAccessIssue, reportUnknownMemberType]
            if item:
                widget: QWidget = item.widget() # pyright: ignore[reportUnknownVariableType, reportAssignmentType, reportUnknownMemberType]
                if isinstance(widget, QLabel):
                    if text.lower() in widget.text().lower() or text.lower() in widget.toolTip().lower():
                        widget.show()
                        self.content_layout.itemAtPosition(i, 1).widget().show()  # pyright: ignore[reportOptionalMemberAccess, reportUnknownMemberType, reportAttributeAccessIssue] # Show the edit button as well
                        self.content_layout.itemAtPosition(i, 2).widget().show()  # pyright: ignore[reportOptionalMemberAccess, reportUnknownMemberType, reportAttributeAccessIssue] # Show the view button as well
                    else:
                        widget.hide()
                        self.content_layout.itemAtPosition(i, 1).widget().hide()  # pyright: ignore[reportOptionalMemberAccess, reportUnknownMemberType, reportAttributeAccessIssue] # Hide the edit button as well
                        self.content_layout.itemAtPosition(i, 2).widget().hide()  # pyright: ignore[reportOptionalMemberAccess, reportUnknownMemberType, reportAttributeAccessIssue] # Hide the view button as well
        
    def edit_case_brief(self, case_brief: CaseBrief):
        """View the details of a case brief."""
        # Open the CaseBriefCreator window with the case brief details filled in
        self.creator = CaseBriefCreator()
        self.creator.plaintiff_entry.setText(case_brief.plaintiff)
        self.creator.defendant_entry.setText(case_brief.defendant)
        self.creator.citation_entry.setText(case_brief.citation)
        self.creator.class_selector.setCurrentText(case_brief.course)
        self.creator.current_subjects_str_list = [s.name for s in case_brief.subject]
        self.creator.rerender_subjects_list()
        self.creator.facts_entry.setPlainText(case_brief.facts)
        self.creator.procedure_entry.setPlainText(case_brief.procedure)
        self.creator.issue_entry.setPlainText(case_brief.issue)
        self.creator.holding_entry.setText(case_brief.holding)
        self.creator.principle_entry.setText(case_brief.principle)
        self.creator.reasoning_entry.setText(case_brief.reasoning)
        opinions_str = '\n'.join(f"{op.author}: {op.text}" for op in case_brief.opinions)
        self.creator.opinions_entry.setText(opinions_str)
        self.creator.label_entry.setText(case_brief.label.text)
        # Disable the label entry to prevent changing it
        self.creator.label_entry.setDisabled(True)
        self.creator.notes_entry.setPlainText(case_brief.notes)
        # Set the create button to update the existing case brief instead of creating a new one
        self.creator.create_button.setText("Update Case Brief")
        self.creator.create_button.clicked.disconnect() # pyright: ignore[reportUnknownMemberType]
        self.creator.create_button.clicked.connect(lambda: self.update_case_brief( # pyright: ignore[reportUnknownMemberType]
            case_brief,
            self.creator.plaintiff_entry.text(),
            self.creator.defendant_entry.text(),
            self.creator.citation_entry.text(),
            self.creator.current_subjects_str_list,
            self.creator.facts_entry.toPlainText(),
            self.creator.procedure_entry.toPlainText(),
            self.creator.issue_entry.toPlainText(),
            self.creator.holding_entry.text(),
            self.creator.principle_entry.text(),
            self.creator.reasoning_entry.toPlainText(),
            self.creator.opinions_entry.toPlainText(),
            self.creator.label_entry.text()  # This will not change
        ))

        self.creator.show()

    def update_case_brief(self,
                            case_brief: CaseBrief,
                            plaintiff: str,
                            defendant: str,
                            citation: str,
                            subjects: list[str],
                            facts: str,
                            procedure: str,
                            issue: str,
                            holding: str,
                            principle: str,
                            reasoning: str,
                            opinions_str: str,
                            label: str):
        """Update an existing case brief and save it to a file."""
        if not plaintiff or not defendant or not citation or not label:
            QMessageBox.warning(self, "Warning", "Plaintiff, Defendant, Citation and Label cannot be empty.")
            return
        opinions: list[Opinion] = []
        if opinions_str:
            for opinion in opinions_str.split(','):
                if ':' in opinion:
                    person, text = opinion.split(':', 1)
                    opinions.append(Opinion(person.strip(), text.strip()))
        case_brief.update_plaintiff(plaintiff)
        case_brief.update_defendant(defendant)
        case_brief.update_citation(citation)
        case_brief.course = self.creator.class_selector.currentText()
        case_brief.subject = [Subject(s) for s in subjects]
        case_brief.update_facts(facts)
        case_brief.update_procedure(procedure)
        case_brief.update_issue(issue)
        case_brief.update_holding(holding)
        case_brief.update_principle(principle)
        case_brief.update_reasoning(reasoning)
        case_brief.opinions = opinions
        case_brief.to_sql()
        # Label does not change
        filename = f"./Cases/{case_brief.filename}.tex"
        case_brief.save_to_file(filename)
        case_briefs.update_case_brief(case_brief)
        QMessageBox.information(self, "Success", f"Case brief '{case_brief.title}' created successfully!")
        self.creator.close()
        self.close()
    
    def show(self):
        super().show()
        print("Case brief manager opened")

class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Settings")
        self.setGeometry(150, 150, 400, 300)
        layout = QVBoxLayout()
        classes_label = QLabel("Classes:")
        layout.addWidget(classes_label)
        classes_combo = QComboBox()
        classes_combo.addItems(["Class 1", "Class 2", "Class 3"])  # pyright: ignore[reportUnknownMemberType] # Example classes
        layout.addWidget(classes_combo)
        self.setLayout(layout)
    
    def show(self):
        super().show()
        print("Settings window opened")


class CaseBriefApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Case Briefs Manager")
        self.setGeometry(100, 100, 600, 400)
        
        layout = QGridLayout()
        new_case_brief_button = QPushButton("Create Case Brief")
        new_case_brief_button.clicked.connect(self.create_case_brief) # pyright: ignore[reportUnknownMemberType]
        layout.addWidget(new_case_brief_button, 0, 0, 1, 1)

        view_case_briefs_button = QPushButton("View Case Briefs")
        view_case_briefs_button.clicked.connect(self.view_case_briefs) # pyright: ignore[reportUnknownMemberType]
        layout.addWidget(view_case_briefs_button, 1, 0, 1, 1)

        render_pdf_button = QPushButton("Render PDF")
        render_pdf_button.clicked.connect(self.render_pdf) # pyright: ignore[reportUnknownMemberType]
        layout.addWidget(render_pdf_button, 2, 0, 1, 1)

        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self.open_settings) # pyright: ignore[reportUnknownMemberType]
        layout.addWidget(settings_button, 3, 0, 1, 1)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
    
    def create_case_brief(self):
        # Logic to create a new case brief
        print("Creating a new case brief...")
        self.creator = CaseBriefCreator()
        self.creator.show()
        
    def view_case_briefs(self):
        # Logic to view existing case briefs
        print("Viewing existing case briefs...")
        self.manager = CaseBriefManager()
        self.manager.show()

    def render_pdf(self):
        # Logic to render the case brief as a PDF
        print("Rendering PDF for the case brief...")
        if not os.path.exists("./Cases"):
            os.makedirs("./Cases")
            QMessageBox.warning(self, "Error", "No case briefs found. Please create a case brief first.")
            return
        if not os.path.exists("./TMP"):
            os.makedirs("./TMP")
        if not os.path.exists(f"./{master_file}.tex"):
            QMessageBox.warning(self, "Error", f"No case brief found with the name {master_file}. Please reinstall the application.")
            return
        try:
            process = QProcess(self)
            process.start("latexmk", [ # pyright: ignore[reportUnknownMemberType]
                        "-synctex=1",
                        "-interaction=nonstopmode",
                        "-file-line-error",
                        "-pdf",
                        "-shell-escape", 
                        "-outdir=./TMP",
                        f"./{master_file}.tex"])
            process.waitForFinished()
            if process.exitStatus() != QProcess.ExitStatus.NormalExit or process.exitCode() != 0:
                error_output = process.readAllStandardError().data().decode()
                QMessageBox.critical(self, "LaTeX Error", error_output)
                return
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        QMessageBox.information(self, "PDF Rendered", f"PDF for {master_file} has been generated successfully.")
        shutil.move(f"./TMP/{master_file}.pdf", f"./{master_file}.pdf")
        # Here you would typically call the method to generate the PDF

    def open_settings(self):
        # Logic to open the settings window
        print("Opening settings...")
        self.settings = SettingsWindow()
        self.settings.show()

global case_briefs, subjects, labels
case_briefs = CaseBriefs()
subjects = reload_subjects(case_briefs.get_case_briefs())
labels = reload_labels(case_briefs.get_case_briefs())

if __name__ == "__main__":
    # Create a simple gui for the application

    app = QApplication(sys.argv)
    window = CaseBriefApp()
    window.show()
    sys.exit(app.exec())
else:
    print("This module is intended to be run as a standalone application.")
    print("Please run it directly to use the Case Briefs Manager.")