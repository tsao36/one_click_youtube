# ADR 0015: World Setting Spec, Anachronism Guard, and Footage Domain-Gating

## Status
Accepted

## Context
In historical and topic-specific documentaries (such as the 1946 Tokyo War Crimes Trials / 東京大審), image generation and stock footage selection previously suffered from two major classes of errors:
1. **False-Positive Stock Footage Matches**: Acronyms without word boundaries in [`agents/scene_planner.py`](file:///c:/AI%20Project/Youtube_video/agents/scene_planner.py) caused English substrings to trigger unrelated stock assets (e.g. `conCERN` matched `CERN`, injecting the 3D model of the CERN Large Hadron Collider into 1946 tribunal scenes 12 and 38). Furthermore, technical/physics regexes ran indiscriminately across historical war documentaries.
2. **Loss of Historical Facts & Physical Reality**: The pipeline lacked an upstream grounding schema for era, physical condition, and architectural settings. Generic visual styles (e.g., `cinematic_documentary` / `anime_shinkai`) injected tags like "pristine urban streets and tranquil nature" into 1945 Tokyo, completely ignoring that postwar Tokyo was in firebomb ruins, that the Tokyo Trials took place indoors at the Ichigaya War Ministry building, and that the 11 judges on the bench were all male representing 11 Allied nations (including India, the Philippines, and China).

## Decisions

### 1. Stage 1 Upstream `world_setting` Extraction
Stage 1 (Research) now outputs a structured `world_setting` schema stored in `research/research.json`:
- `temporal_era`: The authoritative time period (e.g., "1945–1946 Post-WWII").
- `environment_reality`: The factual physical state of locations (e.g., "Tokyo in ruins from firebombing, debris, rubble, destroyed wooden structures, overcast/smoke; no modern skyscrapers").
- `key_settings`: Canonical physical architectures & interiors (e.g., "Indoor military tribunal courtroom at Ichigaya War Ministry auditorium, wooden judge bench, translation headphones, microphones, enclosed hall").
- `ensemble_specs`: Strict demographics, gender, ethnicity, and attire constraints for groups (e.g., "11 judges, all male, representing 11 Allied nations including Radhabinod Pal from India in turban, Delfin Jaranilla from Philippines, Mei Ru'ao from China in black robe; no female judges").
- `negative_anachronisms`: Explicit forbidden visual elements (e.g., "modern Tokyo, skyscrapers, pristine streets, outdoor court, female judges, digital screens").

### 2. Anachronism Guard & Dynamic Style Conflict Stripping (Stage 4)
When composing generation prompts, `world_setting` constraints take precedence over global visual style presets:
- Generic style tags that conflict with `environment_reality` (e.g., "pristine urban streets", "vibrant sunlight glints", "modern architecture") are dynamically stripped from positive prompts.
- **Dual-Mode Engine Support**:
  - For local ComfyUI/SDXL: `negative_anachronisms` are injected directly into the native `negative_prompt` field.
  - For Cloud APIs (Google Nano Banana / Gemini Image, DALL-E 3, FLUX cloud): an explicit natural language constraint clause is appended to the prompt (e.g. `CRITICAL ERA CONSTRAINTS: Must be strictly historically accurate 1945-1946; absolutely NO modern buildings, NO modern vehicles, NO outdoor court, NO female judges`).

### 3. Two-Tier Pipeline Propagation (Stage 3 & Stage 4)
- **Stage 3 (Scene Planner)**: System prompt receives `world_setting` so the LLM does not hallucinate contradictory visual descriptions (e.g. it knows Tokyo is in ruins and the court is indoors before planning shots).
- **Stage 4 (Prompt Generator)**: Prompts anchor historical era, physical condition, and architectural settings at the front of each prompt string.

### 4. Footage Keyword Domain-Gating & Word Boundary Protection
In `agents/scene_planner.py`:
- All Latin acronyms are enclosed in regex word boundaries (`\bCERN\b`), preventing false positive matches on words like `conCERN`.
- Stock footage keyword rules are domain-gated: technical, semiconductor, and particle physics rules are dormant when the project topic is historical or non-technical.
- Stock keyword matches must pass semantic category validation before replacing AI generation.

### 5. Pre-Stage 5 Prompt-Level Fact Verification
Before dispatching Stage 5 generation, a lightweight validation audit checks prompts against `world_setting` constraints, flagging or auto-correcting spatial and temporal contradictions (e.g. outdoor courtroom vs indoor).

### 6. Scope Boundary: Clean Forward Pipeline (No Retroactive Backfill)
We explicitly reject retroactive automated backfill buttons for older project folders. When historical settings are desired, creators run or re-run Stage 1 Research through the standard clean forward pipeline.

### 7. UI Exposure & Interactive Editing (Stage 1 Research Workspace)
The Stage 1 Research UI displays an editable "World Setting & Historical Constraints" card with fields for Temporal Era, Physical Environment Reality, Key Settings, Ensemble Rules, and Forbidden Anachronisms, allowing creators to inspect or adjust historical parameters before moving downstream.

### 8. Artistic Medium vs. Physical Reality Coexistence
When stylized aesthetics (such as Makoto Shinkai anime or 35mm cinematic film) are selected, the Anachronism Guard preserves the artistic rendering medium (linework, lighting gradient, film grain), but strictly purges contradictory content keywords (e.g. pristine modern streets) and substitutes the historical physical reality (1945 war ruins).

### 9. Auto-Fill & Smart Preservation on Stage 1 Re-Runs
- By default, re-running Stage 1 automatically populates all 5 `world_setting` fields using LLM inference on the topic and research dossier.
- **Smart Preservation**: If a creator has already customized and saved `world_setting` fields in `research.json`, full Stage 1 re-runs preserve their manual adjustments to prevent accidental overwrites.
- A `🔄 Reset to AI Suggestion` action allows resetting to newly generated AI values on demand.

### 10. Instant World Setting Generation Endpoint (`POST /api/projects/{id}/generate_world_setting`)
To facilitate rapid testing, creators can trigger an instant ~2-second LLM inference that analyzes the current topic and notes and populates the World Setting card directly, avoiding the need to wait for the complete Stage 1 web research execution.

## Consequences
- **Positive**: Eliminates nonsensical stock replacements (e.g. CERN collider in WWII trials) and ensures historical documentaries accurately depict war ruins, accurate courtroom interiors, and authentic judge rosters.
- **Zero Friction**: Initial project creation and testing auto-fill all parameters without requiring manual typing.
- **Non-destructive**: Manual customizations are safely preserved across full pipeline re-runs while remaining refreshable with a single click.
