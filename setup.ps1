# Setup script for Windows 11
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Setting up Local-First AI YouTube Video Generator" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python
$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) {
    $py = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $py) {
    Write-Host "[!] Python 3.11 not found! Please install Python 3.11." -ForegroundColor Red
    exit 1
}

# 2. Setup Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "[+] Creating virtual environment (.venv)..." -ForegroundColor Green
    py -3.11 -m venv .venv
}

Write-Host "[+] Upgrading pip and installing dependencies..." -ForegroundColor Green
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Check / Download FFmpeg
if (-not (Test-Path "tools\ffmpeg\bin\ffmpeg.exe")) {
    Write-Host "[+] Downloading portable FFmpeg essentials..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force tools | Out-Null
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip -OutFile tools\ffmpeg.zip
    Expand-Archive tools\ffmpeg.zip -DestinationPath tools\ffmpeg_tmp -Force
    $d = Get-ChildItem tools\ffmpeg_tmp -Directory | Select-Object -First 1
    Move-Item "$($d.FullName)" tools\ffmpeg -Force
    Remove-Item tools\ffmpeg_tmp,tools\ffmpeg.zip -Recurse -Force
    Write-Host "[✓] FFmpeg installed in tools\ffmpeg" -ForegroundColor Green
} else {
    Write-Host "[✓] Portable FFmpeg already present." -ForegroundColor Green
}

# 4. Copy .env.example if .env does not exist
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[+] Created .env file from .env.example" -ForegroundColor Green
}

Write-Host "`nSetup complete! You can now start the application using: .\run.ps1" -ForegroundColor Cyan
