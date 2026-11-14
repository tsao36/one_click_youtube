"""Real-asset-first image sourcing.

Pipeline (all steps cache to <project>/assets/real and research/real_assets.json):

1. discover   - find sources beyond YouTube thumbnails:
                 * full-length YouTube videos (episodes / openings) -> frames at >=720p
                 * Internet Archive video items                       -> frames
                 * Wikipedia / Wikimedia Commons / Openverse stills   -> only full-resolution files
2. mine       - download short windows of each video (<=1080p) and extract sharp, de-duplicated frames
3. caption    - Gemini vision describes every asset and flags unusable ones (burned-in subs, logos, blur)
4. match      - Gemini picks the best asset per scene; low scores are left to the AI generator
5. apply      - writes images/scene_XXX.png (real), backs up the previous AI image, marks the scene

Scenes that are not matched keep their AI image / generate normally.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import shutil
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any, Optional

import requests
from PIL import Image, ImageFilter, ImageStat

from core.logging_setup import log
from rendering.ffmpeg_utils import ffmpeg_bin

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) YoutubeVideoBot/1.0 (documentary research)"
H = {"User-Agent": UA}

MIN_STILL_LONG_EDGE = 1280      # stills must be at least this wide/tall (no thumbnails)
MIN_VIDEO_HEIGHT = 720          # video sources must offer at least this height
WINDOWS_PER_VIDEO = 8
WINDOW_SEC = 6
MATCH_MIN_SCORE = 6             # 0-10; below this the scene stays AI
MAX_REUSE = 2                   # one real asset may be used at most this many times


# ---------------------------------------------------------------- helpers
def _pool_path(project) -> Path:
    return project.path("research", "real_assets.json")


def _asset_dir(project) -> Path:
    d = project.path("assets", "real")
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_pool(project) -> dict[str, Any]:
    p = _pool_path(project)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"sources": [], "assets": []}


def save_pool(project, pool: dict[str, Any]) -> None:
    _pool_path(project).write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")


def _ahash(im: Image.Image) -> int:
    g = im.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    px = list(g.getdata())
    avg = sum(px) / 64.0
    return sum(1 << i for i, v in enumerate(px) if v > avg)


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _sharpness(im: Image.Image) -> float:
    g = im.convert("L").resize((480, int(480 * im.height / im.width)))
    return ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0]


def _brightness(im: Image.Image) -> float:
    return ImageStat.Stat(im.convert("L").resize((64, 36))).mean[0]


def _get_json(url: str, params: dict | None = None, timeout: int = 30) -> Any:
    r = requests.get(url, params=params, headers=H, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- 1. discovery: stills
def search_still_sources(queries: list[str], min_long_edge: int = MIN_STILL_LONG_EDGE) -> list[dict[str, Any]]:
    """Wikimedia Commons + Wikipedia article images + Openverse; full-res only."""
    out: dict[str, dict[str, Any]] = {}

    def add(item: dict[str, Any]) -> None:
        if max(item.get("width", 0), item.get("height", 0)) < min_long_edge:
            return
        out.setdefault(item["url"], item)

    for q in queries:
        # Commons file search (namespace 6) with real dimensions
        try:
            d = _get_json("https://commons.wikimedia.org/w/api.php", {
                "action": "query", "format": "json", "generator": "search", "gsrsearch": q,
                "gsrnamespace": 6, "gsrlimit": 12, "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata"})
            for pg in (d.get("query", {}).get("pages", {}) or {}).values():
                ii = (pg.get("imageinfo") or [{}])[0]
                if not str(ii.get("mime", "")).startswith("image/") or ii.get("mime") == "image/svg+xml":
                    continue
                em = ii.get("extmetadata", {})
                add({"url": ii["url"], "width": ii.get("width", 0), "height": ii.get("height", 0),
                     "title": pg["title"].replace("File:", ""), "source": "Wikimedia Commons",
                     "license": em.get("LicenseShortName", {}).get("value", "CC/PD"),
                     "author": re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))[:60], "query": q})
        except Exception as e:
            log.debug("commons search failed %s: %s", q, e)

        # Wikipedia articles (en/ja/zh): every image used in the article, at original size
        for lang in ("en", "ja", "zh"):
            try:
                d = _get_json(f"https://{lang}.wikipedia.org/w/api.php", {
                    "action": "query", "format": "json", "generator": "search", "gsrsearch": q,
                    "gsrlimit": 2, "prop": "images", "imlimit": 40})
                titles = [i["title"] for pg in (d.get("query", {}).get("pages", {}) or {}).values()
                          for i in pg.get("images", []) if not i["title"].lower().endswith((".svg", ".gif", ".ogg", ".webm"))]
                for i in range(0, len(titles), 20):
                    d2 = _get_json(f"https://{lang}.wikipedia.org/w/api.php", {
                        "action": "query", "format": "json", "titles": "|".join(titles[i:i + 20]),
                        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata"})
                    for pg in (d2.get("query", {}).get("pages", {}) or {}).values():
                        ii = (pg.get("imageinfo") or [{}])[0]
                        if not ii.get("url"):
                            continue
                        em = ii.get("extmetadata", {})
                        add({"url": ii["url"], "width": ii.get("width", 0), "height": ii.get("height", 0),
                             "title": pg["title"].split(":", 1)[-1], "source": f"Wikipedia ({lang})",
                             "license": em.get("LicenseShortName", {}).get("value", "see file page"),
                             "author": re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))[:60], "query": q})
            except Exception as e:
                log.debug("wikipedia %s search failed %s: %s", lang, q, e)

        # Openverse (Flickr, museums, ...) - keep only large originals
        try:
            d = _get_json("https://api.openverse.org/v1/images/", {"q": q, "page_size": 20, "size": "large"})
            for r in d.get("results", []):
                add({"url": r["url"], "width": r.get("width") or 0, "height": r.get("height") or 0,
                     "title": r.get("title") or q, "source": f"Openverse/{r.get('source')}",
                     "license": f"{r.get('license')} {r.get('license_version') or ''}".strip(),
                     "author": (r.get("creator") or "")[:60], "query": q})
        except Exception as e:
            log.debug("openverse search failed %s: %s", q, e)
    return list(out.values())


# ---------------------------------------------------------------- 1b. discovery: video
_BAD_TITLE = re.compile(r"2011|予告|trailer|MAD|AMV|カラオケ|karaoke|ダンボール|解説|レビュー|review|unboxing|おもちゃ|玩具", re.I)


def search_video_sources(queries: list[str], must_match: re.Pattern, limit_per_query: int = 8) -> list[dict[str, Any]]:
    from providers.youtube_snippet_client import search_youtube_videos
    seen: dict[str, dict[str, Any]] = {}
    for q in queries:
        try:
            for v in search_youtube_videos(q, limit=limit_per_query, filter_simplified_chinese=True):
                t = v.get("title", "")
                if v["id"] in seen or not must_match.search(t) or _BAD_TITLE.search(t):
                    continue
                if float(v.get("duration") or 0) < 60:
                    continue
                seen[v["id"]] = {"kind": "youtube", "id": v["id"], "url": v["url"], "title": t,
                                 "duration": float(v.get("duration") or 0)}
        except Exception as e:
            log.debug("youtube search failed %s: %s", q, e)
    # Internet Archive
    for q in queries[:3]:
        try:
            d = _get_json("https://archive.org/advancedsearch.php", {
                "q": f"({q}) AND mediatype:movies", "fl[]": ["identifier", "title"], "rows": 6, "output": "json"})
            for doc in d["response"]["docs"]:
                t = doc.get("title", "")
                if not must_match.search(t) or _BAD_TITLE.search(t):
                    continue
                seen.setdefault("ia_" + doc["identifier"], {
                    "kind": "archive", "id": "ia_" + doc["identifier"], "identifier": doc["identifier"],
                    "url": f"https://archive.org/details/{doc['identifier']}", "title": t, "duration": 0.0})
        except Exception as e:
            log.debug("archive search failed %s: %s", q, e)
    return list(seen.values())


# ---------------------------------------------------------------- 2. mining
def _extract_frames(video: Path, out_dir: Path, prefix: str) -> list[Path]:
    """1 frame / 1.5 s as high-quality JPEG at native resolution."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pat = out_dir / f"{prefix}_%03d.jpg"
    subprocess.run([ffmpeg_bin(), "-y", "-loglevel", "error", "-i", str(video), "-vf", "fps=1/1.5",
                    "-q:v", "2", str(pat)], check=False, timeout=300)
    return sorted(out_dir.glob(f"{prefix}_*.jpg"))


def _download_window_youtube(url: str, start: float, dur: float, dest: Path) -> Optional[tuple[Path, int]]:
    import yt_dlp
    from providers.youtube_snippet_client import _ensure_ffmpeg_path
    ff = _ensure_ffmpeg_path()
    for old in dest.parent.glob(dest.stem + ".*"):
        old.unlink(missing_ok=True)
    opts = {"quiet": True, "no_warnings": True,
            "format": f"bestvideo[height<=1080][ext=mp4]/bestvideo[height<=1080]/best[height<=1080]",
            "download_ranges": lambda info, ydl: [{"start_time": start, "end_time": start + dur}],
            "force_keyframes_at_cuts": True, "outtmpl": str(dest.with_suffix(".%(ext)s")),
            "ffmpeg_location": ff, "overwrites": True, "socket_timeout": 30, "retries": 2}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    files = list(dest.parent.glob(dest.stem + ".*"))
    if not files:
        return None
    return files[0], int(info.get("height") or 0)


def _youtube_max_height(url: str) -> int:
    import yt_dlp
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    return max([int(f.get("height") or 0) for f in info.get("formats", []) if f.get("vcodec") not in (None, "none")] or [0])


def mine_video_source(src: dict[str, Any], work: Path, min_height: int = MIN_VIDEO_HEIGHT,
                      windows: int = WINDOWS_PER_VIDEO) -> list[dict[str, Any]]:
    """Returns list of {path,width,height,source dict} candidate frames (not yet de-duplicated globally)."""
    tmp = work / "_tmp" / src["id"]
    tmp.mkdir(parents=True, exist_ok=True)
    frames: list[dict[str, Any]] = []
    try:
        if src["kind"] == "youtube":
            h = _youtube_max_height(src["url"])
            src["max_height"] = h
            if h < min_height:
                src["skipped"] = f"max height {h}p < {min_height}p"
                return []
            dur = src.get("duration") or 600.0
            lo, hi = dur * 0.04, max(dur * 0.96 - WINDOW_SEC, dur * 0.5)
            starts = [lo + (hi - lo) * i / max(1, windows - 1) for i in range(windows)] if dur > 120 else [min(2.0, dur / 4)]
            for i, st in enumerate(starts):
                try:
                    got = _download_window_youtube(src["url"], st, WINDOW_SEC, tmp / f"w{i}")
                except Exception as e:
                    log.debug("window %s@%s failed: %s", src["id"], st, e)
                    continue
                if got:
                    for f in _extract_frames(got[0], tmp, f"w{i}"):
                        frames.append({"tmp": f, "t": round(st, 1)})
        else:  # internet archive
            meta = _get_json(f"https://archive.org/metadata/{src['identifier']}")
            vids = [f for f in meta.get("files", []) if f["name"].lower().endswith((".mp4", ".mkv", ".avi", ".ogv"))
                    and int(f.get("height") or 0) >= min_height]
            if not vids:
                src["skipped"] = f"no file >= {min_height}p"
                return []
            f0 = vids[0]
            url = f"https://archive.org/download/{src['identifier']}/{urllib.parse.quote(f0['name'])}"
            dur = float(f0.get("length") or 1200)
            for i in range(windows):
                st = dur * (0.04 + 0.9 * i / max(1, windows - 1))
                clip = tmp / f"w{i}.mp4"
                subprocess.run([ffmpeg_bin(), "-y", "-loglevel", "error", "-ss", f"{st:.1f}", "-i", url, "-t", str(WINDOW_SEC),
                                "-an", "-c:v", "copy", str(clip)], check=False, timeout=300)
                if clip.exists():
                    for f in _extract_frames(clip, tmp, f"w{i}"):
                        frames.append({"tmp": f, "t": round(st, 1)})
    except Exception as e:
        src["skipped"] = f"error: {e}"
        log.warning("mining %s failed: %s", src.get("title"), e)
    return frames


def _admit_frames(frames: list[dict[str, Any]], src: dict[str, Any], out_dir: Path, seen_hashes: list[int],
                  max_keep: int = 14, min_height: int = MIN_VIDEO_HEIGHT) -> list[dict[str, Any]]:
    scored = []
    for fr in frames:
        try:
            with Image.open(fr["tmp"]) as im:
                im.load()
                if im.height < min_height:
                    continue
                if _brightness(im) < 25:       # fade-to-black
                    continue
                sh = _sharpness(im)
                scored.append((sh, fr, im.copy()))
        except Exception:
            continue
    scored.sort(key=lambda x: -x[0])
    kept: list[dict[str, Any]] = []
    for sh, fr, im in scored:
        if len(kept) >= max_keep:
            break
        h = _ahash(im)
        if any(_hamming(h, s) <= 8 for s in seen_hashes):
            continue
        seen_hashes.append(h)
        aid = f"{src['id']}_{int(fr['t'])}_{len(kept)}"
        dest = out_dir / f"{aid}.jpg"
        im.convert("RGB").save(dest, "JPEG", quality=95)
        kept.append({"id": aid, "file": dest.name, "width": im.width, "height": im.height, "kind": "frame",
                     "source": src["kind"], "source_title": src["title"], "source_url": src["url"],
                     "timestamp": fr["t"], "sharpness": round(sh, 1), "lowres": im.height < MIN_VIDEO_HEIGHT,
                     "license": "Copyrighted broadcast footage - fair-use / commentary", "author": src["title"][:60]})
    return kept


def download_still(item: dict[str, Any], out_dir: Path, seen_hashes: list[int]) -> Optional[dict[str, Any]]:
    aid = "still_" + hashlib.md5(item["url"].encode()).hexdigest()[:10]
    dest = out_dir / f"{aid}.jpg"
    try:
        r = requests.get(item["url"], headers=H, timeout=60)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content))
        im.load()
        if max(im.size) < MIN_STILL_LONG_EDGE:
            return None
        h = _ahash(im)
        if any(_hamming(h, s) <= 6 for s in seen_hashes):
            return None
        seen_hashes.append(h)
        im.convert("RGB").save(dest, "JPEG", quality=95)
        return {"id": aid, "file": dest.name, "width": im.width, "height": im.height, "kind": "still",
                "source": item["source"], "source_title": item["title"], "source_url": item["url"],
                "license": item.get("license"), "author": item.get("author"), "query": item.get("query")}
    except Exception as e:
        log.debug("still download failed %s: %s", item["url"], e)
        return None


# ---------------------------------------------------------------- 3. gemini helpers
def _gemini():
    from providers.llm.gemini_provider import GeminiProvider
    return GeminiProvider({"api_key_env": "GEMINI_API_KEY"}, model="gemini-flash-latest")


def _gemini_json(parts: list[dict], system: str = "", max_tokens: int = 8192) -> Any:
    from providers.llm.base import extract_json
    g = _gemini()
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens, "responseMimeType": "application/json"}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    return extract_json(g._text(g._call(body)))


def _jpeg_b64(path: Path, edge: int = 640) -> str:
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((edge, edge))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def caption_assets(project, topic_hint: str, batch: int = 8) -> None:
    pool = load_pool(project)
    d = _asset_dir(project)
    todo = [a for a in pool["assets"] if "caption" not in a]
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        parts: list[dict] = [{"text": (
            f"Context: documentary about {topic_hint}. For each numbered image return JSON list "
            "[{\"n\":int,\"caption\":\"<=25 words English, what is visibly shown\",\"subject\":\"robot|motorcycle|hero_human|villain|"
            "group|location|object|text_graphic|other\",\"tags\":[...],\"usable\":bool,\"reason\":\"why unusable or ''\"}]. "
            "usable=false if: burned-in subtitles/watermark/channel logo covering the picture, severe blur, "
            "black/blank, unrelated to context, or modern (post-1980) footage when the topic is 1970s.")}]
        for n, a in enumerate(chunk):
            parts.append({"text": f"Image {n}:"})
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": _jpeg_b64(d / a["file"])}})
        try:
            res = _gemini_json(parts)
        except Exception as e:
            log.warning("caption batch failed: %s", e)
            continue
        by_n = {int(r.get("n", -1)): r for r in res if isinstance(r, dict)}
        for n, a in enumerate(chunk):
            r = by_n.get(n)
            if r:
                a.update(caption=r.get("caption", ""), subject=r.get("subject", "other"), tags=r.get("tags", []),
                         usable=bool(r.get("usable", True)), unusable_reason=r.get("reason", ""))
        save_pool(project, pool)
        log.info("captioned %d/%d", min(i + batch, len(todo)), len(todo))


# ---------------------------------------------------------------- orchestration
def build_pool(project, queries_video: list[str], queries_still: list[str], title_pattern: str,
               min_height: int = MIN_VIDEO_HEIGHT, windows: int = WINDOWS_PER_VIDEO,
               max_videos: int = 6, topic_hint: str = "", skip_stills: bool = False,
               retry_resolution_skips: bool = False) -> dict[str, Any]:
    pool = load_pool(project)
    if retry_resolution_skips:
        pool["sources"] = [s for s in pool["sources"] if not str(s.get("skipped", "")).startswith("max height")]
    d = _asset_dir(project)
    seen = []
    for a in pool["assets"]:
        try:
            with Image.open(d / a["file"]) as im:
                seen.append(_ahash(im))
        except Exception:
            pass

    # stills
    have_urls = {a.get("source_url") for a in pool["assets"]}
    for it in ([] if skip_stills else search_still_sources(queries_still)):
        if it["url"] in have_urls:
            continue
        a = download_still(it, d, seen)
        if a:
            pool["assets"].append(a)
            log.info("still: %s (%dx%d) %s", a["source_title"], a["width"], a["height"], a["source"])
    save_pool(project, pool)

    # videos
    srcs = search_video_sources(queries_video, re.compile(title_pattern, re.I))
    srcs.sort(key=lambda s: -(s["duration"]))
    done = {s["id"] for s in pool["sources"]}
    n_vid = 0
    for s in srcs:
        if s["id"] in done:
            continue
        if n_vid >= max_videos:
            break
        log.info("mining %s (%s)", s["title"], s["url"])
        frames = mine_video_source(s, d, min_height=min_height, windows=windows)
        kept = _admit_frames(frames, s, d, seen, min_height=min_height) if frames else []
        s["frames_kept"] = len(kept)
        pool["sources"].append(s)
        pool["assets"].extend(kept)
        if kept:
            n_vid += 1
        save_pool(project, pool)
        shutil.rmtree(d / "_tmp" / s["id"], ignore_errors=True)
    shutil.rmtree(d / "_tmp", ignore_errors=True)
    if topic_hint:
        caption_assets(project, topic_hint)
    return load_pool(project)


def match_assets_to_scenes(project, topic_hint: str, min_score: int = MATCH_MIN_SCORE,
                           max_reuse: int = MAX_REUSE) -> dict[int, dict[str, Any]]:
    pool = load_pool(project)
    assets = [a for a in pool["assets"] if a.get("usable", True) and a.get("caption")]
    cat = [{"id": a["id"], "caption": a["caption"], "subject": a.get("subject"), "tags": a.get("tags", [])[:6]} for a in assets]
    scenes = [s for s in project.scenes if not getattr(s, "is_presenter", False) and s.visual_type != "talking_head"]
    proposals: list[tuple[int, int, str, str]] = []
    for i in range(0, len(scenes), 12):
        chunk = scenes[i:i + 12]
        sc = [{"scene_id": s.scene_id, "narration": s.narration, "visual": (s.visual_description or "")[:260]} for s in chunk]
        prompt = (f"Documentary topic: {topic_hint}.\nASSET CATALOGUE (real photos/frames):\n{json.dumps(cat, ensure_ascii=False)}\n\n"
                  f"SCENES:\n{json.dumps(sc, ensure_ascii=False)}\n\n"
                  "For each scene choose up to 3 catalogue assets that would genuinely illustrate the narration/visual "
                  "(correct character/vehicle/location/era). Score 0-10 (10 = exactly what the scene shows, 6 = acceptable "
                  "illustration, below 6 = not suitable). Do NOT force matches; return [] when nothing fits. "
                  "JSON: [{\"scene_id\":int,\"picks\":[{\"asset\":\"id\",\"score\":int}]}]")
        try:
            res = _gemini_json([{"text": prompt}])
        except Exception as e:
            log.warning("match batch failed: %s", e)
            continue
        for r in res:
            for p in r.get("picks", []):
                proposals.append((int(p.get("score", 0)), int(r["scene_id"]), p.get("asset"), ""))
    lowres = {a["id"]: bool(a.get("lowres")) for a in assets}
    proposals.sort(key=lambda x: (-x[0], lowres.get(x[2], False), x[1]))   # prefer hi-res on equal score
    valid = {a["id"] for a in assets}
    use_count: dict[str, int] = {}
    last_scene: dict[str, list[int]] = {}
    assign: dict[int, dict[str, Any]] = {}
    for score, sid, aid, _ in proposals:
        if score < min_score or aid not in valid or sid in assign:
            continue
        if use_count.get(aid, 0) >= max_reuse:
            continue
        if any(abs(sid - o) < 6 for o in last_scene.get(aid, [])):
            continue
        assign[sid] = {"asset": aid, "score": score}
        use_count[aid] = use_count.get(aid, 0) + 1
        last_scene.setdefault(aid, []).append(sid)
    return assign


def _fit_16x9(src: Path, dest: Path, w: int = 1920, h: int = 1080) -> None:
    """Cover-crop when aspect is close to 16:9, otherwise sharp foreground over blurred background."""
    with Image.open(src) as im:
        im = im.convert("RGB")
        ar, tar = im.width / im.height, w / h
        if abs(ar - tar) / tar < 0.2:
            if ar > tar:
                nw = int(im.height * tar)
                im = im.crop(((im.width - nw) // 2, 0, (im.width - nw) // 2 + nw, im.height))
            else:
                nh = int(im.width / tar)
                im = im.crop((0, (im.height - nh) // 2, im.width, (im.height - nh) // 2 + nh))
            im = im.resize((w, h), Image.Resampling.LANCZOS)
        else:
            bg = im.copy().resize((w, h), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(28))
            fg = im.copy()
            fg.thumbnail((w, h), Image.Resampling.LANCZOS)
            bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
            im = bg
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "PNG")


def _fit_native(src: Path, dest: Path, w: int = 1920, h: int = 1080) -> None:
    """Low-res source: keep native pixels 1:1 (no upscaling) centred on a black 1080p canvas."""
    with Image.open(src) as im:
        im = im.convert("RGB")
        if im.width > w or im.height > h:
            im.thumbnail((w, h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (w, h), (0, 0, 0))
        canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
        dest.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(dest, "PNG")


def apply_assignments(project, assign: dict[int, dict[str, Any]]) -> list[int]:
    pool = load_pool(project)
    by_id = {a["id"]: a for a in pool["assets"]}
    d = _asset_dir(project)
    backup = project.path("images", "_ai_backup")
    applied: list[int] = []
    from core.models import Status  # type: ignore
    for s in project.scenes:
        pick = assign.get(s.scene_id)
        if not pick:
            continue
        a = by_id[pick["asset"]]
        out = project.path("images", f"{s.tag}.png")
        if out.exists() and not (backup / out.name).exists() and (s.image.meta or {}).get("provider") != "real_asset":
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out, backup / out.name)
        (_fit_native if a.get("lowres") else _fit_16x9)(d / a["file"], out)
        clip = project.path("animation", f"{s.tag}.mp4")
        if clip.exists():
            clip.unlink()
        s.ai_video = False
        s.media_source = "stock_portrait"
        s.visual_type = "authentic_portrait"
        s.search_keyword = a.get("caption", "")[:80]
        s.image.status = Status.COMPLETED
        s.image.path = project.rel(out)
        s.image.error = None
        s.image.meta = {"provider": "real_asset", "asset_id": a["id"], "asset_kind": a["kind"], "source": a["source"],
                        "source_title": a["source_title"], "source_url": a["source_url"], "license": a.get("license"),
                        "author": a.get("author"), "match_score": pick["score"], "caption": a.get("caption"),
                        "width": a["width"], "height": a["height"], "media_source": "stock_portrait", "is_stock": True}
        applied.append(s.scene_id)
    if applied:
        project.save_scenes()
        project.clear_clips_cache()
        project.invalidate("render")
        project.save()
    return applied


def real_first(project, topic_hint: str) -> dict[str, Any]:
    """Match + apply using whatever is in the pool. Leftover scenes keep/generate AI images."""
    assign = match_assets_to_scenes(project, topic_hint)
    applied = apply_assignments(project, assign)
    total = len(project.scenes)
    return {"applied": applied, "real_scenes": len(applied), "total_scenes": total,
            "ai_scenes": [s.scene_id for s in project.scenes if s.scene_id not in applied]}

