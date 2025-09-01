import os
from pathlib import Path
import shutil
from PyQt6.QtWidgets import (
    QScrollArea, QGridLayout, QLayoutItem, QMainWindow, QPushButton, QVBoxLayout, QWidget, QListWidget, QLineEdit, QLabel, QMessageBox, QComboBox, QTextEdit
)
from PyQt6.QtCore import QUrl, QProcess, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from cleanup import clean_dir
from typing import Callable
from CaseBrief import CaseBrief, Subject, Label, Opinion, log, base_dir, case_briefs, master_file, subjects

from logger import StructuredLogger
log = StructuredLogger("GUI","TRACE","CaseBriefs.log",True,None,True,True)

class CaseBriefCreator(QWidget):
        def __init__(self):
            log.info("Opening Case Brief Creator")
            super().__init__()
            case_briefs.reload_cases_sql()

            subjects: list[Subject] = [Subject(sub) for sub in case_briefs.sql.fetchCaseSubjects()]

            # labels = reload_labels(case_briefs.get_case_briefs())
            self.setWindowTitle("Case Brief Creator")
            self.setGeometry(100, 100, 600, 500)
            
            self.content_layout = QGridLayout() # pyright: ignore[reportAttributeAccessIssue]
            self.content_layout.addWidget(QLabel("Create a new case brief"), 0, 0, 1, 2) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            self.plaintiff_entry = QLineEdit()
            self.plaintiff_entry.setPlaceholderText("Plaintiff Name")
            self.plaintiff_entry.textChanged.connect(self.rerender_label) # pyright: ignore[reportUnknownMemberType]
            vs_label = QLabel("v.")
            self.defendant_entry = QLineEdit()
            self.defendant_entry.setPlaceholderText("Defendant Name")
            self.defendant_entry.textChanged.connect(self.rerender_label) # pyright: ignore[reportUnknownMemberType]
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
            self.setWindowTitle("Case Briefs Creator")
            
        def add_subject(self, subject: str):
            """Add a subject to the case brief."""
            if not subject:
                QMessageBox.warning(self, "Warning", "Subject cannot be empty.")
                return
            log.debug(f"Adding subject: {subject}")
            if subject not in subjects:
                log.trace(f"Subject '{subject}' not in master subject list, adding it.")
                #case_briefs.sql.addCaseSubject(subject, self.label_entry.text())
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
            log.debug(f"Removing subject: {subject}")
            if subject in self.current_subjects_str_list:
                self.current_subjects_str_list.remove(subject)
            self.rerender_subjects_list()

        def rerender_label(self):
            """Rerender the label in the GUI."""
            plaintiff = self.plaintiff_entry.text().strip()
            defendant = self.defendant_entry.text().strip()
            label_format = plaintiff.title().replace(" ", "") + "V" + defendant.title().replace(" ", "")
            self.label_entry.setText(label_format)

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

            #filename = f"./Cases/{case_brief.filename}.tex"
            #case_brief.save_to_file(filename)
            case_briefs.add_case_brief(case_brief)
            case_briefs.sql.saveBrief(case_brief)
            case_briefs.latex.saveBrief(case_brief)
            #case_brief.to_sql()
            QMessageBox.information(self, "Success", f"Case brief '{case_brief.title}' created successfully!")
            log.info(f"Case brief '{case_brief.title}' created successfully!")
            self.close()

        def show(self):
            super().show()
            log.info("Case brief creation window opened")

class CaseBriefManager(QWidget):
    """A window for managing existing case briefs.
    This window should bring up a list of the existing case briefs, 
    and allow the user to select one and search existing case briefs then edit them.
    """
    def __init__(self):
        super().__init__()
        log.info("Initializing Case Brief Manager")
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
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Search case briefs...")
        content_layout.addWidget(self.search_entry, 0, 0)
        self.search_entry.textChanged.connect(self.filter_by_search) # pyright: ignore[reportUnknownMemberType]
        self.class_dropdown = QComboBox()
        self.class_dropdown.setPlaceholderText("Select a class...")
        self.class_dropdown.addItems(["All", "Torts", "Contracts", "Civil Procedure"]) # pyright: ignore[reportUnknownMemberType]
        self.class_dropdown.currentIndexChanged.connect(lambda: self.filter_by_search(self.class_dropdown.currentText() if self.class_dropdown.currentText() != "All" else "")) # pyright: ignore[reportUnknownMemberType]
        content_layout.addWidget(self.class_dropdown, 0, 1, 1, 2) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

        for index, case_brief in enumerate(case_briefs.get_case_briefs()):
            case_brief_item = QLabel(case_brief.title)
            case_brief_edit_button = QPushButton("Edit")
            case_brief_edit_button.clicked.connect(self._make_edit_handler(case_brief)) # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
            case_brief_view_button = QPushButton("View")
            case_brief_view_button.clicked.connect(self._make_view_handler(case_brief)) # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
            case_brief_item.setToolTip(f"Course: {case_brief.course}\nCitation: {case_brief.citation}\nSubjects: {', '.join(str(s) for s in case_brief.subject)}\nLabel: {case_brief.label.text}")
            content_layout.addWidget(case_brief_item, index + 1, 0)
            content_layout.addWidget(case_brief_edit_button, index + 1, 1)
            content_layout.addWidget(case_brief_view_button, index + 1, 2)
        self.setWindowTitle("Case Briefs Manager")

        #self.setLayout(layout)
        self.content_layout = content_layout # pyright: ignore[reportAttributeAccessIssue]
        
        # CaseBriefManager.__init__
        self._pdf_windows = []  # keep viewers alive


    @pyqtSlot(CaseBrief)
    def _make_view_handler(self, cb: CaseBrief) -> Callable[[bool], None]:
        def _handler(_checked: bool) -> None:
            self.view_case_brief(cb)
        return _handler


    @pyqtSlot(CaseBrief)
    def _make_edit_handler(self, cb: CaseBrief) -> Callable[[bool], None]:
        def _handler(_checked: bool) -> None:
            self.edit_case_brief(cb)
        return _handler

    def view_case_brief(self, case_brief: CaseBrief):
        """View the PDF of a case brief."""
        log.info(f"Viewing case brief '{case_brief.title}'")
        pdf_path = case_brief.compile_to_pdf()
        if not pdf_path or not os.path.exists(pdf_path):
            QMessageBox.critical(self, "Error", "Failed to compile PDF. Check LaTeX output.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(pdf_path)))

    def filter_by_search(self, text: str):
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

    
    @pyqtSlot(str)    
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
            self.creator.notes_entry.toPlainText(),
            self.creator.label_entry.text()  # This will not change
        ))

        self.creator.show()
        log.info(f"Editing case brief '{case_brief.title}'")

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
                            notes: str,
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
        case_brief.update_notes(notes)
        case_briefs.sql.saveBrief(case_brief)
        #case_brief.to_sql()
        # Label does not change
        #filename = os.path.join(base_dir, "Cases", f"{case_brief.filename}.tex")
        case_briefs.latex.saveBrief(case_brief)
        #case_brief.save_to_file(filename)
        case_briefs.update_case_brief(case_brief)
        QMessageBox.information(self, "Success", f"Case brief '{case_brief.title}' created successfully!")
        log.info(f"Case brief '{case_brief.title}' created successfully!")
        self.creator.close()
        self.close()
    
    def show(self):
        super().show()
        log.info("Case brief manager opened")

class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        log.info("Initializing Settings Window")
        self.setWindowTitle("Settings")
        self.setGeometry(150, 150, 400, 300)
        layout = QVBoxLayout()
        classes_label = QLabel("Classes:")
        layout.addWidget(classes_label)
        classes_combo = QComboBox()
        classes_combo.addItems(["Class 1", "Class 2", "Class 3"])  # pyright: ignore[reportUnknownMemberType] # Example classes
        layout.addWidget(classes_combo)
        self.setLayout(layout)
        self.setWindowTitle("Case Briefs Settings")
    
    def show(self):
        super().show()
        log.info("Settings window opened")


class CaseBriefApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Case Briefs Manager")
        self.setGeometry(100, 100, 600, 400)
        log.info("Initializing Case Briefs Application")

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
        self.setWindowTitle("Case Briefs App")
    
    def create_case_brief(self):
        # Logic to create a new case brief
        log.info("Creating a new case brief...")
        self.creator = CaseBriefCreator()
        self.creator.show()
        
    def view_case_briefs(self):
        # Logic to view existing case briefs
        log.info("Viewing existing case briefs...")
        self.manager = CaseBriefManager()
        self.manager.show()

    def render_pdf(self):
        # Logic to render the case brief as a PDF
        log.info("Rendering PDF for the case brief...")
        if not os.path.exists(os.path.join(base_dir, "Cases")):
            os.makedirs(os.path.join(base_dir, "Cases"))
            QMessageBox.warning(self, "Error", "No case briefs found. Please create a case brief first.")
            return
        if not os.path.exists(os.path.join(base_dir, "TMP")):
            os.makedirs(os.path.join(base_dir, "TMP"))
        if not os.path.exists(os.path.join(base_dir, "tex_src", f"{master_file}.tex")):
            QMessageBox.warning(self, "Error", f"No case brief found with the name {master_file}. Please reinstall the application.")
            return
        try:
            process = QProcess(self)
            program = os.path.join(base_dir, "bin/tinitex")
            args = [
                "--output-dir=../TMP",
                "--pdf-engine=pdflatex",                 # or xelatex/lualatex
                "--pdf-engine-opt=-shell-escape",        # <-- include the leading dash
                f"./tex_src/{master_file}.tex",
            ]
            process.setProgram(program)
            process.setArguments(args)
            process.start()
            """
            process.start("latexmk", [ # pyright: ignore[reportUnknownMemberType]
                        "-synctex=1",
                        "-interaction=nonstopmode",
                        "-file-line-error",
                        "-pdf",
                        "-shell-escape", 
                        "-outdir=./TMP",
                        f"./{master_file}.tex"])"""
            process.waitForFinished()
            if process.exitStatus() != QProcess.ExitStatus.NormalExit or process.exitCode() != 0:
                error_output = process.readAllStandardError().data().decode()
                QMessageBox.critical(self, "LaTeX Error", error_output)
                return
            else:
                clean_dir("./TMP")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        QMessageBox.information(self, "PDF Rendered", f"PDF for {master_file} has been generated successfully.")
        shutil.move(os.path.join(base_dir, "TMP", f"{master_file}.pdf"), os.path.join(Path.home(),"Downloads", f"{master_file}.pdf"))
        # Here you would typically call the method to generate the PDF

    def open_settings(self):
        # Logic to open the settings window
        log.info("Opening settings...")
        self.settings = SettingsWindow()
        self.settings.show()