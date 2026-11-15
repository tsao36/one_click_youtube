"""Tests for generators.youtube_music module."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from generators.youtube_music import (
    is_valid_youtube_url,
    sanitize_filename,
    find_js_runtime_args,
    find_yt_dlp_binary,
    find_ffmpeg_binary,
    ensure_media_tools_in_path,
    get_youtube_video_info,
    download_and_convert_youtube_track,
)


def test_is_valid_youtube_url():
    valid = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=5qap5aO4i9A&list=RD5qap5aO4i9A",
    ]
    for u in valid:
        assert is_valid_youtube_url(u) is True, f"Expected {u} to be valid"

    invalid = [
        "",
        "   ",
        "https://vimeo.com/123456",
        "https://google.com",
        "invalid_id",
    ]
    for u in invalid:
        assert is_valid_youtube_url(u) is False, f"Expected {u} to be invalid"


def test_sanitize_filename():
    assert sanitize_filename("A/B\\C:D*E?F\"G<H>I|J") == "A_B_C_D_E_F_G_H_I_J"
    assert sanitize_filename("   Hello    World   ") == "Hello_World"
    assert sanitize_filename("放鬆音樂 - 深度思考") == "放鬆音樂_-_深度思考"
    assert sanitize_filename("") == "youtube_ambient_track"


def test_find_js_runtime_args():
    args = find_js_runtime_args()
    # On this machine Node.js is installed
    assert isinstance(args, list)
    assert len(args) == 2
    assert args[0] == "--js-runtimes"
    assert "node" in args[1]


def test_media_tools_discovery():
    tools = ensure_media_tools_in_path()
    assert "yt_dlp" in tools
    assert "ffmpeg" in tools
    assert "ffmpeg_dir" in tools
    assert Path(tools["yt_dlp"]).is_file()
    assert Path(tools["ffmpeg"]).is_file()


def test_get_youtube_video_info_fast_print():
    # Test with mock subprocess
    mock_proc = MagicMock()
    mock_proc.stdout = "Calm Rain Sound###180.5###RelaxMusic"
    mock_proc.returncode = 0

    with patch("subprocess.run", return_value=mock_proc):
        info = get_youtube_video_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert info["title"] == "Calm Rain Sound"
        assert info["duration"] == 180.5
        assert info["uploader"] == "RelaxMusic"
