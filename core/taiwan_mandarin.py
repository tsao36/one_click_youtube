"""Taiwan Traditional Chinese Mandarin (台灣繁體中文 / 國語) language processing and normalization.

Ensures scripts, research outlines, and narration text strictly adhere to
Taiwanese Mandarin vocabulary, terminology, and natural spoken idioms,
while eliminating Mainland Chinese simplified phrasing and buzzwords.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from core.logging_setup import log

try:
    import opencc
    _CC_T2S = opencc.OpenCC("t2s")
    _CC_S2TWP = opencc.OpenCC("s2twp")
except Exception as _e:
    _CC_T2S = None
    _CC_S2TWP = None
    log.warning("OpenCC could not be initialized (%s); using rule-based dictionary only", _e)


def is_taiwan_mandarin(language: str | None, topic: str = "") -> bool:
    """Return True if the target language is Taiwan Traditional Chinese / Mandarin,
    or if the topic has Chinese characters and no non-Chinese language is explicitly requested.
    """
    if not language:
        return bool(re.search(r"[\u4e00-\u9fff]", topic))

    l_lower = language.lower()
    # Explicit Traditional Chinese / Taiwan references
    if any(k in l_lower for k in [
        "traditional", "taiwan", "繁體", "正體", "台灣", "臺灣", "國語", "zh-tw", "zh_tw", "zh-hant"
    ]):
        return True

    # Generic Chinese (default to Taiwan Traditional Chinese unless explicitly Simplified/Mainland)
    if any(k in l_lower for k in ["chinese", "mandarin", "中文", "華語"]):
        if not any(k in l_lower for k in ["simplified", "簡體", "简体", "普通話", "普通话", "zh-cn", "zh_cn", "zh-hans"]):
            return True

    # If topic has CJK characters and language is not English, Spanish, Japanese, etc.
    if re.search(r"[\u4e00-\u9fff]", topic) and not any(k in l_lower for k in [
        "english", "spanish", "japanese", "french", "german", "korean", "italian", "portuguese"
    ]):
        return True

    return False


TAIWAN_MANDARIN_SYSTEM_PROMPT = """
【重要語言與詞彙規範：臺灣正體中文（臺灣國語 / 華語）】
你是一位專門為臺灣觀眾製作高品質 YouTube 紀錄片與深度科普影片的腳本作家。
本腳本必須全程使用「臺灣正體中文（繁體中文）」撰寫，並嚴格遵循臺灣在地慣用語、詞彙規範與口語發音習慣：

1. 【嚴格字體要求】：必須使用標準臺灣正體中文（教育部標準國字），嚴禁出現任何簡體中文字或大陸字形變體。
2. 【嚴格臺灣在地科技與專業術語（嚴禁大陸用語）】：
   - 影片 / 影音（絕對不用「視頻」）
   - 短影音（絕對不用「短視頻」）
   - 軟體（絕對不用「軟件」）
   - 硬體（絕對不用「硬件」）
   - 專案 / 計劃（絕對不用「項目」）
   - 程式 / 程式碼（絕對不用「程序」或「代碼」）
   - 演算法（絕對不用「算法」）
   - 資料庫（絕對不用「數據庫」）
   - 資料 / 數據（資料記錄用「資料」，數值統計用「數據」；不用「大數據」濫用或「信息」）
   - 資訊 / 訊息（絕對不用「信息」）
   - 網路 / 網際網路（絕對不用「網絡」或「互聯網」）
   - 螢幕（絕對不用「屏幕」）
   - 記憶體（絕對不用「內存」）
   - 晶片（絕對不用「芯片」）
   - 伺服器（絕對不用「服務器」）
   - 預設（絕對不用「默認」）
   - 支援（產品規格或功能相容，絕對不用「支持」）
   - 介面（絕對不用「界面」）
   - 連結 / 超連結（絕對不用「鏈接」）
   - 人工智慧 / AI（絕對不用「人工智能」）
   - 智慧型手機（絕對不用「智能手機」）
   - 解析度（絕對不用「分辨率」）
   - 畫質（絕對不用「清晰度」）
   - 雷射（絕對不用「激光」）
   - 矽谷（絕對不用「硅谷」）
   - 航太（絕對不用「航天」）
   - 列印 / 印表機（絕對不用「打印」/「打印機」）
   - 使用者（偏好「使用者」優於「用戶」）
   - 品質（評估水準用「品質」；「質量」在臺灣僅指物理質量 mass）
   - 水準（評價能力水準，絕對不用「水平」）
   - 隨身碟（絕對不用「U盤」）
   - 筆電 / 筆記型電腦（絕對不用「筆記本」）
   - 塑膠（絕對不用「塑料」）
3. 【生活與交通詞彙】：
   - 計程車 / 叫車（絕對不用「出租車」或「打車」）
   - 捷運 / 地鐵（臺灣情境用「捷運」）
   - 腳踏車 / 單車（絕對不用「自行車」）
   - 超商 / 便利商店（絕對不用「便利店」）
   - 幼稚園 / 幼兒園（臺灣在地用語）
   - 泡麵（絕對不用「方便麵」）
   - 飯店 / 旅館（絕對不用「酒店」）
4. 【嚴格禁止大陸流行 buzzwords 與空話】：
   - 嚴禁使用：「給力」、「立馬」、「走心」、「膠水語言」、「閉環」、「賦能」、「抓手」、「打法」、「痛點」、「降維打擊」、「忽悠」、「吐槽」、「牛逼」、「老鐵」、「小夥伴」、「接地氣」、「腦洞大開」、「妥妥的」、「特麼」、「吃瓜」等大陸網路用語。
5. 【臺灣自然口語語感】：
   - 句型流暢自然、具備臺灣優質紀錄片與知識型 YouTube 頻道的沉穩與生動風格。多使用「透過」、「其實」、「舉例來說」、「我們可以發現」、「讓我們一起來探討」，避免生硬翻譯腔或宣傳教條口吻。
"""

# Explicit replacement rules for Taiwan Mandarin (word/phrase replacements)
_TAIWAN_TERM_MAPPINGS: List[Tuple[re.Pattern, str]] = [
    # Complex/Compound terms first
    (re.compile(r"短[視视][頻频]"), "短影音"),
    (re.compile(r"短影片"), "短影音"),
    (re.compile(r"(?<!短)[視视][頻频]"), "影片"),
    (re.compile(r"音[頻频]"), "音訊"),
    (re.compile(r"屏[幕]"), "螢幕"),
    (re.compile(r"分[辨]率"), "解析度"),
    (re.compile(r"清晰度"), "畫質"),
    (re.compile(r"截屏"), "截圖"),
    (re.compile(r"話筒|话筒"), "麥克風"),
    (re.compile(r"攝像頭|摄像头"), "攝影鏡頭"),
    (re.compile(r"錄像|录像"), "錄影"),
    (re.compile(r"流[媒]體|流媒体"), "串流影音"),

    # Computer & Technology
    (re.compile(r"[軟软][件]"), "軟體"),
    (re.compile(r"[硬][件]"), "硬體"),
    (re.compile(r"程序[員员]"), "工程師"),
    (re.compile(r"代[碼码]"), "程式碼"),
    (re.compile(r"源[碼码]"), "原始碼"),
    (re.compile(r"(?<!演)[算]法"), "演算法"),
    (re.compile(r"演{2,}算法"), "演算法"),
    (re.compile(r"[數数][據据][庫库]"), "資料庫"),
    (re.compile(r"[內内]存"), "記憶體"),
    (re.compile(r"記憶{2,}體"), "記憶體"),
    (re.compile(r"磁[盤盘]"), "硬碟"),
    (re.compile(r"(?<!伺)服[務务]器"), "伺服器"),
    (re.compile(r"伺{2,}服器"), "伺服器"),
    (re.compile(r"芯[片]"), "晶片"),
    (re.compile(r"默[認认]"), "預設"),
    (re.compile(r"界[面]"), "介面"),
    (re.compile(r"交[互]"), "互動"),
    (re.compile(r"超[鏈链][接]"), "超連結"),
    (re.compile(r"(?<!超)[鏈链][接]"), "連結"),
    (re.compile(r"互[聯联][網网]"), "網際網路"),
    (re.compile(r"網際網際網路"), "網際網路"),
    (re.compile(r"局域[網网]"), "區域網路"),
    (re.compile(r"(?<![網際區域])[網网][絡络]"), "網路"),
    (re.compile(r"U[盤盘]"), "隨身碟"),
    (re.compile(r"[筆笔][記记]本[電电][腦脑]"), "筆記型電腦"),
    (re.compile(r"打[印][機机]"), "印表機"),
    (re.compile(r"打[印]"), "列印"),
    (re.compile(r"光[標标]"), "游標"),
    (re.compile(r"[雲云][計计][算]"), "雲端運算"),
    (re.compile(r"海量[數数][據据]"), "巨量資料"),

    # AI & Science
    (re.compile(r"人工[智]能"), "人工智慧"),
    (re.compile(r"[智]能手[機机]"), "智慧型手機"),
    (re.compile(r"[智]能家[居電电]"), "智慧家電"),
    (re.compile(r"[智]能手[錶表]"), "智慧手錶"),
    (re.compile(r"[智]能[設设][備备]"), "智慧裝置"),
    (re.compile(r"[激鐳]光"), "雷射"),
    (re.compile(r"[硅]谷"), "矽谷"),
    (re.compile(r"航[天]"), "航太"),
    (re.compile(r"[塑]料"), "塑膠"),
    (re.compile(r"[數数]字化"), "數位化"),
    (re.compile(r"[數数]字[轉转]型"), "數位轉型"),

    # Daily Life & Society
    (re.compile(r"出租[車车]"), "計程車"),
    (re.compile(r"(?<![叫])打[車车]"), "叫計程車"),
    (re.compile(r"自行[車车]"), "腳踏車"),
    (re.compile(r"便利[店]"), "超商"),
    (re.compile(r"方便[麵面]"), "泡麵"),
    (re.compile(r"菠[蘿萝]"), "鳳梨"),
    (re.compile(r"[獼猕]猴桃"), "奇異果"),
    (re.compile(r"西[紅红]柿"), "番茄"),
    (re.compile(r"金[槍枪][魚鱼]"), "鮪魚"),
    (re.compile(r"三[文][魚鱼]"), "鮭魚"),
    (re.compile(r"[黃黄]油"), "奶油"),

    # Quality & Capability contexts
    (re.compile(r"[高][質质][量]"), "高品質"),
    (re.compile(r"[低][質质][量]"), "低品質"),
    (re.compile(r"[優优][質质]的[質质]量"), "優良的品質"),
    (re.compile(r"[質质][量]保[證证]"), "品質保證"),
    (re.compile(r"[技][術术]水[平]"), "技術水準"),
    (re.compile(r"[專专][業业]水[平]"), "專業水準"),
    (re.compile(r"[生][活]水[平]"), "生活水準"),

    # Mainland Buzzwords & Slang
    (re.compile(r"給力|给力"), "亮眼"),
    (re.compile(r"立[馬马]"), "立刻"),
    (re.compile(r"走[心]"), "用心"),
    (re.compile(r"膠水[語语]言|胶水语言"), "膠合語言"),
    (re.compile(r"閉環|闭环"), "完整體系"),
    (re.compile(r"賦能|赋能"), "提供助力"),
    (re.compile(r"痛點|痛点"), "關鍵問題"),
    (re.compile(r"降維打擊|降维打击"), "壓倒性優勢"),
    (re.compile(r"忽[悠]"), "唬弄"),
    (re.compile(r"吐[槽]"), "調侃"),
    (re.compile(r"牛[逼]"), "厲害"),
    (re.compile(r"小[夥伙][伴]們|小伙伴们"), "夥伴們"),
    (re.compile(r"小[夥伙][伴]|小伙伴"), "夥伴"),
    (re.compile(r"老[鐵铁]"), "朋友"),
    (re.compile(r"接[地][氣气]"), "親民貼切"),
    (re.compile(r"腦洞大開|脑洞大开"), "別出心裁"),
    (re.compile(r"妥妥的"), "穩穩的"),
]


def normalize_to_taiwan_mandarin(text: str) -> str:
    """Transform and normalize text to Taiwan Traditional Chinese Mandarin.

    Converts simplified characters, replaces mainland Chinese terminology,
    and ensures standard Taiwanese vocabulary.
    """
    if not text or not isinstance(text, str):
        return text

    # Pass 1: OpenCC (t2s -> s2twp) to leverage standard Taiwan character and idiom mapping
    if _CC_T2S and _CC_S2TWP:
        try:
            # If text is already Traditional or mixed, converting to simplified first
            # allows OpenCC's comprehensive s2twp (Simplified to Taiwan with Phrases)
            # dictionary to convert terms like 视频->影片, 软件->軟體, 芯片->晶片 reliably.
            simplified = _CC_T2S.convert(text)
            text = _CC_S2TWP.convert(simplified)
        except Exception as e:
            log.warning("OpenCC conversion error (%s); proceeding with regex table", e)

    # Pass 2: Explicit dictionary replacements for fine-grained Taiwan terminology
    for pattern, replacement in _TAIWAN_TERM_MAPPINGS:
        text = pattern.sub(replacement, text)

    return text
