import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.project_manager import Project
from rendering.ffmpeg_renderer import render_project

project = Project("wi_fi")
print(f"Project: {project.id}, {len(project.scenes)} scenes")

for idx in [1, 24, 46]:
    s = project.scenes[idx - 1]
    print(f"Scene {idx}: is_presenter={s.is_presenter}, animation={s.animation}")

print("Starting render_project...")
def on_progress(done, total, msg):
    print(f"[{done}/{total}] {msg}", flush=True)

output_path = render_project(project, progress=on_progress)
print(f"Render completed successfully! Output: {output_path}")
