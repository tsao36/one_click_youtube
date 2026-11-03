# 16. OpenOpus Classical Music Integration and Public Domain Audio Fulfillment

## Status
Accepted

## Context
In documentary and drama video generation, classical orchestral, chamber, and solo instrumental compositions provide timeless emotional atmosphere, gravitas, and period authenticity (especially for history, philosophy, biography, and science narratives).

We sought to integrate the **OpenOpus API** (`https://api.openopus.org`), an open-source database of classical music. However:
1. **Metadata Only**: OpenOpus provides structured metadata (composers, epochs, genres, works, and performers) but hosts no audio files or MP3/WAV streams.
2. **Video Engine Requirements**: Our FFmpeg audio pipeline (`rendering/ffmpeg_renderer.py`) requires tangible audio files on local disk (`data/music/`) with determined sample rates, channels, and durations for multi-movement crossfading and sidechain ducking.
3. **Resilience & Connectivity**: Depending directly on an external community API from the browser introduces CORS constraints, network latency, and vulnerability to downtime during live video authoring.

## Decisions

### 1. Two-Tier Discovery and Audio Fulfillment Architecture
We decouple discovery from audio delivery:
- **Discovery Layer**: The backend queries OpenOpus for composer biographies, historical epochs, and opus catalogs.
- **Fulfillment Layer**: When a creator imports or selects a classical piece, an automated **Public Domain Audio Resolver** queries the **Internet Archive Audio API** (specifically public domain collections like George Blood 78s / Musopen) and **Wikimedia Commons Audio** for matching recordings. Downloaded files are saved to `data/music/classical/{composer_slug}/{work_slug}.mp3`.
- **Manual Upload Fallback**: If no automated recording is indexed or accessible, an integrated upload dropzone allows creators to supply their own recording pre-bound to that OpenOpus work.

### 2. Backend Proxy Gateway with Persistent File Caching
We introduce dedicated endpoints in `api_server.py` under `/api/music/openopus/...`:
- Queries are normalized and cached locally in `cache/openopus/*.json` with TTL validation.
- Subsequent searches or composer browses resolve in sub-millisecond local latency, allowing offline project authoring.

### 3. Dual UI Surface Area (Library Tab + Stage 7 Studio)
We surface OpenOpus at two key creative touchpoints:
1. **Ambient Music Tab**: An interactive Master-Detail "Classical Repertoire" catalog explorer supporting epoch filtering (*All, Baroque, Classical, Romantic, 20th Century*), composer gallery cards with portraits, work genre accordion (*Orchestral, Keyboard, Chamber, Vocal*), and instant search.
2. **Documentary Stage 7 (Ambient Music)**: A direct "Classical Masterpiece" selection drawer allowing creators to audition and swap classical movements into Movement 1 (Opening), Movement 2 (Tension/Development), or Movement 3 (Resolution).

### 4. Configurable Start Offset & Movement Trimming
Because classical works frequently exceed 10 minutes, Stage 7 and the music inspector expose a configurable `start_offset` (seconds or `mm:ss`). In `rendering/ffmpeg_renderer.py`, FFmpeg accepts `-ss {start_offset} -t {movement_duration}` with a 2.5-second crossfade curve so creators can feature iconic climaxes and motifs rather than forcing 00:00 playback.

### 5. Rule-Based Epoch/Genre to Narrative Vibe Mapping
Classical works are automatically mapped into the project's existing 6-vibe taxonomy upon import:
- *Baroque / Chamber / Keyboard* $\rightarrow$ `calm_focus` or `cinematic_documentary`
- *Romantic / Orchestral / Stage* $\rightarrow$ `dramatic_tension` or `uplifting_inspirational`
- *20th Century / Modern* $\rightarrow$ `mystery_cosmic` or `dramatic_tension`
Imported tracks are saved under `data/music/classical/{composer_slug}/` and registered directly in `data/music/catalog.json` with full movement role metadata.

## Consequences
- **Positive**: Equips the video generator with a vast classical repertoire; eliminates external browser CORS issues; ensures all selected music is backed by physical audio assets compatible with FFmpeg rendering.
- **Trade-off**: Requires automated resolution heuristics against public domain sources; tracks with no public-domain audio match require manual audio upload by the user.
