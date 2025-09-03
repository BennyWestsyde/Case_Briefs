# Case Brief Manager

Case Brief Manager is a PyQt6 desktop application for creating and managing law school case briefs. It generates LaTeX documents that are compiled into formatted PDF case briefs, with support for SQLite database storage and PyInstaller-based distribution for macOS.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Bootstrap and Dependencies
- Install Python dependencies:
  - `python3 -m pip install --user -r requirements.txt` -- takes 1-2 seconds if packages cached, 30-60 seconds for fresh install. NEVER CANCEL.
  - Required packages: PyQt6, PyQt6-stubs, PySpellChecker
- Install LaTeX environment (Linux/Ubuntu):
  - `sudo apt-get update && sudo apt-get install -y texlive-latex-base texlive-latex-extra texlive-fonts-recommended` -- takes 5-10 minutes. NEVER CANCEL. Set timeout to 15+ minutes.
- Install GUI dependencies (for Linux):
  - `sudo apt-get install -y xvfb python3-pyqt6 libgl1-mesa-dev mesa-utils` -- takes 2-3 minutes. NEVER CANCEL.

### Building and Testing
- Build with PyInstaller:
  - `pip install pyinstaller` -- takes 10-20 seconds
  - `pyinstaller --onedir main.py` -- takes 8-12 seconds. NEVER CANCEL. Set timeout to 60+ seconds.
  - Output appears in `dist/main/` directory
- Test LaTeX compilation:
  - `cd tex_src && pdflatex --interaction=nonstopmode CaseBriefs.tex` -- takes 0.5-1 seconds. NEVER CANCEL.
  - Generates CaseBriefs.pdf with all case briefs (typically 35-40 pages)

### Running the Application
- IMPORTANT: GUI requires X11 environment. On headless Linux systems, use:
  - `export QT_QPA_PLATFORM=offscreen && python3 main.py`
  - Application will start initialization window, then main application window
- For local development with display: `python3 main.py`
- Application uses SQLite database at `SQL/Cases.sqlite` with 36 pre-loaded case briefs

## Validation

### Always validate these core workflows:
1. **Dependency Installation Test**: Run `python3 -c "import PyQt6.QtWidgets; print('PyQt6 working')"` to verify PyQt6 installation
2. **Database Connectivity Test**: Run `python3 -c "from CaseBrief import case_briefs, global_vars; print('Database loaded successfully'); print('Base directory:', global_vars.res_dir)"`
3. **LaTeX Compilation Test**: 
   - `cd tex_src && pdflatex --interaction=nonstopmode CaseBriefs.tex`
   - Verify CaseBriefs.pdf is created with correct page count (35-40 pages)
4. **Application Startup Test**: 
   - `export QT_QPA_PLATFORM=offscreen && timeout 30 python3 main.py`
   - Should initialize successfully and show "Initialization complete" in logs

### Required LaTeX Packages
The lawbrief.sty style file requires these LaTeX packages (all included in texlive-latex-extra):
- xparse, pgfkeys, fancyhdr, geometry, titlesec, etoolbox, listofitems, hyperref, makeidx, subfiles

### PyInstaller Build Validation
- ALWAYS test PyInstaller build after making Python code changes
- Build artifacts appear in `dist/main/` with executable and `_internal/` directory
- Warning about missing libxcb-cursor.so.0 is expected and non-critical on Linux

## Common Tasks

### Repository Structure
```
/home/runner/work/Case_Briefs/Case_Briefs/
├── main.py                  # Application entry point
├── GUI.py                   # Main GUI implementation  
├── CaseBrief.py             # Core case brief logic and database handling
├── logger.py                # Structured logging implementation
├── requirements.txt         # Python dependencies
├── CaseBriefs.spec         # PyInstaller configuration (macOS-specific paths)
├── Cases/                   # Case brief LaTeX and PDF files (36 cases)
│   ├── *.tex               # Individual case brief LaTeX files
│   ├── *.pdf               # Compiled PDFs for individual cases
│   └── Output/             # Generated output directory
├── SQL/                     # Database files and scripts
│   ├── Cases.sqlite        # Main SQLite database
│   ├── Create_DB.sql       # Database creation script
│   └── Wipe_DB.sql         # Database reset script
├── tex_src/                # LaTeX templates and configuration
│   ├── CaseBriefs.tex      # Main LaTeX document template
│   ├── lawbrief.sty        # Custom LaTeX style package
│   └── CaseBriefs.pdf      # Compiled master document
├── bin/                     # Platform-specific binaries
│   └── tinitex             # macOS-only TeX binary (ARM64)
└── .github/workflows/       # CI/CD configuration
    └── compile.yml         # macOS build workflow
```

### Database Schema
- Tables: Courses, Subjects, Opinions, Cases, CaseSubjects, CaseOpinions
- 36 pre-loaded case briefs covering various legal subjects (Negligence, Torts, Contracts, etc.)
- Database operations handled through CaseBrief.py module

### Platform-Specific Notes
- **macOS**: Uses custom tinitex binary and PyInstaller for app distribution
- **Linux**: Uses system TeX Live installation, tinitex binary will not execute (different architecture)
- **Development**: Works on both platforms with appropriate dependencies installed

### Key Timing Expectations
- Python dependency install: 1-60 seconds (depending on cache)
- LaTeX installation: 5-10 minutes -- NEVER CANCEL, always set 15+ minute timeout
- LaTeX compilation: 0.5-1 seconds for full document
- PyInstaller build: 8-12 seconds -- set 60+ second timeout
- Application startup: 3-5 seconds to initialization complete

### Known Issues and Workarounds
- GUI requires X11/display server - use `QT_QPA_PLATFORM=offscreen` for headless environments
- tinitex binary is macOS ARM64 only - use system pdflatex on other platforms
- PyInstaller warnings about libxcb-cursor.so.0 are expected on Linux and non-critical
- Case files use subfiles LaTeX package for modular document structure

### Always run these validation commands before committing changes:
1. `python3 -c "from CaseBrief import global_vars; print('Globals loaded successfully')"`
2. `cd tex_src && pdflatex --interaction=nonstopmode CaseBriefs.tex`
3. `export QT_QPA_PLATFORM=offscreen && timeout 30 python3 main.py`
4. `pyinstaller --onedir main.py` (if Python code changes made)