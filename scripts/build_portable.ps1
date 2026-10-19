# Build a portable Windows executable for musicfab (lite build: no torch/demucs).
# Usage:  powershell -ExecutionPolicy Bypass -File scripts/build_portable.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

python -m pip install --quiet pyinstaller
if (-not (Test-Path "src/musicfab/__main__.py")) {
@'
from musicfab.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
'@ | Set-Content -Encoding utf8 "src/musicfab/__main__.py"
}

python -m PyInstaller `
  --noconfirm --clean --onefile `
  --name musicfab `
  --runtime-hook scripts/pyi_rthook_numba.py `
  --collect-data basic_pitch `
  --collect-submodules musicfab `
  --hidden-import music21 `
  --hidden-import verovio `
  --hidden-import guitarpro `
  --hidden-import mido `
  --exclude-module torch `
  --exclude-module demucs `
  --exclude-module tensorflow `
  "src/musicfab/__main__.py"

Write-Host ""
Write-Host "built: dist/musicfab.exe"
Write-Host "note: demucs (RipX-style separation) requires torch and is not bundled in this lite build."
Write-Host "note: onefile builds need a writable TEMP; if you see 'Could not create temporary directory',"
Write-Host "      run the exe with TEMP pointing to a writable folder, or build with --onedir instead of --onefile."
