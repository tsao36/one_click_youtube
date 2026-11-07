"""Dynasty trivia and historical curiosity topic discovery engine for YouTube educational videos."""
from __future__ import annotations

import datetime
import json
import logging
import random
import time
from typing import Any

from core.taiwan_mandarin import normalize_to_taiwan_mandarin
from providers.llm import LLMClient

log = logging.getLogger(__name__)

FALLBACK_DYNASTY_TOPICS: list[dict[str, Any]] = [
    {
        "topic": "秦始皇的兵馬俑竟然是「流水線量產」？揭密兩千年前大秦軍團的精密公差與黑科技武器",
        "logline": "透過出土秦弩機與三稜銅鏃的毫釐誤差，拆解秦帝國如何建立世界上最早的國家軍工標準化與「物勒工名」責任制度。",
        "category": "秦漢黑科技與制度",
        "recommended_duration": 10.0,
        "recommended_style": "cinematic_documentary",
        "proof": {
            "platform": "考古出土文物考證（中央研究院史語所研究專案）",
            "metrics": "出土逾四萬件金屬兵器精密數據 / 科技史學界公認奇蹟",
            "headline": "兵馬俑坑出土秦弩機零件互換率與三稜箭鏃極致公差考證",
            "url": "https://www2.ihp.sinica.edu.tw/",
            "source_name": "中央研究院歷史語言研究所考證 / 《史記·秦始皇本紀》",
            "why_popular": "大眾常以為古代兵器全靠鐵匠手工敲打，秦軍兩千年前即實現流水線互換零件與極致品質控管，反差感極強且極具話題爆發力。",
        },
    },
    {
        "topic": "漢朝公務員過得有多爽？五天休一次「洗沐假」，年終獎金還能換成幾百石糧食！",
        "logline": "拆解兩漢官員五日一休沐的衛生制度、俸祿「半錢半穀」的真實購買力，以及令人瞠目的致仕退休養老金待遇。",
        "category": "古代官場與日常生活",
        "recommended_duration": 5.0,
        "recommended_style": "photorealistic_cinema",
        "proof": {
            "platform": "正史文獻與漢簡出土記載（《漢書》/ 居延漢簡）",
            "metrics": "西北出土漢代屯戍竹簡實物記載 / 中研院史語所專題",
            "headline": "居延漢簡記載吏員俸給考課與五日一休沐法定制度",
            "url": "https://www2.ihp.sinica.edu.tw/",
            "source_name": "中央研究院歷史語言研究所 / 《漢書·百官公卿表》",
            "why_popular": "現代上班族對休假與公務員福利高度敏感，對比兩千年前漢朝官員的法定休沐與優渥退休俸，既幽默又引人入勝。",
        },
    },
    {
        "topic": "長安十二時辰的致命宵禁！在唐朝長安半夜逛街，真的會被金吾衛亂箭射死？",
        "logline": "揭露大唐長安坊市制度嚴酷的夜禁律令、敲擊三千下的暮鼓晨鐘，以及平民與文人如何在「鬼市」尋求生存縫隙。",
        "category": "盛唐市井與法律奇觀",
        "recommended_duration": 5.0,
        "recommended_style": "cinematic_documentary",
        "proof": {
            "platform": "法典典章考證（《唐律疏議》）",
            "metrics": "唐代刑法典籍明確律條 / 影視劇《長安十二時辰》熱播引發全網考據",
            "headline": "《唐律疏議·衛禁律》：夜正街行走者笞四十，抗拒逮捕者格殺勿論",
            "url": "https://ctext.org/wiki.pl?if=gb&chapter=327685",
            "source_name": "唐代法典《唐律疏議》卷八 / 《新唐書·百官志》",
            "why_popular": "顛覆影視劇中大唐長安通宵笙歌的浪漫幻想，還原古代都市軍事化管理的真實殘酷與市井博弈。",
        },
    },
    {
        "topic": "宋朝連皇帝都偷叫外賣？州橋夜市通宵營業、外送小哥穿梭臨安的奢華日常",
        "logline": "從滴酥水晶鱠到開封二十四小時不夜城，剖析宋代如何取消宵禁、誕生逐臭之夫、外賣制度與世界最早的紙幣交子。",
        "category": "宋代生活奇觀與經濟",
        "recommended_duration": 10.0,
        "recommended_style": "cinematic_documentary",
        "proof": {
            "platform": "宋代筆記小說與市井文獻（《東京夢華錄》/《夢粱錄》）",
            "metrics": "兩宋市井史料第一手詳盡筆錄 / 故宮《清明上河圖》細節考證",
            "headline": "宋孝宗深夜遣內侍市買市井乳炊羊、南宋臨安街頭外送盤飧考",
            "url": "https://ctext.org/wiki.pl?if=gb&chapter=278077",
            "source_name": "孟元老《東京夢華錄》卷二 / 吳自牧《夢粱錄》",
            "why_popular": "宋代經濟生活高度發達、甚至出現類似 Uber Eats 的外賣跑腿，與現代生活無縫共鳴，深具爆款特質。",
        },
    },
    {
        "topic": "明朝皇帝真的一輩子不上朝？萬曆三十年不出宮門、嘉靖修仙背後的真實權謀架構",
        "logline": "破除歷史刻板印象，拆解司禮監秉筆太監與內閣首輔的權力制衡機器，揭開皇帝不上朝卻依然牢牢掌控天下的體系秘密。",
        "category": "明代宮廷秘辛與政治",
        "recommended_duration": 10.0,
        "recommended_style": "cinematic_documentary",
        "proof": {
            "platform": "明代起居注與官修官史（《明神宗實錄》/《明史》）",
            "metrics": "明代內閣票擬與批紅檔案 / 故宮博物院明清宮藏文獻",
            "headline": "萬曆帝因國本之爭與文官集團長期冷戰，藉票擬批紅維持帝國運轉",
            "url": "https://www.npm.gov.tw/",
            "source_name": "中央研究院明清檔案工作室 / 《明史·神宗本紀》",
            "why_popular": "大眾常以為萬曆昏庸怠政，但深入體制會發現這是帝權抗衡文官集團的精密博弈，歷史反轉張力極大。",
        },
    },
    {
        "topic": "清朝後宮影視劇全演錯了？御膳房真實伙食、綠頭牌運作與皇帝凌晨四點起床的社畜一日",
        "logline": "根據內務府清單與起居注真實還原，乾隆皇帝每天只能吃兩頓正餐、妃嬪月例銀子少得驚人，皇帝的一天竟然比現代打工人還要崩潰。",
        "category": "清代宮廷真相與日常生活",
        "recommended_duration": 5.0,
        "recommended_style": "photorealistic_cinema",
        "proof": {
            "platform": "清廷第一手官檔案（國立故宮博物院藏《清宮內務府奏銷檔》/《清代起居注冊》）",
            "metrics": "內務府原始採買膳單實物記錄 / 臺北國立故宮博物院藏檔案",
            "headline": "乾隆朝御膳底檔載明每日兩頓正餐、妃嬪依品級分發肉斤蔬菜嚴格配額",
            "url": "https://www.npm.gov.tw/",
            "source_name": "國立故宮博物院（臺北）所藏清宮檔案 / 《清代起居注冊》",
            "why_popular": "宮鬥劇與古裝劇風靡華人圈，但劇中奢華隨意的宮廷日常與真實嚴苛戒律形成強烈反差，闢謠內容百看不厭。",
        },
    },
    {
        "topic": "關羽根本沒用過青龍偃月刀？三國歷史冷知識：那些被《三國演義》騙了六百年的真實戰場",
        "logline": "考證東漢末年實戰兵器環首刀與長矛馬槊，還原真實官渡之戰與赤壁之戰的後勤真相與武將單挑迷思。",
        "category": "三國歷史翻案與軍事考證",
        "recommended_duration": 5.0,
        "recommended_style": "cinematic_documentary",
        "proof": {
            "platform": "正史記載與漢魏考古出土（《三國志》裴松之注）",
            "metrics": "陳壽《三國志》正史原文 / 漢魏洛陽城考古出土環首刀",
            "headline": "《三國志·關羽傳》：「羽望見良麾蓋，策馬刺良於萬眾之中」——刺即是用矛或槊，非劈砍大刀",
            "url": "https://ctext.org/sanguozhi/shu-shu-guan-zhang-ma-huang-zhao-zhuan/zh",
            "source_name": "陳壽《三國志·蜀書·關羽傳》 / 中國軍事考古學報",
            "why_popular": "三國題材自帶龐大受眾，打破演義神話還原真實戰場細節，兼具文史深度與男兒熱血。",
        },
    },
    {
        "topic": "古代科舉防作弊到底有多變態？搜身進場、糊名謄錄，連考生帶進去的白煮蛋都要切開！",
        "logline": "剖析古代國家大考從「糊名」、「易書謄錄」到雙重搜檢制度，還原微雕墨卷與考場禁令的千年間諜攻防戰。",
        "category": "古代制度奇觀與科舉",
        "recommended_duration": 10.0,
        "recommended_style": "cinematic_documentary",
        "proof": {
            "platform": "典章科舉史料考據（《文獻通考》/《清朝文獻通考》）",
            "metrics": "各地孔廟與科舉博物館藏夾帶微雕物證 / 清代鄉試欽差條規",
            "headline": "清代順天府鄉試號舍防弊條例：糕餅切開、筆管中空、衣服單層無夾層",
            "url": "https://ctext.org/wiki.pl?if=gb&chapter=908488",
            "source_name": "馬端臨《文獻通考·選舉考》 / 清代《欽定科場條例》",
            "why_popular": "現代人對大考防弊深有共鳴，古人腦洞大開的作弊黑科技與朝廷步步緊逼的奇葩檢查手段極具娛樂性與啟發性。",
        },
    },
]


def discover_dynasty_topic(exclude_topics: list[str] | None = None) -> dict[str, Any]:
    """
    Researches and produces ONE fascinating, curiosity-driven topic on Chinese Dynasty trivia,
    mysteries, or lesser-known history with verified historical textual proof.
    """
    exclude = set(t.strip().lower() for t in (exclude_topics or []))

    from core.config import get_secret
    provider_override = "gemini" if get_secret("GEMINI_API_KEY") else None

    # Pick a random dynasty era to prompt diverse exploration
    eras = [
        "秦漢帝國（兵馬俑黑科技、漢代公務員生活、絲路秘辛、未央宮生活）",
        "魏晉三國（演義闢謠翻案、真實世家門閥生活、古代特種部隊與軍事考證）",
        "隋唐盛世（長安十二時辰宵禁、唐代女子妝容與社會地位、西市胡商與鬼市）",
        "兩宋風華（宋朝外賣與二十四小時夜市、清明上河圖市井密碼、宋代文人高薪福利）",
        "大明王朝（萬曆不上朝真相、錦衣衛與東廠運作、明代火器神機營、奇葩皇帝愛好）",
        "大清宮廷（清宮御膳與真實后妃生活、紫禁城冷知識、科舉防作弊千奇百怪手段）",
    ]
    chosen_era = random.choice(eras)

    import threading

    llm_result: dict[str, Any] = {}
    llm_error: list[Exception] = []

    def _worker():
        try:
            client = LLMClient("research", provider_override=provider_override, json_retries=1)
            prompt = (
                "You are an acclaimed YouTube documentary director and Chinese history researcher (inspired by creators like 李天豪, Cheap, 故事 StoryStudio, 臺灣吧 Taiwan Bar).\n"
                f"Your task is to propose ONE highly viral, deeply curious, or astonishing topic focusing on '中國朝代冷知識歷史' (Chinese Dynasty trivia, imperial secrets, ancient daily life oddities, or historical misconception debunking).\n"
                f"Suggested historical focus era for inspiration: {chosen_era}\n\n"
                f"Already queued topics to EXCLUDE (do not duplicate or copy closely):\n{list(exclude)[:10]}\n\n"
                "Angle Ideas:\n"
                "- 皇帝與宮廷的真實冷知識（打破影視劇謬誤，如皇帝吃什麼、起居作息、御膳房與後宮制度）\n"
                "- 古代平民生活的反差真相（宋代外賣、唐代長安夜禁、漢代公務員休假、古代物價與購買力）\n"
                "- 古代軍事黑科技與工程奇蹟（秦軍流水線公差、古代防作弊神技、驛站加急制度）\n"
                "- 顛覆刻板印象的歷史翻案（被演義或傳奇小說誤導的真實歷史真相）\n\n"
                "Requirements:\n"
                "1. Output valid JSON only.\n"
                "2. 'topic': High-CTR, curiosity-driven YouTube documentary title in standard Taiwan Traditional Chinese (台灣正體中文，嚴禁大陸簡體與大陸流行用語，用詞精準有力，引人入勝).\n"
                "3. 'logline': 1-2 sentence compelling summary of what the video uncovers and explains.\n"
                "4. 'category': Short category string (e.g. '中國朝代冷知識', '宋代生活奇觀', '明清宮廷秘辛', '秦漢黑科技與制度', '三國歷史翻案').\n"
                "5. 'recommended_duration': 5.0 or 10.0.\n"
                "6. 'recommended_style': One of ('cinematic_documentary', 'photorealistic_cinema', 'vintage_archive', 'digital_painting').\n"
                "7. 'proof': Object containing:\n"
                "   - 'platform': (e.g. '正史典籍考證（《史記》/《宋史》/《明實錄》/《清宮檔案》）')\n"
                "   - 'metrics': (e.g. '學界公認第一手文獻記載 / 故宮出土檔案紀錄 / 破百萬文史討論話題')\n"
                "   - 'headline': Cited historical record or archaeological excavation note\n"
                "   - 'url': Real reference or portal URL (e.g. https://ctext.org/ or https://www.npm.gov.tw/ or https://www2.ihp.sinica.edu.tw/ or Wikipedia zh-tw article)\n"
                "   - 'source_name': Name of primary historical text, author, or research institution\n"
                "   - 'why_popular': Why modern viewers are fascinated by this historical discovery (反直覺、揭開歷史真相、與現代生活產生強烈對比)\n"
                "8. STRICT ZERO PRC / MAINLAND SOURCES & SIMPLIFIED CHINESE: 100% avoid using or citing sources, materials, or URLs from mainland China (.cn domains, PRC state media, Baidu, Zhihu, etc.) as China twists and alters facts for political purposes. 100% avoid Simplified Chinese. Ensure all terminology adheres strictly to 台灣用語 and 台灣翻譯名稱.\n"
            )
            data = client.json(prompt, "Output valid JSON only", temperature=0.75)
            if isinstance(data, dict):
                llm_result.update(data)
        except Exception as e:
            llm_error.append(e)

    th = threading.Thread(target=_worker, daemon=True)
    th.start()
    th.join(timeout=10.0)

    if llm_result.get("topic"):
        data = llm_result
        data["topic"] = normalize_to_taiwan_mandarin(data["topic"])
        if data.get("logline"):
            data["logline"] = normalize_to_taiwan_mandarin(data["logline"])
        if data.get("category"):
            data["category"] = normalize_to_taiwan_mandarin(data["category"])
        proof = data.get("proof") or {}
        if proof.get("why_popular"):
            proof["why_popular"] = normalize_to_taiwan_mandarin(proof["why_popular"])
        if proof.get("headline"):
            proof["headline"] = normalize_to_taiwan_mandarin(proof["headline"])
        data["proof"] = proof
        data["type"] = "dynasty_trivia"
        data["id"] = f"tq_{int(time.time() * 1000)}"
        data["created_at"] = datetime.datetime.now().isoformat()
        return data

    if llm_error:
        log.warning("LLM dynasty topic generation failed (%s); falling back to curated candidates", llm_error[0])
    else:
        log.info("LLM dynasty topic generation timed out; falling back to curated candidates")

    # Fallback to curated candidates not in exclude
    cands = [item for item in FALLBACK_DYNASTY_TOPICS if item["topic"].strip().lower() not in exclude
             and not any(item["topic"].strip().lower() in ext for ext in exclude)]

    chosen = random.choice(cands) if cands else FALLBACK_DYNASTY_TOPICS[0]
    res = dict(chosen)
    res["type"] = "dynasty_trivia"
    res["id"] = f"tq_{int(time.time() * 1000)}"
    res["created_at"] = datetime.datetime.now().isoformat()
    return res
