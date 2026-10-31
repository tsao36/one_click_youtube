import sys, os, json
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

from agents.scene_planner import detect_real_world_footage_target

with open('projects/project_2/scenes/scenes.json', 'r', encoding='utf-8') as f:
    scenes = json.load(f)

with open('projects/project_2/project.json', 'r', encoding='utf-8') as f:
    proj = json.load(f)

topic = proj.get("topic", "")
print("Project Topic:", topic)

matched = 0
for s in scenes:
    kw, src = detect_real_world_footage_target(s.get("narration", ""), s.get("visual_description", ""), mode="balanced", topic=topic)
    if kw:
        matched += 1
        print(f"Scene {s['scene_id']:02d}: '{kw}' -> {src}")

print(f"\nTotal real-media matched scenes: {matched} / {len(scenes)}")
