import sys
import json
from pathlib import Path

ROOT = Path(r"c:\AI Project\Youtube_video")
sys.path.insert(0, str(ROOT))

from rendering.ffmpeg_utils import duration

p_path = ROOT / 'projects/intel_28_intel/scenes/scenes.json'
scenes = json.loads(p_path.read_text(encoding='utf-8'))

for sc in scenes:
    sid = sc.get('scene_id')
    if sid in (1, 24, 47):
        anim_f = ROOT / f'projects/intel_28_intel/animation/scene_{sid:03d}.mp4'
        audio_f = ROOT / f'projects/intel_28_intel/audio/scene_{sid:03d}.wav'
        dur = duration(anim_f)
        sc.setdefault('animation', {})
        sc['animation']['status'] = 'COMPLETED'
        sc['animation']['path'] = f'animation/scene_{sid:03d}.mp4'
        sc['animation']['meta'] = {
            'provider': 'masked_speaker',
            'engine': 'masked_speaker',
            'is_cloud': False,
            'duration': dur,
            'masked': True,
            'source': 'base_video.mp4'
        }
        sc['ai_video'] = True
        print(f'Updated Scene {sid}: anim duration = {dur:.2f}s, audio duration = {duration(audio_f):.2f}s')

p_path.write_text(json.dumps(scenes, ensure_ascii=False, indent=2), encoding='utf-8')
print("scenes.json updated successfully.")
