"""Shared prompt fragments for the writing agents."""

BANNED_PHRASES = [
    "in today's world", "in today's fast-paced", "delve", "let's dive in", "dive deep", "buckle up",
    "game-changer", "tapestry", "in conclusion", "it's important to note", "at the end of the day",
    "unlock the secrets", "embark on a journey", "fascinating world", "without further ado",
    "but here's the thing", "the answer may surprise you", "stay tuned",
]

BANNED_MAINLAND_PHRASES = [
    # 3C, tech, internet
    "視頻", "短視頻", "軟件", "硬件", "芯片", "內存", "磁盤", "服務器", "算法", "數據庫",
    "屏幕", "默認", "界面", "交互", "鏈接", "超鏈接", "互聯網", "局域網", "激光", "硅谷",
    "航天", "打印機", "複印", "數組", "宏定義", "優化", "概率", "空間站", "航天飛機",
    "航天員", "宇航員", "巡航導彈", "隱身戰機", "核聚變", "核裂變", "納米", "多普勒效應",
    # Buzzwords & slang
    "立馬", "給力", "走心", "膠水語言", "閉環", "賦能", "痛點", "抓手", "打法", "降維打擊",
    "忽悠", "吐槽", "老鐵", "小夥伴", "接地氣", "腦洞大開", "總而言之", "綜上所述", "讓我們拭目以待",
    "妥妥的", "特麼", "牛逼", "打call", "吃瓜", "帶節奏", "割韭菜", "智商稅", "高大上", "內卷",
    # Mainland translation names (foreign figures & places)
    "奧巴馬", "特朗普", "撒切爾", "普京", "澤連斯基", "戈爾巴喬夫", "斯大林", "丘吉爾",
    "艾森豪威爾", "肯尼迪", "里根", "尼克松", "基辛格", "喬布斯", "蓋茨", "扎克伯格", "貝索斯",
    "斯皮爾伯格", "達芬奇", "梵高", "畢加索", "莫奈", "肖邦", "莫扎特", "玻爾", "薛定諤",
    "開普勒", "奧本海默", "馮諾依曼", "笛卡爾", "新西蘭", "悉尼", "堪培拉", "聖何塞", "得州",
    "休斯敦", "蒙特利爾", "迪拜", "阿布扎比", "卡塔爾", "沙特", "伊斯坦布爾", "戛納", "佛羅倫薩",
    "格魯吉亞", "阿塞拜疆", "肯尼亞", "尼日利亞", "埃塞俄比亞", "索馬里", "坦桑尼亞", "莫桑比克"
]

# Universal Negative Prompt Tokens that apply to all videos & image generations:
# Enforces strictly correct human anatomy, clear high-definition facial features, and no identical faces
UNIVERSAL_ANATOMY_NEGATIVE = (
    "extra arms, extra hands, multiple arms, 4 arms, 3 arms, duplicate arms, duplicate hands, "
    "extra limbs, mutated hands, deformed fingers, extra fingers, missing fingers, fused fingers, "
    "malformed limbs, malformed hands, poorly drawn hands, floating limbs, disconnected limbs, "
    "unnatural body posture, unergonomic body, physically impossible anatomy, bad anatomy, "
    "deformed anatomy, distorted body, duplicate body parts"
)

UNIVERSAL_FACE_QUALITY_NEGATIVE = (
    "featureless face, blurry face, low quality face, indistinct facial features, blank face, "
    "melted face, deformed face, poorly drawn face, disfigured face, faceless, bad face proportions, "
    "distorted eyes, asymmetrical face, morbid facial features, missing facial features"
)

UNIVERSAL_ANTI_CLONE_NEGATIVE = (
    "multiple people with the same face, cloned faces, identical faces, duplicate faces, "
    "identical twins, triplets, clone army, copy-paste faces, identical hairstyles, "
    "identical clothing, identical expressions, repeated facial features across different people, "
    "cloned crowd, identical facial structure, lookalike group, uniform faces, identical siblings, "
    "cloned children, identical boy faces, same face syndrome"
)

UNIVERSAL_TEXT_NEGATIVE = (
    "text, watermark, logo, chinese text, chinese characters, hanzi, kanji, subtitles, "
    "typography, words, letters, signage text, billboard text, newspaper text, labels, "
    "distorted letters, faux chinese, gibberish characters, text on screens, text on signs, "
    "distorted typography, artificial glyphs, unreadable writing"
)

UNIVERSAL_QUALITY_NEGATIVE = (
    f"{UNIVERSAL_ANATOMY_NEGATIVE}, {UNIVERSAL_FACE_QUALITY_NEGATIVE}, "
    f"{UNIVERSAL_ANTI_CLONE_NEGATIVE}, {UNIVERSAL_TEXT_NEGATIVE}"
)


def build_image_system_prompt(negative_prompt: str | list[str] | None = None) -> str:
    """Builds a strict system prompt instruction for image generation backends (Gemini, Imagen, etc.).
    
    Explicitly enforces anti-cloning negative constraints, distinct individual facial diversity,
    biologically accurate anatomy, and total avoidance of malformed Chinese or English text.
    """
    full_neg = merge_negative_prompts(UNIVERSAL_QUALITY_NEGATIVE, negative_prompt)
    return (
        "You are an expert cinematic visual director and photorealistic image generator.\n"
        "CRITICAL SYSTEM DIRECTIVES & STRICT NEGATIVE CONSTRAINTS:\n"
        "1. STRICTLY NO IDENTICAL FACES / ANTI-CLONING:\n"
        "   - When multiple people, children, groups, or crowds appear in the scene, EVERY SINGLE individual "
        "MUST have a distinct, unique facial appearance, individual bone structure, different eye shape, "
        "distinct haircut or hairstyle, varied skin tone/texture, and individual personal facial expressions.\n"
        "   - NEVER generate cloned faces, identical lookalikes, duplicate triplets/twins, copy-paste features, "
        "or same face syndrome across different people in the same frame.\n"
        "2. BIOLOGICALLY ACCURATE ANATOMY:\n"
        "   - Every human figure must have strictly and exactly two natural arms, two natural hands, "
        "five fingers per hand, and natural ergonomic posture.\n"
        "3. STRICTLY NO TEXT / NO CHINESE CHARACTERS:\n"
        "   - Absolutely NO written text, no Chinese characters (漢字), no English letters, no words, no subtitles, "
        "no watermarks, and no fake gibberish typography anywhere in the image.\n"
        "   - All signboards, digital screens, monitors, blueprints, newspapers, documents, street banners, and "
        "commercial billboards must be completely blank, unwritten, or contain purely abstract visual graphics/icons "
        "with zero readable text or characters.\n"
        f"4. NEGATIVE PROMPT (STRICTLY AVOID AND EXCLUDE):\n"
        f"   {full_neg}\n"
    )


def merge_negative_prompts(*prompts: str | list[str] | None) -> str:
    """Combines negative prompt strings or lists into a unified, deduplicated comma-separated string."""
    seen = set()
    tokens = []
    for p in prompts:
        if not p:
            continue
        if isinstance(p, list):
            raw_items = p
        else:
            raw_items = str(p).split(",")
        for item in raw_items:
            clean = item.strip().strip('"').strip("'")
            if not clean:
                continue
            key = clean.lower()
            if key not in seen:
                seen.add(key)
                tokens.append(clean)
    return ", ".join(tokens)

NARRATION_RULES = f"""Rules for narration:
- Write for the ear: natural spoken sentences, varied length, mostly 8-22 words.
- Concrete examples and numbers beat vague claims. Do not invent precise statistics; prefer ranges or qualitative statements when unsure.
- No markdown, no headings, no bullet points, no emojis, no stage directions, no speaker labels.
- Do not recap the previous section; move the story forward.
- Never use these English buzzwords: {", ".join(BANNED_PHRASES)}.
- When writing in Chinese, strictly use Taiwan Traditional Chinese (台灣正體中文 / 國語詞彙) and standard Taiwan translations (台灣翻譯名稱), and never use Mainland Chinese buzzwords, tech jargon, or translation names: {", ".join(BANNED_MAINLAND_PHRASES)}.
- Strict factual grounding: Technical specifications, data rates, version features, and multipliers MUST strictly match the verified research dossier. Never guess or conflate version metrics (e.g. do not misattribute old speeds or bit rates to newer Bluetooth versions). Relative multipliers (e.g. "快上 X 倍") must mathematically agree with the referenced baseline number.
"""
