with open('agents/scene_planner.py', 'r', encoding='utf-8') as f:
    content = f.read()

target_inst = '''    # 3. Dynamic Institution / Landmark Extraction in Narration
    if mode != "disabled":
        inst_match = re.search(r"([\\u4e00-\\u9fa5]{2,8}(?:學院|大學|研究所|委員會|議會|法院|公署|中心))", comb_text)
        if inst_match:
            candidate = inst_match.group(1).strip()
            if candidate not in ("我們的社會", "這個世界", "現代社會", "日常生活", "社會大眾"):
                pref_src = "wikimedia"
                return candidate, pref_src'''

replacement_inst = '''    # 3. Dynamic Institution / Landmark Extraction in Narration
    if mode != "disabled":
        inst_match = re.search(r"([\\u4e00-\\u9fa5]{2,12}(?:學院|大學|研究所|委員會|議事堂|議會|法院|公署|中樞|大樓|中心))", comb_text)
        if inst_match:
            candidate = inst_match.group(1).strip()
            candidate = re.sub(r"^(?:他在|他在這個|在這個|這是一個|我們的|身為|在|進入|出任|參加|加入|成立了|創立了|透過|關於)", "", candidate).strip()
            GENERIC_STOP = ("我們的社會", "這個世界", "現代社會", "日常生活", "社會大眾", "委員會", "中心", "法院", "大學", "學院", "議會", "議事堂")
            if len(candidate) >= 3 and candidate not in GENERIC_STOP:
                pref_src = "wikimedia"
                return candidate, pref_src'''

if target_inst not in content:
    print("Error: target_inst not found!")
    exit(1)

content = content.replace(target_inst, replacement_inst, 1)

with open('agents/scene_planner.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated institution extraction guard successfully!")
