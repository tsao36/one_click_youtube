"""Tests for external drive video archive and playback after YouTube upload."""
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api_server import app
from core.project_manager import Project


@pytest.fixture
def test_project(tmp_path):
    """Create a temporary dummy project with a video file."""
    # Mock projects directory to point here
    with patch("core.project_manager.PROJECTS_DIR", tmp_path), \
         patch("api_server.PROJECTS_DIR", tmp_path), \
         patch("api_routes.media.PROJECTS_DIR", tmp_path):
        proj = Project.create("External video test", project_id="test_external_proj")
        final_dir = proj.dir / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        vid_file = final_dir / f"{proj.id}.mp4"
        vid_file.write_bytes(b"dummy mp4 video data for test" * 100)
        proj.data.outputs["final"] = f"final/{proj.id}.mp4"
        proj.save()
        yield proj, tmp_path


def test_external_video_migration_and_streaming(test_project, tmp_path):
    proj, projects_root = test_project
    client = TestClient(app)

    # Create dummy external drive directory
    ext_dir = tmp_path / "external_drive"
    ext_dir.mkdir(parents=True, exist_ok=True)
    dest_video = ext_dir / "test_external_proj.mp4"

    # Simulate upload move
    local_vid = proj.path(proj.data.outputs["final"])
    assert local_vid.exists()
    shutil.copy2(str(local_vid), str(dest_video))
    os.unlink(str(local_vid))
    assert not local_vid.exists()

    # Update project source location as youtube_uploader does
    proj.data.outputs["external_archive_path"] = str(dest_video.resolve())
    proj.data.outputs["archived_to_external"] = True
    proj.data.outputs["final"] = str(dest_video.resolve())
    proj.save()

    with patch("core.project_manager.PROJECTS_DIR", projects_root), \
         patch("api_server.PROJECTS_DIR", projects_root), \
         patch("api_routes.media.PROJECTS_DIR", projects_root):

        # 1. Test project metadata API recognizes external file
        resp = client.get(f"/api/projects/{proj.id}")
        assert resp.status_code == 200
        data = resp.json()
        final_file = data.get("final_file")
        assert final_file is not None
        assert final_file["exists"] is True
        assert final_file["is_external"] is True
        assert Path(final_file["abs_path"]).resolve() == dest_video.resolve()

        # 2. Test /api/projects/{id}/video streams from external location
        resp_vid = client.get(f"/api/projects/{proj.id}/video")
        assert resp_vid.status_code == 200
        assert resp_vid.headers["content-type"] == "video/mp4"
        assert len(resp_vid.content) == len(b"dummy mp4 video data for test" * 100)

        # 3. Test /media/{id}/final/... fallback safely serves external video
        resp_media = client.get(f"/media/{proj.id}/final/{proj.id}.mp4")
        assert resp_media.status_code == 200
        assert resp_media.headers["content-type"] == "video/mp4"
        assert len(resp_media.content) == len(b"dummy mp4 video data for test" * 100)

        # 4. Test open folder points to external folder
        resp_folder = client.post(f"/api/projects/{proj.id}/open_folder")
        assert resp_folder.status_code == 200
        folder_info = resp_folder.json()
        assert folder_info["status"] == "ok"
        assert Path(folder_info["folder_path"]).resolve() == ext_dir.resolve()


def test_legacy_unmigrated_project_auto_resolution(test_project, tmp_path):
    """Verify that if a project has deleted local file but external_archive_path, it auto-resolves."""
    proj, projects_root = test_project
    client = TestClient(app)

    ext_dir = tmp_path / "external_drive_2"
    ext_dir.mkdir(parents=True, exist_ok=True)
    dest_video = ext_dir / f"{proj.id}_archived.mp4"

    # Move file to external and delete local, but DO NOT update proj.data.outputs["final"] yet
    local_vid = proj.path(proj.data.outputs["final"])
    shutil.copy2(str(local_vid), str(dest_video))
    os.unlink(str(local_vid))

    proj.data.outputs["external_archive_path"] = str(dest_video.resolve())
    proj.data.outputs["archived_to_external"] = True
    proj.data.outputs["final"] = f"final/{proj.id}.mp4"  # still pointing to deleted file
    proj.save()

    with patch("core.project_manager.PROJECTS_DIR", projects_root), \
         patch("api_server.PROJECTS_DIR", projects_root), \
         patch("api_routes.media.PROJECTS_DIR", projects_root):

        # Calling /api/projects/{id} should auto-repair source location to external file
        resp = client.get(f"/api/projects/{proj.id}")
        assert resp.status_code == 200
        data = resp.json()
        final_file = data.get("final_file")
        assert final_file is not None
        assert final_file["exists"] is True
        assert final_file["is_external"] is True
        assert Path(final_file["abs_path"]).resolve() == dest_video.resolve()

        # Streaming should work immediately
        resp_vid = client.get(f"/api/projects/{proj.id}/video")
        assert resp_vid.status_code == 200
        assert resp_vid.headers["content-type"] == "video/mp4"

        # Reload project and confirm outputs["final"] was updated
        proj_reloaded = Project(proj.id)
        assert Path(proj_reloaded.data.outputs["final"]).resolve() == dest_video.resolve()

