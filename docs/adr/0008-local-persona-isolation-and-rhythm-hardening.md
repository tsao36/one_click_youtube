# 0008. Local Persona Isolation, Pre-Flight Quota Checks, and Split-Angle Rhythm Hardening

Date: 2026-11-02  
Status: Accepted

## Context
Following the implementation of the custom drama formula and multi-character pipeline (ADR-0006) and the fail-fast quota guard policy (ADR-0007), three critical operational decisions required architectural hardening:
1. **Character Modification Isolation**: When creators refine character appearance prompts, wardrobe (e.g. episodic costumes, injury makeup), or regenerated portraits within a specific episode, automatic global propagation can unintentionally mutate the base archetype across unrelated or future episodes.
2. **Quota Depletion Early Warning**: Waiting for generation API calls to fail mid-batch on Scene 5 wastes time and token processing on upstream prompts.
3. **Pacing Degradation on Extended Lines**: High-tension viral short video relies on rapid visual cutting (<4.5s per shot). Extended dialogue lines exceeding 6.0 seconds create static, sluggish talking-head segments that damage viewer retention.

## Decision
We adopted the following architectural standards across the drama pipeline:

1. **Local Persona Isolation with Explicit Global Publishing (Q5)**:
   - When a project is created, characters from the global library (`data/characters/{slug}/`) are deep-copied into the project sandbox (`projects/{id}/characters/`).
   - Any modifications made in the Studio (re-generating a face reference, altering clothing tags, re-assigning voice profiles) are isolated strictly to that project.
   - An explicit UI action `[💾 同步回全域角色庫 (Publish to Global Library)]` must be intentionally clicked by the creator to promote project-level character adjustments back to the reusable global registry.

2. **Dual-Layer Quota Defense: Pre-Flight Probe + Runtime Trap (Q6)**:
   - **Pre-flight Probe**: Prior to initiating Stage 5 (Images/Video) and Stage 7 (Lip-Sync Animation), the pipeline executes a balance health check if the provider exposes an account endpoint (e.g. Fal.ai, Kie.ai). If available balance falls below the estimated single-shot floor cost, the stage halts *before* dispatching any requests.
   - **Runtime Trap**: For providers without balance query endpoints, runtime responses (HTTP 402, `balance_depleted`, `insufficient_credits`) immediately halt the pipeline, record stage failure, preserve already completed shot clips, and surface a high-visibility top-up warning banner.

3. **Split-Angle Dialogue Cutting for Extended Lines (Q7)**:
   - When a single spoken line in Stage 3 exceeds 6.0 seconds (~20+ Chinese characters), the visual pipeline automatically segments the scene into a multi-angle shot sequence (e.g. Shot A: Medium Shot Push-In for 0.0s-3.5s ➔ Shot B: Tight Close-Up Reaction for 3.5s-end).
   - The scene's audio track remains continuous and uninterrupted while the visual cut preserves the dynamic 3.5s-4.5s rhythm necessary for 9:16 platform retention.

## Consequences
- **Pros**: Protects global character archetypes from unintended episode-specific mutation. Prevents partial wasted generation on depleted accounts. Eliminates monotonous, static long-shot talking heads in viral short dramas.
- **Cons**: Multi-angle splitting increases the number of generated video segments for long dialogue scenes; balanced by proportional pacing bounds that cap total project shots within budget.
