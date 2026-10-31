# 0004. BlueMagpie-TTS Zero-Shot Synthesis Hardening

## Status
Accepted

## Context
BlueMagpie-TTS provides high-fidelity local Taiwan Mandarin and code-switching zero-shot voice cloning on AMD ROCm GPUs. However, autoregressive diffusion-based speech synthesis exhibits specific vulnerabilities during extended video narrations:
1. **Clause Runaway & Repetition Loops**: On long text clauses (>30 characters), autoregressive attention span degrades, resulting in garbled audio and infinite loop repeats that push speech out of sync with subtitles.
2. **Timbre Drift Across Scenes**: Feeding individual raw reference audio clips (`reference_wav`) injects acoustic variance and noise prefixes into the model prompt, causing the voice to shift pitch and perceived age between scenes.
3. **Tokenizer Byte Fragmentation on Tech Acronyms**: Specialized technical terms (e.g. Unicode subscript `π₀`, number-leetspeak `GR00T`, and fused acronyms like `OpenVLA` or `ChatGPT`) fracture into unknown byte tokens (`<unk>`), causing bizarre pronunciations (e.g. `π₀` vocalized as "派你").

## Decision
We harden BlueMagpie-TTS speech synthesis across four architectural mechanisms:

1. **Speaker Centroid Vector Conditioning**:
   - We extract a normalized 192-dimensional ECAPA speaker embedding (`speaker_centroid.pt`) via `scripts/extract_speaker_centroid.py`.
   - Conditioning exclusively on this fixed centroid tensor bypasses the single-WAV prefix tokens, locking the vocal timbre identically across every scene.

2. **Clause-Level Chunking without Context Bleed**:
   - Narrations are split into respiratory clauses of `max_chunk_chars <= 24` using major (`[。\n！？!?；;：:—]`) and minor (`[，,、]`) punctuation delimiters.
   - We eliminate inter-chunk prompt audio continuation (`continuation_context_sec: 0.0`), synthesizing each clause independently to eliminate chunk boundary loop repeats, and join them with natural punctuation pauses (150ms comma, 250ms period) and 15ms raised-cosine crossfades.

3. **Autoregressive Badcase Detection & Rejection**:
   - We lower `cfg_value` to `2.2` (down from 2.8) and maintain `inference_timesteps: 18` for smooth, natural Mandarin prosody.
   - We activate native `retry_badcase=True` with `retry_badcase_ratio_threshold=5.0`. If any chunk exceeds 5x the expected token duration due to a runaway loop, the model automatically rejects the sample and regenerates with a new seed.

4. **Phonetic Normalization for Tech Names**:
   - Unicode subscripts and superscripts (`₀`-`₉`) are mapped to standard digits.
   - Known technical terms and acronyms are normalized before tokenization:
     - `π₀` / `π0` / `pi0` $\rightarrow$ `「派零」`
     - `GR00T` $\rightarrow$ `Groot`
     - `Gemini` $\rightarrow$ `傑米奈`
     - `OpenVLA` $\rightarrow$ `Open V-L-A`
     - `ChatGPT` $\rightarrow$ `Chat-GPT`
   - Peak loudness is normalized to -1 dB (`0.891`) across all stitched clips to ensure seamless loudness matching.

## Consequences
- **Benefits**:
  - Eliminates garbled audio and repeat loops; Scene 22 audio drops from 18.8s to 10.4s without any subtitle drift.
  - Consistent speaker timbre from opening scene to credits.
  - Clear, accurate pronunciation of AI and robotics technical terminology.
- **Trade-offs**:
  - Requires pre-extracting `speaker_centroid.pt` once per voice profile.
