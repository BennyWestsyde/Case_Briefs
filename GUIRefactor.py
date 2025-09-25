from __future__ import annotations
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import sqlite3
import threading
from PyQt6.QtWidgets import (
    QFileDialog,
    QProgressDialog,
    QScrollArea,
    QGridLayout,
    QLayoutItem,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QListWidget,
    QLineEdit,
    QLabel,
    QMessageBox,
    QComboBox,
    QTextEdit,
)
from PyQt6.QtCore import (
    QMutex,
    QMutexLocker,
    QRunnable,
    QSemaphore,
    QThread,
    QThreadPool,
    QUrl,
    QProcess,
    Qt,
    pyqtSlot,
)
from PyQt6.QtGui import QDesktopServices
from DataClasses import CaseBriefData, Label, Opinion, Subject


from QProcessTeXCompiler import QProcessTeXCompiler
from cleanup import clean_dir
from typing import Any, Callable, List
from CaseCatalog import (
    CaseBriefs,
    TeXCompiler,
)

from logger import StructuredLogger
from Global_Vars import Global_Vars


from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import (
    QTextCursor,
    QSyntaxHighlighter,
    QTextCharFormat,
    QColor,
    QAction,
    QTextDocument,
)
from spellchecker import SpellChecker


from functools import partial
from typing import Any, Optional, Tuple

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QContextMenuEvent, QTextCursor, QAction
from PyQt6.QtWidgets import QLineEdit, QMenu, QTextEdit


from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl


class CompileSingleToPdfWorker(QObject):
    finished: pyqtSignal = pyqtSignal(str)  # absolute path to PDF
    failed: pyqtSignal = pyqtSignal(str)  # error message
    canceled: pyqtSignal = pyqtSignal()

    def __init__(
        self,
        case_brief: CaseBriefData,
        global_vars: Global_Vars,
        logger: StructuredLogger,
        tex_compiler: TeXCompiler,
    ) -> None:
        super().__init__()
        self._case_brief = case_brief
        self._global_vars = global_vars
        self._logger = logger
        self._tex_compiler = tex_compiler

    @pyqtSlot()
    def run(self) -> None:
        try:
            self._logger.debug("Starting PDF compilation")
            pdf_path: Optional[Path] = self._tex_compiler.compile(
                engine=Path(str(self._global_vars.tinitex_binary)),
                workdir=Path(str(self._global_vars.cases_dir)),
                outdir=Path(str(self._global_vars.cases_output_dir)),
                tex_file=(
                    Path(str(self._global_vars.cases_dir))
                    / (self._case_brief.filename + ".tex")
                ),
            )
            if not pdf_path:
                self._logger.error("LaTeX produced no output path.")
                self.failed.emit("LaTeX produced no output path.")
                return
            abs_path = os.path.abspath(pdf_path)
            if not os.path.exists(abs_path):
                self._logger.error("PDF not found after compile.")
                self.failed.emit("PDF not found after compile.")
                return
            self.finished.emit(abs_path)
        except Exception as e:
            self._logger.error(f"PDF compilation failed: {e}")
            self.failed.emit(f"PDF compilation failed: {e}")

        #     ) -> None:
        # try:
        #     # If you want to support cancellation, check QThread.currentThread().isInterruptionRequested()
        #     pdf_path: Optional[str] = self._case_brief.latex.compile()
        #     if not pdf_path:
        #         self.failed.emit("LaTeX produced no output path.")
        #         return
        #     abs_path = os.path.abspath(pdf_path)
        #     if not os.path.exists(abs_path):
        #         self.failed.emit("PDF not found after compile.")
        #         return
        #     self.finished.emit(abs_path)
        # except Exception as e:  # keep broad here to ensure we surface errors to UI
        #     self.failed.emit(str(e))


class RenderAllToPdfWorker(QObject):
    finished: pyqtSignal = pyqtSignal(str)  # absolute path to PDF
    failed: pyqtSignal = pyqtSignal(str)  # error message
    canceled: pyqtSignal = pyqtSignal()

    def __init__(
        self,
        case_briefs: CaseBriefs,
        global_vars: Global_Vars,
        logger: StructuredLogger,
    ):
        super().__init__()
        self._case_briefs = case_briefs
        self._global_vars = global_vars
        self._logger = logger.getChildLogger("RenderAllToPdfWorker")

    @pyqtSlot()
    def run(self) -> None:
        try:
            if (
                not getattr(self._case_briefs.items, "__len__", None)
                or len(self._case_briefs.items) == 0
            ):
                self._logger.warning("No case briefs to compile.")
                self.failed.emit("No case briefs to compile.")
                return
            else:
                self._logger.debug(
                    f"Starting compilation of {len(self._case_briefs.items)} case briefs."
                )
            process = QProcess()

            # Use a path relative to write_dir for output
            output_path = Path("TMP")

            program = self._global_vars.tinitex_binary
            if not program.exists():
                self.failed.emit(f"Program not found: {program}")
                return

            args = [
                f"--outdir={output_path}",
                "-Z",
                "shell-escape",
                "--reruns=2",
                f"{self._global_vars.master_dst_tex}",
            ]
            process.setProgram(str(program))
            process.setArguments(args)
            self._logger.debug(f"Running: {program} {' '.join(args)}")
            process.start()
            process.waitForFinished()

            if (
                process.exitStatus() != QProcess.ExitStatus.NormalExit
                or process.exitCode() != 0
            ):
                # include stdout too, it often has the TeX reason
                # Use .data() to get a bytes object from QByteArray (avoids pyright error)
                stderr = (
                    process.readAllStandardError()
                    .data()
                    .decode("utf-8", errors="replace")
                )
                stdout = (
                    process.readAllStandardOutput()
                    .data()
                    .decode("utf-8", errors="replace")
                )
                self._logger.error(
                    f"LaTeX error: {stderr or stdout or 'Unknown error'}"
                )
                self.failed.emit(f"LaTeX compilation failed:\n{stderr or stdout}")
                return

            # emit the path to the compiled PDF in TMP (same base name as master .tex)

            pdf_path = (
                output_path.resolve()
                / f"{self._global_vars.master_dst_tex.stem}.pdf"
            )
            if not pdf_path.exists():
                self.failed.emit("PDF not found after compile.")
                return
            self._logger.debug(f"Compiled PDF at: {pdf_path}")
            self.finished.emit(str(pdf_path))

        except Exception as e:
            self.failed.emit(str(e))


class SpellCheckHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument, spellchecker: SpellChecker):
        super().__init__(document)
        self.spellchecker = spellchecker
        # Prepare a text format for misspelled words: red wavy underline
        self.error_format = QTextCharFormat()
        self.error_format.setUnderlineColor(QColor("red"))
        # Use a special underline style for spelling errors (wavy line)
        self.error_format.setUnderlineStyle(
            QTextCharFormat.UnderlineStyle.SpellCheckUnderline
        )
        # (On most platforms, SpellCheckUnderline will appear as a red squiggly line:contentReference[oaicite:8]{index=8}.)

    def highlightBlock(self, text: str | None) -> None:
        # Use a regex to find words (sequence of alphabetic characters)
        if text is None:
            return
        for match in re.finditer(r"\b[A-Za-z']+\b", text):
            word = match.group()
            if word and word.lower() not in self.spellchecker:
                # If the word is not in the dictionary, mark it as misspelled
                start, length = match.start(), match.end() - match.start()
                self.setFormat(start, length, self.error_format)


# ----------------------------
# QTextEdit with spell-check
# ----------------------------
class SpellTextEdit(QTextEdit):
    spellchecker: SpellChecker
    highlighter: SpellCheckHighlighter

    def __init__(
        self, *args: Any, spellchecker: Optional[SpellChecker] = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.spellchecker = spellchecker if spellchecker is not None else SpellChecker()
        self.highlighter = SpellCheckHighlighter(
            strict(self.document()), self.spellchecker
        )

    def contextMenuEvent(self, e: QContextMenuEvent | None) -> None:
        menu: QMenu = strict(self.createStandardContextMenu())
        cursor: QTextCursor = self.cursorForPosition(strict(e).pos())
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word: str = cursor.selectedText()

        if word and self._is_misspelled(word):
            suggestions = sorted(list(strict(self.spellchecker.candidates(word))))
            if suggestions:
                menu.addSeparator()
                for sug in suggestions[:5]:
                    action: QAction = strict(menu.addAction(f"Replace with '{sug}'"))
                    action.triggered.connect(partial(self._on_replace, cursor=cursor, replacement=sug))  # type: ignore[arg-type]

            add_action: QAction = strict(menu.addAction("Add to dictionary"))
            add_action.triggered.connect(partial(self._on_add_to_dictionary, word=word))  # type: ignore[arg-type]

        # Show the context menu
        # In PyQt6 the method is .exec() (not exec_ as in PyQt5)
        menu.exec(strict(e).globalPos())

    def _is_misspelled(self, word: str) -> None | bool:
        # SpellChecker works with lowercased tokens
        return bool(self.spellchecker.unknown({word.lower()}))

    # Slots compatible with QAction.triggered(bool)
    def _on_replace(
        self, _checked: bool, *, cursor: QTextCursor, replacement: str
    ) -> None:
        cursor.insertText(replacement)

    def _on_add_to_dictionary(self, _checked: bool, *, word: str) -> None:
        self.spellchecker.word_frequency.add(word.lower())
        self.highlighter.rehighlight()


def strict(input: Any | None) -> Any:
    if input is None:
        raise ValueError("Input cannot be None")
    return input


# -----------------------------------
# QLineEdit with contextual fixes
# (no highlighter; QLineEdit lacks a QTextDocument)
# -----------------------------------
class SpellLineEdit(QLineEdit):
    spellchecker: SpellChecker

    def __init__(
        self, parent: QWidget | None = None, spellchecker: Optional[SpellChecker] = None
    ) -> None:
        super().__init__(parent)
        self.spellchecker = spellchecker if spellchecker is not None else SpellChecker()

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        menu: QMenu = strict(self.createStandardContextMenu())
        pos: QPoint = strict(a0).pos()
        idx: int = self.cursorPositionAt(pos)
        text: str = self.text()
        start, end = self._word_bounds(idx, text)
        word: str = text[start:end]

        if word and self._is_misspelled(word):
            suggestions = sorted(list(strict(self.spellchecker.candidates(word))))
            if suggestions:
                menu.addSeparator()
                for sug in suggestions[:5]:
                    action: QAction = strict(menu.addAction(f"Replace with '{sug}'"))
                    action.triggered.connect(partial(self._on_replace, start=start, end=end, replacement=sug))  # type: ignore[arg-type]

            add_action: QAction = strict(menu.addAction("Add to dictionary"))
            add_action.triggered.connect(partial(self._on_add_to_dictionary, word=word))  # type: ignore[arg-type]

        menu.exec(strict(a0).globalPos())

    def _is_misspelled(self, word: str) -> bool:
        return bool(self.spellchecker.unknown({word.lower()}))

    @staticmethod
    def _word_bounds(index: int, text: str) -> Tuple[int, int]:
        # Expand left/right from index to find word characters
        if not text:
            return (0, 0)
        is_word_char: Callable[[str], bool] = lambda ch: ch.isalnum() or ch == "'"
        n = len(text)
        i = max(0, min(index, n - 1))

        # If click is on a separator, nudge right to next word char (if any)
        if not is_word_char(text[i]):
            j = i
            while j < n and not is_word_char(text[j]):
                j += 1
            i = j if j < n else i

        left = i
        while left > 0 and is_word_char(text[left - 1]):
            left -= 1
        right = i
        while right < n and is_word_char(text[right]):
            right += 1
        return (left, right)

    # Slots compatible with QAction.triggered(bool)
    def _on_replace(
        self, _checked: bool, *, start: int, end: int, replacement: str
    ) -> None:
        length = max(0, end - start)
        self.setSelection(start, length)
        self.insert(replacement)

    def _on_add_to_dictionary(self, _checked: bool, *, word: str) -> None:
        self.spellchecker.word_frequency.add(word.lower())


class CaseBriefCreator(QWidget):
    def __init__(
        self, config: Global_Vars, case_briefs: CaseBriefs, logger: StructuredLogger
    ):
        self.global_vars = config
        self.super_class = case_briefs
        super().__init__()
        self.log = logger.getChildLogger("CaseBriefCreator")
        self.log.info("Opening Case Brief Creator")
        case_briefs.reload_from_sql()

        subjects: list[Subject] = [
            Subject(sub) for sub in case_briefs.catalog.repo.list_subjects()
        ]

        # labels = reload_labels(case_briefs.get_case_briefs())
        self.setWindowTitle("Case Brief Creator")
        self.setGeometry(100, 100, 600, 500)

        self.content_layout = (
            QGridLayout()
        )  # pyright: ignore[reportAttributeAccessIssue]
        self.content_layout.addWidget(
            QLabel("Create a new case brief"), 0, 0, 1, 2
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.plaintiff_entry = QLineEdit()
        self.plaintiff_entry.setPlaceholderText("Plaintiff Name")
        self.plaintiff_entry.textChanged.connect(
            self.rerender_label
        )  # pyright: ignore[reportUnknownMemberType]
        vs_label = QLabel("v.")
        self.defendant_entry = QLineEdit()
        self.defendant_entry.setPlaceholderText("Defendant Name")
        self.defendant_entry.textChanged.connect(
            self.rerender_label
        )  # pyright: ignore[reportUnknownMemberType]
        self.content_layout.addWidget(
            self.plaintiff_entry, 1, 0
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.content_layout.addWidget(
            vs_label, 1, 1
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.content_layout.addWidget(
            self.defendant_entry, 1, 2
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.citation_entry = QLineEdit()
        self.citation_entry.setPlaceholderText("Citation (Year)")
        self.content_layout.addWidget(
            self.citation_entry, 2, 0, 1, 3
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        # Subject box entry: a text box to enter subjects. When the user presses enter, the subject is added to a list of subjects.
        self.class_selector = QComboBox()
        self.class_selector.setPlaceholderText("Select a class")
        subjects_str_list = case_briefs.catalog.repo.list_courses()
        self.class_selector.addItems(
            subjects_str_list
        )  # pyright: ignore[reportUnknownMemberType]
        self.content_layout.addWidget(
            self.class_selector, 2, 4, 1, 4
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        subject_entry_box = SpellLineEdit()
        subject_entry_box.setPlaceholderText("Enter a subject (press Enter to add)")
        self.content_layout.addWidget(
            subject_entry_box, 3, 0, 1, 4
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        # A dropdown list of existing subjects that can be selected by clicking them and then pressing enter to add them
        subject_existing_combo = QComboBox()
        self.existing_subjects_str_list: list[str] = []
        for subject in subjects:
            if subject.name not in self.existing_subjects_str_list:
                self.existing_subjects_str_list.append(subject.name)
        self.existing_subjects_str_list.sort()
        self.current_subjects_str_list: list[str] = []
        subject_existing_combo.addItem("Select an existing subject")
        subject_existing_combo.addItems(
            self.existing_subjects_str_list
        )  # pyright: ignore[reportUnknownMemberType]
        subject_existing_combo.currentIndexChanged.connect(
            lambda: (
                subject_entry_box.setText(subject_existing_combo.currentText())
                if subject_existing_combo.currentText() != "Select an existing subject"
                else subject_entry_box.setText("")
            )
        )  # pyright: ignore[reportUnknownMemberType]
        # When the user presses enter in the subject entry box, the subject is added to the existing subjects combo box if it is not already present
        subject_entry_box.returnPressed.connect(
            lambda: self.add_subject(subject_entry_box.text())
        )  # pyright: ignore[reportUnknownMemberType]
        self.content_layout.addWidget(
            subject_existing_combo, 3, 4, 1, 5
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        subjects_list = QListWidget()
        # Remove a subject when it is selected and the user presses delete
        subjects_list.itemDoubleClicked.connect(
            lambda: (
                self.remove_subject(
                    strict(
                        subjects_list.currentItem()
                    ).text()  # pyright: ignore[reportOptionalMemberAccess]
                )
                if subjects_list.currentItem()
                else None
            )
        )  # pyright: ignore[reportOptionalMemberAccess, reportUnknownMemberType]
        self.content_layout.addWidget(
            subjects_list, 4, 0, 1, 5
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.facts_entry = SpellTextEdit()
        self.facts_entry.setPlaceholderText("Enter relevant facts of the case")
        self.content_layout.addWidget(
            self.facts_entry, 5, 0, 1, 5
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.procedure_entry = SpellTextEdit()
        self.procedure_entry.setPlaceholderText(
            "Enter the procedural history of the case"
        )
        self.content_layout.addWidget(
            self.procedure_entry, 6, 0, 1, 5
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.issue_entry = SpellTextEdit()
        self.issue_entry.setPlaceholderText(
            "Enter the legal issue(s) presented in the case"
        )
        self.content_layout.addWidget(
            self.issue_entry, 7, 0, 1, 5
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.holding_entry = SpellLineEdit()
        self.holding_entry.setPlaceholderText("Enter the court's holding or decision")
        self.content_layout.addWidget(
            self.holding_entry, 8, 0, 1, 5
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.principle_entry = SpellLineEdit()
        self.principle_entry.setPlaceholderText(
            "Enter the legal principle established by the case"
        )
        self.content_layout.addWidget(
            self.principle_entry, 9, 0, 1, 5
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.reasoning_entry = SpellTextEdit()
        self.reasoning_entry.setPlaceholderText(
            "Enter the court's reasoning or rationale for its decision"
        )
        self.content_layout.addWidget(
            self.reasoning_entry, 10, 0, 1, 5
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.opinions_entry = SpellTextEdit()
        self.opinions_entry.setPlaceholderText(
            "Enter any concurring or dissenting opinions (format: Person: Opinion)"
        )
        self.content_layout.addWidget(
            self.opinions_entry, 11, 0, 1, 5
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.label_entry = SpellLineEdit()
        self.label_entry.setPlaceholderText("Enter a unique label for the case")
        self.content_layout.addWidget(
            self.label_entry, 12, 0, 1, 5
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.notes_entry = SpellTextEdit()
        self.notes_entry.setPlaceholderText("Enter any case notes")
        self.content_layout.addWidget(
            self.notes_entry, 4, 5, 9, 4
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.create_button = QPushButton("Create Case Brief")
        self.create_button.clicked.connect(
            lambda: (
                self.create_case_brief(  # pyright: ignore[reportUnknownMemberType]
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
                    self.notes_entry.toPlainText(),
                )
                if self.verify_label(self.label_entry.text())
                else None
            )
        )
        self.content_layout.addWidget(
            self.create_button, 13, 0, 1, 3
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.setLayout(self.content_layout)  # pyright: ignore[reportArgumentType]
        self.setWindowTitle("Case Briefs Creator")

    def add_subject(self, subject: str):
        """Add a subject to the case brief."""
        if not subject:
            QMessageBox.warning(self, "Warning", "Subject cannot be empty.")
            return
        self.log.debug(f"Adding subject: {subject}")
        # if subject not in case_briefs.subjects:
        #    log.trace(f"Subject '{subject}' not in master subject list, adding it.")
        # case_briefs.sql.addCaseSubject(subject, self.label_entry.text())
        #    case_briefs.subjects.append(Subject(subject))
        if subject not in self.current_subjects_str_list:
            self.current_subjects_str_list.append(subject)
        self.current_subjects_str_list.sort()
        self.rerender_subjects_list()

    def remove_subject(self, subject: str):
        """Remove a subject from the case brief."""
        if not subject:
            QMessageBox.warning(self, "Warning", "Subject cannot be empty.")
            return
        self.log.debug(f"Removing subject: {subject}")
        if subject in self.current_subjects_str_list:
            self.current_subjects_str_list.remove(subject)
        self.rerender_subjects_list()

    def rerender_label(self):
        """Rerender the label in the GUI."""
        plaintiff = self.plaintiff_entry.text().strip()
        defendant = self.defendant_entry.text().strip()
        label_format = (
            plaintiff.title().replace(" ", "")
            + "V"
            + defendant.title().replace(" ", "")
        )
        self.label_entry.setText(label_format)

    def rerender_subjects_list(self):
        """Rerender the subjects list in the GUI."""
        subjects_list: QWidget | None = self.content_layout.itemAtPosition(
            4, 0
        ).widget()  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        if subjects_list is not None:
            subjects_list.clear()  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
            for subject in self.current_subjects_str_list:
                subjects_list.addItem(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
                    subject
                )

    def verify_label(self, label: str) -> bool:
        """Verify if the label is unique."""
        if any(cb.label.text == label for cb in self.super_class.items):
            QMessageBox.warning(self, "Warning", "Label must be unique.")
            return False
        return True

    def create_case_brief(
        self,
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
        notes: str,
    ):
        """Create a new case brief and save it to a file."""
        if not plaintiff or not defendant or not citation or not label or not course:
            self.log.warning(
                "Plaintiff, Defendant, Citation, Label and Course cannot be empty."
            )
            QMessageBox.warning(
                self,
                "Warning",
                "Plaintiff, Defendant, Citation, Label and Course cannot be empty.",
            )
            return

        opinions: list[Opinion] = []
        if opinions_str:
            for line in opinions_str.splitlines():
                if ":" in line:
                    person, text = line.split(":", 1)
                    opinions.append(Opinion(person.strip(), text.strip()))

        case_brief = CaseBriefData(
            subjects=[Subject(s) for s in subjects],
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
            notes=notes,
        )

        # filename = f"./Cases/{case_brief.filename}.tex"
        # case_brief.save_to_file(filename)
        self.super_class.items.append(case_brief)
        self.super_class.catalog.save(case_brief)
        self.super_class.catalog.render_to_tex(case_brief)
        # case_brief.to_sql()
        QMessageBox.information(
            self, "Success", f"Case brief '{case_brief.title}' created successfully!"
        )
        self.log.info(f"Case brief '{case_brief.title}' created successfully!")
        self.close()

    def show(self):
        super().show()
        self.log.info("Case brief creation window opened")


class _TaskSignals(QObject):
    done = pyqtSignal(int, str)  # (index, abs_pdf_path)
    error = pyqtSignal(int, str)  # (index, message)


class _CompileTask(QRunnable):
    def __init__(
        self,
        index: int,
        cb: CaseBriefData,
        global_vars: Global_Vars,
        logger: StructuredLogger,
        cancel_flag: threading.Event,
        semaphore: Optional[QSemaphore] = None,
    ):
        super().__init__()
        self.index = index
        self.cb = cb
        self.global_vars = global_vars
        self.logger = logger.getChildLogger(f"CompileTask[{index}]")
        self.cancel_flag = cancel_flag
        self.signals = _TaskSignals()
        self.semaphore = semaphore

    @pyqtSlot()
    def run(self) -> None:
        self.logger.trace(f"Thread [{self.index}] is awake")
        if self.cancel_flag.is_set():
            self.signals.error.emit(self.index, "Canceled")
            return
        try:
            if self.semaphore:
                self.semaphore.acquire()
                self.logger.trace(f"Thread [{self.index}] acquired semaphore")
            try:
                self.logger.debug(
                    f"Thread [{self.index}] starting LaTeX compile on {self.cb.label.text}"
                )
                tex_compiler = QProcessTeXCompiler(logger=self.logger)
                pdf_path: Optional[Path] = tex_compiler.compile(
                    engine=Path(str(self.global_vars.tinitex_binary)),
                    workdir=Path(str(self.global_vars.cases_dir)),
                    outdir=Path(str(self.global_vars.cases_output_dir)),
                    tex_file=(
                        Path(str(self.global_vars.cases_dir))
                        / (self.cb.filename + ".tex")
                    ),
                )
            finally:
                if self.semaphore:
                    self.semaphore.release()

            if self.cancel_flag.is_set():
                self.signals.error.emit(self.index, "Canceled")
                return
            if not pdf_path:
                self.logger.error(
                    f"LaTeX produced no output path for {self.cb.label.text}."
                )
                self.signals.error.emit(
                    self.index,
                    f"LaTeX produced no output path for {self.cb.label.text}.",
                )
                return
            abs_path = os.path.abspath(pdf_path)
            if not os.path.exists(abs_path):
                self.logger.error(
                    f"PDF not found after compile for {self.cb.label.text}."
                )
                self.signals.error.emit(
                    self.index, f"PDF not found after compile for {self.cb.label.text}."
                )
                return
            self.logger.debug(
                f"Thread [{self.index}] finished LaTeX compile successfully"
            )
            self.signals.done.emit(self.index, abs_path)
        except Exception as e:
            self.logger.error(f"Error occurred in thread [{self.index}]: {e}")
            self.signals.error.emit(self.index, str(e))


class CompileAllToPdfWorker(QObject):
    finished = pyqtSignal(list)  # list[str] absolute paths
    failed = pyqtSignal(str)  # first fatal error
    canceled = pyqtSignal()
    progress = pyqtSignal(int)  # 0..100

    def __init__(
        self,
        case_briefs: CaseBriefs,
        logger: StructuredLogger,
        global_vars: Global_Vars,
        *,
        max_workers: Optional[int] = 8,
        stop_on_error: bool = True,
    ):
        super().__init__()
        self._case_briefs = case_briefs
        for cb in self._case_briefs.items:
            self._case_briefs.catalog.render_to_tex(cb)
        self._logger = logger.getChildLogger("CompileAllToPdfWorker")
        self._global_vars = global_vars
        self._pool = QThreadPool.globalInstance()
        if self._pool is None:
            raise RuntimeError("QThreadPool.globalInstance() returned None")
        # Bound the pool; if None, Qt uses a heuristic; you can also do: min(os.cpu_count() or 2, 4)
        if max_workers is not None:
            self._pool.setMaxThreadCount(max_workers)
        self._stop_on_error = stop_on_error
        self._cancel_flag = threading.Event()

        # Shared state
        self._mutex = (
            QSemaphore(max_workers // 2) if max_workers and max_workers > 1 else None
        )
        self._mutex2 = QMutex()
        self._total = len(self._case_briefs.items)
        self._done_count = 0
        self._results: List[Optional[str]] = [None] * self._total
        self._failed_already = False

    @pyqtSlot()
    def run(self) -> None:
        self._logger.info("Starting compilation of all case briefs to PDF")
        briefs = self._case_briefs.items
        self._logger.info(f"Found {len(briefs)} case briefs to compile")
        if not briefs:
            self.failed.emit("No case briefs to compile.")
            return

        # Schedule all tasks
        for i, cb in enumerate(briefs):
            self._logger.info(f"Scheduling task for case brief {i}: {cb.label.text}")
            task = _CompileTask(
                i,
                cb,
                self._global_vars,
                self._logger,
                self._cancel_flag,
                self._mutex,
            )
            task.signals.done.connect(self._on_task_done)
            task.signals.error.connect(self._on_task_error)
            if self._pool is None:
                self.failed.emit("QThreadPool.globalInstance() returned None")
                return
            self._pool.start(task)
        if self._total == 0:
            # Edge case: no tasks
            self.finished.emit([])
        else:
            self.progress.emit(0)

    @pyqtSlot(int, str)
    def _on_task_done(self, idx: int, path: str) -> None:
        with QMutexLocker(self._mutex2):
            if self._failed_already or self._cancel_flag.is_set():
                return
            self._results[idx] = path
            self._done_count += 1
            self.progress.emit(self._done_count)
            if self._done_count == self._total:
                # All succeeded
                self.finished.emit([p for p in self._results if p is not None])

    @pyqtSlot(int, str)
    def _on_task_error(self, idx: int, message: str) -> None:
        with QMutexLocker(self._mutex2):
            if self._failed_already:
                return
            if message == "Canceled":
                # A task noticed cancellation; if every task reports cancel, you could decide what to emit.
                # For simplicity, treat first cancel as a global cancel.
                self._failed_already = True
                self._cancel_flag.set()
                self.canceled.emit()
                return

            # A real error occurred
            self._failed_already = True
            if self._stop_on_error:
                # Stop launching further work (already launched tasks will finish).
                self._cancel_flag.set()
            self.failed.emit(f"[{idx}] {message}")

    @pyqtSlot()
    def cancel(self) -> None:
        # Public API for your UI to request cancel
        self._cancel_flag.set()


class CaseBriefManager(QWidget):
    """A window for managing existing case briefs.
    This window should bring up a list of the existing case briefs,
    and allow the user to select one and search existing case briefs then edit them.
    """

    def __init__(
        self,
        global_vars: Global_Vars,
        case_briefs: CaseBriefs,
        logger: StructuredLogger,
    ):
        super().__init__()
        self.global_vars = global_vars
        self.case_briefs = case_briefs
        self.log = logger.getChildLogger("CaseBriefManager")
        self.log.info("Initializing Case Brief Manager")
        case_briefs.reload_from_sql()

        self.setWindowTitle("Case Brief Manager")
        self.setGeometry(100, 100, 600, 400)

        scrollable_area = QScrollArea(self)
        scrollable_area.setWidgetResizable(True)

        content_widget = QWidget()
        content_layout: QGridLayout = QGridLayout(content_widget)
        scrollable_area.setWidget(content_widget)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scrollable_area)

        # Add a search bar to search for case briefs
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Search case briefs...")
        content_layout.addWidget(self.search_entry, 0, 0)
        self.search_entry.textChanged.connect(
            self.filter_by_search
        )  # pyright: ignore[reportUnknownMemberType]
        self.class_dropdown = QComboBox()
        self.class_dropdown.setPlaceholderText("Select a class...")
        self.class_dropdown.addItems(
            ["All"] + case_briefs.catalog.repo.list_courses()
        )  # pyright: ignore[reportUnknownMemberType]
        self.class_dropdown.currentIndexChanged.connect(
            lambda: self.filter_by_search(
                self.class_dropdown.currentText()
                if self.class_dropdown.currentText() != "All"
                else ""
            )
        )  # pyright: ignore[reportUnknownMemberType]
        content_layout.addWidget(
            self.class_dropdown, 0, 1, 1, 2
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

        for index, case_brief in enumerate(case_briefs.items):
            case_brief_item = QLabel(case_brief.title)
            case_brief_edit_button = QPushButton("Edit")
            case_brief_edit_button.clicked.connect(
                self._make_edit_handler(case_brief)
            )  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
            case_brief_view_button = QPushButton("View")
            case_brief_view_button.clicked.connect(
                self._make_view_handler(case_brief)
            )  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
            case_brief_item.setToolTip(
                f"Course: {case_brief.course}\nCitation: {case_brief.citation}\nSubjects: {', '.join(str(s) for s in case_brief.subjects)}\nLabel: {case_brief.label.text}"
            )
            content_layout.addWidget(case_brief_item, index + 1, 0)
            content_layout.addWidget(case_brief_edit_button, index + 1, 1)
            content_layout.addWidget(case_brief_view_button, index + 1, 2)

        view_all_button = QPushButton("View All Case Briefs")
        view_all_button.clicked.connect(
            lambda: self.view_all_case_briefs(self.case_briefs)
        )  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
        content_layout.addWidget(
            view_all_button, len(case_briefs.items) + 1, 0, 1, 3
        )  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        self.setWindowTitle("Case Briefs Manager")

        # self.setLayout(layout)
        self.content_layout = (
            content_layout  # pyright: ignore[reportAttributeAccessIssue]
        )

        # CaseBriefManager.__init__
        self._pdf_windows: list[QWidget] = []
        self._threads: list[QThread] = []  # keep strong refs so threads don't get GC’d

    @pyqtSlot(CaseBriefData)
    def _make_view_handler(self, cb: CaseBriefData) -> Callable[[bool], None]:
        def _handler(_checked: bool) -> None:
            self.view_case_brief(cb)

        return _handler

    @pyqtSlot(CaseBriefData)
    def _make_edit_handler(self, cb: CaseBriefData) -> Callable[[bool], None]:
        def _handler(_checked: bool) -> None:
            self.edit_case_brief(cb)

        return _handler

    def _compile_and_open_async(self, case_brief: CaseBriefData) -> None:
        # Modal progress dialog (indeterminate)
        dlg = QProgressDialog("Compiling PDF…", "Cancel", 0, 0, self)
        dlg.setWindowTitle("Please wait")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setAutoClose(True)
        dlg.setAutoReset(True)
        dlg.setMinimumDuration(0)  # show immediately

        thread = QThread(self)
        worker = CompileSingleToPdfWorker(
            case_brief=case_brief,
            logger=self.log,
            global_vars=self.global_vars,
            tex_compiler=self.case_briefs.catalog.compiler,
        )
        worker.moveToThread(thread)

        # Wire up lifecycle
        thread.started.connect(worker.run)

        def _on_success(path: str) -> None:
            try:
                dlg.close()
                if QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
                    self.log.info(f"Opened PDF: {path}")
            finally:
                thread.quit()

        def _on_error(msg: str) -> None:
            try:
                dlg.close()
                QMessageBox.critical(self, "Error", f"Failed to compile PDF:\n{msg}")
            finally:
                thread.quit()

        worker.finished.connect(_on_success)
        worker.failed.connect(_on_error)

        # Support user cancel → politely ask the thread to stop; you can poll this in worker if needed
        def _on_cancel() -> None:
            thread.requestInterruption()
            # Optionally emit a canceled signal or just close dialog; we still quit after worker exits.
            # If your compile call is blocking and can't be interrupted, cancel will just wait to finish.

        dlg.canceled.connect(_on_cancel)

        # Ensure cleanup (and remove strong ref)
        def _cleanup() -> None:
            try:
                self._threads.remove(thread)
            except ValueError:
                pass
            thread.deleteLater()
            worker.deleteLater()

        thread.finished.connect(_cleanup)

        # Start
        self._threads.append(thread)
        dlg.show()
        thread.start()

    def view_case_brief(self, case_brief: CaseBriefData) -> None:
        """Compile the brief to PDF on a worker thread, then open it."""
        self.log.info(f"Viewing case brief '{case_brief.title}' (async compile)")
        self._compile_and_open_async(case_brief)

    def _compile_and_open_all_async(self, case_briefs: CaseBriefs) -> None:
        dlg = QProgressDialog(
            "Compiling all case briefs…",
            "Cancel",
            0,
            len(case_briefs.items),
            self,
        )
        dlg.setWindowTitle("Please wait")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setAutoClose(True)
        dlg.setAutoReset(True)
        dlg.setMinimumDuration(0)
        dlg.setRange(0, len(case_briefs.items))
        dlg.setValue(0)
        dlg.show()

        # Worker + thread
        thread = QThread(self)
        worker = CompileAllToPdfWorker(
            case_briefs=case_briefs,
            logger=self.log,
            global_vars=self.global_vars,
            max_workers=min((os.cpu_count() or 2), 4),
            stop_on_error=True,
        )
        worker.moveToThread(thread)

        # Wire
        thread.started.connect(worker.run)
        dlg.canceled.connect(worker.cancel)

        worker.progress.connect(dlg.setValue)

        def _on_failed(msg: str) -> None:
            try:
                dlg.close()
                self.log.error(f"Batch compile failed: {msg}")
                QMessageBox.critical(self, "Batch Compile Failed", msg)
            except Exception as e:
                self.log.error(f"Error showing batch compile failed dialog: {e}")

        worker.failed.connect(_on_failed)

        def _on_canceled() -> None:
            try:
                dlg.close()
                self.log.info("Batch compilation was canceled.")
                QMessageBox.information(
                    self, "Batch Compile Canceled", "Batch compilation was canceled."
                )
            except Exception as e:
                self.log.error(f"Error showing batch compile canceled dialog: {e}")

        worker.canceled.connect(_on_canceled)

        def _on_finished(paths: list[str]) -> None:
            try:
                dlg.close()
                self.log.info(f"Batch compile finished, {len(paths)} PDFs created.")
                QMessageBox.information(
                    self,
                    "Batch Compile Finished",
                    f"Successfully compiled {len(paths)} PDFs.",
                )
            except Exception as e:
                self.log.error(f"Error showing batch compile finished dialog: {e}")

        worker.finished.connect(_on_finished)

        # Cleanup thread/worker
        def _cleanup():
            thread.quit()
            thread.wait()
            worker.deleteLater()
            thread.deleteLater()

        worker.failed.connect(_cleanup)
        worker.canceled.connect(_cleanup)
        worker.finished.connect(_cleanup)

        thread.start()

    def view_all_case_briefs(self, case_briefs: CaseBriefs) -> None:
        """Compile all briefs to a single PDF on a worker thread, then open it."""
        self.log.info(f"Viewing all case briefs (async compile)")
        self._compile_and_open_all_async(case_briefs)

    def filter_by_search(self, text: str):
        """Filter the case briefs based on the search text."""
        for i in range(
            self.content_layout.rowCount()
        ):  # pyright: ignore[reportUnknownArgumentType, reportAttributeAccessIssue, reportUnknownMemberType]
            item = self.content_layout.itemAtPosition(i, 0)
            if item is None:
                continue
            widget = item.widget()
            if not isinstance(widget, QLabel):
                continue
            matches = text.lower() in widget.text().lower() or text.lower() in widget.toolTip().lower()
            # Column 1: edit button, Column 2: view button may be missing; guard None
            edit_item = self.content_layout.itemAtPosition(i, 1)
            view_item = self.content_layout.itemAtPosition(i, 2)
            edit_widget = edit_item.widget() if edit_item else None
            view_widget = view_item.widget() if view_item else None
            if matches:
                widget.show()
                if edit_widget:
                    edit_widget.show()
                if view_widget:
                    view_widget.show()
            else:
                widget.hide()
                if edit_widget:
                    edit_widget.hide()
                if view_widget:
                    view_widget.hide()

    @pyqtSlot(str)
    def edit_case_brief(self, case_brief: CaseBriefData):
        """View the details of a case brief."""
        # Open the CaseBriefCreator window with the case brief details filled in
        self.creator = CaseBriefCreator(self.global_vars, self.case_briefs, self.log)
        self.creator.plaintiff_entry.setText(case_brief.plaintiff)
        self.creator.plaintiff_entry.textChanged.disconnect()  # pyright: ignore[reportUnknownMemberType]
        self.creator.defendant_entry.setText(case_brief.defendant)
        self.creator.defendant_entry.textChanged.disconnect()  # pyright: ignore[reportUnknownMemberType]
        self.creator.citation_entry.setText(case_brief.citation)
        self.creator.class_selector.setCurrentText(case_brief.course)
        self.creator.current_subjects_str_list = [s.name for s in case_brief.subjects]
        self.creator.rerender_subjects_list()
        self.creator.facts_entry.setPlainText(case_brief.facts)
        self.creator.procedure_entry.setPlainText(case_brief.procedure)
        self.creator.issue_entry.setPlainText(case_brief.issue)
        self.creator.holding_entry.setText(case_brief.holding)
        self.creator.principle_entry.setText(case_brief.principle)
        self.creator.reasoning_entry.setText(case_brief.reasoning)
        opinions_str = "\n".join(
            f"{op.author}: {op.text}" for op in case_brief.opinions
        )
        self.creator.opinions_entry.setText(opinions_str)
        self.creator.label_entry.setText(case_brief.label.text)
        # Disable the label entry to prevent changing it
        self.creator.label_entry.setDisabled(True)
        self.creator.notes_entry.setPlainText(case_brief.notes)
        # Set the create button to update the existing case brief instead of creating a new one
        self.creator.create_button.setText("Update Case Brief")
        self.creator.create_button.clicked.disconnect()  # pyright: ignore[reportUnknownMemberType]
        self.creator.create_button.clicked.connect(
            lambda: self.update_case_brief(  # pyright: ignore[reportUnknownMemberType]
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
                self.creator.label_entry.text(),  # This will not change
            )
        )

        self.creator.show()
        self.log.info(f"Editing case brief '{case_brief.title}'")

    def update_case_brief(
        self,
        case_brief: CaseBriefData,
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
        label: str,
    ):
        """Update an existing case brief and save it to a file."""
        if not plaintiff or not defendant or not citation or not label:
            QMessageBox.warning(
                self,
                "Warning",
                "Plaintiff, Defendant, Citation and Label cannot be empty.",
            )
            return
        opinions: list[Opinion] = []
        if opinions_str:
            for opinion in opinions_str.split(","):
                if ":" in opinion:
                    person, text = opinion.split(":", 1)
                    opinions.append(Opinion(person.strip(), text.strip()))
        case_brief.plaintiff = plaintiff
        case_brief.defendant = defendant
        case_brief.citation = citation
        case_brief.course = self.creator.class_selector.currentText()
        case_brief.subjects = [Subject(s) for s in subjects]
        case_brief.facts = facts
        case_brief.procedure = procedure
        case_brief.issue = issue
        case_brief.holding = holding
        case_brief.principle = principle
        case_brief.reasoning = reasoning
        case_brief.opinions = opinions
        case_brief.notes = notes
        # Save once via catalog and render to tex
        self.case_briefs.catalog.save(case_brief)
        self.case_briefs.catalog.render_to_tex(case_brief)
        QMessageBox.information(
            self, "Success", f"Case brief '{case_brief.title}' created successfully!"
        )
        self.log.info(f"Case brief '{case_brief.title}' created successfully!")
        self.creator.close()
        self.close()

    def show(self):
        super().show()
        self.log.info("Case brief manager opened")


class SettingsWindow(QWidget):
    def __init__(
        self, config: Global_Vars, case_briefs: CaseBriefs, logger: StructuredLogger
    ):
        super().__init__()
        self.case_briefs = case_briefs
        self.global_vars = config
        self.log = logger.getChildLogger("SettingsWindow")
        self.log.info("Initializing Settings Window")
        self.setWindowTitle("Settings")
        self.setGeometry(150, 150, 400, 300)
        self.tabs = QTabWidget()
        main_layout = QVBoxLayout()

        # Courses Tab Layout
        self.courses_tab = QWidget()
        layout = QGridLayout()
        self.classes_label = QLabel("Classes:")
        layout.addWidget(self.classes_label, 0, 0)
        self.new_class_input = QLineEdit()
        layout.addWidget(self.new_class_input, 1, 0)
        self.add_class_button = QPushButton("Add Class")
        layout.addWidget(self.add_class_button, 1, 1)
        self.add_class_button.clicked.connect(self.add_class)
        self.remove_class_button = QPushButton("Remove Class")
        layout.addWidget(self.remove_class_button, 1, 2)
        self.remove_class_button.clicked.connect(self.remove_class)
        self.classes_list = QListWidget()
        self.classes_list.addItems(
            self.case_briefs.catalog.repo.list_courses()
        )  # pyright: ignore[reportUnknownMemberType] # Example classes
        layout.addWidget(self.classes_list, 2, 0, 1, 3)
        self.courses_tab.setLayout(layout)

        # Paths Tab Layout
        self.paths_tab = QWidget()
        layout = QGridLayout()
        self.paths_label = QLabel("Paths:")
        layout.addWidget(self.paths_label, 0, 0)
        self.case_render_path_label = QLabel(f"Case Render Path: ")
        layout.addWidget(self.case_render_path_label, 1, 0)
        self.case_render_path = QLabel(f"{self.global_vars.cases_output_dir}")
        layout.addWidget(self.case_render_path, 2, 0)
        self.case_render_path_selector = QFileDialog()
        self.case_render_path_button = QPushButton("Change")
        layout.addWidget(self.case_render_path_button, 2, 1)
        self.case_render_path_button.clicked.connect(self.select_case_render_path)
        self.paths_tab.setLayout(layout)

        # Backup and Restore Tab
        self.backup_tab = QWidget()
        layout = QGridLayout()
        # Select the Backup Location
        self.backup_location_label = QLabel("Backup Location:")
        layout.addWidget(self.backup_location_label, 0, 0, 1, 1)
        self.backup_restore_toggle = QPushButton("Backup")
        self.backup_restore_toggle.setCheckable(True)
        self.backup_restore_toggle.setStyleSheet(
            "background-color: green; color: white;"
        )
        self.backup_restore_toggle.toggled.connect(self.toggle_backup_restore)
        layout.addWidget(self.backup_restore_toggle, 0, 2)
        self.backup_location = QLabel(f"{self.global_vars.backup_location}")
        layout.addWidget(self.backup_location, 1, 0, 1, 3)
        self.backup_location_selector = QFileDialog()
        self.backup_location_button = QPushButton("Change")
        layout.addWidget(self.backup_location_button, 2, 0, 1, 2)
        self.backup_location_button.clicked.connect(self.select_backup_location)
        self.backup_restore_execute = QPushButton("Execute")
        layout.addWidget(self.backup_restore_execute, 2, 2)
        self.backup_restore_execute.clicked.connect(self.execute_backup_restore)
        self.backup_tab.setLayout(layout)

        self.tabs.addTab(self.courses_tab, "Courses")
        self.tabs.addTab(self.paths_tab, "Paths")
        self.tabs.addTab(self.backup_tab, "Backup/Restore")
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)
        self.setWindowTitle("Case Briefs Settings")

    def execute_backup_restore(self):
        self.log.debug("Executing backup/restore")
        if self.backup_restore_toggle.text() == "Backup":
            self.backup_cases()
        elif self.backup_restore_toggle.text() == "Restore":
            self.restore_cases()

    def toggle_backup_restore(self):
        self.log.debug("Toggling backup/restore")
        if self.backup_restore_toggle.text() == "Backup":
            self.backup_restore_toggle.setText("Restore")
            self.backup_restore_toggle.setStyleSheet(
                "background-color: red; color: white;"
            )
            self.backup_location_button.clicked.disconnect()
            self.backup_location_button.clicked.connect(self.select_restore_location)
        elif self.backup_restore_toggle.text() == "Restore":
            self.backup_restore_toggle.setText("Backup")
            self.backup_restore_toggle.setStyleSheet(
                "background-color: green; color: white;"
            )
            self.backup_location_button.clicked.disconnect()
            self.backup_location_button.clicked.connect(self.select_backup_location)

    def select_backup_location(self):
        self.log.debug("Selecting backup location")
        self.backup_location_selector.setFileMode(QFileDialog.FileMode.Directory)
        self.backup_location_selector.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)

        current_path = Path(self.backup_location.text())
        selected_dir = Path(
            self.backup_location_selector.getExistingDirectory(
                self, "Select Backup Location", ""
            )
        )
        if selected_dir and selected_dir != current_path and selected_dir != Path():
            self.backup_location.setText(f"{selected_dir}")
            self.global_vars.backup_location = Path(selected_dir)
            self.log.debug(f"Set backup location to {selected_dir}")
        else:
            self.backup_location.setText(f"{current_path}")

    def select_restore_location(self):
        self.log.debug("Selecting restore location")
        self.backup_location_selector.setFileMode(QFileDialog.FileMode.ExistingFile)
        self.backup_location_selector.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        self.backup_location_selector.setNameFilter("SQL Files (*.sql)")

        current_path = Path(self.backup_location.text())
        selected_dir = Path(
            self.backup_location_selector.getOpenFileName(
                self, "Select Restore Location", ""
            )[0]
        )
        if selected_dir and selected_dir != current_path and selected_dir != Path():
            self.backup_location.setText(f"{selected_dir}")
            # self.global_vars.tmp_dir = Path(selected_dir).parent
            self.log.debug(f"Set restore location to {selected_dir}")
        else:
            self.backup_location.setText(f"{current_path}")

    def backup_cases(self):
        self.log.debug("Backing up cases")
        curr_dt = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = (
            Path(self.backup_location.text()) / f"CaseBriefBackup_{curr_dt}.sql"
        )
        self.case_briefs.catalog.repo.export_db_file(backup_path)
        self.log.info(f"Cases backed up to {backup_path}")
        # Popup a confirmation
        QMessageBox.information(
            self,
            "Backup Complete",
            f"{len(self.case_briefs.items)} cases backed up.",
        )

    def restore_cases(self):
        self.log.debug("Restoring cases")
        backup_path = Path(self.backup_location.text())
        self.case_briefs.catalog.repo.restore_db_file(backup_path)
        self.case_briefs.reload_from_sql()
        # Save all case briefs to .tex files
        for cb in self.case_briefs.items:
            self.case_briefs.catalog.render_to_tex(cb)
        self.log.info(f"Cases restored from {backup_path}")
        # Popup a confirmation
        QMessageBox.information(
            self,
            "Restore Complete",
            f"{len(self.case_briefs.items)} cases restored.",
        )

    def select_case_render_path(self):
        self.log.debug("Selecting case render path")
        current_path = Path(self.case_render_path.text())
        selected_dir = Path(
            self.case_render_path_selector.getExistingDirectory(
                self, "Select Case Render Path", ""
            )
        )
        if selected_dir and selected_dir != current_path and selected_dir != Path():
            self.case_render_path.setText(f"{selected_dir}")
            self.global_vars.cases_output_dir = Path(selected_dir)
            self.log.debug(f"Set case render path to {selected_dir}")
        else:
            self.case_render_path.setText(f"{current_path}")

    def add_class(self):
        new_class = self.new_class_input.text()
        if new_class:
            self.case_briefs.catalog.repo.add_course(new_class)
            self.classes_list.addItem(new_class)

    def remove_class(self):
        selected_item = self.classes_list.currentItem()
        if selected_item:
            self.case_briefs.catalog.repo.remove_course(selected_item.text())
            self.classes_list.takeItem(self.classes_list.row(selected_item))

    def show(self):
        super().show()
        self.log.info("Settings window opened")


from typing import Callable, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QProgressBar,
)


class Initializer:
    def __init__(
        self,
        console: QTextEdit,
        config: Global_Vars,
        logger: StructuredLogger,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> None:
        self.global_vars = config
        self.log = logger.getChildLogger("Initializer")
        super().__init__()
        self.complete: bool = False
        self.console: QTextEdit = console
        self._on_progress = on_progress
        self._step: int = 0
        self._todo: list[tuple[Callable[..., None], tuple[Path, ...]]] = [
            (self.ensure_dir, (self.global_vars.tmp_dir,)),
            (self.ensure_dir, (self.global_vars.cases_dir,)),
            (self.ensure_dir, (self.global_vars.cases_output_dir,)),
            (self.ensure_dir, (self.global_vars.tex_src_dir,)),
            (self.ensure_file, (self.global_vars.master_src_tex,)),
            (self.ensure_file, (self.global_vars.master_src_sty,)),
            (self.ensure_dir, (self.global_vars.tex_dst_dir,)),
            (
                self.ensure_move,
                (self.global_vars.master_src_sty, self.global_vars.master_dst_sty),
            ),
            (
                self.ensure_move,
                (self.global_vars.master_src_tex, self.global_vars.master_dst_tex),
            ),
            (self.ensure_dir, (self.global_vars.sql_dst_dir,)),
            (self.ensure_db, (self.global_vars.sql_dst_file,)),
        ]
        self._total: int = len(self._todo)  # 4 dirs + 2 files + 1 db

        # Steps
        for func, arg in self._todo:
            func(arg)

        self.log.info("Completing initialization")
        self.console.append("Completing initialization\n")
        self.complete = True
        self._emit_progress("Initialization complete")

    def _emit_progress(self, msg: str) -> None:
        # bump progress by one step and report
        self._step += 1
        if self._on_progress is not None:
            self._on_progress(self._step, self._total, msg)

    def ensure_dir(self, path: tuple[Path]) -> None:
        path_str = path[0]
        try:
            relative_print_path = path_str.relative_to(self.global_vars.bundle_dir)
        except ValueError:
            relative_print_path = path_str
        self.log.debug(f"Ensuring directory exists: {relative_print_path}")
        self.console.append(f"Ensuring directory exists: {relative_print_path}\n")
        if not path_str.exists():
            self.log.debug(f"Directory does not exist, creating: {relative_print_path}")
            self.console.append(
                f"Directory does not exist, creating: {relative_print_path}\n"
            )
            path_str.mkdir(parents=True, exist_ok=True)
            self.log.info(f"Created directory: {relative_print_path}")
            self.console.append(f"Created directory: {relative_print_path}\n")
        else:
            self.log.info(f"Directory already exists: {relative_print_path}")
            self.console.append(f"Directory already exists: {relative_print_path}\n")
        self._emit_progress(f"Ensured directory {relative_print_path}")

    def ensure_file(self, file: tuple[Path]) -> None:
        file_path = file[0]
        try:
            relative_print_path = file_path.relative_to(self.global_vars.bundle_dir)
        except ValueError:
            relative_print_path = file_path
        self.log.debug(f"Ensuring file exists: {relative_print_path}")
        self.console.append(f"Ensuring file exists: {relative_print_path}\n")
        if not file_path.exists():
            self.log.debug(f"File does not exist, creating: {relative_print_path}")
            self.console.append(
                f"File does not exist, creating: {relative_print_path}\n"
            )
            file_path.touch(exist_ok=True)
            self.log.info(f"Created file: {relative_print_path}")
            self.console.append(f"Created file: {relative_print_path}\n")
        else:
            self.log.info(f"File already exists: {relative_print_path}")
            self.console.append(f"File already exists: {relative_print_path}\n")
        self._emit_progress(f"Ensured file {relative_print_path}")

    def ensure_db(self, db: tuple[Path]) -> None:
        db_path = db[0]
        try:
            relative_print_path = db_path.relative_to(self.global_vars.bundle_dir)
        except ValueError:
            relative_print_path = db_path
        self.log.debug(f"Ensuring database exists: {relative_print_path}")
        self.console.append(f"Ensuring database exists: {relative_print_path}\n")

        def ensure_db(db_path: Path) -> bool:
            if db_path.exists():
                try:
                    conn = sqlite3.connect(db_path)
                    conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    conn.close()
                    return True
                except sqlite3.DatabaseError:
                    return False
            return False

        if not ensure_db(db_path):
            self.log.info(f"Created database: {relative_print_path}")
            self.console.append(f"Created database: {relative_print_path}\n")
        else:
            self.log.info(f"Database already exists: {relative_print_path}")
            self.console.append(f"Database already exists: {relative_print_path}\n")
        self._emit_progress(f"Ensured database {relative_print_path}")

    def ensure_move(self, src_dst: tuple[Path, Path]) -> None:
        src = src_dst[0]
        dest = src_dst[1]

        try:
            relative_src_path = src.relative_to(self.global_vars.bundle_dir)
        except ValueError:
            relative_src_path = src
        try:
            relative_dest_path = dest.relative_to(self.global_vars.bundle_dir)
        except ValueError:
            relative_dest_path = dest
        self.log.debug(
            f"Ensuring file move from {relative_src_path} to {relative_dest_path}"
        )
        self.console.append(
            f"Ensuring file move from {relative_src_path} to {relative_dest_path}\n"
        )
        if src.exists():
            self.log.debug(f"Source file exists, moving: {relative_src_path}")
            self.console.append(f"Source file exists, moving: {relative_src_path}\n")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(src.read_text())
            self.log.info(f"Moved file to: {relative_dest_path}")
            self.console.append(f"Moved file to: {relative_dest_path}\n")
        else:
            self.log.warning(f"Source file does not exist: {relative_src_path}")
            self.console.append(f"Source file does not exist: {relative_src_path}\n")
        self._emit_progress(
            f"Ensured file move {relative_src_path} to {relative_dest_path}"
        )


class CaseBriefInit(QMainWindow):
    def __init__(
        self, config: Global_Vars, case_briefs: CaseBriefs, logger: StructuredLogger
    ):
        self.super_class = case_briefs
        self.global_vars = config
        self.log = logger.getChildLogger("InitWindow")
        super().__init__()
        self.log.info("Initializing Case Briefs Initialization Window")
        self.setWindowTitle("Case Briefs Initialization")
        self.setGeometry(100, 100, 600, 400)

        # Central container
        central = QWidget(self)
        layout = QVBoxLayout(central)

        # Console
        self.initializer_console = QTextEdit(central)
        self.initializer_console.setReadOnly(True)
        layout.addWidget(self.initializer_console)

        # Progress bar (between console and Next)
        self.progress = QProgressBar(central)
        self.progress.setRange(0, 7)  # matches Initializer._total
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Next button
        next_button = QPushButton("Next", central)
        next_button.setEnabled(False)  # enable when done
        layout.addWidget(next_button)
        next_button.clicked.connect(self.close)

        self.setCentralWidget(central)

        # Kick off initialization and wire progress updates
        def on_progress(step: int, total: int, msg: str) -> None:
            self.progress.setMaximum(total)
            self.progress.setValue(step)
            if step >= total:
                next_button.setEnabled(True)

        self.initializer = Initializer(
            self.initializer_console,
            on_progress=on_progress,
            config=self.global_vars,
            logger=self.log,
        )


class CaseBriefApp(QMainWindow):
    def __init__(
        self,
        global_vars: Global_Vars,
        case_briefs: CaseBriefs,
        logger: StructuredLogger,
    ):
        super().__init__()
        self.case_briefs = case_briefs
        self.global_vars = global_vars
        self.log = logger.getChildLogger("App")
        self.setWindowTitle("Case Briefs Manager")
        self.setGeometry(100, 100, 600, 400)
        self.log.info("Initializing Case Briefs Application")

        layout = QGridLayout()
        new_case_brief_button = QPushButton("Create Case Brief")
        new_case_brief_button.clicked.connect(
            self.create_case_brief
        )  # pyright: ignore[reportUnknownMemberType]
        layout.addWidget(new_case_brief_button, 0, 0, 1, 1)

        view_case_briefs_button = QPushButton("View Case Briefs")
        view_case_briefs_button.clicked.connect(
            self.view_case_briefs
        )  # pyright: ignore[reportUnknownMemberType]
        layout.addWidget(view_case_briefs_button, 1, 0, 1, 1)

        render_pdf_button = QPushButton("Render PDF")
        render_pdf_button.clicked.connect(
            self.render_pdf
        )  # pyright: ignore[reportUnknownMemberType]
        layout.addWidget(render_pdf_button, 2, 0, 1, 1)

        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(
            self.open_settings
        )  # pyright: ignore[reportUnknownMemberType]
        layout.addWidget(settings_button, 3, 0, 1, 1)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.setWindowTitle("Case Briefs App")
        # after super().__init__(...)
        self._threads: list[QThread] = []  # keep strong refs so threads don't get GC’d

    def create_case_brief(self):
        # Logic to create a new case brief
        self.log.info("Creating a new case brief...")
        self.creator = CaseBriefCreator(self.global_vars, self.case_briefs, self.log)
        self.creator.show()

    def view_case_briefs(self):
        # Logic to view existing case briefs
        self.log.info("Viewing existing case briefs...")
        self.manager = CaseBriefManager(
            self.global_vars, self.case_briefs, logger=self.log
        )
        self.manager.show()

    def _render_and_open_async(self) -> None:
        dlg = QProgressDialog("Rendering PDF…", "Cancel", 0, 0, self)
        dlg.setWindowTitle("Please wait")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setAutoClose(True)
        dlg.setAutoReset(True)
        dlg.setMinimumDuration(0)
        dlg.show()

        thread = QThread(self)
        worker = RenderAllToPdfWorker(self.case_briefs, self.global_vars, self.log)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        def _on_success(tmp_pdf_path: str) -> None:
            try:
                dlg.close()

                # Mirror old behavior: message → move → open → clean TMP
                stem = self.global_vars.master_dst_tex.stem
                downloads_dir = Path.home() / "Downloads"
                dest = downloads_dir / f"{stem}.pdf"

                # If a file already exists, replace it
                if dest.exists():
                    try:
                        dest.unlink()
                    except Exception:
                        # fallback to overwrite via replace()
                        pass

                try:
                    shutil.move(tmp_pdf_path, str(dest))
                except Exception:
                    # if move fails across devices, copy & then remove
                    shutil.copy2(tmp_pdf_path, dest)
                    try:
                        Path(tmp_pdf_path).unlink(missing_ok=True)  # py>=3.8
                    except Exception:
                        pass

                QMessageBox.information(
                    self,
                    "PDF Rendered",
                    f"PDF for {stem} has been generated successfully.",
                )

                # Open the **moved** file
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(dest)))

                # Clean TMP like the synchronous version
                try:
                    clean_dir(self.global_vars.tmp_dir)
                except Exception:
                    # non-fatal: leave TMP alone if cleanup fails
                    pass

            finally:
                thread.quit()

        def _on_error(msg: str) -> None:
            try:
                dlg.close()
                QMessageBox.critical(self, "LaTeX Error", msg)
            finally:
                thread.quit()

        worker.finished.connect(_on_success)
        worker.failed.connect(_on_error)

        def _on_cancel() -> None:
            thread.requestInterruption()

        dlg.canceled.connect(_on_cancel)

        def _cleanup() -> None:
            try:
                self._threads.remove(thread)
            except ValueError:
                pass
            thread.deleteLater()
            worker.deleteLater()

        thread.finished.connect(_cleanup)

        self._threads.append(thread)
        thread.start()

    def render_pdf(self):
        # # Logic to render the case brief as a PDF
        self.log.info("Rendering PDF for the case brief...")
        self._render_and_open_async()

    def open_settings(self):
        # Logic to open the settings window
        self.log.info("Opening settings...")
        self.settings = SettingsWindow(
            self.global_vars, self.case_briefs, logger=self.log
        )
        self.settings.show()
