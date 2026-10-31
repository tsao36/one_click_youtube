"""Taiwan Traditional Chinese Mandarin (台灣繁體中文 / 國語) language processing and normalization.

Ensures scripts, research outlines, and narration text strictly adhere to
Taiwanese Mandarin vocabulary, terminology, and natural spoken idioms,
while completely eliminating Mainland Chinese simplified phrasing, buzzwords, and "支語".
"""
from __future__ import annotations

import re
from typing import Any, List, Tuple

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
【最高核心語言規範：100% 臺灣正體中文（臺灣國語 / 在地華語）】
你是一位專門為臺灣觀眾打造高品質 YouTube 紀錄片、科普與文史節目的資深旁白作家。
本腳本必須全程使用「臺灣正體中文（繁體中文）」撰寫，並實施【零容忍中國用語、大陸習慣表達與網路支語】原則。
所有語法、詞彙、科技術語、生活用品與成語習慣，必須 100% 符合臺灣在地真實使用習慣：

1. 【文字與字體】：
   - 全程使用標準臺灣正體中文（教育部標準國字規範），嚴禁任何簡體字、簡體轉繁體的異體字或大陸用字。

2. 【嚴格禁止中國大陸 3C、科技與資訊用語，必須使用臺灣標準】：
   - 影片 / 短影音 / 音訊（❌ 嚴禁：視頻、短視頻、音頻、錄像、流媒體）
   - 軟體 / 硬體（❌ 嚴禁：軟件、硬件）
   - 程式 / 程式碼 / 原始碼（❌ 嚴禁：程序、代碼、源碼、源代碼）
   - 工程師（❌ 嚴禁：程序員、碼農）
   - 演算法（❌ 嚴禁：算法）
   - 資料庫 / 資料（❌ 嚴禁：數據庫、信息；數值統計才稱「數據」）
   - 資訊 / 訊息（❌ 嚴禁：信息、消息）
   - 記憶體（❌ 嚴禁：內存）
   - 硬碟 / 隨身碟 / 外接硬碟（❌ 嚴禁：磁盤、U盤、移動硬盤）
   - 伺服器（❌ 嚴禁：服務器）
   - 晶片（❌ 嚴禁：芯片）
   - 預設（❌ 嚴禁：默認）
   - 介面 / 互動（❌ 嚴禁：界面、交互）
   - 連結 / 超連結（❌ 嚴禁：鏈接、超鏈接）
   - 網路 / 網際網路 / 區域網路（❌ 嚴禁：網絡、互聯網、局域網）
   - 螢幕 / 觸控螢幕（❌ 嚴禁：屏幕、顯示屏、觸摸屏）
   - 解析度 / 畫質（❌ 嚴禁：分辨率、清晰度）
   - 截圖 / 錄影（❌ 嚴禁：截屏、錄像）
   - 麥克風 / 攝影鏡頭（❌ 嚴禁：話筒、攝像頭、攝像機）
   - 人工智慧 / AI（❌ 嚴禁：人工智能）
   - 智慧型手機 / 智慧手錶 / 智慧裝置 / 智慧家電（❌ 嚴禁：智能手機、智能設備、智能家居）
   - 雷射 / 光學雷達（❌ 嚴禁：激光、激光雷達）
   - 矽谷 / 航太 / 塑膠（❌ 嚴禁：硅谷、航天、塑料）
   - 列印 / 印表機 / 影印（❌ 嚴禁：打印、打印機、複印）
   - 游標（❌ 嚴禁：光標）
   - 雲端運算 / 雲端儲存（❌ 嚴禁：雲計算、雲存儲）
   - 數位化 / 數位轉型（❌ 嚴禁：數字化、數字轉型）
   - 行動電源 / 傳輸線（❌ 嚴禁：充電寶、移動電源、數據線）
   - 投影 / 鏡射（❌ 嚴禁：投屏）
   - 重新整理（❌ 嚴禁：刷新網頁）
   - 登入 / 登出（❌ 嚴禁：登錄、退出登錄）
   - 按讚（❌ 嚴禁：點贊、點讚）
   - 使用者 / 使用者體驗（❌ 嚴禁：用戶、用戶體驗）
   - 專案 / 計畫（❌ 嚴禁：項目）
   - 支援（產品規格相容，❌ 嚴禁：支持）
   - 品質（評估水準用品質；❌ 嚴禁：質量，質量在臺灣僅指物理 mass）
   - 水準（評價能力水準；❌ 嚴禁：水平）

3. 【生活、交通、飲食在地用語（❌ 嚴禁大陸用語）】：
   - 計程車 / 叫車（❌ 嚴禁：出租車、打車、的士）
   - 腳踏車 / 單車（❌ 嚴禁：自行車）
   - 公車（❌ 嚴禁：公交車、公交）
   - 捷運（臺灣情境請用捷運，非地鐵）
   - 汽機車 / 機車（❌ 嚴禁：機動車、摩托車）
   - 超商 / 便利商店（❌ 嚴禁：便利店）
   - 泡麵（❌ 嚴禁：方便麵）
   - 便當（❌ 嚴禁：盒飯）
   - 番茄 / 馬鈴薯 / 鳳梨 / 奇異果（❌ 嚴禁：西紅柿、土豆、菠蘿、獼猴桃；臺灣「土豆」專指花生！）
   - 鮭魚 / 鮪魚（❌ 嚴禁：三文魚、金槍魚）
   - 奶油 / 起司 / 優格（❌ 嚴禁：黃油、芝士、酸奶）
   - 高麗菜 / 青花菜（❌ 嚴禁：捲心菜、包菜、西藍花）
   - 飯店 / 旅館（❌ 嚴禁：酒店、賓館；臺灣「酒店」常帶夜生活場所意涵）
   - 化妝室 / 洗手間 / 廁所（❌ 嚴禁：衛生間）
   - 原子筆 / 橡皮擦 / OK繃 / 塑膠袋（❌ 嚴禁：圓珠筆、橡皮、創可貼、塑料袋）
   - 服務生 / 店員（❌ 嚴禁：服務員）
   - 社區（❌ 嚴禁：小區）

4. 【嚴格禁止大陸流行語、網路支語與商務黑話（零容忍）】：
   - ❌ 嚴格禁止：「立馬」（改為「立刻 / 馬上」）
   - ❌ 嚴格禁止：「給力」（改為「出色 / 亮眼 / 強大」）
   - ❌ 嚴格禁止：「走心」（改為「用心 / 誠懇」）
   - ❌ 嚴格禁止：「閉環」（改為「完整迴圈 / 完整體系」）
   - ❌ 嚴格禁止：「賦能」（改為「提供助力 / 賦予能力」）
   - ❌ 嚴格禁止：「痛點」（改為「核心痛點 / 關鍵問題」）
   - ❌ 嚴格禁止：「抓手」（改為「切入點 / 施力點」）
   - ❌ 嚴格禁止：「打法」（改為「策略作法」）
   - ❌ 嚴格禁止：「落地」（改為「落實推行 / 具體實現」）
   - ❌ 嚴格禁止：「底層邏輯」（改為「核心邏輯 / 根本原理」）
   - ❌ 嚴格禁止：「復盤 / 複盤」（改為「檢討覆盤 / 回顧檢討」）
   - ❌ 嚴格禁止：「壁壘」（改為「門檻 / 障礙」）
   - ❌ 嚴格禁止：「賽道」（改為「領域 / 市場」）
   - ❌ 嚴格禁止：「忽悠」（改為「唬弄 / 欺騙」）
   - ❌ 嚴格禁止：「吐槽」（改為「調侃 / 吐嘈」）
   - ❌ 嚴格禁止：「牛逼 / 牛B / NB」（改為「厲害 / 卓越」）
   - ❌ 嚴格禁止：「裝逼」（改為「擺架子 / 裝模作樣」）
   - ❌ 嚴格禁止：「老鐵」（改為「朋友 / 兄弟」）
   - ❌ 嚴格禁止：「小夥伴」（改為「夥伴」）
   - ❌ 嚴格禁止：「接地氣」（改為「親民貼切 / 貼近生活」）
   - ❌ 嚴格禁止：「腦洞大開」（改為「別出心裁 / 創意十足」）
   - ❌ 嚴格禁止：「妥妥的」（改為「穩穩的 / 毫無疑問」）
   - ❌ 嚴格禁止：「吃瓜 / 吃瓜群眾」（改為「圍觀 / 看熱鬧的群眾」）
   - ❌ 嚴格禁止：「帶節奏」（改為「帶風向」）
   - ❌ 嚴格禁止：「割韭菜」（改為「壓榨散戶」）
   - ❌ 嚴格禁止：「智商稅」（改為「冤枉錢」）
   - ❌ 嚴格禁止：「高大上」（改為「高級大器 / 氣派」）
   - ❌ 嚴格禁止：「畫大餅」（改為「開空頭支票」）
   - ❌ 嚴格禁止：「甩鍋」（改為「推卸責任」）
   - ❌ 嚴格禁止：「出圈」（改為「爆紅跨界 / 蔚為風潮」）
   - ❌ 嚴格禁止：「內卷 / 內捲」（改為「過度內耗 / 惡性競爭」）
   - ❌ 嚴格禁止：「躺平 / 擺爛」（若非探討社會現象，避免作為日常口吻濫用）
   - ❌ 嚴格禁止：「絕絕子、芭比Q、泰褲辣、尊嘟假嘟、栓Q、破防、踩坑、避坑、薅羊毛、圈粉、實錘、槓精、網暴、博主、UP主」等大陸網路用語。

5. 【臺灣自然敘事語感與語調】：
   - 語氣客觀沉穩、自然流暢，兼具生動吸睛的 YouTube 節奏。
   - 句型多使用臺灣在地口語連接詞，如「透過」、「其實」、「舉例來說」、「我們可以發現」、「讓我們一起來探討」、「值得注意的是」，徹底去除翻譯腔、官腔教條與說教口吻。
"""

# Explicit rule-based replacement mappings for Taiwan Mandarin (sorted by specificity)
_TAIWAN_TERM_MAPPINGS: List[Tuple[re.Pattern, str]] = [
    # --- 1. Video, Audio, Display, Camera ---
    (re.compile(r"短[視视][頻频]"), "短影音"),
    (re.compile(r"短影片"), "短影音"),
    (re.compile(r"[視视][頻频]博主"), "影片創作者"),
    (re.compile(r"(?<!短)[視视][頻频]"), "影片"),
    (re.compile(r"音[頻频]"), "音訊"),
    (re.compile(r"流[媒]體|流媒体"), "串流影音"),
    (re.compile(r"觸[摸]屏|触摸屏"), "觸控螢幕"),
    (re.compile(r"顯[示]屏|显示屏"), "顯示螢幕"),
    (re.compile(r"屏[幕]"), "螢幕"),
    (re.compile(r"分[辨]率"), "解析度"),
    (re.compile(r"高清晰度"), "高畫質"),
    (re.compile(r"清晰度"), "畫質"),
    (re.compile(r"截屏"), "截圖"),
    (re.compile(r"話筒|话筒"), "麥克風"),
    (re.compile(r"攝像頭|摄像头"), "攝影鏡頭"),
    (re.compile(r"攝像機|摄像机"), "攝影機"),
    (re.compile(r"錄像|录像"), "錄影"),
    (re.compile(r"投[屏]"), "投影鏡射"),

    # --- 2. Computer, Tech, Code, Storage ---
    (re.compile(r"[軟软][件]"), "軟體"),
    (re.compile(r"[硬][件]"), "硬體"),
    (re.compile(r"程序[員员]|碼農|码农"), "工程師"),
    (re.compile(r"代[碼码]"), "程式碼"),
    (re.compile(r"源[代]?[碼码]"), "原始碼"),
    (re.compile(r"(?<!演)[算]法"), "演算法"),
    (re.compile(r"演{2,}算法"), "演算法"),
    (re.compile(r"[數数][據据][庫库]"), "資料庫"),
    (re.compile(r"個人[信]息|敏感[信]息"), "個人資料"),
    (re.compile(r"[信]息[技]術"), "資訊科技"),
    (re.compile(r"[信]息[安]全"), "資訊安全"),
    (re.compile(r"[信]息[量]"), "資訊量"),
    (re.compile(r"[信]息[差]"), "資訊落差"),
    (re.compile(r"發送[信]息|發[信]息"), "傳送訊息"),
    (re.compile(r"(?<![通訊通訊短])([信]息)"), "資訊"),
    (re.compile(r"[內内]存"), "記憶體"),
    (re.compile(r"記憶{2,}體"), "記憶體"),
    (re.compile(r"磁[盤盘]"), "硬碟"),
    (re.compile(r"軟[盤盘]|软盘"), "磁碟片"),
    (re.compile(r"光[驅驱]|光驱"), "光碟機"),
    (re.compile(r"移動硬[盤盘]|移动硬盘"), "外接硬碟"),
    (re.compile(r"U[盤盘]|優盤|优盘"), "隨身碟"),
    (re.compile(r"[筆笔][記记]本[電电][腦脑]"), "筆記型電腦"),
    (re.compile(r"打[印][機机]"), "印表機"),
    (re.compile(r"打[印]"), "列印"),
    (re.compile(r"複[印][機机]|复印机"), "影印機"),
    (re.compile(r"複[印]|复印"), "影印"),
    (re.compile(r"光[標标]"), "游標"),
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
    (re.compile(r"(?<![網際區域電線])([網网][絡络])"), "網路"),
    (re.compile(r"[雲云][計计][算]"), "雲端運算"),
    (re.compile(r"[雲云][存儲储]"), "雲端儲存"),
    (re.compile(r"海量[數数][據据]"), "巨量資料"),
    (re.compile(r"[數数]字化"), "數位化"),
    (re.compile(r"[數数]字[轉转]型"), "數位轉型"),
    (re.compile(r"[數数]字[貨货][幣币]"), "數位貨幣"),
    (re.compile(r"充[電电][寶宝]|移動電源|移动电源"), "行動電源"),
    (re.compile(r"[數数][據据][線线]"), "傳輸線"),
    (re.compile(r"耳[麥麦]"), "耳機麥克風"),
    (re.compile(r"寬[帶带]|宽带"), "寬頻"),
    (re.compile(r"[運运][營营]商"), "電信業者"),
    (re.compile(r"聯[網网]|联网"), "連網"),
    (re.compile(r"[斷断][網网]"), "斷線"),
    (re.compile(r"[網网][頁页]端"), "網頁版"),
    (re.compile(r"客[戶户]端"), "用戶端"),
    (re.compile(r"移[動动]端"), "行動端"),
    (re.compile(r"刷[新][網网][頁页]"), "重新整理網頁"),
    (re.compile(r"(?<![洗手清煥革])刷[新](?=[頁面端])"), "重新整理"),
    (re.compile(r"登[錄录]|登录"), "登入"),
    (re.compile(r"退出登[錄录]|退出登录"), "登出"),
    (re.compile(r"[註注][銷销]帳[號号]"), "刪除帳號"),
    (re.compile(r"點[贊赞]|点赞|點[讚]"), "按讚"),
    (re.compile(r"取[關关]|取关"), "取消關注"),
    (re.compile(r"[網网]民"), "網友"),
    (re.compile(r"充[值]"), "儲值"),
    (re.compile(r"提[現现]"), "提款"),
    (re.compile(r"激[活]"), "啟用"),
    (re.compile(r"拉[黑]"), "加入黑名單"),
    (re.compile(r"刪[庫库]|删库"), "刪除資料庫"),
    (re.compile(r"[跑]路"), "捲款潛逃"),

    # --- 3. AI, Science, Industry ---
    (re.compile(r"人工[智]能"), "人工智慧"),
    (re.compile(r"[智]能手[機机]"), "智慧型手機"),
    (re.compile(r"[智]能家[居電电]"), "智慧家電"),
    (re.compile(r"[智]能手[錶表]"), "智慧手錶"),
    (re.compile(r"[智]能[設设][備备]"), "智慧裝置"),
    (re.compile(r"[智]能化"), "智慧化"),
    (re.compile(r"[激鐳]光[雷]達"), "光學雷達"),
    (re.compile(r"[激鐳]光"), "雷射"),
    (re.compile(r"[硅]谷"), "矽谷"),
    (re.compile(r"航[天]"), "航太"),
    (re.compile(r"[塑]料[袋]"), "塑膠袋"),
    (re.compile(r"[塑]料"), "塑膠"),

    # --- 4. Quality vs Physics Mass Contexts ---
    (re.compile(r"([高低好差優佳劣粗卓越頂級]質?|產品|影片|視頻|音訊|音頻|工程|服務|睡眠|生活|教學|相機|手機|螢幕|設備|軟體|硬體|內容|畫面)(的)?質量"), r"\1\2品質"),
    (re.compile(r"質量(保證|把關|控制|檢驗|問題|很好|很差|很高|很低|優秀|卓越|過硬|上乘|提升)"), r"品質\1"),
    (re.compile(r"(提升|保證|重視|追求|講究|注重)質量"), r"\1品質"),
    (re.compile(r"質[量]監管"), "品質監管"),
    (re.compile(r"質檢"), "品質檢驗"),

    # --- 5. Projects & Capability Contexts ---
    (re.compile(r"(開源|研發|工程|開發|研究|商業|合作|重點)項[目]"), r"\1專案"),
    (re.compile(r"項[目](經理|進度|團隊|代碼|規劃|實施)"), r"專案\1"),
    (re.compile(r"[技][術术]水[平]"), "技術水準"),
    (re.compile(r"[專专][業业]水[平]"), "專業水準"),
    (re.compile(r"[生][活]水[平]"), "生活水準"),
    (re.compile(r"[認认]知水[平]"), "認知水準"),
    (re.compile(r"[能]力水[平]"), "能力水準"),
    (re.compile(r"水[平]有限"), "水準有限"),
    (re.compile(r"支[持](?=\s*4K|\s*1080p|\s*HDR|\s*iOS|\s*Android|\s*Windows|\s*Mac|\s*繁體|\s*繁中|\s*多種格式|\s*快充|\s*藍牙)"), "支援"),

    # --- 6. Users & Roles ---
    (re.compile(r"用[戶户][端]"), "用戶端"),
    (re.compile(r"用[戶户][體体][驗验]"), "使用者體驗"),
    (re.compile(r"(付費|活躍|普通|新增|潛在|註冊|一般)用[戶户]"), r"\1使用者"),
    (re.compile(r"用[戶户](數|群|畫像|資料|權限)"), r"使用者\1"),
    (re.compile(r"[視视][頻频]博主"), "影片創作者"),
    (re.compile(r"(科技|知名|百萬|美食|旅遊|美妝|生活)博主"), r"\1創作者"),
    (re.compile(r"(該|這位|那位|某位)博主"), r"\1創作者"),
    (re.compile(r"UP[主]|up[主]"), "YouTuber"),
    (re.compile(r"(?<![微微薄部落])博[主]"), "創作者"),
    (re.compile(r"帶[貨货]|直播[帶带][貨货]"), "直播促銷"),

    # --- 7. Daily Life, Transport, Food ---
    (re.compile(r"出租[車车]"), "計程車"),
    (re.compile(r"(?<![叫])打[車车]"), "叫計程車"),
    (re.compile(r"的[士]"), "計程車"),
    (re.compile(r"自行[車车]"), "腳踏車"),
    (re.compile(r"公[交][車车]|公[交]"), "公車"),
    (re.compile(r"便利[店]"), "超商"),
    (re.compile(r"方便[麵面]"), "泡麵"),
    (re.compile(r"盒[飯饭]"), "便當"),
    (re.compile(r"菠[蘿萝]"), "鳳梨"),
    (re.compile(r"[獼猕]猴桃"), "奇異果"),
    (re.compile(r"西[紅红]柿"), "番茄"),
    (re.compile(r"土[豆]"), "馬鈴薯"),
    (re.compile(r"金[槍枪][魚鱼]"), "鮪魚"),
    (re.compile(r"三[文][魚鱼]"), "鮭魚"),
    (re.compile(r"[黃黄]油"), "奶油"),
    (re.compile(r"芝[士]"), "起司"),
    (re.compile(r"酸[奶]"), "優格"),
    (re.compile(r"[捲卷]心菜|[包]菜"), "高麗菜"),
    (re.compile(r"西[藍蓝]花"), "青花菜"),
    (re.compile(r"冰[棍]|雪[糕]"), "冰棒"),
    (re.compile(r"衛[生]間|卫生间"), "化妝室"),
    (re.compile(r"圓[珠]筆|圆珠笔"), "原子筆"),
    (re.compile(r"橡[皮]擦?"), "橡皮擦"),
    (re.compile(r"創[可]貼|创可贴"), "OK繃"),
    (re.compile(r"服[務务]員|服务员"), "服務生"),
    (re.compile(r"住[進进]酒店|五星級酒店|預訂酒店|預定酒店"), "入住飯店"),
    (re.compile(r"這家酒店|該酒店|那家酒店"), "這家飯店"),
    (re.compile(r"賓[館馆]|宾馆"), "旅館"),
    (re.compile(r"(居住|住宅|社區)小[區区]"), r"\1社區"),
    (re.compile(r"(?<![大中小微窄])小[區区]"), "社區"),
    (re.compile(r"物[業业][管]理"), "物業管理"),

    # --- 8. Mainland Buzzwords & Slang (支語) ---
    (re.compile(r"給力|给力"), "出色"),
    (re.compile(r"立[馬马]"), "立刻"),
    (re.compile(r"走[心]"), "用心"),
    (re.compile(r"膠水[語语]言|胶水语言"), "膠合語言"),
    (re.compile(r"閉環|闭环"), "完整體系"),
    (re.compile(r"賦能|赋能"), "提供助力"),
    (re.compile(r"痛點|痛点"), "關鍵痛點"),
    (re.compile(r"抓手"), "切入點"),
    (re.compile(r"打法"), "策略作法"),
    (re.compile(r"落[地](?=[項目方案政策機制])"), "推行落實"),
    (re.compile(r"底[層层]邏[輯辑]"), "核心邏輯"),
    (re.compile(r"復盤|複盤|复盘"), "檢討回顧"),
    (re.compile(r"賽[道]"), "競爭領域"),
    (re.compile(r"忽[悠]"), "唬弄"),
    (re.compile(r"吐[槽]"), "調侃"),
    (re.compile(r"牛[逼B]"), "厲害"),
    (re.compile(r"裝[逼B]|装[逼B]"), "擺架子"),
    (re.compile(r"傻[逼B]|煞[筆笔]"), "蠢蛋"),
    (re.compile(r"老[鐵铁]"), "朋友"),
    (re.compile(r"小[夥伙][伴]們|小伙伴们"), "夥伴們"),
    (re.compile(r"小[夥伙][伴]|小伙伴"), "夥伴"),
    (re.compile(r"接[地][氣气]"), "親民貼切"),
    (re.compile(r"腦洞大開|脑洞大开"), "別出心裁"),
    (re.compile(r"妥妥的"), "穩穩的"),
    (re.compile(r"吃[瓜]群[眾众]"), "圍觀民眾"),
    (re.compile(r"吃[瓜]"), "看熱鬧"),
    (re.compile(r"[帶带][節节]奏"), "帶風向"),
    (re.compile(r"[割]韭菜"), "壓榨散戶"),
    (re.compile(r"[智]商[稅税]"), "冤枉錢"),
    (re.compile(r"高大上"), "高級氣派"),
    (re.compile(r"[畫画]大[餅饼]"), "開空頭支票"),
    (re.compile(r"甩[鍋锅]"), "推卸責任"),
    (re.compile(r"出[圈]"), "爆紅跨界"),
    (re.compile(r"[內内][卷捲]"), "過度內耗"),
    (re.compile(r"絕絕子|绝绝子"), "太棒了"),
    (re.compile(r"芭比[Qq]|芭比Q"), "搞砸了"),
    (re.compile(r"泰[褲裤]辣"), "太酷了"),
    (re.compile(r"尊嘟假嘟"), "真的假的"),
    (re.compile(r"栓[Qq]"), "謝謝"),
    (re.compile(r"破[防]"), "崩潰動容"),
    (re.compile(r"[踩]坑"), "踩雷"),
    (re.compile(r"[避]坑"), "避雷"),
    (re.compile(r"[薅]羊毛"), "佔便宜"),
    (re.compile(r"[圈]粉"), "吸粉"),
    (re.compile(r"[實实][錘锤]"), "確鑿鐵證"),
    (re.compile(r"[槓杠]精"), "抬槓狂"),
    (re.compile(r"[網网]暴"), "網路霸凌"),
    (re.compile(r"特[麼么]"), "真是"),
]

# Strict Audit List of Forbidden Mainland Terms (支語與中國用語清單)
FORBIDDEN_MAINLAND_TERMS: List[Tuple[str, str, str]] = [
    # (pattern, taiwan_suggestion, description)
    (r"視頻", "影片 / 影音", "中國用語：應使用『影片』或『影音』"),
    (r"短視頻", "短影音", "中國用語：應使用『短影音』"),
    (r"軟件", "軟體", "中國用語：應使用『軟體』"),
    (r"硬件", "硬體", "中國用語：應使用『硬體』"),
    (r"芯片", "晶片", "中國用語：應使用『晶片』"),
    (r"內存", "記憶體", "中國用語：應使用『記憶體』"),
    (r"磁盤", "硬碟", "中國用語：應使用『硬碟』"),
    (r"服務器", "伺服器", "中國用語：應使用『伺服器』"),
    (r"(?<!演)算法", "演算法", "中國簡稱：臺灣標準為『演算法』"),
    (r"數據庫", "資料庫", "中國用語：應使用『資料庫』"),
    (r"屏幕", "螢幕", "中國用語：應使用『螢幕』"),
    (r"默認", "預設", "中國用語：應使用『預設』"),
    (r"界面", "介面", "中國用語：應使用『介面』"),
    (r"交互", "互動", "中國用語：應使用『互動』"),
    (r"鏈接|超鏈接", "連結 / 超連結", "中國用語：應使用『連結』或『超連結』"),
    (r"互聯網", "網際網路", "中國用語：應使用『網際網路』"),
    (r"局域網", "區域網路", "中國用語：應使用『區域網路』"),
    (r"U盤|優盤", "隨身碟", "中國用語：應使用『隨身碟』"),
    (r"充電寶|移動電源", "行動電源", "中國用語：應使用『行動電源』"),
    (r"移動硬盤", "外接硬碟", "中國用語：應使用『外接硬碟』"),
    (r"數據線", "傳輸線", "中國用語：應使用『傳輸線』"),
    (r"分辨率", "解析度", "中國用語：應使用『解析度』"),
    (r"截屏", "截圖", "中國用語：應使用『截圖』"),
    (r"話筒", "麥克風", "中國用語：應使用『麥克風』"),
    (r"攝像頭", "攝影鏡頭", "中國用語：應使用『攝影鏡頭』"),
    (r"激光", "雷射", "中國用語：應使用『雷射』"),
    (r"硅谷", "矽谷", "中國用語：應使用『矽谷』"),
    (r"航天", "航太", "中國用語：應使用『航太』"),
    (r"打印機", "印表機", "中國用語：應使用『印表機』"),
    (r"雲計算", "雲端運算", "中國用語：應使用『雲端運算』"),
    (r"人工智能", "人工智慧", "中國用語：應使用『人工智慧』"),
    (r"智能手機", "智慧型手機", "中國用語：應使用『智慧型手機』"),
    (r"智能設備", "智慧裝置", "中國用語：應使用『智慧裝置』"),
    (r"投屏", "投影 / 鏡射", "中國用語：應使用『投影』或『鏡射』"),
    (r"點贊|點讚", "按讚", "中國用語：應使用『按讚』"),
    (r"博主", "創作者 / YouTuber", "中國用語：應使用『創作者』或『YouTuber』"),
    (r"UP主|up主", "YouTuber", "中國用語：應使用『YouTuber』"),
    (r"帶貨", "直播銷售", "中國用語：應使用『促銷』或『叫賣』"),
    (r"充值", "儲值", "中國用語：應使用『儲值』"),
    (r"提現", "提款", "中國用語：應使用『提款』"),
    (r"激活", "啟用 / 啟動", "中國用語：應使用『啟用』或『啟動』"),
    (r"網民", "網友", "中國用語：應使用『網友』"),
    (r"網暴", "網路霸凌", "中國用語：應使用『網路霸凌』"),
    (r"出租車|打車", "計程車 / 叫車", "中國用語：應使用『計程車』或『叫車』"),
    (r"自行車", "腳踏車 / 單車", "中國用語：應使用『腳踏車』或『單車』"),
    (r"公交車", "公車", "中國用語：應使用『公車』"),
    (r"便利店", "超商", "中國用語：應使用『超商』或『便利商店』"),
    (r"方便麵", "泡麵", "中國用語：應使用『泡麵』"),
    (r"盒飯", "便當", "中國用語：應使用『便當』"),
    (r"土豆", "馬鈴薯", "中國稱馬鈴薯為土豆；臺灣土豆專指花生"),
    (r"西紅柿", "番茄", "中國用語：應使用『番茄』"),
    (r"菠蘿", "鳳梨", "中國用語：應使用『鳳梨』"),
    (r"獼猴桃", "奇異果", "中國用語：應使用『奇異果』"),
    (r"三文魚", "鮭魚", "中國用語：應使用『鮭魚』"),
    (r"金槍魚", "鮪魚", "中國用語：應使用『鮪魚』"),
    (r"黃油", "奶油", "中國用語：應使用『奶油』"),
    (r"酸奶", "優格", "中國用語：應使用『優格』"),
    (r"衛生間", "化妝室 / 洗手間", "中國用語：應使用『化妝室』或『洗手間』"),
    (r"圓珠筆", "原子筆", "中國用語：應使用『原子筆』"),
    (r"創可貼", "OK繃", "中國用語：應使用『OK繃』"),
    (r"塑料", "塑膠", "中國用語：應使用『塑膠』"),
    (r"小區", "社區", "中國用語：應使用『社區』"),
    (r"給力", "出色 / 亮眼", "支語：應使用『出色』、『亮眼』或『強大』"),
    (r"立馬", "立刻 / 馬上", "支語：應使用『立刻』或『馬上』"),
    (r"走心", "用心", "支語：應使用『用心』或『真誠』"),
    (r"閉環", "完整體系", "中國商務黑話：應使用『完整迴圈』或『完整架構』"),
    (r"賦能", "提供助力", "中國商務黑話：應使用『提供助力』或『賦予能力』"),
    (r"抓手", "切入點", "中國商務黑話：應使用『切入點』或『著力點』"),
    (r"打法", "策略作法", "中國商務黑話：應使用『作法』或『策略』"),
    (r"底層邏輯", "核心邏輯", "中國商務黑話：應使用『核心邏輯』或『基礎原理』"),
    (r"復盤|複盤", "檢討回顧", "中國商務黑話：應使用『回顧檢討』"),
    (r"忽悠", "唬弄", "中國俗語：應使用『唬弄』或『欺騙』"),
    (r"吐槽", "調侃", "中國網路用語：應使用『調侃』或『吐嘈』"),
    (r"牛逼|牛B|牛b", "厲害 / 強大", "中國粗俗語：應使用『厲害』或『強大』"),
    (r"裝逼|裝B", "擺架子", "中國粗俗語：應使用『擺架子』或『裝模作樣』"),
    (r"老鐵", "朋友 / 兄弟", "中國俗語：應使用『朋友』或『兄弟』"),
    (r"小夥伴", "夥伴", "中國流行語：應使用『夥伴』"),
    (r"接地氣", "親民貼切", "中國流行語：應使用『親民』或『貼切生活』"),
    (r"腦洞大開", "創意十足", "中國流行語：應使用『創意十足』或『別出心裁』"),
    (r"妥妥的", "穩穩的", "中國流行語：應使用『穩穩的』或『毫無疑問』"),
    (r"吃瓜", "看熱鬧", "中國網路支語：應使用『看熱鬧』或『圍觀』"),
    (r"帶節奏", "帶風向", "中國網路支語：應使用『帶風向』"),
    (r"割韭菜", "壓榨散戶", "中國流行語：應使用『壓榨散戶』"),
    (r"智商稅", "冤枉錢", "中國流行語：應使用『冤枉錢』"),
    (r"高大上", "高級大器", "中國流行語：應使用『高級』或『氣派』"),
    (r"出圈", "爆紅跨界", "中國網路用語：應使用『爆紅』或『蔚為風潮』"),
    (r"內卷|內捲", "過度內耗", "中國流行語：應使用『過度內耗』或『惡性競爭』"),
    (r"絕絕子", "太棒了", "中國飯圈支語：嚴格禁止"),
    (r"芭比Q", "搞砸了", "中國網路迷因：嚴格禁止"),
    (r"泰褲辣", "太酷了", "中國網路迷因：嚴格禁止"),
    (r"尊嘟假嘟", "真的假的", "中國網路迷因：嚴格禁止"),
    (r"栓Q", "謝謝", "中國網路迷因：嚴格禁止"),
    (r"破防", "崩潰動容", "中國網路用語：應使用『情緒崩潰』或『深受觸動』"),
    (r"踩坑|避坑", "踩雷 / 避雷", "中國網路用語：應使用『踩雷』或『避雷』"),
    (r"薅羊毛", "佔便宜", "中國網路用語：應使用『撿便宜』或『搶好康』"),
    (r"圈粉", "吸粉", "中國網路用語：應使用『吸粉』或『深受喜愛』"),
    (r"實錘", "確鑿鐵證", "中國網路用語：應使用『鐵證如山』或『確鑿證據』"),
    (r"槓精", "抬槓狂", "中國網路用語：應使用『抬槓狂』"),
    (r"特麼", "真是", "中國粗話口頭禪：應使用『真是』或『簡直』"),
]


def audit_taiwan_mandarin(text: str) -> List[dict]:
    """Audit text against known Mainland Chinese vocabulary, slang, and buzzwords.
    
    Returns a list of violation dictionaries with term, replacement suggestion, index, and context.
    """
    if not text or not isinstance(text, str):
        return []

    violations = []
    for pattern, suggestion, desc in FORBIDDEN_MAINLAND_TERMS:
        regex = re.compile(pattern)
        for match in regex.finditer(text):
            start = max(0, match.start() - 10)
            end = min(len(text), match.end() + 10)
            context = text[start:end].replace("\n", " ")
            violations.append({
                "term": match.group(0),
                "suggestion": suggestion,
                "description": desc,
                "position": match.start(),
                "context": f"...{context}..."
            })
    return violations


_PHYS_MASS_PATTERNS = [
    re.compile(r"(?:物理|天體|恆星|行星|黑洞|原子|分子|粒子|重力|引力|慣性|宇宙|相對論|中子星|太陽|地球|月球)(?:的|\s*)*(?:質量守恆|質量)"),
    re.compile(r"(?:質量守恆|質量缺陷|質量數|質量中心|靜止質量|引力質量|慣性質量|負質量|質能方程|質能等價)"),
    re.compile(r"(?:太陽|地球|月球|木星|電子|質子|夸克)質量"),
]
_PHYS_HORIZ_PATTERNS = [
    re.compile(r"(?:水平[線面儀軸尺邊角位移]|水平方向|水平投影|保持水平|水平旋轉|水平放置|水平對齊|呈水平)"),
]


def _convert_mass_and_level(text: str) -> str:
    saved: dict[str, str] = {}

    def protect(patterns, tag):
        nonlocal text
        for p in patterns:
            def _r(m):
                key = f"\u0001{tag}{len(saved)}\u0002"
                saved[key] = m.group(0)
                return key
            text = p.sub(_r, text)

    protect(_PHYS_MASS_PATTERNS, "M")
    protect(_PHYS_HORIZ_PATTERNS, "H")
    text = text.replace("質量", "品質").replace("水平", "水準")
    for key, orig in saved.items():
        text = text.replace(key, orig)
    return text


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

    # Pass 3: context-aware 質量->品質 and 水平->水準, protecting physics/geometry usages
    text = _convert_mass_and_level(text)

    # Clean up known OpenCC segmentation false-positives
    text = (text
            .replace("全閘道器注", "全網關注")
            .replace("閘道器注", "網關注")
            .replace("閘道器鍵", "關鍵")
            .replace("高畫質晰度", "高畫質")
            .replace("影片創作者博主", "影片創作者")
            .replace("影片影片", "影片")
            .replace("軟體軟體", "軟體")
            .replace("硬體硬體", "硬體")
            .replace("晶片晶片", "晶片")
            .replace("記憶體記憶體", "記憶體")
            .replace("演算法演算法", "演算法")
            .replace("預設預設", "預設")
            .replace("網路網路", "網路")
            .replace("網際網際網路", "網際網路")
            .replace("叫計程車叫車", "叫計程車"))

    return text


def enforce_taiwan_mandarin(
    text: str,
    client: Any = None,
    system_prompt: str | None = None
) -> Tuple[str, List[dict]]:
    """Strictly enforce Taiwan Traditional Chinese Mandarin on text.
    
    1. Runs OpenCC and the comprehensive replacement dictionary.
    2. Audits for any remaining forbidden Mainland terms.
    3. If critical violations remain and an LLM client is supplied, performs a targeted
       rewrite pass on offending sentences to ensure 100% natural Taiwanese phrasing.
    4. Returns (cleaned_text, remaining_violations).
    """
    if not text or not isinstance(text, str):
        return text, []

    # Step 1: Rule-based normalization pass
    cleaned = normalize_to_taiwan_mandarin(text)

    # Step 2: Audit
    violations = audit_taiwan_mandarin(cleaned)
    if not violations:
        return cleaned, []

    # Step 3: Targeted regex fallback substitution for any lingering flagged terms
    for v in violations:
        term = v["term"]
        sugg = v["suggestion"].split("/")[0].strip()
        cleaned = re.sub(re.escape(term), sugg, cleaned)

    # Step 4: Re-audit
    violations = audit_taiwan_mandarin(cleaned)
    if not violations:
        return cleaned, []

    # Step 5: If violations still remain and LLM client is available, run targeted rewrite
    if client and hasattr(client, "text"):
        try:
            terms_list = ", ".join(set(v["term"] for v in violations))
            prompt = (
                f"【嚴格語言淨化任務：去除所有中國大陸用語與支語】\n"
                f"以下旁白段落中仍殘留未完全轉換的大陸詞彙或句式：[{terms_list}]。\n"
                f"請將以下段落重新改寫為道地、純粹的臺灣正體中文（臺灣國語生活慣用語），"
                f"徹底去除所有中國用語、支語與大陸黑話，保留完整的資訊量與專業論點。\n\n"
                f"待改寫段落：\n{cleaned}\n\n"
                f"請直接輸出改寫後的純文字旁白，不要有任何多餘解釋或標記。"
            )
            sys_p = system_prompt or TAIWAN_MANDARIN_SYSTEM_PROMPT
            rewritten = client.text(prompt, sys_p, temperature=0.3, max_tokens=len(cleaned) * 3)
            if rewritten and len(rewritten.strip()) > len(cleaned) * 0.5:
                cleaned = normalize_to_taiwan_mandarin(rewritten.strip())
                violations = audit_taiwan_mandarin(cleaned)
        except Exception as err:
            log.warning("LLM Taiwan Mandarin rewrite pass failed: %s; keeping rule-cleaned text", err)

    return cleaned, violations
