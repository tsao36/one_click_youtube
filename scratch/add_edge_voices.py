import sys
import json
from pathlib import Path

ROOT = Path(r"c:\AI Project\Youtube_video")
sys.path.insert(0, str(ROOT))

from generators.voice_generator import synthesize
from core.config import load_settings

def update_file(path: Path, fn):
    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    norm = raw.replace("\r\n", "\n")
    updated = fn(norm)
    assert updated != norm, f"No changes applied to {path}"
    out = updated.replace("\n", "\r\n") if crlf else updated
    path.write_bytes(out.encode("utf-8"))

# 1. Update providers/tts/__init__.py to support pitch in EdgeTTS
def patch_tts(s: str) -> str:
    old = """        pct = round((float(profile.get("speech_rate", 1.0)) - 1.0) * 100)
        rate = f"{'+' if pct >= 0 else ''}{pct}%"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        async def run():
            last_err = None
            for attempt in range(3):
                try:
                    await edge_tts.Communicate(text, voice, rate=rate).save(str(output_file))"""
    new = """        pct = round((float(profile.get("speech_rate", 1.0)) - 1.0) * 100)
        rate = f"{'+' if pct >= 0 else ''}{pct}%"
        raw_pitch = profile.get("pitch")
        if isinstance(raw_pitch, str) and raw_pitch.strip().endswith("Hz"):
            pitch = raw_pitch.strip()
            if not pitch.startswith(("+", "-")):
                pitch = f"+{pitch}"
        else:
            hz = int(round(float(profile.get("pitch_shift", 0) or 0)))
            pitch = f"{'+' if hz >= 0 else ''}{hz}Hz"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        async def run():
            last_err = None
            for attempt in range(3):
                try:
                    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(output_file))"""
    if new in s:
        return s
    assert old in s, "Could not find EdgeTTS target block"
    return s.replace(old, new, 1)

raw_tts = (ROOT / "providers" / "tts" / "__init__.py").read_bytes().decode("utf-8")
if "pitch=pitch" not in raw_tts:
    update_file(ROOT / "providers" / "tts" / "__init__.py", patch_tts)

# 2. Update api_server.py to persist edge fields in create_voice
def patch_api(s: str) -> str:
    old = """    if provider == "voai":
        data["speaker"] = voice_id or voice or "佑希"
        data["version"] = model_id or "Sota+"
        data["voai_style"] = voai_style or "預設"
        data["pitch_shift"] = pitch_shift
        data["breath_pause"] = breath_pause"""
    new = """    if provider == "voai":
        data["speaker"] = voice_id or voice or "佑希"
        data["version"] = model_id or "Sota+"
        data["voai_style"] = voai_style or "預設"
        data["pitch_shift"] = pitch_shift
        data["breath_pause"] = breath_pause
    if provider == "edge":
        chosen_edge_voice = voice or voice_id or "zh-TW-HsiaoChenNeural"
        data["voice"] = chosen_edge_voice
        data["voice_id"] = chosen_edge_voice
        data["model_id"] = chosen_edge_voice
        hz = int(round(float(pitch_shift or 0)))
        data["pitch_shift"] = hz
        data["pitch"] = f"{'+' if hz >= 0 else ''}{hz}Hz"
        data["gender"] = "male" if "YunJhe" in chosen_edge_voice or "WanLung" in chosen_edge_voice or "Yun" in chosen_edge_voice else "female" """
    if "chosen_edge_voice" in s:
        return s
    assert old in s, "Could not find voai block in api_server.py"
    return s.replace(old, new, 1)

raw_api = (ROOT / "api_server.py").read_bytes().decode("utf-8")
if "chosen_edge_voice" not in raw_api:
    update_file(ROOT / "api_server.py", patch_api)

# 3. Update ui/index.html to display Edge-TTS badge/details and Add New Voice Edge-TTS config panel
def patch_ui(s: str) -> str:
    target_html = """      <div id="v-ref-hint" style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">"""
    edge_box_html = """      <!-- EDGE-TTS (臺灣國語女聲/男聲) SPECIFIC SETTINGS -->
      <div id="v-edge-container" style="display:none; background:#071521; border:1px solid #10b981; border-radius:8px; padding:16px; margin:16px 0;">
        <div style="font-weight:700; color:#34d399; font-size:13px; margin-bottom:12px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span>🇹🇼 Microsoft Edge-TTS 臺灣國語男聲 / 女聲配置 (免金鑰 · 免費高擬真神經語音)</span>
            <span style="font-size: 11px; padding:2px 8px; border-radius:4px; font-weight:600; background:rgba(16,185,129,0.2); border:1px solid #10b981; color:#6ee7b7;">✓ Ready (Free Cloud)</span>
          </div>
        </div>
        <div class="form-grid">
          <div class="form-group">
            <label>臺灣國語聲線 (Taiwan Mandarin Neural Voice)</label>
            <select id="v-edge-voice">
              <option value="zh-TW-HsiaoChenNeural" selected>👧 曉臻 (zh-TW-HsiaoChenNeural — 臺灣溫柔知性女聲)</option>
              <option value="zh-TW-HsiaoYuNeural">👧 曉雨 (zh-TW-HsiaoYuNeural — 臺灣甜美清亮女孩)</option>
              <option value="zh-TW-YunJheNeural">👦 雲哲 (zh-TW-YunJheNeural — 臺灣沉穩陽光男聲)</option>
            </select>
          </div>
          <div class="form-group">
            <label>語速 (Speech Rate): <span id="v-edge-speed-val">1.02</span>x</label>
            <input type="range" id="v-edge-speed" min="0.75" max="1.30" step="0.01" value="1.02" oninput="document.getElementById('v-edge-speed-val').textContent = parseFloat(this.value).toFixed(2)">
            <div style="font-size: 12px; color:var(--text-muted); margin-top:3px;">範圍 0.75x ~ 1.30x (推薦 0.96x ~ 1.08x)。</div>
          </div>
          <div class="form-group">
            <label>音調微調 (Pitch Shift): <span id="v-edge-pitch-val">+0</span> Hz</label>
            <input type="range" id="v-edge-pitch" min="-10" max="10" step="1" value="0" oninput="document.getElementById('v-edge-pitch-val').textContent = (parseInt(this.value)>=0?'+':'')+this.value">
            <div style="font-size: 12px; color:var(--text-muted); margin-top:3px;">調高 (+2~+6Hz) 更青春活潑；調低 (-2~-6Hz) 更成熟沉穩。</div>
          </div>
        </div>
      </div>

""" + target_html
    assert target_html in s, "Could not find v-ref-hint in ui/index.html"
    s = s.replace(target_html, edge_box_html, 1)

    old_row = """        const isEleven = v.provider === 'elevenlabs';
        const isVoai = v.provider === 'voai';"""
    new_row = """        const isEleven = v.provider === 'elevenlabs';
        const isVoai = v.provider === 'voai';
        const isEdge = v.provider === 'edge';"""
    assert old_row in s, "Could not find isVoai in loadVoiceProfiles"
    s = s.replace(old_row, new_row, 1)

    old_badge = """                  ${isVoai ? '<span style="background:rgba(2,132,199,0.25); border:1px solid #0284c7; color:#38bdf8; font-size: 12px; font-weight:700; padding:1px 6px; border-radius:4px;">🇹🇼 VoAI 絕好聲創</span>' : ''}"""
    new_badge = old_badge + """\n                  ${isEdge ? `<span style="background:rgba(16,185,129,0.22); border:1px solid #10b981; color:#6ee7b7; font-size: 12px; font-weight:700; padding:1px 6px; border-radius:4px;">🇹🇼 Edge-TTS ${v.gender === 'male' ? '臺灣男聲' : '臺灣女聲'}</span>` : ''}"""
    assert old_badge in s, "Could not find VoAI badge in loadVoiceProfiles"
    s = s.replace(old_badge, new_badge, 1)

    old_meta = """                  ` : `
                    Provider: <b>${v.provider.toUpperCase()}</b> | Language: <b>${v.language || 'Auto'}</b> | Cloned Ref: <b>${v.reference_wav ? 'Uploaded ✓' : 'None'}</b>
                  `)}"""
    new_meta = """                  ` : (isEdge ? `
                    Provider: <b style="color:#34d399;">Edge-TTS (Free Cloud)</b> | Neural Voice: <b style="color:#a7f3d0;">${v.voice || 'zh-TW-HsiaoChenNeural'}</b> | Rate: <b>${v.speech_rate || 1.0}x</b> | Pitch: <b>${v.pitch || '+0Hz'}</b>${v.persona ? ` | <span style="color:#cbd5e1;">${v.persona}</span>` : ''}
                  ` : `
                    Provider: <b>${v.provider.toUpperCase()}</b> | Language: <b>${v.language || 'Auto'}</b> | Cloned Ref: <b>${v.reference_wav ? 'Uploaded ✓' : 'None'}</b>
                  `))}"""
    assert old_meta in s, "Could not find provider meta in loadVoiceProfiles"
    s = s.replace(old_meta, new_meta, 1)

    old_prov_change = """      const voaiBox = document.getElementById('v-voai-container');
      const refBox = document.getElementById('v-ref-audio-group');
      const hintBox = document.getElementById('v-ref-hint');"""
    new_prov_change = """      const voaiBox = document.getElementById('v-voai-container');
      const edgeBox = document.getElementById('v-edge-container');
      const refBox = document.getElementById('v-ref-audio-group');
      const hintBox = document.getElementById('v-ref-hint');
      if (edgeBox) edgeBox.style.display = (prov === 'edge') ? 'block' : 'none';"""
    assert old_prov_change in s, "Could not find voaiBox in handleVoiceProviderChange"
    s = s.replace(old_prov_change, new_prov_change, 1)

    old_else_branch = """      } else {
        if (bmBox) bmBox.style.display = 'none';
        if (elevenBox) elevenBox.style.display = 'none';
        if (voaiBox) voaiBox.style.display = 'none';
        if (refBox) refBox.style.display = 'block';
        if (hintBox) hintBox.style.display = 'block';
      }"""
    new_else_branch = """      } else if (prov === 'edge') {
        if (bmBox) bmBox.style.display = 'none';
        if (elevenBox) elevenBox.style.display = 'none';
        if (voaiBox) voaiBox.style.display = 'none';
        if (refBox) refBox.style.display = 'none';
        if (hintBox) hintBox.style.display = 'none';
      } else {
        if (bmBox) bmBox.style.display = 'none';
        if (elevenBox) elevenBox.style.display = 'none';
        if (voaiBox) voaiBox.style.display = 'none';
        if (refBox) refBox.style.display = 'block';
        if (hintBox) hintBox.style.display = 'block';
      }"""
    assert old_else_branch in s, "Could not find else branch in handleVoiceProviderChange"
    s = s.replace(old_else_branch, new_else_branch, 1)

    old_create = """      } else if (prov === 'voai') {
        const spkSel = document.getElementById('v-voai-speaker')?.value || '佑希';
        const customSpk = (document.getElementById('v-voai-custom-speaker')?.value || '').trim();
        const chosenSpeaker = (spkSel === '__custom__') ? customSpk : spkSel;
        const chosenVer = document.getElementById('v-voai-version')?.value || 'Sota+';
        if (!chosenSpeaker) {
          return alert("Please select or enter a VoAI Speaker name (例如：佑希).");
        }
        if (!name) name = `voai_${chosenVer.toLowerCase().replace(/[^a-z0-9]/g, '')}_${chosenSpeaker}`;
        if (!disp) disp = `VoAI - ${chosenSpeaker} (${chosenVer})`;
      }"""
    new_create = old_create + """ else if (prov === 'edge') {
        const edgeVoice = document.getElementById('v-edge-voice')?.value || 'zh-TW-HsiaoChenNeural';
        const shortTag = edgeVoice.replace('zh-TW-', '').replace('Neural', '').toLowerCase();
        if (!name) name = `edge_tw_${shortTag}_${Date.now().toString().slice(-4)}`;
        if (!disp) disp = `Edge-TTS 臺灣國語 (${edgeVoice})`;
      }"""
    assert old_create in s, "Could not find voai auto-name block in createNewVoice"
    s = s.replace(old_create, new_create, 1)

    old_rate = """      fd.append('speech_rate', prov === 'voai' ? parseFloat(document.getElementById('v-voai-speed')?.value || 1.0) : 1.0);"""
    new_rate = """      fd.append('speech_rate', prov === 'voai' ? parseFloat(document.getElementById('v-voai-speed')?.value || 1.0) : (prov === 'edge' ? parseFloat(document.getElementById('v-edge-speed')?.value || 1.02) : 1.0));"""
    assert old_rate in s, "Could not find speech_rate append in createNewVoice"
    s = s.replace(old_rate, new_rate, 1)

    old_bm_append = """      } else if (prov === 'bluemagpie') {"""
    new_bm_append = """      } else if (prov === 'edge') {
        const edgeVoice = document.getElementById('v-edge-voice')?.value || 'zh-TW-HsiaoChenNeural';
        const edgePitch = parseFloat(document.getElementById('v-edge-pitch')?.value || 0);
        fd.append('voice', edgeVoice);
        fd.append('voice_id', edgeVoice);
        fd.append('model_id', edgeVoice);
        fd.append('pitch_shift', edgePitch);
      } else if (prov === 'bluemagpie') {"""
    assert old_bm_append in s, "Could not find bluemagpie append in createNewVoice"
    s = s.replace(old_bm_append, new_bm_append, 1)

    return s

raw_ui = (ROOT / "ui" / "index.html").read_bytes().decode("utf-8")
if "v-edge-container" not in raw_ui:
    update_file(ROOT / "ui" / "index.html", patch_ui)

# 4. Create new Taiwanese Girl & Taiwanese Man Edge-TTS voice profiles and synthesize test_sample.wav
NEW_PROFILES = [
    {
        "name": "hsiaochen_mandarin",
        "display_name": "曉臻 - 臺灣溫柔知性女聲 (Edge-TTS)",
        "provider": "edge",
        "voice": "zh-TW-HsiaoChenNeural",
        "voice_id": "zh-TW-HsiaoChenNeural",
        "model_id": "zh-TW-HsiaoChenNeural",
        "language": "Traditional Chinese (Taiwan)",
        "speech_rate": 1.02,
        "pitch_shift": 0,
        "pitch": "+0Hz",
        "is_default": False,
        "speaker": "曉臻",
        "gender": "female",
        "persona": "溫柔親切、口條清晰自然的台灣女性旁白與女主角聲線",
        "sample_text": "哈囉大家好，我是曉臻。今天要帶大家一起深入探索這個超有趣的台灣故事與科技趨勢！",
    },
    {
        "name": "hsiaoyu_mandarin",
        "display_name": "曉雨 - 臺灣甜美清亮女孩 (Edge-TTS)",
        "provider": "edge",
        "voice": "zh-TW-HsiaoYuNeural",
        "voice_id": "zh-TW-HsiaoYuNeural",
        "model_id": "zh-TW-HsiaoYuNeural",
        "language": "Traditional Chinese (Taiwan)",
        "speech_rate": 1.04,
        "pitch_shift": 2,
        "pitch": "+2Hz",
        "is_default": False,
        "speaker": "曉雨",
        "gender": "female",
        "persona": "甜美清亮、充滿青春氣息的台灣年輕女孩聲線",
        "sample_text": "嗨！我是曉雨，你有沒有想過為什麼每次到了關鍵時刻，事情總會有意想不到的反轉呢？",
    },
    {
        "name": "tw_girl_lively",
        "display_name": "小晴 - 臺灣元氣活潑少女 (Edge-TTS)",
        "provider": "edge",
        "voice": "zh-TW-HsiaoChenNeural",
        "voice_id": "zh-TW-HsiaoChenNeural",
        "model_id": "zh-TW-HsiaoChenNeural",
        "language": "Traditional Chinese (Taiwan)",
        "speech_rate": 1.08,
        "pitch_shift": 6,
        "pitch": "+6Hz",
        "is_default": False,
        "speaker": "小晴",
        "gender": "female",
        "persona": "語速輕快、活潑俏皮的台灣年輕女孩與閨蜜角色聲線",
        "sample_text": "天啊！你真的不相信我說的嗎？這套系統明明就是我們團隊熬夜寫出來的耶！",
    },
    {
        "name": "tw_lady_mature",
        "display_name": "雅筑 - 臺灣冷靜御姐女聲 (Edge-TTS)",
        "provider": "edge",
        "voice": "zh-TW-HsiaoYuNeural",
        "voice_id": "zh-TW-HsiaoYuNeural",
        "model_id": "zh-TW-HsiaoYuNeural",
        "language": "Traditional Chinese (Taiwan)",
        "speech_rate": 0.97,
        "pitch_shift": -4,
        "pitch": "-4Hz",
        "is_default": False,
        "speaker": "雅筑",
        "gender": "female",
        "persona": "沉著冷靜、氣場強大的台灣職場女主管與知性熟女聲線",
        "sample_text": "這份報告的數據我已經全部查證過了，請大家立刻按照新的專案架構執行。",
    },
    {
        "name": "tw_man_sunny",
        "display_name": "柏翰 - 臺灣陽光暖男男聲 (Edge-TTS)",
        "provider": "edge",
        "voice": "zh-TW-YunJheNeural",
        "voice_id": "zh-TW-YunJheNeural",
        "model_id": "zh-TW-YunJheNeural",
        "language": "Traditional Chinese (Taiwan)",
        "speech_rate": 1.06,
        "pitch_shift": 4,
        "pitch": "+4Hz",
        "is_default": False,
        "speaker": "柏翰",
        "gender": "male",
        "persona": "年輕有活力、親切熱情的台灣陽光青年男聲",
        "sample_text": "放心交給我吧！這個問題我們只要換個角度思考，馬上就能找到最棒的解決方案。",
    },
    {
        "name": "tw_man_deep",
        "display_name": "承恩 - 臺灣低沉霸總男聲 (Edge-TTS)",
        "provider": "edge",
        "voice": "zh-TW-YunJheNeural",
        "voice_id": "zh-TW-YunJheNeural",
        "model_id": "zh-TW-YunJheNeural",
        "language": "Traditional Chinese (Taiwan)",
        "speech_rate": 0.96,
        "pitch_shift": -5,
        "pitch": "-5Hz",
        "is_default": False,
        "speaker": "承恩",
        "gender": "male",
        "persona": "低沉厚實、具威嚴感與磁性魅力的台灣成熟男性與總裁聲線",
        "sample_text": "這場會議我只給你們五分鐘的時間，把真正的關鍵問題說清楚。",
    },
    {
        "name": "tw_man_narrator",
        "display_name": "浩然 - 臺灣沉穩紀錄片男聲 (Edge-TTS)",
        "provider": "edge",
        "voice": "zh-TW-YunJheNeural",
        "voice_id": "zh-TW-YunJheNeural",
        "model_id": "zh-TW-YunJheNeural",
        "language": "Traditional Chinese (Taiwan)",
        "speech_rate": 0.99,
        "pitch_shift": -2,
        "pitch": "-2Hz",
        "is_default": False,
        "speaker": "浩然",
        "gender": "male",
        "persona": "咬字清晰、節奏穩健的台灣深度紀錄片與歷史解說男聲",
        "sample_text": "回顧這段關鍵的歷史轉折，我們可以清楚看見技術革新如何徹底改變了整個產業的命運。",
    },
]

settings = load_settings()
voices_dir = ROOT / "data" / "voices"

for item in NEW_PROFILES:
    sample_text = item.pop("sample_text")
    prof_data = {
        **item,
        "stability": 0.5,
        "similarity_boost": 0.75,
    }
    pdir = voices_dir / item["name"]
    pdir.mkdir(parents=True, exist_ok=True)
    vj = pdir / "voice.json"
    vj.write_text(json.dumps(prof_data, ensure_ascii=False, indent=2), encoding="utf-8")
    sample_wav = pdir / "test_sample.wav"
    if not sample_wav.exists() or sample_wav.stat().st_size < 1000:
        print(f"Synthesizing sample for {item['name']} ({item['display_name']})...")
        synthesize(sample_text, prof_data, sample_wav, settings, provider_override="edge")
    print(f"Ready: {item['name']} -> {sample_wav.stat().st_size} bytes")
