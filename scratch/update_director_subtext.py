from pathlib import Path

p = Path("agents/motion_graphics_director.py")
content = p.read_text(encoding="utf-8")

old_code_1 = '''                        props={
                            "badge": s.section or "KEY TAKEAWAY",
                            "text": narr[:120] if len(narr) <= 120 else narr[:117] + "...",
                            "highlightPhrase": first_sentence[:28],
                            "subtext": s.section or "MODERN TECH EXPLAINER",
                            "accentColor": "#38BDF8",
                        },'''

new_code_1 = '''                        props={
                            "badge": "CONCLUSION" if (s.section or "").lower() in ("conclusion", "總結", "結語") else (s.section or "KEY TAKEAWAY"),
                            "text": narr[:120] if len(narr) <= 120 else narr[:117] + "...",
                            "highlightPhrase": first_sentence[:28],
                            "subtext": "結論" if (s.section or "").lower() in ("conclusion", "總結", "結語") else "重點整理",
                            "accentColor": "#38BDF8",
                        },'''

old_code_2 = '''                        props={
                            "badge": s.section or "KEY TAKEAWAY",
                            "text": narr[:120] if len(narr) <= 120 else narr[:117] + "...",
                            "highlightPhrase": first_sent[:28],
                            "subtext": s.section or "MODERN TECH EXPLAINER",
                            "accentColor": "#38BDF8",
                        },'''

new_code_2 = '''                        props={
                            "badge": "CONCLUSION" if (s.section or "").lower() in ("conclusion", "總結", "結語") else (s.section or "KEY TAKEAWAY"),
                            "text": narr[:120] if len(narr) <= 120 else narr[:117] + "...",
                            "highlightPhrase": first_sent[:28],
                            "subtext": "結論" if (s.section or "").lower() in ("conclusion", "總結", "結語") else "重點整理",
                            "accentColor": "#38BDF8",
                        },'''

assert old_code_1 in content, "old_code_1 not found"
assert old_code_2 in content, "old_code_2 not found"

content = content.replace(old_code_1, new_code_1).replace(old_code_2, new_code_2)
p.write_text(content, encoding="utf-8")
print("Successfully updated agents/motion_graphics_director.py!")
