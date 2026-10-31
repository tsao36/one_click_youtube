with open('ui/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start_marker = 'function onDramaCharImageFilePicked(idx, input) {'
end_marker = 'async function generateAiPortraitForDramaChar(idx) {'

start_pos = text.find(start_marker)
end_pos = text.find(end_marker)

if start_pos != -1 and end_pos != -1:
    repl = '''async function onDramaCharImageFilePicked(idx, input) {
      if (!input.files || !input.files[0]) return;
      const file = input.files[0];
      const c = currentProjectDramaCharacters[idx];
      if (!c) return;

      const reader = new FileReader();
      reader.onload = async function(e) {
        c.image_data_uri = e.target.result;
        c.has_custom_image = true;
        renderDramaCharactersEditor();

        // Immediately persist to backend character storage
        try {
          const charId = (c.id && c.id !== 'None') ? c.id : ('char_' + (idx + 1) + '_' + Date.now());
          c.id = charId;
          const fd = new FormData();
          fd.append('id', charId);
          fd.append('name', c.name || `角色${idx + 1}`);
          fd.append('role', c.role || '主要角色');
          fd.append('gender', c.gender || 'female');
          fd.append('age', c.age || 28);
          fd.append('appearance', c.appearance || '');
          fd.append('voice_profile', c.voice_profile || 'ichiehchieh');
          fd.append('file', file);

          const upRes = await fetch('/api/characters', { method: 'POST', body: fd });
          if (upRes.ok) {
            c.image_url = `/api/characters/image/${charId}?t=${Date.now()}`;
            if (typeof showToast === 'function') showToast(`已成功保存 ${c.name} 的專屬定妝照！`);
          }
        } catch (err) {
          console.warn('Auto save portrait note:', err);
        }
      };
      reader.readAsDataURL(file);
    }

    '''
    new_text = text[:start_pos] + repl + text[end_pos:]
    with open('ui/index.html', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Successfully patched onDramaCharImageFilePicked in ui/index.html!')
else:
    print('Markers not found!')
