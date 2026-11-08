import json
from pathlib import Path
from agents.script_writer import script_markdown

p_dir = Path("projects/bluetooth_7_0_high_data_2")
scr_path = p_dir / "script/script.json"
with open(scr_path, "r", encoding="utf-8") as f:
    scr = json.load(f)

patches = [
    ("比過去快上 7.5 倍", "相較低功耗藍芽最初的 1 Mbps 大幅提升 7.5 倍（更是 2 Mbps 限制的近 4 倍）"),
    ("雖然傳輸速度提升到 24 Mbps", "雖然導入了 Channel Sounding 高精度測距技術但實體層速度仍為 2 Mbps")
]

for target, replacement in patches:
    found = False
    for sec in scr["sections"]:
        if target in sec["text"]:
            sec["text"] = sec["text"].replace(target, replacement)
            print(f"Patched '{target}' in section '{sec['name']}'!")
            found = True
    if not found:
        print(f"Target '{target}' NOT found!")

print("\n--- Patched Hook ---")
print(scr["sections"][0]["text"])

print("\n--- Patched Introduction ---")
print(scr["sections"][1]["text"])
