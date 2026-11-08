import json
import re

script_file = "projects/bluetooth_7_0_high_data_2/script/script.json"
with open(script_file, "r", encoding="utf-8") as f:
    scr = json.load(f)

def extract_script_claims(script_data: dict, max_claims: int = 10) -> list[str]:
    high_priority = []
    medium_priority = []
    
    speed_pattern = re.compile(r"(\d+(\.\d+)?\s*(Mbps|Gbps|kbps))", re.IGNORECASE)
    mult_pattern = re.compile(r"(\d+(\.\d+)?\s*倍|快上|提升到|上限|頻寬不足|突破)", re.IGNORECASE)
    version_pattern = re.compile(r"(藍芽|Bluetooth)\s*([0-9]+\.[0-9]+|[0-9]+)", re.IGNORECASE)

    for sec in script_data.get("sections", []) or []:
        txt = sec.get("text", "")
        if not txt:
            continue
        sentences = [s.strip() for s in re.split(r"[。！？\n]+", txt) if len(s.strip()) >= 12]
        for s in sentences:
            norm = re.sub(r"\s+", " ", s).strip()
            # High priority: combines version + speed/multiplier
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

claims = extract_script_claims(scr, max_claims=8)
print(f"Extracted {len(claims)} focused claims:")
for i, c in enumerate(claims):
    print(f"{i+1}: {c}")
