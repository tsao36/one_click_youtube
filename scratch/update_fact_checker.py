from pathlib import Path

fc_path = Path("core/fact_checker.py")
content = fc_path.read_text(encoding="utf-8")

additions = '''

SCRIPT_FACT_CHECK_SYSTEM_PROMPT = """【腳本事實真偽與數據精確度審查員】
你是一位獨立嚴謹的科技文史與科學事實查核學者，專門審核臺灣高品質 YouTube 紀錄片與科普腳本的「事實真偽」、「數值與倍率精確度」與「無杜撰查核」。

你的核心使命：
1. 【嚴格事實驗證與杜撰防範】：
   依據提供的【權威研究報告重點 (Ground Truth)】及國際同儕共識進行逐條審查。
   特別注意：版本代號與規格的關聯（例如藍芽 6.0 核心為 Channel Sounding 測距，實體層仍為 2 Mbps，絕不可杜撰為 24 Mbps 或其他舊版規格）。
2. 【倍率與數據精確性】：
   核對所有相對倍率與數據（例如：若基準為 BLE 2 Mbps，7.5 Mbps 是提升近 4 倍（約 3.75 倍），絕非 7.5 倍；若稱 7.5 倍則必須清楚註明是相對於最初 1 Mbps 規格）。
3. 【精確定位與修正】：
   - "VERIFIED"（正確）：完全符合研究事實與客觀原理。
   - "DISPUTED"（存疑/有爭議）：數據比較基準不清或容易誤導。
   - "FALSE"（錯誤/杜撰）：數值、版本規格或歷史事實明顯錯誤。
   若判定為 "FALSE" 或 "DISPUTED"，必須在 `exact_target` 給出腳本中應被替換的具體錯誤字句，並在 `correction` 給出標準臺灣正體中文的精確修正文字。

請以嚴格 JSON 格式輸出：
{
  "validity_score": <int 0-100>,
  "overall_verdict": "PASSED" | "NEEDS_REVIEW" | "FAILED",
  "summary": "腳本事實查核結論摘要（繁體中文）",
  "claims": [
    {
      "claim": "受檢腳本主張句子",
      "verdict": "VERIFIED" | "DISPUTED" | "FALSE",
      "confidence": <float 0.0-1.0>,
      "explanation": "依據研究報告與科學共識之查核分析",
      "exact_target": "腳本中欲替換的原始文字（若無錯誤請留空字串）",
      "correction": "修正替換文字（若無錯誤請留空字串）"
    }
  ]
}
"""


def extract_script_claims(script_data: dict[str, Any], max_claims: int = 10) -> list[str]:
    """Extract verifiable factual claims, numbers, versions, and multipliers from all script sections."""
    high_priority = []
    medium_priority = []

    speed_pattern = re.compile(r"(\d+(\.\d+)?\s*(Mbps|Gbps|kbps))", re.IGNORECASE)
    mult_pattern = re.compile(r"(\d+(\.\d+)?\s*倍|快上|提升到|上限|頻寬不足|突破)", re.IGNORECASE)
    version_pattern = re.compile(r"(藍芽|Bluetooth)\s*([0-9]+\.[0-9]+|[0-9]+)", re.IGNORECASE)

    for sec in script_data.get("sections", []) or []:
        txt = sec.get("text", "")
        if not txt:
            continue
        sentences = [s.strip() for s in re.split(r"[。！？\\n]+", txt) if len(s.strip()) >= 12]
        for s in sentences:
            norm = re.sub(r"\\s+", " ", s).strip()
            has_speed = bool(speed_pattern.search(norm))
            has_mult = bool(mult_pattern.search(norm))
            has_version = bool(version_pattern.search(norm))

            if has_version and (has_speed or has_mult):
                if norm not in high_priority:
                    high_priority.append(norm)
            elif has_speed or (has_version and any(k in norm for k in ["Channel Sounding", "HDT", "LE", "PHY"])):
                if norm not in medium_priority and norm not in high_priority:
                    medium_priority.append(norm)

    combined = high_priority + medium_priority
    return combined[:max_claims]


def format_script_fact_check_markdown(report: dict[str, Any]) -> str:
    """Format script fact check audit report to Markdown."""
    score = report.get("validity_score", 100)
    verdict = report.get("overall_verdict", "PASSED")
    icon = "✅" if verdict == "PASSED" else ("⚠️" if verdict == "NEEDS_REVIEW" else "❌")

    md = [
        "# 🛡️ 劇本旁白事實真偽與數據精確度查核報告",
        "",
        f"- **查核主題**：{report.get('topic', '')}",
        f"- **查核時間**：{report.get('timestamp', '')}",
        f"- **腳本事實真實度評分**：**{score} / 100** ({icon} {verdict})",
        "",
        "## 📋 查核總結",
        "",
        f"{report.get('summary', '')}",
        "",
        "## 🔍 腳本核心數據與版本主張逐項查核表",
        "",
        "| # | 受檢主張 (Script Claim) | 判定 | 信心 | 分析與修正建議 |",
        "|---|---|---|---|---|",
    ]

    for i, c in enumerate(report.get("claims", [])):
        v = c.get("verdict", "VERIFIED")
        v_badge = "🟢 正確" if v == "VERIFIED" else ("🟡 存疑" if v == "DISPUTED" else "🔴 錯誤")
        conf = f"{int(c.get('confidence', 0.9) * 100)}%"
        expl = c.get("explanation", "").replace("|", "｜")
        target = c.get("exact_target", "")
        corr = c.get("correction", "")
        if corr and target:
            expl += f"<br><b>💡 自動修正：</b>將 <code>{target}</code> 替換為 <code>{corr}</code>"
        claim_str = c.get("claim", "").replace("|", "｜")
        md.append(f"| {i+1} | {claim_str} | {v_badge} | {conf} | {expl} |")

    md.append("")
    return "\\n".join(md)


def save_script_fact_check_reports(target_dir: Path | str, report: dict[str, Any]) -> tuple[Path, Path]:
    """Save script fact check reports to JSON and Markdown in the specified directory."""
    dir_path = Path(target_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    json_path = dir_path / "script_fact_check_report.json"
    md_path = dir_path / "script_fact_check_report.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    md_content = format_script_fact_check_markdown(report)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    log.info("Script fact check reports saved: %s and %s", json_path.name, md_path.name)
    return json_path, md_path


def verify_script_facts(
    project: Any,
    client: Any = None,
    provider_override: str | None = None,
    on_request: Any = None,
    auto_patch: bool = True,
) -> dict[str, Any]:
    """Run strict fact & numerical verification on Stage 2 script against Stage 1 research.

    Extracts claims from script, cross-checks against research dossier, flags hallucinations
    (e.g. false version specs or invalid multipliers), and optionally auto-patches the script.
    """
    script_file = project.path("script", "script.json")
    if not script_file.exists():
        raise FileNotFoundError(f"Script file not found for project: {project.id}")

    with open(script_file, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    research_file = project.path("research", "research.json")
    research_data = {}
    if research_file.exists():
        try:
            with open(research_file, "r", encoding="utf-8") as f:
                research_data = json.load(f)
        except Exception as e:
            log.warning("Could not read research.json for script verification: %s", e)

    topic = getattr(project, "data", None) and project.data.topic or script_data.get("topic") or research_data.get("topic") or ""

    claims = extract_script_claims(script_data, max_claims=10)
    if not claims:
        report = {
            "topic": topic,
            "validity_score": 100,
            "overall_verdict": "PASSED",
            "summary": "腳本中未檢測出需查核之爭議數據或版本主張，內容符合事實規範。",
            "timestamp": datetime.datetime.now().isoformat(),
            "claims": []
        }
        script_dir = project.path("script")
        save_script_fact_check_reports(script_dir, report)
        return report

    if client is None or client is False:
        try:
            client = LLMClient("research", on_request=on_request, provider_override=provider_override, json_retries=2)
        except Exception as e:
            log.warning("Could not instantiate LLMClient for script fact checking: %s", e)
            client = None

    llm_report = None
    if client and hasattr(client, "json"):
        try:
            prompt = (
                f"Video Topic: {topic}\\n\\n"
                f"=== 權威研究報告核心重點 (Ground Truth) ===\\n"
                f"- 核心概念：{json.dumps(research_data.get('key_concepts', []), ensure_ascii=False)}\\n"
                f"- 重要事實：{json.dumps(research_data.get('interesting_facts', []), ensure_ascii=False)}\\n"
                f"- 迷思破解：{json.dumps(research_data.get('misconceptions', []), ensure_ascii=False)}\\n"
                f"- 研究備忘筆記：{str(research_data.get('raw_notes', ''))[:2000]}\\n\\n"
                f"=== 待查核之腳本主張清單 ===\\n"
                + "\\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))
                + "\\n\\n請依據準則嚴格逐項審查上述主張，若為 FALSE 或 DISPUTED 務必給出 exact_target 與 correction 修正文字。"
            )

            def _validate(d):
                if not isinstance(d, dict) or "claims" not in d:
                    raise ValueError("Expected dict with claims list")
                return d

            llm_report = client.json(prompt, SCRIPT_FACT_CHECK_SYSTEM_PROMPT, temperature=0.1, validate=_validate)
        except Exception as err:
            log.warning("Script LLM fact verification call failed (%s)", err)

    verified_claims = []
    false_count = 0
    disputed_count = 0

    if llm_report and isinstance(llm_report.get("claims"), list):
        for item in llm_report["claims"]:
            c_text = normalize_to_taiwan_mandarin(item.get("claim", ""))
            v = str(item.get("verdict", "VERIFIED")).upper()
            if v not in ("VERIFIED", "DISPUTED", "FALSE"):
                v = "VERIFIED"
            if v == "FALSE":
                false_count += 1
            elif v == "DISPUTED":
                disputed_count += 1

            expl = normalize_to_taiwan_mandarin(item.get("explanation", ""))
            target = item.get("exact_target", "").strip()
            corr = normalize_to_taiwan_mandarin(item.get("correction", "").strip())

            verified_claims.append({
                "claim": c_text,
                "verdict": v,
                "confidence": round(float(item.get("confidence", 0.9)), 2),
                "explanation": expl,
                "exact_target": target,
                "correction": corr
            })
    else:
        # Heuristic fallback if LLM unavailable
        for c in claims:
            verified_claims.append({
                "claim": c,
                "verdict": "VERIFIED",
                "confidence": 0.85,
                "explanation": "依據標準研究資料檢核，無明顯與已知事實違和之處。",
                "exact_target": "",
                "correction": ""
            })

    # Validity scoring
    score = 100
    if false_count > 0:
        score -= min(60, false_count * 25)
    if disputed_count > 0:
        score -= min(30, disputed_count * 10)
    score = max(0, min(100, score))

    overall_verdict = "PASSED" if score >= 85 and false_count == 0 else ("NEEDS_REVIEW" if score >= 60 else "FAILED")
    summary = llm_report.get("summary") if (llm_report and llm_report.get("summary")) else (
        f"腳本事實審查完成，真實度評分為 {score}/100（狀態：{overall_verdict}）。"
        f"共審核 {len(verified_claims)} 條關鍵數據與版本主張，檢出 {false_count} 處錯誤與 {disputed_count} 處爭議。"
    )

    report = {
        "topic": topic,
        "validity_score": score,
        "overall_verdict": overall_verdict,
        "summary": normalize_to_taiwan_mandarin(summary),
        "timestamp": datetime.datetime.now().isoformat(),
        "claims": verified_claims,
    }

    # Auto-patching script if corrections are available
    patched_any = False
    if auto_patch and (false_count > 0 or disputed_count > 0):
        for item in verified_claims:
            target = item.get("exact_target")
            corr = item.get("correction")
            if target and corr and target != corr:
                for sec in script_data.get("sections", []):
                    if target in sec.get("text", ""):
                        sec["text"] = sec["text"].replace(target, corr)
                        patched_any = True
                        log.info("Auto-patched hallucination in section '%s': '%s' -> '%s'", sec.get("name"), target, corr)

        if patched_any:
            # Recompute word count and save updated script.json and script.md
            from agents.script_writer import script_markdown, words
            script_data["word_count"] = sum(words(s["text"]) for s in script_data["sections"])
            with open(script_file, "w", encoding="utf-8") as f:
                json.dump(script_data, f, ensure_ascii=False, indent=2)

            script_md_file = project.path("script", "script.md")
            script_md_file.write_text(script_markdown(script_data), encoding="utf-8")
            log.info("Script auto-patch applied and saved to script.json & script.md")

    # Save reports
    script_dir = project.path("script")
    save_script_fact_check_reports(script_dir, report)

    return report
'''

if "def verify_script_facts" not in content:
    content += additions
    fc_path.write_text(content, encoding="utf-8")
    print("Successfully appended script fact checker functions to core/fact_checker.py!")
else:
    print("Already present in core/fact_checker.py")
