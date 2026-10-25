# Start the app on Windows, then open http://localhost:8000
#   powershell -ExecutionPolicy Bypass -File .\start.ps1
# The first start downloads the embedding and re-ranking models (~200 MB).
Push-Location backend
try {
    ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
} finally {
    Pop-Location
}
