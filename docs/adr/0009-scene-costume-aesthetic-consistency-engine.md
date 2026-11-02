# 0009. Scene, Costume, and Aesthetic Consistency Engine for Stage 5 Drama Generation

Date: 2026-11-02  
Status: Accepted

## Context
In previous iterations of the AI short drama pipeline, while character facial likeness could be conditioned via single-image face references, generated shots across an episode suffered from visual incoherence:
1. **Background Scene Drift**: Consecutive shots in the same scene randomly switched between different architectural backdrops, interior decors, wall textures, and window views.
2. **Costume and Wardrobe Mutation**: Characters frequently had their shirts, ties, jackets, fabric patterns, or colors randomly changed between shots within the same continuous scene.
3. **Aesthetic/Look & Feel Misalignment**: Stage 5 image generation prompts used hardcoded "authentic corporate short drama aesthetic" regardless of whether the drama was high-finance suspense, gritty revenge, historical period, or cyberpunk.
4. **Anatomical/Ergonomic Artifacts**: Multi-modal diffusion models frequently generated unnatural extra limbs or awkward anatomical poses when attempting dynamic action descriptions.

## Decision
We implemented a comprehensive 4-pillar Visual Consistency Engine:

1. **Environment & Aesthetic Bible (Stage 1 / Stage 2)**:
   - Each drama formula specifies a `default_primary_setting` (e.g. *"modern luxury executive CEO office, floor-to-ceiling glass windows overlooking city skyline, dark oak and polished marble"*) and an `aesthetic_profile` (e.g. *"sleek high-contrast cinematic realism, cold executive blue and sharp amber accent lighting, razor-sharp 8k film texture"*).
   - In Stage 1/2 (`plan_drama_production`), these are derived into `drama_plan.json` and `drama_bible.md` as canonical production guidelines.
   - Every storyboard shot defaults to `scene_location="primary"` and `costume_variant="default"`.

2. **Contextual Costume Locking**:
   - By default, all shots are locked to the character's Master Anchor Portrait (`costume_locked=True`, `costume_variant="default"`).
   - Character clothing prompts are forced to match the master approved costume unless the scriptwriter explicitly specifies a scene-level tag (`costume_variant != 'default'`), preventing inadvertent wardrobe shifts across dialogue cuts.

3. **Dual-Image Anchor Lock Conditioning in Stage 5**:
   - `generators/face_reference_generator.py` was enhanced to support dual-image anchor prompting:
     - **Image 1: Master Anchor Reference** (`{char_id}_styled_9x16.png`): Instructs the model to reproduce identical clothing style, fabrics, collar cuts, ambient lighting temperature, and room decor.
     - **Image 2: Face Reference** (`{char_id}_face.png`): Instructs the model to maintain exact facial structure, eye shape, nose bridge, skin tone, and hairstyle.
   - When only one anchor image exists, it serves as both master style/costume anchor and facial likeness anchor.

4. **Negative Ergonomic & Anatomical Safeguards**:
   - Injected strict negative constraints into all Stage 5 Gemini prompts: *"strictly two arms only, natural human anatomy, no extra limbs, no extra fingers, no mutated hands, no duplicate people in background, no background location change, no wardrobe color drift"*.

## Consequences
- **Pros**: Delivers visual continuity comparable to professionally shot live-action productions across 9:16 vertical episodes. Ensures costumes, room architecture, and color palettes remain identical across cuts. Custom formulas now dynamically dictate distinct aesthetic profiles without hardcoding.
- **Cons**: Requires initial anchor portrait generation during cast turnaround setup, adding a one-time setup step per character before episode generation.
