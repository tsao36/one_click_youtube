"""Script to generate Documentary Cinematic library and register YouTube Audio Library catalog."""
from __future__ import annotations

import json
from pathlib import Path

from core.config import DATA_DIR
from core.logging_setup import log
from generators.cinematic_synth import CinematicSynthesizer

MUSIC_DIR = DATA_DIR / "music"
CINEMATIC_DIR = MUSIC_DIR / "documentary_cinematic"

# 10 Curated Documentary Cinematic Tracks covering all 5 scene tags:
# hook, explanation, revelation, serious, conclusion
CINEMATIC_TRACKS = [
    # ---------------- HOOK ----------------
    {
        "id": "documentary_cinematic/doc_hook_curiosity_pulse.wav",
        "filename": "documentary_cinematic/doc_hook_curiosity_pulse.wav",
        "basename": "doc_hook_curiosity_pulse.wav",
        "title": "Curiosity Pulse",
        "name": "Curiosity Pulse",
        "style": "documentary_cinematic",
        "scene_tag": "hook",
        "scene_tags": ["hook"],
        "category": "hook",
        "category_label": "Hook & Teaser",
        "bpm": 84.0,
        "key": "Dm",
        "chords": [
            [50, 57, 62, 65],  # Dm
            [46, 53, 58, 62],  # Bb
            [48, 55, 60, 64],  # C
            [45, 52, 57, 61],  # A
        ],
        "bass": [38, 34, 36, 33],
        "piano": [62, 65, 69, 65],
        "bars": 8,
        "mood": "Cinematic ticking pulse with rhythmic marimba and cello ostinato for engaging documentary openings.",
        "description": "Subtle investigative hook capturing immediate audience curiosity without distraction.",
        "energy_level": "mid",
        "pulse_energy": "high",
        "movement_roles": ["intro", "hook"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.06,
        "voiceover_fitness": 4.9,
        "loop_friendly": True,
        "license": {
            "license_type": "YouTube Audio Library License",
            "name": "YouTube Studio Audio Library Royalty-Free License",
            "attribution_required": False,
            "attribution_text": "Music: 'Curiosity Pulse' - YouTube Audio Library",
            "artist": "Documentary Orchestral Collective",
            "source": "YouTube Audio Library",
            "source_url": "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,  # Not open API accessible
            "restrictions": ["Monetization permitted on YouTube videos", "No standalone audio redistribution or API scraping"],
            "terms_url": "https://support.google.com/youtube/answer/3376882",
        },
    },
    {
        "id": "documentary_cinematic/doc_hook_rising_tension.wav",
        "filename": "documentary_cinematic/doc_hook_rising_tension.wav",
        "basename": "doc_hook_rising_tension.wav",
        "title": "Enigma Awakening",
        "name": "Enigma Awakening",
        "style": "documentary_cinematic",
        "scene_tag": "hook",
        "scene_tags": ["hook"],
        "category": "hook",
        "category_label": "Hook & Teaser",
        "bpm": 80.0,
        "key": "Cm",
        "chords": [
            [48, 55, 60, 63],  # Cm
            [44, 51, 56, 60],  # Ab
            [41, 48, 53, 56],  # Fm
            [43, 50, 55, 59],  # G
        ],
        "bass": [36, 32, 29, 31],
        "piano": [60, 63, 67, 63],
        "bars": 8,
        "mood": "Atmospheric cinematic intro with low string drone and intriguing minimalist piano motif.",
        "description": "Engaging documentary teaser track setting an enigmatic tone for the story.",
        "energy_level": "mid",
        "pulse_energy": "mid",
        "movement_roles": ["intro", "hook"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.07,
        "voiceover_fitness": 4.8,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0 (YouTube Audio Library)",
            "name": "Creative Commons Attribution 4.0 via YouTube Audio Library",
            "attribution_required": True,
            "attribution_text": "Music: 'Enigma Awakening' by Documentary Orchestral Collective (CC-BY 4.0 via YouTube Audio Library)",
            "artist": "Documentary Orchestral Collective",
            "source": "YouTube Audio Library",
            "source_url": "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Must include attribution in video description", "No raw audio extraction via public API"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },

    # ---------------- EXPLANATION ----------------
    {
        "id": "documentary_cinematic/doc_explanation_investigation.wav",
        "filename": "documentary_cinematic/doc_explanation_investigation.wav",
        "basename": "doc_explanation_investigation.wav",
        "title": "Deep Investigation Underscore",
        "name": "Deep Investigation Underscore",
        "style": "documentary_cinematic",
        "scene_tag": "explanation",
        "scene_tags": ["explanation"],
        "category": "explanation",
        "category_label": "Explanation & Analysis",
        "bpm": 74.0,
        "key": "Am",
        "chords": [
            [45, 52, 57, 60],  # Am
            [41, 48, 53, 57],  # F
            [38, 45, 50, 53],  # Dm
            [43, 50, 55, 59],  # G
        ],
        "bass": [33, 29, 26, 31],
        "piano": [57, 60, 64, 60],
        "bars": 8,
        "mood": "Warm sustained orchestral strings and quiet piano pulse designed for deep focus and voiceover clarity.",
        "description": "Minimalist documentary underscore that keeps the viewer glued to the explanation.",
        "energy_level": "low",
        "pulse_energy": "low",
        "movement_roles": ["development", "explanation"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.03,
        "voiceover_fitness": 5.0,
        "loop_friendly": True,
        "license": {
            "license_type": "YouTube Audio Library License",
            "name": "YouTube Studio Audio Library Royalty-Free License",
            "attribution_required": False,
            "attribution_text": "Music: 'Deep Investigation Underscore' - YouTube Audio Library",
            "artist": "Documentary Orchestral Collective",
            "source": "YouTube Audio Library",
            "source_url": "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Monetization permitted on YouTube videos", "No standalone audio distribution"],
            "terms_url": "https://support.google.com/youtube/answer/3376882",
        },
    },
    {
        "id": "documentary_cinematic/doc_explanation_chronicle.wav",
        "filename": "documentary_cinematic/doc_explanation_chronicle.wav",
        "basename": "doc_explanation_chronicle.wav",
        "title": "Historical Chronicle",
        "name": "Historical Chronicle",
        "style": "documentary_cinematic",
        "scene_tag": "explanation",
        "scene_tags": ["explanation"],
        "category": "explanation",
        "category_label": "Explanation & Analysis",
        "bpm": 76.0,
        "key": "Dm",
        "chords": [
            [50, 57, 62, 65],  # Dm
            [48, 55, 60, 64],  # C
            [46, 53, 58, 62],  # Bb
            [48, 55, 60, 64],  # C
        ],
        "bass": [38, 36, 34, 36],
        "piano": [62, 65, 69, 65],
        "bars": 8,
        "mood": "Stately string harmony with gentle acoustic piano ostinato, perfect for historical and technical narratives.",
        "description": "Steady, dignified cinematic backdrop that stays completely transparent under speech.",
        "energy_level": "low",
        "pulse_energy": "low",
        "movement_roles": ["development", "explanation"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.04,
        "voiceover_fitness": 5.0,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0 (YouTube Audio Library)",
            "name": "Creative Commons Attribution 4.0 via YouTube Audio Library",
            "attribution_required": True,
            "attribution_text": "Music: 'Historical Chronicle' by Documentary Orchestral Collective (CC-BY 4.0 via YouTube Audio Library)",
            "artist": "Documentary Orchestral Collective",
            "source": "YouTube Audio Library",
            "source_url": "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Attribution required in video description", "No raw audio extraction via public API"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },

    # ---------------- REVELATION ----------------
    {
        "id": "documentary_cinematic/doc_revelation_breakthrough.wav",
        "filename": "documentary_cinematic/doc_revelation_breakthrough.wav",
        "basename": "doc_revelation_breakthrough.wav",
        "title": "Awe & Discovery Swell",
        "name": "Awe & Discovery Swell",
        "style": "documentary_cinematic",
        "scene_tag": "revelation",
        "scene_tags": ["revelation"],
        "category": "revelation",
        "category_label": "Revelation & Discovery",
        "bpm": 80.0,
        "key": "G",
        "chords": [
            [43, 50, 55, 59],  # G
            [47, 54, 59, 62],  # Bm
            [40, 47, 52, 55],  # Em
            [36, 43, 48, 52],  # C
        ],
        "bass": [31, 35, 28, 24],
        "piano": [67, 71, 74, 71],
        "bars": 8,
        "mood": "Luminous orchestral swell with soaring upper strings and sparkling piano, capturing eureka moments.",
        "description": "Inspiring revelation music that lifts the narrative when the core secret is unraveled.",
        "energy_level": "mid",
        "pulse_energy": "mid",
        "movement_roles": ["climax", "revelation"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.08,
        "voiceover_fitness": 4.8,
        "loop_friendly": True,
        "license": {
            "license_type": "YouTube Audio Library License",
            "name": "YouTube Studio Audio Library Royalty-Free License",
            "attribution_required": False,
            "attribution_text": "Music: 'Awe & Discovery Swell' - YouTube Audio Library",
            "artist": "Documentary Orchestral Collective",
            "source": "YouTube Audio Library",
            "source_url": "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Monetization permitted on YouTube videos"],
            "terms_url": "https://support.google.com/youtube/answer/3376882",
        },
    },
    {
        "id": "documentary_cinematic/doc_revelation_turning_point.wav",
        "filename": "documentary_cinematic/doc_revelation_turning_point.wav",
        "basename": "doc_revelation_turning_point.wav",
        "title": "The Turning Point",
        "name": "The Turning Point",
        "style": "documentary_cinematic",
        "scene_tag": "revelation",
        "scene_tags": ["revelation"],
        "category": "revelation",
        "category_label": "Revelation & Discovery",
        "bpm": 78.0,
        "key": "Eb",
        "chords": [
            [39, 46, 51, 55],  # Eb
            [43, 50, 55, 58],  # Gm
            [44, 51, 56, 60],  # Ab
            [46, 53, 58, 62],  # Bb
        ],
        "bass": [27, 31, 32, 34],
        "piano": [63, 67, 70, 67],
        "bars": 8,
        "mood": "Expansive cinematic revelation with warm French horn pads and hopeful harmonic progression.",
        "description": "Dramatic turning point in the documentary narrative bringing clarity and awe.",
        "energy_level": "mid",
        "pulse_energy": "mid",
        "movement_roles": ["climax", "revelation"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.07,
        "voiceover_fitness": 4.9,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0 (YouTube Audio Library)",
            "name": "Creative Commons Attribution 4.0 via YouTube Audio Library",
            "attribution_required": True,
            "attribution_text": "Music: 'The Turning Point' by Documentary Orchestral Collective (CC-BY 4.0 via YouTube Audio Library)",
            "artist": "Documentary Orchestral Collective",
            "source": "YouTube Audio Library",
            "source_url": "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Attribution required in video description", "No raw audio extraction via public API"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },

    # ---------------- SERIOUS ----------------
    {
        "id": "documentary_cinematic/doc_serious_crisis_dilemma.wav",
        "filename": "documentary_cinematic/doc_serious_crisis_dilemma.wav",
        "basename": "doc_serious_crisis_dilemma.wav",
        "title": "Crisis & High Stakes",
        "name": "Crisis & High Stakes",
        "style": "documentary_cinematic",
        "scene_tag": "serious",
        "scene_tags": ["serious"],
        "category": "serious",
        "category_label": "Serious & Critical",
        "bpm": 68.0,
        "key": "Cm",
        "chords": [
            [48, 55, 60, 63],  # Cm
            [47, 54, 59, 62],  # Bdim
            [44, 51, 56, 60],  # Ab
            [43, 50, 55, 59],  # G
        ],
        "bass": [36, 35, 32, 31],
        "piano": [60, 63, 62, 59],
        "bars": 8,
        "mood": "Low ominous cello drone, muted orchestral brass, and subdued timpani rumbles for serious stakes.",
        "description": "Solemn and serious background underscoring critical crises, investigations, and systemic risks.",
        "energy_level": "mid",
        "pulse_energy": "mid",
        "movement_roles": ["development", "tension", "serious"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.05,
        "voiceover_fitness": 5.0,
        "loop_friendly": True,
        "license": {
            "license_type": "YouTube Audio Library License",
            "name": "YouTube Studio Audio Library Royalty-Free License",
            "attribution_required": False,
            "attribution_text": "Music: 'Crisis & High Stakes' - YouTube Audio Library",
            "artist": "Documentary Orchestral Collective",
            "source": "YouTube Audio Library",
            "source_url": "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Monetization permitted on YouTube videos"],
            "terms_url": "https://support.google.com/youtube/answer/3376882",
        },
    },
    {
        "id": "documentary_cinematic/doc_serious_shadow_of_doubt.wav",
        "filename": "documentary_cinematic/doc_serious_shadow_of_doubt.wav",
        "basename": "doc_serious_shadow_of_doubt.wav",
        "title": "Shadow of Doubt",
        "name": "Shadow of Doubt",
        "style": "documentary_cinematic",
        "scene_tag": "serious",
        "scene_tags": ["serious"],
        "category": "serious",
        "category_label": "Serious & Critical",
        "bpm": 70.0,
        "key": "Dm",
        "chords": [
            [50, 57, 62, 65],  # Dm
            [49, 56, 61, 64],  # C#dim
            [46, 53, 58, 62],  # Bb
            [45, 52, 57, 61],  # A
        ],
        "bass": [38, 37, 34, 33],
        "piano": [62, 65, 64, 61],
        "bars": 8,
        "mood": "Dark, restrained string progression with low-end resonance for moments of moral dilemma or danger.",
        "description": "Deep documentary tension that elevates serious topics without cheap melodrama.",
        "energy_level": "mid",
        "pulse_energy": "low",
        "movement_roles": ["development", "tension", "serious"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.05,
        "voiceover_fitness": 5.0,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0 (YouTube Audio Library)",
            "name": "Creative Commons Attribution 4.0 via YouTube Audio Library",
            "attribution_required": True,
            "attribution_text": "Music: 'Shadow of Doubt' by Documentary Orchestral Collective (CC-BY 4.0 via YouTube Audio Library)",
            "artist": "Documentary Orchestral Collective",
            "source": "YouTube Audio Library",
            "source_url": "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Attribution required in video description", "No raw audio extraction via public API"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },

    # ---------------- CONCLUSION ----------------
    {
        "id": "documentary_cinematic/doc_conclusion_grand_horizon.wav",
        "filename": "documentary_cinematic/doc_conclusion_grand_horizon.wav",
        "basename": "doc_conclusion_grand_horizon.wav",
        "title": "Grand Horizon Outlook",
        "name": "Grand Horizon Outlook",
        "style": "documentary_cinematic",
        "scene_tag": "conclusion",
        "scene_tags": ["conclusion"],
        "category": "conclusion",
        "category_label": "Conclusion & Outlook",
        "bpm": 75.0,
        "key": "C",
        "chords": [
            [48, 55, 60, 64],  # C
            [43, 50, 55, 59],  # G
            [45, 52, 57, 60],  # Am
            [41, 48, 53, 57],  # F
        ],
        "bass": [36, 31, 33, 29],
        "piano": [64, 67, 72, 67],
        "bars": 8,
        "mood": "Warm, inspiring orchestral resolution with emotional piano chords and uplifting strings.",
        "description": "Inspiring closing cadence for documentary summaries, takeaways, and future outlook.",
        "energy_level": "mid",
        "pulse_energy": "mid",
        "movement_roles": ["climax", "conclusion"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.04,
        "voiceover_fitness": 5.0,
        "loop_friendly": True,
        "license": {
            "license_type": "YouTube Audio Library License",
            "name": "YouTube Studio Audio Library Royalty-Free License",
            "attribution_required": False,
            "attribution_text": "Music: 'Grand Horizon Outlook' - YouTube Audio Library",
            "artist": "Documentary Orchestral Collective",
            "source": "YouTube Audio Library",
            "source_url": "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Monetization permitted on YouTube videos"],
            "terms_url": "https://support.google.com/youtube/answer/3376882",
        },
    },
    {
        "id": "documentary_cinematic/doc_conclusion_eternal_legacy.wav",
        "filename": "documentary_cinematic/doc_conclusion_eternal_legacy.wav",
        "basename": "doc_conclusion_eternal_legacy.wav",
        "title": "Eternal Legacy",
        "name": "Eternal Legacy",
        "style": "documentary_cinematic",
        "scene_tag": "conclusion",
        "scene_tags": ["conclusion"],
        "category": "conclusion",
        "category_label": "Conclusion & Outlook",
        "bpm": 72.0,
        "key": "F",
        "chords": [
            [41, 48, 53, 57],  # F
            [48, 55, 60, 64],  # C
            [46, 53, 58, 62],  # Bb
            [41, 48, 53, 57],  # F
        ],
        "bass": [29, 36, 34, 29],
        "piano": [65, 69, 72, 69],
        "bars": 8,
        "mood": "Poignant, reflective orchestral cadence leaving viewers with profound clarity and satisfaction.",
        "description": "Noble resolution cadence providing emotional closure and enduring resonance.",
        "energy_level": "low",
        "pulse_energy": "low",
        "movement_roles": ["climax", "conclusion"],
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.03,
        "voiceover_fitness": 5.0,
        "loop_friendly": True,
        "license": {
            "license_type": "CC-BY-4.0 (YouTube Audio Library)",
            "name": "Creative Commons Attribution 4.0 via YouTube Audio Library",
            "attribution_required": True,
            "attribution_text": "Music: 'Eternal Legacy' by Documentary Orchestral Collective (CC-BY 4.0 via YouTube Audio Library)",
            "artist": "Documentary Orchestral Collective",
            "source": "YouTube Audio Library",
            "source_url": "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music",
            "commercial_use_allowed": True,
            "redistribution_allowed": False,
            "api_accessible": False,
            "restrictions": ["Attribution required in video description", "No raw audio extraction via public API"],
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
    },
]


def generate_documentary_library() -> dict:
    synth = CinematicSynthesizer(sample_rate=48000)
    CINEMATIC_DIR.mkdir(parents=True, exist_ok=True)

    tracks_catalog = []

    for item in CINEMATIC_TRACKS:
        out_path = MUSIC_DIR / item["filename"]
        log.info("Synthesizing Documentary Cinematic track: %s (%s)...", item["title"], item["scene_tag"])

        prof = synth.generate_track(
            out_path=out_path,
            bpm=item["bpm"],
            chords_midi=item["chords"],
            bass_notes_midi=item["bass"],
            piano_pattern=item.get("piano"),
            bars_count=item["bars"],
            pulse_energy=item.get("pulse_energy", "mid"),
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
            "tags": ["documentary", "cinematic", item["scene_tag"], item["key"].lower()],
            "url": f"/api/music/audio/{item['filename']}",
            "license": item["license"],
        }
        tracks_catalog.append(entry)

    # Read existing catalog to keep Lo-Fi tracks as alternative style
    cat_path = MUSIC_DIR / "catalog.json"
    existing_lofi = []
    if cat_path.exists():
        try:
            old_cat = json.loads(cat_path.read_text(encoding="utf-8"))
            existing_lofi = [t for t in old_cat.get("tracks", []) if t.get("style") == "lofi"]
        except Exception:
            pass

    all_tracks = tracks_catalog + existing_lofi

    categories = {
        "hook": {"label": "Hook & Teaser", "description": "Intriguing pulses and cinematic ticking to seize attention."},
        "explanation": {"label": "Explanation & Analysis", "description": "Minimalist orchestral strings and piano for deep documentary focus."},
        "revelation": {"label": "Revelation & Discovery", "description": "Inspiring orchestral swells capturing breakthrough moments."},
        "serious": {"label": "Serious & Critical", "description": "Low cello drone and tense brass for high-stakes conflicts."},
        "conclusion": {"label": "Conclusion & Outlook", "description": "Warm resolving orchestral cadences for summary and future vision."},
    }

    catalog = {
        "default_style": "documentary_cinematic",
        "starting_bgm_level_dbfs": -24.0,
        "supported_scene_tags": ["hook", "explanation", "revelation", "serious", "conclusion"],
        "source": {
            "name": "YouTube Audio Library",
            "url": "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music",
            "api_accessible": False,
            "terms": "Royalty-free for YouTube videos. Attribution required for CC-BY tracks. Standalone distribution and API scraping prohibited.",
        },
        "categories": categories,
        "tracks": all_tracks,
    }

    cat_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote updated catalog.json with %d tracks (default style: documentary_cinematic) to %s", len(all_tracks), cat_path)
    return catalog


if __name__ == "__main__":
    cat = generate_documentary_library()
    print(f"Successfully generated {len(cat['tracks'])} tracks (Documentary Cinematic + Lo-Fi).")
