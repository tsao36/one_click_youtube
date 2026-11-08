import json
import subprocess
from pathlib import Path

mg_path = Path("projects/bluetooth_7_0_high_data_2/scenes/motion_graphics.json")
mg = json.load(open(mg_path, "r", encoding="utf-8"))

# Test scene index 36 (scene_id 37)
s36 = mg["scenes"][36]
props = dict(s36["props"])
props["subtext"] = "結論"

props_json = json.dumps(props, ensure_ascii=False)
out_png = Path("scratch/test_conclusion_scene_37.png").resolve()

cmd = [
    "npx", "remotion", "still", "src/index.ts", "KineticTypographyScene",
    str(out_png),
    f"--props={props_json}",
    "--frame=30"
]

print("Running remotion still...")
res = subprocess.run(cmd, cwd="remotion-video", capture_output=True, text=True, shell=True)
print("Exit code:", res.returncode)
if res.returncode != 0:
    print("Stderr:", res.stderr)
else:
    print(f"Rendered still: {out_png} (size={out_png.stat().st_size} bytes)")
