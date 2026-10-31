with open('ui/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''        if (formula.default_characters && formula.default_characters.length > 0) {
          currentProjectDramaCharacters = JSON.parse(JSON.stringify(formula.default_characters));
        }'''

repl = '''        const hasCustomChars = (currentProjectDramaCharacters || []).some(ch => ch.image_data_uri || ch.has_custom_image || (ch.image_url && !ch.image_url.includes('manager_wang') && !ch.image_url.includes('shen_director') && !ch.image_url.includes('chairman_chen')));
        if (!hasCustomChars && formula.default_characters && formula.default_characters.length > 0) {
          currentProjectDramaCharacters = JSON.parse(JSON.stringify(formula.default_characters));
        }'''

if target in text:
    text = text.replace(target, repl, 1)
    with open('ui/index.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched onDramaFormulaSelectChange!')
else:
    print('Target not found!')
