with open('rendering/ffmpeg_renderer.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """def build_narration(project: Project, scenes: list[Scene], slots: list[Slot], out: Path, cancel: Callable[[], bool] | None = None) -> None:
    sr = int(project.settings["voice"].get("sample_rate", 48000))"""

replacement = """def build_narration(project: Project, scenes: list[Scene], slots: list[Slot], out: Path, cancel: Callable[[], bool] | None = None) -> None:
    settings = project.settings
    is_drama = bool(
        settings.get("project_mode") == "short_drama"
        or (hasattr(project, "data") and project.data and project.data.settings.get("project_mode") == "short_drama")
    )
    avatar_allowed = project.is_avatar_enabled() if hasattr(project, "is_avatar_enabled") else bool(
        settings.get("avatar_enabled", True) and settings.get("presenter_placement") not in ("none", "off", "disabled", False)
    )
    sr = int(project.settings["voice"].get("sample_rate", 48000))"""

target_norm = target.replace('\r\n', '\n')
content_norm = content.replace('\r\n', '\n')

assert target_norm in content_norm, 'Target not found in content!'
content_norm = content_norm.replace(target_norm, replacement.replace('\r\n', '\n'), 1)

with open('rendering/ffmpeg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(content_norm)

print('Successfully patched build_narration in ffmpeg_renderer.py')
