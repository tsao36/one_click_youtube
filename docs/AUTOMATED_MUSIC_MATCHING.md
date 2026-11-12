# Automated background-music matching

Stage 7 now treats soundtrack creation as a constrained sequence-optimization
problem rather than choosing one track from a topic label.

## Runtime flow

1. Group adjacent scenes into meaningful narrative movements.
2. Infer a `MusicIntent` for every movement: energy, tension, cognitive load,
   rhythm tolerance, and a short synopsis.
3. Remove tracks that fail vocal, distraction, voiceover-readiness, file, or
   licence gates.
4. Score the safe library for semantic fit, style, energy, speech clarity,
   cognitive fit, loopability, and recent-use penalty.
5. If TypeSafe is configured, re-rank only the top five safe candidates for
   each movement. If it is unavailable, continue with deterministic scores.
6. Use dynamic programming to select the best complete sequence, including
   transition coherence and repetition costs.
7. Persist the backward-compatible `music/music_plan.json`, with extra intent,
   score, confidence, and selection-mode fields.
8. Persist `music/music_plan_qa.json`. The renderer validates an existing plan
   again and regenerates invalid plans before mixing.
9. If no licensed, voiceover-safe track exists, render narration without music.

## Settings

The behavior is automatic with existing projects. Optional music settings are:

```json
{
  "music": {
    "enabled": true,
    "autonomous_matching": true,
    "typesafe_rerank": true,
    "typesafe_timeout": 8,
    "style": "ambient",
    "volume_db": -24,
    "ducking": true
  }
}
```

`typesafe_rerank` is opportunistic: it is used when a key is configured and is
never required to finish a video. An explicit track choice still wins for a
single-movement video.

## Preparing the library

Run the catalog grader after importing tracks:

```powershell
.\.venv\Scripts\python.exe scripts\grade_music_catalog.py --force
```

The grader extracts duration, loudness, dynamic range, one-second energy curve,
energy slope, transient density, zero-crossing rate, and a conservative
speech-band-risk proxy. It uses TypeSafe when configured and otherwise applies
the deterministic offline safety grader. Add `--strict-typesafe` only when a
missing semantic service should fail the command.

The system cannot guarantee a mathematically perfect artistic match. Its
zero-touch guarantee is operational: it always produces a safe plan or an
intentional voice-only fallback, without waiting for a human choice.
