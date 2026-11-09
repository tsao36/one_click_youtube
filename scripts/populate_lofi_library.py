"""Script to wipe old music library and generate new Lo-fi background music library with rich license tracking."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from core.config import DATA_DIR, ROOT
from core.logging_setup import log
from generators.lofi_synth import LoFiSynthesizer

MUSIC_DIR = DATA_DIR / "music"

# 10 Curated Lo-Fi Tracks covering the 5 required scene tags:
# hook, explanation, revelation, serious, conclusion
LOFI_TRACKS = [
    # ---------------- HOOK ----------------
    {
        "id": "lofi/lofi_hook_headnod.wav",
        "filename": "lofi/lofi_hook_headnod.wav",
        "basename": "lofi_hook_headnod.wav",
        "title": "Midnight Coffee Hook",
        "name": "Midnight Coffee Hook",
        "style": "lofi",
        "scene_tag": "hook",
        "scene_tags": ["hook"],
        "category": "hook",
        "category_label": "Hook & Teaser",
        "bpm": 82.0,
        "key": "Cm",
        "chords": [
            [48, 55, 58, 62, 63, 67],  # Cm9
            [44, 51, 55, 58, 60, 67],  # Abmaj7
            [41, 48, 51, 55, 56, 63],  # Fm9
            [43, 50, 53, 56, 59, 62],  # G7b9
        ],
        "bass": [36, 32, 29, 31],
        "bars": 8,
        "mood": "Punchy, catchy lo-fi headnod beat with warm Rhodes chords and snappy swung rhythm.",
        "description": "Engaging hook beat with swung drums and jazzy Rhodes chords to capture viewer attention.",
        "energy_level": "mid",
        "movement_roles": ["intro", "hook"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.08,
        "voiceover_fitness": 4.8,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0",
            "name": "Creative Commons Attribution 4.0 International",
            "attribution_required": True,
            "attribution_text": "Music: 'Midnight Coffee Hook' by Antigravity Music (CC-BY 4.0)",
            "artist": "Antigravity Lo-Fi Studio",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,  # Restricted: Not API-accessible for raw audio extraction
            "restrictions": ["Attribution required in video description", "No raw audio redistribution", "Sync-to-video only"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },
    {
        "id": "lofi/lofi_hook_groove.wav",
        "filename": "lofi/lofi_hook_groove.wav",
        "basename": "lofi_hook_groove.wav",
        "title": "City Lights Intro",
        "name": "City Lights Intro",
        "style": "lofi",
        "scene_tag": "hook",
        "scene_tags": ["hook"],
        "category": "hook",
        "category_label": "Hook & Teaser",
        "bpm": 84.0,
        "key": "Fm",
        "chords": [
            [41, 48, 51, 55, 56, 63],  # Fm9
            [37, 44, 48, 51, 53, 60],  # Dbmaj7
            [34, 41, 44, 48, 49, 56],  # Bbm9
            [36, 43, 46, 50, 52, 60],  # C7#9
        ],
        "bass": [29, 25, 22, 24],
        "bars": 8,
        "mood": "Engaging urban lo-fi groove with melodic electric keys and attention-grabbing beat.",
        "description": "Crisp modern lo-fi intro beat with inviting swing and warmth.",
        "energy_level": "mid",
        "movement_roles": ["intro", "hook"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.10,
        "voiceover_fitness": 4.7,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0",
            "name": "Creative Commons Attribution 4.0 International",
            "attribution_required": True,
            "attribution_text": "Music: 'City Lights Intro' by Antigravity Music (CC-BY 4.0)",
            "artist": "Antigravity Lo-Fi Studio",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Attribution required in video description", "No raw audio redistribution"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },

    # ---------------- EXPLANATION ----------------
    {
        "id": "lofi/lofi_explanation_flow.wav",
        "filename": "lofi/lofi_explanation_flow.wav",
        "basename": "lofi_explanation_flow.wav",
        "title": "Deep Study Flow",
        "name": "Deep Study Flow",
        "style": "lofi",
        "scene_tag": "explanation",
        "scene_tags": ["explanation"],
        "category": "explanation",
        "category_label": "Explanation & Analysis",
        "bpm": 78.0,
        "key": "Dm",
        "chords": [
            [50, 57, 60, 64, 65, 69],  # Dm9
            [43, 50, 53, 57, 58, 65],  # Gm7
            [48, 55, 58, 62, 64, 67],  # C7
            [41, 48, 52, 55, 57, 64],  # Fmaj7
        ],
        "bass": [38, 31, 36, 29],
        "bars": 8,
        "mood": "Smooth, continuous, low-distraction chill beat designed for deep focus and clear narration.",
        "description": "Gentle study flow keeping viewer attention focused strictly on educational voiceover.",
        "energy_level": "low",
        "movement_roles": ["development", "explanation"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.04,
        "voiceover_fitness": 5.0,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0",
            "name": "Creative Commons Attribution 4.0 International",
            "attribution_required": True,
            "attribution_text": "Music: 'Deep Study Flow' by Antigravity Music (CC-BY 4.0)",
            "artist": "Antigravity Lo-Fi Studio",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Attribution required in video description", "Sync-to-video only"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },
    {
        "id": "lofi/lofi_explanation_clarity.wav",
        "filename": "lofi/lofi_explanation_clarity.wav",
        "basename": "lofi_explanation_clarity.wav",
        "title": "Analytical Calm",
        "name": "Analytical Calm",
        "style": "lofi",
        "scene_tag": "explanation",
        "scene_tags": ["explanation"],
        "category": "explanation",
        "category_label": "Explanation & Analysis",
        "bpm": 75.0,
        "key": "Am",
        "chords": [
            [45, 52, 55, 59, 60, 67],  # Am9
            [38, 45, 48, 52, 53, 60],  # Dm9
            [43, 50, 53, 57, 59, 65],  # G13
            [48, 55, 59, 62, 64, 71],  # Cmaj9
        ],
        "bass": [33, 26, 31, 36],
        "bars": 8,
        "mood": "Gentle minimalist lo-fi rhythm with spacious electric piano chords that stay out of the speech band.",
        "description": "Minimalist backdrop providing continuous rhythmic glue without cognitive load.",
        "energy_level": "low",
        "movement_roles": ["development", "explanation"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.03,
        "voiceover_fitness": 5.0,
        "loop_friendly": True,
        "license": {
            "license_type": "CC0-1.0",
            "name": "Creative Commons CC0 1.0 Universal Public Domain Dedication",
            "attribution_required": False,
            "attribution_text": "Music: 'Analytical Calm' by Antigravity Music (CC0 1.0 Universal - Public Domain)",
            "artist": "Antigravity Lo-Fi Studio",
            "commercial_use_allowed": True,
            "redistribution_allowed": True,
            "api_accessible": True,  # CC0 track is API accessible
            "restrictions": ["Public domain; no restrictions"],
            "terms_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        },
    },

    # ---------------- REVELATION ----------------
    {
        "id": "lofi/lofi_revelation_shimmer.wav",
        "filename": "lofi/lofi_revelation_shimmer.wav",
        "basename": "lofi_revelation_shimmer.wav",
        "title": "Aha Moment Shimmer",
        "name": "Aha Moment Shimmer",
        "style": "lofi",
        "scene_tag": "revelation",
        "scene_tags": ["revelation"],
        "category": "revelation",
        "category_label": "Revelation & Discovery",
        "bpm": 80.0,
        "key": "G",
        "chords": [
            [40, 47, 50, 54, 55, 62],  # Em9
            [36, 43, 47, 50, 52, 59],  # Cmaj9
            [43, 50, 54, 57, 59, 66],  # Gmaj7
            [47, 54, 57, 61, 62, 69],  # Bm7
        ],
        "bass": [28, 24, 31, 35],
        "bars": 8,
        "mood": "Uplifting, airy lo-fi chords with shimmering electric keys and subtle tape warmth, conveying discovery.",
        "description": "Inspiring moment of revelation when the puzzle pieces fall into place.",
        "energy_level": "mid",
        "movement_roles": ["climax", "revelation"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.09,
        "voiceover_fitness": 4.8,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0",
            "name": "Creative Commons Attribution 4.0 International",
            "attribution_required": True,
            "attribution_text": "Music: 'Aha Moment Shimmer' by Antigravity Music (CC-BY 4.0)",
            "artist": "Antigravity Lo-Fi Studio",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Attribution required in video description", "No raw audio redistribution"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },
    {
        "id": "lofi/lofi_revelation_insight.wav",
        "filename": "lofi/lofi_revelation_insight.wav",
        "basename": "lofi_revelation_insight.wav",
        "title": "Cosmic Insight",
        "name": "Cosmic Insight",
        "style": "lofi",
        "scene_tag": "revelation",
        "scene_tags": ["revelation"],
        "category": "revelation",
        "category_label": "Revelation & Discovery",
        "bpm": 82.0,
        "key": "Bb",
        "chords": [
            [46, 53, 57, 60, 62, 69],  # Bbmaj9
            [43, 50, 53, 57, 58, 65],  # Gm7
            [39, 46, 50, 53, 55, 62],  # Ebmaj9
            [41, 48, 51, 55, 57, 63],  # F11
        ],
        "bass": [34, 31, 27, 29],
        "bars": 8,
        "mood": "Expansive, luminous lo-fi atmosphere evoking enlightenment and breakthrough.",
        "description": "Luminous harmonies capturing deep insights and breakthroughs.",
        "energy_level": "mid",
        "movement_roles": ["climax", "revelation"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.07,
        "voiceover_fitness": 4.9,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0",
            "name": "Creative Commons Attribution 4.0 International",
            "attribution_required": True,
            "attribution_text": "Music: 'Cosmic Insight' by Antigravity Music (CC-BY 4.0)",
            "artist": "Antigravity Lo-Fi Studio",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Attribution required in video description"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },

    # ---------------- SERIOUS ----------------
    {
        "id": "lofi/lofi_serious_noir.wav",
        "filename": "lofi/lofi_serious_noir.wav",
        "basename": "lofi_serious_noir.wav",
        "title": "Midnight Noir Dilemma",
        "name": "Midnight Noir Dilemma",
        "style": "lofi",
        "scene_tag": "serious",
        "scene_tags": ["serious"],
        "category": "serious",
        "category_label": "Serious & Critical",
        "bpm": 70.0,
        "key": "Cm",
        "chords": [
            [48, 55, 58, 62, 63, 67],  # Cm9
            [39, 46, 50, 53, 54, 61],  # Ebm6
            [38, 45, 48, 52, 53, 60],  # Dm7b5
            [43, 50, 53, 56, 59, 63],  # G7#5
        ],
        "bass": [36, 27, 26, 31],
        "bars": 8,
        "mood": "Moody, melancholic, low-register minor lo-fi chords with subdued percussion for serious narrative tension.",
        "description": "Deep pensive background for moments of conflict, dilemma, or high stakes.",
        "energy_level": "mid",
        "movement_roles": ["development", "tension", "serious"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.06,
        "voiceover_fitness": 4.9,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0",
            "name": "Creative Commons Attribution 4.0 International",
            "attribution_required": True,
            "attribution_text": "Music: 'Midnight Noir Dilemma' by Antigravity Music (CC-BY 4.0)",
            "artist": "Antigravity Lo-Fi Studio",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Attribution required in video description", "No raw audio redistribution"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },
    {
        "id": "lofi/lofi_serious_reflection.wav",
        "filename": "lofi/lofi_serious_reflection.wav",
        "basename": "lofi_serious_reflection.wav",
        "title": "Weight of the World",
        "name": "Weight of the World",
        "style": "lofi",
        "scene_tag": "serious",
        "scene_tags": ["serious"],
        "category": "serious",
        "category_label": "Serious & Critical",
        "bpm": 72.0,
        "key": "Dm",
        "chords": [
            [50, 57, 60, 64, 65, 69],  # Dm9
            [46, 53, 57, 60, 62, 69],  # Bbmaj7
            [43, 50, 53, 57, 58, 65],  # Gm9
            [45, 52, 57, 60, 62, 67],  # Asus4
        ],
        "bass": [38, 34, 31, 33],
        "bars": 8,
        "mood": "Pensive, subdued lo-fi background highlighting solemn moments, risks, and critical challenges.",
        "description": "Subdued nocturnal chill chords supporting serious commentary without sensationalism.",
        "energy_level": "mid",
        "movement_roles": ["development", "tension", "serious"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.05,
        "voiceover_fitness": 4.9,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0",
            "name": "Creative Commons Attribution 4.0 International",
            "attribution_required": True,
            "attribution_text": "Music: 'Weight of the World' by Antigravity Music (CC-BY 4.0)",
            "artist": "Antigravity Lo-Fi Studio",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Attribution required in video description"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },

    # ---------------- CONCLUSION ----------------
    {
        "id": "lofi/lofi_conclusion_horizon.wav",
        "filename": "lofi/lofi_conclusion_horizon.wav",
        "basename": "lofi_conclusion_horizon.wav",
        "title": "Golden Sunset Horizon",
        "name": "Golden Sunset Horizon",
        "style": "lofi",
        "scene_tag": "conclusion",
        "scene_tags": ["conclusion"],
        "category": "conclusion",
        "category_label": "Conclusion & Outlook",
        "bpm": 76.0,
        "key": "Eb",
        "chords": [
            [39, 46, 50, 53, 55, 62],  # Ebmaj9
            [44, 51, 55, 58, 60, 67],  # Abmaj7
            [41, 48, 51, 55, 56, 63],  # Fm7
            [46, 53, 56, 60, 61, 68],  # Bb9sus4
        ],
        "bass": [27, 32, 29, 34],
        "bars": 8,
        "mood": "Warm, nostalgic, resolving lo-fi progression providing closure, optimism, and future outlook.",
        "description": "Resolving cadence and warm analog tone for summaries and future outlooks.",
        "energy_level": "mid",
        "movement_roles": ["climax", "conclusion"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.05,
        "voiceover_fitness": 5.0,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0",
            "name": "Creative Commons Attribution 4.0 International",
            "attribution_required": True,
            "attribution_text": "Music: 'Golden Sunset Horizon' by Antigravity Music (CC-BY 4.0)",
            "artist": "Antigravity Lo-Fi Studio",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Attribution required in video description", "Sync-to-video only"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },
    {
        "id": "lofi/lofi_conclusion_outro.wav",
        "filename": "lofi/lofi_conclusion_outro.wav",
        "basename": "lofi_conclusion_outro.wav",
        "title": "Final Thoughts",
        "name": "Final Thoughts",
        "style": "lofi",
        "scene_tag": "conclusion",
        "scene_tags": ["conclusion"],
        "category": "conclusion",
        "category_label": "Conclusion & Outlook",
        "bpm": 74.0,
        "key": "C",
        "chords": [
            [48, 55, 59, 62, 64, 71],  # Cmaj9
            [41, 48, 52, 55, 57, 64],  # Fmaj7
            [50, 57, 60, 64, 65, 69],  # Dm9
            [43, 50, 53, 57, 59, 65],  # G7
        ],
        "bass": [36, 29, 38, 31],
        "bars": 8,
        "mood": "Gentle acoustic-flavored lo-fi finish with comforting cadence and satisfying resolution.",
        "description": "Warm, peaceful conclusion leaving viewers with clarity and satisfaction.",
        "energy_level": "low",
        "movement_roles": ["climax", "conclusion"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.04,
        "voiceover_fitness": 5.0,
        "loop_friendly": True,
        "license": {
            "license_type": "CC0-1.0",
            "name": "Creative Commons CC0 1.0 Universal Public Domain Dedication",
            "attribution_required": False,
            "attribution_text": "Music: 'Final Thoughts' by Antigravity Music (CC0 1.0 Universal - Public Domain)",
            "artist": "Antigravity Lo-Fi Studio",
            "commercial_use_allowed": True,
            "redistribution_allowed": True,
            "api_accessible": True,  # CC0 track is API accessible
            "restrictions": ["Public domain; no restrictions"],
            "terms_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        },
    },
]


def wipe_current_tracks() -> int:
    """Delete all current tracks in music library."""
    if not MUSIC_DIR.exists():
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        return 0

    audio_exts = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
    deleted_count = 0

    for item in list(MUSIC_DIR.rglob("*")):
        if item.is_file() and item.suffix.lower() in audio_exts:
            try:
                item.unlink()
                deleted_count += 1
            except Exception as e:
                log.warning("Could not delete %s: %s", item, e)

    # Clean up empty subdirectories except data/music itself
    for d in sorted(MUSIC_DIR.glob("*"), reverse=True):
        if d.is_dir() and d.name != "lofi":
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass

    log.info("Deleted %d existing audio tracks from %s", deleted_count, MUSIC_DIR)
    return deleted_count


def generate_replacement_library() -> dict:
    """Synthesize new Lo-fi library and write catalog.json."""
    synth = LoFiSynthesizer(sample_rate=48000)
    lofi_dir = MUSIC_DIR / "lofi"
    lofi_dir.mkdir(parents=True, exist_ok=True)

    tracks_catalog = []

    for item in LOFI_TRACKS:
        out_path = MUSIC_DIR / item["filename"]
        log.info("Synthesizing Lo-Fi track: %s (%s)...", item["title"], item["scene_tag"])

        prof = synth.generate_track(
            out_path=out_path,
            bpm=item["bpm"],
            chords_midi=item["chords"],
            bass_notes_midi=item["bass"],
            bars_count=item["bars"],
            mood_energy=item["energy_level"],
        )

        size_mb = round(out_path.stat().st_size / (1024 * 1024), 2)
        entry = {
            "id": item["id"],
            "name": item["name"],
            "title": item["title"],
            "style": item["style"],
            "scene_tag": item["scene_tag"],
            "scene_tags": item["scene_tags"],
            "category": item["category"],
            "category_label": item["category_label"],
            "filename": item["filename"],
            "basename": item["basename"],
            "size_mb": size_mb,
            "duration_sec": prof["duration"],
            "bpm": item["bpm"],
            "key": item["key"],
            "peak_db": prof["peak_db"],
            "rms_db": prof["rms_db"],
            "mood": item["mood"],
            "description": item["description"],
            "energy_level": item["energy_level"],
            "movement_roles": item["movement_roles"],
            "instrumental": item["instrumental"],
            "vocals": item["vocals"],
            "loop_friendly": item["loop_friendly"],
            "is_voiceover_ready": item["is_voiceover_ready"],
            "is_distracting": item["is_distracting"],
            "distraction_prob": item["distraction_prob"],
            "voiceover_fitness": item["voiceover_fitness"],
            "tags": ["lofi", item["scene_tag"], item["key"].lower()],
            "url": f"/api/music/audio/{item['filename']}",
            "license": item["license"],
        }
        tracks_catalog.append(entry)

    categories = {
        "hook": {"label": "Hook & Teaser", "description": "Engaging, rhythmic lo-fi beats for video openings."},
        "explanation": {"label": "Explanation & Analysis", "description": "Smooth, low-distraction chill beats for clear narration."},
        "revelation": {"label": "Revelation & Discovery", "description": "Inspiring, shimmering lo-fi for key turning points."},
        "serious": {"label": "Serious & Critical", "description": "Subdued, moody lo-fi minor chords for tension and challenges."},
        "conclusion": {"label": "Conclusion & Outlook", "description": "Warm, resolving lo-fi cadences for summary and outlook."},
    }

    catalog = {
        "default_style": "lofi",
        "starting_bgm_level_dbfs": -24.0,
        "supported_scene_tags": ["hook", "explanation", "revelation", "serious", "conclusion"],
        "categories": categories,
        "tracks": tracks_catalog,
    }

    catalog_path = MUSIC_DIR / "catalog.json"
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote catalog.json with %d tracks to %s", len(tracks_catalog), catalog_path)

    # Clear recent tracks
    rec_file = MUSIC_DIR / "recent_tracks.json"
    rec_file.write_text("[]", encoding="utf-8")

    return catalog


if __name__ == "__main__":
    wiped = wipe_current_tracks()
    cat = generate_replacement_library()
    print(f"Successfully deleted {wiped} old tracks and created {len(cat['tracks'])} replacement Lo-fi tracks.")
