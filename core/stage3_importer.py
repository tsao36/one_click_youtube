"""Stage 3 Storyboard & Scenes Script Importer with Coded Line-by-Line Diff.

Enables exporting Stage 3 scenes (.txt review manuscript, .csv spreadsheet,
.md markdown, .json structured, or clean narration text), having external collaborators
or clients review and edit it, and then importing it back into Stage 3.

Uses deterministic coded line-by-line diffing (Python difflib) to auto-detect
all differences without consuming any LLM tokens.
"""

from __future__ import annotations

import csv
import difflib
import io
import json
import re
from datetime import datetime
from typing import Any, Optional


def parse_stage3_script(text: str, filename: str = "") -> list[dict[str, Any]]:
    """Parse an exported or edited Stage 3 script file/text into a list of scene dictionaries.
    
    Supports:
    1. CSV (.csv): Excel UTF-8 BOM or standard comma/tab-delimited review tables
    2. JSON (.json): Structured scene list or dict with "scenes"
    3. TXT Review Manuscript (.txt): Formatted with `[Scene #1] ... 【旁白台詞 (Narration)】:`
    4. TXT Clean Narration (.txt): `[Scene #1] (5.0s) [Speaker] Narration text...`
    5. Markdown (.md): `### 📍 Scene #1 ... - **旁白台詞 (Narration)**: > ...`
    6. Generic numbered text: `Scene 1: ...` or `1. ...`
    """
    if not text or not text.strip():
        return []

    # Normalize line endings
    norm_text = text.replace("\r\n", "\n")
    clean_text = norm_text.strip()
    fn_lower = filename.lower()

    # 1. JSON check
    if fn_lower.endswith(".json") or (clean_text.startswith(("{", "[")) and clean_text.endswith(("}", "]"))):
        try:
            parsed = json.loads(clean_text)
            if isinstance(parsed, dict) and "scenes" in parsed and isinstance(parsed["scenes"], list):
                return _normalize_parsed_scenes(parsed["scenes"])
            elif isinstance(parsed, list):
                return _normalize_parsed_scenes(parsed)
        except Exception:
            pass

    # 2. CSV check
    # Excel files usually have UTF-8 BOM (\ufeff) or filename ends with .csv
    # or header contains "Scene #" / "分鏡編號"
    if fn_lower.endswith(".csv") or "\ufeff" in text[:10] or ("Scene #" in clean_text[:300] and "," in clean_text[:300]) or ("分鏡編號" in clean_text[:300]):
        csv_scenes = _parse_csv_script(clean_text)
        if csv_scenes:
            return _normalize_parsed_scenes(csv_scenes)

    # 3. Markdown (.md) check
    # Check for Markdown scene headers like "### 📍 Scene #" or "### Scene #"
    if re.search(r"###\s*(?:📍\s*)?Scene\s*#?\d+", clean_text, re.IGNORECASE):
        md_scenes = _parse_markdown_script(clean_text)
        if md_scenes:
            return _normalize_parsed_scenes(md_scenes)

    # 4. TXT Review Manuscript check
    # Formatted with `[Scene #1]` and `【旁白台詞`
    if re.search(r"\[Scene\s*#?\d+\]", clean_text, re.IGNORECASE) and "【旁白台詞" in clean_text:
        txt_scenes = _parse_txt_review_script(clean_text)
        if txt_scenes:
            return _normalize_parsed_scenes(txt_scenes)

    # 5. TXT Clean Narration check
    # Formatted with `[Scene #1] ...`
    if re.search(r"\[Scene\s*#?\d+\]", clean_text, re.IGNORECASE):
        narr_scenes = _parse_clean_narration_script(clean_text)
        if narr_scenes:
            return _normalize_parsed_scenes(narr_scenes)

    # 6. Generic Numbered Lines or Paragraphs
    fallback_scenes = _parse_generic_script(clean_text)
    return _normalize_parsed_scenes(fallback_scenes)


def _parse_csv_script(text: str) -> list[dict[str, Any]]:
    """Parse CSV text with UTF-8 BOM or regular comma/semicolon/tab delimiter."""
    clean = text.lstrip("\ufeff").strip()
    # Detect delimiter
    sample = clean[:2048]
    delimiter = ","
    if "\t" in sample and sample.count("\t") > sample.count(","):
        delimiter = "\t"
    elif ";" in sample and sample.count(";") > sample.count(","):
        delimiter = ";"

    reader = csv.reader(io.StringIO(clean), delimiter=delimiter)
    rows = [r for r in reader if r and any(cell.strip() for cell in r)]
    if not rows:
        return []

    header = [c.strip().lower() for c in rows[0]]
    # Map column names to indices
    col_map = {}
    for idx, col in enumerate(header):
        if any(k in col for k in ("分鏡編號", "scene #", "scene_id", "scene")):
            col_map.setdefault("scene_id", idx)
        elif any(k in col for k in ("章節", "section", "chapter")):
            col_map.setdefault("section", idx)
        elif any(k in col for k in ("講者", "角色", "speaker", "character")):
            col_map.setdefault("speaker", idx)
        elif any(k in col for k in ("旁白", "台詞", "narration", "dialogue", "text")):
            col_map.setdefault("narration", idx)
        elif any(k in col for k in ("時長", "duration", "estimated_duration")):
            col_map.setdefault("duration", idx)
        elif any(k in col for k in ("運鏡", "camera", "motion", "camera_motion")):
            col_map.setdefault("camera_motion", idx)
        elif any(k in col for k in ("類型", "visual_type", "type")):
            col_map.setdefault("visual_type", idx)
        elif any(k in col for k in ("畫面", "畫面設定", "畫面規劃", "visual_description", "description")):
            col_map.setdefault("visual_description", idx)
        elif any(k in col for k in ("字卡", "callout", "callout_text")):
            col_map.setdefault("callout_text", idx)
        elif any(k in col for k in ("轉場", "phase", "phase_turn")):
            col_map.setdefault("phase_turn_text", idx)
        elif any(k in col for k in ("審核", "反饋", "修改", "feedback", "review")):
            col_map.setdefault("review_feedback", idx)

    # If narration column wasn't explicitly found, try 4th column (index 3) standard
    if "narration" not in col_map and len(header) >= 4:
        col_map["narration"] = 3

    scenes = []
    for r_idx, row in enumerate(rows[1:], start=1):
        def get_val(key):
            if key in col_map and col_map[key] < len(row):
                return row[col_map[key]].strip()
            return ""

        raw_id = get_val("scene_id")
        id_match = re.search(r"\d+", raw_id) if raw_id else None
        scene_id = int(id_match.group(0)) if id_match else r_idx

        narration = get_val("narration")
        # If narration is empty, this could be an empty row or feedback row
        if not narration and not raw_id:
            continue

        sc: dict[str, Any] = {
            "scene_id": scene_id,
            "section": get_val("section"),
            "speaker": get_val("speaker") or None,
            "narration": narration,
            "camera_motion": get_val("camera_motion") or "slow_zoom_in",
            "visual_type": get_val("visual_type") or "image",
            "visual_description": get_val("visual_description"),
            "callout_text": get_val("callout_text") or None,
            "phase_turn_text": get_val("phase_turn_text") or None,
        }
        dur_str = get_val("duration")
        if dur_str:
            try:
                sc["estimated_duration"] = float(re.sub(r"[^\d.]", "", dur_str))
            except Exception:
                pass
        fb = get_val("review_feedback")
        if fb:
            sc["review_feedback"] = fb
        scenes.append(sc)

    return scenes


def _parse_markdown_script(text: str) -> list[dict[str, Any]]:
    """Parse Markdown Stage 3 script exported by api_server."""
    scenes = []
    # Split by `### 📍 Scene #X` or `### Scene #X`
    pattern = re.compile(r"###\s*(?:📍\s*)?Scene\s*#?(\d+)(?:\s*\(([\d.]+)s\))?", re.IGNORECASE)
    parts = pattern.split(text)

    # parts[0] is preamble/header
    # parts[1] is scene_id, parts[2] is dur, parts[3] is content, parts[4] is scene_id, etc.
    i = 1
    while i < len(parts):
        scene_id = int(parts[i])
        dur_str = parts[i + 1] if (i + 1 < len(parts)) else None
        content = parts[i + 2] if (i + 2 < len(parts)) else ""
        i += 3

        sc: dict[str, Any] = {
            "scene_id": scene_id,
            "narration": "",
            "camera_motion": "slow_zoom_in",
            "visual_description": "",
        }
        if dur_str:
            try:
                sc["estimated_duration"] = float(dur_str)
            except Exception:
                pass

        # Extract fields from markdown
        sec_m = re.search(r"- \*\*章節.*?\*\*:\s*(.*)", content)
        if sec_m:
            sc["section"] = sec_m.group(1).strip()

        spk_m = re.search(r"- \*\*講者.*?/角色.*?\*\*:\s*(?:\*\*)?(.*?)(?:\*\*)?$", content, re.MULTILINE)
        if spk_m:
            spk_val = spk_m.group(1).strip()
            if spk_val:
                sc["speaker"] = spk_val

        cm_m = re.search(r"\*\*運鏡動態\*\*:\s*`([^`]+)`", content)
        if cm_m:
            sc["camera_motion"] = cm_m.group(1).strip()

        vt_m = re.search(r"\*\*畫面類型\*\*:\s*`([^`]+)`", content)
        if vt_m:
            sc["visual_type"] = vt_m.group(1).strip()

        vd_m = re.search(r"- \*\*畫面設定.*?\*\*:\s*(.*)", content)
        if vd_m:
            sc["visual_description"] = vd_m.group(1).strip()

        co_m = re.search(r"- \*\*動態字卡.*?\*\*:\s*`?([^`\n]+)`?", content)
        if co_m:
            sc["callout_text"] = co_m.group(1).strip()

        pt_m = re.search(r"- \*\*黑幕轉場.*?\*\*:\s*`?([^`\n]+)`?", content)
        if pt_m:
            sc["phase_turn_text"] = pt_m.group(1).strip()

        fb_m = re.search(r"- \*\*審核回饋.*?\*\*:\s*(.*)", content)
        if fb_m and fb_m.group(1).strip():
            sc["review_feedback"] = fb_m.group(1).strip()

        # Narration is inside blockquote:
        # - **旁白台詞 (Narration)**:
        #   > line 1
        #   > line 2
        narr_m = re.search(r"-\s*\*\*旁白台詞.*?\*\*:\s*\n((?:\s*>.*(?:\n|$))+)", content)
        if narr_m:
            lines = []
            for line in narr_m.group(1).splitlines():
                stripped = line.strip()
                if stripped.startswith(">"):
                    lines.append(stripped.lstrip(">").strip())
            sc["narration"] = "\n".join(lines).strip()
        else:
            # Fallback blockquote search
            bq_m = re.search(r"(?:^|\n)\s*> (.*?)(?=\n\s*-|\n\n|\Z)", content, re.DOTALL)
            if bq_m:
                lines = [l.strip().lstrip(">").strip() for l in bq_m.group(0).splitlines() if l.strip().startswith(">")]
                sc["narration"] = "\n".join(lines).strip()

        scenes.append(sc)

    return scenes


def _parse_txt_review_script(text: str) -> list[dict[str, Any]]:
    """Parse TXT Stage 3 Review Manuscript exported by api_server."""
    scenes = []
    pattern = re.compile(r"\[Scene\s*#?(\d+)\]", re.IGNORECASE)
    parts = pattern.split(text)

    i = 1
    while i < len(parts):
        scene_id = int(parts[i])
        block = parts[i + 1] if (i + 1 < len(parts)) else ""
        i += 2

        sc: dict[str, Any] = {
            "scene_id": scene_id,
            "narration": "",
            "camera_motion": "slow_zoom_in",
            "visual_description": "",
        }

        # Header line of the scene: [Scene #1] ⏱️ 5.0s | 🎥 運鏡: slow_zoom_in | 講者: John
        first_line = block.splitlines()[0] if block.splitlines() else ""
        dur_m = re.search(r"⏱️\s*([\d.]+)s", first_line)
        if dur_m:
            try:
                sc["estimated_duration"] = float(dur_m.group(1))
            except Exception:
                pass

        cm_m = re.search(r"🎥\s*運鏡:\s*([a-zA-Z0-9_]+)", first_line) or re.search(r"運鏡:\s*([a-zA-Z0-9_]+)", first_line)
        if cm_m:
            sc["camera_motion"] = cm_m.group(1).strip()

        spk_m = re.search(r"講者:\s*([^\n|]+)", first_line)
        if spk_m:
            sc["speaker"] = spk_m.group(1).strip()

        sec_m = re.search(r"所屬章節:\s*([^\n]+)", block)
        if sec_m:
            sc["section"] = sec_m.group(1).strip()

        # Narration:
        # 【旁白台詞 (Narration)】:
        # content...
        # 【畫面規劃...
        narr_m = re.search(r"【旁白台詞.*?\】:\s*\n?(.*?)(?=\n\s*【|\n-{10,}|\Z)", block, re.DOTALL)
        if narr_m:
            sc["narration"] = narr_m.group(1).strip()

        vd_m = re.search(r"【畫面規劃.*?\】:\s*\n?(.*?)(?=\n\s*【|\n-{10,}|\Z)", block, re.DOTALL)
        if vd_m:
            sc["visual_description"] = vd_m.group(1).strip()

        co_m = re.search(r"【動態重點字卡.*?\】:\s*([^\n]+)", block)
        if co_m:
            sc["callout_text"] = co_m.group(1).strip()

        pt_m = re.search(r"【黑幕轉場字卡.*?\】:\s*([^\n]+)", block)
        if pt_m:
            sc["phase_turn_text"] = pt_m.group(1).strip()

        fb_m = re.search(r"【審核意見.*?\】:\s*\n?(.*?)(?=\n-{10,}|\Z)", block, re.DOTALL)
        if fb_m:
            fb_text = fb_m.group(1).replace("_", "").strip()
            if fb_text:
                sc["review_feedback"] = fb_text

        scenes.append(sc)

    return scenes


def _parse_clean_narration_script(text: str) -> list[dict[str, Any]]:
    """Parse pure narration lines:
    [Scene #1] (5.0s) [Speaker] Narration text...
    """
    scenes = []
    # Match lines starting with [Scene #X]
    # May span multiple lines until the next [Scene #Y]
    pattern = re.compile(r"^\[Scene\s*#?(\d+)\]", re.MULTILINE | re.IGNORECASE)
    matches = list(pattern.finditer(text))

    if not matches:
        return []

    for idx, match in enumerate(matches):
        scene_id = int(match.group(1))
        start_idx = match.end()
        end_idx = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start_idx:end_idx].strip()

        # Check for duration (e.g. `(5.0s)`) and speaker (e.g. `[Speaker]`)
        dur = None
        speaker = None

        m_dur = re.match(r"^\s*\(([\d.]+)s?\)", block)
        if m_dur:
            try:
                dur = float(m_dur.group(1))
            except Exception:
                pass
            block = block[m_dur.end():].strip()

        m_spk = re.match(r"^\[([^\]]+)\]", block)
        if m_spk:
            speaker = m_spk.group(1).strip()
            block = block[m_spk.end():].strip()

        sc: dict[str, Any] = {
            "scene_id": scene_id,
            "narration": block,
        }
        if dur is not None:
            sc["estimated_duration"] = dur
        if speaker:
            sc["speaker"] = speaker
        scenes.append(sc)

    return scenes


def _parse_generic_script(text: str) -> list[dict[str, Any]]:
    """Fallback: parse numbered items or non-empty paragraphs into sequential scenes."""
    scenes = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Check for numbered lines like "1. ..." or "Scene 1: ..."
    numbered_re = re.compile(r"^(?:Scene\s*)?#?(\d+)[:.]\s*(.*)", re.IGNORECASE)
    has_numbered = any(numbered_re.match(l) for l in lines)

    if has_numbered:
        for idx, line in enumerate(lines, start=1):
            m = numbered_re.match(line)
            if m:
                s_id = int(m.group(1))
                narr = m.group(2).strip()
            else:
                s_id = idx
                narr = line
            scenes.append({
                "scene_id": s_id,
                "narration": narr,
                "camera_motion": "slow_zoom_in"
            })
    else:
        # Split by blank lines / paragraphs
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        for idx, para in enumerate(paras or lines, start=1):
            scenes.append({
                "scene_id": idx,
                "narration": para,
                "camera_motion": "slow_zoom_in"
            })

    return scenes


def _normalize_parsed_scenes(raw_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure consistent typing and required fields on parsed scenes."""
    normalized = []
    for idx, item in enumerate(raw_list, start=1):
        if not isinstance(item, dict):
            continue
        try:
            s_id = int(item.get("scene_id") or idx)
        except Exception:
            s_id = idx

        narr = str(item.get("narration") or "").strip()

        sc: dict[str, Any] = {
            "scene_id": s_id,
            "narration": narr,
        }
        if "camera_motion" in item and item["camera_motion"]:
            cam = str(item["camera_motion"]).strip()
            if cam in ("slow_zoom_in", "slow_zoom_out", "pan_left", "pan_right", "static"):
                sc["camera_motion"] = cam
        if "visual_type" in item and item["visual_type"]:
            sc["visual_type"] = str(item["visual_type"]).strip()
        if "visual_description" in item and item["visual_description"]:
            sc["visual_description"] = str(item["visual_description"]).strip()
        if "section" in item and item["section"]:
            sc["section"] = str(item["section"]).strip()
        if "speaker" in item and item["speaker"]:
            sc["speaker"] = str(item["speaker"]).strip()
        if "callout_text" in item and item["callout_text"]:
            sc["callout_text"] = str(item["callout_text"]).strip()
        if "phase_turn_text" in item and item["phase_turn_text"]:
            sc["phase_turn_text"] = str(item["phase_turn_text"]).strip()
        if "estimated_duration" in item and item["estimated_duration"]:
            try:
                sc["estimated_duration"] = float(item["estimated_duration"])
            except Exception:
                pass
        if "review_feedback" in item and item["review_feedback"]:
            sc["review_feedback"] = str(item["review_feedback"]).strip()

        normalized.append(sc)

    return normalized


def diff_scene_text_lines(old_text: str, new_text: str) -> list[dict[str, Any]]:
    """Perform deterministic line-by-line diff using Python's difflib.
    
    Zero tokens consumed. Returns structured line changes:
    - op: "-" (removed / original)
    - op: "+" (added / updated)
    - op: " " (identical / unchanged)
    - op: "m" (modified line with old_text and new_text)
    """
    old_lines = (old_text or "").splitlines()
    new_lines = (new_text or "").splitlines()

    # If both are single line, split into clauses/sentences for fine-grained line diff if long
    if len(old_lines) <= 1 and len(new_lines) <= 1:
        old_val = (old_lines[0] if old_lines else "").strip()
        new_val = (new_lines[0] if new_lines else "").strip()
        if old_val == new_val:
            return [{"op": " ", "text": old_val}]
        else:
            return [
                {"op": "-", "text": old_val},
                {"op": "+", "text": new_val}
            ]

    # Multi-line diff using difflib.ndiff
    diff_gen = list(difflib.ndiff(old_lines, new_lines))
    line_diffs: list[dict[str, Any]] = []

    idx = 0
    while idx < len(diff_gen):
        d = diff_gen[idx]
        code = d[:2]
        val = d[2:]

        if code == "  ":
            line_diffs.append({"op": " ", "text": val})
            idx += 1
        elif code == "- ":
            # Check if next line is "+ " (replacement)
            if idx + 1 < len(diff_gen) and diff_gen[idx + 1].startswith("+ "):
                new_val = diff_gen[idx + 1][2:]
                line_diffs.append({"op": "-", "text": val})
                line_diffs.append({"op": "+", "text": new_val})
                idx += 2
                # Skip any '? ' guide line
                if idx < len(diff_gen) and diff_gen[idx].startswith("? "):
                    idx += 1
            else:
                line_diffs.append({"op": "-", "text": val})
                idx += 1
                if idx < len(diff_gen) and diff_gen[idx].startswith("? "):
                    idx += 1
        elif code == "+ ":
            line_diffs.append({"op": "+", "text": val})
            idx += 1
            if idx < len(diff_gen) and diff_gen[idx].startswith("? "):
                idx += 1
        elif code == "? ":
            idx += 1
        else:
            line_diffs.append({"op": " ", "text": val})
            idx += 1

    return line_diffs


def compare_stage3_scenes(
    current_scenes: list[dict[str, Any]],
    imported_scenes: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compare existing Stage 3 scenes with newly imported scenes.
    
    Uses pure coded line-by-line algorithm (Python difflib).
    Returns comprehensive diff statistics, per-scene line diffs,
    and field change markers.
    """
    cur_map = {s["scene_id"]: s for s in current_scenes if "scene_id" in s}
    imp_map = {s["scene_id"]: s for s in imported_scenes if "scene_id" in s}

    # All unique scene_ids preserving order
    all_scene_ids = []
    seen = set()
    for s in current_scenes:
        sid = s.get("scene_id")
        if sid not in seen:
            all_scene_ids.append(sid)
            seen.add(sid)
    for s in imported_scenes:
        sid = s.get("scene_id")
        if sid not in seen:
            all_scene_ids.append(sid)
            seen.add(sid)

    diffs: list[dict[str, Any]] = []
    modified_count = 0
    unchanged_count = 0
    added_count = 0
    removed_count = 0
    changed_scene_ids: list[int] = []

    for sid in all_scene_ids:
        cur_sc = cur_map.get(sid)
        imp_sc = imp_map.get(sid)

        # 1. Added scene (in imported, not in current)
        if cur_sc is None and imp_sc is not None:
            added_count += 1
            changed_scene_ids.append(sid)
            narr = imp_sc.get("narration", "")
            diffs.append({
                "scene_id": sid,
                "status": "added",
                "has_changes": True,
                "narration_changed": True,
                "old_narration": "",
                "new_narration": narr,
                "line_diff": [{"op": "+", "text": line} for line in (narr.splitlines() or [""])],
                "field_changes": [{"field": "scene", "old": None, "new": f"Scene #{sid}"}],
                "imported_scene": imp_sc,
            })
            continue

        # 2. Removed scene (in current, not in imported)
        if cur_sc is not None and imp_sc is None:
            removed_count += 1
            changed_scene_ids.append(sid)
            narr = cur_sc.get("narration", "")
            diffs.append({
                "scene_id": sid,
                "status": "removed",
                "has_changes": True,
                "narration_changed": True,
                "old_narration": narr,
                "new_narration": "",
                "line_diff": [{"op": "-", "text": line} for line in (narr.splitlines() or [""])],
                "field_changes": [{"field": "scene", "old": f"Scene #{sid}", "new": None}],
                "current_scene": cur_sc,
            })
            continue

        # 3. Both exist: perform field & line-level diff
        old_narr = (cur_sc.get("narration") or "").strip()
        new_narr = (imp_sc.get("narration") or "").strip()
        narr_changed = (old_narr != new_narr)

        field_changes: list[dict[str, Any]] = []
        if narr_changed:
            field_changes.append({
                "field": "narration",
                "label": "旁白台詞 (Narration)",
                "old": old_narr,
                "new": new_narr
            })

        # Check other relevant fields
        for field, label in [
            ("camera_motion", "運鏡動態 (Camera Motion)"),
            ("visual_description", "畫面設定 (Visual Description)"),
            ("speaker", "講者/角色 (Speaker)"),
            ("callout_text", "動態字卡 (Callout Text)"),
            ("phase_turn_text", "黑幕轉場 (Phase Turn)"),
            ("section", "章節 (Section)"),
        ]:
            if field in imp_sc and imp_sc[field]:
                old_val = (cur_sc.get(field) or "").strip()
                new_val = (imp_sc.get(field) or "").strip()
                if old_val != new_val:
                    field_changes.append({
                        "field": field,
                        "label": label,
                        "old": old_val,
                        "new": new_val
                    })

        has_changes = len(field_changes) > 0
        if has_changes:
            modified_count += 1
            changed_scene_ids.append(sid)
            status = "modified"
        else:
            unchanged_count += 1
            status = "unchanged"

        line_diff = diff_scene_text_lines(old_narr, new_narr) if narr_changed else [
            {"op": " ", "text": line} for line in (old_narr.splitlines() or [""])
        ]

        diff_item: dict[str, Any] = {
            "scene_id": sid,
            "status": status,
            "has_changes": has_changes,
            "narration_changed": narr_changed,
            "old_narration": old_narr,
            "new_narration": new_narr,
            "line_diff": line_diff,
            "field_changes": field_changes,
            "imported_scene": imp_sc,
        }
        if imp_sc.get("review_feedback"):
            diff_item["review_feedback"] = imp_sc["review_feedback"]

        diffs.append(diff_item)

    return {
        "summary": {
            "total_current": len(current_scenes),
            "total_imported": len(imported_scenes),
            "modified_count": modified_count,
            "unchanged_count": unchanged_count,
            "added_count": added_count,
            "removed_count": removed_count,
            "changed_scene_ids": changed_scene_ids,
            "algorithm": "Python difflib / Coded Line Diff (0 LLM Tokens)",
        },
        "diffs": diffs
    }


def apply_stage3_import(
    project: Any,
    imported_scenes: list[dict[str, Any]],
    diff_result: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """Apply imported scenes to a Project, marking diffs and invalidating affected downstream stages.
    
    1. Updates scene attributes (narration, camera_motion, visual_description, etc.)
    2. Attaches diff markers to `sc.meta['import_diff']` so UI marks differences clearly
    3. If narration changed, marks audio take outdated and invalidates downstream stages
    4. Saves the updated scenes to disk
    """
    from core.models import Scene, Status

    cur_scenes = project.scenes
    cur_dict = [s.model_dump(mode="json") for s in cur_scenes]

    if diff_result is None:
        diff_result = compare_stage3_scenes(cur_dict, imported_scenes)

    diff_map = {d["scene_id"]: d for d in diff_result.get("diffs", [])}
    cur_map = {s.scene_id: s for s in cur_scenes}

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    modified_scene_ids: list[int] = []
    updated_scene_objs: list[Scene] = []
    avatar_narr_changed = False

    for raw_imp in imported_scenes:
        sid = raw_imp.get("scene_id")
        existing_sc = cur_map.get(sid)
        diff_info = diff_map.get(sid, {})
        is_modified = diff_info.get("has_changes", False) or diff_info.get("status") == "modified"

        if existing_sc:
            # Clone or update existing scene
            sc_data = existing_sc.model_dump(mode="json")
            old_narration = existing_sc.narration.strip()
            new_narration = (raw_imp.get("narration") or "").strip()

            # Update fields
            sc_data["narration"] = new_narration
            if raw_imp.get("camera_motion"):
                sc_data["camera_motion"] = raw_imp["camera_motion"]
            if raw_imp.get("visual_description"):
                sc_data["visual_description"] = raw_imp["visual_description"]
            if raw_imp.get("visual_type"):
                sc_data["visual_type"] = raw_imp["visual_type"]
            if raw_imp.get("speaker") is not None:
                sc_data["speaker"] = raw_imp["speaker"]
            if raw_imp.get("section"):
                sc_data["section"] = raw_imp["section"]
            if raw_imp.get("callout_text") is not None:
                sc_data["callout_text"] = raw_imp["callout_text"]
            if raw_imp.get("phase_turn_text") is not None:
                sc_data["phase_turn_text"] = raw_imp["phase_turn_text"]
            if raw_imp.get("estimated_duration"):
                sc_data["estimated_duration"] = raw_imp["estimated_duration"]

            sc = Scene(**sc_data)

            if is_modified:
                modified_scene_ids.append(sid)
                # Store diff marker on scene metadata
                if sc.meta is None:
                    sc.meta = {}
                sc.meta["import_diff"] = {
                    "modified": True,
                    "imported_at": now_str,
                    "old_narration": old_narration,
                    "new_narration": new_narration,
                    "line_diff": diff_info.get("line_diff", []),
                    "field_changes": diff_info.get("field_changes", []),
                    "review_feedback": diff_info.get("review_feedback"),
                }

                if old_narration != new_narration:
                    # Invalidate old audio and mark for TTS regeneration
                    sc.audio.status = Status.PENDING
                    sc.audio.error = None
                    if sc.audio.meta is None:
                        sc.audio.meta = {}
                    sc.audio.meta["text_outdated"] = True
                    sc.audio.meta["previous_narration"] = old_narration

                    # If this is an avatar presenter scene, invalidate presenter animation so it re-syncs
                    if getattr(sc, "is_presenter", False) or sc.visual_type in ("talking_head", "talking_actor"):
                        sc.animation.status = Status.PENDING
                        if sc.animation.meta is None:
                            sc.animation.meta = {}
                        sc.animation.meta["audio_outdated"] = True
                        try:
                            project.path("animation", f"{sc.tag}.mp4").unlink(missing_ok=True)
                        except Exception:
                            pass
                        avatar_narr_changed = True
            else:
                # If unchanged, retain or clear existing diff marker
                if sc.meta and "import_diff" in sc.meta:
                    sc.meta.pop("import_diff", None)

            updated_scene_objs.append(sc)
        else:
            # Newly added scene
            modified_scene_ids.append(sid)
            sc = Scene(**raw_imp)
            if sc.meta is None:
                sc.meta = {}
            sc.meta["import_diff"] = {
                "modified": True,
                "status": "added",
                "imported_at": now_str,
                "line_diff": diff_info.get("line_diff", []),
                "field_changes": diff_info.get("field_changes", []),
            }
            updated_scene_objs.append(sc)

    # Invalidate downstream stages if changes occurred
    if modified_scene_ids:
        project.set_scenes(updated_scene_objs)
        project.invalidate("prompts")
        # Check if any narration changed
        narr_changed = any(d.get("narration_changed") for d in diff_result.get("diffs", []))
        if narr_changed:
            project.invalidate("voice")
            project.invalidate("subtitles")
            project.invalidate("render")
            project.set_stage("voice", Status.PENDING)
            project.set_stage("subtitles", Status.PENDING)
            project.set_stage("render", Status.PENDING)
            if avatar_narr_changed:
                project.invalidate("presenter")
                project.invalidate("animation")
                project.set_stage("presenter", Status.PENDING)
                project.set_stage("animation", Status.PENDING)
        project.save()

    return {
        "status": "ok",
        "modified_count": len(modified_scene_ids),
        "modified_scene_ids": modified_scene_ids,
        "total_scenes": len(updated_scene_objs),
        "diff_summary": diff_result.get("summary", {}),
    }


def clear_stage3_diff_markers(project: Any) -> int:
    """Clear all import_diff metadata markers from project scenes."""
    cleared = 0
    scenes = project.scenes
    for sc in scenes:
        if sc.meta and "import_diff" in sc.meta:
            sc.meta.pop("import_diff", None)
            cleared += 1
    if cleared > 0:
        project.save_scenes()
        project.save()
    return cleared

