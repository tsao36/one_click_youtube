import sys, os, json
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

with open('projects/project_2/scenes/scenes.json', 'r', encoding='utf-8') as f:
    scenes = json.load(f)

with open('projects/project_2/project.json', 'r', encoding='utf-8') as f:
    proj = json.load(f)

topic = proj.get("topic", "")
print("Project Topic:", topic)

# Simulate expanded pattern matching
patterns = [
    (r"(?:沈柏洋|沈伯洋|Puma Shen)", "Puma Shen", "wikimedia"),
    (r"(?:黑熊學院|Kuma Academy)", "Kuma Academy Puma Shen", "wikimedia"),
    (r"(?:黃國昌)", "黃國昌", "wikimedia"),
    (r"(?:立法院|國會議場|立法院議場)", "立法院議場", "wikimedia"),
    (r"(?:行政院)", "行政院", "wikimedia"),
    (r"(?:五分埔)", "Wufenpu Taipei", "wikimedia"),
    (r"(?:臺大|國立臺灣大學|台大)", "National Taiwan University", "wikimedia"),
]

import re

matched_count = 0
for s in scenes:
    narr = s.get("narration", "")
    vdesc = s.get("visual_description", "")
    comb = f"{narr} {vdesc}"
    matched_target = None
    for pat, q, src in patterns:
        if re.search(pat, comb):
            matched_target = (q, src)
            break
    if matched_target:
        matched_count += 1
        print(f"Scene {s['scene_id']:02d}: matched '{matched_target[0]}' ({matched_target[1]}) | Text: {narr[:40]}")

print(f"\nTotal matched scenes: {matched_count} / {len(scenes)}")
