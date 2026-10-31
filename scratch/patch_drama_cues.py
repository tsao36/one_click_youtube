import re
p = 'core/drama_pipeline.py'
t = open(p, encoding='utf-8').read()
pat = re.compile(r'(max_lines=int\(sub_cfg\.get\("max_lines", 2\)\))(\s*\))')
repl = r'''\1,
            frame_width=int(cfg["video"]["width"]),
            frame_height=int(cfg["video"]["height"]),
            style=sub_cfg.get("style", "youtube_standard"),
        )'''
t2, n = pat.subn(repl, t, count=1)
print('replaced', n)
open(p, 'w', encoding='utf-8').write(t2)
