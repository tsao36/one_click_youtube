import subprocess
import json

cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', 'projects/wi_fi/final/wi_fi.mp4']
res = subprocess.run(cmd, capture_output=True, text=True)
data = json.loads(res.stdout)
f = data.get('format', {})
print('Final Video Duration:', f.get('duration'), 's')
print('Final Video Size:', round(int(f.get('size', 0)) / (1024 * 1024), 2), 'MB')
for s in data.get('streams', []):
    ctype = s.get('codec_type')
    cname = s.get('codec_name')
    if ctype == 'video':
        print(f"Video Stream: {cname}, {s.get('width')}x{s.get('height')}, fps={s.get('r_frame_rate')}")
    elif ctype == 'audio':
        print(f"Audio Stream: {cname}, {s.get('sample_rate')}Hz, {s.get('channels')} channels")
