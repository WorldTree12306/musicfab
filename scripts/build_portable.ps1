# Build a portable Windows executable for musicfab (lite build: no torch/demucs)
# and bundle it with THIRD_PARTY_NOTICES.md into a versioned zip for release.
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts/build_portable.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

# always drive the *current* interpreter, whatever "python" resolves to
$python = (Get-Command python).Source
if (-not $python) { Write-Error "python not found on PATH"; exit 1 }

& $python -m pip install --quiet pyinstaller

if (-not (Test-Path "src/musicfab/__main__.py")) {
    Write-Error "src/musicfab/__main__.py is missing; it is a tracked file - restore it from git instead of generating it here."
    exit 1
}

# single canonical build recipe (onefile + numba runtime hook + datas/excludes)
& $python -m PyInstaller --noconfirm --clean musicfab.spec
if (-not (Test-Path "dist/musicfab.exe")) {
    Write-Error "PyInstaller did not produce dist/musicfab.exe"
    exit 1
}

# third-party licence notices (shipped inside the release zip)
& $python scripts/collect_licenses.py -o dist/THIRD_PARTY_NOTICES.md
if (-not (Test-Path "dist/THIRD_PARTY_NOTICES.md")) {
    Write-Error "scripts/collect_licenses.py did not produce dist/THIRD_PARTY_NOTICES.md"
    exit 1
}

$version = (& $python -c "import musicfab; print(musicfab.__version__)") | Select-Object -First 1
$version = "$version".Trim()
$zip = "dist/musicfab-$version-win64.zip"
Compress-Archive -Path "dist/musicfab.exe", "dist/THIRD_PARTY_NOTICES.md" -DestinationPath $zip -Force

Write-Host ""
Write-Host "built:  dist/musicfab.exe"
Write-Host "notices: dist/THIRD_PARTY_NOTICES.md"
Write-Host "release zip: $zip"
Write-Host "note: demucs (RipX-style separation) requires torch and is not bundled in this lite build."
Write-Host "note: onefile builds need a writable TEMP; if you see 'Could not create temporary directory',"
Write-Host "      run the exe with TEMP pointing to a writable folder."
