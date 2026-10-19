# Publish the local musicfab repository to GitHub (SSH, without gh CLI).
# Usage:
#   1. Create an EMPTY repo at https://github.com/new (e.g. musicfab, public).
#   2. powershell -ExecutionPolicy Bypass -File scripts/publish_github.ps1 -RepoUrl git@github.com:WorldTree12306/musicfab.git
param(
  [Parameter(Mandatory = $true)][string]$RepoUrl
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

# github.com:22 is blocked on this network; ~/.ssh/config already maps
# github.com -> ssh.github.com:443. The explicit key avoids ssh-agent issues.
$env:GIT_SSH_COMMAND = 'ssh -i "' + $env:USERPROFILE + '\.ssh\id_ed25519_github" -o IdentitiesOnly=yes'

$existing = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0 -and $existing) {
  git remote set-url origin $RepoUrl
} else {
  git remote add origin $RepoUrl
}
Write-Host "remote: $RepoUrl"
git push -u origin main
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "push failed. If the remote repo is not empty, try:" -ForegroundColor Yellow
  Write-Host "  git pull --rebase origin main   # then re-run this script"
  exit 1
}
Write-Host "published: $RepoUrl"
