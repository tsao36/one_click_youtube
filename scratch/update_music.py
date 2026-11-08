import re
from pathlib import Path

path = Path("generators/music.py")
content = path.read_text(encoding="utf-8")

# 1. Update COMPLEMENTARY_MOVEMENT_CATEGORY
old_comp = '''COMPLEMENTARY_MOVEMENT_CATEGORY = {
    "tech_futuristic": "dramatic_tension",      # Tech setup -> dramatic tension / core problem
    "cinematic_documentary": "dramatic_tension",# History setup -> conflict / turning point
    "dramatic_tension": "mystery_cosmic",       # Investigation -> deep cosmic/forensic mystery
    "mystery_cosmic": "dramatic_tension",       # Cosmic setup -> physical dilemma / tension
    "calm_focus": "tech_futuristic",            # Study/focus setup -> advanced exploration
    "uplifting_inspirational": "calm_focus",     # Inspirational setup -> reflective depth
}'''

new_comp = '''COMPLEMENTARY_MOVEMENT_CATEGORY = {
    "tech_futuristic": "calm_focus",            # Tech setup -> calm/analytical focus (never creepy drama)
    "cinematic_documentary": "dramatic_tension",# History setup -> conflict / turning point
    "dramatic_tension": "mystery_cosmic",       # Investigation -> deep cosmic/forensic mystery
    "mystery_cosmic": "dramatic_tension",       # Cosmic setup -> physical dilemma / tension
    "calm_focus": "tech_futuristic",            # Study/focus setup -> advanced exploration
    "uplifting_inspirational": "calm_focus",     # Inspirational setup -> reflective depth
}

CREEPY_CRIME_TAGS = {"crime", "murder", "danger", "crisis", "stealth", "creepy", "horror"}'''

assert old_comp in content, "old_comp not found in generators/music.py"
content = content.replace(old_comp, new_comp)

# 2. Update filter_by_role_and_energy to avoid creepy/crime tags on non-dramatic videos
old_filter = '''            ready_pool.append(t)
            if movement_role and movement_role not in t_info.get("movement_roles", []):
                continue
            if energy and t_info.get("energy_level") != energy:
                continue
            filtered.append(t)'''

new_filter = '''            ready_pool.append(t)
            # Avoid creepy / crime / danger tracks for non-dramatic/educational topics
            t_tags = set(t_info.get("tags", []))
            if t_tags & CREEPY_CRIME_TAGS:
                t_cat = detect_topic_category(topic or "") if topic else None
                if preferred not in ("dramatic_tension",) and t_cat not in ("dramatic_tension",):
                    continue

            if movement_role and movement_role not in t_info.get("movement_roles", []):
                continue
            if energy and t_info.get("energy_level") != energy:
                continue
            filtered.append(t)'''

assert old_filter in content, "old_filter not found in generators/music.py"
content = content.replace(old_filter, new_filter)

# 3. Update plan_music_timeline M2 selection and fallback
old_m2 = '''        # Movement 2 track (Deep Dive / Investigation / Tension - mid energy)
        main_cat = main_track.parent.name.lower()
        comp_cat = COMPLEMENTARY_MOVEMENT_CATEGORY.get(main_cat, "dramatic_tension")
        m2_track = pick_track(
            directory,
            key + "_m2",
            preferred=comp_cat,
            topic=topic,
            context_text=context_text,
            exclude=used_tracks,
            movement_role="development",
            energy="mid"
        )
        if not m2_track or m2_track in used_tracks:
            m2_track = pick_track(
                directory,
                key + "_m2_alt",
                preferred="dramatic_tension",
                topic=topic,
                context_text=context_text,
                exclude=used_tracks,
                movement_role="development",
                energy="mid"
            )'''

new_m2 = '''        # Movement 2 track (Deep Dive / Investigation / Tension - mid energy)
        main_cat = main_track.parent.name.lower()
        default_comp = "calm_focus" if main_cat == "tech_futuristic" else "dramatic_tension"
        comp_cat = COMPLEMENTARY_MOVEMENT_CATEGORY.get(main_cat, default_comp)
        m2_track = pick_track(
            directory,
            key + "_m2",
            preferred=comp_cat,
            topic=topic,
            context_text=context_text,
            exclude=used_tracks,
            movement_role="development",
            energy="mid"
        )
        if not m2_track or m2_track in used_tracks:
            m2_track = pick_track(
                directory,
                key + "_m2_alt",
                preferred=comp_cat,
                topic=topic,
                context_text=context_text,
                exclude=used_tracks,
                movement_role="development",
                energy="mid"
            )'''

assert old_m2 in content, "old_m2 not found in generators/music.py"
content = content.replace(old_m2, new_m2)

path.write_text(content, encoding="utf-8")
print("Successfully updated generators/music.py!")
