from pathlib import Path

from PIL import Image

from rendering import ken_burns


def test_phase_turn_card_uses_dimmed_background_and_centered_neutral_text(tmp_path, monkeypatch):
    background = tmp_path / "background.png"
    output = tmp_path / "phase-turn.mp4"
    Image.new("RGB", (320, 180), (180, 140, 90)).save(background)

    calls = []
    monkeypatch.setattr(ken_burns, "run_ffmpeg", lambda args: calls.append(args))

    ken_burns.render_phase_turn_card(
        "盟友承諾的真相",
        output,
        seconds=3.0,
        width=1920,
        height=1080,
        fps=30,
        background=background,
    )

    assert len(calls) == 1
    args = calls[0]
    vf = args[args.index("-vf") + 1]
    assert str(background) in args
    assert "eq=brightness=-0.14:saturation=0.82:contrast=0.96" in vf
    assert "x=(w-text_w)/2:y=(h-text_h)/2" in vf
    assert "fontsize=120" in vf
    assert "box=1:boxcolor=black@0.48" in vf


def test_phase_turn_card_falls_back_to_neutral_solid_background(tmp_path, monkeypatch):
    output = tmp_path / "phase-turn.mp4"
    calls = []
    monkeypatch.setattr(ken_burns, "run_ffmpeg", lambda args: calls.append(args))

    ken_burns.render_phase_turn_card(
        "下一章",
        output,
        seconds=3.0,
        width=1280,
        height=720,
        fps=30,
    )

    args = calls[0]
    assert "color=c=0x242424:s=1280x720:r=30" in args
