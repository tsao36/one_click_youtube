"""Cloud and local AI pricing catalog and per-stage cost calculation engine."""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

# Standard stages
STAGES = ["research", "script", "scenes", "prompts", "images", "voice", "music", "animation", "subtitles", "render"]

STAGE_META = {
    "research": {"title": "Stage 1: Research", "icon": "🔬", "category": "LLM & Search"},
    "script": {"title": "Stage 2: Narration Script", "icon": "📜", "category": "LLM Narration"},
    "scenes": {"title": "Stage 3: Scene Storyboard", "icon": "🎬", "category": "LLM Directing"},
    "prompts": {"title": "Stage 4: Visual Prompts", "icon": "🎨", "category": "LLM Prompting"},
    "images": {"title": "Stage 5: Image Generation", "icon": "🖼️", "category": "Image Diffusion"},
    "voice": {"title": "Stage 6: Voice Synthesis (TTS)", "icon": "🎙️", "category": "Audio & Speech"},
    "music": {"title": "Stage 7: Ambient Music", "icon": "🎶", "category": "Audio Atmosphere"},
    "animation": {"title": "Stage 8: Animation & Clips", "icon": "✨", "category": "Motion & Video"},
    "presenter": {"title": "Stage 7 (Avatar): Virtual Presenter", "icon": "🎭", "category": "Talking Avatar (Lip-Sync)"},
    "subtitles": {"title": "Stage 8: Subtitle Generation", "icon": "📝", "category": "Transcription"},
    "render": {"title": "Stage 9: Video Rendering", "icon": "⚡", "category": "FFmpeg Encoding"},
}

# Unit rates in USD
PRICING = {
    # LLM pricing per 1M tokens
    "llm": {
        "gemini-3.8-flash": {"input_1m": 0.075, "output_1m": 0.30, "default_req": 0.0006, "is_cloud": True},
        "gemini-3.5-flash": {"input_1m": 0.075, "output_1m": 0.30, "default_req": 0.0006, "is_cloud": True},
        "gemini-2.5-flash": {"input_1m": 0.075, "output_1m": 0.30, "default_req": 0.0006, "is_cloud": True},
        "gemini-1.5-flash": {"input_1m": 0.075, "output_1m": 0.30, "default_req": 0.0006, "is_cloud": True},
        "gemini-1.5-pro": {"input_1m": 1.25, "output_1m": 5.00, "default_req": 0.0040, "is_cloud": True},
        "gemini": {"input_1m": 0.075, "output_1m": 0.30, "default_req": 0.0006, "is_cloud": True},
        "gpt-4o-mini": {"input_1m": 0.15, "output_1m": 0.60, "default_req": 0.0012, "is_cloud": True},
        "gpt-4o": {"input_1m": 2.50, "output_1m": 10.00, "default_req": 0.0150, "is_cloud": True},
        "openai_compat": {"input_1m": 0.15, "output_1m": 0.60, "default_req": 0.0012, "is_cloud": True},
        "ollama": {"input_1m": 0.0, "output_1m": 0.0, "default_req": 0.0, "is_cloud": False},
        "local": {"input_1m": 0.0, "output_1m": 0.0, "default_req": 0.0, "is_cloud": False},
    },
    # Search grounding cost
    "search": {
        "gemini_search": 0.0010,  # $1.00 per 1k grounded search requests
        "google_search": 0.0010,
    },
    # Image providers (per image generated)
    "images": {
        "gemini-2.5-flash-image": 0.039,    # Gemini 2.5 Flash Image (1,290 output tokens @ $30/1M)
        "minimax_video_01": 0.25,           # MiniMax Video-01 Dynamic Scene (~$0.05/sec, 5s clip)
        "minimax": 0.25,
        "canonical_character_portrait": 0.0, # Pre-existing local character anchor portrait (Free)
        "nano-banana-2.1": 0.0168,          # Google Nano Banana 2.1 ($0.0168 batch / $0.0336 online)
        "gemini-nano-banana-2.1": 0.0168,
        "nano-banana": 0.0168,
        "banana": 0.0168,
        "gpt-image-1": 0.080,               # OpenAI gpt-image-1 1536x1024 ($0.080)
        "gpt_image_1": 0.080,
        "imagen-3.0-generate-002": 0.040,   # Google Imagen 3.0 Generate 002 ($0.040)
        "imagen-30.0-generate-002": 0.040,
        "imagen_3_0_generate_002": 0.040,
        "dalle3": 0.040,                    # DALL-E 3 Standard ($0.040)
        "dall-e-3": 0.040,
        "openai": 0.040,
        "imagen3": 0.030,                   # Google Imagen 3 / Gemini Flash Image ($0.030)
        "imagen-3": 0.030,
        "gemini_image": 0.030,
        "fal-ai/flux-1/schnell": 0.003,     # Fal.ai FLUX.1 [schnell] ($0.003)
        "fal-ai/flux/schnell": 0.003,
        "flux-schnell": 0.003,
        "fal-flux-schnell": 0.003,
        "flux-1-schnell": 0.003,
        "stock": 0.0,                       # Online Stock Photos (Free)
        "comfyui": 0.0,                     # Local AMD GPU DirectML (Free)
        "placeholder": 0.0,
    },
    # TTS providers (per 1,000 characters)
    "tts": {
        "elevenlabs": 0.30,      # $0.30 per 1,000 characters
        "voai": 0.030,           # ~$0.03 per 1,000 characters (1 char = 1 point)
        "openai": 0.015,         # $0.015 per 1,000 characters (tts-1)
        "edge": 0.0,             # Microsoft Edge TTS (Free cloud)
        "edge_tts": 0.0,
        "bluemagpie": 0.0,       # Local TTS (Free)
        "sapi": 0.0,             # Local Windows SAPI (Free)
    },
    # AI Video / Animation providers (per clip)
    "animation": {
        "veo": 0.20,             # Google Veo ($0.20/clip)
        "kling": 0.20,            # Kling AI ($0.20/clip)
        "runway": 0.25,          # Runway Gen-3 ($0.25/clip)
        "luma": 0.20,
        "kenburns": 0.0,         # Hardware AMF / CPU Ken Burns (Free)
        "comfyui_video": 0.0,    # Local GPU (Free)
    },
    # Virtual Presenter / Talking Avatar providers (per clip)
    "presenter": {
        "hedra_v3": 0.025,                                # Hedra Character-3 ($0.025/sec)
        "hedra": 0.025,
        "hedra-character-3": 0.025,
        "fal-ai/latentsync": 0.050,                       # Fal.ai LatentSync ($0.05/clip)
        "latentsync": 0.050,
        "fal-ai/kling-video/v1/standard/ai-avatar": 0.100,# Kling AI Avatar Standard ($0.10/clip)
        "kling_std": 0.100,
        "kling-video": 0.100,
        "fal-ai/kling-video/v1/pro/ai-avatar": 0.150,     # Kling AI Avatar Pro ($0.15/clip)
        "kling_pro": 0.150,
        "fal-ai/sadtalker": 0.020,                        # SadTalker ($0.02/clip)
        "sadtalker": 0.020,
        "local_fallback": 0.0,                            # Local FFmpeg / Ken Burns (Free)
        "local": 0.0,
    },
    # Subtitles
    "subtitles": {
        "openai_whisper": 0.006, # $0.006 per audio minute
        "local": 0.0,            # Local faster-whisper (Free)
    },
    # Render
    "render": {
        "h264_amf": 0.0,         # Local AMD AMF (Free)
        "libx264": 0.0,          # Local CPU (Free)
    }
}


def estimate_llm_cost(model_name: str, prompt_tokens: int = 0, completion_tokens: int = 0, requests: int = 1) -> tuple[float, str]:
    """Estimate cost for an LLM call or stage."""
    m_key = model_name.lower().strip()
    rate_info = PRICING["llm"].get(m_key)
    if not rate_info:
        for k, v in PRICING["llm"].items():
            if k in m_key:
                rate_info = v
                break
    if not rate_info:
        rate_info = PRICING["llm"]["gemini-3.8-flash"] if ("gemini" in m_key or "flash" in m_key) else PRICING["llm"]["ollama"]

    if not rate_info.get("is_cloud", False):
        return 0.0, f"{model_name} (Local Free)"

    if prompt_tokens > 0 or completion_tokens > 0:
        cost = (prompt_tokens * rate_info["input_1m"] / 1_000_000.0) + (completion_tokens * rate_info["output_1m"] / 1_000_000.0)
        desc = f"{model_name} ({prompt_tokens:,} in, {completion_tokens:,} out)"
    else:
        cost = requests * rate_info.get("default_req", 0.0006)
        desc = f"{model_name} ({requests} req)"
    return cost, desc


def calculate_project_costs(project: Any) -> dict[str, Any]:
    """
    Examines project configuration, scene assets, and telemetry to calculate
    exact per-stage cloud cost and total sum in USD.
    """
    settings = getattr(project, "settings", {}) or {}
    data = getattr(project, "data", None)
    stage_models = settings.get("stage_models", {})
    cloud_enabled = bool(settings.get("cloud", {}).get("enabled", False))

    stage_costs: dict[str, float] = {}
    stage_details: dict[str, dict[str, Any]] = {}

    scenes = getattr(project, "scenes", []) or []
    scene_count = len(scenes)

    # 1. RESEARCH
    res_model = stage_models.get("research") or ("gemini_search" if cloud_enabled else "ollama")
    res_data = project.read_json("research/research.json", {}) if hasattr(project, "read_json") else {}
    has_res = bool(res_data)
    res_cost = 0.0
    res_desc = "Local / Skipped"
    if has_res:
        mode = res_data.get("mode", "")
        if mode == "gemini_search" or res_model == "gemini_search" or cloud_enabled:
            # Gemini search grounding + LLM generation
            base_cost, _ = estimate_llm_cost("gemini-3.8-flash", prompt_tokens=1200, completion_tokens=1500, requests=1)
            search_grounding = PRICING["search"]["gemini_search"]
            res_cost = base_cost + search_grounding
            res_desc = "Gemini 3.8 Flash + Google Search Grounding"
        elif "gemini" in res_model.lower():
            res_cost, res_desc = estimate_llm_cost("gemini-3.8-flash", prompt_tokens=800, completion_tokens=1200, requests=1)
        elif "openai" in res_model.lower() or "gpt" in res_model.lower():
            res_cost, res_desc = estimate_llm_cost("gpt-4o-mini", prompt_tokens=800, completion_tokens=1200, requests=1)
        else:
            res_desc = f"{res_model} (Local Compute)"
    stage_costs["research"] = round(res_cost, 5)
    stage_details["research"] = {
        "cost": round(res_cost, 5),
        "provider": res_model,
        "description": res_desc,
        "units": f"{1 if has_res else 0} research run"
    }

    # 2. SCRIPT
    scr_model = stage_models.get("script") or ("gemini" if cloud_enabled else "ollama")
    scr_data = project.read_json("script/script.json", {}) if hasattr(project, "read_json") else {}
    word_count = scr_data.get("word_count", 0) or sum(len(s.narration.split()) for s in scenes)
    scr_cost = 0.0
    scr_desc = "Local Compute"
    if scr_data:
        # Script is typically 2-3 LLM calls (outline + expansion), with input context ~2k tokens and output ~1.5k tokens
        approx_in = max(1500, word_count * 5)
        approx_out = max(800, int(word_count * 1.6))
        scr_cost, scr_desc = estimate_llm_cost(scr_model, prompt_tokens=approx_in, completion_tokens=approx_out, requests=2)
    stage_costs["script"] = round(scr_cost, 5)
    stage_details["script"] = {
        "cost": round(scr_cost, 5),
        "provider": scr_model,
        "description": scr_desc,
        "units": f"{word_count} words ({len(scr_data.get('sections', []))} sections)"
    }

    # 3. SCENES
    scenes_model = stage_models.get("scenes") or ("gemini" if cloud_enabled else "ollama")
    scenes_cost = 0.0
    scenes_desc = "Local Compute"
    if scene_count > 0:
        # Scene director + Visual Bible (~2 LLM calls)
        approx_in = 1800 + (scene_count * 80)
        approx_out = max(600, scene_count * 150)
        scenes_cost, scenes_desc = estimate_llm_cost(scenes_model, prompt_tokens=approx_in, completion_tokens=approx_out, requests=2)
    stage_costs["scenes"] = round(scenes_cost, 5)
    stage_details["scenes"] = {
        "cost": round(scenes_cost, 5),
        "provider": scenes_model,
        "description": scenes_desc,
        "units": f"{scene_count} storyboard scenes"
    }

    # 4. PROMPTS
    prompts_model = stage_models.get("prompts") or ("gemini" if cloud_enabled else "ollama")
    prompts_cost = 0.0
    prompts_desc = "Local Compute"
    if scene_count > 0:
        # Prompt batching (~1-2 LLM calls)
        approx_in = 1200 + (scene_count * 100)
        approx_out = max(500, scene_count * 180)
        prompts_cost, prompts_desc = estimate_llm_cost(prompts_model, prompt_tokens=approx_in, completion_tokens=approx_out, requests=max(1, scene_count // 6))
    stage_costs["prompts"] = round(prompts_cost, 5)
    stage_details["prompts"] = {
        "cost": round(prompts_cost, 5),
        "provider": prompts_model,
        "description": prompts_desc,
        "units": f"{scene_count} image prompts"
    }

    # 5. IMAGES
    img_prov_default = stage_models.get("images") or settings.get("images", {}).get("provider", "comfyui")
    img_cost = 0.0
    cloud_img_count = 0
    local_img_count = 0
    img_prov_summary = []

    for s in scenes:
        img_st = getattr(s, "image", None)
        meta = getattr(img_st, "meta", {}) or {} if img_st else {}
        p_name = meta.get("provider") or img_prov_default
        p_key = p_name.lower().strip()
        unit_rate = PRICING["images"].get(p_key, 0.0)
        # Check if actually completed
        is_done = getattr(img_st, "status", None) in ("COMPLETED", Status.COMPLETED if "Status" in globals() else "COMPLETED")
        if is_done and unit_rate > 0:
            img_cost += unit_rate
            cloud_img_count += 1
            if p_name not in img_prov_summary:
                img_prov_summary.append(p_name)
        elif is_done:
            local_img_count += 1
            if p_name not in img_prov_summary:
                img_prov_summary.append(p_name)

    prov_str = ", ".join(img_prov_summary) if img_prov_summary else img_prov_default
    stage_costs["images"] = round(img_cost, 4)
    stage_details["images"] = {
        "cost": round(img_cost, 4),
        "provider": prov_str,
        "description": f"{cloud_img_count} Cloud images @ rate, {local_img_count} Local GPU images (Free)" if cloud_img_count else "Local AMD GPU DirectML (Free)",
        "units": f"{scene_count} images ({cloud_img_count} cloud, {local_img_count} local)"
    }

    # 6. VOICE (TTS)
    tts_prov_default = stage_models.get("voice") or settings.get("voice_profile", "bluemagpie")
    voice_cost = 0.0
    total_chars = 0
    voice_prov_summary = []

    for s in scenes:
        aud_st = getattr(s, "audio", None)
        is_done = getattr(aud_st, "status", None) in ("COMPLETED", Status.COMPLETED if "Status" in globals() else "COMPLETED")
        if not is_done:
            continue
        meta = getattr(aud_st, "meta", {}) or {}
        p_name = meta.get("provider") or tts_prov_default
        p_key = p_name.lower().strip()
        chars = len(getattr(s, "narration", "") or "")
        total_chars += chars

        disp_voice = "BlueMagpie (Local)"
        if "eleven" in p_key:
            voice_cost += (chars / 1000.0) * PRICING["tts"]["elevenlabs"]
            disp_voice = "ElevenLabs"
        elif "voai" in p_key:
            voice_cost += (chars / 1000.0) * PRICING["tts"]["voai"]
            disp_voice = "VoAI (絕好聲創)"
        elif "openai" in p_key:
            voice_cost += (chars / 1000.0) * PRICING["tts"]["openai"]
            disp_voice = "OpenAI TTS"
        elif "edge" in p_key:
            disp_voice = "Edge TTS (Free Cloud)"
        elif "cosy" in p_key or "cozy" in p_key:
            disp_voice = "CosyVoice (Local)"
        elif "sapi" in p_key:
            disp_voice = "Windows SAPI (Local)"
        elif "bluemagpie" in p_key or "magpie" in p_key:
            disp_voice = "BlueMagpie (Local)"
        else:
            disp_voice = f"{p_name} (Local)"

        if disp_voice not in voice_prov_summary:
            voice_prov_summary.append(disp_voice)

    v_str = ", ".join(voice_prov_summary) if voice_prov_summary else tts_prov_default
    stage_costs["voice"] = round(voice_cost, 4)
    stage_details["voice"] = {
        "cost": round(voice_cost, 4),
        "provider": v_str,
        "description": f"{total_chars:,} characters synthesized",
        "units": f"{total_chars:,} chars ({len(scenes)} clips)"
    }

    # 7. ANIMATION (Non-presenter AI Video & Motion Graphics)
    anim_prov = stage_models.get("animation") or "kenburns"
    anim_cost = 0.0
    cloud_clips = 0
    anim_prov_summary = []
    non_presenter_scenes = [s for s in scenes if not (getattr(s, "is_presenter", False) or getattr(s, "visual_type", "") == "talking_head")]
    presenter_scenes = [s for s in scenes if (getattr(s, "is_presenter", False) or getattr(s, "visual_type", "") == "talking_head")]

    for s in non_presenter_scenes:
        anim_st = getattr(s, "animation", None)
        if not anim_st or getattr(anim_st, "status", None) not in ("COMPLETED", "completed") or not getattr(anim_st, "path", None):
            continue
        meta = getattr(anim_st, "meta", {}) or {}
        p_name = meta.get("provider") or anim_prov
        p_key = p_name.lower().strip()
        dur = float(meta.get("duration") or getattr(s, "audio_duration", 0.0) or 0.0)
        if "hedra" in p_key:
            anim_cost += round(0.025 * max(dur, 1.0), 4)
            cloud_clips += 1
            if "Hedra Character-3" not in anim_prov_summary:
                anim_prov_summary.append("Hedra Character-3")
        elif p_key in PRICING["animation"] and PRICING["animation"][p_key] > 0:
            anim_cost += PRICING["animation"][p_key]
            cloud_clips += 1
            if p_name not in anim_prov_summary:
                anim_prov_summary.append(p_name)

    stage_costs["animation"] = round(anim_cost, 4)
    stage_details["animation"] = {
        "cost": round(anim_cost, 4),
        "provider": ", ".join(anim_prov_summary) if anim_prov_summary else anim_prov,
        "description": f"{cloud_clips} AI Video clips" if cloud_clips else "Ken Burns 2.5D Motion (Hardware AMF - Free)",
        "units": f"{cloud_clips} cloud clips" if cloud_clips else f"{len(non_presenter_scenes)} motion scenes"
    }

    # 7b. VIRTUAL PRESENTER (Talking Avatar Lipsync)
    custom_presenter_rate = float((settings.get("pricing") or {}).get("presenter_clip_usd", 0.0))
    presenter_cost = 0.0
    cloud_presenter_clips = 0
    local_presenter_clips = 0
    presenter_prov_summary = []
    total_presenter_seconds = 0.0

    for s in presenter_scenes:
        anim_st = getattr(s, "animation", None)
        if not anim_st or getattr(anim_st, "status", None) not in ("COMPLETED", "completed") or not getattr(anim_st, "path", None):
            continue
        meta = getattr(anim_st, "meta", {}) or {}
        p_name = meta.get("provider") or "fal-ai/latentsync"
        p_key = p_name.lower().strip()
        dur = float(meta.get("duration") or getattr(s, "audio_duration", 0.0) or 0.0)
        total_presenter_seconds += dur

        rate = custom_presenter_rate
        if rate <= 0.0:
            if "hedra" in p_key:
                rate = round(0.025 * max(dur, 1.0), 4)
            elif p_key in PRICING["presenter"]:
                rate = PRICING["presenter"][p_key]
            else:
                for k, v in PRICING["presenter"].items():
                    if k in p_key:
                        rate = v
                        break
            if rate == 0.0 and meta.get("is_cloud", False):
                rate = 0.050

        if meta.get("is_cloud", False) or rate > 0:
            presenter_cost += rate
            cloud_presenter_clips += 1
            disp_name = p_name
            if "hedra" in p_key: disp_name = "Hedra Character-3"
            elif "latentsync" in p_key: disp_name = "LatentSync (fal.ai)"
            elif "kling" in p_key: disp_name = "Kling AI Avatar (fal.ai)"
            elif "sadtalker" in p_key: disp_name = "SadTalker (fal.ai)"
            if disp_name not in presenter_prov_summary:
                presenter_prov_summary.append(disp_name)
        else:
            local_presenter_clips += 1
            if "Local FFmpeg (Free)" not in presenter_prov_summary:
                presenter_prov_summary.append("Local FFmpeg (Free)")

    pres_prov_str = ", ".join(presenter_prov_summary) if presenter_prov_summary else ("None (No avatar)" if not presenter_scenes else "fal-ai/latentsync")

    stage_costs["presenter"] = round(presenter_cost, 4)
    if cloud_presenter_clips > 0:
        pres_desc = f"{cloud_presenter_clips} Cloud lipsync clips ({total_presenter_seconds:.1f}s)"
        pres_units = f"{cloud_presenter_clips} cloud clips ({total_presenter_seconds:.1f}s)"
    elif local_presenter_clips > 0:
        pres_desc = f"{local_presenter_clips} Local lipsync clips ({total_presenter_seconds:.1f}s, Free)"
        pres_units = f"{local_presenter_clips} local clips"
    elif len(presenter_scenes) > 0:
        pres_desc = f"{len(presenter_scenes)} presenter scenes configured (Pending generation)"
        pres_units = f"{len(presenter_scenes)} scenes pending"
    else:
        pres_desc = "No virtual presenter in this project (Free)"
        pres_units = "0 presenter clips"

    stage_details["presenter"] = {
        "cost": round(presenter_cost, 4),
        "provider": pres_prov_str,
        "description": pres_desc,
        "units": pres_units
    }

    # 8. SUBTITLES
    sub_prov = stage_models.get("subtitles") or "local"
    sub_cost = 0.0
    if sub_prov == "openai_whisper":
        total_audio_mins = sum(getattr(s, "audio_duration", 0.0) for s in scenes) / 60.0
        sub_cost = total_audio_mins * PRICING["subtitles"]["openai_whisper"]
    stage_costs["subtitles"] = round(sub_cost, 4)
    stage_details["subtitles"] = {
        "cost": round(sub_cost, 4),
        "provider": sub_prov,
        "description": "Built-in ASS Subtitle Engine (Local - Free)",
        "units": f"{scene_count} subtitle tracks"
    }

    # 9. RENDER
    render_prov = stage_models.get("render") or "h264_amf"
    stage_costs["render"] = 0.0
    stage_details["render"] = {
        "cost": 0.0,
        "provider": render_prov,
        "description": "AMD Hardware Accelerated AMF H.264 (Local GPU - Free)",
        "units": "1 master 1080p video"
    }

    # TOTAL SUM
    total_sum = round(sum(stage_costs.values()), 4)

    return {
        "stage_costs": stage_costs,
        "stage_details": stage_details,
        "total_cost_usd": total_sum,
        "is_cloud_accelerated": cloud_enabled or any(c > 0.0 for c in stage_costs.values()),
    }


def calculate_and_update_project_costs(project: Any) -> dict[str, Any]:
    """Calculate and save cost breakdown directly to project data."""
    res = calculate_project_costs(project)
    if hasattr(project, "data") and hasattr(project.data, "usage"):
        with project.lock:
            u = project.data.usage
            u.stage_costs = res["stage_costs"]
            u.stage_details = res["stage_details"]
            u.estimated_cost_usd = res["total_cost_usd"]
            project.save()
    return res
