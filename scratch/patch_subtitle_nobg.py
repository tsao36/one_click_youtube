# encoding: utf-8
with open("generators/subtitle_generator.py", "rb") as f:
    text = f.read().decode("utf-8")

text = text.replace(
    'f"{\\\\fs{fs_tag}\\\\c&H00FFE500&\\\\3c&H00140A04&\\\\bord2.5\\\\shad3\\\\b1}◆  {clean_tag}  ◆",',
    'f"{{\\\\fs{fs_tag}\\\\c&H00FFE500&\\\\3c&H00140A04&\\\\bord2.5\\\\shad3\\\\b1}}◆  {clean_tag}  ◆",'
)

text = text.replace(
    'f"{\\\\fs{fs_title}\\\\c{title_color}\\\\3c&H00100804&\\\\bord3.5\\\\shad4\\\\b1}{title}",',
    'f"{{\\\\fs{fs_title}\\\\c{title_color}\\\\3c&H00100804&\\\\bord3.5\\\\shad4\\\\b1}}{title}",'
)

text = text.replace(
    'card_lines.append(f"{\\\\fs{fs_sub}\\\\c&H00F2E6D8&\\\\3c&H00100804&\\\\bord2.4\\\\shad2.5\\\\b0}{subtitle}")',
    'card_lines.append(f"{{\\\\fs{fs_sub}\\\\c&H00F2E6D8&\\\\3c&H00100804&\\\\bord2.4\\\\shad2.5\\\\b0}}{subtitle}")'
)

# Also regex in line 318
text = text.replace(
    'has_metric = bool(re.search(r"(\\\\d|[一二三四五六七八九十百千萬兩]+\\\\s*[尊枚把件座名位人戶個條份公釐公厘毫米公分公尺公里倍成%])", title))',
    'has_metric = bool(re.search(r"(\\d|[一二三四五六七八九十百千萬兩]+\\s*[尊枚把件座名位人戶個條份公釐公厘毫米公分公尺公里倍成%])", title))'
)

with open("generators/subtitle_generator.py", "wb") as f:
    f.write(text.encode("utf-8"))

print("Fixed card_lines escaping!")
