param(
  [string]$Board = "192.168.50.1",
  [string]$User = "lckfb"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$AppDir = Join-Path $RepoRoot "apps\filemgr"

New-Item -ItemType Directory -Force -Path $AppDir | Out-Null

scp "${User}@${Board}:/userdata/server/apps/filemgr/app.py" (Join-Path $AppDir "app.py")

Write-Host "Collected backend app.py into $AppDir"
Write-Host "Review files before committing. Do not commit real users.json, devices.json, keys, or tokens."
