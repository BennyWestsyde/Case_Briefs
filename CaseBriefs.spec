# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

proj_dir = Path(r"/Users/bennettwestfall/Library/Mobile Documents/com~apple~CloudDocs/the_vault/school_work/2025/Fall/Case_Briefs")

# Collect package, binaries, and data for pyspellchecker (imported as 'spellchecker')
sc_datas, sc_binaries, sc_hidden = collect_all("spellchecker")

a = Analysis(
    ['main.py'],
    pathex=[str(proj_dir)],
    binaries=[('bin/tinitex', 'bin')] + sc_binaries,
    datas=[
        ('tex_src', 'tex_src'),
        ('SQL/Create_DB.sql', 'SQL'),
        ('SQL/Wipe_DB.sql', 'SQL'),
        #('Cases', 'Cases'),
        ('bin', 'bin'),
    ] + sc_datas,
    hiddenimports=sc_hidden + ['spellchecker'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CaseBriefs',
    debug=False,                 # keep while debugging
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,               # you’re launching from terminal; flip to False when distributing
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CaseBriefs',
)

app = BUNDLE(
    coll,
    name='CaseBriefs.app',
    icon=None,
    bundle_identifier='com.mycompany.casebriefs',
)
