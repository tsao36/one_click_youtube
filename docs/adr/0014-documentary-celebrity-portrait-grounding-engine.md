# 14. Documentary Celebrity Portrait Grounding Engine

## Status
Accepted

## Context
In Documentary Mode, video scripts frequently reference real-world historical figures (e.g. Albert Einstein, J. Robert Oppenheimer, Winston Churchill), political leaders (e.g. Donald Trump, Tsai Ing-wen, Lee Teng-hui), and technology founders (e.g. Jensen Huang, Elon Musk, Sam Altman). 

Prior to this decision, the pipeline had three structural defects:
1. **Static 50-Name Regex Bottleneck**: Figure recognition was constrained to a static regex array in `agents/scene_planner.py`. Any celebrity not hardcoded (e.g. Linus Torvalds, Sundar Pichai, Richard Feynman) was missed completely and sent to AI diffusion models (ComfyUI / SDXL), yielding distorted, unrecognizable, or hallucinated faces.
2. **Misrouted YouTube Snippet Trap**: Tech figures were assigned `media_source = "youtube_snippet"` with queries like `"Elon Musk interview"`. When `yt_dlp` was absent or video download failed, the fallback Wikimedia Commons search was burdened with the video-oriented query `"Elon Musk interview filetype:bitmap"`, drastically degrading portrait discovery.
3. **Contradictory Visual Bible Suppression**: The visual bible prompt explicitly commanded `"Use generic people (no celebrities)"`, actively suppressing the LLM from registering real historical or tech figures.

## Decisions

### 1. Dynamic Semantic Entity & Celebrity Extraction
We introduce an LLM-assisted entity recognition pass during Stage 3 Storyboarding that scans scene narration and script text for real-world historical, scientific, corporate, and political figures. 
The extractor outputs:
- **Canonical International Name**: Maps vernacular/localized names (e.g. `黃仁勳` $\to$ `Jensen Huang`, `愛因斯坦` $\to$ `Albert Einstein`, `馬斯克` $\to$ `Elon Musk`).
- **Media Source**: Assigns `media_source = "stock_portrait"`.
- **Search Query**: Assigns clean portrait search keywords without interview or video noise.

### 2. Dedicated Wikipedia Infobox Resolver Probe
We implement a zero-key Wikipedia Page Summary resolver (`resolve_wikipedia_portrait`) in `providers/stock_client.py`. 
When `media_source == "stock_portrait"`:
1. The resolver queries the official Wikipedia REST API (`https://en.wikipedia.org/api/rest_v1/page/summary/{title}` and Chinese Wikipedia equivalent) to extract the primary biographical infobox thumbnail.
2. If the Wikipedia page returns an official portrait with resolution $\ge 640\text{px}$, it downloads the original unconstrained image file (`originalimage.source`).
3. If Wikipedia summary yields no direct portrait, it falls back to `search_wikimedia(canonical_name, media_type="image")`.
4. Only if both authentic sources return zero candidates does it gracefully fall back to primary AI image generation.

### 3. Decoupling Still Portraits from YouTube Clips
Still portrait scenes are decoupled from `youtube_snippet`. Real figures featured in narration or visual descriptions strictly resolve to authentic public domain / Creative Commons still portraits formatted to 16:9 1080p via `format_stock_image()`. YouTube video snippets are reserved exclusively for scenes explicitly flagged for action B-roll or product demonstrations.

### 4. Removal of "No Celebrities" Guard in Documentary Mode
We update `agents/scene_planner.py` to lift the `"Use generic people (no celebrities)"` prompt restriction for documentary projects, allowing the visual bible to document recurring historical and public figures with their canonical biographical portrait references.

## Consequences
- **Positive**: 100% coverage of historical, scientific, and industry public figures without maintaining brittle regex lists; authentic, verifiable public domain portraits replace distorted AI diffusion caricatures; zero API key requirement via Wikipedia REST API and Wikimedia Commons.
- **Trade-off**: Requires network access to Wikipedia / Wikimedia during Stage 5 image generation. If completely offline, it falls back to local AI generation.
