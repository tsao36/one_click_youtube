import json
import logging
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from core.project_manager import Project
from core.models import Status
from core.pipeline import get_pipeline
from generators.motion_graphics_renderer import render_motion_graphic_clip

project_id = "bluetooth_7_0_high_data_2"
p = Project(project_id)
print(f"=== Updating Conclusion Scenes for {project_id} ===")

mg_path = p.path("scenes", "motion_graphics.json")
mg_data = json.load(open(mg_path, "r", encoding="utf-8"))

# 1. Update subtext to "結論" for all conclusion scenes
conclusion_indices = [34, 35, 36, 37, 38]
for idx in conclusion_indices:
    s = mg_data["scenes"][idx]
    s["props"]["subtext"] = "結論"
    print(f"Scene {s['scene_id']} props updated: badge='{s['props']['badge']}', subtext='{s['props']['subtext']}'")

with open(mg_path, "w", encoding="utf-8") as f:
    json.dump(mg_data, f, ensure_ascii=False, indent=2)

print("Saved updated motion_graphics.json.")

# 2. Re-render Remotion clips for scenes 35-39
print("\n--- Re-rendering Remotion clips for Conclusion scenes ---")
for idx in conclusion_indices:
    mg = mg_data["scenes"][idx]
    sc = p.scenes[idx]
    out_clip = p.path("animation", f"{sc.tag}.mp4")
    print(f"Rendering Remotion clip for Scene {sc.scene_id} ({sc.tag}) -> {mg['sceneType']} ({mg['durationInFrames']} frames)...")
    t0 = time.perf_counter()
    render_motion_graphic_clip(
        scene_type=mg["sceneType"],
        props=mg["props"],
        out_path=out_clip,
        duration_frames=mg["durationInFrames"],
        use_gpu_gl=True
    )
    sc.animation.status = Status.COMPLETED
    sc.animation.path = f"animation/{sc.tag}.mp4"
    sc.animation.meta = {"provider": "remotion", "scene_type": mg["sceneType"]}
    print(f"Scene {sc.scene_id} rendered in {time.perf_counter() - t0:.1f}s!")

p.save_scenes()
p.save()

# 3. Re-run Final Render (Assembly)
print("\n--- Joining scenes into final MP4 ---")
pipeline = get_pipeline(p)
t_r0 = time.perf_counter()
p.stage("render").status = Status.PENDING
pipeline._run_render()
print(f"Final render completed in {time.perf_counter() - t_r0:.1f}s!")

final_mp4 = p.path("final", f"{project_id}.mp4")
print(f"\n=======================================================")
print(f"=== SUCCESS! Final Video Re-rendered: {final_mp4}")
print(f"=== File Size: {final_mp4.stat().st_size / (1024*1024):.2f} MB")
print(f"=======================================================")
