# 0006. Custom Drama Formulas and Multi-Character Pipeline Architecture

Date: 2026-11-02  
Status: Accepted

## Context
Short-form vertical video (9:16) platforms require high-retention, plot-driven narratives characterized by sharp conflict and micro-drama pacing. The video pipeline originally supported only linear explainer documentaries and a single hardcoded workplace revenge script template.

To enable arbitrary genre archetypes (e.g., suspense twists, romantic melodrama, thriller debt-collection, sci-fi cybercrime) with customizable casts, the system faced critical architectural challenges:
1. **Fixed Scene Count vs. Variable Video Duration**: A static 3-scene structure failed to accommodate durations from 15 seconds to 120 seconds.
2. **Speaker Name vs. Character Cast Disconnect**: When script dialogues used contextual aliases (e.g. `[房東]` / `[林晚晚]`), naive substring and modulo matching collapsed alternating dialogue lines into a single character, erasing the antagonist from voice and image generation.
3. **Hardcoded Styling Overrides**: Image generation prompts previously enforced corporate navy business suits in high-rise offices, completely ignoring character costume and appearance prompts defined in the roster.

## Decision
We implemented a dedicated architecture for customizable short drama generation:

1. **Persistent Formula Registry (`data/drama_formulas.json`)**:
   - Stores user-defined and built-in drama formulas with 3-beat rhythm guidance, default character rosters (2 to 4 actors), and sample prompt templates.
   - Provides CRUD REST endpoints (`GET /api/drama/formulas`, `POST /api/drama/formulas`, `DELETE /api/drama/formulas/{id}`) and LLM autocomplete (`POST /api/drama/formulas/autocomplete`).

2. **Dual-Layer Character Persistence Strategy**:
   - **Global Reusable Library (`data/characters/{slug}/`)**: Stores canonical turnaround face portraits and default configurations (`portrait.png`, voice profiles, appearance prompts) reusable across multiple series episodes.
   - **Project-Level Snapshot (`projects/{id}/characters/`)**: Clones the active cast at project initialization, ensuring future modifications to global characters never corrupt or alter historical renders.

3. **Proportional Scene Pacing Algorithm**:
   - Dynamic formula: target shot count is calculated by dividing total runtime by ~4.0-5.0 seconds per shot (`total_shots = max(3, round(duration_sec / 4.5))`).
   - Distributes dramatic beats according to the viral golden ratio:
     - **Hook** (0-15% duration, ~1-2 shots): Explosive initial conflict line, high-impact camera push-in.
     - **Tension** (15-70% duration, ~55% shots): Sharp verbal sparring, stakes escalation, alternating character shots.
     - **Payoff / Climax** (70-100% duration, ~30% shots): Truth revealed, authority intervention, mic-drop dialogue line.

4. **Global Speaker-to-Roster Alignment Engine (`resolve_script_speakers_to_roster`)**:
   - Performs a full-script pre-pass to map all distinct dialogue speakers to specific roster characters.
   - Resolves matches hierarchically: exact name match -> substring match -> role keyword match -> semantic role/gender heuristics (`MALE_ANTAG_KEYWORDS` vs `FEMALE_HEROINE_KEYWORDS`) -> round-robin slot filling.
   - Enforces 1:1 consistency: every line spoken by a character alias is assigned to the identical character ID, dedicated voice profile (`voice_profile`), appearance prompt, and reference portrait across all scenes.

5. **Dynamic Prompt & Attire Conditioning**:
   - Replaced hardcoded corporate attire with character roster `appearance` / `appearance_prompt` attributes.
   - Prioritizes scene visual descriptions for background synthesis, ensuring authentic environmental settings (e.g. apartment interiors, urban alleys) rather than mandatory office desks.

## Consequences
- **Pros**: Any short drama formula can be authored, shared, and scaled to any duration. Script dialogues automatically map to full multi-character casts with dedicated voices and facial identities without manual tag remapping.
- **Cons**: Dramas with more distinct speakers than available roster slots fall back to round-robin actor reuse; mitigated by formula-level definition of 2 to 4 characters matching the plot structure.
