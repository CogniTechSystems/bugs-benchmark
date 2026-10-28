<#
.SYNOPSIS
    Start the application. Configuration is read from BHB_* environment variables or .env.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Venv = if ($env:BHB_VENV) { $env:BHB_VENV } else { Join-Path $Root "backend\.venv" }
$Executable = Join-Path $Venv "Scripts\bug-hunt-benchmark.exe"

if (-not (Test-Path $Executable)) {
    throw "The backend is not installed. Run scripts\setup.ps1 first."
}
& $Executable @args
exit $LASTEXITCODE
