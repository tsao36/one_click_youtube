import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from generators.avatar_generator import _build_looped_base_video, _generate_fal_latentsync
from rendering.ken_burns import render_talking_avatar_clip


def test_build_looped_base_video_forces_25fps(tmp_path):
    base_vid = tmp_path / "base.mp4"
    base_vid.write_bytes(b"dummy")
    out_vid = tmp_path / "out.mp4"

    ffmpeg_calls = []

    def mock_run_ffmpeg(cmd, **kwargs):
        ffmpeg_calls.append(cmd)

    with patch("generators.avatar_generator.run_ffmpeg", side_effect=mock_run_ffmpeg):
        _build_looped_base_video(base_vid, target_sec=5.0, out_path=out_vid, fps=25)

    assert len(ffmpeg_calls) == 2
    # Verify fps=25 is set in filter and -r 25 in ffmpeg commands
    assert "fps=25" in ffmpeg_calls[0][3]  # filter_complex
    assert "-r" in ffmpeg_calls[0] and ffmpeg_calls[0][ffmpeg_calls[0].index("-r") + 1] == "25"
    assert "-r" in ffmpeg_calls[1] and ffmpeg_calls[1][ffmpeg_calls[1].index("-r") + 1] == "25"


def test_generate_fal_latentsync_prepares_padded_audio(tmp_path):
    base_vid = tmp_path / "base.mp4"
    base_vid.write_bytes(b"dummy_vid")
    audio = tmp_path / "narration.wav"
    audio.write_bytes(b"dummy_audio")
    out_vid = tmp_path / "out.mp4"

    run_ffmpeg_cmds = []

    def mock_run_ffmpeg(cmd, **kwargs):
        run_ffmpeg_cmds.append(cmd)

    with patch("generators.avatar_generator.run_ffmpeg", side_effect=mock_run_ffmpeg):
        with patch("generators.avatar_generator.duration", side_effect=[10.0, 10.8, 10.8]):
            with patch("generators.avatar_generator._build_looped_base_video", return_value=tmp_path / "looped.mp4") as mock_build_loop:
                with patch("generators.avatar_generator.upload_file_to_fal", return_value="https://fal.media/file") as mock_upload:
                    with patch("generators.avatar_generator._fal_queue_run", return_value={"video": {"url": "https://fal.media/out.mp4"}}):
                        with patch("generators.avatar_generator._download_fal_video", return_value="https://fal.media/out.mp4"):
                            res = _generate_fal_latentsync(base_vid, audio, out_vid, fal_key="test_key")
                            assert res["provider"] == "fal-ai/latentsync"
                            # Verify audio prep ffmpeg was run with aresample=16000 and apad=pad_dur=0.8
                            assert any("aresample=16000" in str(cmd) and "apad=pad_dur=0.8" in str(cmd) for cmd in run_ffmpeg_cmds)
                            # Verify _build_looped_base_video was called with fps=25
                            assert mock_build_loop.call_args.kwargs.get("fps") == 25


def test_render_talking_avatar_clip_no_stream_loop(tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"dummy")
    out = tmp_path / "out.mp4"

    ffmpeg_calls = []

    def mock_run_ffmpeg(cmd, **kwargs):
        ffmpeg_calls.append(cmd)

    with patch("rendering.ken_burns.run_ffmpeg", side_effect=mock_run_ffmpeg):
        with patch("rendering.ken_burns.duration", return_value=10.0):
            render_talking_avatar_clip(
                src=src,
                output=out,
                seconds=12.0,
                lead_in=0.5,
                width=1920,
                height=1080,
                fps=30,
            )

    assert len(ffmpeg_calls) == 1
    cmd = ffmpeg_calls[0]
    # Verify -stream_loop is removed so avatar does not loop speech
    assert "-stream_loop" not in cmd
    # Verify tpad clone for lead_in and tail_hold
    vf_arg = cmd[cmd.index("-vf") + 1]
    assert "tpad=start_mode=clone:start_duration=0.5000" in vf_arg
    assert "tpad=stop_mode=clone" in vf_arg


def test_render_talking_avatar_clip_speech_duration_trimming(tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"dummy")
    out = tmp_path / "out.mp4"

    ffmpeg_calls = []

    def mock_run_ffmpeg(cmd, **kwargs):
        ffmpeg_calls.append(cmd)

    with patch("rendering.ken_burns.run_ffmpeg", side_effect=mock_run_ffmpeg):
        with patch("rendering.ken_burns.duration", return_value=10.0):
            render_talking_avatar_clip(
                src=src,
                output=out,
                seconds=12.0,
                lead_in=0.2,
                width=1920,
                height=1080,
                fps=30,
                speech_duration=6.0,
            )

    assert len(ffmpeg_calls) == 1
    cmd = ffmpeg_calls[0]
    # Input should be capped to speech_duration + 0.05 = 6.05s so mouth never moves after speech ends
    assert "-t" in cmd
    t_idx = cmd.index("-t")
    assert cmd[t_idx + 1] == "6.0500"
