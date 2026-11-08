import json
import re
from pathlib import Path
from core.taiwan_mandarin import normalize_to_taiwan_mandarin
from core.logging_setup import log
from providers.llm import LLMClient
from agents.script_writer import script_markdown

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

def extract_script_claims(script_data: dict) -> list[str]:
    claims = []
    if not script_data or not isinstance(script_data, dict):
        return []

    num_version_pattern = re.compile(
        r"(\d+(\.\d+)?\s*(Mbps|Gbps|kbps|GHz|MHz|Hz|kHz|bit|%|倍|年|代|公尺|公里|ms|秒|分鐘|小時))|"
        r"([0-9]+\.[0-9]+)|"
        r"(藍芽|Bluetooth|WiFi|Wi-Fi|晶片|演算法|協定|實體層|PHY|SIG)\s*(\d+(\.\d+)?)",
        re.IGNORECASE
    )

    for sec in script_data.get("sections", []) or []:
        txt = sec.get("text", "")
        if not txt:
            continue
        sentences = [s.strip() for s in re.split(r"[。！？\n]+", txt) if len(s.strip()) >= 12]
        for s in sentences:
            if num_version_pattern.search(s) or any(k in s for k in ["快上", "突破", "上限", "倍", "雖然", "提升到", "瓶頸"]):
                norm = re.sub(r"\s+", " ", s).strip()
                if norm not in claims:
                    claims.append(norm)

    return claims[:25]

# Test on bluetooth_7_0_high_data_2
p_dir = Path("projects/bluetooth_7_0_high_data_2")
with open(p_dir / "research/research.json", "r", encoding="utf-8") as f:
    res = json.load(f)

with open(p_dir / "script/script.json", "r", encoding="utf-8") as f:
    scr = json.load(f)

claims = extract_script_claims(scr)
print(f"Extracted {len(claims)} script claims.")
for i, c in enumerate(claims):
    print(f"{i+1}: {c}")

client = LLMClient("research")
prompt = (
    f"Video Topic: {scr.get('topic')}\n\n"
    f"=== 研究報告核心重點 (Ground Truth) ===\n"
    f"- 核心概念：{json.dumps(res.get('key_concepts', []), ensure_ascii=False)}\n"
    f"- 重要事實：{json.dumps(res.get('interesting_facts', []), ensure_ascii=False)}\n"
    f"- 迷思破解：{json.dumps(res.get('misconceptions', []), ensure_ascii=False)}\n"
    f"- 研究備忘筆記：{str(res.get('raw_notes', ''))[:2000]}\n\n"
    f"=== 待查核之腳本主張清單 ===\n"
    + "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))
    + "\n\n請逐項審查上述主張，並輸出嚴格 JSON。"
)

def _validate(d):
    if not isinstance(d, dict) or "claims" not in d:
        raise ValueError("Missing claims")
    return d

report = client.json(prompt, SCRIPT_FACT_CHECK_SYSTEM_PROMPT, temperature=0.1, validate=_validate)
print("\n--- Fact Check Report Summary ---")
print("Score:", report.get("validity_score"))
print("Verdict:", report.get("overall_verdict"))
print("Summary:", report.get("summary"))

print("\n--- Claims Results ---")
for c in report.get("claims", []):
    v = c.get("verdict")
    print(f"[{v}] {c.get('claim')}")
    if v in ("FALSE", "DISPUTED"):
        print(f"   Target: '{c.get('exact_target')}' -> Correction: '{c.get('correction')}'")
        print(f"   Reason: {c.get('explanation')}")
