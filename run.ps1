# Launch script for Windows 11
$Host.UI.RawUI.WindowTitle = "AI Video Creator"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[!] Virtual environment not found. Please run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Run the app
.\.venv\Scripts\python.exe app.py $args
