<#
.SYNOPSIS
    Run backend tests (pytest) locally with one command.

.DESCRIPTION
    Locates the uv virtual environment and runs pytest. If the environment does
    not exist yet, `uv sync` is executed first.

    uv is preferred; if uv is not installed, the script falls back to the
    virtual environment's python. Both paths produce identical results.

    NOTE: This file is intentionally ASCII-only. Windows PowerShell 5.1 reads
    .ps1 files using the system ANSI code page (GBK on Chinese Windows) unless a
    UTF-8 BOM is present, so non-ASCII text here would be garbled and could even
    break string terminators. Usage documentation in Chinese lives in README.md.

.PARAMETER Scope
    What to run:
      all         everything (default, 376 tests)
      unit        domain-layer unit tests only (no database, no web framework)
      integration API end-to-end tests only
      layering    architecture/ layering guard checks only

.PARAMETER Keyword
    Filter tests by name (passed through as pytest -k).
    Example: -Keyword renew

.PARAMETER NoUv
    Force running via the virtual environment's python instead of uv.

.EXAMPLE
    .\run-tests.ps1

.EXAMPLE
    .\run-tests.ps1 -Scope layering

.EXAMPLE
    .\run-tests.ps1 -Scope unit -Keyword money
#>
[CmdletBinding()]
param(
    [ValidateSet('all', 'unit', 'integration', 'layering')]
    [string]$Scope = 'all',

    [string]$Keyword = '',

    [switch]$NoUv
)

$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$venvPython = Join-Path $backend '.venv\Scripts\python.exe'

# --- 1. make sure the environment exists -----------------------------------
if (-not (Test-Path $venvPython)) {
    Write-Host '[setup] virtual environment not found, creating it with uv ...' -ForegroundColor Yellow

    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host '[error] uv is not installed, cannot create the environment.' -ForegroundColor Red
        Write-Host '        install: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"'
        exit 1
    }

    Push-Location $backend
    try { uv sync } finally { Pop-Location }
}

# --- 2. build the pytest arguments ----------------------------------------
$target = 'backend/tests'
switch ($Scope) {
    'unit'        { $target = 'backend/tests/unit' }
    'integration' { $target = 'backend/tests/integration' }
    'layering'    { $target = 'backend/tests/integration/test_layering.py' }
}

$pytestArgs = @($target, '-q')
if ($Keyword) { $pytestArgs += @('-k', $Keyword) }

# --- 3. run ----------------------------------------------------------------
$useUv = (-not $NoUv) -and (Get-Command uv -ErrorAction SilentlyContinue)

Push-Location $root
try {
    if ($useUv) {
        Write-Host ('> uv run --project backend pytest ' + ($pytestArgs -join ' ')) -ForegroundColor DarkGray
        & uv run --project backend pytest @pytestArgs
    }
    else {
        Write-Host ('> ' + $venvPython + ' -m pytest ' + ($pytestArgs -join ' ')) -ForegroundColor DarkGray
        & $venvPython -m pytest @pytestArgs
    }
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
}

# --- 4. summarize ----------------------------------------------------------
if ($code -eq 0) {
    Write-Host ''
    Write-Host '[OK] all selected tests passed' -ForegroundColor Green
}
else {
    Write-Host ''
    Write-Host ('[FAIL] tests failed (exit code ' + $code + ')') -ForegroundColor Red
}
exit $code
