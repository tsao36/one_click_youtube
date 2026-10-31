"""Stage 3 - split narration into visual scenes (deterministic timing + LLM visual direction)."""
from __future__ import annotations

import random
import re

from core.logging_setup import log
from core.models import CAMERA_MOTIONS, Scene
from providers.llm import LLMClient
from rendering.ken_burns import choose_motions

SYSTEM = ("You are a documentary director and storyboard artist. For each narration line you design one strong, "
          "filmable still image that a text-to-image model can render. Never ask for readable text, captions, "
          "logos or UI in images. CRITICAL: All visual_description fields MUST be written strictly in ENGLISH "
          "even if narration is in Chinese or other languages, because the image generation models (SDXL) require English. "
          "Output only JSON.")


def count_units(text: str) -> int:
    """Accurately count spoken units: CJK characters + Latin words."""
    cjk = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))
    if cjk > 0:
        latin_words = len(re.findall(r"[a-zA-Z0-9'-]+", re.sub(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", " ", text)))
        return cjk + latin_words
    return len(re.findall(r"\b[\w'-]+\b", text))


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, strictly respecting quotation marks and brackets."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    # Track quote / bracket depth so punctuation inside quotes does NOT sever sentences
    open_quotes = {"「": "」", "『": "』", "“": "”", '"': '"', "（": "）", "(": ")", "《": "》", "【": "】"}
    close_quotes = {v: k for k, v in open_quotes.items()}

    quote_stack = []
    sentence_end_chars = set("。！？!?；;…\n")
    closing_quote_chars = set("」』”\"’')）》】")

    sentences = []
    current = []

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        current.append(ch)

        # Update quotation balance
        if ch in open_quotes:
            if ch == '"' and quote_stack and quote_stack[-1] == '"':
                quote_stack.pop()
            else:
                quote_stack.append(ch)
        elif ch in close_quotes:
            expected_open = close_quotes[ch]
            if quote_stack and quote_stack[-1] == expected_open:
                quote_stack.pop()
            elif ch == '"' and not quote_stack:
                quote_stack.append(ch)

        # Only split if we are strictly outside all quotes and brackets
        if not quote_stack and ch in sentence_end_chars:
            # Consume any immediately following closing quote characters so they attach to this sentence
            while i + 1 < n and text[i + 1] in closing_quote_chars:
                i += 1
                current.append(text[i])
            s = "".join(current).strip()
            if s:
                sentences.append(s)
            current = []
        i += 1

    if current:
        s = "".join(current).strip()
        if s:
            sentences.append(s)

    return sentences


def _split_long(sentence: str, max_units: int) -> list[str]:
    """Split an over-long sentence at clause boundaries, respecting quotation marks."""
    if count_units(sentence) <= max_units:
        return [sentence]

    open_quotes = {"「": "」", "『": "』", "“": "”", '"': '"', "（": "）", "(": ")", "《": "》", "【": "】"}
    close_quotes = {v: k for k, v in open_quotes.items()}
    quote_stack = []
    delims = set("，、,;:—–")

    clauses = []
    cur = []
    i = 0
    n = len(sentence)
    while i < n:
        ch = sentence[i]
        cur.append(ch)
        if ch in open_quotes:
            if ch == '"' and quote_stack and quote_stack[-1] == '"':
                quote_stack.pop()
            else:
                quote_stack.append(ch)
        elif ch in close_quotes:
            expected_open = close_quotes[ch]
            if quote_stack and quote_stack[-1] == expected_open:
                quote_stack.pop()
            elif ch == '"' and not quote_stack:
                quote_stack.append(ch)

        # Only split on clause boundaries when outside quotes
        if not quote_stack and ch in delims:
            while i + 1 < n and sentence[i + 1] in delims:
                i += 1
                cur.append(sentence[i])
            clauses.append("".join(cur))
            cur = []
        i += 1
    if cur:
        clauses.append("".join(cur))

    out, buf = [], ""
    for c in clauses:
        if buf and count_units(buf + c) > max_units:
            out.append(buf.strip())
            buf = c
        else:
            buf += c
    if buf:
        out.append(buf.strip())

    final = []
    for o in out:
        if count_units(o) <= max_units:
            final.append(o)
        else:
            if re.search(r"[\u4e00-\u9fff]", o):
                for k in range(0, len(o), max(1, max_units)):
                    part = o[k:k + max_units].strip()
                    if part:
                        final.append(part)
            else:
                w = o.split()
                while len(w) > max_units:
                    final.append(" ".join(w[:max_units]))
                    w = w[max_units:]
                if w:
                    final.append(" ".join(w))
    return final


def balance_scene_quotes(scenes: list[dict]) -> list[dict]:
    """Validate and heal any scene boundaries that sever paired quotes or brackets across scenes."""
    pairs = [("「", "」"), ("『", "』"), ("“", "”"), ("（", "）"), ("《", "》"), ("【", "】")]

    for i in range(len(scenes) - 1):
        s1 = scenes[i]
        s2 = scenes[i + 1]
        n1 = s1.get("narration", "")
        n2 = s2.get("narration", "")

        for o_ch, c_ch in pairs:
            # If s1 has an unclosed open quote and s2 has the closing quote
            if n1.count(o_ch) > n1.count(c_ch) and n2.count(c_ch) > n2.count(o_ch):
                last_open = n1.rfind(o_ch)
                if last_open != -1:
                    # Look backwards for a natural clause lead-in before the quote (e.g. preceding comma, colon, or sentence end)
                    comma_pos = max(n1.rfind("，", 0, last_open), n1.rfind("。", 0, last_open), n1.rfind("、", 0, last_open), n1.rfind("：", 0, last_open))
                    cut_pos = (comma_pos + 1) if comma_pos != -1 else last_open

                    unclosed_fragment = n1[cut_pos:]
                    s1["narration"] = n1[:cut_pos].rstrip("，、,;:—– ")
                    if s1["narration"] and not s1["narration"].endswith(("。", "！", "？", "!", "?", "…")):
                        s1["narration"] += "。"
                    s2["narration"] = unclosed_fragment + s2["narration"]
                    n1 = s1["narration"]
                    n2 = s2["narration"]

    # Clean any orphan leading closing marks or trailing unclosed quotes from each scene
    for s in scenes:
        nar = s.get("narration", "")
        for o_ch, c_ch in pairs:
            if nar.startswith(c_ch) and nar.count(o_ch) < nar.count(c_ch):
                nar = nar[len(c_ch):].lstrip()
            if nar.endswith(o_ch) and nar.count(o_ch) > nar.count(c_ch):
                nar = nar[:-len(o_ch)].rstrip()
        s["narration"] = nar

    return scenes


def segment(sections: list[dict], wpm: float, avg: float, mn: float, mx: float, seed: int = 0) -> list[dict]:
    """Group sentences into scenes with varied durations between mn and mx seconds (estimated from spoken units)."""
    rnd = random.Random(seed)
    scenes = []
    for sec in sections:
        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", sec.get("text", "")))
        wps = 3.6 if has_cjk else (wpm / 60.0)
        units = []
        for s in split_sentences(sec["text"]):
            units += _split_long(s, int(mx * wps))
        buf: list[str] = []
        target = rnd.uniform(max(mn, avg - 2.0), min(mx, avg + 2.0))
        sep = "" if has_cjk else " "
        for u in units:
            cur = count_units(sep.join(buf)) / wps
            add = count_units(u) / wps
            if buf and (cur >= target or cur + add > mx):
                scenes.append({"section": sec["name"], "narration": sep.join(buf).strip()})
                buf = []
                target = rnd.uniform(max(mn, avg - 2.0), min(mx, avg + 2.0))
            buf.append(u)
        if buf:
            tail = sep.join(buf).strip()
            if scenes and scenes[-1]["section"] == sec["name"] and count_units(tail) / wps < mn and \
                    (count_units(scenes[-1]["narration"]) + count_units(tail)) / wps <= mx:
                scenes[-1]["narration"] += (sep + tail)
            else:
                scenes.append({"section": sec["name"], "narration": tail})
    scenes = balance_scene_quotes(scenes)
    for i, s in enumerate(scenes):
        s["scene_id"] = i + 1
        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", s["narration"]))
        wps = 3.6 if has_cjk else (wpm / 60.0)
        s["estimated_duration"] = round(count_units(s["narration"]) / wps, 2)
    return scenes


def _clamp01(x, default=0.5) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return default


def visual_bible(topic: str, script_text: str, client: LLMClient) -> dict:
    prompt = (f"Topic: {topic}\nNarration:\n{script_text[:9000]}\n\n"
              "List the recurring visual entities (people, places, objects, eras) that appear in several scenes and "
              "must look consistent. Give each a short fixed visual description (appearance, colours, clothing, materials). "
              'Return JSON: {"entities": [{"name": "short name", "description": "fixed visual description"}]} '
              "with at most 8 entities. Use generic people (no celebrities).")
    try:
        data = client.json(prompt, SYSTEM, temperature=0.4)
        ents = [e for e in data.get("entities", []) if e.get("name") and e.get("description")][:8]
        return {"entities": ents}
    except Exception as e:  # non-critical
        log.warning("Visual bible failed (%s); continuing without it", e)
        return {"entities": []}


def extract_auto_callout(narration: str) -> tuple[str | None, str | None]:
    """Extract prominent metric, number with units, or key technical phrase if narration has one."""
    if not narration:
        return None, None
    units_regex = (
        r"(\b\d[\d,.]*\s*(?:[億萬千百]?\s*(?:滴/秒|滴|顆|nm|奈米|微米|公厘|公分|公尺|公里|"
        r"度|秒|分鐘|小時|年|世紀|歐元|美元|美金|台幣|瓦|KW|MW|GW|%|折|倍|層|片|片/小時|NA|EV)))"
    )
    m = re.search(units_regex, narration, flags=re.IGNORECASE)
    if m:
        clean = m.group(1).strip()
        if not clean.startswith("⚡"):
            clean = f"⚡ {clean}"
        return clean, "metric"

    record_regex = r"((?:每秒|高達|超過|達到|僅有|歷時|耗時)\s*\d[\d,.]*\s*[^\s，。！？、]{1,6})"
    m2 = re.search(record_regex, narration)
    if m2:
        clean = m2.group(1).strip()
        if not clean.startswith("⚡"):
            clean = f"⚡ {clean}"
        return clean, "metric"

    return None, None


def extract_phase_turn_text(section_name: str, narration: str, topic: str = "") -> str:
    """Extract an impactful 8-22 character critical text in Traditional Chinese to foretell the next phase's story."""
    clean_sec = re.sub(r"\s*\([^\)]*\)", "", section_name).strip() if section_name else ""
    
    if narration:
        sentences = [p.strip() for p in re.split(r"[。！？!?]+", narration) if p.strip()]
        for sent in sentences[:2]:
            if any(k in sent for k in ["真相", "憑什麼", "事實", "到底", "關鍵", "革命", "轉折", "代價", "秘密", "為什麼", "如何", "不只是"]):
                clean_s = re.sub(r"^(但是|然而|不過|其實|所以)，?", "", sent).strip()
                if 6 <= len(clean_s) <= 22:
                    return clean_s
                elif len(clean_s) > 22:
                    sub_parts = re.split(r"[，,：:]", clean_s)
                    if sub_parts and 6 <= len(sub_parts[0]) <= 22:
                        return sub_parts[0]

    if clean_sec:
        if "核心" in clean_sec or "解析" in clean_sec or "主題" in clean_sec:
            return "關鍵真相：深度核心解析"
        if "總結" in clean_sec or "啟發" in clean_sec:
            return "關鍵啟發：未來影響與啟發"
        if "轉折" in clean_sec or "危機" in clean_sec:
            return f"關鍵轉折：{clean_sec}"
        return f"關鍵真相：{clean_sec}"

    return "關鍵轉折：核心真相解析"


# Real-world authentic media pattern mapping
# Format: (pattern, query, preferred_source)
# preferred_source: "youtube_snippet" | "wikimedia"
REAL_MEDIA_PATTERNS: list[tuple[str, str, str]] = [
    # Key Tech Personalities & Leaders (prefer authentic YouTube keynotes/interviews)
    (r"(?:Yann LeCun|楊立昆|LeCun)", "Yann LeCun interview", "youtube_snippet"),
    (r"(?:Jensen Huang|黃仁勳)", "Jensen Huang Computex keynote", "youtube_snippet"),
    (r"(?:Sam Altman|奧特曼)", "Sam Altman interview", "youtube_snippet"),
    (r"(?:Elon Musk|馬斯克)", "Elon Musk interview", "youtube_snippet"),
    (r"(?:Demis Hassabis|哈薩比斯)", "Demis Hassabis DeepMind", "youtube_snippet"),
    (r"(?:Ilya Sutskever)", "Ilya Sutskever SSI interview", "youtube_snippet"),
    (r"(?:Geoffrey Hinton|辛頓)", "Geoffrey Hinton interview", "youtube_snippet"),
    (r"(?:Mark Zuckerberg|祖克柏|扎克伯格)", "Mark Zuckerberg Meta keynote interview", "youtube_snippet"),
    (r"(?:Satya Nadella|納德拉)", "Satya Nadella Microsoft keynote", "youtube_snippet"),
    (r"(?:Tim Cook|庫克)", "Tim Cook Apple keynote", "youtube_snippet"),
    (r"(?:Lisa Su|蘇姿丰)", "Lisa Su AMD Computex keynote", "youtube_snippet"),
    (r"(?:Morris Chang|張忠謀)", "Morris Chang TSMC interview", "youtube_snippet"),
    (r"(?:Steve Jobs|賈伯斯)", "Steve Jobs keynote iPhone", "youtube_snippet"),
    (r"(?:Andrew Ng|吳恩達)", "Andrew Ng AI lecture", "youtube_snippet"),
    (r"(?:Fei-Fei Li|李飛飛)", "Fei-Fei Li World Labs AI keynote", "youtube_snippet"),

    # Robotics, Autonomous Vehicles & Live Product Demos (prefer YouTube clips)
    (r"(?:Sora|OpenAI Sora)", "OpenAI Sora demo", "youtube_snippet"),
    (r"(?:Boston Dynamics|波士頓動力|Atlas robot)", "Boston Dynamics Atlas robot demo", "youtube_snippet"),
    (r"(?:Tesla Optimus|Optimus|特斯拉機器人)", "Tesla Optimus robot demo", "youtube_snippet"),
    (r"(?:Tesla Cybercab|Cybercab|Robotaxi|特斯拉無人計程車)", "Tesla Cybercab Robotaxi unveil", "youtube_snippet"),
    (r"(?:Waymo|自駕車|自動駕駛)", "Waymo autonomous vehicle drive", "youtube_snippet"),
    (r"(?:Figure 01|Figure 02)", "Figure 01 humanoid robot demo", "youtube_snippet"),
    (r"(?:Unitree|宇樹科技|宇樹機器人)", "Unitree humanoid robot demo", "youtube_snippet"),
    (r"(?:Apple Vision Pro|Vision Pro)", "Apple Vision Pro demo review", "youtube_snippet"),
    (r"(?:Neuralink|腦機介面)", "Neuralink patient demo", "youtube_snippet"),
    (r"(?:SpaceX Starship|星艦)", "SpaceX Starship launch", "youtube_snippet"),
    (r"(?:World Model|世界模型|V-JEPA|JEPA)", "World Models AI Yann LeCun JEPA", "youtube_snippet"),

    # Networking, Wi-Fi, Routers & Telecom (prefer authentic Wikimedia Commons photos)
    (r"(?:Wi-Fi 8|802\.11bn|WiFi 8)", "Wi-Fi router antenna wireless technology", "wikimedia"),
    (r"(?:Wi-Fi 7|802\.11be|WiFi 7)", "Wi-Fi 7 wireless router hardware", "wikimedia"),
    (r"(?:Wi-Fi 6E|Wi-Fi 6|802\.11ax)", "Wi-Fi router antenna", "wikimedia"),
    (r"(?:路由器|無線路由器|Wi-Fi AP|無線AP|Router)", "wireless router hardware network", "wikimedia"),
    (r"(?:基地台|5G基地台|通訊塔|行動基地台)", "cellular base station antenna tower", "wikimedia"),
    (r"(?:光纖|光纖電纜|海底電纜)", "fiber optic cable telecommunication glowing", "wikimedia"),
    (r"(?:低軌衛星|通訊衛星|Starlink|星鏈)", "communications satellite solar array space", "wikimedia"),

    # Semiconductor, Chips & Hardware (prefer authentic Wikimedia Commons photos)
    (r"(?:ASML|High-NA EUV|微影機|光刻機)", "ASML EUV machine cleanroom lithography", "wikimedia"),
    (r"(?:TSMC|台積電|晶圓代工)", "TSMC semiconductor wafer cleanroom fab", "wikimedia"),
    (r"(?:矽晶圓|半導體晶圓|Wafer)", "semiconductor silicon wafer cleanroom", "wikimedia"),
    (r"(?:Blackwell|GB200|B200|H100|H200|Nvidia GPU)", "Nvidia GPU processor board chip", "wikimedia"),
    (r"(?:Apple M4|Apple M3|Apple Silicon|M4晶片|M3晶片)", "Apple silicon processor chip die", "wikimedia"),
    (r"(?:微處理器|中央處理器|CPU晶片|晶片架構)", "microprocessor integrated circuit silicon die", "wikimedia"),
    (r"(?:量子電腦|超導量子|IBM Quantum)", "IBM quantum computer cryostat dilution", "wikimedia"),
    (r"(?:伺服器機房|資料中心|機房伺服器|Server rack)", "data center server rack row interior", "wikimedia"),
    (r"(?:液冷散熱|水冷伺服器|浸沒式冷卻)", "liquid cooling computer heat sink radiator", "wikimedia"),
    (r"(?:太陽能板|太陽能發電|光伏)", "solar photovoltaic panel array renewable", "wikimedia"),
    (r"(?:風力發電機|風力發電|風力發電廠)", "wind turbine wind farm renewable energy", "wikimedia"),
    (r"(?:大型強子對撞機|粒子加速器|CERN)", "Large Hadron Collider CERN particle detector", "wikimedia"),

    # Historical Events, Treaties, Figures & Landmarks (prefer authentic Wikimedia Commons photos)
    (r"(?:臺北公會堂|中山堂)", "Taipei Zhongshan Hall Public Hall", "wikimedia"),
    (r"(?:受降典禮|受降儀式|臺灣省受降|受降)", "Surrender ceremony Japan Taiwan 1945", "wikimedia"),
    (r"(?:安藤利吉)", "Ando Rikichi Governor-General", "wikimedia"),
    (r"(?:陳儀)", "General Chen Yi 1945", "wikimedia"),
    (r"(?:林獻堂)", "Lin Hsien-tang Taiwan", "wikimedia"),
    (r"(?:丘念臺)", "Chiu Nien-tai Taiwan", "wikimedia"),
    (r"(?:臺灣總督府|總督府|長官公署)", "Taiwan Governor-General Office", "wikimedia"),
    (r"(?:開羅宣言)", "Cairo Conference 1943 Chiang Kai-shek", "wikimedia"),
    (r"(?:舊金山和約)", "Treaty of San Francisco 1951", "wikimedia"),
    (r"(?:中日和約|臺北和約)", "Treaty of Taipei 1952", "wikimedia"),
    (r"(?:二二八事件|228事件)", "228 Incident monument Taiwan", "wikimedia"),
    (r"(?:麥克阿瑟|一般命令第一號)", "General Douglas MacArthur 1945", "wikimedia"),
    (r"(?:蔣介石|蔣中正)", "Chiang Kai-shek portrait", "wikimedia"),
    (r"(?:日本投降|終戰|玉音放送)", "Japanese surrender 1945", "wikimedia"),
    (r"(?:孫中山|國父)", "Sun Yat-sen", "wikimedia"),
    (r"(?:李登輝)", "Lee Teng-hui", "wikimedia"),
    (r"(?:白色恐怖)", "White Terror Taiwan memorial", "wikimedia"),
    (r"(?:邱吉爾|Churchill)", "Winston Churchill", "wikimedia"),
    (r"(?:羅斯福|Roosevelt)", "Franklin D Roosevelt", "wikimedia"),
    (r"(?:愛因斯坦|Einstein)", "Albert Einstein", "wikimedia"),
    (r"(?:奧本海默|Oppenheimer|曼哈頓計畫)", "J Robert Oppenheimer Manhattan Project", "wikimedia"),
    (r"(?:圖靈|Alan Turing)", "Alan Turing", "wikimedia"),
    (r"(?:阿波羅計畫|登月|Apollo 11)", "Apollo 11 Moon landing NASA", "wikimedia"),
    (r"(?:NASA|甘迺迪太空中心)", "NASA Kennedy Space Center", "wikimedia"),
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
]

# Legacy backward-compatibility alias
REAL_ENTITY_PATTERNS = [(p[0], p[1]) for p in REAL_MEDIA_PATTERNS]

# Regex classifying person/leader entity patterns
PERSON_ENTITY_REGEX = re.compile(
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
)

# Inanimate macro / still life / document / object shot indicators in visual descriptions
MACRO_STILL_LIFE_REGEX = re.compile(
    r"\b(macro|tabletop|still life|pocket watch|watch|clock|pen|fountain pen|stamp pad|official seal|"
    r"inkwell|desk|conference table|document|documents|parchment|blueprint|microchip|silicon die|"
    r"circuit board|antenna|cable|microscope|radio set)\b",
    re.IGNORECASE,
)

# Human figure depiction indicators in visual descriptions
PERSON_DEPICTION_REGEX = re.compile(
    r"\b(portrait|face|man|woman|person|figure|standing|speaking|talking|seated|sitting|walking|"
    r"podium|officer|general|leader|commander|elder|aide|delegates|crowd|audience)\b",
    re.IGNORECASE,
)

# Landmark / building patterns that shouldn't override macro object shots
PLACE_BUILDING_PATTERNS = re.compile(
    r"(?:臺北公會堂|中山堂|臺灣總督府|總督府|長官公署|白宮|White House|聯合國|United Nations)",
    re.IGNORECASE,
)


def detect_real_world_footage_target(narration: str, visual_desc: str = "", mode: str = "balanced", topic: str = "") -> tuple[str | None, str]:
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
                    if not re.search(r"\b(hall|building|exterior|interior|auditorium|facade|architecture)\b", visual_desc, flags=re.IGNORECASE):
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
        inst_match = re.search(r"([\u4e00-\u9fa5]{2,12}(?:學院|大學|研究所|委員會|議事堂|議會|法院|公署|中樞|大樓|中心))", comb_text)
        if inst_match:
            candidate = inst_match.group(1).strip()
            candidate = re.sub(r"^(?:他在|他在這個|在這個|這是一個|我們的|身為|在|進入|出任|參加|加入|成立了|創立了|透過|關於)", "", candidate).strip()
            GENERIC_STOP = ("我們的社會", "這個世界", "現代社會", "日常生活", "社會大眾", "委員會", "中心", "法院", "大學", "學院", "議會", "議事堂")
            if len(candidate) >= 3 and candidate not in GENERIC_STOP:
                pref_src = "wikimedia"
                return candidate, pref_src

    # 4. Aggressive mode: extract concrete technical / device keywords
    if mode == "aggressive":
        from providers.stock_client import extract_stock_search_keywords
        kws = extract_stock_search_keywords(visual_desc or narration)
        if kws and kws[0] not in ("modern technology", "clean energy landscape", "nature landscape"):
            return kws[0], "wikimedia"

    return None, "ai"


def direct_scenes(topic: str, raw: list[dict], bible: dict, settings: dict, client: LLMClient,
                  progress=None) -> list[Scene]:
    batch = int(settings.get("scenes", {}).get("llm_batch_size", 8))
    ent_names = [e["name"] for e in bible.get("entities", [])]
    directions: dict[int, dict] = {}
    for b in range(0, len(raw), batch):
        chunk = raw[b:b + batch]
        lines = "\n".join(f'{s["scene_id"]}. [{s["section"]}] {s["narration"]}' for s in chunk)
        prompt = (f"Video topic: {topic}\nRecurring entities: {ent_names}\n\nScenes:\n{lines}\n\n"
                  "For EVERY scene id return a visual plan. JSON shape:\n"
                  '{"scenes": [{"id": 1, "visual_description": "one concrete photographable shot: subject, action, setting", '
                  '"visual_type": "image or diagram", "importance": 0.0-1.0, "motion_potential": 0.0-1.0, '
                  '"narrative_emphasis": 0.0-1.0, "camera_motion": "one of ' + "|".join(CAMERA_MOTIONS) + '", '
                  '"entities": ["names from recurring entities used in this shot"], '
                  '"callout_text": "for scenes with a key metric, technical term, or core insight, a concise fOx Hsiao style kinetic callout card in Traditional Chinese formatted as TAG | KEY_TERM_OR_NUMBER | SHORT_CONTEXT (e.g. 📊 關鍵規模數據 | 八千尊陶俑 | 秦始皇陵地下軍團奇蹟), or empty string", '
                  '"phase_turn_text": "for the opening scene of a new section/phase, a dramatic 8-18 character critical turning title or question in Traditional Chinese that foretells the next phase of the story (e.g. 關鍵真相：客廳 AI 革命), otherwise empty string"}]}\n'
                  "Vary shot sizes (wide, medium, close-up, macro, aerial). Never request readable text or logos on images. "
                  "Use phase_turn_text at key section turns to foretell the dramatic direction of the next phase.")

        def val(d, ids=[s["scene_id"] for s in chunk]):
            got = {int(x.get("id", -1)): x for x in d.get("scenes", []) if isinstance(x, dict)}
            if len([i for i in ids if i in got and got[i].get("visual_description")]) < max(1, int(len(ids) * 0.7)):
                raise ValueError(f"only {len(got)} of {len(ids)} scenes returned")
            return got

        try:
            directions.update(client.json(prompt, SYSTEM, temperature=0.6, max_tokens=4096, validate=val))
        except Exception as e:
            log.warning("Visual direction batch %d failed (%s); using narration as description", b // batch + 1, e)
        if progress:
            progress(min(b + batch, len(raw)), len(raw))

    hints = [directions.get(s["scene_id"], {}).get("camera_motion") for s in raw]
    motions = choose_motions(len(raw), seed=len(raw), hints=hints)
    scenes = []
    for s, motion in zip(raw, motions):
        d = directions.get(s["scene_id"], {})
        vt = d.get("visual_type", "image")
        phase_turn = (d.get("phase_turn_text") or "").strip()
        callout_txt = (d.get("callout_text") or "").strip()
        is_first_in_sec = not scenes or scenes[-1].section != s["section"]
        if is_first_in_sec and not phase_turn and len(scenes) > 0:
            phase_turn = extract_phase_turn_text(s["section"], s["narration"], topic)

        auto_stock_mode = settings.get("images", {}).get("auto_stock_mode") or settings.get("auto_stock_mode", "balanced")
        search_kw = (d.get("search_keyword") or "").strip()
        media_src = (d.get("media_source") or "ai").strip()
        if not search_kw and auto_stock_mode != "disabled":
            auto_kw, auto_src = detect_real_world_footage_target(
                s["narration"],
                visual_desc=(d.get("visual_description") or ""),
                mode=auto_stock_mode,
                topic=topic
            )
            if auto_kw:
                search_kw = auto_kw
                media_src = auto_src
        if search_kw and media_src not in ("youtube_snippet", "youtube_screenshot", "wikimedia", "stock"):
            media_src = "wikimedia" if auto_stock_mode == "wikimedia_only" else "youtube_snippet"

        scenes.append(Scene(
            scene_id=s["scene_id"], section=s["section"], narration=s["narration"],
            estimated_duration=s["estimated_duration"],
            visual_type=vt if vt in ("image", "diagram") else "image",
            visual_description=(d.get("visual_description") or s["narration"])[:600],
            camera_motion=motion,
            importance=_clamp01(d.get("importance")), motion_potential=_clamp01(d.get("motion_potential")),
            narrative_emphasis=_clamp01(d.get("narrative_emphasis")),
            entities=[e for e in d.get("entities", []) if e in ent_names] if isinstance(d.get("entities"), list) else [],
            callout_text=callout_txt or None,
            callout_type="fox_card" if callout_txt else None,
            phase_turn_text=phase_turn or None,
            search_keyword=search_kw or None,
            media_source=media_src if search_kw else "ai",
            transition=settings.get("rendering", {}).get("transition", "crossfade"),
        ))
    # section openings get a fade-through-black for rhythm; everything else uses the default
    # Presenter scenes always crossfade smoothly into content, never dip to black
    for prev, cur in zip(scenes, scenes[1:]):
        if cur.section != prev.section:
            is_prev_presenter = getattr(prev, "is_presenter", False) or getattr(prev, "visual_type", "") == "talking_head"
            if not is_prev_presenter:
                prev.transition = "fadeblack"
    return scenes
