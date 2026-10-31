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
