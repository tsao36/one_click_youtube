"""Tests for Taiwan Mandarin terminology, Taiwan standard translation names,
PRC/China source exclusion, and fact validity double-check engine.
"""
import json
import pytest
from pathlib import Path

from core.fact_checker import (
    double_check_facts,
    extract_claims_from_research_and_script,
    format_fact_check_markdown,
    save_fact_check_reports,
)
from core.taiwan_mandarin import (
    audit_taiwan_mandarin,
    contains_simplified_chinese,
    is_prohibited_china_source,
    normalize_to_taiwan_mandarin,
    sanitize_and_filter_sources,
)


def test_prohibited_china_source_detection():
    """Verify that mainland China (.cn) domains, platforms, and state media are strictly flagged."""
    prc_samples = [
        "https://news.cctv.com/world/123",
        "https://www.xinhuanet.com/politics/article.html",
        "https://baike.baidu.com/item/%E5%A5%A5%E5%B7%B4%E9%A9%AC",
        "https://www.zhihu.com/question/12345",
        "https://www.bilibili.com/video/BV123456",
        "https://weibo.com/u/123456",
        "http://www.people.com.cn/gb/paper.html",
        "https://globaltimes.cn/page/123.shtml",
        "https://blog.csdn.net/developer/article",
        "https://www.thepaper.cn/newsDetail_forward_123",
        "新華社專題考證報導",
        "人民日報社論",
        "中國中央電視台紀錄片頻道",
        "環球時報評論",
    ]
    for sample in prc_samples:
        is_prc, reason = is_prohibited_china_source(sample)
        assert is_prc is True, f"Failed to detect PRC source: {sample}"
        assert len(reason) > 0


def test_allowed_sources_not_flagged():
    """Verify that Taiwanese and international authoritative sources are not blocked."""
    safe_samples = [
        "https://www.sinica.edu.tw/",
        "https://www2.ihp.sinica.edu.tw/research",
        "https://www.npm.gov.tw/exhibition.aspx",
        "https://ctext.org/wiki.pl?chapter=123",
        "https://zh.wikipedia.org/zh-tw/%E8%87%BA%E7%81%A3",
        "https://en.wikipedia.org/wiki/Taiwan",
        "https://www.nature.com/articles/s41586-024-07487-w",
        "https://www.bbc.com/zhongwen/trad",
        "https://www.reuters.com/technology",
        "中央研究院歷史語言研究所",
        "國立臺灣大學歷史學系研究報告",
    ]
    for sample in safe_samples:
        is_prc, _ = is_prohibited_china_source(sample)
        assert is_prc is False, f"Erroneously flagged safe source: {sample}"


def test_sanitize_and_filter_sources():
    """Verify that sanitize_and_filter_sources cleanly separates safe from blocked sources."""
    mixed_sources = [
        "https://www.sinica.edu.tw/bulletin",
        "https://baike.baidu.com/item/test",
        "https://en.wikipedia.org/wiki/Steve_Jobs",
        "https://www.bilibili.com/video/BV111",
        "https://www.npm.gov.tw/",
        "新華社新聞發布",
    ]
    safe, rejected = sanitize_and_filter_sources(mixed_sources)
    assert len(safe) == 3
    assert len(rejected) == 3
    assert any("baidu.com" in r for r in rejected)
    assert any("bilibili.com" in r for r in rejected)
    assert any("新華社" in r for r in rejected)


def test_simplified_chinese_detection():
    """Verify detection of simplified characters distinct from traditional Chinese."""
    has_simp, chars = contains_simplified_chinese("这是简体字测试内容，包含芯片与视频。")
    assert has_simp is True
    assert len(chars) > 0

    has_simp_tw, chars_tw = contains_simplified_chinese("這是臺灣正體中文測試內容，包含晶片與影片。")
    assert has_simp_tw is False
    assert len(chars_tw) == 0


def test_taiwan_standard_translation_names():
    """Verify standard Taiwan translation names for foreign figures and historical personalities."""
    cases = [
        ("奥巴马与特朗普", "歐巴馬與川普"),
        ("克林顿与撒切尔夫人", "柯林頓與柴契爾夫人"),
        ("普京与泽连斯基会晤", "普丁與澤倫斯基會晤"),
        ("斯大林与丘吉尔在雅尔塔", "史達林與邱吉爾在雅爾達"),
        ("艾森豪威尔与肯尼迪总统", "艾森豪與甘迺迪總統"),
        ("里根与尼克松", "雷根與尼克森"),
        ("基辛格的外交政策", "季辛吉的外交政策"),
        ("乔布斯与盖茨创立科技巨头", "賈伯斯與蓋茲創立科技巨頭"),
        ("扎克伯格与贝索斯", "祖克柏與貝佐斯"),
        ("达芬奇与毕加索的艺术", "達文西與畢卡索的藝術"),
        ("梵高与莫奈", "梵谷與莫內"),
        ("肖邦与莫扎特的音乐", "蕭邦與莫札特的音樂"),
        ("玻尔与薛定谔的猫", "波耳與薛丁格的貓"),
        ("开普勒定律与奥本海默", "克卜勒定律與歐本海默"),
        ("冯诺依曼架构与笛卡尔哲学", "馮紐曼架構與笛卡兒哲學"),
    ]
    for raw, expected in cases:
        norm = normalize_to_taiwan_mandarin(raw)
        assert expected in norm, f"Expected '{expected}' in '{norm}' (from '{raw}')"


def test_taiwan_standard_geography_and_country_names():
    """Verify standard Taiwan translation names for foreign geography, countries and cities."""
    cases = [
        ("前往新西兰与悉尼旅行", "前往紐西蘭與雪梨旅行"),
        ("澳洲首都堪培拉", "澳洲首都坎培拉"),
        ("硅谷圣何塞", "矽谷聖荷西"),
        ("得克萨斯州休斯敦", "德克薩斯州休士頓"),
        ("加拿大蒙特利尔", "加拿大蒙特婁"),
        ("阿联酋迪拜与阿布扎比", "阿聯酋杜拜與阿布達比"),
        ("卡特尔世界杯", "卡達世界盃"),
        ("沙特阿拉伯与伊斯坦布尔", "沙烏地阿拉伯與伊斯坦堡"),
        ("戛纳电影节", "坎城電影節"),
        ("意大利佛罗伦萨", "義大利佛羅倫斯"),
        ("格鲁吉亚与阿塞拜疆", "喬治亞與亞塞拜然"),
        ("肯尼亚与埃塞俄比亚", "肯亞與衣索比亞"),
        ("索马里与坦桑尼亚", "索馬利亞與坦尚尼亞"),
    ]
    for raw, expected in cases:
        norm = normalize_to_taiwan_mandarin(raw)
        assert expected in norm, f"Expected '{expected}' in '{norm}' (from '{raw}')"


def test_taiwan_science_defense_and_tech_terms():
    """Verify standard Taiwan terminology for science, defense, space and computing."""
    cases = [
        ("航天飞机发射升空", "太空梭發射升空"),
        ("国际空间站宇航员", "國際太空站太空人"),
        ("巡航导弹与隐身战机", "巡弋飛彈與匿蹤戰機"),
        ("核聚变与核裂变反应", "核融合與核分裂反應"),
        ("纳米技术与多普勒效应", "奈米技術與都卜勒效應"),
        ("定义一个数组与函数", "定義一個陣列與函式"),
        ("代码优化与概率统计", "程式碼最佳化與機率統計"),
        ("芯片制程与内存容量", "晶片製程與記憶體容量"),
        ("高清视频与录像", "高畫質影片與錄影"),
    ]
    for raw, expected in cases:
        norm = normalize_to_taiwan_mandarin(raw)
        assert expected in norm, f"Expected '{expected}' in '{norm}' (from '{raw}')"


def test_audit_taiwan_mandarin_flags_forbidden_terms():
    """Verify that audit_taiwan_mandarin flags mainland terms with appropriate suggestions."""
    bad_text = "奥巴马在悉尼观看视频，研究芯片与算法，立马觉得很给力。"
    violations = audit_taiwan_mandarin(bad_text)
    terms_flagged = [v["term"] for v in violations]
    assert "奧巴馬" in terms_flagged
    assert "悉尼" in terms_flagged
    assert "視頻" in terms_flagged
    assert "芯片" in terms_flagged
    assert "算法" in terms_flagged
    assert "立馬" in terms_flagged
    assert "給力" in terms_flagged


def test_double_check_facts_engine(tmp_path):
    """Verify the fact-check double-checking engine without remote LLM."""
    mock_res = {
        "topic": "秦始皇的兵馬俑與戰國軍工標準化",
        "main_question": "秦軍兩千年前是否真正實現了青銅兵器的流水線生產與零件互換？",
        "key_concepts": [
            "秦弩機關鍵零件具有高度互換性",
            "物勒工名制度確保了責任追溯與軍工品質"
        ],
        "interesting_facts": [
            "出土四萬件三稜銅鏃各個稜角公差在毫釐之間"
        ],
        "misconceptions": [
            "誤以為古代所有冷兵器皆為工匠手工個別敲打無法互換"
        ],
        "sources": [
            "https://www2.ihp.sinica.edu.tw/",
            "https://baike.baidu.com/item/sample",
            "https://www.npm.gov.tw/"
        ]
    }

    report = double_check_facts(
        topic="秦始皇的兵馬俑與戰國軍工標準化",
        research_data=mock_res,
        use_llm=False,
    )

    assert isinstance(report, dict)
    assert "validity_score" in report
    assert "overall_status" in report
    assert report["validity_score"] > 0
    assert len(report["claims_audit"]) >= 4

    # Verify PRC source was blocked
    blocked = report["source_integrity"]["prohibited_prc_sources_blocked"]
    assert len(blocked) == 1
    assert "baidu.com" in blocked[0]

    # Verify report formatting
    md = format_fact_check_markdown(report)
    assert "# 🛡️ 事實真偽雙重查核與臺灣用語檢驗報告" in md
    assert "baike.baidu.com" in md

    # Verify file persistence
    json_path, md_path = save_fact_check_reports(tmp_path, report)
    assert json_path.exists()
    assert md_path.exists()
    with open(json_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["validity_score"] == report["validity_score"]


def test_extract_claims_from_research_and_script():
    """Verify extraction of claims from both research and script sections."""
    research_data = {
        "main_question": "為什麼量子纏結能超越光速？",
        "key_concepts": ["量子態疊加與波函數塌縮"],
        "interesting_facts": ["愛因斯坦稱之為幽靈般的超距作用"],
    }
    script_data = {
        "sections": [
            {"name": "Hook", "text": "在微觀宇宙中，兩顆光子即使相隔百萬光年也能瞬間感應。這徹底顛覆了古典物理學的定域性假設。"}
        ]
    }
    claims = extract_claims_from_research_and_script("量子纏結的真相", research_data, script_data)
    assert len(claims) >= 3
    assert any("量子纏結" in c for c in claims)
    assert any("愛因斯坦" in c for c in claims)


def test_fact_check_api_endpoints(monkeypatch):
    """Verify the /api/projects/{project_id}/fact-check GET and POST endpoints."""
    from fastapi.testclient import TestClient
    from api_server import app
    from core.project_manager import Project

    p = Project.create("test_fact_check_api_proj")
    try:
        sample_research = {
            "main_question": "大谷翔平如何顛覆棒球科學？",
            "key_concepts": ["二刀流體能修復與揮棒軌跡演算法"],
            "interesting_facts": ["投球時速突破 160 公里"],
            "sources": ["https://www.sinica.edu.tw/", "https://baike.baidu.com/item/ohtani"]
        }
        p.write_json("research/research.json", sample_research)

        client = TestClient(app)

        # 1. POST fact-check
        post_res = client.post(f"/api/projects/{p.id}/fact-check")
        assert post_res.status_code == 200, f"POST failed: {post_res.text}"
        post_data = post_res.json()
        assert post_data["status"] == "ok"
        report = post_data["report"]
        assert "validity_score" in report
        assert "source_integrity" in report

        # 2. GET fact-check
        get_res = client.get(f"/api/projects/{p.id}/fact-check")
        assert get_res.status_code == 200, f"GET failed: {get_res.text}"
        get_data = get_res.json()
        assert get_data["status"] == "ok"
        assert get_data["report"]["validity_score"] == report["validity_score"]
    finally:
        p.delete()

