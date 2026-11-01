import re
from pathlib import Path

ROOT = Path(r"c:\AI Project\Youtube_video")

p = ROOT / "core" / "base_pipeline.py"
raw = p.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
norm = raw.replace("\r\n", "\n")

target = "self._run_subtitles()"
avatar_block = """
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

            """

if "Re-generating talking avatar for Scene" not in norm:
    # Find the position of self._run_subtitles() within rerender_voice_and_video
    idx = norm.find("def rerender_voice_and_video")
    sub_idx = norm.find("self._run_subtitles()", idx)
    assert sub_idx != -1, "Could not find self._run_subtitles() in rerender_voice_and_video"
    norm = norm[:sub_idx] + avatar_block + norm[sub_idx:]
    out = norm.replace("\n", "\r\n") if crlf else norm
    p.write_bytes(out.encode("utf-8"))
    print("Patched base_pipeline.py successfully.")
else:
    print("Already patched.")
