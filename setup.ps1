# One-time setup on Windows (PowerShell). Run from the project folder:
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
# Safe to run again: existing steps are skipped or quickly re-checked.
$ErrorActionPreference = "Stop"

function Fail($msg) { Write-Host "`n$msg" -ForegroundColor Red; exit 1 }

# ---- Python ------------------------------------------------------------------
if (-not (Test-Path .venv\Scripts\python.exe)) {
    Write-Host "Creating Python virtual environment in .venv ..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the virtual environment. Is Python 3.10-3.13 installed and on PATH?" }
}
Write-Host "Installing Python packages (the first time this downloads torch, about 200 MB) ..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
if ($LASTEXITCODE -ne 0) { Fail "pip install failed. Scroll up for the first error." }

if (-not (Test-Path backend\.env)) {
    Copy-Item .env.example backend\.env
    Write-Host "Created backend\.env - open it and set GOOGLE_API_KEY."
}

# ---- Web UI ------------------------------------------------------------------
# Node.js is only needed to (re)build the UI. Without it, the prebuilt UI in
# frontend\out is used as-is.
$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($npm) {
    Write-Host "Installing and building the web UI ..."
    Push-Location frontend
    try {
        npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { Fail "npm install failed." }
        npm run build
        if ($LASTEXITCODE -ne 0) { Fail "The UI build failed." }
    } finally {
        Pop-Location
    }
} elseif (Test-Path frontend\out\index.html) {
    Write-Host "Node.js not found: using the prebuilt UI in frontend\out." -ForegroundColor Yellow
    Write-Host "(Install Node.js LTS only if you want to change the UI: winget install OpenJS.NodeJS.LTS)"
} else {
    Fail ("Node.js is needed to build the UI and frontend\out is missing.`n" +
          "Install it with:  winget install OpenJS.NodeJS.LTS   then open a new terminal and run setup again.")
}

Write-Host "`nDone. Start the app with:  powershell -ExecutionPolicy Bypass -File .\start.ps1" -ForegroundColor Green
