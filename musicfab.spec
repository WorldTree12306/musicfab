# -*- mode: python ; coding: utf-8 -*-
# musicfab portable (lite) build recipe — the single canonical spec file.
#
# Usage (from the repository root):
#   python -m PyInstaller --noconfirm --clean musicfab.spec
#
# Produces dist/musicfab.exe (onefile, no torch/demucs/PySide6).
# scripts/build_portable.ps1 wraps this call and additionally bundles
# THIRD_PARTY_NOTICES.md into a versioned zip for release.
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = []
hiddenimports = ['music21', 'verovio', 'guitarpro', 'mido']
datas += collect_data_files('basic_pitch')
datas += collect_data_files('music21')
datas += collect_data_files('verovio')
hiddenimports += collect_submodules('musicfab')


a = Analysis(
    ['src/musicfab/__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['scripts/pyi_rthook_numba.py'],
    excludes=['torch', 'demucs', 'tensorflow', 'pandas', 'matplotlib', 'tkinter', 'openpyxl', 'IPython', 'notebook', 'jupyter', 'PyQt5', 'PySide6', 'PIL'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='musicfab',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
