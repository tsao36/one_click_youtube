from pathlib import Path

path = Path('config/settings.yaml')
text = path.read_text(encoding='utf-8')

target = 'remotion:'
assert target in text, 'remotion: not found'

addition = '''  taiwan_political_explainer:
    label: "Taiwan Political Explainer (一起看世界 / 台灣政論插畫風)"
    style: "2D clean vector flat editorial illustration, Japanese and Taiwanese political caricature art style, bold clean black outlines, flat solid color fills, subtle cel-shading, distinct caricature portraits of real Taiwanese political figures with recognizable iconic facial features, hairstyles, and formal business attire, satirical and concrete visual metaphors directly visualizing the spoken narration, dramatic high-contrast pure solid black background, 8k resolution editorial art"
    lighting: "high-contrast dramatic stage lighting, crisp highlights, isolated subjects against pitch black background"
    lens: "flat 2D front-on or three-quarter editorial graphic composition, clean theatrical framing"
    mood: "satirical, insightful, compelling, political explainer, sharp, analytical"
    negative: "photorealistic, 3D, CGI, realistic skin pores, photorealistic human photo, messy cluttered background, realistic background, blurry, lowres, distorted anatomy, extra fingers, watermark, logo, text"
'''

new_text = text.replace(target, addition + target, 1)
path.write_text(new_text, encoding='utf-8')
print('Successfully patched settings.yaml!')
