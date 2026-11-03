# 12. Batch Background Track Ingestion with Drag-and-Drop and Safe Categorization

## Status
Accepted

## Context
Creators frequently acquire royalty-free music libraries in packs of 10 to 50 tracks. The previous upload interface in the Ambient Music tab was restricted to single-file selection via a native HTML file picker, lacked drag-and-drop capabilities, and forced all files into a single manual category or root folder with risk of overwriting existing tracks.

## Decisions

### 1. Multi-File Selection and Drag-and-Drop Dropzone
We enhance the Ambient Music upload UI in `ui/index.html` by:
- Adding the `multiple` attribute to the audio file picker.
- Implementing an interactive visual Drag & Drop Zone (`music-dropzone`) allowing creators to drag groups of `.mp3`, `.wav`, `.m4a`, `.ogg`, or `.flac` files directly from Windows Explorer.
- Displaying real-time batch upload progress (e.g., "Uploading 14 audio tracks...").

### 2. Multi-File Dispatch to `/api/music/upload-multiple`
All selected or dropped files are batched into a single `FormData` multipart payload and sent directly to `/api/music/upload-multiple`.

### 3. Intelligent Filename-Based Auto-Categorization
The category selector introduces an `auto` option ("Auto Categorize by Filename"). When selected, the backend inspects each file's stem name against `CATEGORY_KEYWORDS` (e.g., "cyber", "piano", "tension", "space", "calm") to place each track into its optimal target subdirectory (`tech_futuristic`, `cinematic_documentary`, `mystery_cosmic`, `dramatic_tension`, `uplifting_inspirational`, `calm_focus`). Files with no specific keyword match are routed to `calm_focus` or `custom`.

### 4. Non-Destructive Conflict Resolution
When an uploaded file collides with an existing file in the target folder, the backend generates an incremental suffix (e.g. `track_1.mp3`, `track_2.mp3`), preventing accidental mutation or broken references in historical video projects.

### 5. Immediate Catalog Synchronization
Following file writes, `/api/music/upload-multiple` triggers `sync_catalog("data/music")` so newly ingested tracks are immediately visible, labeled, and auditionable across both the Ambient Music tab and Documentary Stage Studio (Stage 7).

## Consequences
- **Positive**: Massively simplifies expanding the ambient soundtrack library; enables dropping full music packs in seconds; auto-sorts tracks into appropriate narrative vibe categories without file collisions.
- **Trade-off**: High file counts (e.g. >100 files in a single drag) may take several seconds to upload and sync catalog; file size validation is enforced to avoid browser memory spikes.
