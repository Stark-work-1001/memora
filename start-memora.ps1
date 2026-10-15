param([int]$Port = 8765, [string]$Data = "")
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv (Join-Path $projectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create Python environment' }
    & $pythonPath -m pip install -e $projectRoot
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install dependencies' }
}
if (-not $Data) { $Data = Join-Path $projectRoot 'agent-data' }
Set-Location -LiteralPath $projectRoot
& $pythonPath -m memory_merge --data $Data agent --port $Port
