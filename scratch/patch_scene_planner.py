with open('agents/scene_planner.py', 'r', encoding='utf-8') as f:
    content = f.read()

target_patterns = '''    (r"(?:NASA|甘迺迪太空中心)", "NASA Kennedy Space Center", "wikimedia"),
    (r"(?:白宮|White House)", "White House Washington DC", "wikimedia"),
    (r"(?:聯合國|United Nations)", "United Nations Headquarters New York", "wikimedia"),
]'''

replacement_patterns = '''    (r"(?:NASA|甘迺迪太空中心)", "NASA Kennedy Space Center", "wikimedia"),
    (r"(?:白宮|White House)", "White House Washington DC", "wikimedia"),
    (r"(?:聯合國|United Nations)", "United Nations Headquarters New York", "wikimedia"),

    # Taiwanese & Contemporary Political, Civic & Academic figures & institutions
    (r"(?:沈柏洋|沈伯洋|Puma Shen)", "Puma Shen", "wikimedia"),
    (r"(?:黑熊學院|Kuma Academy)", "Kuma Academy Puma Shen", "wikimedia"),
    (r"(?:黃國昌)", "黃國昌", "wikimedia"),
    (r"(?:柯文哲)", "柯文哲", "wikimedia"),
    (r"(?:賴清德)", "賴清德", "wikimedia"),
    (r"(?:蕭美琴)", "蕭美琴", "wikimedia"),
    (r"(?:蔡英文)", "蔡英文", "wikimedia"),
    (r"(?:馬英九)", "馬英九", "wikimedia"),
    (r"(?:蔣萬安)", "蔣萬安", "wikimedia"),
    (r"(?:陳水扁)", "陳水扁", "wikimedia"),
    (r"(?:韓國瑜)", "韓國瑜", "wikimedia"),
    (r"(?:蘇貞昌)", "蘇貞昌", "wikimedia"),
    (r"(?:游錫堃)", "游錫堃", "wikimedia"),
    (r"(?:郭台銘)", "郭台銘", "wikimedia"),
    (r"(?:曹興誠)", "曹興誠", "wikimedia"),
    (r"(?:立法院|立法院議場|國會議場)", "立法院議場", "wikimedia"),
    (r"(?:行政院)", "行政院", "wikimedia"),
    (r"(?:總統府|臺灣總統府)", "Taiwan Presidential Office Building", "wikimedia"),
    (r"(?:司法院|監察院|中選會)", "Taiwan government building", "wikimedia"),
    (r"(?:五分埔)", "Wufenpu Taipei", "wikimedia"),
    (r"(?:臺大|國立臺灣大學|台大)", "National Taiwan University", "wikimedia"),
    (r"(?:清大|國立清華大學)", "National Tsing Hua University", "wikimedia"),
    (r"(?:陽明交大|交大|國立交通大學)", "National Yang Ming Chiao Tung University", "wikimedia"),
    (r"(?:中研院|中央研究院)", "Academia Sinica Taiwan", "wikimedia"),

    # International Leaders & Contemporary Public Figures
    (r"(?:川普|特朗普|Donald Trump)", "Donald Trump", "wikimedia"),
    (r"(?:拜登|Joe Biden)", "Joe Biden", "wikimedia"),
    (r"(?:賀錦麗|Kamala Harris)", "Kamala Harris", "wikimedia"),
    (r"(?:歐巴馬|Barack Obama)", "Barack Obama", "wikimedia"),
    (r"(?:習近平|Xi Jinping)", "Xi Jinping", "wikimedia"),
    (r"(?:普丁|普京|Putin)", "Vladimir Putin", "wikimedia"),
]'''

if target_patterns not in content:
    print("Error: target_patterns not found!")
    exit(1)

content = content.replace(target_patterns, replacement_patterns, 1)

target_person_regex = '''PERSON_ENTITY_REGEX = re.compile(
    r"(?:Yann LeCun|楊立昆|LeCun|Jensen Huang|黃仁勳|Sam Altman|奧特曼|Elon Musk|馬斯克|"
    r"Demis Hassabis|哈薩比斯|Ilya Sutskever|Geoffrey Hinton|辛頓|Mark Zuckerberg|祖克柏|扎克伯格|"
    r"Satya Nadella|納德拉|Tim Cook|庫克|Lisa Su|蘇姿丰|Morris Chang|張忠謀|Steve Jobs|賈伯斯|"
    r"Andrew Ng|吳恩達|Fei-Fei Li|李飛飛|安藤利吉|陳儀|林獻堂|丘念臺|麥克阿瑟|"
    r"蔣介石|蔣中正|孫中山|國父|李登輝|邱吉爾|Churchill|羅斯福|Roosevelt|愛因斯坦|Einstein|"
    r"奧本海默|Oppenheimer|曼哈頓計畫|圖靈|Alan Turing)",
    re.IGNORECASE,
)'''

replacement_person_regex = '''PERSON_ENTITY_REGEX = re.compile(
    r"(?:Yann LeCun|楊立昆|LeCun|Jensen Huang|黃仁勳|Sam Altman|奧特曼|Elon Musk|馬斯克|"
    r"Demis Hassabis|哈薩比斯|Ilya Sutskever|Geoffrey Hinton|辛頓|Mark Zuckerberg|祖克柏|扎克伯格|"
    r"Satya Nadella|納德拉|Tim Cook|庫克|Lisa Su|蘇姿丰|Morris Chang|張忠謀|Steve Jobs|賈伯斯|"
    r"Andrew Ng|吳恩達|Fei-Fei Li|李飛飛|安藤利吉|陳儀|林獻堂|丘念臺|麥克阿瑟|"
    r"蔣介石|蔣中正|孫中山|國父|李登輝|邱吉爾|Churchill|羅斯福|Roosevelt|愛因斯坦|Einstein|"
    r"奧本海默|Oppenheimer|曼哈頓計畫|圖靈|Alan Turing|"
    r"沈柏洋|沈伯洋|Puma Shen|黃國昌|柯文哲|賴清德|蕭美琴|蔡英文|馬英九|蔣萬安|陳水扁|"
    r"韓國瑜|蘇貞昌|游錫堃|郭台銘|曹興誠|川普|特朗普|Donald Trump|拜登|Joe Biden|"
    r"賀錦麗|Kamala Harris|歐巴馬|Barack Obama|習近平|Xi Jinping|普丁|普京|Putin)",
    re.IGNORECASE,
)'''

if target_person_regex not in content:
    print("Error: target_person_regex not found!")
    exit(1)

content = content.replace(target_person_regex, replacement_person_regex, 1)

target_detect_func = '''def detect_real_world_footage_target(narration: str, visual_desc: str = "", mode: str = "balanced") -> tuple[str | None, str]:
    """Auto-detect real-world tech figures, company demos, chips or hardware for authentic footage lookup.
    
    Modes:
      - 'disabled': 100% pure AI generation.
      - 'balanced': Figures/demos -> YouTube snippet; hardware/chips/routers -> Wikimedia Commons.
      - 'aggressive': Aggressively search Wikimedia / YouTube even on general tech keywords.
      - 'youtube_only': Map all detected entities to YouTube snippet/screenshot.
      - 'wikimedia_only': Map all detected entities to Wikimedia Commons high-res photos.
    """
    if mode == "disabled" or not narration:
        return None, "ai"

    comb_text = f"{narration} {visual_desc}".strip()

    # 1. Check curated high-precision real entity patterns
    for pattern, query, pref_source in REAL_MEDIA_PATTERNS:
        if re.search(pattern, comb_text, flags=re.IGNORECASE):
            # Guard A: If entity is a person, but visual_desc is an inanimate object/macro shot without depicting a person
            if PERSON_ENTITY_REGEX.search(pattern) and visual_desc:
                if MACRO_STILL_LIFE_REGEX.search(visual_desc) and not PERSON_DEPICTION_REGEX.search(visual_desc):
                    continue
                # If person only appeared in narration as a citation/attribution, and visual_desc doesn't depict the person
                if not re.search(pattern, visual_desc, flags=re.IGNORECASE) and not PERSON_DEPICTION_REGEX.search(visual_desc):
                    continue

            # Guard B: If entity is a building/place, but visual_desc is a macro/tabletop object shot
            if PLACE_BUILDING_PATTERNS.search(pattern) and visual_desc:
                if MACRO_STILL_LIFE_REGEX.search(visual_desc):
                    if not re.search(r"\\b(hall|building|exterior|interior|auditorium|facade|architecture)\\b", visual_desc, flags=re.IGNORECASE):
                        continue

            if mode == "youtube_only":
                return query, "youtube_snippet"
            elif mode == "wikimedia_only":
                return query, "wikimedia"
            else:
                return query, pref_source

    # 2. Aggressive mode: extract concrete technical / device keywords
    if mode == "aggressive":
        from providers.stock_client import extract_stock_search_keywords
        kws = extract_stock_search_keywords(visual_desc or narration)
        if kws and kws[0] not in ("modern technology", "clean energy landscape", "nature landscape"):
            return kws[0], "wikimedia"

    return None, "ai"'''

replacement_detect_func = '''def detect_real_world_footage_target(narration: str, visual_desc: str = "", mode: str = "balanced", topic: str = "") -> tuple[str | None, str]:
    """Auto-detect real-world tech figures, company demos, chips or hardware for authentic footage lookup.
    
    Modes:
      - 'disabled': 100% pure AI generation.
      - 'balanced': Figures/demos -> YouTube snippet; hardware/chips/routers -> Wikimedia Commons.
      - 'aggressive': Aggressively search Wikimedia / YouTube even on general tech keywords.
      - 'youtube_only': Map all detected entities to YouTube snippet/screenshot.
      - 'wikimedia_only': Map all detected entities to Wikimedia Commons high-res photos.
    """
    if mode == "disabled" or not narration:
        return None, "ai"

    comb_text = f"{narration} {visual_desc}".strip()

    # 1. Check curated high-precision real entity patterns
    for pattern, query, pref_source in REAL_MEDIA_PATTERNS:
        if re.search(pattern, comb_text, flags=re.IGNORECASE):
            # Guard A: If entity is a person, but visual_desc is an inanimate object/macro shot without depicting a person
            if PERSON_ENTITY_REGEX.search(pattern) and visual_desc:
                if MACRO_STILL_LIFE_REGEX.search(visual_desc) and not PERSON_DEPICTION_REGEX.search(visual_desc):
                    continue
                # If person only appeared in narration as a citation/attribution, and visual_desc doesn't depict the person
                if not re.search(pattern, visual_desc, flags=re.IGNORECASE) and not PERSON_DEPICTION_REGEX.search(visual_desc):
                    continue

            # Guard B: If entity is a building/place, but visual_desc is a macro/tabletop object shot
            if PLACE_BUILDING_PATTERNS.search(pattern) and visual_desc:
                if MACRO_STILL_LIFE_REGEX.search(visual_desc):
                    if not re.search(r"\\b(hall|building|exterior|interior|auditorium|facade|architecture)\\b", visual_desc, flags=re.IGNORECASE):
                        continue

            if mode == "youtube_only":
                return query, "youtube_snippet"
            elif mode == "wikimedia_only":
                return query, "wikimedia"
            else:
                return query, pref_source

    # 2. Dynamic Topic-Subject Extraction: If project topic specifies a real person or institution
    if topic:
        # Strip common topic suffixes/prefixes
        clean_topic = re.sub(r"[：:—\-·|].*$", "", topic).strip()
        clean_topic = re.sub(r"(?:人生哲學|生平|經歷|專題|故事|解析|選戰|秘辛|內幕|紀錄片|從.*到.*)$", "", clean_topic).strip()
        if 2 <= len(clean_topic) <= 20:
            if re.search(re.escape(clean_topic), comb_text, flags=re.IGNORECASE):
                if not (MACRO_STILL_LIFE_REGEX.search(visual_desc) and not PERSON_DEPICTION_REGEX.search(visual_desc)):
                    pref_src = "youtube_snippet" if mode == "youtube_only" else ("wikimedia" if mode == "wikimedia_only" else "wikimedia")
                    return clean_topic, pref_src

    # 3. Dynamic Institution / Landmark Extraction in Narration
    if mode != "disabled":
        inst_match = re.search(r"([\\u4e00-\\u9fa5]{2,8}(?:學院|大學|研究所|委員會|議會|法院|公署|中心))", comb_text)
        if inst_match:
            candidate = inst_match.group(1).strip()
            if candidate not in ("我們的社會", "這個世界", "現代社會", "日常生活", "社會大眾"):
                pref_src = "wikimedia"
                return candidate, pref_src

    # 4. Aggressive mode: extract concrete technical / device keywords
    if mode == "aggressive":
        from providers.stock_client import extract_stock_search_keywords
        kws = extract_stock_search_keywords(visual_desc or narration)
        if kws and kws[0] not in ("modern technology", "clean energy landscape", "nature landscape"):
            return kws[0], "wikimedia"

    return None, "ai"'''

if target_detect_func not in content:
    print("Error: target_detect_func not found!")
    exit(1)

content = content.replace(target_detect_func, replacement_detect_func, 1)

# Pass topic=topic in direct_scenes
target_direct = '''        if not search_kw and auto_stock_mode != "disabled":
            auto_kw, auto_src = detect_real_world_footage_target(
                s["narration"],
                visual_desc=(d.get("visual_description") or ""),
                mode=auto_stock_mode
            )'''

replacement_direct = '''        if not search_kw and auto_stock_mode != "disabled":
            auto_kw, auto_src = detect_real_world_footage_target(
                s["narration"],
                visual_desc=(d.get("visual_description") or ""),
                mode=auto_stock_mode,
                topic=topic
            )'''

if target_direct not in content:
    print("Error: target_direct not found!")
    exit(1)

content = content.replace(target_direct, replacement_direct, 1)

with open('agents/scene_planner.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated agents/scene_planner.py successfully!")
