import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generators.subtitle_generator import Cue, write_ass
from rendering.ffmpeg_utils import ffmpeg_bin, run_ffmpeg

def main():
    proj_dir = Path("projects/project_16")
    image_path = proj_dir / "images" / "scene_001.png"
    audio_path = proj_dir / "audio" / "scene_001.wav"
    music_path = Path("data/music")
    # Find any music file in data/music
    music_files = list(music_path.glob("*.mp3")) + list(music_path.glob("*.wav"))
    bgm_path = music_files[0] if music_files else None

    out_dir = proj_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    ui_dir = Path("ui")

    narration_text = "走在剛鋪好的平整柏油路上，你可能很難想像，"
    cue_start = 0.25
    cue_end = 3.92
    cues = [Cue(cue_start, cue_end, narration_text)]

    callouts = [{
        "style": "FoxCalloutCard",
        "start": 0.50,
        "end": 3.86,
        "banner_style": "corner_metric",
        "tag": "現代基礎設施",
        "title": "剛性瀝青路面",
        "subtitle": "現代文明運轉的黑色動脈",
    }]

    fonts_dir = (Path("data/fonts")).resolve()
    f_dir_esc = str(fonts_dir).replace("\\", "/").replace(":", "\\:")

    # Generate ASS for 55pt (+30%)
    ass_55 = out_dir / "pilot_55pt.ass"
    write_ass(
        cues,
        ass_55,
        style="youtube_standard",
        width=1920,
        height=1080,
        callouts=callouts,
        font_override="Microsoft JhengHei UI",
        font_size=55,
        callout_style="corner_metric",
    )

    # Generate ASS for 42pt (Baseline)
    ass_42 = out_dir / "pilot_42pt.ass"
    write_ass(
        cues,
        ass_42,
        style="youtube_standard",
        width=1920,
        height=1080,
        callouts=callouts,
        font_override="Microsoft JhengHei UI",
        font_size=42,
        callout_style="corner_metric",
    )

    total_duration = 4.0

    for size_label, ass_file in [("55pt", ass_55), ("42pt", ass_42)]:
        out_mp4 = out_dir / f"pilot_scene_{size_label}.mp4"
        ass_esc = str(ass_file.resolve()).replace("\\", "/").replace(":", "\\:")
        
        # Build audio filter with narration + ducked music
        # Video: 1080p with gentle Ken Burns zoom 1.04 to 1.08
        vf = (
            f"scale=1920:1080:force_original_aspect_ratio=increase,"
            f"crop=1920:1080,"
            f"zoompan=z='min(zoom+0.0006,1.06)':d=120:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30,"
            f"subtitles='{ass_esc}':fontsdir='{f_dir_esc}'"
        )

        args = [
            "-y",
            "-loop", "1", "-i", str(image_path.resolve()),
            "-i", str(audio_path.resolve()),
        ]

        if bgm_path:
            args += ["-i", str(bgm_path.resolve())]
            filter_complex = (
                f"[0:v]{vf}[v];"
                f"[1:a]adelay=250|250,volume=1.0[a_narr];"
                f"[2:a]volume=0.18,afade=t=in:ss=0:d=1.0,afade=t=out:st=3.2:d=0.8[a_bgm];"
                f"[a_narr][a_bgm]amix=inputs=2:duration=first:dropout_transition=2[a]"
            )
            args += [
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", "[a]",
            ]
        else:
            filter_complex = (
                f"[0:v]{vf}[v];"
                f"[1:a]adelay=250|250,volume=1.0[a]"
            )
            args += [
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", "[a]",
            ]

        args += [
            "-t", f"{total_duration:.2f}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(out_mp4.resolve()),
        ]

        print(f"Rendering {size_label} pilot scene...")
        run_ffmpeg(args)
        print(f"Generated {out_mp4} ({out_mp4.stat().st_size} bytes)")

        # Copy to ui/ directory
        ui_mp4 = ui_dir / f"pilot_scene_{size_label}.mp4"
        shutil.copy2(out_mp4, ui_mp4)

        # Extract snapshot at t=2.0s for quick visual inspection
        frame_png = ui_dir / f"pilot_scene_{size_label}_frame.png"
        snap_args = [
            "-y",
            "-ss", "00:00:02.000",
            "-i", str(out_mp4.resolve()),
            "-vframes", "1",
            "-q:v", "2",
            str(frame_png.resolve())
        ]
        run_ffmpeg(snap_args)
        print(f"Extracted snapshot {frame_png}")

    print("Pilot generation complete!")

if __name__ == "__main__":
    main()
