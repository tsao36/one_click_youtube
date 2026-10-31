from pathlib import Path

path = Path('agents/prompt_generator.py')
text = path.read_text(encoding='utf-8')

# 1. Update compose() detection
old_compose_block = """    style_key = (style.get("key") or "").lower()
    is_cartoon_explainer = any(k in style_key for k in ["cartoon", "explainer", "doodle", "stickman", "minimalist_explainer"])

    if visual_type == "diagram":
        pieces.append("clean illustrated visual metaphor, simple shapes, no text")
    elif is_cartoon_explainer:"""

new_compose_block = """    style_key = (style.get("key") or "").lower()
    is_political_explainer = any(k in style_key for k in ["political_explainer", "taiwan_political", "see_world"])
    is_cartoon_explainer = (not is_political_explainer) and any(k in style_key for k in ["cartoon", "explainer", "doodle", "stickman", "minimalist_explainer"])

    if visual_type == "diagram":
        pieces.append("clean illustrated visual metaphor, simple shapes, no text")
    elif is_political_explainer:
        pieces.append("2D clean vector flat editorial illustration, Japanese and Taiwanese political caricature art style, solid pitch black background, clean bold outlines, flat solid color fills, dramatic stage lighting, high contrast")
    elif is_cartoon_explainer:"""

assert old_compose_block in text, "old_compose_block not found"
text = text.replace(old_compose_block, new_compose_block, 1)

# 2. Update generate_prompts() detection & directive
old_gen_block = """    style_key = (style.get("key") or "").lower()
    is_cartoon_explainer = any(k in style_key for k in ["cartoon", "explainer", "doodle", "stickman", "minimalist_explainer"])
    
    cartoon_directive = ""
    if is_cartoon_explainer:
        cartoon_directive = (
            "\\nSPECIAL STYLE DIRECTIVE (MINIMALIST EXPLAINER CARTOON / 商業大師 風格):\\n"
            "- Human Characters: ALWAYS describe all people as simple circular-head cartoon figures with two black dot eyes and a single line mouth, completely bald (no hair, no nose, no ears), wearing simplified solid-color suits/hoodies with cylindrical limbs and mitt hands.\\n"
            "- Visual Metaphors: Strongly translate abstract economic, social, or military terms into concrete, clever cartoon visual props and situations (e.g. padlocked items in fridges, characters dumping sacks of cash into trash, plunging red arrow graphs, oversized coins, contracts with red X marks).\\n"
            "- Color Accents: Include spot accents like vibrant red warning signs/graphs or golden yellow money stacks against clean, muted backgrounds.\\n"
        )"""

new_gen_block = """    style_key = (style.get("key") or "").lower()
    is_political_explainer = any(k in style_key for k in ["political_explainer", "taiwan_political", "see_world"])
    is_cartoon_explainer = (not is_political_explainer) and any(k in style_key for k in ["cartoon", "explainer", "doodle", "stickman", "minimalist_explainer"])
    
    cartoon_directive = ""
    if is_cartoon_explainer:
        cartoon_directive = (
            "\\nSPECIAL STYLE DIRECTIVE (MINIMALIST EXPLAINER CARTOON / 商業大師 風格):\\n"
            "- Human Characters: ALWAYS describe all people as simple circular-head cartoon figures with two black dot eyes and a single line mouth, completely bald (no hair, no nose, no ears), wearing simplified solid-color suits/hoodies with cylindrical limbs and mitt hands.\\n"
            "- Visual Metaphors: Strongly translate abstract economic, social, or military terms into concrete, clever cartoon visual props and situations (e.g. padlocked items in fridges, characters dumping sacks of cash into trash, plunging red arrow graphs, oversized coins, contracts with red X marks).\\n"
            "- Color Accents: Include spot accents like vibrant red warning signs/graphs or golden yellow money stacks against clean, muted backgrounds.\\n"
        )
    elif is_political_explainer:
        cartoon_directive = (
            "\\nSPECIAL STYLE DIRECTIVE (TAIWAN POLITICAL EXPLAINER / 一起看世界風格):\\n"
            "- Visual Art Style: 2D clean vector flat editorial illustration, Japanese and Taiwanese political caricature art style, bold clean black outlines, flat solid color fills, subtle cel-shading.\\n"
            "- Background: ALWAYS use a solid pitch black background ('isolated on solid black background, stage spotlight, theatrical dark backdrop') so characters and visual props pop out sharply with dramatic contrast.\\n"
            "- Recognizable Politician Caricatures: When real Taiwanese politicians or public figures appear, ALWAYS describe their iconic caricature traits in 'subject':\\n"
            "  * 盧秀燕 (Lu Shiow-yen): female Taiwanese mayor, short pixie haircut, light blue suit blazer, white open-collar shirt, expressive facial caricature.\\n"
            "  * 江啟臣 (Johnny Chiang): male Taiwanese politician, rectangular black-frame glasses, neat pompadour / side-part haircut, sharp navy suit, light blue necktie, small Taiwan flag lapel pin.\\n"
            "  * 何欣純 (Ho Hsin-chun): female Taiwanese legislator, signature bob haircut with gentle side bangs, confident warm smile, ivory/cream tailored blazer.\\n"
            "  * 顏寬恒 (Yen Kuan-heng): stout Taiwanese male local politician, short black crew cut, round face, dark polo or casual suit jacket.\\n"
            "  * 柯文哲 (Ko Wen-je): Taiwanese male politician, wire glasses, messy grey-flecked hair, short-sleeve button-down shirt with chest pens.\\n"
            "  * 賴清德 (Lai Ching-te): Taiwanese male president, signature middle-part haircut, sharp dark suit, purple necktie.\\n"
            "  * 韓國瑜 (Han Kuo-yu): bald Taiwanese male politician with glasses, rolled-up light blue dress shirt, animated gestures.\\n"
            "  * 蔡英文 (Tsai Ing-wen): female former president, rounded bob haircut, wire-rim glasses, minimalist dark blazer.\\n"
            "  * Party Elders (大老): senior elderly Taiwanese male politician, receding grey hair, formal charcoal suit.\\n"
            "- Concrete Visual Metaphors: ALWAYS translate abstract political jargon or metaphors directly into concrete physical objects and actions matching the spoken sentence:\\n"
            "  * '交棒' -> physically passing a shiny golden relay baton.\\n"
            "  * '保護傘' -> an elder holding an actual black umbrella over the politician.\\n"
            "  * '下戰帖/同意書' -> candidate signing debate agreements on a desk surrounded by press microphones.\\n"
            "  * '躲在背後' -> standing behind miniature city hall building.\\n"
            "  * '民調縮小/緊咬' -> side-by-side bar chart on document with blue and red bars nearly tied.\\n"
            "  * '派系分權/組織動員' -> elders sitting around a traditional tea table with zoning maps.\\n"
        )"""

assert old_gen_block in text, "old_gen_block not found"
text = text.replace(old_gen_block, new_gen_block, 1)

path.write_text(text, encoding='utf-8')
print("Successfully patched agents/prompt_generator.py!")
