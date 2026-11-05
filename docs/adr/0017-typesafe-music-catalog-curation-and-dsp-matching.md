# 17. TypeSafe AI Music Inventory Curation, Semantic Matching, and Automated DSP Mastering Chain

## Status
Accepted

## Context
When background music (BGM) is paired with informational, educational, or documentary videos (e.g. *言究院*, *fOx Hsiao*, *小東老師電子學*), music frequently feels "odd," distracting, or fatigue-inducing. This defect stems from two interconnected failures:
1. **Semantic & Cognitive Mismatch**: Raw music libraries contain tracks with prominent lead vocals, vocal samples, virtuosic instrument solos, or jarring dynamic drops that compete directly with the viewer's cognitive bandwidth during high-density voiceovers.
2. **Acoustic & Frequency Collision**: Unprocessed music tracks clash with human speech frequencies (800 Hz - 3.5 kHz) and lack automatic sidechain ducking, causing background percussion and leads to poke above the narrator's voice.

Creators previously had to manually audition dozens of local audio files or rely on shallow keyword title matching, often selecting tracks whose musical energy clashed with the narration.

## Decisions

### 1. Two-Tier Acoustic Profiler for Track Ingestion
To feed TypeSafe AI's System One models with concrete acoustic grounding without heavy neural audio transcription dependencies, we implement a deterministic Python/FFprobe extractor. It computes an `AudioProfile` for every track in `data/music`:
- `duration_sec`: Exact audio length.
- `rms_db`: Root-mean-square loudness.
- `peak_db`: Peak signal amplitude.
- `dynamic_range_db`: Crest factor (difference between peak and RMS).
- `filename_tags`: Heuristic vocal markers (`lead_vocal`, `background_vocals`, `instrumental`).

### 2. Comprehensive TypeSafe AI Catalog Curation (Direct Holistic Evaluation)
Rather than applying destructive regex gates, all audio tracks in the local inventory are submitted to TypeSafe AI (Jev System One model) in structured state format. TypeSafe evaluates three typed judgments per track:
- `is_distracting` (`Noul`): Probability that the track's melodic hooks, vocal textures, or sonic density distract from informational narration.
- `voiceover_fitness` (`Score`, levels 1 to 5):
  - 1: Disruptive (Prominent lead vocals, erratic drums, clashing solos).
  - 2: Borderline (Acceptable for cinematic montage, but intrusive under voiceover).
  - 3: Neutral (Standard acoustic carpet; non-intrusive).
  - 4: Supportive (Gentle rhythmic pulse or clean minimalist synth; maintains focus).
  - 5: Ideal Underscore (Invisible harmony; spacious, soft transients, perfectly complements data/speech).
- `movement_role` (`Choice`): Optimal narrative placement (`intro_context`, `deep_dive_tension`, `climax_resolution`, `unfit_for_voiceover`).

A track is classified as `is_voiceover_ready = true` if `voiceover_fitness >= 3.0` and `distraction_prob <= 0.40`. Tracks scoring below this threshold are tagged `speech_intrusive: true` and excluded from voiceover movements. The resulting calibrated scores and probability vectors are persisted into `data/music/catalog.json` under `typesafe_score`, `is_voiceover_ready: bool`, and `distraction_prob`.

### 3. Dual Execution Interface for Catalog Grading
Inventory grading can be run via:
1. Standalone CLI: `python scripts/grade_music_catalog.py [--force] [--limit N]`.
2. REST Endpoint & UI: `POST /api/music/grade-inventory` triggered via an interactive button in Stage Studio, rendering progress and visual badges (`Safe for Voiceover` vs `Speech Intrusive`).

### 4. Narrative Semantic Re-Ranking in Stage 7 (Ambient Music)
During Stage 7 timeline planning, `generators/music.py` extracts the Stage 1 research synopsis, Stage 2 script chapter outline, and target movement duration. It retrieves pre-screened candidate tracks from `catalog.json` with `is_voiceover_ready = true` and queries TypeSafe AI to rank candidate tracks against the specific chapter's narrative tension.

### 5. Multi-Movement S-Curve Crossfading & Creator Override
- **3.5s Equal-Power Crossfade**: Track transitions between movements (e.g. Exposition -> Tension -> Resolution) use equal-power S-curve crossfading (`iqsin` / `qsin` curves over 3.5s) synchronized to chapter boundaries, preventing perceived volume dips.
- **Stage 7 Studio Auditioning & Override**: Stage Studio displays TypeSafe AI's top recommendations per movement with scores and rationale, while preserving in-browser HTML5 auditioning and manual dropdown overrides prior to final render.

### 6. Strict Fail-Fast on TypeSafe AI Availability
To prevent unvetted, musically dissonant fallback tracks from silently contaminating informational videos, Stage 7 strictly enforces TypeSafe AI availability. If `TYPESAFE_API_KEY` is missing or the TypeSafe API is unreachable, the pipeline raises an explicit configuration/availability error (`TypeSafeUnavailableError`) rather than falling back to unvetted random or keyword picking.

### 7. Automated Active DSP Mastering Chain in FFmpeg Render
To eliminate acoustic oddness mathematically during final rendering (`rendering/ffmpeg_renderer.py`):
1. **Dynamic Voice Carving EQ**: Apply a continuous bell notch (`-3.0 dB` cut at `1.8 kHz` with `Q=1.2`) on the master music bed (`[mus_bed]`) to prevent frequency masking in the speech clarity pocket.
2. **Real-Time DSP Sidechain Ducking**: Insert FFmpeg `sidechaincompress` filter with a 15ms attack and 350ms release keyed against the synthesized voice narration track (`[voice]`), attenuating music by `-13 dB` during active speech and allowing it to breathe during pauses.
3. **Loudness Normalization**: Master voice narration is normalized to `-16 LUFS`, while the background music bed is pegged to `-26 LUFS`, ensuring the low-volume "mute-to-whisper" test passes deterministically.

## Consequences
- **Positive**: Guarantees zero cognitive fatigue for viewers; provides a curated, permanently scored music library; ensures audio mixing is automated at broadcast standards without manual DAW work; prevents unvetted tracks from slipping into production.
- **Trade-off**: Requires an active `TYPESAFE_API_KEY` with available credits; video generation will intentionally fail-fast if TypeSafe API is unreachable; requires one-time batch token expenditure across the music library.

