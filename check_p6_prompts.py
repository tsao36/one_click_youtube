import json
import sys
sys.stdout.reconfigure(encoding="utf-8")
from core.config import PROJECTS_DIR

ip = json.loads((PROJECTS_DIR / "project_6" / "prompts" / "image_prompts.json").read_text(encoding="utf-8"))
p1 = ip[0]["prompt"]
p2 = ip[1]["prompt"]

# Find common prefix length
prefix_len = 0
for c1, c2 in zip(p1, p2):
    if c1 == c2:
        prefix_len += 1
    else:
        break

print(f"Common prefix length: {prefix_len} characters")
print("Common prefix text:")
print(p1[:prefix_len])
print("\nWhere Scene 1 diverges:")
print(p1[prefix_len:prefix_len+150])
print("\nWhere Scene 2 diverges:")
print(p2[prefix_len:prefix_len+150])
