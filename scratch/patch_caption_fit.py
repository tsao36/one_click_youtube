p = 'generators/subtitle_generator.py'
t = open(p, encoding='utf-8').read()

helper = '''def _side_margin_ratio(width: int, height: int) -> float:
    return 0.07 if height > width else 0.04


def caption_chars_per_line(width: int, height: int, style: str = "youtube_standard") -> int:
    """Max CJK characters per caption line that fit the frame at the style font size (scaled by short edge)."""
    style_vals = STYLES.get(style, STYLES["youtube_standard"])
    scale = min(width, height) / 1080
    font_px = max(1.0, style_vals[1] * scale)
    usable = width * (1 - 2 * _side_margin_ratio(width, height))
    return max(8, int(usable / (font_px * 1.12)))


def build_cues('''
assert 'def build_cues(' in t
t = t.replace('def build_cues(', helper, 1)

old_sig = 'def build_cues(scene_texts: list[tuple[str, Slot]], max_chars_per_line: int = 42, max_lines: int = 2) -> list[Cue]:\n    cues: list[Cue] = []'
assert old_sig in t
t = t.replace(old_sig, '''def build_cues(scene_texts: list[tuple[str, Slot]], max_chars_per_line: int = 42, max_lines: int = 2,
               frame_width: int | None = None, frame_height: int | None = None,
               style: str = "youtube_standard") -> list[Cue]:
    cues: list[Cue] = []
    fit_cjk = caption_chars_per_line(frame_width, frame_height, style) if (frame_width and frame_height) else None''', 1)

old = 'cjk_max = min(max_chars_per_line, 22) if has_cjk else max_chars_per_line'
assert old in t
t = t.replace(old, old + '''
        if fit_cjk:
            cjk_max = min(cjk_max, fit_cjk)
            if not has_cjk:
                max_chars_per_line = min(max_chars_per_line, int(fit_cjk * 1.7))''', 1)

old = '    scale = height / 1080\n    header'
assert old in t
t = t.replace(old, '''    scale = min(width, height) / 1080
    side_m = round(width * _side_margin_ratio(width, height))
    if height > width and align not in (5, 8):
        # vertical frames: keep captions above platform UI / lower third
        mv = max(mv, round(height * 0.12 / scale))
    header''', 1)

old = '{bs},{outline},{shadow},{align},80,80,{round(mv * scale)},1'
assert old in t
t = t.replace(old, '{bs},{outline},{shadow},{align},{side_m},{side_m},{round(mv * scale)},1', 1)
open(p, 'w', encoding='utf-8').write(t)

p = 'core/drama_pipeline.py'
t = open(p, encoding='utf-8').read()
old = 'max_lines=int(sub_cfg.get("max_lines", 2))\r\n\r\n\r\n\r\n        )'
assert old in t
t = t.replace(old, 'max_lines=int(sub_cfg.get("max_lines", 2)),\r\n            frame_width=int(cfg["video"]["width"]),\r\n            frame_height=int(cfg["video"]["height"]),\r\n            style=sub_cfg.get("style", "youtube_standard"),\r\n        )', 1)
open(p, 'w', encoding='utf-8', newline='').write(t)
print('ok')
