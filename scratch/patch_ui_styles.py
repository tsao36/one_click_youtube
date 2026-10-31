from pathlib import Path

path = Path('ui/index.html')
text = path.read_text(encoding='utf-8')

# 1. Update first dropdown around line 1587
s1 = '<option value="minimalist_explainer_cartoon">'
r1 = '<option value="taiwan_political_explainer">Taiwan Political Explainer (一起看世界 / 台灣政論插畫風)</option>\n            <option value="minimalist_explainer_cartoon">'
assert s1 in text, "s1 not found"

# 2. Update array around line 9339
s2 = "{ value: 'minimalist_explainer_cartoon', localLabel:"
r2 = "{ value: 'taiwan_political_explainer', localLabel: 'Taiwan Political Explainer (一起看世界 / 台灣政論插畫風)', cloudLabel: 'Taiwan Political Explainer (一起看世界風)' },\n      { value: 'minimalist_explainer_cartoon', localLabel:"
assert s2 in text, "s2 not found"

# 3. Update third dropdown around line 12693
# Note: s1 will replace both occurrences of s1 in dropdowns!
text = text.replace(s1, r1)
text = text.replace(s2, r2)

path.write_text(text, encoding='utf-8')
print("Successfully patched ui/index.html with taiwan_political_explainer!")
