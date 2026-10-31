from pathlib import Path

ui_p = Path("ui/index.html")
content = ui_p.read_text(encoding="utf-8")

# 1. Update Drama Stage 7 Scene card
old_drama_scene_card = """                  <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">

                    <span style="font-weight: 700; color: #93c5fd;">Scene #${s.scene_id}</span>

                    <span style="background: rgba(245, 158, 11, 0.18); border: 1px solid #f59e0b; color: #fbbf24; font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px;">🎭 ${escapeHtml(charName)}</span>

                    <span style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #6ee7b7; font-size: 11px; padding: 2px 6px; border-radius: 4px;">🎙️ ${escapeHtml(voiceProf)}</span>

                  </div>"""

new_drama_scene_card = """                  <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap;">
                    <span style="font-weight: 700; color: #93c5fd;">Scene #${s.scene_id}</span>
                    <span style="background: rgba(245, 158, 11, 0.18); border: 1px solid #f59e0b; color: #fbbf24; font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px;">🎭 ${escapeHtml(charName)}</span>
                    <span style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #6ee7b7; font-size: 11px; padding: 2px 6px; border-radius: 4px;">🎙️ ${escapeHtml(voiceProf)}</span>
                    ${s.action_gesture ? `<span style="background: rgba(139, 92, 246, 0.2); border: 1px solid #8b5cf6; color: #c4b5fd; font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px;">🎯 [gesture: ${escapeHtml(s.action_gesture)}]</span>` : ''}
                  </div>"""

# 2. Add video generation action buttons to Stage 7
old_drama_meta_line = """                  <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">

                    時長: <b>${s.estimated_duration || 5}s</b> | 景別: <b>${s.framing || '中景'}</b> | 模型: <b>${(s.animation && s.animation.meta && s.animation.meta.provider) || 'Hedra Character-2'}</b>

                  </div>"""

new_drama_meta_line = """                  <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
                    時長: <b>${s.estimated_duration || 5}s</b> | 景別: <b>${s.framing || '中景'}</b> | 模型: <b>${(s.animation && s.animation.meta && s.animation.meta.provider) || 'MiniMax Video-01'}</b>
                  </div>
                  <div style="display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap;">
                    <button class="btn-sec" style="font-size: 11px; padding: 4px 10px; background: rgba(56, 189, 248, 0.15); border: 1px solid #38bdf8; color: #38bdf8; font-weight: 700; border-radius: 4px; cursor: pointer;" onclick="triggerSceneVideoGeneration(${s.scene_id}, 'minimax')">
                      ⚡ MiniMax Video-01 動態生成
                    </button>
                    <button class="btn-sec" style="font-size: 11px; padding: 4px 10px; background: rgba(245, 158, 11, 0.15); border: 1px solid #f59e0b; color: #fbbf24; font-weight: 700; border-radius: 4px; cursor: pointer;" onclick="triggerSceneVideoGeneration(${s.scene_id}, 'hedra')">
                      👄 Hedra 對嘴生成
                    </button>
                  </div>"""

# 3. Add JS function triggerSceneVideoGeneration
old_js_anchor = "async function previewStandaloneRemotionClip() {"
new_js_fn = """    async function triggerSceneVideoGeneration(sceneId, engine) {
      if (!currentProjectId) return alert("請先選取或建立專案。");
      const engineName = (engine === 'minimax') ? 'MiniMax Video-01' : 'Hedra';
      if (!confirm(`確定為 Scene #${sceneId} 啟動 [${engineName}] 動態算繪？`)) return;
      try {
        const res = await fetch(`/api/projects/${currentProjectId}/scenes/${sceneId}/generate_video`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ engine: engine })
        });
        const d = await res.json();
        if (!res.ok) throw new Error(d.detail || '生成失敗');
        alert(`✓ Scene #${sceneId} 已成功由 [${engineName}] 生成影片！`);
        if (typeof activeDramaStudioStage !== 'undefined' && activeDramaStudioStage === 'animation') {
          const sData = await (await fetch(`/api/projects/${currentProjectId}/stages/animation`)).json();
          renderStudioWorkspace('animation', sData, studioProject, 'drama');
        } else {
          location.reload();
        }
      } catch (e) {
        alert("❌ 影片生成失敗：" + e.message);
      }
    }

    async function previewStandaloneRemotionClip() {"""

pairs = [
    ("Drama scene card gesture badge", old_drama_scene_card, new_drama_scene_card),
    ("Drama scene meta & action buttons", old_drama_meta_line, new_drama_meta_line),
    ("JS triggerSceneVideoGeneration", old_js_anchor, new_js_fn)
]

for name, old_s, new_s in pairs:
    if old_s in content:
        content = content.replace(old_s, new_s, 1)
        print(f"OK: {name}")
    else:
        c_norm = content.replace("\r\n", "\n")
        old_norm = old_s.replace("\r\n", "\n")
        if old_norm in c_norm:
            c_norm = c_norm.replace(old_norm, new_s.replace("\r\n", "\n"), 1)
            content = c_norm.replace("\n", "\r\n")
            print(f"OK (normalized): {name}")
        else:
            print(f"FAILED: {name}")

ui_p.write_text(content, encoding="utf-8")
print("Done updating ui/index.html")
