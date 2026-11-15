"""CLI: real-asset-first image sourcing for a project.

  python scripts/real_assets.py build    project_15     # discover + mine + caption
  python scripts/real_assets.py match    project_15     # dry-run matching report
  python scripts/real_assets.py apply    project_15     # write real images into scenes (rest stay AI)
  python scripts/real_assets.py upscale  project_15     # upscale all lowres/vintage images to 1080p
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.project_manager import Project  # noqa: E402
from core import real_asset_pipeline as rap  # noqa: E402
from core.image_upscaler import upscale_image_to_1080p, is_image_low_resolution  # noqa: E402

DEFAULTS = {
    "topic": "Denjin Zaborger (1974 Japanese tokusatsu TV series, P-Productions): robot, motorcycle, cast, Sigma villains, Fuji TV, toys",
    "video_queries": ["電人ザボーガー 第1話", "電人ザボーガー 第50話", "Denjin Zaborger episode", "電人ザボーガー 1974 本編",
                      "電人ザボーガー オープニング 1974", "Denjin Zaborger 1974 full episode", "電人ザボーガー 第39話", "電人ザボーガー 第13話"],
    "still_queries": ["Denjin Zaborger", "電人ザボーガー", "Karate-Robo Zaborgar", "P Productions tokusatsu", "Bullmark chogokin Zaborger",
                      "Enter the Dragon 1973 Bruce Lee", "Fuji Television headquarters 1970s", "Showa 1974 Tokyo street",
                      "Kamen Rider 1971", "Transformers 1984 Optimus Prime toy", "Nakano Broadway", "Popy Chogokin Zaborger"],
    "title_pattern": r"ザボーガー|Zaborger|Zaborgar|ZABOGA|ザボ",
}


def upscale_project_images(p: Project) -> list[int]:
    """Upscale all low-resolution / vintage archive images in project scenes to 1080p."""
    upscaled = []
    for s in p.scenes:
        img_path = p.path("images", f"{s.tag}.png")
        if not img_path.exists():
            continue
        is_low, w, h = is_image_low_resolution(img_path)
        img_meta = s.image.meta or {}
        orig_w = img_meta.get("original_width") or (img_meta.get("width") if img_meta.get("width", 1920) < 1280 else w)
        orig_h = img_meta.get("original_height") or (img_meta.get("height") if img_meta.get("height", 1080) < 720 else h)

        # Target low-res vintage archive images or real assets
        needs_upscale = (
            (img_meta.get("provider") == "real_asset" and not img_meta.get("enhanced"))
            or (orig_w < 1280 and orig_h < 720)
            or (s.visual_type in ("authentic_portrait", "historical_footage") and not img_meta.get("enhanced"))
        )
        if needs_upscale:
            is_face = (s.visual_type in ("authentic_portrait", "talking_head")) or any(
                k in (s.prompt or s.visual_description or "").lower() for k in ["portrait", "face", "actor", "shouting", "helmet"]
            )
            # Find clean source asset if available in assets/real
            src_path = img_path
            aid = img_meta.get("asset_id")
            if aid:
                matches = list(p.path("assets", "real").glob(f"*{aid}*"))
                if matches and matches[0].exists():
                    src_path = matches[0]

            print(f"Upscaling scene #{s.scene_id} ({src_path.name}) to 1920x1080...", flush=True)
            try:
                meta = upscale_image_to_1080p(src_path, img_path, target_w=1920, target_h=1080, face_enhance=is_face, force=True)
                if not s.image.meta:
                    s.image.meta = {}
                s.image.meta.update({
                    "enhanced": True,
                    "upscaled": True,
                    "enhancement": meta,
                    "width": 1920,
                    "height": 1080,
                    "original_width": meta.get("original_size", (orig_w, orig_h))[0],
                    "original_height": meta.get("original_size", (orig_w, orig_h))[1],
                })
                if not s.meta:
                    s.meta = {}
                s.meta["enhanced"] = True
                s.meta["upscaled"] = True
                s.meta["enhancement"] = meta
                p.clear_clips_cache(s.scene_id)
                p.save_scenes()
                upscaled.append(s.scene_id)
                print(f"  -> Scene #{s.scene_id} upscaled successfully ({meta['engine']})", flush=True)
            except Exception as e:
                print(f"  -> Scene #{s.scene_id} upscale error: {e}", flush=True)

    if upscaled:
        p.save()
    return upscaled


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "match", "apply", "upscale"])
    ap.add_argument("project")
    ap.add_argument("--min-height", type=int, default=rap.MIN_VIDEO_HEIGHT)
    ap.add_argument("--max-videos", type=int, default=6)
    ap.add_argument("--windows", type=int, default=rap.WINDOWS_PER_VIDEO)
    ap.add_argument("--tier2", action="store_true", help="also mine 480p sources (automatically upscaled to 1080p via AI super-resolution)")
    ap.add_argument("--min-score", type=int, default=rap.MATCH_MIN_SCORE)
    a = ap.parse_args()
    p = Project(a.project)
    if a.cmd == "upscale":
        up = upscale_project_images(p)
        print(f"Upscaled {len(up)} scenes in {p.id}: {up}")
    elif a.cmd == "build":
        if a.tier2:
            a.min_height, a.windows, a.max_videos = 480, 6, 24
        pool = rap.build_pool(p, DEFAULTS["video_queries"], DEFAULTS["still_queries"], DEFAULTS["title_pattern"],
                              min_height=a.min_height, windows=a.windows, max_videos=a.max_videos, topic_hint=DEFAULTS["topic"], skip_stills=a.tier2, retry_resolution_skips=a.tier2)
        usable = [x for x in pool["assets"] if x.get("usable", True)]
        print(json.dumps({"sources": [(s["title"], s.get("max_height"), s.get("frames_kept"), s.get("skipped")) for s in pool["sources"]],
                          "assets": len(pool["assets"]), "usable": len(usable)}, ensure_ascii=False, indent=1))
    else:
        assign = rap.match_assets_to_scenes(p, DEFAULTS["topic"], min_score=a.min_score)
        print(f"matched {len(assign)}/{len(p.scenes)} scenes")
        if a.cmd == "apply":
            applied = rap.apply_assignments(p, assign)
            print("applied", len(applied), "scenes; AI keeps:", sorted(set(s.scene_id for s in p.scenes) - set(applied)))
        else:
            print(json.dumps(assign, indent=1))


if __name__ == "__main__":
    main()

