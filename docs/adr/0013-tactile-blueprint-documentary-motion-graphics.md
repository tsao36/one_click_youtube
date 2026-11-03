# 13. Tactile Blueprint Documentary Motion Graphics Architecture

## Status
Accepted

## Context
In Documentary Mode, video scenes explaining complex engineering, scientific, and geopolitical topics previously relied on generic SaaS presentation cards (`TitleScene`, `GridCompareScene`, `KCurveScene`, `StatNumberScene`). These flat cards lacked visual depth and pedagogical variety, falling far short of broadcast-grade documentary explainers such as fOx Hsiao's investigative tech videos (e.g. *The Four Paths to Reading Brain Signals: Neuralink*).

Furthermore, motion graphics were previously triggered in `generators/remotion_cards.py` via naive regex keyword matching for metrics, lacking semantic comprehension of why an explanatory visual is needed or how multi-part comparative data should be structured.

## Decisions

### 1. Dedicated 4-Archetype Documentary Component Suite
We deprecate generic SaaS-style cards in Documentary Mode in favor of four domain-specific documentary motion graphic archetypes in `remotion-video/src/documentary/`:
1. **`BranchPathwayScene` (4-Path Branching & Elimination)**: Visualizes alternative technical routes, evolutionary branches, or strategic choices via animated SVG flow lines, node highlights, and elimination strike-throughs.
2. **`LeaderCalloutScene` (Technical & Anatomical HUD)**: Generates origin anchor dots, elbow leader lines, and telemetry labels that point to anatomical layers or mechanical components on an underlying image.
3. **`ScaleCompareScene` (Microscopic vs Real-World Loupe)**: Pairs microscopic elements against everyday reference objects with an animated metric ruler to convey scale extremes (e.g. 5μm thread vs 100μm hair).
4. **`EvidenceHighlightScene` (Paper Document & Marker Redaction)**: Archival document/patent clipping on tactile paper with animated highlighter pen sweep (`clip-path`) over critical text.

### 2. "Tactile Blueprint" Design Language
All documentary motion graphic components adhere to a unified visual aesthetic:
- **Canvas Base**: Slate blueprint dark canvas (`#0A0E17`) with a subtle 20px coordinate grid (`rgba(255, 255, 255, 0.05)`).
- **Physical Depth**: Subtle rotational jitter ($-1.5^\circ$ to $+1.5^\circ$) and drop shadows (`0 20px 40px rgba(0,0,0,0.6)`) to simulate paper cutouts and physical blueprints.
- **Dynamic Linework**: SVG connectors animated with `strokeDasharray` and `strokeDashoffset` driven by Remotion `spring()`.
- **Telemetry Accents**: High-contrast typography paired with luminous telemetry indicators (`#00F5FF` electric cyan, `#F59E0B` amber warning, `#10B981` success green).

### 3. Full Canvas Background Composition in Remotion
We maintain Option A (full canvas rendering inside Remotion) rather than multi-pass transparent alpha video overlays. Remotion directly composites the dimmed background image, camera drift, blueprint grid, and motion graphics into a unified 1080p MP4. This avoids heavy alpha ProRes/WebM transcoding, prevents edge-compositing artifacts, and enables synchronized lighting and vignette effects.

### 4. Semantic Motion Graphic Director Pass
We replace the regex-based heuristic in `generators/remotion_cards.py` with an LLM-driven Motion Graphic Director pass in Stage 3/Storyboarding. The director identifies 2 to 4 high-cognitive-load explanatory beats per documentary, assigns the optimal archetype, and produces structured Pydantic props (e.g. branch titles, elimination states, anatomical pointer coordinates, and scale comparison values).

### 5. Normalized Anchor Coordinates with Golden-Ratio Fallbacks
For `LeaderCalloutScene`, origin feature targets on the underlying background image are specified as relative $(x, y) \in [0.1, 0.9]$ normalized coordinates. If coordinates are omitted or the image is abstract, the engine automatically selects balanced golden-ratio fallback slots (e.g. focal point $(0.38, 0.45) \to$ telemetry card $(0.72, 0.35)$) to guarantee collision-free layout.

### 6. Three-Phase Dramatic Animation Timeline
Dynamic scenes such as `BranchPathwayScene` utilize a standardized 3-phase dramatic curve:
- **Phase 1 (0% – 30%)**: Staggered branch entry with progressive SVG stroke drawing.
- **Phase 2 (30% – 65%)**: Elimination dimming (opacity 0.35, strike-through) and luminous accentuation of the chosen path.
- **Phase 3 (65% – 100%)**: Deep technical telemetry expansion on the chosen path.

### 7. Concentric Loupe Micro-Scale Visual Engine
`ScaleCompareScene` implements a laboratory-grade dual inspection interface featuring a circular magnification loupe ($20\times$ zoom with crosshairs) and an animated sliding micrometer/millimeter scale ruler with physical spring dampening, directly contrasting microscopic elements with macro reference benchmarks.

### 8. Two-Pass Orchestration Lifecycle (Stage 3 & Stage 8)
- **Pass 1 (Stage 3 Storyboard)**: LLM emits structured `motion_graphic_spec` with pedagogical intent, category, and props.
- **Pass 2 (Stage 8 Animation)**: Conforming pass binds the exact audio narration duration (`duration_in_frames = round(duration * fps)`), attaches the rendered image background (`bgSrc`), validates with Pydantic, and calls Remotion rendering. Any render failure automatically falls back to Ken Burns on the background image without crashing the pipeline.

### 9. Slim Codebase Policy & Legacy Card Deprecation
To keep the codebase slim, maintainable, and free of architectural debt, all legacy prototype cards (`TechCard`, `MinimalistCard`, `CinemaImpactCard`, `HelloWorld`, and outdated generic comparisons) are removed from `remotion-video/src/`. The Remotion composition catalog and Pydantic schemas will exclusively maintain the 4 active Tactile Blueprint documentary archetypes.

### 10. Canonical Reference Preview Compositions
`remotion-video/src/Root.tsx` will register dedicated preview compositions with realistic Neuralink reference props modeled after fOx Hsiao's investigative documentary:
1. `Preview_BranchPathway`: The 4 Brain Signal Paths with 3-phase elimination animation.
2. `Preview_LeaderCallout`: Cortical anatomical layer leader lines with telemetry tags.
3. `Preview_ScaleCompare`: 5μm polymer thread vs 100μm hair with $20\times$ concentric loupe and sliding micro-ruler.
4. `Preview_EvidenceHighlight`: Archival clinical document with dynamic highlighter sweep.

These enable instantaneous visual inspection and hot-reload testing via Remotion Studio (`npm run start`).

### 11. Documentary Style Gallery Modernization in Settings & Stage Studio
The frontend Style Gallery in Global Settings (`ui/index.html`) is updated to feature the 4 active Tactile Blueprint archetypes in a responsive grid, with `EvidenceHighlightScene` established as the default factory style.

### 12. Automated High-Fidelity Static Preview Assets
All preview thumbnails displayed in the Web UI (`ui/remotion/style_*.png` and `scene_overlay_preview.png`) are directly rendered from the Remotion `Preview-*` compositions using Remotion CLI still capture, ensuring 100% visual fidelity between the UI gallery and rendered MP4 deliverables. Older prototype thumbnails are deleted.

## Consequences
- **Positive**: Produces cinematic, investigative explainers matching high-end YouTube channels; guarantees structured, meaningful data visualization instead of random metric popups; provides clean Remotion components that preview smoothly in Remotion Player.
- **Trade-off**: Requires expanding `core/motion_graphics_schema.py` and adding a new planning prompt pass in the documentary pipeline.
