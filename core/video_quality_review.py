"""Post-render technical and AI-assisted quality checks for project videos."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.ffmpeg import ffmpeg_bin, probe
from providers.llm import LLMClient


def _validate_review(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        raise ValueError("Review must include a findings list")
    for item in data["findings"]:
        if not isinstance(item, dict) or not isinstance(item.get("title"), str):
            raise ValueError("Each finding must include a title")
        item.setdefault("severity", "info")
        item.setdefault("detail", "")
        item.setdefault("timestamp_seconds", None)
    return data


def review_rendered_video(project) -> dict[str, Any]:
    final_rel = (project.data.outputs or {}).get("final") or f"final/{project.id}.mp4"
    video_path = project.path(final_rel)
    if not video_path.is_file() and (project.data.outputs or {}).get("external_archive_path"):
        video_path = Path(project.data.outputs["external_archive_path"])
    if not video_path.is_file():
        raise FileNotFoundError("Rendered video file was not found")

    media = probe(video_path)
    streams = media.get("streams", [])
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    duration = float((media.get("format") or {}).get("duration") or 0)
    checks = [
        {"title": "Video stream", "status": "pass" if video_streams else "fail",
         "detail": f"{len(video_streams)} video stream(s) found."},
        {"title": "Audio stream", "status": "pass" if audio_streams else "fail",
         "detail": f"{len(audio_streams)} audio stream(s) found."},
    ]

    silence_count = black_count = None
    if audio_streams and video_streams:
        cmd = [ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(video_path),
               "-vf", "blackdetect=d=2:pix_th=0.10",
               "-af", "silencedetect=noise=-45dB:d=3", "-f", "null", "-"]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=max(120, int(duration * 2) if duration else 120),
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log_text = proc.stderr or ""
        silence_count = len(re.findall(r"silence_start:", log_text))
        black_count = len(re.findall(r"black_start:", log_text))
        checks.extend([
            {"title": "Prolonged silence", "status": "warning" if silence_count else "pass",
             "detail": f"Detected {silence_count} silence interval(s) of at least 3 seconds; music-only sections may be intentional."},
            {"title": "Black frames", "status": "warning" if black_count else "pass",
             "detail": f"Detected {black_count} black interval(s) of at least 2 seconds; intentional fades may be included."},
        ])

    scenes = [s for s in project.active_scenes()]
    expected_narration = "\n".join(f"Scene {s.scene_id}: {s.narration}" for s in scenes)
    transcript = ""
    transcript_note = "Speech transcription unavailable; install/start the configured local CosyVoice Whisper service to check spoken words."
    if audio_streams:
        try:
            with tempfile.TemporaryDirectory(prefix="video-quality-") as temp_dir:
                wav_path = Path(temp_dir) / "rendered_audio.wav"
                subprocess.run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_path),
                                "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav_path)],
                               check=True, capture_output=True, timeout=max(120, int(duration * 2) if duration else 120),
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                from providers.tts import CosyVoiceTTS
                transcript = CosyVoiceTTS.transcribe(str(wav_path))
                transcript_note = "Rendered audio transcribed with the local CosyVoice Whisper service."
        except Exception as exc:
            transcript_note = f"Speech transcription unavailable: {str(exc)[:240]}"

    provider = (project.settings.get("stage_models") or {}).get("script_review")
    client = LLMClient("script_review", provider_override=provider, project_id=project.id)
    ai = client.json(
        json.dumps({"topic": project.data.topic, "duration_seconds": duration,
                    "intended_narration": expected_narration[:18000],
                    "transcribed_rendered_audio": transcript[:18000],
                    "audio_transcription_status": transcript_note,
                    "audio_stream_count": len(audio_streams),
                    "narration_speaker_labels": sorted({str(getattr(s, "speaker", "") or "Narrator") for s in scenes}),
                    "audio_channels": [s.get("channels") for s in audio_streams]}, ensure_ascii=False),
        system=("You are reviewing a rendered video's speech using the intended narration and an ASR transcript. "
                "The transcript is only a recognizer hypothesis, not ground truth for what was spoken. Compare the "
                "pronunciation implied by each transcript phrase with the intended narration, not the Chinese "
                "characters or spelling. Do not report a mismatch when the phrases are homophones or close enough "
                "in pronunciation that the ASR could reasonably have chosen the other characters (for example, "
                "韌性/任性, 新詩/新師, 財源/裁員, 期程/其成, or 健檢/漸減). Those are transcript spelling "
                "differences, not evidence of an audio problem. Emit a warning only for a meaning-changing phrase "
                "whose spoken sounds materially differ, such as 八年 versus 二年, or for a clear omission, addition, "
                "repetition, or unintelligible section that the transcript supports. When uncertain whether a mismatch "
                "is phonetic or ASR-only, omit it rather than warn. An empty findings array is appropriate when all "
                "differences are homophones or otherwise unsupported. Give approximate timestamp_seconds for each "
                "actionable finding. Do not invent visual or speaker-diarization observations; no video frames are "
                "provided and the transcript is not speaker-labeled. Return JSON with findings: an array of {title, "
                "severity (critical|warning|info), detail, timestamp_seconds (number or null)}. Also check whether "
                "the narration speaker labels imply an unexpected speaker change, while clearly separating that "
                "metadata check from identifying actual voices."),
        temperature=0.1, max_tokens=2500, validate=_validate_review,
    )
    speaker_labels = {str(getattr(s, "speaker", "") or "Narrator") for s in scenes}
    checks.append({"title": "Speaker labels", "status": "warning" if len(speaker_labels) > 1 else "info",
                   "detail": (f"Project metadata contains {len(speaker_labels)} speaker labels; actual voice count cannot be confirmed by this review." if len(speaker_labels) > 1 else
                              "Actual speaker count cannot be verified automatically by the available speech recognizer.")})
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "video_filename": video_path.name,
              "duration_seconds": round(duration, 2), "checks": checks, "findings": ai["findings"],
              "transcript": transcript, "transcript_status": transcript_note,
              "suggested_manual_checks": ["Confirm there is only one intended voice throughout (speaker diarization is unavailable).",
                                          "Check subtitle timing and clipping at scene transitions.",
                                          "Inspect visual continuity, awkward crops, and text overlays.",
                                          "Listen for clipped peaks, abrupt edits, and music masking narration."],
              "metadata": {"model": getattr(client.provider, "model", ""), "duration_seconds": duration,
                           "audio_stream_count": len(audio_streams), "video_stream_count": len(video_streams),
                           "silence_intervals": silence_count, "black_intervals": black_count}}
    project.write_json("final/quality_review.json", report)
    return report
