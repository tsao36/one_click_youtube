"""Test narrative-adaptive dynamic background music planning and audio mixing."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from core.project_manager import Project
from generators.music import plan_music_timeline
from rendering.transitions import Slot, total_length
from rendering.ffmpeg_renderer import project_timeline, build_audio_mix

project = Project("robot_foundation_models_also_called")
scenes, slots = project_timeline(project)
total = total_length(slots)

chap_file = project.path("scenes/chapters.json")
chapters = json.loads(chap_file.read_text(encoding="utf-8")) if chap_file.exists() else None

print(f"[*] Project ID: {project.id}, Total Duration: {total:.2f}s, Scenes: {len(scenes)}")

# 1. Plan music timeline
plan = plan_music_timeline(
    directory="data/music",
    key=project.id,
    preferred="auto",
    topic=project.data.topic,
    total_duration=total,
    scenes=scenes,
    slots=slots,
    chapters=chapters,
    music_settings=project.data.settings.get("music", {}),
)

print(f"[*] Music plan generated with {len(plan)} segment(s):")
for idx, seg in enumerate(plan, 1):
    print(f"  Segment {idx}: '{seg.name}' ({seg.category}) | {seg.start_time:.1f}s -> {seg.end_time:.1f}s (fade_in: {seg.crossfade_in}s, fade_out: {seg.crossfade_out}s, vol: {seg.volume_db}dB)")

assert len(plan) == 2, f"Expected 2 segments for dynamic music, got {len(plan)}"
assert plan[1].start_time > 200.0, f"Expected transition in late video, got {plan[1].start_time}"
assert plan[1].category == "uplifting_inspirational", f"Expected uplifting_inspirational ending vibe, got {plan[1].category}"

# 2. Build test audio mix
out_mix = Path("scratch/test_dynamic_music_mix.wav")
narration_path = project.path("temp/narration.wav")
if not narration_path.exists():
    from rendering.ffmpeg_renderer import build_narration
    print("[*] Generating narration track via build_narration...")
    narration_path.parent.mkdir(parents=True, exist_ok=True)
    build_narration(project, scenes, slots, narration_path)

print(f"[*] Testing build_audio_mix with dynamic multi-track music...")
info = build_audio_mix(project, narration_path, total, out_mix, scenes=scenes, slots=slots)
print(f"[OK] Mix completed! Info: {info}")
print(f"[OK] Output file exists: {out_mix.exists()}, size: {out_mix.stat().st_size if out_mix.exists() else 0} bytes")
