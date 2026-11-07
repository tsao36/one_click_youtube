# AI Video Generator Context

A local-first, cloud-accelerated automated video creation pipeline that transforms research topics into broadcast-quality 1080p YouTube explainer videos using LLMs, text-to-speech, AI imagery, lip-synced talking avatars, and hardware-accelerated rendering.

## Language

**Scene**:
The fundamental narrative and visual unit of a video, corresponding to a single storyboard script beat containing narration, visual description, camera motion, and three associated assets (`image`, `audio`, `animation`).
_Avoid_: Shot, clip, storyboard item, segment

**Presenter Scene**:
A storyboard scene specifically designated for an on-screen synthetic human host, where a talking avatar portrait or base video is lip-synced to the scene's voice audio track.
_Avoid_: Talking head, face clip, avatar shot, host cut

**B-Roll Scene**:
Any storyboard scene that conveys content visually through illustrated images, dynamic motion graphics, infographics, or video clips rather than an on-screen talking presenter.
_Avoid_: Normal scene, non-presenter scene, slide

**Stage Version**:
A macro-level snapshot of an entire upstream stage's output files (such as an outline, full script, or storyboard JSON), enabling rolling back or comparing different narrative drafts across the project.
_Avoid_: Revision, iteration, checkpoint

**Take**:
A micro-level media asset generation attempt for a single scene (such as an audio reading or image generation), preserved non-destructively so creators can audition and toggle alternative takes via `active_take`.
_Avoid_: Generation attempt, retry, draft asset

**Avatar Profile**:
An on-screen visual identity asset package consisting of portrait imagery, optional base video footage, and lip-sync configuration used to animate presenter scenes.
_Avoid_: Digital human, bot skin, presenter template

**Voice Profile**:
An auditory identity configuration specifying a TTS engine, timbre clone reference audio, and synthesis parameters used to voice narration lines across scenes.
_Avoid_: Voice font, speaker preset, sound profile

**Speaker Centroid**:
A normalized multi-dimensional latent speaker embedding vector (e.g. 192-dim ECAPA-TDNN) computed across clean reference recordings, used as an invariant conditioning tensor across all scenes to prevent acoustic drift and pitch variation.
_Avoid_: Voice vector, clone embedding, speaker stamp

**Clause Chunking**:
The process of dividing complex sentences into short, natural respiratory clauses (typically <= 24 characters) prior to neural speech synthesis, preventing attention degradation and repetition loops.
_Avoid_: Sentence cutting, phrase slicing, text splitting

**Dialogue Subtitle**:
Standard bottom-aligned, multi-line timed subtitles rendered directly into the video stream to ensure accessibility and clear comprehension.
_Avoid_: Caption, rolling text, bottom script

**Motion Callout**:
An animated on-screen kinetic card or floating badge that highlights key metrics, critical terminology, or phase turns extracted from scene narration.
_Avoid_: Popup text, floating badge, sticker, overlay label

**Incremental Conforming**:
A selective re-assembly technique that regenerates only modified scene assets while directly reusing cached intermediate clips for untouched scenes, updating a master 1080p video in seconds.
_Avoid_: Partial render, quick patch, fast bake

**Universal Text Replacement**:
A synchronized, cross-stage search and replace mechanism that atomically updates keywords and terminology across Stage 1 (Research), Stage 2 (Script), Stage 3 (Scenes), Stage 4 (Prompts), and Subtitles simultaneously to maintain absolute project semantic consistency.
_Avoid_: Global find-replace, multi-tab string edit, batch word change

**Text Outdated Invalidation**:
An automated dependency tracking state where modifying any scene's narration text marks its audio asset as pending and outdated (`text_outdated = True`), cascading into voice and subtitle pipeline stages so incremental conforming only re-synthesizes the affected audio clips.
_Avoid_: Dirty audio flag, stale voice tag, modified script mark

**Drama Formula**:
A structured narrative recipe defining a genre archetype, golden-ratio 3-beat rhythm (Hook, Tension, Payoff), premise guidelines, and a default cast template for short-form viral storytelling.
_Avoid_: Script prompt, drama preset, story template

**Character Roster**:
A project-bound and global ensemble specification containing normalized identity tags (`id`, `name`, `gender`, `role`), visual appearance prompts, voice profiles, and canonical turnaround face portraits.
_Avoid_: Actor list, cast sheet, character setting

**Proportional Scene Pacing**:
A dynamic storyboard allocation strategy where total shot count and narrative beat durations scale dynamically with total target video duration (15% Hook, 55% Tension, 30% Payoff, ~3.5s-5.0s per shot) rather than fixed-length scene cuts.
_Avoid_: Fixed 3-act cuts, static scene pacing, hardcoded shot counts

**Fail-Fast Quota Guard**:
An intentional pipeline halt policy that immediately halts video generation, flags the stage with a prominent warning, and prevents downstream asset degradation when external cloud GPU credits or API balance are depleted.
_Avoid_: Silent downgrade, invisible fallback, cheap avatar fallback

**Pre-flight Quota Check**:
A verification probe executed prior to dispatching GPU-heavy generation stages that queries provider balance endpoints, preventing the creation of partial or unfinishable video batches.

**World Setting Spec**:
A structured metadata specification generated during Stage 1 Research defining the temporal era, physical environmental conditions (e.g. war ruins vs pristine city), canonical interior/exterior architecture, and cast ensemble parameters across all scenes.
_Avoid_: Era notes, history prompt, background context

**Anachronism Guard**:
An automated prompt conditioning and negative constraint engine that purges chronologically impossible objects, modern infrastructure, and conflicting demographics from historical image generation prompts.
_Avoid_: Era filter, anti-modern prompt, negative check

**Footage Keyword Domain-Gating**:
A boundary enforcement mechanism ensuring real-world stock media search rules only evaluate within semantically matching topic classifications, preventing accidental substring collisions across unrelated genres.
_Avoid_: Regex isolation, keyword barrier, domain blacklist

**Smart World Setting Preservation**:
A non-destructive pipeline lifecycle policy ensuring user-edited historical constraints, architectural locations, and ensemble specs are preserved across Stage 1 re-runs while providing an on-demand reset mechanism to generate fresh AI suggestions.
_Avoid_: Config lock, freeze schema, sticky world setting
_Avoid_: Late credit check, runtime billing probe, mid-job balance test

**PRC Source Exclusion**:
A zero-tolerance source filtering and validation policy that automatically blocks, strips, and prevents the ingestion or citation of materials, websites, and data originating from the People's Republic of China (.cn domains, PRC state-controlled media, search engines, forums, content farms) or simplified Chinese texts, protecting documentary content from state-sponsored political propaganda and historical distortions.
_Avoid_: China block, domain ban, PRC filter, red list

**Taiwan Translation Names**:
The rigorous enforcement of Taiwan National Academy for Educational Research (國家教育研究院) and Ministry of Foreign Affairs (外交部) standard translation naming conventions and authentic Taiwanese Mandarin vocabulary across all project stages, replacing mainland Chinese transliterations (e.g. 歐巴馬 not 奧巴馬, 川普 not 特朗普, 柴契爾 not 撒切爾, 普丁 not 普京, 澤倫斯基 not 澤連斯基, 史達林 not 斯大林, 邱吉爾 not 丘吉爾, 賈伯斯 not 喬布斯, 晶片 not 芯片, 演算法 not 算法, 軟體 not 軟件).
_Avoid_: Taiwan words, Chinese conversion, localize terms

**Fact Validity Double-Check**:
A systematic post-research and pre-rendering verification subsystem that cross-examines documentary claims against verified Taiwanese academic institutions (e.g. 中央研究院, 國史館, 國家圖書館) and reputable international peer-reviewed consensus, outputting a structured validity score, claim-by-claim verdict (VERIFIED, DISPUTED, FALSE), and Taiwan-standard corrections while generating persistent JSON and Markdown reports.
_Avoid_: Truth check, fact probe, myth check

**Split-Angle Dialogue Cut**:
A visual pacing mechanism that automatically alternates camera sizes or angles (e.g. medium push-in to tight close-up) during an extended spoken line (>6.0s) while preserving continuous uninterrupted audio.
_Avoid_: Jump cut, audio split, sentence interruption

**Local Persona Mutation**:
The policy where character styling, wardrobe variations, and portrait takes altered within a specific project remain isolated to that project's snapshot unless explicitly published back to the global library.
_Avoid_: Global character auto-sync, uncontrolled asset mutation

**Visual Aesthetic Profile**:
A formula-level cinematic texture, color palette, lighting temperature, and camera rendering descriptor (e.g. sharp corporate glass vs warm golden luxury vs cold dystopian neon) injected into Stage 5 image prompting to preserve look-and-feel unity across all shots.
_Avoid_: Art style prompt, visual preset, image theme

**Master Anchor Reference**:
The canonical 9:16 full-body or medium-shot character portrait (`{char_id}_styled_9x16.png`) capturing approved face identity, hairstyle, lighting, and baseline wardrobe, serving as the master visual conditioning anchor across the entire production.
_Avoid_: Face template, base photo, profile pic

**Dual-Image Anchor Lock Conditioning**:
A Stage 5 image generation architecture where Gemini Image Generation is fed both the Master Anchor Reference (conditioned for wardrobe, fabric texture, and environment coherence) and Face Reference (conditioned for facial identity), combined with strict anatomical negative constraints.
_Avoid_: Single face swap, freeform diffusion, unanchored re-prompting

**Contextual Costume Variant**:
An explicit shot-level wardrobe override tag (`costume_variant`) enabling deliberate clothing changes (e.g. pajamas, hospital gown, tactical gear) only when specified in the screenplay, defaulting to `"default"` to lock wardrobe consistency.
_Avoid_: Random outfit variation, costume drift, unmanaged dress change

**Primary Setting Anchor**:
The default architectural and environmental space profile derived from the drama formula and story premise (e.g. high-rise CEO office, modern police interrogation room) that binds background scenes across the video episode.
_Avoid_: Random background, floating location, prompt backdrop

**Narrative Movement**:
A distinct emotional and thematic musical phase within a documentary timeline (such as Opening Context, Deep Tension, or Climax Resolution) mapped to script chapters and paced dynamically across the video.
_Avoid_: Music clip, audio chunk, BGM cut, loop segment

**Ambient Music Stage**:
A dedicated pipeline inspection and tuning stage in Documentary Stage Studio situated prior to final video rendering that analyzes narration pacing, selects and crossfades multi-movement tracks, and exposes audio audition controls.
_Avoid_: BGM setting, audio tab, music toggle, render option

**Music Vibe Profile**:
A multi-dimensional acoustic classification encompassing narrative genre, emotional valence, pacing tempo, and instrumentation texture, governing how audio atmosphere is mapped to video themes.
_Avoid_: Music tag, sound label, audio type, song category

**Sonic Grounding**:
The semantic alignment process that analyzes script dramatic tone, research topic, and chapter sentiment to select harmonized musical tracks from the catalog, preventing tonal mismatch and acoustic dissonance.
_Avoid_: Folder shuffle, hash pick, random BGM, generic track choice

**Batch Track Ingestion**:
The concurrent uploading and automatic catalog indexing of multiple audio assets into designated vibe folders with instantaneous metadata enrichment.
_Avoid_: Bulk song drop, mass upload, loose audio dump

**Tactile Blueprint Aesthetic**:
A documentary visual language combining dark slate technical grids, SVG path drawing strokes, paper cutout drop shadows with subtle rotational imperfection, and high-contrast kinetic typography with vibrant telemetry accents.
_Avoid_: SaaS card UI, flat corporate slide, generic glassmorphism

**Branch Pathway Graphic**:
A documentary motion graphic archetype visualizing competing technical routes, historical lineages, or strategic choices through branching SVG nodes, highlighting the chosen path while dimming or crossing out alternatives.
_Avoid_: Comparison table, split box, VS card

**Leader Callout Graphic**:
A high-precision technical motion graphic that animates an origin anchor point, an elbow connecting line, and a floating telemetry badge pointing to anatomical layers or mechanical components on an underlying image.
_Avoid_: Arrow pointer, popup badge, floating text box

**Scale Loupe Comparison**:
A dual-tier visual benchmark graphic that pairs microscopic elements against macroscopic everyday objects with an animated metric ruler to convey extreme proportions and precision.
_Avoid_: Simple stat bar, ratio card, size table

**Evidence Document Highlight**:
An investigative motion graphic displaying an archival patent, paper clipping, or official record with a dynamic highlighter ink sweep across crucial phrases.
_Avoid_: Text zoom, quote box, highlighted subtitle

**Motion Graphic Director**:
A dedicated semantic analysis stage where an LLM inspects script chapters to identify high-cognitive-load explanatory beats, choosing appropriate visual archetypes and populating structured coordinate and comparison props.
_Avoid_: Regex keyword trigger, metric card picker, random graphic generator

**Two-Pass Motion Graphic Lifecycle**:
An orchestration architecture where narrative intent and structured props are authored during Stage 3 Storyboarding, then exact audio-duration frame counts and background image paths are conformed during Stage 8 Animation rendering.
_Avoid_: Runtime generation, late script generation, uncoupled animation rendering

**Three-Phase Dramatic Progression**:
A structured Remotion animation timeline divided into Staggered Entrance (0–30%), Elimination & Selection (30–65%), and Focused Telemetry Zoom (65–100%) to build narrative tension in documentary motion graphics.
_Avoid_: Static card display, linear fade-in, single-state diagram

**Normalized Anchor Coordinate**:
A relative coordinate pair $(x, y) \in [0.1, 0.9]$ specifying visual feature focal points on background images, accompanied by deterministic golden-ratio fallback slots when coordinates are unspecified.
_Avoid_: Pixel coordinates, absolute offsets, floating alignment

**Documentary Style Gallery**:
A centralized configuration and audition interface situated in Global Settings and Stage Studio that allows creators to select, audition, and override default motion graphic archetypes with live Remotion preview cards.
_Avoid_: Card picker, theme selector, template tab

**Celebrity Portrait Grounding**:
The automated pipeline mechanism that identifies real-world historical, political, scientific, and corporate figures from documentary narration, resolving their canonical international identities and binding authentic biographical infobox or Wikimedia portraits into scene media assets rather than synthetic diffusion imagery.
_Avoid_: Celebrity face swap, deepfake portrait, generic AI avatar, hallucinated face generation

**Wikipedia Infobox Resolver**:
A zero-key biographical image retrieval probe querying the Wikipedia Page Summary API to fetch curated, high-resolution public domain biographical portraits and infobox photography for verified public figures.
_Avoid_: Google web scrape, Bing image scraper, random photo crawler

**Classical Work Catalog**:
A structured directory of public domain classical music compositions and metadata (composers, epochs, genres, movements) referenced from OpenOpus.
_Avoid_: Classical playlist, opus table, piece list

**OpenOpus Metadata Provider**:
The external REST service interface querying classical composer biographies, epoch breakdowns, catalogs of works, and movement indices.
_Avoid_: Music API, classical backend, opus scraper

**Audio Fulfillment Provider**:
The resolver service responsible for pairing abstract OpenOpus work metadata with playable, copyright-cleared audio recordings for in-app preview and FFmpeg soundtrack rendering.
_Avoid_: Music downloader, mp3 fetcher, audio link grabber

**Epoch-to-Vibe Mapper**:
The deterministic translation heuristic converting classical epoch and instrumentation metadata into video narrative atmosphere categories and movement energy tiers.
_Avoid_: Style converter, classical tagger, genre translator

**Work Ingestion Snapshot**:
A catalog record combining OpenOpus opus metadata with local file audio descriptors (sample rate, duration, volume normalization) registered in the music catalog.
_Avoid_: Music entry, track row, cached audio item

**Start Offset**:
A designated timestamp (in seconds or mm:ss) into an audio track from which FFmpeg begins extraction, allowing iconic musical passages located mid-composition to align with video narrative movements.
_Avoid_: Audio seek time, track start trim, cut beginning

**Public Domain Audio Resolver**:
An automated background service querying the Internet Archive and Wikimedia Commons APIs for zero-key, copyright-cleared classical audio recordings matching composer and opus metadata.
_Avoid_: MP3 crawler, audio scraper, torrent fetcher

**Movement Bed**:
A continuous, progression-based background music segment mapped across an entire narrative movement (e.g., Exposition, Deep Dive, Resolution), crossfading smoothly at movement chapter boundaries.
_Avoid_: BGM track, audio background, music loop

**Acoustic Carpet**:
An unobtrusive musical texture with soft transients, muted high-mids, and minimal melodic presence, engineered specifically to fill room silence without competing with speech comprehension.
_Avoid_: Filler sound, background noise, ambient bed

**Track Fitness Score**:
A structured, calibrated judgment rating (such as evaluated via TypeSafe AI System One models) that grades an audio track's cognitive non-intrusiveness and suitability for high-density voiceover content.
_Avoid_: Music rating, song score, BGM rank

**Epic Chronicle Mural Style**:
A visual style preset (`epic_chronicle_mural`) characterized by dense, textured digital impasto oil painting, fine art narrative illustration, rich mineral earth palettes accented with vermilion, and a unified single-subject focal hierarchy, decoupled from mandatory historical era constraints.
_Avoid_: Split-screen collage, multi-panel vignettes, flat comic borders, anime, glossy 3D CGI render

**Frequency Masking Gate**:
An automated filter rule and dynamic spectral carving that detects and attenuates background music energy in the human voice intelligibility band (800 Hz - 3.5 kHz) to prevent vocal competition.
_Avoid_: Audio ducker, sound dip, vocal clash check
