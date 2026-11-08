import json
import re

research_file = "projects/bluetooth_7_0_high_data_2/research/research.json"
script_file = "projects/bluetooth_7_0_high_data_2/script/script.json"

with open(research_file, "r", encoding="utf-8") as f:
    res = json.load(f)

with open(script_file, "r", encoding="utf-8") as f:
    scr = json.load(f)

print("Topic:", scr.get("topic"))
for sec in scr.get("sections", []):
    print(f"--- Section: {sec.get('name')} ---")
    txt = sec.get("text", "")
    # Find sentences with numbers or versions
    sentences = [s.strip() for s in re.split(r"[。！？\n]+", txt) if s.strip()]
    for s in sentences:
        if any(w in s for w in ["6.0", "7.0", "7.5", "24", "Mbps", "倍"]):
            print("  Claim sentence:", s)
