# Setup script for BlueMagpie-TTS voice cloning environment
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Setting up BlueMagpie-TTS Voice Cloning Environment" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$envDir = ".venv_bluemagpie"

if (-not (Test-Path $envDir)) {
    Write-Host "[+] Creating dedicated Python 3.11 environment for BlueMagpie ($envDir)..." -ForegroundColor Green
    py -3.11 -m venv $envDir
}

Write-Host "[+] Installing AMD ROCm PyTorch (gfx120X / Radeon RX 9000 series)..." -ForegroundColor Green
& "$envDir\Scripts\python.exe" -m pip install --upgrade pip
& "$envDir\Scripts\python.exe" -m pip install --index-url https://rocm.nightlies.amd.com/v2/gfx120X-all/ --pre torch torchaudio

Write-Host "[+] Installing Transformers, SoundFile, FastAPI..." -ForegroundColor Green
& "$envDir\Scripts\python.exe" -m pip install "transformers>=4.44" "soundfile" "fastapi" "uvicorn" "pydantic" "python-multipart" "huggingface_hub" "safetensors" "librosa" "einops"

Write-Host "[+] Installing Barbet and BlueMagpie-TTS from GitHub..." -ForegroundColor Green
& "$envDir\Scripts\python.exe" -m pip install "git+https://github.com/OpenFormosa/Barbet.git"
& "$envDir\Scripts\python.exe" -m pip install "git+https://github.com/OpenFormosa/BlueMagpie-TTS.git"

Write-Host "`n[✓] BlueMagpie-TTS setup complete!" -ForegroundColor Green
Write-Host "You can start the BlueMagpie server using: .\run_bluemagpie.ps1" -ForegroundColor Cyan
