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

from logger import StructuredLogger
log = StructuredLogger("Main","TRACE","CaseBriefs.log",True,None,True,True)

log.info("Starting Case Briefs Application")
import os
import sys
from PyQt6.QtWidgets import (
    QApplication
)
from PyQt6.QtGui import QIcon
from GUI import CaseBriefApp



log.debug("Determining base directory")
if getattr(sys, 'frozen', False):  # running as frozen
    base_dir = sys.__file__  # PyInstaller bundle dir for one-file, or internal dir for one-folder
    log.trace("Running in packaged mode with base directory: %s", base_dir)
else:
    base_dir = os.path.dirname(__file__)
    log.trace("Running in normal mode with base directory: %s", base_dir)

# Start by finding and loading all of the case brief files in ./Cases

if __name__ == "__main__":
    # Create a simple gui for the application
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('ui/text.book.closed.png'))
    window = CaseBriefApp()
    window.show()
    sys.exit(app.exec())
else:
    print("This module is intended to be run as a standalone application.")
    print("Please run it directly to use the Case Briefs Manager.")