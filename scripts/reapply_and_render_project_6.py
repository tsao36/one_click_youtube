"""Re-apply TypeSafe AI music plan and render project_6."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.logging_setup import log
from core.models import Status
from core.project_manager import Project
from core.documentary_pipeline import DocumentaryPipeline
from generators.music import plan_music_timeline
from rendering.ffmpeg_renderer import project_timeline, render_project
from rendering.transitions import total_length

def main():
    print("Loading project_6...")
    p = Project("project_6")
    scenes, slots = project_timeline(p)
    total = total_length(slots)
    m = p.settings.get("music", {})
    pref = p.settings.get("music_preference") or m.get("track")
    topic = p.data.topic

    chapters = None
    chap_file = p.path("scenes/chapters.json")
    if chap_file.exists():
        chapters = json.loads(chap_file.read_text(encoding="utf-8"))

    context_text = ""
    scr_file = p.path("script/script.md")
    if scr_file.exists():
        context_text = scr_file.read_text(encoding="utf-8")[:1200]

    print(f"Generating TypeSafe AI music timeline for '{topic}' ({total:.1f}s)...")
    new_plan = plan_music_timeline(
        directory=m.get("directory", "data/music"),
        key=p.id,
        preferred=pref,
        topic=topic,
        context_text=context_text,
        total_duration=total,
        scenes=scenes,
        slots=slots,
        chapters=chapters,
        music_settings=m,
    )

    plan_dicts = [seg.to_dict() for seg in new_plan]
    plan_file = p.path("music/music_plan.json")
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(json.dumps(plan_dicts, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nSaved new TypeSafe AI music plan to music/music_plan.json:")
    for i, seg in enumerate(new_plan, 1):
        print(f"  Movement {i}: {seg.name} ({seg.start_time:.1f}s -> {seg.end_time:.1f}s) | Cat: {seg.category}")

    p.set_stage("music", Status.COMPLETED, done=1, total=1)
    p.save()

    print("\nStarting video render with new DSP mastering chain...")
    pipe = DocumentaryPipeline(p)
    pipe.run_stage("render")
    
    mp4_path = p.path("final/project_6.mp4")
    if not mp4_path.exists():
        mp4_path = p.path("final/final.mp4")

    print(f"\nRender completed successfully!")
    print(f"Output video: {mp4_path} ({round(mp4_path.stat().st_size / (1024*1024), 2)} MB)")

if __name__ == "__main__":
    main()
