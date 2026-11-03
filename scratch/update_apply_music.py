from pathlib import Path

html_file = Path("ui/index.html")
text = html_file.read_text(encoding="utf-8")

old_code = """    async function applyMusicToActiveProject(filename) {
      if (!currentProjectId) {
        alert("No project currently selected.");
        return;
      }
      const sel = document.getElementById('project-music-track-select');
      if (sel) sel.value = filename;
      await saveActiveProjectMusic();
      alert(`Applied "${filename}" to project ${currentProjectId}. You can click "Re-Render 1080p Video" to compose the mix with this music.`);
    }"""

new_code = """    async function applyMusicToActiveProject(filename) {
      if (typeof studioTargetMovementIdx === 'number' && studioTargetMovementIdx !== null) {
        const segIdx = studioTargetMovementIdx;
        studioTargetMovementIdx = null;
        if (studioStageData && studioStageData.music_plan && studioStageData.music_plan[segIdx]) {
          const seg = studioStageData.music_plan[segIdx];
          const matched = cachedMusicTracks.find(t => t.filename === filename);
          seg.track = filename;
          seg.name = filename.split(/[\\/\\\\]/).pop();
          seg.audio_url = matched ? matched.url : `/api/music/audio/${filename}`;
          if (matched && matched.category) seg.category = matched.category;
          alert(`已成功將古典名曲「${seg.name}」指派至樂章 Movement ${segIdx + 1}！正在返回 Stage Studio...`);
          switchTab('creator');
          openStageInspector('music');
          return;
        }
      }
      if (!currentProjectId) {
        alert("No project currently selected.");
        return;
      }
      const sel = document.getElementById('project-music-track-select');
      if (sel) sel.value = filename;
      await saveActiveProjectMusic();
      alert(`Applied "${filename}" to project ${currentProjectId}. You can click "Re-Render 1080p Video" to compose the mix with this music.`);
    }"""

if old_code in text:
    text = text.replace(old_code, new_code, 1)
    html_file.write_text(text, encoding="utf-8")
    print("SUCCESS: applyMusicToActiveProject updated!")
else:
    print("WARNING: old_code not found in index.html")
