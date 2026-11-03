# 10. Documentary Ambient Music Stage and Multi-Movement Progression

## Status
Accepted

## Context
In documentary video generation, narrative pacing requires dynamic acoustic atmosphere transitions across distinct narrative movements (Movement 1: Opening Context/Atmosphere, Movement 2: Deep Dive/Investigation/Tension, Movement 3: Climax/Uplifting Resolution) rather than monotonous single-track looping.

Two critical defects and workflow gaps were identified:
1. **Audio Premature Cutoff Defect**: In `rendering/ffmpeg_renderer.py`, the multi-track background music filter used FFmpeg's `amix` filter with `duration=first`. Because Movement 1 only spans the initial ~35% of the documentary, `duration=first` caused the entire background music mix (`[mus_bed]`) to immediately terminate when the first track finished, silencing Movements 2 and 3 and making background music disappear for the remainder of the documentary.
2. **Invisible Black-Box Selection**: Background music was dynamically selected and mixed on-the-fly directly inside the monolithic `render` stage. Creators in Documentary Stage Studio had no dedicated inspection interface to view which tracks were matched to their topic, review the multi-movement transition timestamps, audition tracks in-browser, or override individual movement selections.

## Decisions

### 1. Dedicated Stage 7: Ambient Music in Documentary Pipeline
We expand the documentary pipeline to a 10-stage sequential topology:
`1. Research` ➔ `2. Script` ➔ `3. Scenes` ➔ `4. Prompts` ➔ `5. Images` ➔ `6. Voice TTS` ➔ `7. Ambient Music` ➔ `8. Animation` ➔ `9. Subtitles` ➔ `10. Render`

Placing Ambient Music immediately after Voice TTS guarantees that exact narration audio durations and chapter boundaries are known before planning musical movement crossfades. Short Drama mode (`STAGE_META_DRAMA`) remains on its dedicated 9-stage lip-sync structure.

### 2. Decoupled Persistence via `music/music_plan.json`
Stage 7 execution runs `plan_music_timeline()` and writes a structured snapshot to `music/music_plan.json` containing:
- Timeline segments with `track`, `start_time`, `end_time`, `crossfade_in`, `crossfade_out`, `volume_db`, `category`, and `name`.
- Metadata explaining the topic/narrative genre match.

The final `render` stage reads `music/music_plan.json` if present, ensuring complete determinism and honoring any creator-tuned overrides.

### 3. Interactive Auditioning & Debugging UI in Stage Studio
The Stage Studio Inspector for Ambient Music exposes:
- **Visual Movement Cards**: Movement 1 (Opening Context), Movement 2 (Deep Dive / Rising Tension), and Movement 3 (Uplifting Resolution) with exact time ranges and category rationale.
- **In-Browser Audio Auditioning**: Native HTML5 `<audio>` player for each movement to test audio synergy before full video rendering.
- **Track Selection & Re-Roll**: Per-movement dropdown to swap tracks from the local music catalog or re-roll candidates.
- **Ducking & Master BGM Controls**: Global volume and sidechain ducking sensitivity adjustments.

### 4. FFmpeg Audio Mix Duration Fix
In `rendering/ffmpeg_renderer.py`, `amix=inputs={len(bed_labels)}:duration=first:normalize=0[mus_bed]` is corrected to `duration=longest`. With track delay offsets accurately positioned via `adelay`, `duration=longest` ensures the music bed remains active throughout the entire duration of the production without premature termination.

## Consequences
- **Positive**: Eliminates silent audio cutoffs after Movement 1; gives creators full transparency into ambient music selection with instant in-browser playback; allows fine-tuning and overriding soundtracks prior to CPU/GPU-intensive rendering.
- **Trade-off**: The documentary pipeline gains one explicit stage step (totaling 10 stages); existing projects without `music/music_plan.json` will continue to gracefully fallback to runtime calculation during render until Stage 7 is executed.
