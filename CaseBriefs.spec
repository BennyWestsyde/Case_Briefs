# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=['./bin'],
    binaries=[('/usr/bin/sqlite3', 'bin'), ("bin/tinitex","bin")],
    datas=[('CaseBriefs.tex', '.'), ('lawbrief.sty', '.'), ('SQL', 'SQL'), ('Cases', 'Cases'), ('bin', 'bin')],
    hiddenimports=[],
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
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
