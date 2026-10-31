    function renderStudioWorkspace(stKey, data, project) {
      const wsEl = document.getElementById('studio-stage-workspace');
      if (!wsEl) return;

      const meta = STAGE_META[stKey] || {};
      const st = project && project.stages ? project.stages[stKey] : null;
      const isProjectActive = project && (project.state === 'running');
      const isThisStageTracked = (typeof studioStageRunning !== 'undefined' && studioStageRunning === stKey);
      const isRunning = st && (st.status === 'RUNNING') && (isProjectActive || isThisStageTracked);
      const isDone = st && st.status === 'COMPLETED';

      // Stage Model Selector for this workspace
      const currentSm = (project && project.settings && project.settings.stage_models) ? project.settings.stage_models[stKey] : null;
      let stageModelSwitcherHtml = '';
      if (stKey === 'images') {
        stageModelSwitcherHtml = `
          <div style="display:flex; align-items:center; gap:6px; font-size:12px; background:var(--bg-sunken); padding:4px 8px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin:0;">Model:</label>
            <select style="padding:4px 8px; font-size:12px; border-radius:var(--radius-sm); background:var(--bg-canvas); color:var(--text-primary); border:1px solid var(--border-muted);" onchange="updateStudioStageModel('images', this.value)">
              <option value="comfyui" ${currentSm === 'comfyui' || !currentSm ? 'selected' : ''}>Local: ComfyUI (DirectML)</option>
              <option value="dalle3" ${currentSm === 'dalle3' ? 'selected' : ''}>Cloud: OpenAI DALL-E 3</option>
              <option value="imagen3" ${currentSm === 'imagen3' ? 'selected' : ''}>Cloud: Google Imagen 3</option>
            </select>
          </div>
        `;
      } else if (stKey === 'script' || stKey === 'scenes' || stKey === 'prompts') {
        stageModelSwitcherHtml = `
          <div style="display:flex; align-items:center; gap:6px; font-size:12px; background:var(--bg-sunken); padding:4px 8px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin:0;">Model:</label>
            <select style="padding:4px 8px; font-size:12px; border-radius:var(--radius-sm); background:var(--bg-canvas); color:var(--text-primary); border:1px solid var(--border-muted);" onchange="updateStudioStageModel('${stKey}', this.value)">
              <option value="ollama" ${currentSm === 'ollama' || !currentSm ? 'selected' : ''}>Local: Ollama (qwen3:8b)</option>
              <option value="gemini" ${currentSm === 'gemini' ? 'selected' : ''}>Cloud: Gemini 3.8 Flash</option>
              <option value="openai_compat" ${currentSm === 'openai_compat' ? 'selected' : ''}>Cloud: GPT-4o-mini</option>
            </select>
          </div>
        `;
      } else if (stKey === 'research') {
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
      } else if (stKey === 'animation') {
        stageModelSwitcherHtml = `
          <div style="display:flex; align-items:center; gap:6px; font-size:12px; background:var(--bg-sunken); padding:4px 8px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin:0;">Engine:</label>
            <select style="padding:4px 8px; font-size:12px; border-radius:var(--radius-sm); background:var(--bg-canvas); color:var(--text-primary); border:1px solid var(--border-muted);" onchange="updateStudioStageModel('animation', this.value)">
              <option value="kenburns" ${currentSm === 'kenburns' || !currentSm ? 'selected' : ''}>Local: Ken Burns 2.5D Motion</option>
              <option value="comfyui_video" ${currentSm === 'comfyui_video' ? 'selected' : ''}>Local: ComfyUI Video</option>
              <option value="veo" ${currentSm === 'veo' ? 'selected' : ''}>Cloud: Google Veo</option>
              <option value="kling" ${currentSm === 'kling' ? 'selected' : ''}>Cloud: Kling Video AI</option>
              <option value="runway" ${currentSm === 'runway' ? 'selected' : ''}>Cloud: Runway Gen-3</option>
            </select>
          </div>
        `;
      } else if (stKey === 'render') {
        stageModelSwitcherHtml = `
          <div style="display:flex; align-items:center; gap:6px; font-size:12px; background:var(--bg-sunken); padding:4px 8px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin:0;">Encoder:</label>
            <select style="padding:4px 8px; font-size:12px; border-radius:var(--radius-sm); background:var(--bg-canvas); color:var(--text-primary); border:1px solid var(--border-muted);" onchange="updateStudioStageModel('render', this.value)">
              <option value="h264_amf" ${currentSm === 'h264_amf' || !currentSm ? 'selected' : ''}>Local GPU: AMD AMF Hardware</option>
              <option value="libx264" ${currentSm === 'libx264' ? 'selected' : ''}>Local CPU: FFmpeg libx264</option>
            </select>
          </div>
        `;
      }

      // 1. Header Bar
      let headerHtml = `
        <div style="background: linear-gradient(135deg, #0b1526 0%, #060a12 100%); border-bottom: 1px solid var(--card-border); padding: 18px 20px; border-radius: 8px 8px 0 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
          <div>
            <div style="display: flex; align-items: center; gap: 10px;">
              <span style="font-size: 26px;">${meta.icon}</span>
              <h2 style="font-size: 18px; font-weight: 800; color: #fff; margin: 0;">${meta.title}</h2>
              <span style="font-size: 12px; padding: 3px 8px; border-radius: 12px; font-weight: 700; ${isDone ? 'background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981;' : (isRunning ? 'background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid #3b82f6;' : 'background: #1e293b; color: #94a3b8;')}">
                ${st ? st.status : 'PENDING'}
              </span>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
              ${meta.desc}
            </div>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
            ${stageModelSwitcherHtml}
            ${(stKey === 'render' && isRunning) ? `
              <button class="btn-sec btn-danger" style="padding: 8px 14px; font-size: 12px; font-weight: 700;" onclick="stopRenderingVideo()">
                🛑 Stop Rendering Video
              </button>
            ` : ''}
            <button id="studio-run-btn" class="btn-primary" style="padding: 8px 14px; font-size: 12px; background: #1e3a8a; border: 1px solid #3b82f6;" onclick="runStudioStageOnly('${stKey}')" ${isRunning ? 'disabled' : ''}>
              ${isRunning ? `<span class="spinner-inline" style="width:12px; height:12px; margin-right:6px;"></span> Generating ${meta.name}...` : (meta.runBtn || '▶ Run This Stage Only')}
            </button>
            <button class="btn-sec" style="padding: 8px 14px; font-size: 12px;" onclick="saveStudioStage('${stKey}')">
              💾 Save Changes
            </button>
            <button class="btn-primary" style="padding: 8px 16px; font-size: 12px; font-weight: 700; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);" onclick="assembleAllStagesNow()">
              🔗 String All Stages Together
            </button>
          </div>
        </div>
      `;

      // 1.5 Version Cycling Toolbar
      let versionBarHtml = '';
      const vData = data.versioning || {};
      const versList = vData.versions || [];
      const totalV = vData.total_versions || versList.length || 0;
      const activeV = vData.active_version || (totalV > 0 ? totalV : 1);

      let versionOptionsHtml = '';
      if (versList.length > 0) {
        versList.forEach(v => {
          versionOptionsHtml += `<option value="${v.version}" ${v.version === activeV ? 'selected' : ''}>Version ${v.version}: ${v.summary || 'v' + v.version}</option>`;
        });
      } else {
        versionOptionsHtml = `<option value="1" selected>Version 1 (Active)</option>`;
      }

      const hasPrev = activeV > 1;
      const hasNext = activeV < totalV;

      versionBarHtml = `
        <div style="background: #091220; border-bottom: 1px solid var(--card-border); padding: 10px 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 13px; font-weight: 700; color: #93c5fd; display: flex; align-items: center; gap: 6px;">
              <span>📑</span> Stage Version:
            </span>
            <select id="studio-version-select" onchange="switchStudioVersion('${stKey}', parseInt(this.value))" style="background: #04070e; border: 1px solid #1e3a8a; color: #fff; padding: 5px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; cursor: pointer;">
              ${versionOptionsHtml}
            </select>
            <button class="btn-sec" style="padding: 4px 10px; font-size: 12px;" onclick="cycleStudioVersion('${stKey}', -1)" ${hasPrev ? '' : 'disabled'} title="Previous version">◀ Prev</button>
            <button class="btn-sec" style="padding: 4px 10px; font-size: 12px;" onclick="cycleStudioVersion('${stKey}', 1)" ${hasNext ? '' : 'disabled'} title="Next version">Next ▶</button>
            <span style="font-size: 12px; color: #94a3b8;">(${totalV > 0 ? totalV : 1} version${(totalV > 1) ? 's' : ''} recorded)</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <button class="btn-sec" style="padding: 5px 12px; font-size: 12px; background: #1e3a8a; border-color: #3b82f6; color: #fff;" onclick="runStudioStageOnly('${stKey}')" ${isRunning ? 'disabled' : ''}>
              ➕ Generate New Version
            </button>
          </div>
        </div>
      `;

      let alertMsg = `AI is processing stage '${meta.name}'...`;
      if (stKey === 'research') alertMsg = 'AI Researcher is analyzing topic & gathering knowledge...';
      else if (stKey === 'script') alertMsg = 'AI Scriptwriter is drafting a fresh narration script...';
      else if (stKey === 'scenes') alertMsg = 'AI Storyboarder is segmenting scenes & camera motions...';
      else if (stKey === 'prompts') alertMsg = 'AI Prompt Engineer is synthesizing visual prompts...';
      else if (stKey === 'images') alertMsg = 'ComfyUI DirectML is rendering high-res scene images...';
      else if (stKey === 'voice') alertMsg = 'BlueMagpie-TTS is synthesizing expressive voiceover audio...';
      else if (stKey === 'animation') alertMsg = 'Processing motion dynamics and animation...';
      else if (stKey === 'subtitles') alertMsg = 'Aligning timestamps and compiling subtitle cues...';
      else if (stKey === 'render') alertMsg = 'FFmpeg is assembling scenes, audio, and subtitles into 1080p MP4...';

      let liveBannerHtml = `
        <div id="studio-stage-alert" style="${isRunning ? 'display:flex;' : 'display:none;'} background: rgba(59, 130, 246, 0.15); border-bottom: 1px solid #3b82f6; padding: 12px 20px; color: #93c5fd; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <div class="spinner-inline" style="width: 20px; height: 20px;"></div>
            <div>
              <div style="font-weight: 700; color: #fff; font-size: 13px;" id="studio-alert-title">${alertMsg}</div>
              <div style="font-size: 12px; color: #cbd5e1; margin-top: 2px;" id="studio-alert-subtitle">This stage is executing independently. The workspace will automatically refresh once it completes.</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <div id="studio-alert-metric" style="font-family: monospace; font-size: 12px; color: #93c5fd;"></div>
            ${stKey === 'render' ? `
              <button class="btn-sec btn-danger" style="padding: 5px 12px; font-size: 12px; font-weight: 700;" onclick="stopRenderingVideo()">
                🛑 Stop Rendering
              </button>
            ` : ''}
          </div>
        </div>
      `;

      // 2. Stage-Specific Workspace Body
      let bodyHtml = '<div style="padding: 20px;">';

      if (stKey === 'research') {
        const resText = typeof data.research === 'string' ? data.research : JSON.stringify(data.research || {}, null, 2);
        bodyHtml += `
          <div style="margin-bottom: 16px;">
            <label style="font-weight: 600; display: block; margin-bottom: 8px; color: #cbd5e1;">Topic Research Notes & Knowledge Base (JSON / Markdown):</label>
            <textarea id="studio-research" style="width: 100%; height: 380px; font-family: monospace; font-size: 13px; background: #080d16; color: #e2e8f0; border: 1px solid var(--card-border); padding: 12px; border-radius: 6px; line-height: 1.5;">${resText}</textarea>
          </div>
          <div style="font-size: 12px; color: var(--text-muted);">
            💡 <b>Tip:</b> You can refine the research notes directly above. When you run Scriptwriting, it will use these tuned facts and points to draft your narration.
          </div>
        `;
      } else if (stKey === 'script') {
        const scriptMd = data.script_md || '';
        bodyHtml += `
          <div style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <label style="font-weight: 600; color: #cbd5e1;">YouTube Narration Script (Markdown):</label>
              <span id="studio-script-wc" style="font-size: 12px; color: #93c5fd; background: #080d16; padding: 3px 8px; border-radius: 4px; border: 1px solid #1e293b;">
                ${scriptMd.length} characters
              </span>
            </div>
            <textarea id="studio-script-md" style="width: 100%; height: 400px; font-size: 14px; background: #080d16; color: #e2e8f0; border: 1px solid var(--card-border); padding: 14px; border-radius: 6px; line-height: 1.6;" oninput="updateStudioScriptCount(this.value)">${scriptMd}</textarea>
          </div>
          <div style="font-size: 12px; color: var(--text-muted);">
            💡 <b>Tip:</b> Polish your script here. Once satisfied, click <b>"▶ Run Scene Segmentation Only"</b> or <b>"Save Changes"</b> to break it down into storyboard scenes.
          </div>
        `;
      } else if (stKey === 'scenes') {
        const scenes = data.scenes || [];
        bodyHtml += `
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <div style="font-size: 13px; color: var(--text-muted);">
              Total Storyboard Scenes: <b style="color: #93c5fd;">${scenes.length}</b>. Edit narration chunks and camera motion per scene below.
            </div>
            <button class="btn-sec" style="font-size: 12px; padding: 5px 12px;" onclick="saveStudioStage('scenes')">💾 Save Scenes</button>
          </div>
          <div style="display: flex; flex-direction: column; gap: 14px;">
        `;
        scenes.forEach((s, idx) => {
          bodyHtml += `
            <div style="background: #080d16; border: 1px solid var(--card-border); border-radius: 8px; padding: 14px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-weight: 700; color: #93c5fd; font-size: 14px;">Scene #${s.scene_id}</span>
                <span style="font-size: 12px; color: var(--text-muted);">Est: ${s.estimated_duration || 5}s</span>
              </div>
              <div style="margin-bottom: 10px;">
                <label style="font-size: 12px; color: var(--text-muted); display: block; margin-bottom: 4px;">Narration Text:</label>
                <textarea rows="2" style="width: 100%; font-size: 13px; background: #04070e; border: 1px solid #1e293b; color: #fff; padding: 8px; border-radius: 4px;" onchange="studioStageData.scenes[${idx}].narration=this.value">${s.narration}</textarea>
              </div>
              <div style="display: flex; gap: 16px; align-items: center; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 200px;">
                  <label style="font-size: 12px; color: var(--text-muted); display: block; margin-bottom: 4px;">Camera Motion Dynamics:</label>
                  <select style="width: 100%; font-size: 12px; padding: 6px; background: #04070e; border: 1px solid #1e293b; color: #cbd5e1; border-radius: 4px;" onchange="studioStageData.scenes[${idx}].camera_motion=this.value">
                    <option value="slow_zoom_in" ${s.camera_motion==='slow_zoom_in'?'selected':''}>Slow Zoom In (Engaging focus)</option>
                    <option value="slow_zoom_out" ${s.camera_motion==='slow_zoom_out'?'selected':''}>Slow Zoom Out (Reveal context)</option>
                    <option value="pan_left" ${s.camera_motion==='pan_left'?'selected':''}>Pan Left (Dynamic cinematic)</option>
                    <option value="pan_right" ${s.camera_motion==='pan_right'?'selected':''}>Pan Right (Dynamic cinematic)</option>
                    <option value="static" ${s.camera_motion==='static'?'selected':''}>Static (Still shot)</option>
                  </select>
                </div>
              </div>
            </div>
          `;
        });
        bodyHtml += `</div>`;
      } else if (stKey === 'prompts') {
        const scenes = data.scenes || [];
        const styles = data.available_styles || {};
        const curStyle = data.current_style || 'cinematic_documentary';

        let styleOptionsHtml = '';
        for (const [sKey, sObj] of Object.entries(styles)) {
          styleOptionsHtml += `<option value="${sKey}" ${sKey === curStyle ? 'selected' : ''}>${sObj.label || sKey}</option>`;
        }

        bodyHtml += `
          <!-- Visual Style Preset Selector -->
          <div style="background: linear-gradient(135deg, #0e1e38 0%, #0a1324 100%); border: 1px solid #1e3a8a; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
            <div style="font-size: 14px; font-weight: 700; color: #93c5fd; margin-bottom: 8px;">🎨 Visual Style for Prompts</div>
            <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
              <div style="flex: 1; min-width: 240px;">
                <select id="studio-prompt-style" style="width: 100%; font-size: 13px; padding: 8px; background: #080d16; color: #fff; border: 1px solid #2b456b; border-radius: 6px;">
                  ${styleOptionsHtml}
                </select>
              </div>
              <button class="btn-sec" style="font-size: 12px; padding: 8px 16px; background: #1e3a8a; border-color: #3b82f6; color: #fff;" onclick="applyStudioStyleFromPromptsTab()">🎨 Apply Style to All Prompts</button>
            </div>
          </div>

          <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">Tune ComfyUI SDXL prompts per scene below. Keywords and artistic modifiers directly steer image generation.</div>
          <div style="display: flex; flex-direction: column; gap: 14px;">
        `;
        scenes.forEach((s, idx) => {
          bodyHtml += `
            <div style="background: #080d16; border: 1px solid var(--card-border); border-radius: 8px; padding: 14px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-weight: 700; color: #93c5fd; font-size: 13px;">Scene #${s.scene_id}</span>
                <span style="font-size: 12px; color: #94a3b8; background: #04070e; padding: 2px 6px; border-radius: 4px;">${s.visual_type || 'image'}</span>
              </div>
              <div style="margin-bottom: 8px;">
                <label style="font-size: 12px; color: var(--text-muted); display: block; margin-bottom: 3px;">Positive Image Prompt:</label>
                <textarea rows="2" style="width: 100%; font-size: 12px; background: #04070e; border: 1px solid #1e293b; color: #fff; padding: 6px; border-radius: 4px;" onchange="studioStageData.scenes[${idx}].prompt=this.value">${s.prompt || ''}</textarea>
              </div>
              <div>
                <label style="font-size: 12px; color: var(--text-muted); display: block; margin-bottom: 3px;">Negative Prompt:</label>
                <input type="text" style="width: 100%; font-size: 12px; background: #04070e; border: 1px solid #1e293b; color: #cbd5e1; padding: 6px; border-radius: 4px;" value="${s.negative_prompt || ''}" onchange="studioStageData.scenes[${idx}].negative_prompt=this.value">
              </div>
            </div>
          `;
        });
        bodyHtml += `</div>`;
      } else if (stKey === 'images') {
        const scenes = data.scenes || [];
        const styles = data.available_styles || {};
        const models = data.available_models || ['sd_xl_base_1.0.safetensors'];
        const curStyle = data.current_style || 'cinematic_documentary';
        const curModel = data.current_model || 'sd_xl_base_1.0.safetensors';
        const curSteps = data.current_steps || 25;
        const curCfg = data.current_cfg || 6.5;

        const isProjCloud = isProjectCloudAccelerated(project || data);
        let styleOptionsHtml = '';
        for (const [sKey, sObj] of Object.entries(styles)) {
          const lbl = formatStyleDisplayName(sKey, sObj.label, isProjCloud);
          styleOptionsHtml += `<option value="${sKey}" ${sKey === curStyle ? 'selected' : ''}>${lbl}</option>`;
        }

        const allModels = models.includes('stock') ? models : ['stock', ...models];
        let modelOptionsHtml = '';
        allModels.forEach(m => {
          modelOptionsHtml += `<option value="${m}" ${m === curModel ? 'selected' : ''}>${formatModelLabel(m)}</option>`;
        });

        const activeStyleObj = styles[curStyle] || {};

        bodyHtml += `
          <!-- Global Style & Checkpoint Config Panel -->
          <div style="background: linear-gradient(135deg, #0e1e38 0%, #0a1324 100%); border: 1px solid #1e3a8a; border-radius: 8px; padding: 18px; margin-bottom: 22px;">
            <div style="font-size: 14px; font-weight: 700; color: #93c5fd; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
              <span>🎨 Global Image Style & Engine Configuration</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 12px;">
              <div>
                <label style="font-size: 12px; font-weight: 600; color: #cbd5e1; display: block; margin-bottom: 4px;">Visual Generation Style:</label>
                <select id="studio-img-style" style="width: 100%; font-size: 12px; padding: 7px; background: #080d16; color: #fff; border: 1px solid #2b456b; border-radius: 4px;" onchange="onStudioStyleDropdownChange(this.value)">
                  ${styleOptionsHtml}
                </select>
              </div>
              <div>
                <label style="font-size: 12px; font-weight: 600; color: #cbd5e1; display: block; margin-bottom: 4px;">Image Engine / Checkpoint:</label>
                <select id="studio-img-model" style="width: 100%; font-size: 12px; padding: 7px; background: #080d16; color: #fff; border: 1px solid #2b456b; border-radius: 4px;">
                  ${modelOptionsHtml}
                </select>
              </div>
              <div style="display: flex; gap: 10px;">
                <div style="flex: 1;">
                  <label style="font-size: 12px; font-weight: 600; color: #cbd5e1; display: block; margin-bottom: 4px;">Steps:</label>
                  <input type="number" id="studio-img-steps" value="${curSteps}" min="10" max="60" style="width: 100%; font-size: 12px; padding: 7px; background: #080d16; color: #fff; border: 1px solid #2b456b; border-radius: 4px;">
                </div>
                <div style="flex: 1;">
                  <label style="font-size: 12px; font-weight: 600; color: #cbd5e1; display: block; margin-bottom: 4px;">CFG Scale:</label>
                  <input type="number" id="studio-img-cfg" value="${curCfg}" min="1.0" max="15.0" step="0.5" style="width: 100%; font-size: 12px; padding: 7px; background: #080d16; color: #fff; border: 1px solid #2b456b; border-radius: 4px;">
                </div>
              </div>
            </div>
            <div id="studio-style-preview-box" style="font-size: 12px; background: #060a12; border: 1px solid #1a2538; padding: 8px 12px; border-radius: 4px; margin-bottom: 14px; color: #94a3b8;">
              <b>Active Style Tags:</b> <span id="studio-style-tag-text">${activeStyleObj.style || ''} (${activeStyleObj.mood || ''}, ${activeStyleObj.lighting || ''})</span>
            </div>
            <div id="studio-img-gpu-banner" style="display: flex; justify-content: space-between; align-items: center; background: #071329; border: 1px solid #1e3a8a; border-radius: 6px; padding: 10px 14px; margin-bottom: 14px; font-size: 12px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 15px;">🎮</span>
                <span style="color: #93c5fd; font-weight: 600;">Hardware Accelerator:</span>
                <span id="studio-gpu-device-title" style="color: #e2e8f0; font-weight: 600;">AMD Radeon RX 9060 XT (8GB)</span>
              </div>
              <div id="studio-gpu-metric-title" style="color: #94a3b8; font-family: monospace;">
                VRAM: <span style="color: #38bdf8;">-- GB / 8.0 GB</span> | Engine Load: <span style="color: #34d399;">--%</span>
              </div>
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
              <button class="btn-sec" style="font-size: 12px; padding: 6px 14px;" onclick="saveStudioImageSettings(false)">💾 Save Style & Model</button>
              <button class="btn-sec" style="font-size: 12px; padding: 6px 14px; background: #1e3a8a; border-color: #3b82f6; color: #fff;" onclick="saveStudioImageSettings(true)">🎨 Apply Style to All Prompts</button>
              <button class="btn-primary" style="font-size: 12px; padding: 6px 14px;" onclick="runStudioImagesWithSave(false)">▶ Generate All Images</button>
              <button class="btn-primary" style="font-size: 12px; padding: 6px 14px; background: linear-gradient(135deg, #059669 0%, #047857 100%); border-color: #10b981; font-weight: 700;" onclick="runStudioImagesWithSave(true)" title="Fetch online stock photos for all scenes without using local GPU">🌐 Fetch Online Stock Photos (All Scenes)</button>
            </div>
          </div>

          <!-- Per-Scene Gallery & Tuning -->
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
            <div style="font-size: 13px; color: var(--text-muted);">Scene Images Gallery: Tune prompts or change models per scene, then click Regenerate to re-render using ComfyUI DirectML.</div>
            <div style="display: flex; gap: 6px; align-items: center;">
              <span style="font-size: 12px; color: #94a3b8; font-weight: 600;">Gallery View:</span>
              <button class="btn-sec" id="btn-gallery-grid" style="padding: 3px 8px; font-size: 12px; font-weight: 600; ${imagesGalleryLayout !== 'strip' ? 'background: #1e3a8a; border-color: #3b82f6; color: #fff;' : ''}" onclick="toggleImagesGalleryLayout('grid')" title="Wrap cards in a responsive grid">🔲 Grid View</button>
              <button class="btn-sec" id="btn-gallery-strip" style="padding: 3px 8px; font-size: 12px; font-weight: 600; ${imagesGalleryLayout === 'strip' ? 'background: #1e3a8a; border-color: #3b82f6; color: #fff;' : ''}" onclick="toggleImagesGalleryLayout('strip')" title="Horizontal scroll bar across all scene images">↔️ Horizontal Scroll View</button>
            </div>
          </div>
          <div id="studio-images-gallery-container" class="custom-horizontal-scroll" style="${imagesGalleryLayout === 'strip' ? 'display: flex; gap: 16px; overflow-x: auto; padding-bottom: 14px;' : 'display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; overflow-x: auto; padding-bottom: 10px;'}">
        `;

        const buster = Date.now();
        scenes.forEach(s => {
          const imgUrl = s.image && s.image.path ? `/media/${currentProjectId}/${s.image.path}` : '';
          const imgUrlBusted = imgUrl ? `${imgUrl}?t=${buster}` : '';
          const renderedModel = (s.image && s.image.meta && s.image.meta.model) ? s.image.meta.model : curModel;
          const renderedStyle = s.visual_style || (s.image && s.image.meta && (s.image.meta.visual_style || s.image.meta.style)) || curStyle || 'cinematic_documentary';

          let perSceneModelOptions = '';
          allModels.forEach(m => {
            perSceneModelOptions += `<option value="${m}" ${m === renderedModel ? 'selected' : ''}>${formatModelLabel(m)}</option>`;
          });

          let perSceneStyleOptions = '';
          for (const [stk, stv] of Object.entries(styles)) {
            const lbl = formatStyleDisplayName(stk, stv ? stv.label : '', isProjCloud);
            perSceneStyleOptions += `<option value="${stk}" ${stk === renderedStyle ? 'selected' : ''}>${lbl}</option>`;
          }

          const takes = (s.image && s.image.meta && s.image.meta.takes) ? s.image.meta.takes : [];
          const activeTake = (s.image && s.image.meta && s.image.meta.active_take) ? s.image.meta.active_take : (imgUrl ? 1 : 0);
          const totalTakes = Math.max(takes.length, activeTake, imgUrl ? 1 : 0);
          const hasPrevTake = activeTake > 1;
          const hasNextTake = activeTake < totalTakes;

          bodyHtml += `
            <div id="studio-scene-card-${s.scene_id}" style="background: #080d16; border: 1px solid var(--card-border); border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 10px; min-width: 0; ${imagesGalleryLayout === 'strip' ? 'flex: 0 0 350px;' : ''} transition: border-color 0.3s ease;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 700; color: #93c5fd; font-size: 14px;">Scene #${s.scene_id}</span>
                <span id="studio-scene-badge-${s.scene_id}" style="font-size: 12px; color: ${imgUrl?'#34d399':'#f59e0b'}; font-weight: 600;">${imgUrl ? '✓ Generated' : '⏳ Pending'}</span>
              </div>
              <div style="width: 100%; height: 160px; background: #000; border-radius: 6px; overflow: hidden; display: flex; align-items: center; justify-content: center; position: relative;">
                ${imgUrl ? `
                  <img id="studio-scene-img-${s.scene_id}" src="${imgUrlBusted}" style="width: 100%; height: 100%; object-fit: cover; cursor: pointer;" onclick="window.open('${imgUrl}')" title="Click to view full image">
                  <button onclick="event.stopPropagation(); deleteSceneActiveImage(${s.scene_id})" style="position: absolute; top: 4px; right: 4px; background: rgba(0,0,0,0.75); border: 1px solid #ef4444; color: #fca5a5; border-radius: 3px; padding: 2px 6px; font-size: 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 3px; z-index: 2;" title="Delete current image">
                    🗑️ Delete
                  </button>
                ` : `<span id="studio-no-img-${s.scene_id}" style="font-size: 12px; color: gray;">No Image Generated</span>`}
              </div>

              <!-- Live Progress & GPU Workload Box (Active during generation) -->
              <div id="studio-prog-box-${s.scene_id}" style="display: none; background: #040914; border: 1px solid #2563eb; border-radius: 6px; padding: 8px 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <span id="studio-prog-title-${s.scene_id}" style="color: #60a5fa; font-weight: 600; font-size: 12px;">🚀 Initializing ComfyUI...</span>
                  <span id="studio-prog-pct-${s.scene_id}" style="color: #93c5fd; font-weight: 700; font-size: 12px;">0%</span>
                </div>
                <div style="width: 100%; height: 7px; background: #1e293b; border-radius: 999px; overflow: hidden; margin-bottom: 6px;">
                  <div id="studio-prog-bar-${s.scene_id}" style="width: 0%; height: 100%; background: linear-gradient(90deg, #2563eb, #38bdf8); transition: width 0.25s ease;"></div>
                </div>
                <div id="studio-prog-gpu-${s.scene_id}" style="font-size: 12px; color: #94a3b8; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #1e293b; padding-top: 4px;">
                  <span>DirectML GPU:</span>
                  <span id="studio-prog-gpu-val-${s.scene_id}" style="color: #38bdf8; font-weight: 600;">Querying load...</span>
                </div>
              </div>

              <!-- Success Alert Flash -->
              <div id="studio-scene-toast-${s.scene_id}" style="display: none; background: #064e3b; border: 1px solid #059669; border-radius: 4px; padding: 4px 8px; color: #a7f3d0; font-size: 12px; font-weight: 600; text-align: center;">✓ Scene #${s.scene_id} Image Regenerated!</div>

              <!-- Takes Management & Selector -->
              <div style="background: #04070e; border: 1px solid #1e293b; border-radius: 6px; padding: 8px 10px; display: flex; flex-direction: column; gap: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
                  <div style="display: flex; align-items: center; gap: 6px;">
                    <span id="studio-takes-header-count-${s.scene_id}" style="font-weight: 700; color: #93c5fd; font-size: 12px;">🎞️ Takes (${totalTakes}):</span>
                    <span id="studio-scene-active-take-badge-${s.scene_id}" style="background: rgba(5,150,105,0.25); border: 1px solid #059669; color: #34d399; font-size: 12px; font-weight: 700; padding: 1px 6px; border-radius: 4px;">✓ Take #${activeTake || 1} Active</span>
                  </div>
                  <div style="display: flex; gap: 4px; align-items: center;">
                    <button id="studio-take-prev-btn-${s.scene_id}" class="btn-sec" style="padding: 2px 7px; font-size: 12px;" onclick="cycleSceneImageTake(${s.scene_id}, -1)" ${hasPrevTake ? '' : 'disabled'} title="Previous Take">◀</button>
                    <button id="studio-take-next-btn-${s.scene_id}" class="btn-sec" style="padding: 2px 7px; font-size: 12px;" onclick="cycleSceneImageTake(${s.scene_id}, 1)" ${hasNextTake ? '' : 'disabled'} title="Next Take">▶</button>
                    <button class="btn-sec" style="padding: 2px 8px; font-size: 12px; background: #1e3a8a; border-color: #3b82f6; color: #fff; font-weight: 600;" onclick="openTakesGalleryModal(${s.scene_id})">🖼️ Compare Takes (${totalTakes})</button>
                  </div>
                </div>

                <!-- Horizontal Takes Thumbnail Strip with dedicated scrollbar and scroll controls -->
                ${takes.length > 0 ? `
                  <div id="studio-takes-wrapper-${s.scene_id}" style="display: flex; flex-direction: column; gap: 4px; background: #03060c; border: 1px solid #1e293b; border-radius: 6px; padding: 6px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                      <span id="studio-takes-count-${s.scene_id}" style="font-size: 12px; color: #94a3b8; font-weight: 600;">Images created (${takes.length}):</span>
                      <div style="display: flex; gap: 3px;">
                        <button class="btn-sec" style="padding: 1px 6px; font-size: 12px;" onclick="scrollTakesStrip('studio-takes-strip-${s.scene_id}', -120)" title="Scroll Left">◀</button>
                        <button class="btn-sec" style="padding: 1px 6px; font-size: 12px;" onclick="scrollTakesStrip('studio-takes-strip-${s.scene_id}', 120)" title="Scroll Right">▶</button>
                      </div>
                    </div>
                    <div id="studio-takes-strip-${s.scene_id}" class="takes-scroll-strip" onwheel="if(event.deltaY !== 0){ event.preventDefault(); this.scrollLeft += event.deltaY; }">
                      ${takes.map(tk => {
                        const isAct = (tk.take === activeTake);
                        const tkSrc = `/media/${currentProjectId}/${tk.path}?t=${buster}`;
                        const tkStyle = (styles[tk.style] && styles[tk.style].label) || tk.style || 'Default';
                        return `
                          <div style="flex: 0 0 105px; background: ${isAct ? '#081a38' : '#03060d'}; border: 2px solid ${isAct ? '#3b82f6' : '#1e293b'}; border-radius: 6px; padding: 5px; display: flex; flex-direction: column; gap: 4px; cursor: pointer; transition: all 0.2s ease;" onclick="switchSceneTakeDirect(${s.scene_id}, ${tk.take})" title="Click to select Take #${tk.take} for final video">
                            <div style="width: 100%; height: 56px; background: #000; border-radius: 4px; overflow: hidden; position: relative;">
                              <img src="${tkSrc}" alt="" onerror="this.onerror=null; this.src='/media/${currentProjectId}/images/scene_${String(s.scene_id).padStart(3, '0')}.png';" style="width: 100%; height: 100%; object-fit: cover;" title="Take #${tk.take}: ${tk.prompt || ''}">
                              ${isAct ? '<span style="position: absolute; top: 2px; right: 2px; background: #10b981; color: #fff; font-size: 8px; font-weight: 700; padding: 1px 4px; border-radius: 3px; box-shadow: 0 1px 3px rgba(0,0,0,0.6);">ACTIVE</span>' : ''}
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 9px; font-weight: 700;">
                              <span style="color: ${isAct ? '#93c5fd' : '#cbd5e1'};">Take #${tk.take}</span>
                              <span style="font-size: 8px; color: #94a3b8;">${tk.created_at ? tk.created_at.split(' ')[1] || '' : ''}</span>
                            </div>
                            <div style="font-size: 8px; color: #94a3b8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${tkStyle}">
                              ${tkStyle}
                            </div>
                            <div style="display: flex; gap: 3px; margin-top: auto; padding-top: 2px;">
                              <button class="btn-sec" style="flex: 1; font-size: 8px; padding: 3px 4px; font-weight: 600; ${isAct ? 'background: #059669; border-color: #10b981; color: #fff;' : 'background: #1e3a8a; border-color: #3b82f6; color: #fff;'}" onclick="event.stopPropagation(); switchSceneTakeDirect(${s.scene_id}, ${tk.take})">
                                ${isAct ? '✓ In Video' : '👉 Select'}
                              </button>
                              <button class="btn-sec" style="padding: 2px 6px; font-size: 9px; background: rgba(239, 68, 68, 0.25); border-color: #b91c1c; color: #fca5a5; font-weight: 700;" onclick="event.stopPropagation(); deleteSceneImageTake(${s.scene_id}, ${tk.take})" title="Delete Take #${tk.take}">
                                🗑️
                              </button>
                            </div>
                          </div>
                        `;
                      }).join('')}
                    </div>
                  </div>
                ` : ''}
              </div>

              <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #94a3b8;">
                <span>Active Model: <b style="color: #94a3b8;">${formatModelLabel(renderedModel)}</b></span>
                <span>Active Style: <b style="color: #93c5fd;">${(styles[renderedStyle] && styles[renderedStyle].label) || renderedStyle}</b></span>
              </div>

              <div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;">
                  <label style="font-size: 12px; color: var(--text-muted);">Prompt Tuning:</label>
                  <a href="javascript:void(0)" onclick="applyStudioSceneStyleTags(${s.scene_id})" style="color: #60a5fa; font-size: 12px; text-decoration: none;" title="Format prompt with style keywords">✨ Format with Style Tags</a>
                </div>
                <textarea id="studio-scene-prompt-${s.scene_id}" rows="2" style="width: 100%; font-size: 12px; padding: 6px; background: #04070e; border: 1px solid #1e293b; color: #e2e8f0; border-radius: 4px;">${s.prompt || s.visual_description || ''}</textarea>
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                <div>
                  <label style="font-size: 12px; font-weight: 600; color: #94a3b8; display: block; margin-bottom: 2px;">🎨 Visual Style:</label>
                  <select id="studio-scene-style-${s.scene_id}" style="width: 100%; font-size: 12px; padding: 5px; background: #04070e; border: 1px solid #1e293b; color: #cbd5e1; border-radius: 4px;" onchange="onStudioSceneStyleChange(${s.scene_id}, this.value)">
                    ${perSceneStyleOptions}
                  </select>
                </div>
                <div>
                  <label style="font-size: 12px; font-weight: 600; color: #94a3b8; display: block; margin-bottom: 2px;">🧠 Model / Checkpoint:</label>
                  <select id="studio-scene-model-${s.scene_id}" style="width: 100%; font-size: 12px; padding: 5px; background: #04070e; border: 1px solid #1e293b; color: #cbd5e1; border-radius: 4px;">
                    ${perSceneModelOptions}
                  </select>
                </div>
              </div>

              <div style="margin-top: 2px; display: flex; gap: 4px; flex-wrap: wrap;">
                <button class="btn-sec" style="flex: 1; font-size: 12px; padding: 6px 12px; background: #1e3a8a; border-color: #3b82f6; color: #fff; font-weight: 600;" onclick="regenStudioImage(${s.scene_id})" id="studio-btn-regen-${s.scene_id}">🔄 Regenerate Scene Image</button>
                <button class="btn-sec" style="font-size: 12px; padding: 6px 10px; background: rgba(5, 150, 105, 0.25); border-color: #059669; color: #6ee7b7; font-weight: 600;" onclick="quickStockPhotoForScene(${s.scene_id}, false)" title="Immediately fetch online stock photo for Scene #${s.scene_id}">🌐 Quick Stock</button>
                <button class="btn-sec" style="font-size: 12px; padding: 6px 10px; background: rgba(16, 185, 129, 0.2); border-color: #059669; color: #6ee7b7; font-weight: 600;" onclick="openStockMediaModal(${s.scene_id}, \`${(s.visual_description || s.prompt || '').replace(/[`\\$]/g, ' ')}\`)" title="Search online stock footage & photos for Scene #${s.scene_id}">🔍 Stock Library</button>
                ${imgUrl ? `<button class="btn-sec" style="padding: 6px 10px; font-size: 12px; background: rgba(239, 68, 68, 0.15); border-color: #b91c1c; color: #fca5a5; font-weight: 600;" onclick="deleteSceneActiveImage(${s.scene_id})" title="Delete image for Scene #${s.scene_id}">🗑️ Delete</button>` : ''}
              </div>
            </div>
          `;
        });
        bodyHtml += `</div>`;
      } else if (stKey === 'voice') {
        const scenes = data.scenes || [];
        const vProf = data.voice_profile || {};
        const vName = data.voice_name || 'tsao';
        const buster = Date.now();
        const hasRef = vProf.reference_wav;
        const refSrc = hasRef ? `/media/voices/${vName}/reference.wav?t=${buster}` : '';

        // Query BlueMagpie server status if relevant
        if (vProf.provider === 'bluemagpie') {
          fetch('http://127.0.0.1:8008/health').then(r => r.json()).then(h => {
            const el = document.getElementById('studio-bm-live-badge');
            if (el) el.innerHTML = `<b style="color:#34d399;">🟢 Online (Device: ${h.device})</b>`;
          }).catch(() => {
            const el = document.getElementById('studio-bm-live-badge');
            if (el) el.innerHTML = `<b style="color:#ef4444;">🔴 Offline (Port 8008 unreachable)</b>`;
          });
        }

        const isStudioEleven = vProf.provider === 'elevenlabs';

        bodyHtml += `
          <!-- Active Voice Profile & Server Status -->
          <div style="background: #0e1e38; border: 1px solid #1e3a8a; border-radius: 8px; padding: 16px 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
              <div>
                <div style="font-size: 15px; font-weight: 700; color: #fff;">Active Voice Profile: <span style="color: #93c5fd;">${vProf.display_name || vName}</span></div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                  ${isStudioEleven ? `
                    Provider: <b style="color: #60a5fa;">ElevenLabs Cloud TTS</b> | Model: <b style="color: #93c5fd;">${vProf.model_id || 'eleven_multilingual_v2'}</b> | Voice ID: <b>${vProf.voice_id || vProf.voice || 'Rachel'}</b>
                  ` : `
                    Provider: <b>${(vProf.provider || 'bluemagpie').toUpperCase()}</b> | Status: <span id="studio-bm-live-badge" style="color: #f59e0b;">Checking...</span>
                  `}
                </div>
              </div>
              ${refSrc ? `
                <div style="display: flex; flex-direction: column; align-items: flex-end;">
                  <span style="font-size: 12px; color: #cbd5e1; margin-bottom: 3px;">Reference Voice Sample:</span>
                  <audio controls src="${refSrc}" style="height: 32px; max-width: 260px;"></audio>
                </div>
              ` : (isStudioEleven ? `
                <div style="font-size: 12px; background: rgba(37,99,235,0.2); border: 1px solid #2563eb; color: #93c5fd; padding: 4px 10px; border-radius: 4px;">
                  ⚡ ElevenLabs Cloud Multilingual TTS
                </div>
              ` : '<div style="font-size: 12px; color: #f59e0b;">No reference audio sample uploaded</div>')}
            </div>
          </div>

          <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">Scene Narration Audio Clips: Listen to each scene synthesis or re-synthesize individual scenes using your cloned voice.</div>
          <div style="display: flex; flex-direction: column; gap: 12px;">
        `;

        const availVoices = data.available_voices || [];
        scenes.forEach(s => {
          const hasAudio = s.audio && s.audio.path;
          const aSrc = hasAudio ? `/media/${currentProjectId}/${s.audio.path}?t=${buster}` : '';
          const vTakes = (s.audio && s.audio.meta && s.audio.meta.takes) ? s.audio.meta.takes : [];
          const activeVTake = (s.audio && s.audio.meta && s.audio.meta.active_take) ? s.audio.meta.active_take : (aSrc ? 1 : 0);
          const totalVTakes = Math.max(vTakes.length, activeVTake, aSrc ? 1 : 0);
          const hasPrevVTake = activeVTake > 1;
          const hasNextVTake = activeVTake < totalVTakes;
          const activeSceneVoice = s.voice_profile || (s.audio && s.audio.meta && s.audio.meta.voice) || vName || 'default_local';

          let perSceneVoiceOptions = '';
          availVoices.forEach(av => {
            const isSel = (av.name === activeSceneVoice);
            perSceneVoiceOptions += `<option value="${av.name}" ${isSel ? 'selected' : ''}>${av.display_name} (${av.provider.toUpperCase()}${av.has_test_sample ? ' ✓' : ''})</option>`;
          });
          if (!availVoices.length) {
            perSceneVoiceOptions = `<option value="${vName}">${vProf.display_name || vName}</option>`;
          }

          bodyHtml += `
            <div id="studio-scene-voice-card-${s.scene_id}" style="background: #080d16; border: 1px solid var(--card-border); border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 10px;">
              <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <span style="font-weight: 700; color: #93c5fd; font-size: 14px;">Scene #${s.scene_id}</span>
                  <span style="font-size: 12px; color: var(--text-muted);">Duration: <b>${s.audio ? (s.audio.duration_seconds || s.audio_duration || s.estimated_duration || 5).toFixed(1) : 5}s</b></span>
                </div>
                <div id="studio-scene-voice-toast-${s.scene_id}" style="display: none; background: #064e3b; border: 1px solid #059669; border-radius: 4px; padding: 2px 8px; color: #a7f3d0; font-size: 12px; font-weight: 600;">✓ Saved</div>
              </div>

              <div style="font-size: 13px; color: #e2e8f0; line-height: 1.5; background: #04070e; border: 1px solid #1e293b; border-radius: 6px; padding: 10px 12px;">
                "${s.narration}"
              </div>

              <!-- Voice Profile Selector & Regeneration Controls -->
              <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; background: #0e1e38; border: 1px solid #1e3a8a; border-radius: 6px; padding: 8px 12px;">
                <div style="display: flex; align-items: center; gap: 8px; flex: 1; min-width: 240px;">
                  <label style="font-size: 12px; font-weight: 600; color: #93c5fd; white-space: nowrap;">🎙️ Scene Voice:</label>
                  <select id="studio-scene-voice-${s.scene_id}" style="width: 100%; font-size: 12px; padding: 5px 8px; background: #04070e; border: 1px solid #1e293b; color: #cbd5e1; border-radius: 4px;">
                    ${perSceneVoiceOptions}
                  </select>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                  <button class="btn-sec" style="font-size: 12px; padding: 6px 14px; background: #1e3a8a; border-color: #3b82f6; color: #fff; font-weight: 600;" onclick="regenStudioVoice(${s.scene_id})" id="studio-btn-voice-${s.scene_id}">🎙️ Synthesize Voice</button>
                  ${hasAudio ? `<button class="btn-sec" style="padding: 6px 10px; font-size: 12px; background: rgba(239, 68, 68, 0.15); border-color: #b91c1c; color: #fca5a5; font-weight: 600;" onclick="deleteSceneActiveVoice(${s.scene_id})" title="Delete voice for Scene #${s.scene_id}">🗑️ Delete</button>` : ''}
                </div>
              </div>

              <!-- Takes Management Bar & Strip -->
              <div style="background: #04070e; border: 1px solid #1e293b; border-radius: 6px; padding: 8px 10px; display: flex; flex-direction: column; gap: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
                  <div style="display: flex; align-items: center; gap: 6px;">
                    <span id="studio-voice-takes-header-count-${s.scene_id}" style="font-weight: 700; color: #93c5fd; font-size: 12px;">🎞️ Voice Takes (${totalVTakes}):</span>
                    <span id="studio-scene-active-voice-badge-${s.scene_id}" style="background: rgba(5,150,105,0.25); border: 1px solid #059669; color: #34d399; font-size: 12px; font-weight: 700; padding: 1px 6px; border-radius: 4px;">✓ Take #${activeVTake || 1} Active</span>
                  </div>
                  <div style="display: flex; gap: 4px; align-items: center;">
                    <button id="studio-voice-prev-btn-${s.scene_id}" class="btn-sec" style="padding: 2px 7px; font-size: 12px;" onclick="cycleSceneVoiceTake(${s.scene_id}, -1)" ${hasPrevVTake ? '' : 'disabled'} title="Previous Voice Take">◀</button>
                    <button id="studio-voice-next-btn-${s.scene_id}" class="btn-sec" style="padding: 2px 7px; font-size: 12px;" onclick="cycleSceneVoiceTake(${s.scene_id}, 1)" ${hasNextVTake ? '' : 'disabled'} title="Next Voice Take">▶</button>
                    <button class="btn-sec" style="padding: 2px 8px; font-size: 12px; background: #1e3a8a; border-color: #3b82f6; color: #fff; font-weight: 600;" onclick="openVoiceTakesGalleryModal(${s.scene_id})">🎧 Compare Takes (${totalVTakes})</button>
                  </div>
                </div>

                <!-- Horizontal Voice Takes Strip with dedicated scrollbar and scroll controls -->
                ${vTakes.length > 0 ? `
                  <div id="studio-voice-takes-wrapper-${s.scene_id}" style="display: flex; flex-direction: column; gap: 4px; background: #03060c; border: 1px solid #1e293b; border-radius: 6px; padding: 6px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                      <span id="studio-voice-takes-count-${s.scene_id}" style="font-size: 12px; color: #94a3b8; font-weight: 600;">Voice takes created (${vTakes.length}):</span>
                      <div style="display: flex; gap: 3px;">
                        <button class="btn-sec" style="padding: 1px 6px; font-size: 12px;" onclick="scrollTakesStrip('studio-voice-takes-strip-${s.scene_id}', -150)" title="Scroll Left">◀</button>
                        <button class="btn-sec" style="padding: 1px 6px; font-size: 12px;" onclick="scrollTakesStrip('studio-voice-takes-strip-${s.scene_id}', 150)" title="Scroll Right">▶</button>
                      </div>
                    </div>
                    <div id="studio-voice-takes-strip-${s.scene_id}" class="takes-scroll-strip" onwheel="if(event.deltaY !== 0){ event.preventDefault(); this.scrollLeft += event.deltaY; }">
                      ${vTakes.map(tk => {
                        const isAct = (tk.take === activeVTake);
                        const tkSrc = `/media/${currentProjectId}/${tk.path}?t=${buster}`;
                        const tkVoice = tk.voice || 'default';
                        const dur = (tk.duration_seconds || 0).toFixed(1);
                        return `
                          <div style="flex: 0 0 175px; background: ${isAct ? '#081a38' : '#03060d'}; border: 2px solid ${isAct ? '#3b82f6' : '#1e293b'}; border-radius: 6px; padding: 6px 8px; display: flex; flex-direction: column; gap: 5px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; font-weight: 700;">
                              <span style="color: ${isAct ? '#93c5fd' : '#cbd5e1'};">Take #${tk.take}</span>
                              ${isAct ? '<span style="background: #10b981; color: #fff; font-size: 8px; font-weight: 700; padding: 1px 4px; border-radius: 3px;">ACTIVE</span>' : ''}
                            </div>
                            <div style="font-size: 9px; color: #94a3b8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="Voice: ${tkVoice}">
                              Voice: <b style="color: #cbd5e1;">${tkVoice}</b> | <b>${dur}s</b>
                            </div>
                            <audio controls src="${tkSrc}" style="width: 100%; height: 28px;"></audio>
                            <div style="display: flex; gap: 4px; margin-top: auto; padding-top: 2px;">
                              <button class="btn-sec" style="flex: 1; font-size: 9px; padding: 3px 6px; font-weight: 600; ${isAct ? 'background: #059669; border-color: #10b981; color: #fff;' : 'background: #1e3a8a; border-color: #3b82f6; color: #fff;'}" onclick="switchSceneVoiceTakeDirect(${s.scene_id}, ${tk.take})">
                                ${isAct ? '✓ In Video' : '👉 Select'}
                              </button>
                              <button class="btn-sec" style="padding: 2px 6px; font-size: 8px; background: rgba(239, 68, 68, 0.25); border-color: #b91c1c; color: #fca5a5; font-weight: 700;" onclick="deleteSceneVoiceTake(${s.scene_id}, ${tk.take})" title="Delete Voice Take #${tk.take}">
                                🗑️
                              </button>
                            </div>
                          </div>
                        `;
                      }).join('')}
                    </div>
                  </div>
                ` : `
                  <div style="display: flex; align-items: center; justify-content: space-between;">
                    ${aSrc ? `<audio controls src="${aSrc}" style="height: 32px; max-width: 280px;"></audio>` : '<span style="font-size: 12px; color: #f59e0b;">⏳ No voice audio generated yet</span>'}
                  </div>
                `}
              </div>
            </div>
          `;
        });
        bodyHtml += `</div>`;
      } else if (stKey === 'animation') {
        const scenes = data.scenes || [];
        bodyHtml += `
          <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 14px;">Camera Motion & Pan/Zoom dynamics for all scenes. Static images are brought to life using Ken Burns dynamic effects.</div>
          <div style="display: flex; flex-direction: column; gap: 12px;">
        `;
        scenes.forEach((s, idx) => {
          bodyHtml += `
            <div style="background: #080d16; border: 1px solid var(--card-border); border-radius: 8px; padding: 14px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
              <div>
                <span style="font-weight: 700; color: #93c5fd;">Scene #${s.scene_id}</span>
                <div style="font-size: 12px; color: #cbd5e1; margin-top: 2px;">Motion: <b>${s.camera_motion || 'slow_zoom_in'}</b> | Duration: <b>${s.estimated_duration || 5}s</b></div>
              </div>
              <div style="display: flex; gap: 10px; align-items: center;">
                <select style="font-size: 12px; padding: 6px; background: #04070e; border: 1px solid #1e293b; color: #cbd5e1; border-radius: 4px;" onchange="studioStageData.scenes[${idx}].camera_motion=this.value">
                  <option value="slow_zoom_in" ${s.camera_motion==='slow_zoom_in'?'selected':''}>Slow Zoom In</option>
                  <option value="slow_zoom_out" ${s.camera_motion==='slow_zoom_out'?'selected':''}>Slow Zoom Out</option>
                  <option value="pan_left" ${s.camera_motion==='pan_left'?'selected':''}>Pan Left</option>
                  <option value="pan_right" ${s.camera_motion==='pan_right'?'selected':''}>Pan Right</option>
                  <option value="static" ${s.camera_motion==='static'?'selected':''}>Static</option>
                </select>
              </div>
            </div>
          `;
        });
        bodyHtml += `</div>`;
      } else if (stKey === 'subtitles') {
        const srtText = data.srt || '';
        bodyHtml += `
          <div style="margin-bottom: 16px;">
            <label style="font-weight: 600; display: block; margin-bottom: 8px; color: #cbd5e1;">Subtitles (.srt format with timing):</label>
            <textarea id="studio-srt" style="width: 100%; height: 380px; font-family: monospace; font-size: 13px; background: #080d16; color: #e2e8f0; border: 1px solid var(--card-border); padding: 12px; border-radius: 6px; line-height: 1.5;">${srtText}</textarea>
          </div>
          <div style="font-size: 12px; color: var(--text-muted);">
            💡 <b>Tip:</b> Subtitles are precisely rendered onto the final 1080p video with styled drop shadow. You can edit phrases or timestamps here.
          </div>
        `;
      } else if (stKey === 'render') {
        const finalRel = data.outputs && data.outputs.final ? data.outputs.final : null;
        const vSrc = finalRel ? `/media/${currentProjectId}/${finalRel}` : '';
        bodyHtml += `
          <div style="margin-bottom: 16px;">
            <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">Final 1080p Video Player and Render Output:</div>
            ${vSrc ? `
              <div style="background: #000; border-radius: 8px; overflow: hidden; border: 1px solid var(--card-border);">
                <video controls src="${vSrc}" style="width: 100%; max-height: 480px; display: block;"></video>
              </div>
              <div style="margin-top: 14px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                <a href="${vSrc}" download class="button" style="text-decoration: none;">
                  <button style="padding: 10px 20px;">Download Final MP4 (1080p)</button>
                </a>
                <button class="btn-primary" style="padding: 10px 18px; font-size: 13px; font-weight: 700; background: linear-gradient(135deg, #dc2626, #b91c1c); border-color: #b91c1c; display: inline-flex; align-items: center; gap: 6px;" onclick="openYouTubeUploadModal()" title="Upload finished video to YouTube channel @tsao36">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
                  <span>📺 Upload to YouTube (@tsao36)</span>
                </button>
                ${isRunning ? `
                  <button class="btn-sec btn-danger" style="padding: 10px 18px; font-size: 13px; font-weight: 700;" onclick="stopRenderingVideo()">
                    🛑 Stop Rendering Video
                  </button>
                ` : ''}
              </div>
            ` : `
              <div style="padding: 50px 20px; text-align: center; background: #080d16; border-radius: 8px; border: 1px dashed var(--card-border); color: var(--text-muted);">
                <div style="font-size: 36px; margin-bottom: 12px;">🎥</div>
                <div style="font-size: 15px; font-weight: 600; color: #fff; margin-bottom: 6px;">${isRunning ? '⏳ FFmpeg Video Rendering in Progress...' : 'No final video rendered yet'}</div>
                <div style="font-size: 12px; max-width: 440px; margin: 0 auto 16px auto;">${isRunning ? 'FFmpeg is compiling scene clips, transitions, narration, and subtitles into MP4.' : 'When you\'re ready, click "String All Stages Together & Create Video" or "▶ Render 1080p Video" to assemble all tuned assets.'}</div>
                <div style="display: flex; gap: 10px; justify-content: center; align-items: center; flex-wrap: wrap;">
                  ${isRunning ? `
                    <button class="btn-sec btn-danger" style="padding: 10px 24px; font-size: 13px; font-weight: 700;" onclick="stopRenderingVideo()">
                      🛑 Stop Rendering Video
                    </button>
                  ` : `
                    <button class="btn-primary" style="padding: 10px 24px; font-size: 13px; font-weight: 700; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);" onclick="assembleAllStagesNow()">
                      🔗 String All Stages Together & Create Video
                    </button>
                  `}
                </div>
              </div>
            `}
          </div>
        `;
      }

      bodyHtml += '</div>';

      // 3. Footer Navigation Bar
      const currentIdx = STAGE_ORDER.indexOf(stKey);
      const prevKey = currentIdx > 0 ? STAGE_ORDER[currentIdx - 1] : null;
      const nextKey = currentIdx < STAGE_ORDER.length - 1 ? STAGE_ORDER[currentIdx + 1] : null;

      let footerHtml = `
        <div style="background: #080d16; border-top: 1px solid var(--card-border); padding: 14px 20px; border-radius: 0 0 8px 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
          <div>
            ${prevKey ? `
              <button class="btn-sec" style="font-size: 12px; padding: 7px 14px;" onclick="switchStudioStage('${prevKey}')">
                ← Previous Stage (${STAGE_META[prevKey].num}. ${STAGE_META[prevKey].name})
              </button>
            ` : '<div style="width: 120px;"></div>'}
          </div>
          <button class="btn-primary" style="padding: 9px 20px; font-size: 13px; font-weight: 700; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);" onclick="assembleAllStagesNow()">
            🔗 String All Stages Together & Create Video
          </button>
          <div>
            ${nextKey ? `
              <button class="btn-sec" style="font-size: 12px; padding: 7px 14px;" onclick="switchStudioStage('${nextKey}')">
                Next Stage (${STAGE_META[nextKey].num}. ${STAGE_META[nextKey].name}) →
              </button>
            ` : '<div style="width: 120px;"></div>'}
          </div>
        </div>
      `;

      wsEl.innerHTML = headerHtml + versionBarHtml + liveBannerHtml + bodyHtml + footerHtml;
      if (stKey === 'script') {
        updateStudioScriptCount(data.script_md || '');
      } else if (stKey === 'images') {
        fetch('/api/images/live_status').then(r => r.json()).then(sdata => {
          const gBanner = document.getElementById('studio-gpu-metric-title');
          if (gBanner && sdata.gpu) {
            const loadCol = sdata.gpu.util_percent > 60 ? '#f59e0b' : (sdata.gpu.util_percent > 15 ? '#38bdf8' : '#34d399');
            gBanner.innerHTML = `VRAM: <span style="color:#38bdf8;">${sdata.gpu.vram_gb} GB / ${sdata.gpu.vram_total_gb} GB</span> | Engine Load: <span style="color:${loadCol}; font-weight:700;">${sdata.gpu.util_percent}%</span>`;
          }
        }).catch(() => {});
      }
    }

    async function switchStudioVersion(stKey, targetV) {
      if (!currentProjectId) return;
      try {
        const res = await fetch(`/api/projects/${currentProjectId}/stages/${stKey}/versions/switch/${targetV}`, { method: 'POST' });
        const d = await res.json();
        if (d.status === 'error') throw new Error(d.message);
        loadStageStudio(stKey);
      } catch (e) {
        alert("Failed to switch version: " + e.message);
      }
    }

    async function cycleStudioVersion(stKey, delta) {
      if (!studioStageData || !studioStageData.versioning) return;
      const curV = studioStageData.versioning.active_version || 1;
      const targetV = curV + delta;
      switchStudioVersion(stKey, targetV);
    }

    async function cycleSceneImageTake(sceneId, delta) {
      const stageData = studioStageData || inspectedStageData;
      if (!stageData || !stageData.scenes) return;
      const sc = stageData.scenes.find(s => s.scene_id === sceneId);
      if (!sc) return;
      const curTake = (sc.image && sc.image.meta && sc.image.meta.active_take) ? sc.image.meta.active_take : 1;
      const targetTake = curTake + delta;
      await switchSceneTakeDirect(sceneId, targetTake);
    }