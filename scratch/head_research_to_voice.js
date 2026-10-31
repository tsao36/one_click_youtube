if (stKey === 'research') {
        stageModelSwitcherHtml = `
          <div style="display:flex; align-items:center; gap:6px; font-size:12px; background:var(--bg-sunken); padding:4px 8px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin:0;">Search:</label>
            <select style="padding:4px 8px; font-size:12px; border-radius:var(--radius-sm); background:var(--bg-canvas); color:var(--text-primary); border:1px solid var(--border-muted);" onchange="updateStudioStageModel('research', this.value)">
              <option value="gemini_search" ${currentSm === 'gemini_search' || !currentSm ? 'selected' : ''}>Cloud: Gemini Search Grounding</option>
              <option value="ollama" ${currentSm === 'ollama' ? 'selected' : ''}>Local: Ollama</option>
              <option value="none" ${currentSm === 'none' ? 'selected' : ''}>Disabled</option>
            </select>
          </div>
        `;
      