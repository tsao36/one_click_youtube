"""CLI: real-asset-first image sourcing for a project.

  python scripts/real_assets.py build  project_15     # discover + mine + caption
  python scripts/real_assets.py match  project_15     # dry-run matching report
  python scripts/real_assets.py apply  project_15     # write real images into scenes (rest stay AI)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.project_manager import Project  # noqa: E402
from core import real_asset_pipeline as rap  # noqa: E402

DEFAULTS = {
    "topic": "Denjin Zaborger (1974 Japanese tokusatsu TV series, P-Productions): robot, motorcycle, cast, Sigma villains, Fuji TV, toys",
    "video_queries": ["電人ザボーガー 第1話", "電人ザボーガー 第50話", "Denjin Zaborger episode", "電人ザボーガー 1974 本編",
                      "電人ザボーガー オープニング 1974", "Denjin Zaborger 1974 full episode", "電人ザボーガー 第39話", "電人ザボーガー 第13話"],
    "still_queries": ["Denjin Zaborger", "電人ザボーガー", "Karate-Robo Zaborgar", "P Productions tokusatsu", "Bullmark chogokin Zaborger",
                      "Enter the Dragon 1973 Bruce Lee", "Fuji Television headquarters 1970s", "Showa 1974 Tokyo street",
                      "Kamen Rider 1971", "Transformers 1984 Optimus Prime toy", "Nakano Broadway", "Popy Chogokin Zaborger"],
    "title_pattern": r"ザボーガー|Zaborger|Zaborgar|ZABOGA|ザボ",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "match", "apply"])
    ap.add_argument("project")
    ap.add_argument("--min-height", type=int, default=rap.MIN_VIDEO_HEIGHT)
    ap.add_argument("--max-videos", type=int, default=6)
    ap.add_argument("--windows", type=int, default=rap.WINDOWS_PER_VIDEO)
    ap.add_argument("--tier2", action="store_true", help="also mine 480p sources (shown 1:1 on black canvas)")
    ap.add_argument("--min-score", type=int, default=rap.MATCH_MIN_SCORE)
    a = ap.parse_args()
    p = Project(a.project)
    if a.cmd == "build":
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

