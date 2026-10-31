# 0005. Cross-Stage Universal Text Replacement & Downstream Voice Cascade

Date: 2026-10-24  
Status: Accepted

## Context
When producing automated AI video projects, script and narration content is generated sequentially across multiple pipeline stages:
1. **Stage 1 (Research)**: Notes, entities, and grounding facts (`research/research.json`).
2. **Stage 2 (Script)**: Markdown draft and structured sections (`script/script.md` & `script/script.json`).
3. **Stage 3 (Scenes)**: Storyboard segments with spoken narration, phase headers, and callouts (`scenes/scenes.json`).
4. **Stage 4 (Prompts)**: SDXL/Flux image generation prompts containing visual descriptions and character names (`prompts/image_prompts.json`).
5. **Subtitles**: Synthesized cue tracks (`subtitles/subtitles.srt` & `subtitles/subtitles.ass`).

Previously, find-and-replace tools operated strictly within single local UI fields or single stages. If a user discovered a technical mispronunciation, misspelled entity, or changed a proper name in Stage 1 or Stage 2, Stage 3's scene narrations still contained the stale text. If changed in Stage 3, the script and research remained out-of-sync, causing future re-segmentations to resurrect the incorrect word. Furthermore, modifying a word in scenes required manual hunting through 40+ scene cards to find which ones required TTS re-synthesis.

## Decision
We implemented an atomic, cross-stage text replacement and cascading invalidation architecture:
1. **Unified Text Replace API (`POST /api/projects/{project_id}/text_replace`)**:
   - Accepts search keywords, replacement strings, case sensitivity flags, and optional target stage lists.
   - Atomically updates `research.json`, `script.md`, `script.json`, `scenes.json` (all string fields: narration, phase_turn_text, callout_text, visual_description, prompt), `image_prompts.json`, `subtitles.srt`, `subtitles.ass`, and `project.json` (title, topic, thumbnail metadata).
   - Tracks exact occurrence counts per stage and identifies affected scene IDs.
2. **Automatic Downstream Audio Invalidation**:
   - Any scene whose spoken `narration` changes is automatically marked with `sc.audio.status = Status.PENDING` and `sc.audio.meta["text_outdated"] = True`.
   - The project's `voice`, `subtitles`, and `render` stages are transitioned to `PENDING`.
3. **Instant Re-synthesis & Fast Re-render Integration**:
   - `core/pipeline.py::rerender_voice_and_video` was updated so that `scope="mismatched"` checks `s.audio.status == Status.PENDING or meta.get("text_outdated")`.
   - The UI immediately renders a one-click action button (`[🎙️⚡ 立即極速重整語音與 1080p 影片]`), enabling the user to re-synthesize only the changed scenes and re-render the master 1080p MP4 in seconds.
4. **Universal UI Presence & Keyboard Shortcut**:
   - Available via batch replace toolbars in Stage 1 (Research), Stage 2 (Script), Stage 3 (Scenes), Stage 4 (Prompts), and the Scene Editor table.
   - Accessible globally via top-bar header button and `Ctrl+H` shortcut with a modal dialog supporting live preview and occurrence breakdown.

## Consequences
- **Pros**: Zero drift between research, script, scenes, prompts, and subtitles. Rapid iteration without manual retyping across multiple tabs. High-speed video regeneration by selectively touching only invalidated scene audio tracks.
- **Cons**: Case-insensitive batch replace requires user awareness when replacing short strings; mitigated by default word boundary matching, preview mode, and dry-run inspection.
