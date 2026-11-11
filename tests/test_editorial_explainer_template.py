from core.motion_graphics_schema import MotionGraphicScene, SceneType


def test_editorial_explainer_props_are_subject_agnostic_and_validated():
    scene = MotionGraphicScene(
        id="editorial-001",
        scene_id=1,
        sceneType=SceneType.EDITORIAL_EXPLAINER,
        props={
            "sceneRole": "constraint",
            "kicker": "SYSTEM LIMIT",
            "title": "One scarce dependency caps the entire system",
            "statement": "The bottleneck can be equipment, people, time, or quality.",
            "items": [
                {"label": "Core system", "value": "2×", "status": "active"},
                {"label": "Equipment", "note": "Long lead time", "status": "negative"},
            ],
            "source": "Verified source",
        },
    )

    assert scene.scene_type == SceneType.EDITORIAL_EXPLAINER
    assert scene.props["sceneRole"] == "constraint"
    assert scene.props["items"][1]["status"] == "negative"
    assert scene.props["accentColor"] == "#F59E0B"

