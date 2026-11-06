# ADR 0018: Epic Chronicle Mural Visual Style (`epic_chronicle_mural`)

## Status
Accepted

## Context
A new visual art style inspired by textured, grand narrative oil paintings and fine art murals was introduced. The reference imagery demonstrated:
1. Masterful tactile digital oil painting with textured impasto brushwork, weathered surface materiality, and rich mineral pigment palettes (ochre, slate grey, raw umber, and vibrant vermilion accents).
2. Tense, character-driven dramatic staging with heroic focal presence.
3. A visual risk where diffusion models encountering narrative or mural prompts produce fragmented multi-vignette collages, split panels, or discordant sub-scenes (as seen in panoramic scroll illustrations).

Two critical architectural forks required resolution:
1. **Coupling to Historical Era**: While initial references depicted ancient Chinese military subjects, hardcoding historical anachronism guards or ancient Chinese dynasty requirements into the style definition would restrict the aesthetic from being used across mythological, allegorical, fantasy, or modern dramatic narratives.
2. **Compositional Staging Hierarchy**: Multi-vignette / multi-plane mural compositions frequently confuse modern diffusion models into rendering messy multi-panel splits, border vignettes, or duplicated characters.

## Decisions

### 1. Style Key and Canonical Naming
The style is registered in `config/settings.yaml` under the key:
- **Key**: `epic_chronicle_mural`
- **Label**: `Historical Chronicle & Epic Mural (史詩歷史巨畫)`

### 2. Decoupling Medium Aesthetics from Historical Period Gating
The style definition specifies the *rendering medium, brushwork, pigment behavior, and lighting* rather than imposing mandatory ancient historical locks:
- **Style**: `masterful epic chronicle digital oil painting, textured impasto brushwork, rich mineral earth tones with vermilion and deep ochre accents, fine art narrative illustration, textured canvas grain, 8k resolution`
- **Lighting**: `dramatic natural sunlight, dusty atmospheric volumetric light beams, warm directional rim lighting, rich chiaroscuro depth`
- The pipeline's ADR 0015 Anachronism Guard remains active if and only if the Stage 1 Research explicitly defines a historical `world_setting`. The style preset itself remains era-agnostic.

### 3. Strict Single-Subject Focal Enforcement & Anti-Collage Negatives
To prevent diffusion models from generating split-screen collages, separate vignettes, or comic panel frames (like image #2's multi-scene composition), the preset enforces:
- **Lens**: `cinematic 50mm lens, single clear primary focal subject, centered heroic perspective, unified single-frame composition, deep atmospheric environmental depth`
- **Negative Safeguards**: Explicitly bans `split screen, multi-panel, collage, montage, multiple frames, comic panel borders, vignette borders, diptych, triptych, anime, 3D CGI plastic render, airbrushed digital art, smooth plastic skin, extra limbs, bad anatomy, duplicate faces, text, watermark`.

### 4. Standard Typography Synergy
Maintains the clean standard `youtube_standard` subtitle layout and Microsoft JhengHei UI typography without imposing specialized calligraphy overlays.

## Consequences
- **Positive**: Creators can apply this rich, textured oil and mineral-vermilion mural aesthetic to any narrative topic without triggering false historical era conflicts. Images remain focused and cinematic without messy split-panel collage artifacts.
- **Negative**: Videos requiring simultaneous multi-event scroll compositions must compose them explicitly via storyboard scene sequences rather than relying on a single multi-vignette prompt frame.
