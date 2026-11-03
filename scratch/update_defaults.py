with open('api_server.py', 'r', encoding='utf-8') as f:
    c = f.read()

target = '"current_model": p.data.settings.get("stage_models", {}).get("images") or p.data.settings.get("images", {}).get("provider") or p.data.settings.get("images", {}).get("checkpoint") or "sd_xl_base_1.0.safetensors",'
replacement = '"current_model": (p.data.settings.get("stage_models", {}).get("images") or p.settings.get("stage_models", {}).get("images") or p.data.settings.get("images", {}).get("provider") or p.settings.get("images", {}).get("provider") or "nano-banana-2.1"),'
assert target in c, "Target not found in api_server.py"
c = c.replace(target, replacement, 1)

with open('api_server.py', 'w', encoding='utf-8') as f:
    f.write(c)

print("api_server.py updated successfully")
