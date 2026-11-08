import json
import re
from core.taiwan_mandarin import normalize_to_taiwan_mandarin
from providers.llm import LLMClient

research_file = "projects/bluetooth_7_0_high_data_2/research/research.json"
script_file = "projects/bluetooth_7_0_high_data_2/script/script.json"

with open(research_file, "r", encoding="utf-8") as f:
    res = json.load(f)

with open(script_file, "r", encoding="utf-8") as f:
    scr = json.load(f)

client = LLMClient("research")

SCRIPT_FACT_CHECK_PROMPT = """【腳本事實真偽與數據精確度雙重審查員】
你是一位嚴謹的科技文史與科學事實查核專家，專門審查 YouTube 科技解說與紀錄片腳本的「事實真實性」、「數據一致性」與「無杜撰查核」。

你手中有【權威研究調查報告 (Research Dossier)】作為真理依據：
=== 研究報告重點 (Ground Truth) ===
- 主題：{topic}
- 核心概念：{key_concepts}
- 重要事實：{interesting_facts}
- 迷思破解：{misconceptions}
- 研究筆記摘要：{raw_notes_summary}

請逐一審查下列從影片腳本中提取的具體主張 (Claims)：
審查準則：
1. 【數據與版本真偽】：核對各代規格是否被杜撰（例如：藍芽 6.0 核心功能為 Channel Sounding 測距，實體層仍為 2 Mbps，絕非 24 Mbps；24 Mbps 乃古早藍芽 3.0+HS）。
2. 【倍率計算精確性】：若聲稱「快上 X 倍」，必須精確吻合前後文的基準數值（若基準為 BLE 2 Mbps，7.5 Mbps 應為提升近 4 倍或 3.75 倍；若稱 7.5 倍則必須清楚註明是相對於最初 1 Mbps 規格）。
3. 【嚴格修正建議】：若判定為 "FALSE" 或 "DISPUTED"，必須在 `exact_target` 給出腳本中應被替換的具體文字，並在 `correction` 給出符合臺灣正體中文的精確修正文字。

輸出 JSON 格式：
{{
  "claims": [
    {{
      "claim": "受檢主張文字",
      "verdict": "VERIFIED" | "DISPUTED" | "FALSE",
      "explanation": "查核分析原因",
      "exact_target": "腳本中欲替換的原始文字（若無錯誤可為空）",
      "correction": "修正替換文字（若無錯誤可為空）"
    }}
  ]
}}
"""

candidate_claims = [
    "藍芽 7.0 HDT 這次直接把速度拉到 7.5 Mbps，比過去快上 7.5 倍，無損音訊、穿戴裝置都要被顛覆了！",
    "從藍芽 5.0 開始，低功耗藍芽（BLE）就奠定了 2 Mbps 的實體層上限，這條速度牆卡了近十年，讓無損音訊和大量資料傳輸變得困難。",
    "到了藍芽 6.0，雖然傳輸速度提升到 24 Mbps，但還是無法真正解決頻寬不足的問題。",
    "直到藍芽 7.0 帶來 HDT 技術，才正式突破這道瓶頸。"
]

prompt = SCRIPT_FACT_CHECK_PROMPT.format(
    topic=scr.get("topic"),
    key_concepts=res.get("key_concepts"),
    interesting_facts=res.get("interesting_facts"),
    misconceptions=res.get("misconceptions"),
    raw_notes_summary=res.get("raw_notes", "")[:1500]
) + "\n\n待審查腳本主張清單：\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(candidate_claims))

result = client.json(prompt, "You are a precise technical fact-checker.", temperature=0.1)
print(json.dumps(result, ensure_ascii=False, indent=2))
