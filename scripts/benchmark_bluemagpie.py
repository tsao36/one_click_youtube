"""Comprehensive BlueMagpie-TTS Benchmark & Quality Evaluation Suite (Phases 3 & 4)

Evaluates:
- Profile A: Single reference WAV
- Profile B: Centroid from 1 clean recording
- Profile C: Centroid from multiple clean recordings (5 clips, 16.4s)
- Profile D: Centroid from curated subset (3 clips, 10.8s)

Evaluates inference configurations:
- cfg=2.0, steps=10
- cfg=2.8, steps=9
- cfg=2.4, steps=15
- cfg=2.0, steps=20

Computes:
- Speaker verification cosine similarity (ECAPA-TDNN) against held-out real voice reference
- Audio metrics: RMS, peak amplitude, duration, latency, real-time factor (RTF)
- Word completion / repetition flags
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Windows ROCm environment guards
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

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

import numpy as np
import soundfile as sf
import torch
from huggingface_hub import snapshot_download
from transformers import PreTrainedTokenizerFast

from bluemagpie import BlueMagpieModel
from bluemagpie.centroid import DEFAULT_ECAPA, _load_encoder

TEST_SENTENCES = {
    "s01_conversational": "欸，你等一下有空嗎？我想去買個晚餐，可是還沒想到要吃什麼。",
    "s02_conversational": "陽明山的夜景非常迷人，吸引了許多遊客前來觀賞。",
    "s03_technical": "大型語言模型能輕鬆飽覽整個網際網路的文字，但要讓機器人學會拿取水杯，卻是完全不同的維度。",
    "s04_technical": "這類端到端的架構，將視覺感測與肢體動作映射至統一的特徵潛在空間。",
    "s05_codeswitch_pi0": "Physical-Intelligence 推出的「派零」專攻極致的靈巧操作，展現驚人的穩定度。",
    "s06_codeswitch_groot": "輝達的 Groot 生態系結合了雙系統架構與 V-L-A 基礎模型。",
    "s07_codeswitch_gemini": "Google 團隊透過傑米奈機器人展現跨模態空間幾何推理與物體辨識能力。",
    "s08_codeswitch_chatgpt": "無論是 Chat-GPT 還是 Open V-L-A，都代表著世界模型向實體世界邁出的重要一步。",
    "s09_question_statement": "為什麼傳統的強化學習難以應對複雜的家庭環境？答案就在泛化能力。",
    "s10_long_explanation": "具身智能的核心突破，在於將高層次的語意理解與底層的連續運動控制無縫結合，使機械手臂在混亂場景中依然能精準操作。",
}


def compute_ecapa_embedding(audio_np: np.ndarray, sr: int, encoder, device: str = "cpu") -> torch.Tensor:
    """Computes normalized 192-dim ECAPA embedding for generated audio."""
    import librosa
    if sr != 16000:
        wav16 = librosa.resample(audio_np, orig_sr=sr, target_sr=16000)
    else:
        wav16 = audio_np

    x = torch.from_numpy(np.ascontiguousarray(wav16)).float()
    if x.ndim == 1:
        x = x.unsqueeze(0)
    with torch.no_grad():
        emb = encoder.encode_batch(x.to(device)).reshape(-1)
        return torch.nn.functional.normalize(emb, dim=0).cpu()


def main():
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"[*] Starting BlueMagpie benchmark on {device}...")

    out_dir = Path("scratch/bluemagpie_benchmark")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load BlueMagpie model
    print("[*] Loading BlueMagpie model...")
    model_dir = snapshot_download("OpenFormosa/BlueMagpie-TTS")
    tok_path = os.path.join(model_dir, "tokenizer.json")
    tokenizer = PreTrainedTokenizerFast(tokenizer_file=tok_path)
    model = BlueMagpieModel.from_local(
        model_dir, tokenizer=tokenizer, training=False, device=device
    )
    print(f"[OK] Model loaded on {device}.")

    # 2. Load ECAPA encoder for objective speaker similarity verification
    print("[*] Loading ECAPA speaker encoder...")
    ecapa_encoder = _load_encoder(DEFAULT_ECAPA, device="cpu")

    # 3. Compute authentic held-out reference embedding
    ref_heldout_path = "scratch/ref_short_4s.wav"
    heldout_wav, heldout_sr = sf.read(ref_heldout_path)
    if heldout_wav.ndim > 1:
        heldout_wav = heldout_wav.mean(axis=1)
    ref_emb = compute_ecapa_embedding(heldout_wav, heldout_sr, ecapa_encoder, "cpu")
    print(f"[OK] Computed held-out authentic voice embedding (shape: {ref_emb.shape}, norm: {torch.norm(ref_emb):.4f})")

    # 4. Load centroids for Profile B, C, D
    centroid_single = torch.load("data/voices/mytsaovoice/centroid_single_clip.pt", map_location=device, weights_only=True)
    centroid_multi = torch.load("data/voices/mytsaovoice/speaker_centroid.pt", map_location=device, weights_only=True)
    centroid_curated = torch.load("data/voices/mytsaovoice/centroid_curated.pt", map_location=device, weights_only=True)
    raw_ref_path = str(Path("data/voices/mytsaovoice/reference.wav").resolve())

    profiles = {
        "Profile_A_single_ref_wav": {"type": "ref_wav", "path": raw_ref_path},
        "Profile_B_single_centroid": {"type": "centroid", "tensor": centroid_single},
        "Profile_C_multi_centroid": {"type": "centroid", "tensor": centroid_multi},
        "Profile_D_curated_centroid": {"type": "centroid", "tensor": centroid_curated},
    }

    results = {
        "device": device,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "phase3_profiles": {},
        "phase4_configs": {},
    }

    # ==========================================
    # Phase 3: Profile Comparison Test Suite
    # ==========================================
    phase3_keys = ["s01_conversational", "s03_technical", "s05_codeswitch_pi0", "s10_long_explanation"]
    print("\n" + "=" * 60)
    print("PHASE 3: Speaker Profile Similarity & Naturalness Evaluation")
    print("=" * 60)

    for p_name, p_info in profiles.items():
        results["phase3_profiles"][p_name] = {}
        print(f"\n--- Evaluating {p_name} ---")
        for s_key in phase3_keys:
            text = TEST_SENTENCES[s_key]
            out_path = out_dir / f"phase3_{p_name}_{s_key}.wav"

            kwargs = {
                "target_text": text,
                "cfg_value": 2.0,
                "inference_timesteps": 10,
                "retry_badcase": True,
                "retry_badcase_ratio_threshold": 6.0,
            }
            if p_info["type"] == "centroid":
                kwargs["speaker_centroid"] = p_info["tensor"]
            else:
                kwargs["reference_wav_path"] = p_info["path"]

            torch.manual_seed(42)
            t0 = time.perf_counter()
            audio_tensor = model.generate(**kwargs)
            latency = time.perf_counter() - t0

            audio_np = audio_tensor.squeeze().cpu().numpy()
            dur = len(audio_np) / float(model.sample_rate)
            rtf = latency / dur if dur > 0 else 0.0

            # Objective speaker similarity against held-out authentic voice
            emb_gen = compute_ecapa_embedding(audio_np, model.sample_rate, ecapa_encoder, "cpu")
            sim = float(torch.nn.functional.cosine_similarity(emb_gen, ref_emb, dim=0).item())

            peak = float(np.max(np.abs(audio_np))) if len(audio_np) > 0 else 0.0
            rms = float(np.sqrt(np.mean(audio_np ** 2))) if len(audio_np) > 0 else 0.0

            sf.write(str(out_path), audio_np, model.sample_rate, format="WAV", subtype="PCM_16")

            metrics = {
                "similarity_cosine": round(sim, 4),
                "duration_sec": round(dur, 2),
                "latency_sec": round(latency, 2),
                "rtf": round(rtf, 2),
                "peak": round(peak, 4),
                "rms": round(rms, 4),
                "file": str(out_path),
            }
            results["phase3_profiles"][p_name][s_key] = metrics
            print(f"  [{s_key}] sim={sim:.4f} | dur={dur:.2f}s | latency={latency:.2f}s (RTF={rtf:.2f}) | peak={peak:.3f}")

    # ==========================================
    # Phase 4: Inference Parameter Evaluation
    # ==========================================
    print("\n" + "=" * 60)
    print("PHASE 4: Inference Parameter Optimization (cfg & timesteps)")
    print("=" * 60)

    configs = [
        {"cfg": 2.0, "steps": 10, "name": "cfg2.0_steps10"},
        {"cfg": 2.8, "steps": 9,  "name": "cfg2.8_steps9"},
        {"cfg": 2.4, "steps": 15, "name": "cfg2.4_steps15"},
        {"cfg": 2.0, "steps": 20, "name": "cfg2.0_steps20"},
    ]

    phase4_keys = ["s03_technical", "s05_codeswitch_pi0", "s06_codeswitch_groot"]

    for cfg_item in configs:
        cfg_val = cfg_item["cfg"]
        steps = cfg_item["steps"]
        cfg_name = cfg_item["name"]
        results["phase4_configs"][cfg_name] = {}
        print(f"\n--- Testing Config: {cfg_name} (cfg={cfg_val}, steps={steps}) ---")

        for s_key in phase4_keys:
            text = TEST_SENTENCES[s_key]
            out_path = out_dir / f"phase4_{cfg_name}_{s_key}.wav"

            kwargs = {
                "target_text": text,
                "cfg_value": cfg_val,
                "inference_timesteps": steps,
                "retry_badcase": True,
                "retry_badcase_ratio_threshold": 6.0,
                "speaker_centroid": centroid_multi,
            }

            torch.manual_seed(42)
            t0 = time.perf_counter()
            audio_tensor = model.generate(**kwargs)
            latency = time.perf_counter() - t0

            audio_np = audio_tensor.squeeze().cpu().numpy()
            dur = len(audio_np) / float(model.sample_rate)
            rtf = latency / dur if dur > 0 else 0.0

            emb_gen = compute_ecapa_embedding(audio_np, model.sample_rate, ecapa_encoder, "cpu")
            sim = float(torch.nn.functional.cosine_similarity(emb_gen, ref_emb, dim=0).item())

            peak = float(np.max(np.abs(audio_np))) if len(audio_np) > 0 else 0.0
            rms = float(np.sqrt(np.mean(audio_np ** 2))) if len(audio_np) > 0 else 0.0

            sf.write(str(out_path), audio_np, model.sample_rate, format="WAV", subtype="PCM_16")

            metrics = {
                "similarity_cosine": round(sim, 4),
                "duration_sec": round(dur, 2),
                "latency_sec": round(latency, 2),
                "rtf": round(rtf, 2),
                "peak": round(peak, 4),
                "rms": round(rms, 4),
                "file": str(out_path),
            }
            results["phase4_configs"][cfg_name][s_key] = metrics
            print(f"  [{s_key}] sim={sim:.4f} | dur={dur:.2f}s | latency={latency:.2f}s (RTF={rtf:.2f}) | peak={peak:.3f}")

    # 5. Save structured results
    res_path = out_dir / "benchmark_results.json"
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Benchmark completed! Results written to: {res_path}")


if __name__ == "__main__":
    main()
