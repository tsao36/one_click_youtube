# 0001. Audio-Driven Timeline Architecture

## Status
Accepted

## Context
Video creation tools traditionally establish a visual timeline first (e.g. fixed 5-second video durations per slide) and fit narration audio via padding, cutting, or time-stretching. In synthetic explainer videos, narration clarity and natural human speech cadence are the highest priority; artificial audio stretching creates robotic artifacts, while fixed slide timings frequently clip sentences.

## Decision
We establish narration speech duration (`Scene.audio_duration`) measured post-TTS synthesis as the single source of truth for the entire pipeline timeline.

All downstream stages dynamically derive their timings from the audio duration:
1. **Stage 7 (Animation & Presenter)**: Video generation, Ken Burns pan/zoom, and LatentSync lip-sync conform exactly to the scene's audio length.
2. **Stage 8 (Subtitles)**: Word and sentence timestamps are computed directly against the audio track boundaries.
3. **Stage 9 (Final Render)**: FFmpeg concatenates scenes using transition offsets calculated from cumulative audio track timestamps.

## Consequences
- **Benefits**: Perfect voice intelligibility with zero robotic pitch-shifting or cadence distortion. Subtitles and mouth movements remain frame-accurate.
- **Trade-offs**: Total video duration and individual scene lengths cannot be predetermined prior to Stage 4 (Voice Synthesis). Any edit to narration script requires invalidating downstream audio, lip-sync clips, and subtitles.
