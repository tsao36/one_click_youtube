from pathlib import Path

drama_p = Path("core/drama_pipeline.py")
lines = drama_p.read_text(encoding="utf-8").splitlines(keepends=True)

for i, l in enumerate(lines):
    if 'spk = s.speaker or shot.get("speaker"' in l:
        print('Stage 4 prompt loop line:', i + 1)
    if 'styled_char_path = self.p.path("characters"' in l:
        print('Stage 5 styled char line:', i + 1)
    if 'target_anim_engine = self.get_stage_model("animation")' in l:
        print('Stage 7 target engine line:', i + 1)
    if '# 1. Primary: Hedra AI Character Lip-Syncing' in l:
        print('Stage 7 hedra loop line:', i + 1)
