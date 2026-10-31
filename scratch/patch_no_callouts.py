with open('core/pipeline.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('callout_text=f"{spk} | {full_narration[:18]}" if is_climax else None', 'callout_text=None')
text = text.replace('callout_type="drama_subtitle" if is_climax else None', 'callout_type=None')

with open('core/pipeline.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Successfully replaced callout_text and callout_type with None!')
