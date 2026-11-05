import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from core.project_manager import Project
from core.documentary_pipeline import DocumentaryPipeline

p = Project('project_5')
print("Re-rendering project_5 with no-background text overlays...")
pipe = DocumentaryPipeline(p)
pipe._run_render()
final_path = p.path("final", "project_5.mp4")
print(f"Render complete! Final path: {final_path}, Exists: {final_path.exists()}, Size: {final_path.stat().st_size if final_path.exists() else 0}")
