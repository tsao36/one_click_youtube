with open('api_server.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''    if p_mode == "short_drama":
        p.data.settings.setdefault("video", {})["aspect_ratio"] = aspect
        p.data.settings["video"]["duration_seconds"] = dur_sec'''

repl = '''    if p_mode == "short_drama":
        p.data.settings.setdefault("video", {})["aspect_ratio"] = aspect
        p.data.settings["video"]["duration_seconds"] = dur_sec
        p.data.settings.setdefault("subtitles", {})["motion_graphics_callouts"] = False
        p.data.settings["subtitles"]["callouts_enabled"] = False'''

target_crlf = target.replace('\n', '\r\n')
repl_crlf = repl.replace('\n', '\r\n')

if target_crlf in text:
    text = text.replace(target_crlf, repl_crlf, 1)
    with open('api_server.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched api_server.py successfully!')
elif target in text:
    text = text.replace(target, repl, 1)
    with open('api_server.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched api_server.py (LF)!')
else:
    print('Target not found!')
