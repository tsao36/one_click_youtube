# Runner script for BlueMagpie-TTS local microservice
$envDir = ".venv_bluemagpie"
$py = "$envDir\Scripts\python.exe"

if (-not (Test-Path $py)) {
    # If dedicated env doesn't exist, check standard venv
    if (Test-Path ".venv\Scripts\python.exe") {
        $py = ".venv\Scripts\python.exe"
    } else {
        Write-Host "[!] Environment not found. Run .\setup_bluemagpie.ps1 first." -ForegroundColor Red
        exit 1
    }
}

Write-Host "[+] Launching BlueMagpie-TTS server on http://127.0.0.1:8008..." -ForegroundColor Green
& $py tools\bluemagpie_server.py --port 8008 --device cpu $args
