# Minimal bootstrap for Windows (save as bootstrap.ps1 in repo root)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

Write-Host "Bootstrapping repository in $root" -ForegroundColor Cyan

# 1) Check python
try {
    $py = & python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
    if (-not $py) { throw "python not found" }
    $parts = $py.Split('.') | ForEach-Object { [int]$_ }
    if ($parts[0] -lt 3 -or ($parts[0] -eq 3 -and $parts[1] -lt 8)) {
        throw "Python 3.8+ is required. Found: $py"
    }
}
catch {
    Write-Error "Python 3.8+ is required and 'python' must be on PATH. $_"
    exit 1
}

# 2) Create venv
$venvPath = Join-Path $root ".venv"
if (-Not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at $venvPath"
    python -m venv $venvPath
}
else {
    Write-Host "Virtual environment already exists at $venvPath"
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"

if (-Not (Test-Path $venvPython)) {
    Write-Error "Expected venv python not found at $venvPython"
    exit 1
}

# 3) Upgrade pip
Write-Host "Upgrading pip..."
& $venvPython -m pip install --upgrade pip

# 4) Install dependencies
$reqFile = Join-Path $root "requirements.txt"
if (Test-Path $reqFile -and (Get-Content $reqFile -ErrorAction SilentlyContinue | Where-Object { $_.Trim() -ne "" } | Measure-Object).Count -gt 0) {
    Write-Host "Installing packages from requirements.txt..."
    & $venvPython -m pip install -r $reqFile
}
else {
    Write-Host "No pinned requirements found; installing 'playwright'..."
    & $venvPython -m pip install playwright
}

# 5) Install Playwright browsers (Chromium used by the app)
Write-Host "Installing Playwright Chromium runtime..."
& $venvPython -m playwright install chromium

Write-Host ""
Write-Host "Bootstrap completed." -ForegroundColor Green
Write-Host "To run the app:"
Write-Host "  1) (Optional) Activate the venv: .\.venv\Scripts\Activate.ps1"
Write-Host "  2) Run: python main.py"
Write-Host ""
Write-Host "Or run directly without activating:" 
Write-Host "  .\.venv\Scripts\python.exe main.py"
