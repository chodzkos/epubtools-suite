# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec dla epubTools Suite
# Buduj: python -m PyInstaller epubtools_suite.spec --clean

import os

# Bundlujemy pliki epubQTools w podkatalogu epubqtools/ — NIE w katalogu głównym _MEI.
# Dzięki temu subprocess (dowolna wersja Pythona) nie znajdzie .pyd z Python 3.11
# w sys.path[0] i nie dostanie błędu konfliktu DLL.
datas = [
    ('__main__.py', 'epubqtools'),
    ('lib',         'epubqtools/lib'),
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
    icon='icon.ico',
)
