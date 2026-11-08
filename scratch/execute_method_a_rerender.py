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
print(f"=== Starting Method A Re-render for {project_id} ===")

# -------------------------------------------------------------
# 1. Update narration in p.scenes with verified fact-checked text
# -------------------------------------------------------------
new_nar_s1 = "藍芽 7.0 HDT 這次直接把速度拉到 7.5 Mbps，比過去快上 3.75 倍，無損音訊、穿戴裝置都要被顛覆了！"
p.scenes[1].narration = new_nar_s1

new_nar_s3 = "無損音訊和大量資料傳輸變得困難。到了藍芽 6.0，雖然導入了 Channel Sounding 測距技術，但 PHY 速度仍為 2 Mbps，但還是無法真正解決頻寬不足的問題。"
p.scenes[3].narration = new_nar_s3

p.save_scenes()
p.save()

# -------------------------------------------------------------
# 2. Re-synthesize Voice via Pipeline
# -------------------------------------------------------------
pipeline = get_pipeline(p)
print("\n--- [Stage 6: Voice] Synthesizing updated narrations ---")
t_v0 = time.perf_counter()
pipeline._run_voice()
print(f"Voice synthesis complete in {time.perf_counter() - t_v0:.1f}s!")

dur_s1 = p.scenes[1].audio_duration or p.scenes[1].audio.meta.get("duration", 10.7)
dur_s2 = p.scenes[2].audio_duration or p.scenes[2].audio.meta.get("duration", 10.0)
dur_s3 = p.scenes[3].audio_duration or p.scenes[3].audio.meta.get("duration", 13.0)

print(f"Scene 1 audio duration: {dur_s1:.2f}s")
print(f"Scene 2 audio duration: {dur_s2:.2f}s")
print(f"Scene 3 audio duration: {dur_s3:.2f}s")

# -------------------------------------------------------------
# 3. Update motion_graphics.json for Scenes 1, 2, 3
# -------------------------------------------------------------
mg_path = p.path("scenes", "motion_graphics.json")
mg_data = json.load(open(mg_path, "r", encoding="utf-8"))

# Scene 1 (motion-002, scene_id 2):
s1_mg = mg_data["scenes"][1]
s1_mg["props"]["subtitle"] = "從 2 Mbps 到 7.5 Mbps 的技術躍進 (提升近 4 倍)"
s1_mg["props"]["pillars"][0]["subtitle"] = "7.5 Mbps (較 2M 提升近 4 倍)"
s1_mg["durationInFrames"] = max(30, int(round(dur_s1 * 30)))

# Scene 2 (motion-003, scene_id 3):
s2_mg = mg_data["scenes"][2]
s2_mg["props"]["pillars"][1]["title"] = "藍芽 6.0"
s2_mg["props"]["pillars"][1]["subtitle"] = "Channel Sounding 測距"
s2_mg["props"]["pillars"][1]["metric"] = "2 Mbps"
s2_mg["props"]["pillars"][1]["points"] = ["高精度測距", "實體層維持 2 Mbps", "頻寬瓶頸未解"]
s2_mg["durationInFrames"] = max(30, int(round(dur_s2 * 30)))

# Scene 3 (motion-004, scene_id 4):
s3_mg = mg_data["scenes"][3]
s3_mg["props"]["leftBadge"] = "藍芽 6.0"
s3_mg["props"]["leftTitle"] = "實體層速度 2 Mbps"
s3_mg["props"]["leftContent"] = "導入 Channel Sounding 測距，但實體層速度仍為 2 Mbps"
s3_mg["props"]["leftTags"] = ["Channel Sounding", "PHY 2 Mbps", "頻寬瓶頸"]
s3_mg["durationInFrames"] = max(30, int(round(dur_s3 * 30)))

with open(mg_path, "w", encoding="utf-8") as f:
    json.dump(mg_data, f, ensure_ascii=False, indent=2)
print("Updated motion_graphics.json for scenes 1, 2, 3 successfully.")

# -------------------------------------------------------------
# 4. Re-render Remotion clips for scenes 1, 2, 3
# -------------------------------------------------------------
print("\n--- [Stage 8: Animation] Re-rendering updated Remotion clips ---")
for idx in [1, 2, 3]:
    sc = p.scenes[idx]
    mg = mg_data["scenes"][idx]
    out_clip = p.path("animation", f"{sc.tag}.mp4")
    print(f"Rendering Remotion clip for Scene {sc.scene_id} ({sc.tag}) -> {mg['sceneType']} ({mg['durationInFrames']} frames)...")
    t_c0 = time.perf_counter()
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
    print(f"Scene {sc.scene_id} rendered in {time.perf_counter() - t_c0:.1f}s!")

p.save_scenes()
p.save()

# -------------------------------------------------------------
# 5. Re-plan Background Music (using improved algorithm)
# -------------------------------------------------------------
print("\n--- [Stage 8: Music] Planning new background music timeline ---")
p.stage("music").status = Status.PENDING
pipeline._run_music()
music_file = p.path("audio", "music.json")
if music_file.exists():
    m_info = json.load(open(music_file, "r", encoding="utf-8"))
    print("Music Timeline Planned:")
    for seg in m_info.get("segments", []):
        print(f"  {seg.get('name')} ({seg.get('category')}) from {seg.get('start_time')}s to {seg.get('end_time')}s")

# -------------------------------------------------------------
# 6. Re-generate Subtitles
# -------------------------------------------------------------
print("\n--- [Stage 9: Subtitles] Generating updated subtitles ---")
p.stage("subtitles").status = Status.PENDING
pipeline._run_subtitles()
print("Subtitles generated successfully.")

# -------------------------------------------------------------
# 7. Render Final MP4 Video
# -------------------------------------------------------------
print("\n--- [Stage 10: Render] Joining scenes into final MP4 ---")
t_r0 = time.perf_counter()
p.stage("render").status = Status.PENDING
pipeline._run_render()
print(f"Final render completed in {time.perf_counter() - t_r0:.1f}s!")

final_mp4 = p.path("final", f"{project_id}.mp4")
print(f"\n=======================================================")
print(f"=== SUCCESS! Final Video Generated: {final_mp4}")
print(f"=== File Size: {final_mp4.stat().st_size / (1024*1024):.2f} MB")
print(f"=======================================================")
