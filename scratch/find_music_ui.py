from pathlib import Path

index_html = Path("ui/index.html").read_text(encoding="utf-8")
lines = index_html.splitlines()

for i, line in enumerate(lines):
    if 'id="music"' in line or 'id="tab-music"' in line or "loadMusicTracks" in line:
        print(f"Line {i+1}: {line[:120]}")
