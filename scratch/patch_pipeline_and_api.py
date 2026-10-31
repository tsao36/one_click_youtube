import re

# 1. Patch core/documentary_pipeline.py
with open('core/documentary_pipeline.py', 'r', encoding='utf-8') as f:
    doc_content = f.read()

pattern_doc = r'dyn_kw,\s*dyn_src\s*=\s*detect_real_world_footage_target\(\s*s\.narration,\s*getattr\(s,\s*"visual_description",\s*""\)\s*or\s*"",\s*mode=auto_stock_mode\s*\)'

replacement_doc = '''dyn_kw, dyn_src = detect_real_world_footage_target(

                        s.narration,

                        getattr(s, "visual_description", "") or "",

                        mode=auto_stock_mode,

                        topic=self.p.data.topic or ""

                    )'''

doc_new, count = re.subn(pattern_doc, replacement_doc, doc_content)
if count == 0:
    print("Error: pattern_doc not found in core/documentary_pipeline.py")
    exit(1)

with open('core/documentary_pipeline.py', 'w', encoding='utf-8') as f:
    f.write(doc_new)
print("core/documentary_pipeline.py patched successfully!")

# 2. Patch api_server.py
with open('api_server.py', 'r', encoding='utf-8') as f:
    api_content = f.read()

target_api1 = '''                auto_kw, auto_src = detect_real_world_footage_target(sc.narration, sc.visual_description, mode=auto_mode)'''
replacement_api1 = '''                auto_kw, auto_src = detect_real_world_footage_target(sc.narration, sc.visual_description, mode=auto_mode, topic=p.data.topic or "")'''

if target_api1 in api_content:
    api_content = api_content.replace(target_api1, replacement_api1, 1)

target_api2 = '''            auto_kw, auto_src = detect_real_world_footage_target(s.narration, s.visual_description, mode=auto_mode)'''
replacement_api2 = '''            auto_kw, auto_src = detect_real_world_footage_target(s.narration, s.visual_description, mode=auto_mode, topic=p.data.topic or "")'''

if target_api2 in api_content:
    api_content = api_content.replace(target_api2, replacement_api2, 1)

# Search for any remaining calls in api_server.py
pattern_api_more = r'detect_real_world_footage_target\(s\.narration,\s*s\.visual_description,\s*mode=auto_mode\)'
replacement_api_more = 'detect_real_world_footage_target(s.narration, s.visual_description, mode=auto_mode, topic=p.data.topic or "")'
api_content = re.sub(pattern_api_more, replacement_api_more, api_content)

with open('api_server.py', 'w', encoding='utf-8') as f:
    f.write(api_content)
print("api_server.py patched successfully!")
