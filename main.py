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

from CaseCatalog import (
    CaseBriefs,
    CaseCatalog,
)
from GUIRefactor import CaseBriefInit, CaseBriefApp
from Global_Vars import Global_Vars
from QProcessTeXCompiler import QProcessTeXCompiler
from RegexLatexCodec import RegexLatexCodec
from SQLiteCaseBriefRepository import SQLiteCaseBriefRepository
from logger import StructuredLogger
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon


# Start by finding and loading all of the case brief files in ./Cases

if __name__ == "__main__":
    logger = StructuredLogger("CaseBriefs", log_file="CaseBriefs.log", level="Trace")
    logger.info("Starting Case Briefs Manager Application")
    global_vars = Global_Vars(logger=logger)

    sqlite_repo = SQLiteCaseBriefRepository(
        global_vars.sql_dst_file, global_vars.sql_create, logger
    )
    regex_latex_codec = RegexLatexCodec()
    qprocess_tex_compiler = QProcessTeXCompiler(logger)
    catalog = CaseCatalog(
        sqlite_repo,
        regex_latex_codec,
        qprocess_tex_compiler,
        global_vars,
        logger,
    )
    briefs = CaseBriefs(catalog)
    briefs.reload_from_sql()

    app: QApplication = QApplication(sys.argv)
    app.setWindowIcon(QIcon("ui/text.book.closed.png"))
    init_window: CaseBriefInit = CaseBriefInit(global_vars, briefs, logger=logger)
    init_window.show()
    if init_window.initializer.complete:
        logger.info("Initialization complete, launching main application")
    while init_window.isVisible():
        app.processEvents()
    app_window: CaseBriefApp = CaseBriefApp(global_vars, briefs, logger)
    app_window.show()
    
    # Check for updates on startup if enabled
    try:
        app_window.check_for_updates_on_startup()
    except Exception as e:
        logger.error(f"Error during startup update check: {e}")
    
    sys.exit(app.exec())
else:
    print("This module is intended to be run as a standalone application.")
    print("Please run it directly to use the Case Briefs Manager.")
