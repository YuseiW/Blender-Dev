$ErrorActionPreference = "Stop"

# Move to project root
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "=== GitHub Sync Start ==="

# Stage all changes
git add -A

if ($LASTEXITCODE -ne 0) {
    Write-Host "git add failed."
    exit 1
}

# Check whether there is anything staged
git diff --cached --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host "No changes to commit."
    exit 0
}

# Commit
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

git commit -m "Auto backup: $timestamp"

if ($LASTEXITCODE -ne 0) {
    Write-Host "git commit failed."
    exit 1
}

# Pull remote changes before pushing
git pull --rebase origin main

if ($LASTEXITCODE -ne 0) {
    Write-Host "git pull failed."
    exit 1
}

# Push
git push origin main

if ($LASTEXITCODE -ne 0) {
    Write-Host "git push failed."
    exit 1
}

Write-Host "=== GitHub Sync Complete ==="