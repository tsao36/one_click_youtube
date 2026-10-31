with open('rendering/ffmpeg_renderer.py', 'r', encoding='utf-8') as f:
    c = f.read()

target = 'args += ["-i", str(project.abs(sc.audio.path))]'
repl = 'wav_file = project.abs(sc.audio.path) if (sc.audio and sc.audio.path) else project.path("audio", f"{sc.tag}.wav")\n            args += ["-i", str(wav_file)]'

if target in c:
    c = c.replace(target, repl, 1)
    with open('rendering/ffmpeg_renderer.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print('Patched successfully!')
else:
    print('Target not found!')
