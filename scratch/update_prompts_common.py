from pathlib import Path

path = Path("agents/prompts_common.py")
content = path.read_text(encoding="utf-8")

old_text = '''- When writing in Chinese, strictly use Taiwan Traditional Chinese (台灣正體中文 / 國語詞彙) and standard Taiwan translations (台灣翻譯名稱), and never use Mainland Chinese buzzwords, tech jargon, or translation names: {", ".join(BANNED_MAINLAND_PHRASES)}.'''

new_text = '''- When writing in Chinese, strictly use Taiwan Traditional Chinese (台灣正體中文 / 國語詞彙) and standard Taiwan translations (台灣翻譯名稱), and never use Mainland Chinese buzzwords, tech jargon, or translation names: {", ".join(BANNED_MAINLAND_PHRASES)}.
- Strict factual grounding: Technical specifications, data rates, version features, and multipliers MUST strictly match the verified research dossier. Never guess or conflate version metrics (e.g. do not misattribute old speeds or bit rates to newer Bluetooth versions). Relative multipliers (e.g. "快上 X 倍") must mathematically agree with the referenced baseline number.'''

assert old_text in content, "old_text not found in agents/prompts_common.py"
content = content.replace(old_text, new_text)
path.write_text(content, encoding="utf-8")
print("Successfully updated agents/prompts_common.py!")
