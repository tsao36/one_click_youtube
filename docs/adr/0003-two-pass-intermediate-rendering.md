# 0003. Two-Pass Intermediate Clip Caching for Video Assembly

## Status
Accepted

## Context
Rendering a long-form 40+ scene video using a single monolithic FFmpeg filtergraph (decoding all raw PNGs, panning/zooming, applying complex transition matrixes, mixing audio tracks, and burning subtitles in one command) frequently causes out-of-memory crashes, uninterpretable filter graph syntax errors, and zero tolerance for single-scene glitches. Furthermore, modifying any single scene requires re-rendering the entire video from scratch.

## Decision
We decouple video assembly into a robust two-pass intermediate cached pipeline:
1. **Pass 1 (Per-Scene Normalization & Caching)**: Each scene is rendered into an independent, normalized 1080p 30fps H.264 MP4 intermediate clip (`animation/scene_001.mp4`). Each clip is fingerprinted by a cache key (`_clip_key`) hashing image source, animation type, motion parameters, and duration.
2. **Pass 2 (Parallel Transition Joining & Master Mix)**: A multi-threaded transition engine joins the normalized intermediate clips using pairwise `xfade` filters (executed with 8 parallel worker threads using `-preset ultrafast`), then burns ASS subtitles and mixes the master ducked audio track.

## Consequences
- **Benefits**: Unprecedented crash resilience (a failure in scene 35 does not ruin scenes 1-34). Near-instantaneous fast re-renders (replacing one scene only re-renders that single intermediate clip, while the other 39 scenes hit cache).
- **Trade-offs**: Consumes additional temporary disk space for intermediate MP4 files, which are automatically cleaned or retained in the project's working directory.
