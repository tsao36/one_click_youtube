import pytest
from agents.prompts_common import (
    UNIVERSAL_ANATOMY_NEGATIVE,
    UNIVERSAL_FACE_QUALITY_NEGATIVE,
    UNIVERSAL_ANTI_CLONE_NEGATIVE,
    UNIVERSAL_QUALITY_NEGATIVE,
    merge_negative_prompts,
)
from agents.prompt_generator import compose, generate_prompts
from core.models import Scene


def test_merge_negative_prompts_deduplication():
    # Test deduplication, whitespace trimming, and preserving order
    p1 = "text, watermark, blurry"
    p2 = "blurry, extra arms, 4 arms, text"
    merged = merge_negative_prompts(p1, p2)
    tokens = [t.strip() for t in merged.split(",")]
    assert tokens == ["text", "watermark", "blurry", "extra arms", "4 arms"]


def test_universal_negative_contents():
    # Verify critical failure modes are covered in the universal negative tokens
    # 1. 4 hands / extra arms (Scene 23 bug)
    assert "4 arms" in UNIVERSAL_ANATOMY_NEGATIVE
    assert "extra hands" in UNIVERSAL_ANATOMY_NEGATIVE
    assert "extra arms" in UNIVERSAL_ANATOMY_NEGATIVE
    assert "duplicate arms" in UNIVERSAL_ANATOMY_NEGATIVE
    assert "duplicate hands" in UNIVERSAL_ANATOMY_NEGATIVE
    assert "bad anatomy" in UNIVERSAL_ANATOMY_NEGATIVE

    # 2. Low quality face / unclear features (Scene 45 bug)
    assert "featureless face" in UNIVERSAL_FACE_QUALITY_NEGATIVE
    assert "blurry face" in UNIVERSAL_FACE_QUALITY_NEGATIVE
    assert "low quality face" in UNIVERSAL_FACE_QUALITY_NEGATIVE
    assert "indistinct facial features" in UNIVERSAL_FACE_QUALITY_NEGATIVE
    assert "faceless" in UNIVERSAL_FACE_QUALITY_NEGATIVE

    # 3. Identical faces / clone army
    assert "multiple people with the same face" in UNIVERSAL_ANTI_CLONE_NEGATIVE
    assert "identical faces" in UNIVERSAL_ANTI_CLONE_NEGATIVE
    assert "cloned faces" in UNIVERSAL_ANTI_CLONE_NEGATIVE
    assert "duplicate faces" in UNIVERSAL_ANTI_CLONE_NEGATIVE


def test_compose_human_anatomy_and_face_anchoring_scene23_type():
    # Simulates Scene 23 where Judge Mei Ruyao appears (historical role not matching simple "man/woman" keyword previously)
    style = {
        "style": "Makoto Shinkai anime aesthetic",
        "lighting": "golden hour",
        "lens": "35mm",
        "mood": "solemn",
    }
    parts = {
        "subject": "Judge Mei Ruyao standing confidently holding the judgment copy",
        "environment": "courtroom filled with judges and military representatives",
        "composition": "wide shot focusing on the judge and audience",
    }

    prompt = compose(parts, style, [], "image")

    # Positive anatomical baseline must be triggered
    assert "strictly two arms and two hands only" in prompt
    assert "anatomically correct" in prompt
    assert "detailed clear facial features" in prompt

    # Multiple people (judges, military representatives, audience) must trigger diversity anchor
    assert "distinct individual faces" in prompt
    assert "absolutely no identical faces" in prompt


def test_compose_human_anatomy_and_face_anchoring_scene45_type():
    # Simulates Scene 45 where military personnel appear in wide shot
    style = {
        "style": "Makoto Shinkai anime aesthetic",
        "lighting": "golden hour",
        "lens": "panoramic vista",
        "mood": "nostalgic",
    }
    parts = {
        "subject": "Allied military personnel in formal uniforms",
        "environment": "exterior of IMTFE building amidst urban landscape",
        "composition": "wide shot",
    }

    prompt = compose(parts, style, [], "image")

    assert "strictly two arms and two hands only" in prompt
    assert "detailed clear facial features" in prompt
    assert "distinct individual faces" in prompt


def test_compose_technocrats_multi_person_strips_single_focal():
    # Simulates epic_chronicle_mural style which has single clear primary focal subject in its lens
    style = {
        "style": "masterful epic chronicle digital oil painting, textured impasto brushwork",
        "lighting": "dramatic natural sunlight",
        "lens": "cinematic 50mm lens, single clear primary focal subject, centered heroic perspective",
        "mood": "grand, solemn, gritty",
    }
    parts = {
        "subject": "Technocrats analyzing construction progress",
        "environment": "Modern city municipal council",
        "composition": "wide shot",
    }
    prompt = compose(parts, style, [], "image")

    # Conflicting single-subject instructions MUST be stripped for multi-person scenes
    assert "single clear primary focal subject" not in prompt
    assert "centered heroic perspective" not in prompt
    assert "balanced multi-person ensemble composition" in prompt
    assert "distinct individual faces" in prompt
    assert "absolutely no identical faces" in prompt

    assert "absolutely no identical faces" in prompt


def test_generate_prompts_enforces_universal_negative():
    class DummyLLM:
        def json(self, prompt, sys, **kwargs):
            return {"prompts": [{"id": 1, "subject": "Judge at bench", "environment": "hall", "composition": "medium"}]}

    scenes = [
        Scene(scene_id=1, section="Intro", narration="Judge stands in tribunal.", visual_description="Judge at bench", visual_type="image")
    ]
    style = {
        "key": "anime_shinkai",
        "style": "anime style",
        "lighting": "bright",
        "lens": "50mm",
        "mood": "serious",
        "negative": "text, watermark, logo, photo",
        "consistency_seed": 12345,
    }
    bible = {"entities": []}

    results = generate_prompts(scenes, style, bible, DummyLLM())
    assert len(results) == 1
    neg = results[0]["negative"]

    # Verify universal negative tokens are present in generated scene negative prompt
    assert "extra arms" in neg
    assert "4 arms" in neg
    assert "featureless face" in neg
    assert "blurry face" in neg
    assert "identical faces" in neg
    assert "cloned faces" in neg


def test_build_image_system_prompt_and_anti_clone_negatives():
    from agents.prompts_common import build_image_system_prompt, UNIVERSAL_ANTI_CLONE_NEGATIVE

    # Verify extended anti-cloning tokens to avoid triplets / same face syndrome (Scene 5)
    assert "triplets" in UNIVERSAL_ANTI_CLONE_NEGATIVE
    assert "same face syndrome" in UNIVERSAL_ANTI_CLONE_NEGATIVE
    assert "cloned children" in UNIVERSAL_ANTI_CLONE_NEGATIVE
    assert "identical hairstyles" in UNIVERSAL_ANTI_CLONE_NEGATIVE

    sys_prompt = build_image_system_prompt("blurry, watermark")
    assert "CRITICAL SYSTEM DIRECTIVES & STRICT NEGATIVE CONSTRAINTS" in sys_prompt
    assert "STRICTLY NO IDENTICAL FACES / ANTI-CLONING" in sys_prompt
    assert "triplets" in sys_prompt
    assert "same face syndrome" in sys_prompt
    assert "blurry" in sys_prompt
    assert "watermark" in sys_prompt


def test_compose_scene5_children_anti_clone():
    style = {
        "style": "photorealistic 35mm",
        "lighting": "daylight",
        "lens": "50mm",
        "mood": "nostalgia",
    }
    parts = {
        "subject": "Energetic Japanese children with distinct lively facial features, striking transformation poses",
        "environment": "Bustling 1971 Tokyo street corner, colorful vintage toy store windows",
        "composition": "wide shot",
    }
    prompt = compose(parts, style, [], "image")

    assert "strictly two arms and two hands only" in prompt
    assert "detailed clear facial features" in prompt
    assert "distinct individual faces" in prompt


def test_compose_technocrats_multi_person_strips_single_focal():
    # Simulates epic_chronicle_mural style which has single clear primary focal subject in its lens
    style = {
        "style": "masterful epic chronicle digital oil painting, textured impasto brushwork",
        "lighting": "dramatic natural sunlight",
        "lens": "cinematic 50mm lens, single clear primary focal subject, centered heroic perspective",
        "mood": "grand, solemn, gritty",
    }
    parts = {
        "subject": "Technocrats analyzing construction progress",
        "environment": "Modern city municipal council",
        "composition": "wide shot",
    }
    prompt = compose(parts, style, [], "image")

    # Conflicting single-subject instructions MUST be stripped for multi-person scenes
    assert "single clear primary focal subject" not in prompt
    assert "centered heroic perspective" not in prompt
    assert "balanced multi-person ensemble composition" in prompt
    assert "distinct individual faces" in prompt
    assert "absolutely no identical faces" in prompt

    assert "absolutely no identical faces" in prompt
    assert "no cloned triplets" in prompt

