"""Action & Gesture Registry for Short Drama and Character Video Pipelines.

Provides a catalog of expressive cinematic body postures, gestures, and motions.
Enables AI Directors in Stage 4/5 to assign contextual gesture tags, and
Stage 7 MiniMax Video-01 / Hedra to animate with realistic physical movement
instead of static passport-style frontal portraits.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ActionGesture:
    tag: str                        # e.g. "pointing_forward"
    name: str                       # Display name in Traditional Chinese
    visual_prompt: str              # Visual prompt injected into Stage 5 image generation
    motion_prompt: str              # Dynamic motion prompt for Stage 7 MiniMax Video-01
    keywords: List[str]             # Dialogue / emotional keywords that trigger this gesture
    character_roles: List[str]      # Typical roles that use this gesture
    framing: str = "medium_close_up"# Recommended camera framing (medium, close_up, wide)
    intensity: float = 0.8          # Dramatic tension (0.0 - 1.0)


# Master registry of 12 distinct dramatic gestures
GESTURE_REGISTRY: Dict[str, ActionGesture] = {
    "pointing_forward": ActionGesture(
        tag="pointing_forward",
        name="強勢指責 / 鎖定前進",
        visual_prompt="pointing assertively forward toward camera with a dominant hand gesture, body angled slightly, sharp piercing eyes",
        motion_prompt="raising hand to point assertively forward with conviction, intense eye contact, breathing naturally, subtle confident nod",
        keywords=["你", "就是你", "說謊", "憑什麼", "立刻", "指責", "交代", "敢不敢", "滾出", "放肆", "站住"],
        character_roles=["經理", "董事長", "反派", "主管", "督察"],
        framing="medium_close_up",
        intensity=0.9,
    ),
    "holding_document": ActionGesture(
        tag="holding_document",
        name="翻閱文件 / 出示合約證據",
        visual_prompt="holding official business contract documents in hand, reviewing papers with furrowed brow, paper texture visible",
        motion_prompt="raising confidential paper documents in hand to examine them, flipping pages with fingers, glancing up with a piercing look",
        keywords=["文件", "合約", "這份協議", "報表", "證據", "簽字", "審核", "公文", "條款", "紀錄"],
        character_roles=["經理", "總監", "律師", "調查員", "秘書"],
        framing="medium",
        intensity=0.75,
    ),
    "thoughtful_chin_touch": ActionGesture(
        tag="thoughtful_chin_touch",
        name="托下巴沉思 / 密謀反擊",
        visual_prompt="one hand gently resting on chin in deep contemplation and sharp intellectual focus, strictly two arms only, natural ergonomic human anatomy, slight tilt of the head, calculating gaze",
        motion_prompt="slowly lowering hand from chin in contemplation, eyes narrowing thoughtfully, turning head to make sharp eye contact",
        keywords=["思考", "不對勁", "原來如此", "計畫", "秘密", "陰謀", "如果", "算計", "奇怪", "為什麼"],
        character_roles=["總監", "駭客", "主角", "幕後黑手"],
        framing="close_up",
        intensity=0.6,
    ),
    "crossed_arms_stern": ActionGesture(
        tag="crossed_arms_stern",
        name="雙手抱胸 / 冷笑對峙",
        visual_prompt="standing with arms crossed firmly across chest, authoritative posture, slight smirk and skeptical haughty expression",
        motion_prompt="shifting body weight slightly with arms crossed, slight cynical smirk, subtle head tilt sizing up the opponent",
        keywords=["冷笑", "笑話", "就這點能耐", "自不量力", "痴心妄想", "拒絕", "沒用", "隨便你", "哼"],
        character_roles=["反派主管", "傲慢經理", "高階長官", "對手"],
        framing="medium",
        intensity=0.8,
    ),
    "desk_lean_forward": ActionGesture(
        tag="desk_lean_forward",
        name="雙手撐桌 / 步步逼近",
        visual_prompt="leaning aggressively forward with palms pressed flat against the mahogany executive desk, intense commanding presence",
        motion_prompt="leaning aggressively forward over desk toward camera, jaw clenching, powerful dominant body movement under moody lighting",
        keywords=["聽清楚", "威脅", "這家公司", "由不得你", "後果自負", "我才是老闆", "警告", "最後一次"],
        character_roles=["董事長", "老總", "強勢主管"],
        framing="medium_close_up",
        intensity=0.95,
    ),
    "phone_call_urgent": ActionGesture(
        tag="phone_call_urgent",
        name="緊急通話 / 暗通款曲",
        visual_prompt="holding a sleek black smartphone to ear with urgent tense expression, focused eyes scanning room warily",
        motion_prompt="speaking urgently into smartphone, glancing around warily, taking phone down as sudden dramatic realization strikes",
        keywords=["電話", "喂", "出事了", "立刻處理", "封鎖消息", "快去", "秘密行動", "聽到了嗎", "回話"],
        character_roles=["秘書", "反派助手", "督察", "外線人員"],
        framing="close_up",
        intensity=0.85,
    ),
    "hand_spread_explaining": ActionGesture(
        tag="hand_spread_explaining",
        name="攤手說明 / 利益遊說",
        visual_prompt="gesturing expressively with open hands spread, articulate persuasive executive stance, negotiating demeanor",
        motion_prompt="moving hands articulately in persuasive explanatory gestures, nodding head deliberately to emphasize strategic points",
        keywords=["這是一門生意", "合作", "雙贏", "市場", "資金", "利潤", "很簡單", "你想清楚", "解釋"],
        character_roles=["業務總監", "投資人", "顧問", "談判專家"],
        framing="medium",
        intensity=0.65,
    ),
    "inspecting_tablet": ActionGesture(
        tag="inspecting_tablet",
        name="檢視平板數據 / 核心解鎖",
        visual_prompt="holding modern glass tablet computer with glowing blue screen reflections on face, technical focused expression",
        motion_prompt="swiping on a glowing tablet screen, eyes darting across data, eyes widening in sudden discovery, looking up toward camera",
        keywords=["數據", "系統", "金流", "後台", "伺服器", "權限", "破解", "紀錄", "查到了", "代碼"],
        character_roles=["架構師", "女主角", "技術駭客", "稽核員"],
        framing="medium_close_up",
        intensity=0.7,
    ),
    "sipping_drink_composed": ActionGesture(
        tag="sipping_drink_composed",
        name="從容品茗 / 勝券在握",
        visual_prompt="holding a luxury crystal whiskey tumbler or porcelain teacup with elegant composed poise, unflinching calm",
        motion_prompt="swirling drink glass slowly, bringing cup to lips with calm steady gaze, subtle triumphant expression under ambient light",
        keywords=["別急", "喝茶", "好戲開場", "坐下", "慢慢來", "勝券在握", "品味", "享受"],
        character_roles=["董事長", "幕後大佬", "優雅女霸總"],
        framing="medium_close_up",
        intensity=0.5,
    ),
    "head_turn_shock": ActionGesture(
        tag="head_turn_shock",
        name="猛然轉頭 / 震驚反轉",
        visual_prompt="turning head sharply toward camera with widened pupils and parted lips in sudden realization of betrayal or revelation",
        motion_prompt="turning head rapidly toward camera in shock, eyes widening in disbelief, dramatic tension building with sharp focal shift",
        keywords=["怎麼可能", "你是誰", "難道", "不可能", "被發現了", "竟敢", "背叛", "圈套"],
        character_roles=["被揭發者", "主角", "反派主管"],
        framing="close_up",
        intensity=1.0,
    ),
    "standing_tall_revelation": ActionGesture(
        tag="standing_tall_revelation",
        name="挺拔挺立 / 身分揭曉",
        visual_prompt="standing upright with broad shoulders and regal posture, buttoning suit jacket with confident charismatic gaze",
        motion_prompt="fastening jacket button smoothly, squaring shoulders, lifting chin with unstoppable commanding authority",
        keywords=["重新認識一下", "我就是", "隱藏身分", "這就是我的回答", "真相", "正式宣布", "歸來"],
        character_roles=["真總裁", "隱藏高層", "女戰神", "男主角"],
        framing="medium",
        intensity=0.9,
    ),
    "subtle_gaze_smirk": ActionGesture(
        tag="subtle_gaze_smirk",
        name="斜睨冷笑 / 掌控全域",
        visual_prompt="eyes angled sideways with a knowing subtle half-smirk, head tilted slightly back with quiet immense confidence",
        motion_prompt="slowly turning eyes to camera, subtle half-smirk forming at corner of mouth, exudes calm absolute control",
        keywords=["你太天真了", "早就料到了", "自投羅網", "可惜", "一切盡在掌握", "太遲了"],
        character_roles=["核心主角", "大BOSS", "高智商操盤手"],
        framing="close_up",
        intensity=0.85,
    ),
}


def get_gesture_by_tag(tag: str) -> Optional[ActionGesture]:
    """Retrieve gesture specification by tag."""
    if not tag:
        return None
    clean = re.sub(r"[\[\]gesture:\s]", "", tag.lower())
    return GESTURE_REGISTRY.get(clean) or GESTURE_REGISTRY.get(tag)


def assign_gesture_to_scene(
    narration: str,
    emotion: str = "",
    role_or_speaker: str = "",
    previous_tag: Optional[str] = None,
    scene_idx: int = 0,
) -> ActionGesture:
    """Smartly assign the most dramatically compelling gesture for a scene.
    
    Ensures:
    1. Emotion & dialogue semantics alignment (contract -> holding_document, anger -> pointing_forward, etc.)
    2. Zero repetitive boredom: never assigns the exact same gesture back-to-back.
    3. Natural dramatic escalation across the 9:16 vertical narrative.
    """
    text = f"{narration} {emotion} {role_or_speaker}".lower()
    
    # 1. Score all gestures against dialogue keywords and role match
    scores: List[tuple[float, ActionGesture]] = []
    
    for gesture in GESTURE_REGISTRY.values():
        score = 0.0
        # Keyword matching
        for kw in gesture.keywords:
            if kw.lower() in text:
                score += 3.0
                
        # Role matching
        for role in gesture.character_roles:
            if role.lower() in role_or_speaker.lower():
                score += 1.5
                
        # Consecutive penalty
        if gesture.tag == previous_tag:
            score -= 5.0
            
        scores.append((score, gesture))
        
    scores.sort(key=lambda x: x[0], reverse=True)
    best_score, best_gesture = scores[0]
    
    # If no strong keyword triggered (score <= 0), rotate through a curated high-drama sequence
    if best_score <= 0.5:
        rotation = [
            "standing_tall_revelation",
            "thoughtful_chin_touch",
            "crossed_arms_stern",
            "pointing_forward",
            "holding_document",
            "subtle_gaze_smirk",
            "desk_lean_forward",
            "hand_spread_explaining"
        ]
        # Choose next in rotation different from previous
        for cand_tag in rotation[scene_idx % len(rotation):] + rotation:
            if cand_tag != previous_tag and cand_tag in GESTURE_REGISTRY:
                return GESTURE_REGISTRY[cand_tag]
                
    return best_gesture


def list_all_gestures() -> List[Dict]:
    """Return catalog of gestures for Web UI display and manual selection."""
    return [
        {
            "tag": g.tag,
            "name": g.name,
            "framing": g.framing,
            "intensity": g.intensity,
            "visual_prompt": g.visual_prompt,
            "motion_prompt": g.motion_prompt,
        }
        for g in GESTURE_REGISTRY.values()
    ]
