from pathlib import Path

ag_p = Path("generators/avatar_generator.py")
content = ag_p.read_text(encoding="utf-8")

old_upload = '''def upload_file_to_fal(file_path: Path, fal_key: str) -> str:
    """Upload local file to Fal.ai storage CDN and return public accessible URL."""
    import mimetypes
    init_url = "https://rest.alpha.fal.ai/storage/upload/initiate"
    mime, _ = mimetypes.guess_type(str(file_path))
    mime = mime or "application/octet-stream"
    headers = {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}
    payload = {"file_name": file_path.name, "content_type": mime}
    r = requests.post(init_url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    d = r.json()
    upload_url = d["upload_url"]
    file_url = d["file_url"]
    
    put_r = requests.put(upload_url, data=file_path.read_bytes(), headers={"Content-Type": mime}, timeout=60)
    put_r.raise_for_status()
    return file_url'''

new_upload = '''def upload_file_to_fal(file_path: Path, fal_key: str) -> str:
    """Upload local file to Fal.ai storage CDN and return public accessible URL."""
    import mimetypes
    init_url = "https://rest.alpha.fal.ai/storage/upload/initiate"
    mime, _ = mimetypes.guess_type(str(file_path))
    mime = mime or "application/octet-stream"
    headers = {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}
    payload = {"file_name": file_path.name, "content_type": mime}
    try:
        r = requests.post(init_url, json=payload, headers=headers, timeout=30)
    except Exception as req_err:
        raise RuntimeError(f"連線至 Fal.ai 上傳伺服器失敗: {req_err}")

    if r.status_code == 403:
        err_msg = ""
        try:
            err_msg = r.json().get("detail", "")
        except Exception:
            err_msg = r.text
        if "exhausted balance" in err_msg.lower() or "locked" in err_msg.lower() or "billing" in err_msg.lower():
            raise RuntimeError(
                f"❌ Fal.ai 帳號額度已耗盡 (User is locked: Exhausted balance)。\\n"
                f"請前往 https://fal.ai/dashboard/billing 儲值，或在虛擬人分頁切換口型引擎為「戴口罩真人 (Masked Speaker)」本地自錄免額度模式。\\n"
                f"Fal.ai 原文回應: {err_msg}"
            )
        raise RuntimeError(f"❌ Fal.ai 授權驗證失敗 (HTTP 403 Forbidden)。請檢查 FAL_KEY 是否正確。回應: {err_msg}")

    r.raise_for_status()
    d = r.json()
    upload_url = d["upload_url"]
    file_url = d["file_url"]
    
    put_r = requests.put(upload_url, data=file_path.read_bytes(), headers={"Content-Type": mime}, timeout=60)
    put_r.raise_for_status()
    return file_url'''

old_fallback = '''        except Exception as e:
            if strict:
                raise
            log.warning("Fal.ai talking avatar (%s) failed (%s); trying SadTalker / local fallback...", key, e)
            if key != "sadtalker":
                try:
                    return _generate_fal_sadtalker(portrait_path, audio_path, output_mp4, fal_key)
                except Exception as e2:
                    log.warning("SadTalker fallback failed too: %s", e2)

    # Fallback to local animated avatar
    return _generate_fallback_talking_avatar(portrait_path, audio_path, output_mp4, width, height, fps)'''

new_fallback = '''        except Exception as e:
            if strict:
                raise
            log.warning("Fal.ai talking avatar (%s) failed (%s); trying base video / SadTalker fallback...", key, e)
            # If the avatar has a real recorded base_video, fallback should use the REAL base_video!
            if base_video.exists():
                log.info("Base video exists for %s: falling back to high-fidelity base video loop and audio mux", name)
                return _generate_masked_speaker_avatar(base_video, audio_path, output_mp4, width=width, height=height, fps=fps)
            if key != "sadtalker":
                try:
                    return _generate_fal_sadtalker(portrait_path, audio_path, output_mp4, fal_key)
                except Exception as e2:
                    log.warning("SadTalker fallback failed too: %s", e2)

    # Fallback to local animated avatar: if base_video exists, prioritize it over still image!
    if base_video.exists():
        log.info("Base video exists for %s: prioritizing base video loop over still image fallback", name)
        return _generate_masked_speaker_avatar(base_video, audio_path, output_mp4, width=width, height=height, fps=fps)
    return _generate_fallback_talking_avatar(portrait_path, audio_path, output_mp4, width, height, fps)'''

# Also update load_avatar to check is_default and handle matching display_name properly
old_load = '''    # Return default if set
    for av in all_avs:
        if av.get("is_default"):
            return av

    return all_avs[0]'''

new_load = '''    # Return default if set
    for av in all_avs:
        if av.get("is_default"):
            return av

    # Prefer tsaotsao / 小曹 if present over arbitrary alphabetic first
    for av in all_avs:
        if av.get("name") in ("tsaotsao", "cao") or av.get("display_name") in ("小曹", "tsaotsao"):
            return av

    return all_avs[0]'''

for label, o, n in [("upload", old_upload, new_upload), ("fallback", old_fallback, new_fallback), ("load", old_load, new_load)]:
    o_clean = o.replace("\r\n", "\n")
    n_clean = n.replace("\r\n", "\n")
    c_clean = content.replace("\r\n", "\n")
    if o_clean in c_clean:
        c_clean = c_clean.replace(o_clean, n_clean, 1)
        content = c_clean
        print(f"Patched: {label}")
    else:
        print(f"FAILED to find: {label}")

ag_p.write_text(content, encoding="utf-8")
print("Done updating generators/avatar_generator.py")
