"""Taiwan Traditional Chinese Mandarin (台灣繁體中文 / 國語) language processing and normalization.

Ensures scripts, research outlines, and narration text strictly adhere to
Taiwanese Mandarin vocabulary, terminology, and natural spoken idioms,
while completely eliminating Mainland Chinese simplified phrasing, buzzwords, and "支語".
"""
from __future__ import annotations

import json
import re
from typing import Any, List, Tuple

from core.logging_setup import log

try:
    import opencc
    _CC_T2S = opencc.OpenCC("t2s")
    _CC_S2TWP = opencc.OpenCC("s2twp")
    _CC_S2T = opencc.OpenCC("s2t")
except Exception as _e:
    _CC_T2S = None
    _CC_S2TWP = None
    _CC_S2T = None
    log.warning("OpenCC could not be initialized (%s); using rule-based dictionary only", _e)


# ==============================================================================
# PROHIBITED CHINA (PRC) DOMAINS, PLATFORMS, AND STATE MEDIA
# China alters, rewrites, and censors historical, geopolitical, and factual records
# for political propaganda. All sources from mainland China and simplified Chinese
# are strictly prohibited.
# ==============================================================================
PROHIBITED_CHINA_DOMAINS = {
    ".cn", ".com.cn", ".gov.cn", ".edu.cn", ".org.cn", ".net.cn", ".mil.cn",
    "baidu.com", "zhihu.com", "bilibili.com", "weibo.com", "weibo.cn",
    "xinhuanet.com", "news.cn", "people.com.cn", "peopledaily.com.cn",
    "cctv.com", "cgtn.com", "cri.cn", "globaltimes.cn", "chinadaily.com.cn",
    "sohu.com", "sina.com.cn", "sina.cn", "163.com", "netease.com",
    "qq.com", "tencent.com", "weixin.qq.com", "wechat.com",
    "csdn.net", "douban.com", "xiaohongshu.com", "douyin.com",
    "toutiao.com", "byteance.com", "kuaishou.com", "tieba.baidu.com",
    "baike.baidu.com", "360.cn", "so.com", "sogou.com", "huanqiu.com",
    "guancha.cn", "thepaper.cn", "ifeng.com", "chinaso.com", "youth.cn",
    "gmw.cn", "chinanews.com.cn", "chinanews.com", "cyol.com", "zjol.com.cn",
    "eastday.com", "dpm.org.cn", "bmy.com.cn"
}

PROHIBITED_CHINA_NAMES = [
    "新華社", "人民日報", "央視", "中國中央電視台", "環球時報", "觀察者網",
    "中國新聞社", "中新社", "光明日報", "中國日報", "求是", "學習強國",
    "百度", "知乎", "嗶哩嗶哩", "抖音", "小紅書", "今日頭條", "微博",
    "澎湃新聞", "共青團", "國務院新聞辦", "中共中央", "中宣部",
    "cctv", "cgtn", "百家讲坛", "百家講壇", "央视频", "央視頻",
]


def is_prohibited_china_source(source_str: str) -> tuple[bool, str]:
    """Check if a URL or source name belongs to mainland China (PRC) or CCP state media.
    
    Returns (is_prohibited, reason).
    """
    if not source_str or not isinstance(source_str, str):
        return False, ""
    
    src_lower = source_str.lower().strip()
    
    # Check domain patterns
    for dom in PROHIBITED_CHINA_DOMAINS:
        if dom.startswith("."):
            # e.g. .cn top level domain
            if re.search(r"https?://[^\s/]*" + re.escape(dom) + r"([/:?]|$)", src_lower):
                return True, f"Prohibited PRC mainland domain ({dom})"
        else:
            if dom in src_lower:
                return True, f"Prohibited PRC platform or domain ({dom})"
                
    # Check state media / organization names (case-insensitive)
    for name in PROHIBITED_CHINA_NAMES:
        if name.lower() in src_lower:
            return True, f"Prohibited PRC state media or platform ({name})"
            
    return False, ""


# Common Simplified Chinese characters distinct from Traditional Chinese
_SIMPLIFIED_DISTINCT_CHARS = set(
    "爱罢备笔毕边惨仓产长尝车彻尘称惩迟齿虫宠抽处触辞从聪达呆代带单担胆弹党挡导灯邓敌"
    "订顶东动冻斗独顿队对吨夺舵尔儿耳发罚阀法矾反贩饭访纺飞废费纷坟奋讽丰风凤肤福抚复"
    "负妇盖干赶个巩沟构购谷顾刮关观馆惯广规硅归龟国过海汉号呵合轰红后胡壶护画划话怀坏"
    "欢环还换黄荒会伙获击机积饥鸡极际继夹价驾歼监艰渐捡践简剪见鉴江将奖浆蒋酱胶浇骄娇"
    "阶街节杰洁借届斤谨进尽劲荆茎惊经竞静纠酒旧救就居举局聚惧剧据距惧卷眷觉绝决军君开"
    "凯颗壳克肯垦恳阔腊蜡来兰栏览蓝篮浪捞劳牢姥乐类累泪离里礼历丽励砾帘联恋粮辽僚疗寮"
    "列猎临林邻岭领浏留龙楼漏滤录陆驴乱轮罗逻络妈马码玛蚂马谩猫毛门扪闷们猛蒙眯弥觅眠"
    "缅灭庙灭民悯敏名明鸣命摩磨魔墨没莫谋母亩目耐南难囊脑恼闹呢嫩能泥拟逆匿年撵念娘酿"
    "鸟尿捏聂啮镊狞宁凝扭纽农浓奴怒女偶趴爬啪帕拍排牌派潘盘畔庞旁跑泡胚陪培配佩辔喷棚"
    "蓬碰膨批披劈皮疲脾匹辟片偏便篇漂瓢票撇瞥乒凭评凭频拼聘贫频苹瓶评平魄破剖扑铺仆瀑"
    "凄齐骑旗歧祈脐崎弃齐启器迁牵铅千迁乾签谦前欠枪强抢墙悄乔桥乔锹翘窍切且妾窃钦侵亲"
    "轻氢清倾晴请庆穷琼秋丘求囚求曲屈驱趋渠取去趣圈全权泉劝券确群然燃壤让饶扰绕惹热人"
    "仁忍任认扔仍日荣冗揉柔肉儒如茹乳辱入软锐瑞润若塞三伞丧扫骚色森僧杀沙纱刹傻煞晒伤"
    "商晌賞上尚梢烧绍少勺哨奢舌蛇舍赦摄慑涉社设射涉申伸身深神审渗甚慎升生声牲胜绳盛圣"
    "师失狮湿诗尸十石时识实食拾蚀适示市饰誓势嗜室视试收手首寿受兽售授狩瘦书树竖数耍衰"
    "摔霜双爽谁水税睡顺说硕死祀四寺似饲肆松耸宋诵讼颂搜嗖搜俗诉肃素速粟算穗孙损笋缩琐"
    "索所塔踏胎台态泰贪摊滩瘫坛谈叹炭汤糖堂膛唐躺烫掏涛桃淘套特藤疼腾梯提题啼体屉剃替"
    "天添田甜填条跳帖铁听挺通同统痛投头透秃图涂途屠土吐唾团推蜕腿退脱拖妥驼椭拓唾挖哇"
    "袜蛙娃歪外弯湾玩顽挽晚惋碗万汪亡网枉忘望妄威微危巍委违唯维伪纬萎畏胃喂魏文纹闻蚊"
    "吻稳问翁蜗窝我握卧乌屋污钨恶巫呜誣无吴五午武侮悟晤物勿雾务吸希稀析昔息悉夕西膝席"
    "袭喜洗细系戏隙吓侠夏峡下厦先仙鲜纤闲现宪县险线相香乡详祥想享向项响象像消硝销小效"
    "校笑肖孝哮些歇协斜携挟胁鞋写泄泻屑谢芯心辛新薪信星腥醒兴幸性凶兄胸雄熊休修羞嗅秀"
    "袖锈须虚需徐许叙续畜轩喧悬选癣绚学雪血寻循旬询训讯逊巡押鸦鸭压崖涯雅哑亚讶研炎岩"
    "严言延沿掩眼焰演厌宴艳验央殃秧氧扬羊阳杨洋仰养样摇尧遥窑瑶谣耀药耀爷也野业夜叶医"
    "衣依仪夷宜移遗疑乙已以矣亿忆义议异易医役抑译益谊疫谊溢毅翼阴茵荫音银引饮隐印英鹰"
    "应营萤营赢盈迎颖佣拥庸痈咏泳勇踊用优忧幽悠尤由犹油游友有右佑幼诱于余鱼渔隅盂愚娱"
    "愉逾舆予羽宇雨语狱育玉浴预域欲遇寓御裕愈誉渊冤元原圆园员源远愿约跃粤月悦乐阅耘云"
    "运匀韵杂灾载再在咱攒暂赞遭遭遭凿躁造灶燥燥则责泽择贼怎赠增扎札轧闸炸摘斋寨战占瞻"
    "斩展盏战站张涨掌丈仗账障胀招昭找沼兆照赵罩折哲辄者遮谪折震镇阵鸩振针砧珍枕疹诊镇"
    "阵振争蒸征怔整政正症之支汁芝枝知织肢脂直值殖植执指止址齿旨止址纸指致智滞置帜质炙"
    "掷中忠终钟盅肿重州舟周洲昼皱咒宙昼骤朱蛛猪诸诛逐助祝注著驻柱筑铸祝砖转传专庄装壮"
    "状桩捉桌灼拙卓茁浊准酌著啄孜兹滋淄资仔姿滋子自宗总纵阻祖组钻攥罪尊遵昨左佐作做座"
)

# Characters that are legitimately standard Traditional Chinese characters but s2t maps them anyway
TRADITIONAL_COMPATIBLE_MERGED = set("岳里后面才干松板台准余只复钟秋系致谷征采胡沈苏郁注脏折")


def contains_simplified_chinese(text: str) -> tuple[bool, list[str]]:
    """Detect if text contains simplified Chinese characters that differ from Taiwan Traditional characters.
    
    Returns (has_simplified, sample_simplified_chars).
    """
    if not text or not isinstance(text, str):
        return False, []
    
    found: list[str] = []
    if _CC_S2T:
        try:
            for c in text:
                if not ("\u4e00" <= c <= "\u9fff"):
                    continue
                conv_ch = _CC_S2T.convert(c)
                if c != conv_ch and c not in TRADITIONAL_COMPATIBLE_MERGED:
                    found.append(c)
                    if len(found) >= 10:
                        break
            return bool(found), found
        except Exception:
            pass

    # Fallback if OpenCC is unavailable
    for c in text:
        if c in _SIMPLIFIED_DISTINCT_CHARS and c not in TRADITIONAL_COMPATIBLE_MERGED:
            found.append(c)
            if len(found) >= 10:
                break

    return bool(found), found


def sanitize_and_filter_sources(sources: list[str] | list[dict]) -> tuple[list[str], list[str]]:
    """Filter out all sources originating from mainland China (PRC) or containing simplified Chinese.
    
    Returns (safe_sources, rejected_sources).
    """
    safe: list[str] = []
    rejected: list[str] = []
    
    for s in sources:
        s_text = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False)
        is_prc, reason = is_prohibited_china_source(s_text)
        if is_prc:
            rejected.append(f"{s_text} [{reason}]")
            continue
            
        has_simp, simp_chars = contains_simplified_chinese(s_text)
        if has_simp and len(simp_chars) >= 3:
            rejected.append(f"{s_text} [Contains Simplified Chinese: {''.join(simp_chars[:5])}]")
            continue
            
        safe.append(s if isinstance(s, str) else s_text)
        
    return safe, rejected


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

6. 【外國人名、國際地名與國名：100% 臺灣標準翻譯名稱（❌ 嚴格禁止中國大陸譯名）】：
   - 外國人名臺灣標準（括號內為嚴禁使用之大陸譯名）：
     * 歐巴馬（❌ 奧巴馬）
     * 川普（❌ 特朗普）
     * 柯林頓（❌ 克林頓）
     * 柴契爾 / 柴契爾夫人（❌ 撒切爾 / 撒切爾夫人）
     * 普丁（❌ 普京）
     * 澤倫斯基（❌ 澤連斯基）
     * 戈巴契夫（❌ 戈爾巴喬夫）
     * 史達林（❌ 斯大林）
     * 邱吉爾（❌ 丘吉爾）
     * 艾森豪（❌ 艾森豪威爾）
     * 甘迺迪（❌ 肯尼迪）
     * 雷根（❌ 里根）
     * 尼克森（❌ 尼克松）
     * 季辛吉（❌ 基辛格）
     * 賈伯斯（❌ 喬布斯）
     * 比爾·蓋茲 / 蓋茲（❌ 比爾·蓋茨 / 蓋茨）
     * 祖克柏（❌ 扎克伯格）
     * 貝佐斯（❌ 貝索斯）
     * 史匹柏（❌ 斯皮爾伯格）
     * 李奧納多·狄卡皮歐（❌ 萊昂納多·迪卡普里奧）
     * 達文西（❌ 達芬奇）
     * 梵谷（❌ 梵高）
     * 畢卡索（❌ 畢加索）
     * 莫內（❌ 莫奈）
     * 蕭邦（❌ 肖邦）
     * 莫札特（❌ 莫扎特）
     * 波耳（❌ 玻爾）
     * 薛丁格（❌ 薛定諤）
     * 克卜勒（❌ 開普勒）
     * 歐本海默（❌ 奧本海默）
     * 馮紐曼（❌ 馮·諾依曼 / 馮諾曼）
     * 笛卡兒（❌ 笛卡爾）
   - 國際地名、國名與城市臺灣標準：
     * 紐西蘭（❌ 新西蘭）
     * 雪梨（❌ 悉尼）
     * 坎培拉（❌ 堪培拉）
     * 聖荷西（❌ 聖何塞）
     * 德州 / 德克薩斯（❌ 得州 / 得克薩斯）
     * 休士頓（❌ 休斯敦）
     * 蒙特婁（❌ 蒙特利爾）
     * 杜拜（❌ 迪拜）
     * 阿布達比（❌ 阿布扎比）
     * 卡達（❌ 卡塔爾）
     * 沙烏地阿拉伯 / 沙烏地（❌ 沙特阿拉伯 / 沙特）
     * 伊斯坦堡（❌ 伊斯坦布爾）
     * 坎城（❌ 戛納）
     * 佛羅倫斯（❌ 佛羅倫薩）
     * 喬治亞（❌ 格魯吉亞）
     * 亞塞拜然（❌ 阿塞拜疆）
     * 肯亞（❌ 肯尼亞）
     * 奈及利亞（❌ 尼日利亞）
     * 衣索比亞（❌ 埃塞俄比亞）
     * 索馬利亞（❌ 索馬里）
     * 坦尚尼亞（❌ 坦桑尼亞）
     * 莫三比克（❌ 莫桑比克）
     * 辛巴威（❌ 津巴布韋）
     * 獅子山（❌ 塞拉利昂）
     * 象牙海岸（❌ 科特迪瓦）
     * 查德（❌ 乍得）
     * 盧安達（❌ 盧旺達）
     * 蒲隆地（❌ 布隆迪）
     * 賴比瑞亞（❌ 利比里亞）
     * 瓜地馬拉（❌ 危地馬拉）
     * 宏都拉斯（❌ 洪都拉斯）
     * 哥斯大黎加（❌ 哥斯達黎加）
     * 多明尼加（❌ 多米尼加）
     * 厄瓜多（❌ 厄瓜多爾）
     * 蘇利南（❌ 蘇里南）
     * 帛琉（❌ 帕勞）
     * 吐瓦魯（❌ 圖瓦盧）
     * 諾魯（❌ 瑙魯）
     * 萬那杜（❌ 瓦努阿圖）
     * 吉里巴斯（❌ 基里巴斯）
     * 巴布亞紐幾內亞（❌ 巴布亞新幾內亞）
   - 國防航太與科技翻譯名詞：
     * 太空梭（❌ 航天飛機）
     * 太空站（❌ 空間站）
     * 太空人（❌ 航天員、宇航員）
     * 巡弋飛彈（❌ 巡航導彈）
     * 匿蹤戰機（❌ 隱身戰機）
     * 核融合（❌ 核聚變）
     * 核分裂（❌ 核裂變）
     * 奈米（❌ 納米）
     * 都卜勒效應（❌ 多普勒效應）
     * 陣列（❌ 數組）
     * 巨集（❌ 宏）
     * 最佳化（❌ 優化）
     * 機率（❌ 概率）

7. 【100% 排除中國大陸來源與簡體字資料（防止政治扭曲與宣傳）】：
   - 中國官方機構、審查機制及中共黨媒長年因政治宣傳與意識形態目的，對歷史事實、二戰紀錄、國家主權、人權、公共衛生、統計數據與科學技術進行系統性竄改、粉飾與審查。
   - 本系統【100% 絕對禁止】採用或引用任何來自中國大陸（.cn 網域、新華社、人民日報、央視、環球時報、百度、知乎、Bilibili、微博、抖音、小紅書等）之網站、資料與說法。
   - 嚴格禁止使用簡體中文來源，所有事實考證必須採用臺灣正體中文權威資料（中央研究院、國立臺灣大學、教育部、國立編譯館、國史館、國家圖書館）或具國際公信力之學術期刊、百科全書（臺灣維基百科 zh-tw、大英百科 Britannica、Nature、Science、IEEE）與國際中立通訊社（Reuters、AP、BBC）。
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

    # --- 9. Foreign Personalities & Historical Figures (外國人名臺灣標準翻譯) ---
    (re.compile(r"[奧奥]巴[馬马]"), "歐巴馬"),
    (re.compile(r"特[朗]普"), "川普"),
    (re.compile(r"克林[頓顿]"), "柯林頓"),
    (re.compile(r"撒切[爾尔]夫人"), "柴契爾夫人"),
    (re.compile(r"撒切[爾尔]"), "柴契爾"),
    (re.compile(r"普[京]"), "普丁"),
    (re.compile(r"[澤泽][連连]斯基"), "澤倫斯基"),
    (re.compile(r"戈[爾尔]巴[喬乔]夫"), "戈巴契夫"),
    (re.compile(r"斯大林"), "史達林"),
    (re.compile(r"丘吉[爾尔]"), "邱吉爾"),
    (re.compile(r"艾森豪威[爾尔]"), "艾森豪"),
    (re.compile(r"肯尼迪"), "甘迺迪"),
    (re.compile(r"里[根]"), "雷根"),
    (re.compile(r"尼克松"), "尼克森"),
    (re.compile(r"基辛格"), "季辛吉"),
    (re.compile(r"[喬乔]布斯"), "賈伯斯"),
    (re.compile(r"比[爾尔]·?[蓋盖]茨"), "比爾·蓋茲"),
    (re.compile(r"(?<![覆掩遮蓋膝網])([蓋盖]茨)"), "蓋茲"),
    (re.compile(r"[扎紥]克伯格"), "祖克柏"),
    (re.compile(r"[貝贝]索斯"), "貝佐斯"),
    (re.compile(r"斯皮[爾尔]伯格"), "史匹柏"),
    (re.compile(r"[萊莱]昂[納纳]多"), "李奧納多"),
    (re.compile(r"迪卡普里[奧奥]"), "狄卡皮歐"),
    (re.compile(r"[達达]芬奇"), "達文西"),
    (re.compile(r"梵高"), "梵谷"),
    (re.compile(r"[畢毕]加索"), "畢卡索"),
    (re.compile(r"莫[奈]"), "莫內"),
    (re.compile(r"肖邦"), "蕭邦"),
    (re.compile(r"莫扎特"), "莫札特"),
    (re.compile(r"玻[爾尔]"), "波耳"),
    (re.compile(r"[薛]定[諤谔]"), "薛丁格"),
    (re.compile(r"[開开]普勒"), "克卜勒"),
    (re.compile(r"[奧奥]本海默"), "歐本海默"),
    (re.compile(r"馮·?[諾诺]依曼|冯·?[诺诺]依曼|馮·?[諾诺]曼|冯·?[诺诺]曼"), "馮紐曼"),
    (re.compile(r"笛卡[爾尔]"), "笛卡兒"),

    # --- 10. Foreign Geography, Countries & Cities (外國地名、國名與城市) ---
    (re.compile(r"新西[蘭兰]"), "紐西蘭"),
    (re.compile(r"悉尼"), "雪梨"),
    (re.compile(r"堪培拉"), "坎培拉"),
    (re.compile(r"[聖圣]何塞"), "聖荷西"),
    (re.compile(r"得克[薩萨]斯"), "德克薩斯"),
    (re.compile(r"(?<![獲取贏奪立心得])得州"), "德州"),
    (re.compile(r"休斯[敦]"), "休士頓"),
    (re.compile(r"蒙特利[爾尔]"), "蒙特婁"),
    (re.compile(r"迪拜"), "杜拜"),
    (re.compile(r"阿布扎比"), "阿布達比"),
    (re.compile(r"卡[塔特][爾尔]"), "卡達"),
    (re.compile(r"雅[爾尔][塔]"), "雅爾達"),
    (re.compile(r"沙特阿拉伯"), "沙烏地阿拉伯"),
    (re.compile(r"(?<![在赴從到進離])沙特(?=[國王軍政當聯境人局])"), "沙烏地"),
    (re.compile(r"伊斯坦布[爾尔林]"), "伊斯坦堡"),
    (re.compile(r"戛[納纳]"), "坎城"),
    (re.compile(r"佛[羅罗][倫伦][薩萨]"), "佛羅倫斯"),
    (re.compile(r"格[魯鲁]吉[亞亚]"), "喬治亞"),
    (re.compile(r"阿塞拜[疆]"), "亞塞拜然"),
    (re.compile(r"肯[尼][亞亚]"), "肯亞"),
    (re.compile(r"[尼]日利[亞亚]"), "奈及利亞"),
    (re.compile(r"埃塞俄比[亞亚]"), "衣索比亞"),
    (re.compile(r"索[馬马]里"), "索馬利亞"),
    (re.compile(r"坦桑[尼][亞亚]"), "坦尚尼亞"),
    (re.compile(r"莫桑比克"), "莫三比克"),
    (re.compile(r"津巴布[韋韦]"), "辛巴威"),
    (re.compile(r"塞拉利昂"), "獅子山"),
    (re.compile(r"科特迪瓦"), "象牙海岸"),
    (re.compile(r"乍得"), "查德"),
    (re.compile(r"[盧卢]旺[達达]"), "盧安達"),
    (re.compile(r"布隆迪"), "蒲隆地"),
    (re.compile(r"利比里[亞亚]"), "賴比瑞亞"),
    (re.compile(r"危地[馬马]拉"), "瓜地馬拉"),
    (re.compile(r"洪都拉斯"), "宏都拉斯"),
    (re.compile(r"哥斯[達达]黎加"), "哥斯大黎加"),
    (re.compile(r"多米[尼]加"), "多明尼加"),
    (re.compile(r"厄瓜多[爾尔]"), "厄瓜多"),
    (re.compile(r"[蘇苏]里南"), "蘇利南"),
    (re.compile(r"帕[勞劳]"), "帛琉"),
    (re.compile(r"[圖图]瓦[盧卢]"), "吐瓦魯"),
    (re.compile(r"[瑙]魯|[瑙]鲁"), "諾魯"),
    (re.compile(r"瓦努阿[圖图]"), "萬那杜"),
    (re.compile(r"基里巴斯"), "吉里巴斯"),
    (re.compile(r"巴布[亞亚]新[幾几][內内][亞亚]"), "巴布亞紐幾內亞"),

    # --- 11. Science, Space, Defense & Computing Terminology (科學、國防、太空與科技名詞) ---
    (re.compile(r"航天[飛飞][機机]"), "太空梭"),
    (re.compile(r"空[間间]站"), "太空站"),
    (re.compile(r"航天[員员]|宇航[員员]"), "太空人"),
    (re.compile(r"巡航[導导][彈弹]"), "巡弋飛彈"),
    (re.compile(r"[隱隐]身[戰战][機机]"), "匿蹤戰機"),
    (re.compile(r"核聚[變变]"), "核融合"),
    (re.compile(r"核裂[變变]"), "核分裂"),
    (re.compile(r"[納纳]米"), "奈米"),
    (re.compile(r"多普勒效[應应]"), "都卜勒效應"),
    (re.compile(r"[數数][組组]"), "陣列"),
    (re.compile(r"鏈[表]"), "鏈結串列"),
    (re.compile(r"(?<![佇排])隊[列]"), "佇列"),
    (re.compile(r"堆[棧栈]"), "堆疊"),
    (re.compile(r"哈希|散列"), "雜湊"),
    (re.compile(r"字[符]串"), "字串"),
    (re.compile(r"字[節节]"), "位元組"),
    (re.compile(r"比[特]"), "位元"),
    (re.compile(r"(?<!顯)顯[卡]"), "顯示卡"),
    (re.compile(r"主[板]"), "主機板"),
    (re.compile(r"[虛虚][擬拟][機机]"), "虛擬機器"),
    (re.compile(r"模[塊块]"), "模組"),
    (re.compile(r"線[程]"), "執行緒"),
    (re.compile(r"進[程]"), "行程"),
    (re.compile(r"端[口]"), "連接埠"),
    (re.compile(r"[帶带][寬宽]"), "頻寬"),
    (re.compile(r"[數数][據据]包"), "封包"),
    (re.compile(r"[優优]化"), "最佳化"),
    (re.compile(r"概[率]"), "機率"),
    (re.compile(r"矢[量]"), "向量"),
    (re.compile(r"[標标][量]"), "純量"),
    (re.compile(r"引力波"), "重力波"),
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

    # --- Foreign Names (外國人名大陸譯名審查) ---
    (r"奧巴馬", "歐巴馬", "中國大陸譯名：臺灣標準譯名為『歐巴馬』"),
    (r"特朗普", "川普", "中國大陸譯名：臺灣標準譯名為『川普』"),
    (r"克林頓", "柯林頓", "中國大陸譯名：臺灣標準譯名為『柯林頓』"),
    (r"撒切爾夫人", "柴契爾夫人", "中國大陸譯名：臺灣標準譯名為『柴契爾夫人』"),
    (r"撒切爾", "柴契爾", "中國大陸譯名：臺灣標準譯名為『柴契爾』"),
    (r"普京", "普丁", "中國大陸譯名：臺灣標準譯名為『普丁』"),
    (r"澤連斯基", "澤倫斯基", "中國大陸譯名：臺灣標準譯名為『澤倫斯基』"),
    (r"戈爾巴喬夫", "戈巴契夫", "中國大陸譯名：臺灣標準譯名為『戈巴契夫』"),
    (r"斯大林", "史達林", "中國大陸譯名：臺灣標準譯名為『史達林』"),
    (r"丘吉爾", "邱吉爾", "中國大陸譯名：臺灣標準譯名為『邱吉爾』"),
    (r"艾森豪威爾", "艾森豪", "中國大陸譯名：臺灣標準譯名為『艾森豪』"),
    (r"肯尼迪", "甘迺迪", "中國大陸譯名：臺灣標準譯名為『甘迺迪』"),
    (r"里根", "雷根", "中國大陸譯名：臺灣標準譯名為『雷根』"),
    (r"尼克松", "尼克森", "中國大陸譯名：臺灣標準譯名為『尼克森』"),
    (r"基辛格", "季辛吉", "中國大陸譯名：臺灣標準譯名為『季辛吉』"),
    (r"喬布斯", "賈伯斯", "中國大陸譯名：臺灣標準譯名為『賈伯斯』"),
    (r"比爾·?蓋茨", "比爾·蓋茲", "中國大陸譯名：臺灣標準譯名為『比爾·蓋茲』"),
    (r"扎克伯格", "祖克柏", "中國大陸譯名：臺灣標準譯名為『祖克柏』"),
    (r"貝索斯", "貝佐斯", "中國大陸譯名：臺灣標準譯名為『貝佐斯』"),
    (r"斯皮爾伯格", "史匹柏", "中國大陸譯名：臺灣標準譯名為『史匹柏』"),
    (r"萊昂納多", "李奧納多", "中國大陸譯名：臺灣標準譯名為『李奧納多』"),
    (r"迪卡普里奧", "狄卡皮歐", "中國大陸譯名：臺灣標準譯名為『狄卡皮歐』"),
    (r"達芬奇", "達文西", "中國大陸譯名：臺灣標準譯名為『達文西』"),
    (r"梵高", "梵谷", "中國大陸譯名：臺灣標準譯名為『梵谷』"),
    (r"畢加索", "畢卡索", "中國大陸譯名：臺灣標準譯名為『畢卡索』"),
    (r"莫奈", "莫內", "中國大陸譯名：臺灣標準譯名為『莫內』"),
    (r"肖邦", "蕭邦", "中國大陸譯名：臺灣標準譯名為『蕭邦』"),
    (r"莫扎特", "莫札特", "中國大陸譯名：臺灣標準譯名為『莫札特』"),
    (r"玻爾", "波耳", "中國大陸譯名：臺灣標準譯名為『波耳』"),
    (r"薛定諤", "薛丁格", "中國大陸譯名：臺灣標準譯名為『薛丁格』"),
    (r"開普勒", "克卜勒", "中國大陸譯名：臺灣標準譯名為『克卜勒』"),
    (r"奧本海默", "歐本海默", "中國大陸譯名：臺灣標準譯名為『歐本海默』"),
    (r"馮·?諾依曼|馮·?諾曼", "馮紐曼", "中國大陸譯名：臺灣標準譯名為『馮紐曼』"),
    (r"笛卡爾", "笛卡兒", "中國大陸譯名：臺灣標準譯名為『笛卡兒』"),

    # --- Foreign Places & Countries (外國地名與國名大陸譯名審查) ---
    (r"新西蘭", "紐西蘭", "中國大陸譯名：臺灣標準譯名為『紐西蘭』"),
    (r"悉尼", "雪梨", "中國大陸譯名：臺灣標準譯名為『雪梨』"),
    (r"堪培拉", "坎培拉", "中國大陸譯名：臺灣標準譯名為『坎培拉』"),
    (r"聖何塞", "聖荷西", "中國大陸譯名：臺灣標準譯名為『聖荷西』"),
    (r"得克薩斯", "德克薩斯", "中國大陸譯名：臺灣標準譯名為『德克薩斯』"),
    (r"(?<![獲取贏奪立心得])得州", "德州", "中國大陸簡稱：臺灣標準為『德州』"),
    (r"休斯敦", "休士頓", "中國大陸譯名：臺灣標準譯名為『休士頓』"),
    (r"蒙特利爾", "蒙特婁", "中國大陸譯名：臺灣標準譯名為『蒙特婁』"),
    (r"迪拜", "杜拜", "中國大陸譯名：臺灣標準譯名為『杜拜』"),
    (r"阿布扎比", "阿布達比", "中國大陸譯名：臺灣標準譯名為『阿布達比』"),
    (r"卡塔爾", "卡達", "中國大陸譯名：臺灣標準譯名為『卡達』"),
    (r"沙特阿拉伯", "沙烏地阿拉伯", "中國大陸譯名：臺灣標準譯名為『沙烏地阿拉伯』"),
    (r"(?<![在赴從到進離])沙特(?=[國王軍政當聯境人局])", "沙烏地", "中國大陸簡稱：臺灣標準為『沙烏地』"),
    (r"伊斯坦布爾", "伊斯坦堡", "中國大陸譯名：臺灣標準譯名為『伊斯坦堡』"),
    (r"戛納", "坎城", "中國大陸譯名：臺灣標準譯名為『坎城』"),
    (r"佛羅倫薩", "佛羅倫斯", "中國大陸譯名：臺灣標準譯名為『佛羅倫斯』"),
    (r"格魯吉亞", "喬治亞", "中國大陸譯名：臺灣標準譯名為『喬治亞』"),
    (r"阿塞拜疆", "亞塞拜然", "中國大陸譯名：臺灣標準譯名為『亞塞拜然』"),
    (r"肯尼亞", "肯亞", "中國大陸譯名：臺灣標準譯名為『肯亞』"),
    (r"尼日利亞", "奈及利亞", "中國大陸譯名：臺灣標準譯名為『奈及利亞』"),
    (r"埃塞俄比亞", "衣索比亞", "中國大陸譯名：臺灣標準譯名為『衣索比亞』"),
    (r"索馬里", "索馬利亞", "中國大陸譯名：臺灣標準譯名為『索馬利亞』"),
    (r"坦桑尼亞", "坦尚尼亞", "中國大陸譯名：臺灣標準譯名為『坦尚尼亞』"),
    (r"莫桑比克", "莫三比克", "中國大陸譯名：臺灣標準譯名為『莫三比克』"),
    (r"津巴布韋", "辛巴威", "中國大陸譯名：臺灣標準譯名為『辛巴威』"),
    (r"塞拉利昂", "獅子山", "中國大陸譯名：臺灣標準譯名為『獅子山』"),
    (r"科特迪瓦", "象牙海岸", "中國大陸譯名：臺灣標準譯名為『象牙海岸』"),
    (r"乍得", "查德", "中國大陸譯名：臺灣標準譯名為『查德』"),
    (r"盧旺達", "盧安達", "中國大陸譯名：臺灣標準譯名為『盧安達』"),
    (r"布隆迪", "蒲隆地", "中國大陸譯名：臺灣標準譯名為『蒲隆地』"),
    (r"利比里亞", "賴比瑞亞", "中國大陸譯名：臺灣標準譯名為『賴比瑞亞』"),
    (r"危地馬拉", "瓜地馬拉", "中國大陸譯名：臺灣標準譯名為『瓜地馬拉』"),
    (r"洪都拉斯", "宏都拉斯", "中國大陸譯名：臺灣標準譯名為『宏都拉斯』"),
    (r"哥斯達黎加", "哥斯大黎加", "中國大陸譯名：臺灣標準譯名為『哥斯大黎加』"),
    (r"多米尼加", "多明尼加", "中國大陸譯名：臺灣標準譯名為『多明尼加』"),
    (r"厄瓜多爾", "厄瓜多", "中國大陸譯名：臺灣標準譯名為『厄瓜多』"),
    (r"蘇里南", "蘇利南", "中國大陸譯名：臺灣標準譯名為『蘇利南』"),
    (r"帕勞", "帛琉", "中國大陸譯名：臺灣標準譯名為『帛琉』"),
    (r"圖瓦盧", "吐瓦魯", "中國大陸譯名：臺灣標準譯名為『吐瓦魯』"),
    (r"瑙魯", "諾魯", "中國大陸譯名：臺灣標準譯名為『諾魯』"),
    (r"瓦努阿圖", "萬那杜", "中國大陸譯名：臺灣標準譯名為『萬那杜』"),
    (r"基里巴斯", "吉里巴斯", "中國大陸譯名：臺灣標準譯名為『吉里巴斯』"),
    (r"巴布亞新幾內亞", "巴布亞紐幾內亞", "中國大陸譯名：臺灣標準譯名為『巴布亞紐幾內亞』"),

    # --- Science, Space & Military Terms (科學、太空與軍事用語審查) ---
    (r"航天飛機", "太空梭", "中國大陸名詞：臺灣標準為『太空梭』"),
    (r"空間站", "太空站", "中國大陸名詞：臺灣標準為『太空站』"),
    (r"航天員|宇航員", "太空人", "中國大陸名詞：臺灣標準為『太空人』"),
    (r"巡航導彈", "巡弋飛彈", "中國大陸名詞：臺灣標準為『巡弋飛彈』"),
    (r"隱身戰機", "匿蹤戰機", "中國大陸名詞：臺灣標準為『匿蹤戰機』"),
    (r"核聚變", "核融合", "中國大陸名詞：臺灣標準為『核融合』"),
    (r"核裂變", "核分裂", "中國大陸名詞：臺灣標準為『核分裂』"),
    (r"納米", "奈米", "中國大陸名詞：臺灣標準為『奈米』"),
    (r"多普勒效應", "都卜勒效應", "中國大陸名詞：臺灣標準為『都卜勒效應』"),
    (r"數組", "陣列", "中國大陸電腦名詞：臺灣標準為『陣列』"),
    (r"優化", "最佳化", "中國大陸用語：資訊科技與演算法情境應使用『最佳化』"),
    (r"概率", "機率", "中國大陸用語：臺灣學術與日常標準為『機率』"),
]


def audit_taiwan_mandarin(text: str) -> List[dict]:
    """Audit text against known Mainland Chinese vocabulary, slang, and buzzwords.
    
    Returns a list of violation dictionaries with term, replacement suggestion, index, and context.
    """
    if not text or not isinstance(text, str):
        return []

    # Audit normalized traditional text so simplified mainland inputs are also caught
    text_for_audit = _CC_S2T.convert(text) if _CC_S2T else text
    violations = []
    seen_terms_at_pos = set()
    for pattern, suggestion, desc in FORBIDDEN_MAINLAND_TERMS:
        regex = re.compile(pattern)
        for match in regex.finditer(text_for_audit):
            pos = match.start()
            term = match.group(0)
            key = (pos, term)
            if key in seen_terms_at_pos:
                continue
            seen_terms_at_pos.add(key)
            start = max(0, pos - 10)
            end = min(len(text_for_audit), match.end() + 10)
            context = text_for_audit[start:end].replace("\n", " ")
            violations.append({
                "term": term,
                "suggestion": suggestion,
                "description": desc,
                "position": pos,
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
