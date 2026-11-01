"""AI Short Drama Agent (AI 微短劇創作引擎).

Inspired by professional AI short drama workflows (e.g. 蝦說AI / 小金老師):
1. 3-Beat Golden Structure: 0-3s Hook -> 10-20s Tension/Stakes -> 35-50s Climax/Payoff
2. Character Consistency Turnaround Roster (2-3 distinct characters with visual & vocal personas)
3. Shot-by-shot Screenplay Breakdown with precise character dialogue, actions & cinematic angles
4. Multi-Character Voice Assignment
5. Dramatic Impact Hit SFX & 9:16 / 16:9 Aspect Ratio Support
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from core.taiwan_mandarin import TAIWAN_MANDARIN_SYSTEM_PROMPT, enforce_taiwan_mandarin
from providers.llm import LLMClient

log = logging.getLogger(__name__)

# Pre-packaged short drama formula templates
DRAMA_FORMULAS = {
    "workplace_revenge": {
        "id": "workplace_revenge",
        "name": "職場逆襲打臉（如《開除我？那套AI是我寫的》）",
        "hook_premise": "主管狂妄當眾解雇核心技術女主，宣稱新系統一個月才一千塊；女主冷靜收回管理員權限，董事長親自到場威嚴打臉",
        "beats": [
            "Beat 1 (0-3s Hook): 衝突爆發，主管居高臨下摔解僱公文，冷笑宣稱女主被AI取代",
            "Beat 2 (10-25s Tension): 女主淡定反問系統是誰寫的，主管狂妄嘲諷；女主手指輕敲鍵盤收回核心權限，辦公室警報響起",
            "Beat 3 (35-50s Payoff): 董事長大步推門而入尋找系統總架構師，當面尊稱女主為總監，主管瞬間臉色慘白軟倒"
        ],
        "default_characters": [
            {
                "name": "沈總監",
                "role": "女主角 / 隱藏核心系統總架構師",
                "gender": "female",
                "age": 28,
                "appearance": "28-year-old sleek elegant East Asian woman, sharp confident eyes, minimalist charcoal blazer, modern professional look, high detail",
                "voice_persona": "冷靜沉穩、字句分明、略帶威嚴的年輕女聲",
                "voice_provider": "ichiehchieh"
            },
            {
                "name": "王經理",
                "role": "反派主管 / 自負傲慢的中年業務主管",
                "gender": "male",
                "age": 48,
                "appearance": "48-year-old arrogant middle-aged East Asian man, receding hairline, rimless gold glasses, navy corporate suit, smug condescending expression",
                "voice_persona": "語速偏快、帶嘲諷冷笑與不耐煩的中年男聲",
                "voice_provider": "mytsaovoicemagpie"
            },
            {
                "name": "陳董",
                "role": "董事長 / 關鍵反轉掌控者",
                "gender": "male",
                "age": 60,
                "appearance": "60-year-old authoritative silver-haired Asian chairman, charcoal bespoke tailored wool overcoat, piercing commanding gaze",
                "voice_persona": "渾厚深沉、極具壓迫感與威嚴的老闆男聲",
                "voice_provider": "aurora_mandarin"
            }
        ]
    },
    "suspense_twist": {
        "id": "suspense_twist",
        "name": "懸疑極限反轉（暗室審訊與雙重佈局）",
        "hook_premise": "嫌疑人被逼入死角即將簽署認罪書，最後三秒揭曉審訊官才是真正的獵物",
        "beats": [
            "Beat 1 (0-3s Hook): 昏暗審訊室，桌上倒數計時器逼近歸零，審訊官拍桌逼迫簽字",
            "Beat 2 (10-25s Tension): 嫌疑人抬起頭露出詭異微笑，指出房間內的監控訊號早已被掉包",
            "Beat 3 (35-50s Payoff): 門外全副武裝的督察組破門而入，扣押審訊官，嫌疑人亮出特勤督察證"
        ],
        "default_characters": [
            {
                "name": "陸督察",
                "role": "男主角 / 偽裝成嫌犯的特勤高階督察",
                "gender": "male",
                "age": 32,
                "appearance": "32-year-old ruggedly handsome East Asian investigator, calm penetrating eyes, black leather jacket, faint scar on eyebrow",
                "voice_persona": "冷冽、低沉、掌控全域的青年男聲",
                "voice_provider": "mytsaovoicemagpie"
            },
            {
                "name": "趙長官",
                "role": "反派 / 內鬼審訊官",
                "gender": "male",
                "age": 52,
                "appearance": "52-year-old stern corrupted senior officer, heavy eyebags, unbuttoned police uniform, tense sweating forehead",
                "voice_persona": "急躁、沙啞且帶威脅口氣的中老年男聲",
                "voice_provider": "aurora_mandarin"
            }
        ]
    },
    "scifi_cyber": {
        "id": "scifi_cyber",
        "name": "科幻神展開（世界模型與意識覺醒）",
        "hook_premise": "頂尖工程師發現自己所處的世界只是伺服器裡運行的一千次模擬之一",
        "beats": [
            "Beat 1 (0-3s Hook): 窗外的雨滴在半空中突然定格成六角形數位代碼，警報響起",
            "Beat 2 (10-25s Tension): 虛擬管家警告即將執行記憶格式化，主角駭入底層核心日誌",
            "Beat 3 (35-50s Payoff): 主角按下手動終止鍵，玻璃大樓化為數位粒子散開，現實艙門緩緩開啟"
        ],
        "default_characters": [
            {
                "name": "林克",
                "role": "男主角 / 覺醒的AI架構師",
                "gender": "male",
                "age": 27,
                "appearance": "27-year-old intense Asian tech prodigy, glowing neural interface on temple, black cyberpunk trench coat, sharp features",
                "voice_persona": "冷靜沉著、富有穿透力的磁性男聲",
                "voice_provider": "mytsaovoicemagpie"
            },
            {
                "name": "艾娃",
                "role": "系統中樞語音 / 觀察者",
                "gender": "female",
                "age": 25,
                "appearance": "Ethereal translucent holographic female avatar, glowing cyan luminescence, geometric floating particle aura",
                "voice_persona": "空靈、標準且微帶機械感的空調女聲",
                "voice_provider": "ichiehchieh"
            }
        ]
    }
}




DATA_FORMULAS_PATH = Path(__file__).resolve().parent.parent / "data" / "drama_formulas.json"


def calculate_proportional_scenes(duration_sec: int) -> dict[str, int]:
    """Calculate proportional scene count based on ~4.5s per scene,
    and distribute across 3-beat structure: 15% Hook, 55% Tension, 30% Payoff/Climax.
    """
    total = max(4, round(duration_sec / 4.5))
    hook = max(1, round(total * 0.15))
    climax = max(1, round(total * 0.30))
    tension = max(2, total - hook - climax)
    return {
        "total": total,
        "hook": hook,
        "tension": tension,
        "climax": climax,
    }


def load_all_formulas() -> dict[str, Any]:
    """Load built-in formulas and merge with custom formulas from data/drama_formulas.json."""
    res = {}
    for k, v in DRAMA_FORMULAS.items():
        entry = dict(v)
        entry["is_custom"] = False
        res[k] = entry

    if DATA_FORMULAS_PATH.exists():
        try:
            with open(DATA_FORMULAS_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                items = loaded if isinstance(loaded, list) else list(loaded.values())
                for item in items:
                    fid = item.get("id")
                    if fid and fid not in DRAMA_FORMULAS:
                        item_copy = dict(item)
                        item_copy["is_custom"] = True
                        res[fid] = item_copy
        except Exception as e:
            log.warning("Could not read custom formulas from %s: %s", DATA_FORMULAS_PATH, e)
    return res


def save_custom_formula(data: dict[str, Any]) -> dict[str, Any]:
    """Save or update a custom formula into data/drama_formulas.json."""
    from generators.character_manager import slugify_character
    import time

    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Formula name is required")

    fid = (data.get("id") or "").strip()
    if not fid:
        fid = slugify_character(name) or f"custom_{int(time.time())}"
    if fid in DRAMA_FORMULAS:
        raise ValueError(f"Cannot overwrite built-in formula '{fid}'")

    hook_premise = (data.get("hook_premise") or data.get("basic_plot") or "").strip()
    beats = data.get("beats") or [
        "Beat 1 (0-3s Hook): 衝突爆發震撼開場",
        "Beat 2 (10-25s Tension): 危機加深與多輪語言交鋒",
        "Beat 3 (35-50s Payoff): 絕殺反轉與打臉收尾",
    ]
    chars = data.get("default_characters") or []
    for idx, c in enumerate(chars):
        if not c.get("id"):
            c["id"] = slugify_character(c.get("name") or f"char_{idx+1}")
        if not c.get("voice_provider"):
            c["voice_provider"] = "ichiehchieh" if c.get("gender") == "female" else "mytsaovoicemagpie"

    formula_obj = {
        "id": fid,
        "name": name,
        "hook_premise": hook_premise,
        "character_count": len(chars),
        "beats": beats,
        "default_characters": chars,
        "default_script": data.get("default_script", ""),
        "is_custom": True,
    }

    existing = []
    if DATA_FORMULAS_PATH.exists():
        try:
            with open(DATA_FORMULAS_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                existing = loaded if isinstance(loaded, list) else list(loaded.values())
        except Exception as e:
            log.warning("Error reading %s: %s", DATA_FORMULAS_PATH, e)

    updated = [f for f in existing if f.get("id") != fid]
    updated.append(formula_obj)

    DATA_FORMULAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FORMULAS_PATH, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)

    return formula_obj


def delete_custom_formula(formula_id: str) -> bool:
    """Delete a custom formula by ID from data/drama_formulas.json."""
    if formula_id in DRAMA_FORMULAS:
        raise ValueError("Cannot delete built-in formula template")
    if not DATA_FORMULAS_PATH.exists():
        return False

    existing = []
    try:
        with open(DATA_FORMULAS_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            existing = loaded if isinstance(loaded, list) else list(loaded.values())
    except Exception as e:
        log.warning("Error reading %s: %s", DATA_FORMULAS_PATH, e)
        return False

    orig_len = len(existing)
    filtered = [f for f in existing if f.get("id") != formula_id]
    if len(filtered) == orig_len:
        return False

    with open(DATA_FORMULAS_PATH, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)
    return True


def autocomplete_custom_formula(
    basic_plot: str,
    character_count: int = 2,
    formula_name: str = "",
    client: Optional[LLMClient] = None,
) -> dict[str, Any]:
    """Given a basic plot premise and character count (2-4), call LLM to generate:
    - Formula name (if empty)
    - 3-Beat Golden Structure
    - Detailed character roster with names, roles, gender, age, appearance prompts, and voices
    - A sample 5-6 line punchy dialogue script
    """
    char_count = max(2, min(4, int(character_count or 2)))
    from generators.character_manager import slugify_character

    prompt = f"""請為這部高節奏 AI 微短劇新公式自動補完黃金結構與角色定妝設定（繁體中文 / 台灣短劇用語）。
基本劇情大綱：{basic_plot}
公式自訂名稱：{formula_name or '自動命名'}
需求角色數量：剛好 {char_count} 位核心角色

【設計原則】：
1. 黃金三幕結構 (3 Beats)：
   - Beat 1 (0-3s Hook): 衝突爆發震撼開場，引爆第一張核心矛盾
   - Beat 2 (10-25s Tension): 危機加深與多輪語言交鋒、心理戰與伏筆部署
   - Beat 3 (35-50s Payoff): 絕殺反轉與身分底牌亮出，反派崩潰打臉
2. 剛好 {char_count} 位角色：
   - 包含主角、對手/反派，以及必要的關鍵第三方（若3-4人）
   - 每位角色給出中文名、劇本定位 (role)、性別 (female/male)、年齡
   - appearance: 詳細的英文 photorealistic 人像提示詞（年齡、外表特徵、髮型、服裝材質、光影、純肖像）
   - voice_persona: 中文聲音性格特徵（如「冷靜沉穩、字句分明、略帶威嚴的年輕女聲」）
   - voice_provider: 女性角色填 "ichiehchieh"（或 "hsiaochen"），男性年輕/中年角色填 "mytsaovoicemagpie"，權威長者男性角色填 "aurora_mandarin"
3. default_script: 包含 5~6 句精彩對白與情境動作的示範短劇劇本，每行格式為「角色名：台詞」或附帶動作情境。

請嚴格返回 JSON 格式如下：
{{
  "name": "公式名稱（如：{formula_name or '逆襲反擊'}）",
  "hook_premise": "一句話核心衝突大綱",
  "beats": [
    "Beat 1 (0-3s Hook): ...",
    "Beat 2 (10-25s Tension): ...",
    "Beat 3 (35-50s Payoff): ..."
  ],
  "default_characters": [
    {{
      "id": "char_slug",
      "name": "角色名",
      "role": "定位",
      "gender": "female or male",
      "age": 28,
      "appearance": "28-year-old sleek elegant East Asian woman, photorealistic portrait, 8k",
      "voice_persona": "聲音特徵描述",
      "voice_provider": "ichiehchieh"
    }}
  ],
  "default_script": "示範對白腳本文字..."
}}"""

    system = f"{TAIWAN_MANDARIN_SYSTEM_PROMPT}\n你是一位百萬級短劇王牌編導與導演。嚴格返回合法 JSON。"

    if client:
        try:
            from providers.llm.base import extract_json
            raw = client.text(prompt + "\nReturn ONLY the JSON object.", system=system, temperature=0.7, max_tokens=2500)
            data = extract_json(raw)
            if data and data.get("default_characters"):
                for idx, c in enumerate(data.get("default_characters", [])):
                    if not c.get("id"):
                        c["id"] = slugify_character(c.get("name") or f"char_{idx+1}")
                    if not c.get("voice_provider"):
                        c["voice_provider"] = "ichiehchieh" if c.get("gender") == "female" else "mytsaovoicemagpie"
                data["character_count"] = len(data["default_characters"])
                return data
        except Exception as ex:
            log.warning("Autocomplete LLM note: %s; using structured fallback", ex)

    # Heuristic Fallback
    fallback_chars = []
    if char_count == 2:
        fallback_chars = [
            {
                "id": "lead_heroine",
                "name": "林芯怡",
                "role": "女主角 / 冷靜強勢受害者",
                "gender": "female",
                "age": 26,
                "appearance": "26-year-old sleek elegant East Asian woman, sharp intelligent eyes, dark tailored blouse, stylish modern look, studio lighting, photorealistic portrait",
                "voice_persona": "冷靜沉著、聲音清晰且帶有不卑不亢的堅定感",
                "voice_provider": "ichiehchieh"
            },
            {
                "id": "antagonist_boss",
                "name": "張豪",
                "role": "反派 / 居高臨下的自負對手",
                "gender": "male",
                "age": 45,
                "appearance": "45-year-old arrogant middle-aged East Asian man, silk shirt, heavy gold ring, smug cynical smirk, dramatic contrast lighting, photorealistic portrait",
                "voice_persona": "語速沉緩、略帶威脅與輕浮的中年男聲",
                "voice_provider": "mytsaovoicemagpie"
            }
        ]
    elif char_count == 3:
        fallback_chars = [
            {
                "id": "lead_heroine",
                "name": "林芯怡",
                "role": "女主角 / 隱藏身分的關鍵當事人",
                "gender": "female",
                "age": 26,
                "appearance": "26-year-old sleek elegant East Asian woman, sharp intelligent eyes, dark tailored blouse, studio lighting, photorealistic portrait",
                "voice_persona": "冷靜沉著、聲音清晰且帶有不卑不亢的堅定感",
                "voice_provider": "ichiehchieh"
            },
            {
                "id": "antagonist_boss",
                "name": "張豪",
                "role": "反派 / 自負壓迫者",
                "gender": "male",
                "age": 45,
                "appearance": "45-year-old arrogant middle-aged East Asian man, silk shirt, heavy gold ring, smug smirk, photorealistic portrait",
                "voice_persona": "語速沉緩、略帶威脅與輕浮的中年男聲",
                "voice_provider": "mytsaovoicemagpie"
            },
            {
                "id": "key_authority",
                "name": "趙特助",
                "role": "權威介入者 / 幕後實力派代表",
                "gender": "male",
                "age": 50,
                "appearance": "50-year-old authoritative East Asian executive in black tailored trench coat, silver-rimmed glasses, stern piercing gaze, cinematic lighting",
                "voice_persona": "威嚴沉穩、字句如山的老闆男聲",
                "voice_provider": "aurora_mandarin"
            }
        ]
    else:
        fallback_chars = [
            {
                "id": "lead_heroine",
                "name": "林芯怡",
                "role": "女主角",
                "gender": "female",
                "age": 26,
                "appearance": "26-year-old sleek elegant East Asian woman, sharp intelligent eyes, dark tailored blouse, photorealistic portrait",
                "voice_persona": "冷靜沉著、聲音清晰",
                "voice_provider": "ichiehchieh"
            },
            {
                "id": "antagonist_boss",
                "name": "張豪",
                "role": "反派",
                "gender": "male",
                "age": 45,
                "appearance": "45-year-old arrogant East Asian man, silk shirt, smug smirk, photorealistic portrait",
                "voice_persona": "略帶威脅的中年男聲",
                "voice_provider": "mytsaovoicemagpie"
            },
            {
                "id": "supporting_witness",
                "name": "小雨",
                "role": "知情目擊者",
                "gender": "female",
                "age": 23,
                "appearance": "23-year-old nervous East Asian woman, casual cardigan, fearful eyes, photorealistic portrait",
                "voice_persona": "焦慮急促的青年女聲",
                "voice_provider": "hsiaochen"
            },
            {
                "id": "key_authority",
                "name": "趙特助",
                "role": "權威介入者",
                "gender": "male",
                "age": 50,
                "appearance": "50-year-old authoritative East Asian executive in black trench coat, stern piercing gaze, cinematic lighting",
                "voice_persona": "威嚴沉穩的老闆男聲",
                "voice_provider": "aurora_mandarin"
            }
        ]

    return {
        "name": formula_name or "極致反轉新篇章",
        "hook_premise": basic_plot,
        "character_count": char_count,
        "beats": [
            f"Beat 1 (0-3s Hook): 危機降臨，{fallback_chars[1]['name']}強勢逼迫，{fallback_chars[0]['name']}陷入絕境但目光堅定",
            f"Beat 2 (10-25s Tension): 雙方激烈對峙與條件交鋒，{fallback_chars[0]['name']}暗中啟動反制手段",
            f"Beat 3 (35-50s Payoff): 真相爆發，{fallback_chars[-1]['name']}強勢現身掀開底牌，局面徹底反轉"
        ],
        "default_characters": fallback_chars,
        "default_script": f"{fallback_chars[1]['name']}冷笑將協議拍在桌上：「今天不簽，妳就別想走出這扇門！」\n{fallback_chars[0]['name']}神情平靜，緩緩抬頭：「你真以為你掌握了全局？」\n{fallback_chars[1]['name']}大笑：「在這條街上，我說的話就是規矩！」\n大門突然被重重推開，{fallback_chars[-1]['name']}帶著護衛大步走入：「張豪，是誰給你的膽子，動我們的人？！」\n{fallback_chars[0]['name']}從容起身：「遊戲結束了。」"
    }


def generate_drama_script_for_duration(
    topic: str,
    formula_key: str = "workplace_revenge",
    duration_sec: int = 50,
    characters: Optional[list[dict[str, Any]]] = None,
    client: Optional[LLMClient] = None,
) -> dict[str, Any]:
    """Generate structured screenplay script tailored to target duration (3-4 scenes for 50s, 5-6 scenes for 90s).
    Returns {"title": str, "tagline": str, "duration_seconds": int, "scenes_count": int, "scenes": list[dict], "script_text": str, "characters": list[dict]}
    """
    all_formulas = load_all_formulas()
    formula = all_formulas.get(formula_key) or DRAMA_FORMULAS.get(formula_key, DRAMA_FORMULAS["workplace_revenge"])
    active_characters = characters if (characters and len(characters) > 0) else formula["default_characters"]
    pacing = calculate_proportional_scenes(duration_sec)
    target_scenes_count = pacing["total"]
    hook_count = pacing["hook"]
    tension_count = pacing["tension"]
    climax_count = pacing["climax"]

    spk_lead = active_characters[0].get("name", "沈總監")
    spk_villain = active_characters[1].get("name", "王經理") if len(active_characters) > 1 else "主管"
    spk_boss = active_characters[2].get("name", "陳董") if len(active_characters) > 2 else "董事長"

    char_desc = "\n".join([f"- {c.get('name')} ({c.get('role', '角色')}): {c.get('gender', 'unknown')}, {c.get('appearance', '')}" for c in active_characters])

    prompt = f"""請為這部高節奏 AI 微短劇創作專屬劇本（繁體中文 / 台灣用語）。
劇本主題：{topic}
爽劇公式：{formula['name']}
目標時長：{duration_sec} 秒（請嚴格分配成剛好 {target_scenes_count} 個核心戲劇場景）
出場角色：
{char_desc}

【微短劇節奏原則（黃金三幕 15% / 55% / 30% 分配）】：
- 總時長 {duration_sec} 秒，劃分為剛好 {target_scenes_count} 個戲劇場景。
- 第 1 ~ {hook_count} 場（Hook 開場衝突，約前15%）：0-3秒內第一句台詞必須極具衝擊力，迅速建立核心壓迫與矛盾。
- 第 {hook_count + 1} ~ {hook_count + tension_count} 場（Tension 危機升級與多次語言交鋒，約中段55%）：反派步步進逼嘲諷、主角冷靜反問與布局，多輪語言心理戰，節奏緊咬不拖沓。
- 第 {hook_count + tension_count + 1} ~ {target_scenes_count} 場（Payoff 絕殺反轉與收尾打臉，約後段30%）：底牌亮出、權威登場、反派心理崩潰跪地求饒、主角從容離場。
- 台詞必須簡潔有力，角色性格鮮明，禁止任何無效廢話。

請嚴格返回 JSON 格式如下：
{{
  "title": "{topic}",
  "tagline": "一句話金句",
  "scenes": [
    {{
      "scene_id": 1,
      "beat_name": "衝突開場",
      "speaker": "{spk_villain}",
      "action_summary": "主管居高臨下將解僱公文狠狠摔在桌面上冷笑",
      "dialogues": [
        {{"speaker": "{spk_villain}", "text": "從今天起，妳被AI取代了。新系統一個月才一千塊。妳呢？"}},
        {{"speaker": "{spk_lead}", "text": "你確定要換掉我？那套系統的核心架構……"}}
      ]
    }}
  ]
}}"""

    system = f"{TAIWAN_MANDARIN_SYSTEM_PROMPT}\n你是一位精通字字珠璣、百萬播放量爆款微短劇的頂尖編劇。只返回合法 JSON 物件。"

    if client:
        try:
            from providers.llm.base import extract_json
            raw = client.text(prompt + "\nReturn ONLY the JSON object.", system=system, temperature=0.7, max_tokens=2500)
            data = extract_json(raw)
            if data and data.get("scenes") and len(data.get("scenes")) >= 2:
                script_text = f"# 《{data.get('title', topic)}》\n\n"
                for sc in data.get("scenes", []):
                    script_text += f"【第{sc.get('scene_id')}場：{sc.get('beat_name', '戲劇場景')}】\n"
                    if sc.get("action_summary"):
                        script_text += f"*(情境：{sc.get('action_summary')})*\n"
                    for d in sc.get("dialogues", []):
                        script_text += f"{d.get('speaker')}：{d.get('text')}\n"
                    script_text += "\n"
                data["script_text"] = script_text.strip()
                data["duration_seconds"] = duration_sec
                data["scenes_count"] = len(data.get("scenes", []))
                data["characters"] = active_characters
                return data
        except Exception as e:
            log.warning("LLM script generation note: %s; using curated template", e)

    # Curated High-Grade Fallback templates
    if target_scenes_count <= 4:
        # 50s standard (4 scenes)
        scenes = [
            {
                "scene_id": 1,
                "beat_name": "衝突開場",
                "speaker": spk_villain,
                "action_summary": f"{spk_villain}居高臨下將公文摔在桌上冷笑",
                "dialogues": [
                    {"speaker": spk_villain, "text": "從今天起，妳被AI取代了。新系統一個月才一千塊。妳呢？"},
                    {"speaker": spk_lead, "text": "你確定要換掉我？那套系統的核心架構……"}
                ]
            },
            {
                "scene_id": 2,
                "beat_name": "傲慢交鋒",
                "speaker": spk_villain,
                "action_summary": f"{spk_villain}拍桌咆哮，{spk_lead}神情自若按下Enter鍵撤銷權限",
                "dialogues": [
                    {"speaker": spk_villain, "text": "別拿資歷壓我！字是我簽的，權限我說了算！"},
                    {"speaker": spk_lead, "text": "好。希望你手腳夠快。管理員權限，我收回了。"}
                ]
            },
            {
                "scene_id": 3,
                "beat_name": "反轉降臨",
                "speaker": spk_boss,
                "action_summary": f"玻璃大門猛烈推開，{spk_boss}怒氣沖沖大步走入",
                "dialogues": [
                    {"speaker": spk_boss, "text": "住手！你知不知道你在跟誰講話？！"},
                    {"speaker": spk_boss, "text": f"總部剛剛估值十億的AI專利，唯一的所有人就是{spk_lead}！"}
                ]
            },
            {
                "scene_id": 4,
                "beat_name": "絕殺打臉",
                "speaker": spk_lead,
                "action_summary": f"{spk_lead}優雅起身拎起公事包，{spk_villain}雙膝發軟跪坐在地",
                "dialogues": [
                    {"speaker": spk_lead, "text": f"{spk_villain}，一個月一千塊的系統，祝你維護愉快。"},
                    {"speaker": spk_villain, "text": f"{spk_lead}……我錯了！求求妳給公司一條活路！"}
                ]
            }
        ]
    else:
        # 90s extended (6 scenes)
        scenes = [
            {
                "scene_id": 1,
                "beat_name": "暗潮洶湧",
                "speaker": spk_villain,
                "action_summary": f"早會上{spk_villain}當眾將解聘通知甩在會議桌中央",
                "dialogues": [
                    {"speaker": spk_villain, "text": "從今天起，研發部全體由AI系統接管。妳被開除了！"},
                    {"speaker": spk_lead, "text": "王經理，這份系統的底層代碼，你連一行都沒看過吧？"}
                ]
            },
            {
                "scene_id": 2,
                "beat_name": "落井下石",
                "speaker": spk_villain,
                "action_summary": f"{spk_villain}指著門口冷嘲熱諷，同事竊竊私語",
                "dialogues": [
                    {"speaker": spk_villain, "text": "能賺錢就行！新AI模型一個月才一千塊，妳憑什麼拿年薪三百萬？"},
                    {"speaker": spk_lead, "text": "那是因為你們買的，只是我三年前開源的測試殘卷。"}
                ]
            },
            {
                "scene_id": 3,
                "beat_name": "權限撤銷",
                "speaker": spk_lead,
                "action_summary": f"{spk_lead}端起咖啡輕敲鍵盤，終端螢幕紅光警報狂閃",
                "dialogues": [
                    {"speaker": spk_villain, "text": "胡言亂語！保安呢？立刻把她轟出去！"},
                    {"speaker": spk_lead, "text": "不用叫保安。核心授權秘鑰，我已經全部註銷了。祝你們系統崩潰愉快。"}
                ]
            },
            {
                "scene_id": 4,
                "beat_name": "系統全面崩盤",
                "speaker": spk_villain,
                "action_summary": f"辦公室電話狂響，伺服器發出刺耳警報聲",
                "dialogues": [
                    {"speaker": spk_villain, "text": "怎麼回事？！為什麼客戶訂單全空了？！快恢復啊！"},
                    {"speaker": spk_lead, "text": "沒有我的主密鑰，整個雲端每十分鐘就會自動格式化。"}
                ]
            },
            {
                "scene_id": 5,
                "beat_name": "總部巨頭親臨",
                "speaker": spk_boss,
                "action_summary": f"{spk_boss}帶著法務團隊快步推門而入，神色震怒",
                "dialogues": [
                    {"speaker": spk_boss, "text": f"混帳東西！是誰允許你對{spk_lead}無禮的？！"},
                    {"speaker": spk_boss, "text": f"集團剛剛用八億美金收購這套架構，{spk_lead}是全體董事會的首席技術長！"}
                ]
            },
            {
                "scene_id": 6,
                "beat_name": "終局打臉",
                "speaker": spk_lead,
                "action_summary": f"{spk_villain}面如死灰癱倒在碎紙片中，{spk_lead}昂首步向總裁辦公室",
                "dialogues": [
                    {"speaker": spk_lead, "text": "王經理，一個月一千塊的系統，就留給你慢慢維修了。"},
                    {"speaker": spk_villain, "text": "沈總監……董事長……我瞎了狗眼！求求你們放我一條生路！"}
                ]
            }
        ]

    script_text = f"# 《{topic}》\n\n"
    for sc in scenes:
        script_text += f"【第{sc.get('scene_id')}場：{sc.get('beat_name', '戲劇場景')}】\n"
        if sc.get("action_summary"):
            script_text += f"*(情境：{sc.get('action_summary')})*\n"
        for d in sc.get("dialogues", []):
            script_text += f"{d.get('speaker')}：{d.get('text')}\n"
        script_text += "\n"

    return {
        "title": topic,
        "tagline": "一個鏡頭好看很容易，難的是十個鏡頭都在打你的臉。",
        "duration_seconds": duration_sec,
        "scenes_count": len(scenes),
        "scenes": scenes,
        "script_text": script_text.strip(),
        "characters": active_characters
    }


def parse_dialogue_script_to_shots(
    script_text: str,
    active_characters: list[dict[str, Any]],
    duration_sec: int = 50,
) -> list[dict[str, Any]]:
    """Convert raw user script/dialogue text directly into structured short drama shots."""
    import re
    if not script_text or not script_text.strip():
        return []
    lines = [ln.strip() for ln in script_text.strip().splitlines() if ln.strip()]
    parsed_dialogues = []
    char_names = [c.get("name") for c in active_characters if c.get("name")]
    default_spk = char_names[0] if char_names else "主角"

    for ln in lines:
        if ln.startswith("#") or ln.startswith("//"):
            continue
        m = re.match(r"^([^\s:：]{1,15})\s*[:：]\s*(.+)$", ln)
        if m:
            spk = m.group(1).strip()
            diag = m.group(2).strip()
            if diag:
                parsed_dialogues.append((spk, diag))
        else:
            if "：" in ln or ":" in ln:
                parts = re.split(r"[:：]", ln, maxsplit=1)
                if len(parts) == 2 and len(parts[0].strip()) <= 15 and parts[1].strip():
                    parsed_dialogues.append((parts[0].strip(), parts[1].strip()))
            elif len(ln) > 1:
                spk = char_names[len(parsed_dialogues) % len(char_names)] if char_names else default_spk
                parsed_dialogues.append((spk, ln))

    if not parsed_dialogues:
        return []

    num_shots = len(parsed_dialogues)
    per_shot_dur = round(max(3.0, duration_sec / max(1, num_shots)), 1)
    shots = []

    for i, (spk, diag) in enumerate(parsed_dialogues, 1):
        if i <= max(1, num_shots // 4):
            beat = "hook"
            cam = "push_in" if i == 1 else "slow_zoom_in"
            hit = False
            sfx = "paper_slam" if i == 1 else None
        elif i >= num_shots - 1:
            beat = "climax"
            cam = "push_in_fast" if i == num_shots - 1 else "slow_pull_back"
            hit = True if i == num_shots - 1 else False
            sfx = "bass_drop" if hit else "cinematic_outro"
        else:
            beat = "tension"
            cam = ["dolly_left", "rack_focus", "static", "close_up"][i % 4]
            hit = False
            sfx = "keyboard_click" if (i % 2 == 1) else None

        c_info = next((c for c in active_characters if c.get("name") == spk), {})
        app = c_info.get("appearance") or c_info.get("appearance_prompt") or f"Cinematic East Asian character {spk}"

        shots.append({
            "shot_id": i,
            "dramatic_beat": beat,
            "speaker": spk,
            "dialogue": diag,
            "action": f"{spk}情緒飽滿地說出對白",
            "camera_motion": cam,
            "shot_size": "close_up" if hit else "medium_shot",
            "visual_description": f"Cinematic shot of {spk}, {app}, high tension drama film still, 8k photorealistic",
            "estimated_duration": per_shot_dur,
            "sfx_cue": sfx,
            "has_impact_hit": hit,
        })
    return shots


def plan_drama_production(
    topic: str,
    formula_key: str = "workplace_revenge",
    duration_sec: int = 50,
    aspect_ratio: str = "9:16",
    user_premise: Optional[str] = None,
    client: Optional[LLMClient] = None,
    settings: Optional[dict] = None,
    custom_characters: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Generate a complete short drama production package:
    1. Narrative 3-Beat Hook/Tension/Climax breakdown
    2. Character Turnaround Roster (Appearance, Traits & Vocal assignment)
    3. Shot-by-shot Script with Character Dialogue lines & Cinematic Actions
    """
    all_formulas = load_all_formulas()
    formula = all_formulas.get(formula_key) or DRAMA_FORMULAS.get(formula_key, DRAMA_FORMULAS["workplace_revenge"])
    active_characters = custom_characters if (custom_characters and len(custom_characters) > 0) else formula["default_characters"]
    pacing = calculate_proportional_scenes(duration_sec)
    target_shots = pacing["total"]
    hook_shots = pacing["hook"]
    tension_shots = pacing["tension"]
    climax_shots = pacing["climax"]

    # Try parsing user-supplied script directly if structured with dialogues
    user_parsed_shots = parse_dialogue_script_to_shots(user_premise or "", active_characters, duration_sec)
    if user_parsed_shots and len(user_parsed_shots) >= 3 and (not client or formula_key == "custom"):
        log.info("Directly using %d parsed script shots for drama '%s'", len(user_parsed_shots), topic)
        return {
            "title": topic,
            "tagline": f"{active_characters[0].get('name', '主角')}的命運對決",
            "characters": active_characters,
            "shots": user_parsed_shots,
        }

    # Fast-path for the flagship reference video template 《開除我？那套AI是我寫的》
    if formula_key == "workplace_revenge" and (not user_premise or user_premise.strip() == "") and any(k in topic for k in ("開除", "AI是我寫", "職場", "那套AI", "取代")):
        log.info("Loading reference master drama package for '%s'", topic)
        return {
            "title": "開除我？那套AI是我寫的",
            "tagline": "一個鏡頭好看很容易，難的是十個鏡頭都在打你的臉。",
            "characters": active_characters,
            "shots": [
                {
                    "shot_id": 1,
                    "dramatic_beat": "hook",
                    "speaker": "王經理",
                    "dialogue": "從今天起，妳被AI取代了。",
                    "action": "王經理居高臨下將解雇通知狠狠摔在桌面上，嘴角揚起傲慢冷笑",
                    "camera_motion": "push_in",
                    "shot_size": "medium_close_up",
                    "visual_description": "Close-up of arrogant 48-year-old Asian manager in navy suit slamming dismissal letter on sleek wooden desk, high tension, cinematic office lighting",
                    "estimated_duration": 4.0,
                    "sfx_cue": "paper_slam",
                    "has_impact_hit": False
                },
                {
                    "shot_id": 2,
                    "dramatic_beat": "hook",
                    "speaker": "王經理",
                    "dialogue": "新系統一個月才一千塊。妳呢？",
                    "action": "王經理雙手插口袋，眼神不屑地掃視女主角",
                    "camera_motion": "slow_zoom_in",
                    "shot_size": "close_up",
                    "visual_description": "Tight close-up of arrogant manager smirking with rimless glasses reflecting computer screen light, dramatic shadow",
                    "estimated_duration": 4.0,
                    "sfx_cue": None,
                    "has_impact_hit": False
                },
                {
                    "shot_id": 3,
                    "dramatic_beat": "tension",
                    "speaker": "沈總監",
                    "dialogue": "你確定要換掉我？那套系統的核心架構……",
                    "action": "沈總監端坐辦公椅，神色自若，雙眼直視王經理",
                    "camera_motion": "static",
                    "shot_size": "medium_shot",
                    "visual_description": "Over-the-shoulder shot of calm, sharp 28-year-old female tech lead in minimalist charcoal blazer sitting in modern tech office",
                    "estimated_duration": 4.5,
                    "sfx_cue": None,
                    "has_impact_hit": False
                },
                {
                    "shot_id": 4,
                    "dramatic_beat": "tension",
                    "speaker": "王經理",
                    "dialogue": "別拿資歷壓我！字是我簽的，權限我說了算！",
                    "action": "王經理指著沈總監鼻子，情緒激動咆哮",
                    "camera_motion": "dolly_left",
                    "shot_size": "medium_close_up",
                    "visual_description": "Dramatic side angle of agitated male manager pointing finger aggressively across meeting table, high contrast lighting",
                    "estimated_duration": 4.5,
                    "sfx_cue": None,
                    "has_impact_hit": False
                },
                {
                    "shot_id": 5,
                    "dramatic_beat": "tension",
                    "speaker": "沈總監",
                    "dialogue": "好。希望你手腳夠快。",
                    "action": "沈總監優雅地在機械鍵盤上按下回車鍵，終端顯示「權限已撤銷」",
                    "camera_motion": "rack_focus",
                    "shot_size": "close_up",
                    "visual_description": "Extreme close-up of slender female hand pressing glowing mechanical enter key, red terminal error text reflecting in dark sunglasses or calm eyes",
                    "estimated_duration": 3.5,
                    "sfx_cue": "keyboard_click",
                    "has_impact_hit": False
                },
                {
                    "shot_id": 6,
                    "dramatic_beat": "climax",
                    "speaker": "陳董",
                    "dialogue": "住手！王經理，你知不知道你在跟誰講話？！",
                    "action": "辦公室大門猛然被推開，白髮威嚴的董事長帶著隨扈大步走入",
                    "camera_motion": "whip_pan",
                    "shot_size": "wide_shot",
                    "visual_description": "Wide low-angle tracking shot of authoritative 62-year-old CEO entering glass office doors with heavy step, dramatic backlight",
                    "estimated_duration": 4.5,
                    "sfx_cue": "door_slam",
                    "has_impact_hit": True
                },
                {
                    "shot_id": 7,
                    "dramatic_beat": "climax",
                    "speaker": "陳董",
                    "dialogue": "總部剛剛估值十億的AI專利，唯一的所有人就是沈總監！",
                    "action": "陳董怒不可遏將紅頭專利授權合約甩在王經理臉上",
                    "camera_motion": "push_in_fast",
                    "shot_size": "medium_shot",
                    "visual_description": "Medium shot of CEO pointing furiously at trembling manager, red patent certificate visible on table, intense cinematic atmosphere",
                    "estimated_duration": 5.0,
                    "sfx_cue": "bass_drop",
                    "has_impact_hit": True
                },
                {
                    "shot_id": 8,
                    "dramatic_beat": "climax",
                    "speaker": "沈總監",
                    "dialogue": "王經理，一個月一千塊的系統，祝你維護愉快。",
                    "action": "沈總監拎起公事包從容起身，王經理臉色慘白跌坐在地",
                    "camera_motion": "slow_pull_back",
                    "shot_size": "medium_wide",
                    "visual_description": "Wide cinematic shot of female protagonist gracefully walking out into sunny glass corridor as stunned manager collapses into chair in defeat",
                    "estimated_duration": 5.0,
                    "sfx_cue": "cinematic_outro",
                    "has_impact_hit": False
                }
            ]
        }
    
    prompt = f"""You are an elite short drama showrunner and director specializing in high-CTR, viral AI short dramas (like TikTok/Reels/Shorts 50s mini-series).
Topic / Story Premise: {topic}
Selected Formula: {formula['name']} ({formula['hook_premise']})
User Custom Notes: {user_premise or 'None'}
Target Video Duration: {duration_sec} seconds (Exactly {target_shots} dramatic shots)
Aspect Ratio: {aspect_ratio}

Golden Rules for Viral Short Dramas (參考小金老師短劇法則 - 15% Hook / 55% Tension / 30% Payoff):
1. Beat 1: Hook (First {hook_shots} shots, ~15% duration) - First line must be an explosive, shocking conflict line that arrests attention immediately.
2. Beat 2: Tension & Complication (Next {tension_shots} shots, ~55% duration) - Multiple rounds of sharp verbal sparring, stakes escalation, and trap setting.
3. Beat 3: Climax & Dramatic Reversal (Final {climax_shots} shots, ~30% duration) - Truth revealed, authority intervenes, mic-drop dialogue, humiliating defeat of the antagonist.
4. Total Characters: 2 to 3 characters max. Give each character exact appearance tags (clothing, hairstyle, facial features, age) so their face remains consistent across shots.
5. Dialogue: Snappy, razor-sharp Traditional Chinese (Taiwan Mandarin terms: 程式, 軟體, 總監, 專案, etc.). No filler.

Return JSON in this EXACT structure:
{{
  "title": "短劇劇名 (e.g. 開除我？那套AI是我寫的)",
  "tagline": "吸引人的單句金句",
  "characters": [
    {{
      "name": "角色名 (e.g. 沈總監)",
      "role": "主角 / 反派 / 翻轉者",
      "gender": "female or male",
      "age": 28,
      "appearance_prompt": "English photorealistic prompt describing face, hair, clothing, lighting consistency",
      "voice_persona": "中文聲音特徵 (e.g. 冷靜低沉年輕女聲)"
    }}
  ],
  "shots": [
    {{
      "shot_id": 1,
      "dramatic_beat": "hook",
      "speaker": "王經理",
      "dialogue": "從今天起，妳被AI取代了。新系統一個月才一千塊。妳呢？",
      "action": "王經理傲慢冷笑將解雇公文狠狠摔在桌面上，居高臨下俯視主角",
      "camera_motion": "push_in",
      "shot_size": "medium_close_up",
      "visual_description": "Cinematic shot of arrogant middle-aged manager slamming white termination paper onto modern wooden office desk, moody office lighting, 8k, photorealistic",
      "estimated_duration": 4.5,
      "sfx_cue": "paper_slam",
      "has_impact_hit": false
    }}
  ]
}}
Ensure exactly {target_shots} shots that add up to ~{duration_sec}s."""

    system = f"{TAIWAN_MANDARIN_SYSTEM_PROMPT}\nYou are an expert AI short drama scriptwriter and director. Return strictly valid JSON."

    if client:
        try:
            from providers.llm.base import extract_json
            raw = client.text(prompt + "\nReturn ONLY the JSON object.", system=system, temperature=0.7, max_tokens=2500)
            data = extract_json(raw)
            if data and data.get("shots") and len(data.get("shots")) >= 3:
                data["characters"] = active_characters
                return data
        except Exception as e:
            log.warning("LLM drama generation failed: %s; using high-grade formula template", e)

    # If user provided a script that was parsed, use it before generic fallback
    if user_parsed_shots and len(user_parsed_shots) >= 2:
        return {
            "title": topic,
            "tagline": "極限反轉，高能對決",
            "characters": active_characters,
            "shots": user_parsed_shots,
        }

    # Built-in High-Impact Fallback Package (Based directly on reference video)
    return {
        "title": "開除我？那套AI是我寫的",
        "tagline": "一個鏡頭好看很容易，難的是十個鏡頭都在打你的臉。",
        "characters": active_characters,
        "shots": [
            {
                "shot_id": 1,
                "dramatic_beat": "hook",
                "speaker": "王經理",
                "dialogue": "從今天起，妳被AI取代了。",
                "action": "王經理居高臨下將解雇通知狠狠摔在桌面上，嘴角揚起傲慢冷笑",
                "camera_motion": "push_in",
                "shot_size": "medium_close_up",
                "visual_description": "Close-up of arrogant 48-year-old Asian manager in navy suit slamming dismissal letter on sleek wooden desk, high tension, cinematic office lighting",
                "estimated_duration": 4.0,
                "sfx_cue": "paper_slam",
                "has_impact_hit": False
            },
            {
                "shot_id": 2,
                "dramatic_beat": "hook",
                "speaker": "王經理",
                "dialogue": "新系統一個月才一千塊。妳呢？",
                "action": "王經理雙手插口袋，眼神不屑地掃視女主角",
                "camera_motion": "slow_zoom_in",
                "shot_size": "close_up",
                "visual_description": "Tight close-up of arrogant manager smirking with rimless glasses reflecting computer screen light, dramatic shadow",
                "estimated_duration": 4.0,
                "sfx_cue": None,
                "has_impact_hit": False
            },
            {
                "shot_id": 3,
                "dramatic_beat": "tension",
                "speaker": "沈總監",
                "dialogue": "那套系統……不是她做的嗎？",
                "action": "同事在隔壁隔間悄悄探頭耳語，沈總監神色自若地端起咖啡杯",
                "camera_motion": "pan_left",
                "shot_size": "over_the_shoulder",
                "visual_description": "Over the shoulder view of calm 28-year-old sleek Taiwanese female engineer sipping coffee peacefully, modern tech open-plan office",
                "estimated_duration": 4.5,
                "sfx_cue": None,
                "has_impact_hit": False
            },
            {
                "shot_id": 4,
                "dramatic_beat": "tension",
                "speaker": "沈總監",
                "dialogue": "王經理，你知道那套AI是誰寫的嗎？",
                "action": "沈總監緩緩放下咖啡杯，清澈冰冷的目光直視王經理",
                "camera_motion": "slow_zoom_in",
                "shot_size": "close_up",
                "visual_description": "Sharp cinematic close-up of gorgeous 28-year-old female tech lead in dark blazer, calm piercing gaze, glowing dual-monitor reflection in eyes",
                "estimated_duration": 5.0,
                "sfx_cue": "subtle_riser",
                "has_impact_hit": False
            },
            {
                "shot_id": 5,
                "dramatic_beat": "tension",
                "speaker": "王經理",
                "dialogue": "誰寫的？重要嗎？能賺錢就行！",
                "action": "王經理不耐煩地揮手打斷，冷笑出聲",
                "camera_motion": "push_in",
                "shot_size": "medium_shot",
                "visual_description": "Medium shot of angry manager waving hands dismissively, fluorescent ambient ceiling light, cinematic contrast",
                "estimated_duration": 4.5,
                "sfx_cue": None,
                "has_impact_hit": False
            },
            {
                "shot_id": 6,
                "dramatic_beat": "reversal_action",
                "speaker": "沈總監",
                "dialogue": "管理員權限，我已經收回了。",
                "action": "沈總監右手食指優雅按下鍵盤Enter，螢幕瞬間跳出紅色權限撤銷警告",
                "camera_motion": "push_in",
                "shot_size": "close_up",
                "visual_description": "Macro shot of slender female hand pressing glowing mechanical keyboard Enter key, computer monitor turns glowing red warning screen, high tension",
                "estimated_duration": 5.0,
                "sfx_cue": "bass_drop",
                "has_impact_hit": True
            },
            {
                "shot_id": 7,
                "dramatic_beat": "reversal_arrival",
                "speaker": "陳董",
                "dialogue": "沈總監，全體董事會都在等妳主持大局。",
                "action": "厚重玻璃大門被推開，身著頂級大衣的董事長大步邁入，對著沈總監躬身示意",
                "camera_motion": "dolly_in",
                "shot_size": "wide_shot",
                "visual_description": "Cinematic wide shot of prestigious silver-haired 60-year-old CEO walking through modern glass doors flanked by security, bowing respectfully to young female lead",
                "estimated_duration": 6.0,
                "sfx_cue": "orchestral_hit",
                "has_impact_hit": True
            },
            {
                "shot_id": 8,
                "dramatic_beat": "climax_payoff",
                "speaker": "王經理",
                "dialogue": "沈……沈總監？！",
                "action": "王經理整個人如遭雷擊，手中公文袋滑落掉地，雙膝發軟靠在牆邊",
                "camera_motion": "slow_zoom_out",
                "shot_size": "close_up",
                "visual_description": "Extreme close-up of panicked manager trembling in shock, eyes wide open in sheer horror, sweat on temples, cinematic slow push",
                "estimated_duration": 4.5,
                "sfx_cue": "impact_whoosh",
                "has_impact_hit": False
            },
            {
                "shot_id": 9,
                "dramatic_beat": "payoff_outro",
                "speaker": "沈總監",
                "dialogue": "王經理，從今天起，你被公司取代了。",
                "action": "沈總監從容站起身，拿起名牌掛上胸口，昂首步向總裁辦公室",
                "camera_motion": "push_in",
                "shot_size": "medium_shot",
                "visual_description": "Hero shot of confident 28-year-old female tech director walking past stunned office colleagues into executive boardroom, lens flare, cinematic triumph",
                "estimated_duration": 5.5,
                "sfx_cue": "cinematic_outro",
                "has_impact_hit": True
            }
        ]
    }
