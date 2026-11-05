import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from core.project_manager import Project
from core.character_detector import enforce_main_character_real_image_ratio

p = Project('project_5')
print(f"Running enforce_main_character_real_image_ratio on {p.id} with ratio=0.9...")

res = enforce_main_character_real_image_ratio(
    p,
    ratio=0.9,
    clip_ratio=0.7,
    extra_queries=["快傑ライオン丸", "風雲ライオン丸", "快傑ライオン丸 変身"]
)

print("Enforce result:", res)
