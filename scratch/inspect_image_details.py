import sys
sys.path.insert(0, ".")
from PIL import Image
from pathlib import Path
from rendering.ffmpeg_utils import duration

p = Path("projects/ai_3")

def info(fpath):
    if not fpath.exists():
        return "NOT FOUND"
    if fpath.suffix.lower() == ".mp4":
        d = duration(fpath)
        return f"MP4: {d:.2f}s, {fpath.stat().st_size} bytes"
    else:
        im = Image.open(fpath)
        return f"IMG: {im.size}, format={im.format}, {fpath.stat().st_size} bytes"

print("Scene 1 files:")
print("  characters/char_2_1793284389435.png:", info(p / "characters/char_2_1793284389435.png"))
print("  characters/char_2_1793284389435_styled_9x16.png:", info(p / "characters/char_2_1793284389435_styled_9x16.png"))
print("  images/scene_001.png:", info(p / "images/scene_001.png"))
print("  images/scene_001.mp4:", info(p / "images/scene_001.mp4"))
print("  animation/scene_001.mp4:", info(p / "animation/scene_001.mp4"))
