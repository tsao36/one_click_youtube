import soundfile as sf
import torch
import numpy as np
import librosa
import os
from transformers import PreTrainedTokenizerFast
from huggingface_hub import snapshot_download

# Fix Windows ROCm missing ReduceOp
try:
    import torch.distributed as dist
    if not hasattr(dist, "ReduceOp"):
        class DummyReduceOp:
            SUM = 0
            AVG = 1
            PRODUCT = 2
            MIN = 3
            MAX = 4
            BAND = 5
            BOR = 6
            BXOR = 7
        dist.ReduceOp = DummyReduceOp
except Exception:
    pass

from bluemagpie import BlueMagpieModel
from bluemagpie.centroid import DEFAULT_ECAPA, _load_encoder

device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
model_dir = snapshot_download('OpenFormosa/BlueMagpie-TTS')
tokenizer = PreTrainedTokenizerFast(tokenizer_file=os.path.join(model_dir, 'tokenizer.json'))
model = BlueMagpieModel.from_local(model_dir, tokenizer=tokenizer, training=False, device=device)
ecapa = _load_encoder(DEFAULT_ECAPA, device='cpu')

heldout_wav, _ = librosa.load('scratch/ref_short_4s.wav', sr=16000)
ref_emb = ecapa.encode_batch(torch.from_numpy(heldout_wav).float().unsqueeze(0)).reshape(-1)
ref_emb = torch.nn.functional.normalize(ref_emb, dim=0)

centroid = torch.load('data/voices/mytsaovoice/speaker_centroid.pt', map_location=device, weights_only=True)
ref_path = 'data/voices/mytsaovoice/reference.wav'

text = '大型語言模型能輕鬆飽覽整個網際網路的文字，但要讓機器人學會拿取水杯，卻是完全不同的維度。'

# Test 1: Both Centroid AND reference_wav
torch.manual_seed(42)
audio = model.generate(
    target_text=text,
    reference_wav_path=ref_path,
    speaker_centroid=centroid,
    cfg_value=2.0,
    inference_timesteps=10,
    retry_badcase=True
).squeeze().cpu().numpy()
sf.write('scratch/bluemagpie_benchmark/phase8_hybrid_centroid_plus_ref.wav', audio, model.sample_rate)

w, _ = librosa.load('scratch/bluemagpie_benchmark/phase8_hybrid_centroid_plus_ref.wav', sr=16000)
e = ecapa.encode_batch(torch.from_numpy(w).float().unsqueeze(0)).reshape(-1)
e = torch.nn.functional.normalize(e, dim=0)
sim = torch.nn.functional.cosine_similarity(e, ref_emb, dim=0).item()
print('SIMILARITY (BOTH Centroid + Ref WAV):', sim)
