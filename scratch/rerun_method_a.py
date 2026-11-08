import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from core.project_manager import Project
from core.models import Status
from core.pipeline import get_pipeline

project_id = "bluetooth_7_0_high_data_2"
p = Project(project_id)

print(f"=== Priming {project_id} for 100% Gary Chen Remotion ===")

# 1. Update project settings
p.data.settings["presenter_placement"] = "none"
p.data.settings["auto_presenter"] = False
p.data.settings["avatar_enabled"] = False
p.data.settings.setdefault("animation", {})["motion_graphics_density"] = "full"
p.data.settings["animation"]["ai_video_percentage"] = 0.0
p.data.settings["remotion"] = {
    "style": "modern_tech_explainer",
    "theme": "dark_obsidian",
    "density": "full",
    "accentColor": "#38BDF8"
}
p.data.settings.setdefault("stage_models", {})["animation"] = "remotion"

# 2. Reset scenes so all 39 scenes get re-planned and rendered with Remotion
for s in p.scenes:
    s.is_presenter = False
    if s.visual_type == "talking_head":
        s.visual_type = "image"
    s.animation.status = Status.PENDING
    s.animation.path = None
    s.animation.meta = {}
    s.animation.error = None

p.save_scenes()
p.save()
print(f"Project settings primed: density=full, presenter_placement=none, total_scenes={len(p.scenes)}")

# 3. Instantiate DocumentaryPipeline and run animation + render
pipeline = get_pipeline(p)

print("\n--- Running Stage 8: Animation (100% Remotion) ---")
pipeline.run_stage("animation")

print("\n--- Running Stage 10: Render Final Video ---")
pipeline.run_stage("render")

final_mp4 = p.path("final", f"{project_id}.mp4")
print(f"\n=== FINISHED! Final Video: {final_mp4} (exists={final_mp4.exists()}, size={final_mp4.stat().st_size if final_mp4.exists() else 0} bytes) ===")
