with open('core/pipeline.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = 'motion_callouts_enabled = bool(\n\n            sub_cfg.get("motion_graphics_callouts", sub_cfg.get("callouts_enabled", True))\n\n        )\n\n        callouts = None\n\n        if motion_callouts_enabled:\n\n            from generators.motion_callout_generator import extract_motion_callouts\n\n            callouts = extract_motion_callouts(scenes, slots)\n\n\n\n        is_drama = bool(self.p.settings.get("project_mode") == "short_drama" or self.p.data.settings.get("project_mode") == "short_drama")'

repl = 'is_drama = bool(self.p.settings.get("project_mode") == "short_drama" or self.p.data.settings.get("project_mode") == "short_drama")\n\n        # Motion graphics callouts are strictly disabled for short drama videos\n        motion_callouts_enabled = bool(\n            sub_cfg.get("motion_graphics_callouts", sub_cfg.get("callouts_enabled", True))\n        ) and not is_drama\n\n        callouts = None\n        if motion_callouts_enabled:\n            from generators.motion_callout_generator import extract_motion_callouts\n            callouts = extract_motion_callouts(scenes, slots)'

target_crlf = target.replace('\n', '\r\n')
repl_crlf = repl.replace('\n', '\r\n')

if target_crlf in text:
    text = text.replace(target_crlf, repl_crlf, 1)
    with open('core/pipeline.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Successfully patched core/pipeline.py!')
elif target in text:
    text = text.replace(target, repl, 1)
    with open('core/pipeline.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Successfully patched core/pipeline.py (LF)!')
else:
    print('Target still not found!')
