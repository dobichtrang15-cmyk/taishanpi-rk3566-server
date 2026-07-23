param(
    [string]$VersionLabel = (Get-Date -Format 'yyyyMMdd-HHmmss')
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$releaseRoot = Join-Path $projectRoot 'release'
$packageName = "taishanpi-rk3566-server-$VersionLabel"
$stagingDir = Join-Path $releaseRoot $packageName
$zipPath = Join-Path $releaseRoot "$packageName.zip"

$includeItems = @(
    'apps',
    'deploy',
    'docs',
    'miniapp',
    'qt',
    'scripts',
    'www',
    '.gitattributes',
    '.gitignore',
    'README.md',
    'project.config.json'
)

$removePatterns = @(
    '.git',
    'release',
    'node_modules',
    '__pycache__',
    '.venv',
    'venv'
)

$removeFiles = @(
    'apps\filemgr\users.json',
    'apps\filemgr\devices.json',
    'apps\filemgr\tokens.json',
    'apps\filemgr\secret.key',
    'apps\filemgr\bootstrap-admin.txt',
    'miniapp\project.private.config.json',
    'apps\project.private.config.json'
)

$removeExtensions = @('.log', '.tmp', '.key', '.pem', '.crt', '.token')

New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null

if (Test-Path $stagingDir) {
    Remove-Item -Recurse -Force -LiteralPath $stagingDir
}

if (Test-Path $zipPath) {
    Remove-Item -Force -LiteralPath $zipPath
}

New-Item -ItemType Directory -Force -Path $stagingDir | Out-Null

foreach ($item in $includeItems) {
    $source = Join-Path $projectRoot $item
    if (Test-Path $source) {
        $sourceItem = Get-Item -Force -LiteralPath $source
        if ($sourceItem.PSIsContainer) {
            $destination = Join-Path $stagingDir $sourceItem.Name
            $robocopyArgs = @(
                $source,
                $destination,
                '/E',
                '/R:1',
                '/W:1',
                '/NFL',
                '/NDL',
                '/NJH',
                '/NJS',
                '/NP',
                '/XD',
                'node_modules',
                '__pycache__',
                '.venv',
                'venv',
                '.git',
                'release',
                '/XF',
                '*.log',
                '*.tmp',
                '*.key',
                '*.pem',
                '*.crt',
                '*.token',
                'users.json',
                'devices.json',
                'tokens.json',
                'bootstrap-admin.txt',
                'project.private.config.json'
            )
            & robocopy @robocopyArgs | Out-Null
            if ($LASTEXITCODE -ge 8) {
                throw "robocopy failed for $source with exit code $LASTEXITCODE"
            }
        }
        else {
            Copy-Item -Force -LiteralPath $source -Destination $stagingDir
        }
    }
}

Get-ChildItem -LiteralPath $projectRoot -File -Filter '*.md' |
    ForEach-Object {
        Copy-Item -Force -LiteralPath $_.FullName -Destination $stagingDir
    }

foreach ($name in $removePatterns) {
    Get-ChildItem -LiteralPath $stagingDir -Recurse -Force -Directory |
        Where-Object { $_.Name -eq $name } |
        ForEach-Object { Remove-Item -Recurse -Force -LiteralPath $_.FullName }
}

foreach ($relativePath in $removeFiles) {
    $target = Join-Path $stagingDir $relativePath
    if (Test-Path $target) {
        Remove-Item -Force -LiteralPath $target
    }
}

Get-ChildItem -LiteralPath $stagingDir -Recurse -Force -File |
    Where-Object { $removeExtensions -contains $_.Extension } |
    ForEach-Object { Remove-Item -Force -LiteralPath $_.FullName }

Compress-Archive -Path (Join-Path $stagingDir '*') -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Package ready:"
Write-Host "Staging: $stagingDir"
Write-Host "Zip:     $zipPath"
