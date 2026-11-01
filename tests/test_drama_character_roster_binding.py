import pytest
from core.drama_pipeline import resolve_script_speakers_to_roster, parse_drama_script_markdown

def test_resolve_script_speakers_to_roster():
    # Simulate ai_5 scenario:
    # Script has "房東" and "林晚晚"
    # Roster has "lead_heroine" (林芯怡) and "antagonist_boss" (張豪)
    roster = [
        {
            "id": "lead_heroine",
            "name": "林芯怡",
            "role": "女主角 / 冷靜強勢受害者",
            "gender": "female",
            "voice_profile": "ichiehchieh",
            "appearance": "26-year-old sleek elegant East Asian woman"
        },
        {
            "id": "antagonist_boss",
            "name": "張豪",
            "role": "反派 / 居高臨下的自負對手",
            "gender": "male",
            "voice_profile": "mytsaovoicemagpie",
            "appearance": "45-year-old arrogant middle-aged East Asian man"
        }
    ]

    script_md = """# 房租對決
**[房東]**：這個月的房租，妳拿什麼付？別跟我說沒錢。
**[林晚晚]**：我……我下個月一定補上，求求你再寬限幾天……
**[房東]**：寬限？我已經給過三次了。現在只有一個辦法。
**[林晚晚]**：你……你不能這樣逼我……
**[房東]**：這間屋子是我的，規矩也是我定的。
**[林晚晚]**：……我簽。
**[房東]**：這就對了。
"""
    title, sections = parse_drama_script_markdown(script_md)
    assert len(sections) == 7

    speaker_map = resolve_script_speakers_to_roster(sections, roster)
    assert "房東" in speaker_map
    assert "林晚晚" in speaker_map

    # "房東" must be mapped to 張豪 (antagonist_boss) with mytsaovoicemagpie
    landlord_char = speaker_map["房東"]
    assert landlord_char["id"] == "antagonist_boss"
    assert landlord_char["name"] == "張豪"
    assert landlord_char["voice_profile"] == "mytsaovoicemagpie"

    # "林晚晚" must be mapped to 林芯怡 (lead_heroine) with ichiehchieh
    tenant_char = speaker_map["林晚晚"]
    assert tenant_char["id"] == "lead_heroine"
    assert tenant_char["name"] == "林芯怡"
    assert tenant_char["voice_profile"] == "ichiehchieh"

    # Verify both characters are distinct!
    assert landlord_char["id"] != tenant_char["id"]
