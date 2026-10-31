"""Global AI technology news and frontier breakthrough topic discovery engine for YouTube educational videos."""
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

FALLBACK_AI_TOPICS: list[dict[str, Any]] = [
    {
        "topic": "OpenAI o3 思考推理模型顛覆 AI 競賽！為什麼「思考時間越長越聰明」能打破十年縮放定律？",
        "logline": "深度剖析 Test-Time Compute（推論期運算）革命，拆解 o1 與 o3 模型如何透過強化學習自我反思、糾錯與深層蒙地卡羅樹搜尋，改寫人工智慧發展公式。",
        "category": "前沿大模型與推理架構",
        "recommended_duration": 10.0,
        "recommended_style": "tech_schematic",
        "proof": {
            "platform": "OpenAI 官方技術發布與 NeurIPS 2024 前沿論文",
            "metrics": "Codeforces 評分破 2727 分達特級大師水準 / 博士級科學測試超越人類專家",
            "headline": "OpenAI o-series reasoning models introduce test-time search compute scaling paradigm",
            "url": "https://openai.com/index/learning-to-reason-with-llms/",
            "source_name": "OpenAI Research / arXiv:2409.12183",
            "why_popular": "大眾常以為預訓練模型參數已撞牆，OpenAI 開闢『推論期思考縮放』全新維度，讓 AI 具備真正解決複雜奧數與軟體架構能力，震撼全球科技界。",
        },
    },
    {
        "topic": "諾貝爾化學獎欽點！DeepMind AlphaFold 3 如何精準預測所有生命分子結構，引爆全球 AI 新藥海嘯？",
        "logline": "揭密 AlphaFold 3 從蛋白質跨越至 DNA、RNA 與配體分子的全原子擴散模型架構，剖析人工智慧如何將數十年的濕實驗生物研發縮短至幾秒鐘。",
        "category": "科學 AI 與生醫革命",
        "recommended_duration": 10.0,
        "recommended_style": "cinematic_documentary",
        "proof": {
            "platform": "《Nature》自然期刊封面論文與 Google DeepMind 官方發布",
            "metrics": "覆蓋全生物分子相互作用 / 預測精度相比前代提升超過 50%",
            "headline": "Accurate structure prediction of biomolecular interactions with AlphaFold 3 (Nature 2024)",
            "url": "https://www.nature.com/articles/s41586-024-07487-w",
            "source_name": "Google DeepMind / Isomorphic Labs / Nature",
            "why_popular": "AI 首次奪得諾貝爾獎等級榮譽，AlphaFold 3 徹底顛覆傳統藥物開發週期，將人類對生命密碼的理解推進到全新次元。",
        },
    },
    {
        "topic": "AI 真正接管電腦！Anthropic Computer Use 實機操作螢幕、點擊滑鼠，軟體工程師真的要失業了嗎？",
        "logline": "詳解 Claude 3.5 Sonnet 如何藉由視覺畫面辨識、座標轉換與鍵盤滑鼠 API，化身能像人類一樣自主操作瀏覽器與軟體環境的端到端 Agent。",
        "category": "自主 AI 智慧體與操作系統",
        "recommended_duration": 10.0,
        "recommended_style": "tech_schematic",
        "proof": {
            "platform": "Anthropic 官方技術白皮書與 GitHub 實測基準",
            "metrics": "OSWorld 基準測試領先現有模型近兩倍 / 支援完整 GUI 介面閉環操作",
            "headline": "Developing Computer Use: Claude 3.5 Sonnet can now interact directly with computer interfaces",
            "url": "https://www.anthropic.com/news/3-5-models-and-computer-use",
            "source_name": "Anthropic Engineering / OSWorld Benchmark",
            "why_popular": "跳脫聊天對話框，AI 第一次可以直接握起滑鼠在作業系統中填表格、寫程式碼並執行除錯，象徵通用人機介面轉移的歷史時刻。",
        },
    },
    {
        "topic": "輝達最強 AI 巨獸 Blackwell B200！液冷散熱、NVLink 5 與 2000 瓦功耗背後的晶片工程奇蹟",
        "logline": "拆解 2080 億電晶體雙晶粒雙向互連技術、第 5 代 NVLink 驚人的每秒 1.8 TB 雙向頻寬，以及為什麼現代資料中心必須全面進入液冷世代。",
        "category": "AI 晶片與超級運算硬體",
        "recommended_duration": 10.0,
        "recommended_style": "tech_schematic",
        "proof": {
            "platform": "NVIDIA GTC 大會技術主題演講與台積電 4NP 製程發布",
            "metrics": "單晶片算力高達 20 PFLOPS FP4 / LLM 推論吞吐量提升 30 倍",
            "headline": "NVIDIA Blackwell Architecture: World's Most Powerful Chip for Trillion-Parameter AI",
            "url": "https://www.nvidia.com/en-us/data-center/technologies/blackwell-architecture/",
            "source_name": "NVIDIA / TSMC Technology Symposium",
            "why_popular": "全球科技巨頭瘋狂搶購的算力核武，結合台積電先進封裝與超大規模液冷散熱工程，極具視覺衝擊力與硬核科技魅力。",
        },
    },
    {
        "topic": "具身智慧大爆發！Tesla Optimus 與 Figure 02 人形機器人，走進工廠流水線的終極大腦秘密",
        "logline": "從神經網路端到端視覺移動（End-to-End Visuomotor Policies）到多模態具身模型，探討人形機器人如何學會看懂物理空間、靈巧操縱手指組裝零件。",
        "category": "具身智慧與實體機器人",
        "recommended_duration": 10.0,
        "recommended_style": "photorealistic_cinema",
        "proof": {
            "platform": "BMW 斯巴達堡工廠實測報告與 Tesla AI Day 技術展示",
            "metrics": "Figure 02 成功進駐汽車工廠實習組裝 / 自由度高達 16 個靈巧手部關節",
            "headline": "Humanoid robot Figure 02 successfully deployed inside BMW manufacturing plant",
            "url": "https://www.figure.ai/",
            "source_name": "Figure AI / Tesla AI Robotics Division / IEEE Spectrum",
            "why_popular": "科幻電影中的仿生機器人正在真實走入人類工廠，大模型賦予實體身體後所展現的學習速度超乎預期，全球引頸期盼。",
        },
    },
    {
        "topic": "不只是生成影片！Sora 與世界模型（World Models）如何讓 AI 理解真實物理世界的運作規律？",
        "logline": "從文字擴散變換器（DiT）到三維物理時空區塊（Spacetime Patches），解析次世代生成式 AI 如何從被動模仿像素進化到預測重力、光影與流體動力學。",
        "category": "世界模型與前沿視覺生成",
        "recommended_duration": 10.0,
        "recommended_style": "tech_schematic",
        "proof": {
            "platform": "OpenAI Sora 官方技術報告與 NeurIPS 世界模型前沿研究",
            "metrics": "支援高達 1080p 60fps 物理逼真影像時空生成 / 具備 3D 空間一致性記憶",
            "headline": "Video generation models as world simulators: technical report on spacetime latent diffusion",
            "url": "https://openai.com/index/video-generation-models-as-world-simulators/",
            "source_name": "OpenAI Research / DeepMind Genie Project",
            "why_popular": "視訊生成被視為通往 AGI 世界模型的必經之路，讓大眾看懂 AI 是如何從單純作畫走向理解宇宙物理法則的震撼演化。",
        },
    },
    {
        "topic": "AI 算力大塞車！台積電埃米時代 GAA 奈米片與次世代 HBM4 記憶體，如何成為全球 AI 霸權生死線？",
        "logline": "解密記憶體牆（Memory Wall）瓶頸，拆解 3D IC、台積電 CoWoS 先進封裝與三星/SK海力士 16 層堆疊 HBM4 如何決定下一代人工智慧的生死極限。",
        "category": "半導體製程與先進封裝",
        "recommended_duration": 10.0,
        "recommended_style": "tech_schematic",
        "proof": {
            "platform": "台積電開放創新平台（OIP）論壇與 JEDEC 固態技術協會標準",
            "metrics": "HBM4 匯流排寬度倍增至 2048 位元 / 台積電 CoWoS 產能年增超過 150%",
            "headline": "JEDEC publishes HBM4 memory standard: double the interconnect width for next-gen AI accelerators",
            "url": "https://www.jedec.org/",
            "source_name": "TSMC Technology Symposium / JEDEC / SK Hynix",
            "why_popular": "台灣半導體位居全球 AI 革命核心心臟，拆解晶片底層物理極限與先進封裝技術，既具備高度家國榮譽感，又充滿深度知識含金量。",
        },
    },
    {
        "topic": "不連網也能跑！小語言模型（SLM）與手機 NPU 晶片突圍，我們真的需要十億參數跑在手掌心嗎？",
        "logline": "從 Apple Intelligence 到微軟 Phi-4 與 Google Gemma 2，探討模型蒸餾（Distillation）、4-bit 量化與混合專家架構如何讓行動裝置實現毫秒級隱私離線 AI。",
        "category": "邊緣端 AI 與輕量化架構",
        "recommended_duration": 5.0,
        "recommended_style": "photorealistic_cinema",
        "proof": {
            "platform": "Apple Machine Learning Research & Microsoft Research Technical Papers",
            "metrics": "3B 參數量化模型在行動端 NPU 達到每秒 30 tokens 以上流暢速度",
            "headline": "On-device language models: distillation, quantization and neural engine optimization",
            "url": "https://machinelearning.apple.com/",
            "source_name": "Apple ML Research / Microsoft Research / Hugging Face",
            "why_popular": "每個人都擁有一部智慧型手機，端側 AI 直接關乎個人隱私、電池續航與不用付雲端訂閱費的革命性便利體驗。",
        },
    },
]


def discover_ai_topic(exclude_topics: list[str] | None = None) -> dict[str, Any]:
    """
    Researches and produces ONE fascinating, high-impact topic focusing on
    world AI technology news, frontier breakthroughs, and industry shifts.
    """
    exclude = set(t.strip().lower() for t in (exclude_topics or []))

    from core.config import get_secret
    provider_override = "gemini" if get_secret("GEMINI_API_KEY") else None

    # Focus angles for inspiration
    ai_subfields = [
        "前沿大模型架構與推論期運算（Reasoning Models, Test-Time Compute Scaling, o1, o3, DeepSeek R1, 鏈式思考自我驗證）",
        "自主 AI 智慧體與人機介面革命（AI Agents, Computer Use, 軟體工程自動化, 瀏覽器操控, 工作流閉環）",
        "具身智慧與實體人形機器人（Embodied AI, Tesla Optimus, Figure 02, Boston Dynamics Atlas, 端到端神經網路控制）",
        "次世代 AI 晶片與算力硬體（NVIDIA Blackwell B200, 液冷架構, TPU v6, 自研 ASIC 晶片, 2000W 散熱挑戰）",
        "半導體先進封裝與記憶體牆（台積電 2nm GAA 奈米片, CoWoS 產能競賽, 次世代 HBM4 堆疊技術）",
        "多模態空間理解與世界模型（World Models, Sora, Genie 2, 物理規律預測, 3D 空間運算與視訊生成）",
        "端側輕量化 AI 與晶片神經引擎（On-Device SLM, Apple Intelligence, Phi-4, 行動端 NPU 量化與隱私算力）",
        "科學 AI 突破與生命革命（DeepMind AlphaFold 3, AI 預測全分子結構, AI 核融合電漿控制, 新材料研發）",
    ]
    chosen_field = random.choice(ai_subfields)

    import threading

    llm_result: dict[str, Any] = {}
    llm_error: list[Exception] = []

    def _worker():
        try:
            client = LLMClient("research", provider_override=provider_override, json_retries=1)
            prompt = (
                "You are an elite Silicon Valley AI technology analyst and high-production YouTube tech documentary director (inspired by creators like 極客灣, 柴知道, Two Minute Papers, Yannic Kilcher, 泛科學, TechLead, ColdFusion).\n"
                "Your task is to propose ONE highly viral, technically rigorous, and captivating topic focusing on 'NEW AI TECHNOLOGY NEWS IN THE WORLD' (全球最新 AI 前沿科技與產業重大突破).\n"
                f"Suggested AI frontier focus area for inspiration: {chosen_field}\n\n"
                f"Already queued topics to EXCLUDE (do not duplicate or copy closely):\n{list(exclude)[:10]}\n\n"
                "Core Angles to explore:\n"
                "- 推論期運算突破（大模型不再只靠死背巨量預訓練，而是具備自我反思與測試期深度搜尋）\n"
                "- 具身智慧機器人（人形機器人如何進駐汽車與物流工廠，解決真實物理空間抓取問題）\n"
                "- AI 算力基建與半導體（台積電先進封裝、HBM4 記憶體頻寬瓶頸、千瓦級液冷散熱工程）\n"
                "- 自主 Agent 與軟體顛覆（AI 接管滑鼠鍵盤、自主除錯上線、顛覆傳統軟體生態）\n"
                "- 世界模型（World Models）與物理規律模擬（超越像素生成，進入物理空間規律預測）\n\n"
                "Requirements:\n"
                "1. Output valid JSON only.\n"
                "2. 'topic': High-CTR, curiosity-driven YouTube documentary title in standard Taiwan Traditional Chinese (台灣繁體中文，嚴禁大陸簡體與大陸用語，用詞精準有力，引人入勝).\n"
                "3. 'logline': 1-2 sentence compelling summary of what the video uncovers, explains, and demystifies.\n"
                "4. 'category': Short category string (e.g. '全球 AI 科技前沿', '前沿大模型與推理架構', '具身智慧與實體機器人', 'AI 晶片與超級運算硬體', '世界模型與前沿視覺生成').\n"
                "5. 'recommended_duration': 5.0 or 10.0.\n"
                "6. 'recommended_style': One of ('tech_schematic', 'photorealistic_cinema', 'cinematic_documentary', 'hyperreal_3d').\n"
                "7. 'proof': Object containing:\n"
                "   - 'platform': (e.g. 'NeurIPS 頂會論文 / OpenAI 官方工程日誌 / Nature 自然期刊')\n"
                "   - 'metrics': (e.g. '基準測試超越人類頂尖專家 / 全球科技巨頭千億美元競逐 / 突破十萬次實機運行')\n"
                "   - 'headline': Cited official technical paper title or engineering release headline\n"
                "   - 'url': Real reference or portal URL (e.g. arXiv paper, OpenAI, Nature, DeepMind, NVIDIA, IEEE Spectrum)\n"
                "   - 'source_name': Name of primary research lab, tech organization, or scientific journal\n"
                "   - 'why_popular': Why this AI breakthrough electrifies tech enthusiasts and broad audiences alike (顛覆認知、跨越人機界限、引領全球未來十年科技走向)\n"
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
        data["type"] = "ai_technology"
        data["id"] = f"tq_{int(time.time() * 1000)}"
        data["created_at"] = datetime.datetime.now().isoformat()
        return data

    if llm_error:
        log.warning("LLM AI topic generation failed (%s); falling back to curated candidates", llm_error[0])
    else:
        log.info("LLM AI topic generation timed out; falling back to curated candidates")

    # Fallback to curated candidates not in exclude
    cands = [item for item in FALLBACK_AI_TOPICS if item["topic"].strip().lower() not in exclude
             and not any(item["topic"].strip().lower() in ext for ext in exclude)]

    chosen = random.choice(cands) if cands else FALLBACK_AI_TOPICS[0]
    res = dict(chosen)
    res["type"] = "ai_technology"
    res["id"] = f"tq_{int(time.time() * 1000)}"
    res["created_at"] = datetime.datetime.now().isoformat()
    return res
