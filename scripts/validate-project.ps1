param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$failed = $false

function Invoke-Check {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host "==> $Name"
    try {
        $global:LASTEXITCODE = 0
        & $Action
        if ($LASTEXITCODE -ne 0) {
            throw "exit code $LASTEXITCODE"
        }
    }
    catch {
        $script:failed = $true
        Write-Error "$Name failed: $($_.Exception.Message)" -ErrorAction Continue
    }
}

Push-Location $projectRoot
try {
    Invoke-Check 'JSON syntax' {
        Get-ChildItem -Recurse -File -Filter '*.json' |
            Where-Object {
                $_.FullName -notmatch '\\release\\' -and
                $_.FullName -notmatch '\\node_modules\\'
            } |
            ForEach-Object {
                Get-Content -Raw -Encoding UTF8 -LiteralPath $_.FullName |
                    ConvertFrom-Json | Out-Null
            }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notmatch '\\WindowsApps\\') {
        Invoke-Check 'Python syntax' {
            & $pythonCommand.Source -m py_compile apps/filemgr/app.py qt/kiosk_qt.py
        }
    }
    else {
        Write-Warning 'A working Python executable is unavailable; Python syntax check skipped.'
    }

    if (Get-Command node -ErrorAction SilentlyContinue) {
        Invoke-Check 'Matter JavaScript syntax' {
            node --check apps/matter-workstation/src/index.mjs
        }
    }
    else {
        Write-Warning 'Node.js is unavailable; Matter syntax check skipped.'
    }

    Invoke-Check 'Forbidden tracked runtime files' {
        $forbidden = @(
            'apps/filemgr/users.json',
            'apps/filemgr/devices.json',
            'apps/filemgr/tokens.json',
            'apps/filemgr/secret.key',
            'apps/filemgr/bootstrap-admin.txt',
            'miniapp/project.private.config.json',
            'apps/project.private.config.json'
        )
        $tracked = @(git ls-files)
        $matches = @($forbidden | Where-Object { $tracked -contains $_ })
        if ($matches.Count -gt 0) {
            throw "tracked private files: $($matches -join ', ')"
        }
    }

    Invoke-Check 'Portable Markdown links' {
        $matches = @(Get-ChildItem -Recurse -File -Filter '*.md' |
            Where-Object { $_.FullName -notmatch '\\release\\' } |
            Select-String -Pattern '\]\([A-Za-z]:[/\\]')
        if ($matches.Count -gt 0) {
            throw "absolute local Markdown links found: $($matches.Count)"
        }
    }

    Invoke-Check 'Git whitespace' {
        git diff --check
    }
}
finally {
    Pop-Location
}

if ($failed) {
    exit 1
}

Write-Host 'All project checks passed.'
