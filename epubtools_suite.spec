# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec dla epubTools Suite
# Buduj: python -m PyInstaller epubtools_suite.spec --clean

import os

# Bundlujemy pliki epubQTools (są w tym samym katalogu — fork)
datas = [
    ('__main__.py', '.'),
    ('lib',         'lib'),
    ('NOTICE',      '.'),
]

a = Analysis(
    ['gui_main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'PIL', 'cv2',
        'pandas', 'PyQt5', 'PyQt6', 'wx', 'gi',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='epubTools_Suite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
