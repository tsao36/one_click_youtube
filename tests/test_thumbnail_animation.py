from pathlib import Path
from unittest.mock import patch
from PIL import Image
from core.models import Scene, Status, Asset
from generators.thumbnail_generator import get_scene_visual_path, resolve_background_image


def test_get_scene_visual_path_prefers_animation(tmp_path):
    # Setup mock project directory
    anim_dir = tmp_path / "animation"
    anim_dir.mkdir(parents=True)
    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True)
    output_frames_dir = tmp_path / "output" / "scene_frames"
    output_frames_dir.mkdir(parents=True)

    # Create dummy image
    img_file = images_dir / "scene_001.png"
    Image.new("RGB", (100, 100), (255, 0, 0)).save(img_file)

    # Create dummy animation MP4 and pre-extracted frame
    anim_file = anim_dir / "scene_001.mp4"
    anim_file.write_bytes(b"dummy mp4 content" * 100)

    import os, time
    # Set anim_file mtime to past
    os.utime(anim_file, (time.time() - 100, time.time() - 100))

    cached_frame = output_frames_dir / "scene_001.png"
    Image.new("RGB", (100, 100), (0, 255, 0)).save(cached_frame)

    class DummyProject:
        def path(self, *parts):
            return tmp_path.joinpath(*parts)
        def abs(self, path):
            return tmp_path / path if path else None
        def rel(self, path):
            return str(Path(path).relative_to(tmp_path)).replace("\\", "/")

    proj = DummyProject()
    scene = Scene(
        scene_id=1,
        narration="Test scene",
        image=Asset(status=Status.COMPLETED, path="images/scene_001.png"),
        animation=Asset(status=Status.COMPLETED, path="animation/scene_001.mp4"),
    )

    vis = get_scene_visual_path(proj, scene)
    # Must prefer animation clip / cached frame over images/scene_001.png
    assert vis == cached_frame

    # Test resolve_background_image with scene_1
    proj.scenes = [scene]
    proj.active_scenes = lambda: [scene]
    bg_img = resolve_background_image(proj, bg_source="scene_1")
    # Cached frame was green (0, 255, 0)
    assert bg_img.getpixel((0, 0)) == (0, 255, 0)


def test_get_scene_visual_path_falls_back_to_image(tmp_path):
    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True)
    img_file = images_dir / "scene_001.png"
    Image.new("RGB", (100, 100), (0, 0, 255)).save(img_file)

    class DummyProject:
        def path(self, *parts):
            return tmp_path.joinpath(*parts)
        def abs(self, path):
            return tmp_path / path if path else None
        def rel(self, path):
            return str(Path(path).relative_to(tmp_path)).replace("\\", "/")

    proj = DummyProject()
    scene = Scene(
        scene_id=1,
        narration="Test scene without anim",
        image=Asset(status=Status.COMPLETED, path="images/scene_001.png"),
        animation=Asset(status=Status.PENDING, path=None),
    )

    vis = get_scene_visual_path(proj, scene)
    assert vis == img_file
