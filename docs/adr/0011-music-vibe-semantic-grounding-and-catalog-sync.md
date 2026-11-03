# 11. Music Vibe Semantic Grounding, Catalog Auto-Sync, and Energy Staging

## Status
Accepted

## Context
In documentary video production, musical atmosphere must tightly resonate with narrative sentiment and pacing across movements. The legacy music selection logic had three foundational weaknesses:
1. **Shallow Title-Keyword Matching**: Classification relied strictly on substring matching across a small set of static keywords against the raw video topic title. Abstract or metaphoric titles scored 0 matches, causing the engine to fall back to unconstrained pseudo-random hash picking across the entire catalog (e.g. assigning eerie mystery tracks to upbeat business profiles).
2. **Catalog Metadata Disconnect**: When users manually added or uploaded audio files into `data/music`, files were stored without registering in `catalog.json`. Uncataloged files lacked duration, mood, energy, and genre tagging, preventing them from being intelligently chosen.
3. **Flat Narrative Dynamics**: Selecting tracks for multi-movement progression lacked energy awareness, occasionally placing a high-tempo climax track at the opening and a low-energy ambient pad during peak narrative tension.

## Decisions

### 1. Semantic Grounding via Script & Research Tone Inference
We upgrade category detection (`detect_topic_category`) into an LLM-grounded semantic classifier that evaluates both the Stage 1 research core points and the Stage 2 script narrative arc. When LLM services are offline or disabled, it falls back to an expanded, weighted keyword lexical parser with semantic clustering.

### 2. Music Catalog Auto-Scanner and Metadata Normalization
We introduce an automatic catalog synchronization routine in `generators/music.py` and `api_server.py`:
- Scans `data/music` recursively for newly added audio tracks (`.mp3`, `.wav`, `.m4a`, etc.).
- Inspects audio metadata (duration, bitrate, file size, folder-derived category).
- Enriches `data/music/catalog.json` dynamically so user-uploaded tracks are immediately registered with searchable tags and energy classifications.
- Provides an automated categorization heuristic for uploaded files based on audio stem names and folder locations.

### 3. Three-Tier Movement Energy Staging
We establish explicit movement roles and energy constraints:
- **Movement 1 (Opening Context & Setup)**: Constrained to `energy: low` or `energy: mid` with atmospheric pads and curious pulses.
- **Movement 2 (Deep Dive & Conflict/Tension)**: Constrained to `energy: mid` or `energy: high` with driving rhythmic progression and tension beds.
- **Movement 3 (Climax, Resolution & Outlook)**: Constrained to `energy: high` or uplifting resolve (`uplifting_inspirational` / `calm_focus`), avoiding anti-climactic dropouts.

### 4. Direct Vibe Preset Override in Stage Studio
We add a global "Music Vibe Override" control in Documentary Stage Studio (Stage 7). Creators can explicitly select the target primary genre (`tech_futuristic`, `dramatic_tension`, `cinematic_documentary`, `mystery_cosmic`, `uplifting_inspirational`, `calm_focus`) and trigger an instant 3-movement re-match without touching underlying code.

## Consequences
- **Positive**: Eliminates jarring tonal mismatches; guarantees user-uploaded tracks are instantly discovered and cataloged; ensures emotional pacing naturally builds from opening exposition to climax resolution.
- **Trade-off**: Requires lightweight catalog scan overhead on upload and server boot; existing untagged tracks in catalog will be heuristically assigned default energy tiers based on folder category.
