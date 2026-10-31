with open('api_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''            auto_kw, _ = detect_real_world_footage_target(existing_s.narration, existing_s.visual_description, mode=auto_mode)'''
replacement = '''            auto_kw, _ = detect_real_world_footage_target(existing_s.narration, existing_s.visual_description, mode=auto_mode, topic=p.data.topic or "")'''

if target in content:
    content = content.replace(target, replacement, 1)
    with open('api_server.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed line 2627 in api_server.py!")
else:
    print("Target already updated or not found.")
