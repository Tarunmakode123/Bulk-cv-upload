#!/usr/bin/env pwsh
<#
Simple helper to run the Flask dev server using the project's virtual environment python.
Place this next to the project root and run `./run.ps1` from PowerShell.
#>
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$venvPython = Join-Path $scriptDir '.venv\Scripts\python.exe'

if (Test-Path $venvPython) {
    Write-Host "Using venv python: $venvPython"
    & $venvPython (Join-Path $scriptDir 'Resume_Analyser_Using_Python\main.py')
} else {
    Write-Host "Virtual environment python not found at $venvPython"
    Write-Host "Falling back to system 'python' - make sure the correct Python is on PATH"
    & python (Join-Path $scriptDir 'Resume_Analyser_Using_Python\main.py')
}
