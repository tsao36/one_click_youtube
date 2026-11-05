import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from core.project_manager import Project
from core.documentary_pipeline import DocumentaryPipeline

p = Project('project_5')
pipe = DocumentaryPipeline(p)
print("Regenerating subtitles for project_5...")
pipe._run_subtitles()

ass_file = p.path("subtitles", "subtitles.ass")
print("Reading generated subtitles.ass:")
with open(ass_file, "r", encoding="utf-8") as f:
    lines = [line.strip() for line in f if "FoxCallout" in line or "第二次怪獸熱潮" in line]
for l in lines:
    print(l)
