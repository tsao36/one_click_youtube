from pathlib import Path

ROOT = Path(r"c:\AI Project\Youtube_video")

def update_file(path: Path, fn):
    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    norm = raw.replace("\r\n", "\n")
    updated = fn(norm)
    if updated != norm:
        out = updated.replace("\n", "\r\n") if crlf else updated
        path.write_bytes(out.encode("utf-8"))

# 2. Patch core/drama_pipeline.py
def patch_drama(s: str) -> str:
    target_needle = "if out_clip.stat().st_mtime >= max(p_mtime, a_mtime):"
    if "v_dur >= a_dur - 0.25" in s:
        return s
    assert target_needle in s, "Could not find target_needle in drama_pipeline.py"
    replacement = """try:
                    from rendering.ffmpeg_utils import duration as get_dur
                    a_dur = float(get_dur(audio_file)) if audio_file.exists() else 0.0
                    v_dur = float(get_dur(out_clip))
                    if out_clip.stat().st_mtime >= max(p_mtime, a_mtime) and (v_dur >= a_dur - 0.25):
                        continue
                except Exception:
                    if out_clip.stat().st_mtime >= max(p_mtime, a_mtime):
                        continue"""
    return s.replace(target_needle, replacement, 1)

update_file(ROOT / "core" / "drama_pipeline.py", patch_drama)

# 3. Patch core/base_pipeline.py rerender_voice_and_video
def patch_base(s: str) -> str:
    old = """            log.info(
                "Re-rendering voice (%d/%d scenes, profile=%s, provider=%s) & updating video for '%s'",
                invalidated_count, len(self.p.active_scenes()), target_prof_name, target_prov, self.p.id
            )
            self._run_voice()
            if self._cancel_flag:
                raise PipelineCancelled()
            try:
                record_stage_version(self.p, "voice")
            except Exception:
                pass

            self._run_subtitles()"""
    new = """            log.info(
                "Re-rendering voice (%d/%d scenes, profile=%s, provider=%s) & updating video for '%s'",
                invalidated_count, len(self.p.active_scenes()), target_prof_name, target_prov, self.p.id
            )
            self._run_voice()
            if self._cancel_flag:
                raise PipelineCancelled()
            try:
                record_stage_version(self.p, "voice")
            except Exception:
                pass

            # If any scene has a presenter / talking avatar, ensure avatar animation video matches the new audio
            presenter_scenes = [s for s in self.p.scenes if (getattr(s, "is_presenter", False) or s.visual_type in ("talking_head", "talking_actor"))]
            if presenter_scenes:
                from generators.avatar_generator import generate_talking_avatar, load_avatar
                for ps in presenter_scenes:
                    if self._cancel_flag: raise PipelineCancelled()
                    audio_f = self.p.abs(ps.audio.path) if (ps.audio and ps.audio.path) else self.p.path("audio", f"{ps.tag}.wav")
                    if not audio_f or not audio_f.exists():
                        continue
                    av_name = getattr(ps, "avatar_profile", None) or (self.p.data.settings or {}).get("default_avatar")
                    av_prof = load_avatar(av_name)
                    if not av_prof:
                        continue
                    out_clip = self.p.path("animation", f"{ps.tag}.mp4")
                    try:
                        self.p.activity(f"Re-generating talking avatar for Scene {ps.scene_id} to match new audio narration...")
                        meta = generate_talking_avatar(audio_f, av_prof, out_clip)
                        ps.animation.status = Status.COMPLETED
                        ps.animation.path = self.p.rel(out_clip)
                        ps.animation.meta = meta
                        ps.animation.error = None
                        ps.ai_video = True
                    except Exception as ex:
                        log.warning("Could not regenerate avatar for scene %d: %s", ps.scene_id, ex)
                self.p.save_scenes()

            self._run_subtitles()"""
    if "Re-generating talking avatar for Scene" in s:
        return s
    assert old in s, "Could not find target in base_pipeline.py"
    return s.replace(old, new, 1)

update_file(ROOT / "core" / "base_pipeline.py", patch_base)

print("All pipeline files patched successfully.")
