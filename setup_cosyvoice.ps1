# Sets up a local CosyVoice 2 (0.5B) TTS server on an AMD Radeon RX 9000 (gfx120X) GPU via ROCm.
# Isolated venv (.venv_cosyvoice): CosyVoice pins older libs (transformers 4.51, numpy 1.26)
# that would conflict with the BlueMagpie environment.
$ErrorActionPreference = "Continue"
$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$envDir = Join-Path $root ".venv_cosyvoice"
$repo   = Join-Path $root "tools\CosyVoice"
$py     = Join-Path $envDir "Scripts\python.exe"

function Step($m) { Write-Host "`n[+] $m" -ForegroundColor Green }

if (-not (Test-Path (Join-Path $repo "cosyvoice"))) {
    Step "Cloning CosyVoice (with Matcha-TTS submodule)..."
    git clone --recursive --depth 1 https://github.com/FunAudioLLM/CosyVoice.git $repo
}

if (-not (Test-Path $py)) {
    Step "Creating Python 3.11 venv at $envDir ..."
    py -3.11 -m venv $envDir
}
& $py -m pip install --upgrade pip wheel setuptools

Step "Installing AMD ROCm PyTorch (gfx120X / Radeon RX 9000 series)..."
& $py -m pip install --index-url https://rocm.nightlies.amd.com/v2/gfx120X-all/ --pre torch torchaudio

# Pin the ROCm torch so no CosyVoice dependency can swap it for a CUDA/CPU build.
$tv  = & $py -c "import torch; print(torch.__version__)"
$tav = & $py -c "import torchaudio; print(torchaudio.__version__)"
$constraints = Join-Path $envDir "constraints.txt"
"torch==$tv`ntorchaudio==$tav`nnumpy==1.26.4" | Set-Content -Encoding ascii $constraints
Write-Host "    pinned torch==$tv torchaudio==$tav numpy==1.26.4"

Step "Installing openai-whisper (source build; needs setuptools<70 for pkg_resources)..."
& $py -m pip install -c $constraints "setuptools<70" wheel "numpy==1.26.4" tiktoken more-itertools numba tqdm
& $py -m pip install -c $constraints --no-build-isolation "openai-whisper==20231117"

Step "Installing CosyVoice inference dependencies..."
# From tools/CosyVoice/requirements.txt minus CUDA/Linux-only, training and UI packages.
$core = @(
  "conformer==0.3.2", "diffusers==0.29.0", "gdown==5.1.0", "hydra-core==1.3.2", "HyperPyYAML==1.2.3",
  "inflect==7.3.1", "librosa==0.10.2", "lightning==2.2.4", "matplotlib==3.7.5",
  "modelscope==1.20.0", "networkx==3.1", "omegaconf==2.3.0",
  "onnx==1.16.0", "onnxruntime==1.18.0", "protobuf==4.25",
  "pyarrow==18.1.0", "pydantic>=2.7,<3", "pyworld==0.3.4", "rich==13.7.1", "soundfile==0.12.1",
  "transformers==4.51.3", "x-transformers==2.11.24", "wetext==0.0.4", "wget==3.2",
  "fastapi", "uvicorn", "python-multipart", "huggingface_hub"
)
& $py -m pip install -c $constraints @core

$tvAfter = & $py -c "import torch; print(torch.__version__)"
if ($tvAfter -ne $tv) {
    Write-Host "[!] torch was replaced ($tvAfter); restoring ROCm build..." -ForegroundColor Yellow
    & $py -m pip install --force-reinstall --no-deps --index-url https://rocm.nightlies.amd.com/v2/gfx120X-all/ --pre torch torchaudio
}

Step "Downloading CosyVoice2-0.5B model (several GB, one time)..."
$modelDir = Join-Path $repo "pretrained_models\CosyVoice2-0.5B"
& $py -c "from huggingface_hub import snapshot_download; snapshot_download('FunAudioLLM/CosyVoice2-0.5B', local_dir=r'$modelDir')"

Step "Verifying install..."
$check = @"
import sys, os
sys.path.insert(0, r'$repo'); sys.path.insert(0, r'$repo\third_party\Matcha-TTS'); sys.path.insert(0, r'$root\tools')
import cosyvoice_compat; print('compat:', cosyvoice_compat.apply())
import torch, numpy, whisper, onnxruntime, transformers, wetext
from cosyvoice.cli.cosyvoice import AutoModel
need = ['cosyvoice2.yaml', 'llm.pt', 'flow.pt', 'hift.pt', 'campplus.onnx', 'speech_tokenizer_v2.onnx']
missing = [f for f in need if not os.path.exists(os.path.join(r'$modelDir', f))]
print('torch', torch.__version__, '| numpy', numpy.__version__, '| transformers', transformers.__version__)
print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NOT AVAILABLE (CPU fallback)')
print('model files missing:', missing or 'none')
sys.exit(1 if missing else 0)
"@
& $py -c $check
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[FAIL] CosyVoice 2 setup incomplete - see messages above." -ForegroundColor Red
    exit 1
}
Write-Host "`n[OK] CosyVoice 2 setup finished. The app starts tools/cosyvoice_server.py automatically on port 50000." -ForegroundColor Cyan
