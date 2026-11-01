import sys
from pathlib import Path

ROOT = Path(r"c:\AI Project\Youtube_video")
sys.path.insert(0, str(ROOT))

from core.project_manager import Project
from core.pipeline import Pipeline

p = Project("intel_28_intel")
p.clear_clips_cache()
print("Clips cache cleared.")

pipe = Pipeline(p)
print("Starting _run_render for intel_28_intel...")
pipe._run_render()
print("Render complete! Final video output:", p.data.outputs.get("final"))
