# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = [('D:/Python313/Lib/site-packages/librosa', 'librosa'), ('D:/Python313/Lib/site-packages/resampy', 'resampy')]
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
    runtime_hooks=[],
    excludes=['torch', 'demucs', 'tensorflow', 'pandas', 'matplotlib', 'tkinter', 'openpyxl', 'IPython', 'notebook', 'jupyter', 'PyQt5', 'PySide6', 'PIL'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='musicfab_onedir',
    debug=False,
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
    name='musicfab_onedir',
)
