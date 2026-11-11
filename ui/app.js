    let currentProjectId = null;
    let currentProject = null;
    let pollInterval = null;
    let pollGeneration = 0;
    let pollController = null;

    // Use helpers from api.js if present, or assign fallback
    var nativeFetch = window.nativeFetch || (window.fetch ? window.fetch.bind(window) : null);
    if (!window.apiRequest) {
      window.apiRequest = async function apiRequest(url, options = {}) {
        let response;
        try {
          response = await (window.nativeFetch || window.fetch)(url, options);
        } catch (error) {
          throw new Error(error?.message || 'Network request failed');
        }
        if (response.ok) return response;
        const body = await response.json().catch(() => ({}));
        const detail = Array.isArray(body.detail)
          ? body.detail.map(item => item.msg || JSON.stringify(item)).join('; ')
          : (body.detail || body.message);
        throw new Error(detail || `Request failed (${response.status})`);
      };
    }
    if (!window.apiJson) {
      window.apiJson = async function apiJson(url, options = {}) {
        const response = await window.apiRequest(url, options);
        return response.json();
      };
    }
    if (!window.escapeHtml) {
      window.escapeHtml = function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, char => ({
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          "'": '&#39;'
        })[char]);
      };
    }

    function toggleStepMode(enabled) {
      const toggle = document.getElementById('step-mode-toggle');
      if (toggle && typeof enabled === 'boolean') toggle.checked = enabled;
    }
    window.toggleStepMode = toggleStepMode;
    let timerInterval = null;
    let cachedRerenderVoices = [];


        // ---------------- RE-RENDER AVATAR CLIPS & VIDEO MODAL LOGIC ----------------
    let cachedPresenterScenes = [];
    let cachedRaAvatars = [];
    let cachedRaVoices = [];

    function closeRerenderAvatarModal() {
      const m = document.getElementById('rerender-avatar-modal');
      if (m) m.style.display = 'none';
    }

    function toggleRaCustomScenes(val) {
      const box = document.getElementById('ra-custom-scenes-box');
      if (box) box.style.display = (val === 'custom') ? 'block' : 'none';
    }

    function onRaAvatarChange() {
      const avSel = document.getElementById('ra-avatar-profile');
      const voiceSel = document.getElementById('ra-voice-profile');
      const hintEl = document.getElementById('ra-voice-hint');
      const badgeEl = document.getElementById('ra-voice-badge');
      if (!avSel || !voiceSel) return;

      const chosenAvName = avSel.value;
      const avObj = cachedRaAvatars.find(a => a.name === chosenAvName);
      if (avObj && avObj.voice_profile) {
        const matchedVoice = cachedRaVoices.find(v => v.name === avObj.voice_profile);
        if (matchedVoice) {
          voiceSel.value = matchedVoice.name;
          if (badgeEl) {
            badgeEl.textContent = "Avatar's Linked Voice";
            badgeEl.style.background = "rgba(139, 92, 246, 0.25)";
            badgeEl.style.color = "#c4b5fd";
          }
          if (hintEl) {
            hintEl.innerHTML = `✨ Auto-matched <b>${escapeHtml(matchedVoice.display_name || matchedVoice.name)}</b> linked to avatar <b>${escapeHtml(avObj.display_name || avObj.name)}</b>. You can change this or select "Keep Existing Voice Audio".`;
          }
          onRaVoiceProfileChange(true);
          return;
        }
      }
      onRaVoiceProfileChange(false);
    }

    function onRaVoiceProfileChange(isAutoLinked = false) {
      const voiceSel = document.getElementById('ra-voice-profile');
      const scopeBox = document.getElementById('ra-voice-scope-container');
      const hintEl = document.getElementById('ra-voice-hint');
      const badgeEl = document.getElementById('ra-voice-badge');
      if (!voiceSel) return;

      const chosenVal = voiceSel.value;
      if (!chosenVal) {
        if (scopeBox) scopeBox.style.display = 'none';
        if (badgeEl) {
          badgeEl.textContent = "Keep Current Voice";
          badgeEl.style.background = "rgba(100, 116, 139, 0.25)";
          badgeEl.style.color = "#94a3b8";
        }
        if (hintEl) {
          hintEl.innerHTML = `Existing speech audio will be preserved. Only presenter video clips will be replaced.`;
        }
      } else {
        if (scopeBox) scopeBox.style.display = 'block';
        const vObj = cachedRaVoices.find(v => v.name === chosenVal);
        const prov = (vObj && vObj.provider) ? vObj.provider.toUpperCase() : '';
        if (badgeEl) {
          badgeEl.textContent = `Will Re-synthesize (${prov || 'VOICE'})`;
          badgeEl.style.background = "rgba(16, 185, 129, 0.25)";
          badgeEl.style.color = "#34d399";
        }
        if (hintEl && !isAutoLinked) {
          hintEl.innerHTML = `🎙️ Will synthesize lines with <b>${escapeHtml(vObj ? (vObj.display_name || vObj.name) : chosenVal)}</b> (${prov}) before generating new avatar lip-sync clips.`;
        }
      }
    }

    async function openRerenderAvatarModal(preselectedAvatar = null) {
      if (!currentProjectId) return alert("Please select a project first.");

      const m = document.getElementById('rerender-avatar-modal');
      if (m) m.style.display = 'flex';

      const diagBox = document.getElementById('ra-diagnosis-box');
      const avSel = document.getElementById('ra-avatar-profile');
      const voiceSel = document.getElementById('ra-voice-profile');
      const customList = document.getElementById('ra-custom-scenes-list');

      if (diagBox) diagBox.innerHTML = '<span style="color:#c4b5fd;">🔍 Inspecting presenter scenes in project...</span>';

      try {
        const [aData, pData, vData] = await Promise.all([
          apiJson('/api/avatars'),
          apiJson(`/api/projects/${currentProjectId}`),
          apiJson('/api/voices')
        ]);

        cachedRaAvatars = aData.avatars || [];
        cachedRaVoices = Array.isArray(vData) ? vData : (vData.voices || []);
        const proj = pData.project || {};
        const scenes = pData.scenes || [];

        const defaultAv = proj.settings?.default_avatar || '';
        const targetAv = preselectedAvatar || defaultAv;
        const currentProjVoice = proj.settings?.voice_profile || '';

        if (avSel) {
          avSel.innerHTML = cachedRaAvatars.map(av => {
            const isSel = (av.name === targetAv);
            return `<option value="${av.name}" ${isSel ? 'selected' : ''}>${escapeHtml(av.display_name || av.name)} (${av.name}) — ${av.engine || 'latentsync'}</option>`;
          }).join('') || '<option value="">No avatars created yet</option>';
        }

        if (voiceSel) {
          let voiceOpts = `<option value="">Keep Existing Voice Audio (Do not change voice)</option>`;
          cachedRaVoices.forEach(v => {
            let tag = (v.provider || 'local').toUpperCase();
            if (v.provider === 'elevenlabs') tag = 'ElevenLabs';
            else if (v.provider === 'voai') tag = 'VoAI';
            else if (v.provider === 'bluemagpie') tag = 'BlueMagpie';
            else if (v.provider === 'cosyvoice') tag = 'CosyVoice';
            const isProjVoice = (v.name === currentProjVoice);
            voiceOpts += `<option value="${v.name}">${escapeHtml(v.display_name || v.name)} (${v.name}) — 🎙️ ${tag}${isProjVoice ? ' [Current Project Voice]' : ''}</option>`;
          });
          voiceSel.innerHTML = voiceOpts;
        }

        // If a target avatar was selected, trigger auto-match for linked voice
        onRaAvatarChange();

        cachedPresenterScenes = scenes.filter(s => s.is_presenter || s.visual_type === 'talking_head');

        if (diagBox) {
          if (cachedPresenterScenes.length > 0) {
            const idsStr = cachedPresenterScenes.map(s => `#${s.scene_id}`).join(', ');
            diagBox.innerHTML = `
              <div style="font-weight:700; color:#c4b5fd; margin-bottom:4px;">
                ✓ Found <b>${cachedPresenterScenes.length}</b> Talking Avatar scene(s) in this project: ${idsStr}
              </div>
              <div style="font-size:11px; color:#94a3b8;">
                Current Project Avatar: <b>${escapeHtml(defaultAv || 'Not set')}</b> | Project Voice: <b>${escapeHtml(currentProjVoice || 'Default')}</b>
              </div>
            `;
          } else {
            diagBox.innerHTML = `
              <div style="font-weight:700; color:#fbbf24; margin-bottom:4px;">
                ⚠️ No presenter scenes are currently designated in this project.
              </div>
              <div style="font-size:11px; color:#94a3b8;">
                Tip: You can enable "🎭 虛擬主播出鏡 (Talking Avatar)" on any scene card in Stage Studio or Scene Editor first.
              </div>
            `;
          }
        }

        if (customList) {
          customList.innerHTML = cachedPresenterScenes.map(s => `
            <label style="display:flex; align-items:center; gap:8px; font-size:12px; color:#e2e8f0; cursor:pointer;">
              <input type="checkbox" value="${s.scene_id}" checked class="ra-scene-chk">
              <span><b>Scene #${s.scene_id}</b>: ${escapeHtml((s.narration || '').slice(0, 45))}...</span>
            </label>
          `).join('') || '<div style="color:gray; font-size:12px;">No presenter scenes found</div>';
        }

      } catch (err) {
        if (diagBox) diagBox.innerHTML = `<span style="color:#f87171;">Failed to inspect project: ${err.message}</span>`;
      }
    }

    async function fastRerenderUpdatedVideo() {
      if (!currentProjectId) return alert("Please select a project first.");
      if (!confirm("確定僅替換已修改的分鏡片段，並重新合成輸出完整 1080p 影片（取代舊影片）？\n\n其餘未修改的分鏡將直接命中快取，大幅節省時間！")) {
        return;
      }
      try {
        await apiRequest(`/api/projects/${currentProjectId}/fast_rerender_video`, { method: 'POST' })

        startPolling();
        alert("⚡ 已開始快速合成影片！系統僅會替換已修改的分鏡，其餘畫面直接套用快取。完成後將自動更新播放器。");
      } catch (err) {
        alert("Fast render failed: " + err.message);
      }
    }

    async function submitRerenderAvatarClips() {
      if (!currentProjectId) return;

      const avSel = document.getElementById('ra-avatar-profile');
      const engSel = document.getElementById('ra-engine');
      const scopeSel = document.getElementById('ra-scope');
      const voiceSel = document.getElementById('ra-voice-profile');
      const voiceScopeSel = document.getElementById('ra-voice-scope');
      const btn = document.getElementById('btn-execute-rerender-avatar');

      const avatar = avSel ? avSel.value : null;
      const engine = engSel && engSel.value ? engSel.value : null;
      const scope = scopeSel ? scopeSel.value : 'all';
      const voiceProfile = voiceSel && voiceSel.value ? voiceSel.value : null;
      const voiceScope = voiceScopeSel ? voiceScopeSel.value : 'all';

      let sceneIds = null;
      if (scope === 'custom') {
        const chks = Array.from(document.querySelectorAll('.ra-scene-chk:checked')).map(c => parseInt(c.value));
        if (!chks.length) return alert("Please select at least one presenter scene to replace.");
        sceneIds = chks;
      }

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>⏳ Queuing Avatar & Voice Replacement...</span>';
      }

      try {
        const payload = {
          avatar_profile: avatar,
          engine: engine,
          scene_ids: sceneIds,
          voice_profile: voiceProfile,
          voice_scope: voiceScope,
        };

        await apiRequest(`/api/projects/${currentProjectId}/rerender_avatar_clips`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })



        closeRerenderAvatarModal();
        startPolling();
        const voiceMsg = voiceProfile ? ` and voice '${voiceProfile}'` : '';
        alert(`🚀 Human avatar clip replacement${voiceMsg} started! Watch progress in the top activity bar.`);
      } catch (e) {
        alert("Avatar Replacement Error: " + e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<span>🚀 Replace Avatar Clips & Update Video</span>';
        }
      }
    }


    function triggerSceneAvatarUpload(sceneId) {
      const inp = document.getElementById(`scene-avatar-file-${sceneId}`);
      if (inp) inp.click();
    }

    async function uploadCustomSceneAvatarClip(sceneId, file) {
      if (!currentProjectId || !file) return;
      if (!confirm(`Upload "${file.name}" to replace Scene #${sceneId}'s avatar clip and update the final 1080p video?`)) {
        return;
      }

      const fd = new FormData();
      fd.append('file', file);
      fd.append('update_video', 'true');

      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/scenes/${sceneId}/upload_avatar_clip`, {
          method: 'POST',
          body: fd,
        });




        alert(`✓ Scene #${sceneId} avatar video uploaded! Final video update has started in the background.`);
        startPolling();
        if (typeof loadStageStudio === 'function') loadStageStudio();
      } catch (err) {
        alert("Upload error: " + err.message);
      }
    }

    async function rerenderSingleSceneAvatarClip(sceneId) {
      if (!currentProjectId) return;
      if (!confirm(`Re-generate avatar lip-sync clip for Scene #${sceneId} and update the final video?`)) return;

      try {
        await apiRequest(`/api/projects/${currentProjectId}/scenes/${sceneId}/rerender_avatar_clip`, {
          method: 'POST',
        })

        startPolling();
        alert(`Scene #${sceneId} avatar re-generation started!`);
      } catch (err) {
        alert("Re-render error: " + err.message);
      }
    }

    function closeRerenderVoiceModal() {
      const m = document.getElementById('rerender-voice-modal');
      if (m) m.style.display = 'none';
    }

    function previewRerenderSelectedVoice() {
      const sel = document.getElementById('rv-voice-profile');
      if (!sel || !sel.value) return;
      playExistingVoiceSample(sel.value);
    }

    async function switchProjectGlobalVoiceProfile(newProfileName, reloadView = 'studio') {
      if (!currentProjectId || !newProfileName) return;
      try {
        const vp = (cachedVoiceList || []).find(v => v.name === newProfileName) ||
                   (cachedRerenderVoices || []).find(v => v.name === newProfileName);
        const prov = vp ? (vp.provider || 'bluemagpie') : 'bluemagpie';
        await apiRequest(`/api/projects/${currentProjectId}/stage-models`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            stage_models: { voice: prov },
            voice_profile: newProfileName
          })
        })

          showToast(`🎙️ Switched project Active Voice Profile to "${newProfileName}" (${getVoiceProviderLabel(prov)})!`);
          if (reloadView === 'inspector') {
            openStageInspector('voice');
          } else {
            loadStageStudio('voice');
          }

      } catch (e) {
        alert("Failed to switch voice profile: " + e.message);
      }
    }

    function onRerenderScopeChange() {
      const scope = document.getElementById('rv-scope')?.value || 'all';
      const customGrp = document.getElementById('rv-custom-range-group');
      if (customGrp) {
        customGrp.style.display = (scope === 'custom') ? 'block' : 'none';
      }
    }

    function onRerenderVoiceProfileChange() {
      const sel = document.getElementById('rv-voice-profile');
      const provSel = document.getElementById('rv-tts-provider');
      const hintEl = document.getElementById('rv-voice-profile-hint');
      if (!sel) return;
      const chosen = cachedRerenderVoices.find(v => v.name === sel.value);
      if (chosen) {
        if (provSel && chosen.provider) {
          provSel.value = chosen.provider;
        }
        if (hintEl) {
          if (chosen.provider === 'elevenlabs') {
            hintEl.innerHTML = `⚡ ElevenLabs Voice ID: <b style="color:#6ee7b7; font-family:monospace;">${chosen.voice_id || chosen.voice || 'Default'}</b> • Model: <b>${chosen.model_id || 'eleven_multilingual_v2'}</b>`;
          } else if (chosen.provider === 'voai') {
            hintEl.innerHTML = `🇹🇼 VoAI 絕好聲創 Speaker: <b style="color:#38bdf8;">${chosen.speaker || chosen.voice_id || chosen.voice || '佑希'}</b> • Version: <b>${chosen.version || chosen.model_id || 'Sota+'}</b> • Style: <b>${chosen.voai_style || '預設'}</b>`;
          } else {
            hintEl.innerHTML = `🖥️ Provider: <b>${(chosen.provider || 'bluemagpie').toUpperCase()}</b> ${chosen.reference_wav ? '• Reference WAV uploaded ✓' : ''}`;
          }
        }
      }
    }

    async function openRerenderVoiceModal(preselectedProfile = null) {
      if (!currentProjectId) {
        return alert("Please select a project first.");
      }
      const m = document.getElementById('rerender-voice-modal');
      if (m) m.style.display = 'flex';

      const diagBox = document.getElementById('rv-diagnosis-box');
      if (diagBox) diagBox.innerHTML = '⏳ Inspecting project scenes & voice tracks...';

      try {
        const [voiceData, pData] = await Promise.all([
          apiJson('/api/voices'),
          apiJson(`/api/projects/${currentProjectId}`)
        ]);
        cachedRerenderVoices = voiceData;
        const proj = pData.project || {};
        const scenes = pData.scenes || [];

        const subEl = document.getElementById('rv-project-subtitle');
        if (subEl) {
          subEl.textContent = `Project: ${proj.title || proj.topic || currentProjectId} (${scenes.length} scenes)`;
        }

        const sel = document.getElementById('rv-voice-profile');
        const projVoice = preselectedProfile || (proj.settings && proj.settings.voice_profile) || '';
        const projEngine = (proj.settings && proj.settings.stage_models && proj.settings.stage_models.voice) || 'elevenlabs';

        if (sel) {
          sel.innerHTML = '';
          let defaultSelected = projVoice;
          if (!preselectedProfile && projEngine === 'elevenlabs') {
            const customEleven = cachedRerenderVoices.find(v => v.provider === 'elevenlabs' && (v.voice_id || v.voice));
            if (customEleven && (!defaultSelected || defaultSelected === 'mytsaovoice' || defaultSelected === 'elevenlabs')) {
              defaultSelected = customEleven.name;
            }
          } else if (!preselectedProfile && projEngine === 'voai') {
            const customVoai = cachedRerenderVoices.find(v => v.provider === 'voai');
            if (customVoai && (!defaultSelected || defaultSelected === 'mytsaovoice' || defaultSelected === 'voai')) {
              defaultSelected = customVoai.name;
            }
          }
          cachedRerenderVoices.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v.name;
            let tag = `🖥️ ${(v.provider || 'local').toUpperCase()}`;
            if (v.provider === 'elevenlabs') {
              tag = `⚡ ElevenLabs [${v.model_id || 'multilingual_v2'} • ${(v.voice_id || v.voice || '').slice(0, 8)}...]`;
            } else if (v.provider === 'voai') {
              tag = `🇹🇼 VoAI 絕好聲創 [${v.version || v.model_id || 'Sota+'} • ${v.speaker || v.voice_id || '佑希'} • ${v.voai_style || '預設'}]`;
            }
            opt.textContent = `${v.display_name} (${v.name}) — ${tag}`;
            if (v.name === defaultSelected) opt.selected = true;
            sel.appendChild(opt);
          });
        }

        const provSel = document.getElementById('rv-tts-provider');
        if (provSel && projEngine) {
          provSel.value = projEngine;
        }
        onRerenderVoiceProfileChange();

        // Build scene voice diagnosis summary (group contiguous scene runs by provider + voice_id)
        if (diagBox) {
          if (!scenes.length) {
            diagBox.innerHTML = 'No scenes found in this project yet.';
          } else {
            const groups = [];
            scenes.forEach(s => {
              const meta = (s.audio && s.audio.meta) || {};
              const prov = meta.provider || 'pending';
              const vid = meta.voice_id ? `${meta.voice || ''} (${meta.voice_id.slice(0, 8)}...)` : (meta.voice || s.voice_profile || 'default');
              const key = `${prov}::${vid}`;
              const last = groups[groups.length - 1];
              if (last && last.key === key) {
                last.end = s.scene_id;
                last.count++;
              } else {
                groups.push({ key, prov, vid, start: s.scene_id, end: s.scene_id, count: 1 });
              }
            });

            const hasMixed = groups.length > 1;
            let html = `<div style="font-weight:700; color:${hasMixed ? '#fbbf24' : '#93c5fd'}; margin-bottom:6px;">
              ${hasMixed ? '⚠️ Mixed Voice Providers Detected Across Scenes:' : '✓ Current Scene Voice Breakdown:'}
            </div><div style="display:flex; flex-direction:column; gap:4px;">`;
            groups.forEach(g => {
              const rangeLabel = g.start === g.end ? `Scene #${g.start}` : `Scenes #${g.start}–#${g.end} (${g.count} scenes)`;
              html += `<div style="background:#0b1526; border:1px solid #1e293b; border-radius:4px; padding:4px 8px; display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:700; color:#e2e8f0;">${rangeLabel}</span>
                <span style="color:#60a5fa; font-family:monospace; font-size:11px;">Engine: <b>${g.prov.toUpperCase()}</b> • Voice: <b>${g.vid}</b></span>
              </div>`;
            });
            html += `</div>`;
            diagBox.innerHTML = html;

            // If mixed voices detected (e.g. Scenes 22-41), prefill custom range with the second group's range as a helpful hint
            if (hasMixed && groups.length >= 2) {
              const lastGrp = groups[groups.length - 1];
              const rangeInput = document.getElementById('rv-custom-range');
              if (rangeInput && !rangeInput.value) {
                rangeInput.value = `${lastGrp.start}-${lastGrp.end}`;
              }
            }
          }
        }
      } catch (e) {
        console.error("Failed to open rerender voice modal:", e);
        if (diagBox) diagBox.textContent = "Could not load project details: " + e.message;
      }
    }

    function parseSceneRangeInput(str) {
      const out = new Set();
      if (!str) return [];
      str.split(',').forEach(part => {
        const p = part.trim();
        if (!p) return;
        if (p.includes('-')) {
          const [a, b] = p.split('-').map(x => parseInt(x.trim(), 10));
          if (!isNaN(a) && !isNaN(b)) {
            for (let i = Math.min(a, b); i <= Math.max(a, b); i++) out.add(i);
          }
        } else {
          const n = parseInt(p, 10);
          if (!isNaN(n)) out.add(n);
        }
      });
      return Array.from(out).sort((a, b) => a - b);
    }

    async function executeRerenderVoiceAndVideo() {
      if (!currentProjectId) return;
      const voiceProfile = document.getElementById('rv-voice-profile')?.value || '';
      const ttsProvider = document.getElementById('rv-tts-provider')?.value || '';
      const scope = document.getElementById('rv-scope')?.value || 'all';
      const customRangeStr = document.getElementById('rv-custom-range')?.value || '';

      let sceneIds = null;
      if (scope === 'custom') {
        sceneIds = parseSceneRangeInput(customRangeStr);
        if (!sceneIds.length) {
          return alert("Please enter valid scene numbers or a range (e.g. 22-41).");
        }
      }

      const btn = document.getElementById('btn-execute-rerender-voice');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ Starting Voice & Video Update...';
      }

      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/rerender_voice_and_video`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            voice_profile: voiceProfile,
            tts_provider: ttsProvider,
            scope: scope,
            scene_ids: sceneIds
          })
        });


        if (data.status === 'already_running') {
          alert("This project pipeline is already running. Please wait or click Stop first.");
          return;
        }
        closeRerenderVoiceModal();
        showToast(`🎙️🔄 Re-rendering voice (${voiceProfile} / ${ttsProvider}) & updating 1080p video...`);
        startPolling();
      } catch (e) {
        alert("Error starting voice re-render: " + e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<span>🚀 Start Voice Re-render & Update Video</span>';
        }
      }
    }
    let currentScenes = [];
    let projectStartTime = null;
    let imagesGalleryLayout = 'grid';

    function toggleImagesGalleryLayout(layout) {
      imagesGalleryLayout = layout;
      if (inspectedStageName === 'images') {
        openStageInspector('images');
      } else {
        loadStageStudio('images');
      }
    }

    function scrollTakesStrip(stripId, delta) {
      const el = document.getElementById(stripId);
      if (el) {
        el.scrollBy({ left: delta, behavior: 'smooth' });
      }
    }

    const STAGE_ORDER = ["research", "script", "scenes", "prompts", "images", "voice", "music", "animation", "subtitles", "render"];
    const STAGE_LABELS = {
      research: "1/10 Research",
      script: "2/10 Script",
      scenes: "3/10 Scenes",
      prompts: "4/10 Prompts",
      images: "5/10 Images",
      voice: "6/10 Voice TTS",
      music: "7/10 Ambient Music",
      animation: "8/10 Animation",
      subtitles: "9/10 Subtitles",
      render: "10/10 Render"
    };

    window.switchTab = switchTab;
    function switchTab(name) {
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      const foundTab = document.querySelector(`.nav-tab[data-tab="${name}"]`)
        || Array.from(document.querySelectorAll('.nav-tab')).find(t => (t.getAttribute('onclick') || '').includes(`switchTab('${name}')`));
      if (foundTab) foundTab.classList.add('active');
      // Both Stage Studios share one workspace DOM; each mode has its own tab, header and project list.
      const isStudioTab = (name === 'studio' || name === 'dramastudio');
      const targetContent = document.getElementById('tab-' + (isStudioTab ? 'studio' : name));
      if (targetContent) targetContent.classList.add('active');

      if (isStudioTab) {
        studioMode = (name === 'dramastudio') ? 'short_drama' : 'documentary';
        applyStudioModeChrome();
        loadStageStudio();
      }
            if (name === 'voices') { loadVoiceProfiles(); loadElevenLabsVoices(); }
      if (name === 'music') loadMusicTracks();
        if (name === 'avatars') loadAvatars();
      if (name === 'drama') {
        currentCreatorProjectMode = 'short_drama';
        if (typeof checkDramaHedraStatus === 'function') checkDramaHedraStatus();
        if (typeof renderDramaCharactersEditor === 'function') renderDramaCharactersEditor();
        if (typeof loadDramaFormulas === 'function') loadDramaFormulas();
      } else if (name === 'creator') {
        currentCreatorProjectMode = 'documentary';
      }
        if (name === 'characters') loadCharactersLibrary();
      if (name === 'settings') { loadApiKeys(); if (typeof checkYouTubeStatus === 'function') checkYouTubeStatus(); }
      if (name === 'logs') refreshLogs();
      if (name === 'preview') {
        const pSel = document.getElementById('preview-project-select');
        if (pSel && currentProjectId) {
          pSel.value = currentProjectId;
        }
        updatePreviewMedia();
      }
    }

    async function loadStatus() {
      try {
        const s = await apiJson('/api/status');

        document.getElementById('hw-status-summary').innerHTML =
          `CPU: <b>${s.cpu}</b> | RAM: <b>${s.ram_avail_gb} / ${s.ram_gb} GB</b> | GPU: <b>${s.gpu} (${s.vram_gb} GB VRAM)</b> | FFmpeg: <b>${s.ffmpeg ? '✓' : '✗'}</b> | ComfyUI: <b>${s.comfyui ? '✓ ('+s.comfyui_device+')' : '✗'}</b> | Ollama: <b>${s.ollama ? '✓' : '✗'}</b>`;
      } catch (e) {
        console.error("Status check failed", e);
      }
    }

    async function unloadVRAM() {
      const d = await apiJson('/api/memory/unload', { method: 'POST' });

      alert("VRAM Freed: ComfyUI " + d.comfyui + ", Ollama " + d.ollama);
      loadStatus();
    }

    let cachedVoiceList = [];

    function getVoiceProviderLabel(provider) {
      if (provider === 'bluemagpie') return 'Local: BlueMagpie Clone';
      if (provider === 'cosyvoice') return 'Local: CosyVoice 2 Clone';
      if (provider === 'http_clone' || provider === 'f5') return 'Local: F5-TTS Clone';
      if (provider === 'elevenlabs') return 'Cloud: ElevenLabs';
      if (provider === 'voai') return 'Cloud: VoAI 絕好聲創';
      if (provider === 'edge') return 'Cloud: Edge TTS';
      if (provider === 'sapi') return 'Local: Windows SAPI';
      return (provider || 'Local').toUpperCase();
    }

    async function loadVoices() {
      try {
        const voices = await apiJson('/api/voices');

        cachedVoiceList = voices;
        const sel = document.getElementById('voice-select');
        if (!sel) return;
        sel.innerHTML = '';
        voices.forEach(v => {
          const opt = document.createElement('option');
          opt.value = v.name;
          const pLabel = getVoiceProviderLabel(v.provider);
          opt.textContent = `${v.display_name} [${pLabel}]` + (v.name === 'mytsaovoice' ? ' (Default)' : (v.is_default ? ' (Default)' : ''));
          opt.dataset.provider = v.provider || 'bluemagpie';
          if (v.name === 'mytsaovoice') {
            opt.selected = true;
          }
          sel.appendChild(opt);
        });
        // Fallback: if mytsaovoice exists in list, ensure it's selected
        if (voices.some(v => v.name === 'mytsaovoice')) {
          sel.value = 'mytsaovoice';
        }
        onVoiceProfileSelectChange(false);
      } catch (e) {
        console.error('Failed to load voice profiles:', e);
      }
    }

    function selectCreatorRemotionStyle(val) {
      setVal('model-stage-animation', val);
      onStageModelChange('animation');
      updateCreatorRemotionStrip();
    }

    function updateCreatorRemotionStrip() {
      const el = document.getElementById('model-stage-animation');
      const strip = document.getElementById('creator-remotion-preview-strip');
      const activeName = document.getElementById('creator-remotion-active-name');
      if (!el || !strip) return;
      const v = el.value || '';
      if (v.startsWith('remotion')) {
        strip.style.display = 'block';
        const styles = [
          'remotion_coordinate_scale',
          'remotion_coordinate_experiment',
          'remotion_coordinate_split',
          'remotion_evidence',
          'remotion_pathway',
          'remotion_callout',
          'remotion_scale',
        ];
        styles.forEach(k => {
          const card = document.getElementById('creator-style-' + k);
          if (card) {
            const isSel = (v === k || (v === 'remotion' && k === 'remotion_evidence'));
            const color = '#00F5FF';
            card.style.border = isSel ? `2px solid ${color}` : '1px solid #1e293b';
            card.style.boxShadow = isSel ? `0 0 10px ${color}40` : 'none';
          }
        });
        if (activeName) {
          if (v === 'remotion_coordinate_scale') activeName.textContent = '🧭 等緯尺度 (Coordinate Scale)';
          else if (v === 'remotion_coordinate_experiment') activeName.textContent = '🔬 桌面實驗 (Coordinate Experiment)';
          else if (v === 'remotion_coordinate_split') activeName.textContent = '⚖️ 各對一半 (Coordinate Split)';
          else if (v === 'remotion_finance_candlestick') activeName.textContent = '📈 盤勢結構 (Finance Candlestick)';
          else if (v === 'remotion_finance_metrics') activeName.textContent = '📊 財務基本面 (Finance Metrics)';
          else if (v === 'remotion_archival_doc') activeName.textContent = '📜 解密檔案 (Archival Document)';
          else if (v === 'remotion_history_chrono') activeName.textContent = '⏳ 年代編年 (History Chronology)';
          else if (v === 'remotion_vox_split') activeName.textContent = '🗞️ 政策對照 (Vox Split-Screen)';
          else if (v === 'remotion_vox_keystat') activeName.textContent = '⚡ 核心發現 (Vox Key Stat)';
          else if (v === 'remotion_pathway') activeName.textContent = '🔀 分支決策 (Branch Pathway)';
          else if (v === 'remotion_callout') activeName.textContent = '🎯 引線標註 (Leader Callout)';
          else if (v === 'remotion_scale') activeName.textContent = '🔬 尺度對比 (Scale Loupe)';
          else activeName.textContent = '📑 文獻劃記 (Evidence Highlight)';
        }
      } else {
        strip.style.display = 'none';
      }
    }

    function applyFinanceMarketRemotionPreset() {
      window.activeRemotionPreset = 'finance_market';
      setVal('model-stage-animation', 'remotion_finance_candlestick');
      setVal('ai-video-pct', '0');

      setVal('creator-presenter-placement', 'none');
      if (typeof onPresenterPlacementChange === 'function') onPresenterPlacementChange();
      const autoPres = document.getElementById('creator-auto-presenter');
      if (autoPres) autoPres.checked = false;

      const styleEl = document.getElementById('visual-style');
      if (styleEl && styleEl.value !== 'tech_schematic') {
        styleEl.value = 'tech_schematic';
        if (typeof onCreatorStyleChange === 'function') onCreatorStyleChange('tech_schematic');
      }
      onStageModelChange('animation');
      updateCreatorRemotionStrip();
      if (currentProjectId) {
        const sm = getSelectedStageModels();
        sm.animation = 'remotion_finance_candlestick';
        apiRequest(`/api/projects/${currentProjectId}/stage-models`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage_models: sm })
        }).catch(e => console.error(e));

        apiRequest(`/api/projects/${currentProjectId}/settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            presenter_placement: 'none',
            auto_presenter: false,
            avatar_enabled: false,
            animation: {
              motion_graphics_density: 'full',
              ai_video_percentage: 0
            },
            remotion: {
              style: 'finance_market',
              theme: 'finance_grid',
              density: 'full',
              accentColor: '#10B981'
            }
          })
        }).catch(e => console.error(e));
      }
      showToast('📈 已一鍵配置為「金融市場 (Finance Market)」風格！(100% Remotion K線走勢、支撐壓力標線、營運利差對比)');
    }

    function applyArchivalHistoryRemotionPreset() {
      window.activeRemotionPreset = 'archival_history';
      setVal('model-stage-animation', 'remotion_archival_doc');
      setVal('ai-video-pct', '0');
      setVal('creator-callout-style', 'archival_parchment');

      setVal('creator-presenter-placement', 'none');
      if (typeof onPresenterPlacementChange === 'function') onPresenterPlacementChange();
      const autoPres = document.getElementById('creator-auto-presenter');
      if (autoPres) autoPres.checked = false;

      const styleEl = document.getElementById('visual-style');
      if (styleEl && styleEl.value !== 'documentary') {
        styleEl.value = 'documentary';
        if (typeof onCreatorStyleChange === 'function') onCreatorStyleChange('documentary');
      }
      onStageModelChange('animation');
      updateCreatorRemotionStrip();
      if (currentProjectId) {
        const sm = getSelectedStageModels();
        sm.animation = 'remotion_archival_doc';
        apiRequest(`/api/projects/${currentProjectId}/stage-models`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage_models: sm })
        }).catch(e => console.error(e));

        apiRequest(`/api/projects/${currentProjectId}/settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            presenter_placement: 'none',
            auto_presenter: false,
            avatar_enabled: false,
            animation: {
              motion_graphics_density: 'full',
              ai_video_percentage: 0
            },
            remotion: {
              style: 'archival_history',
              theme: 'parchment_paper',
              density: 'full',
              accentColor: '#C2410C'
            }
          })
        }).catch(e => console.error(e));
      }
      showToast('📜 已一鍵配置為「歷史檔案 (Archival History)」風格！(100% Remotion 羊皮紙解密檔案、紅色官印、年代編年進程)');
    }

    function applyVoxJournalismRemotionPreset() {
      window.activeRemotionPreset = 'vox_journalism';
      setVal('model-stage-animation', 'remotion_vox_split');
      setVal('ai-video-pct', '0');
      setVal('creator-callout-style', 'broadcast_news');

      setVal('creator-presenter-placement', 'none');
      if (typeof onPresenterPlacementChange === 'function') onPresenterPlacementChange();
      const autoPres = document.getElementById('creator-auto-presenter');
      if (autoPres) autoPres.checked = false;

      const styleEl = document.getElementById('visual-style');
      if (styleEl && styleEl.value !== 'editorial') {
        styleEl.value = 'editorial';
        if (typeof onCreatorStyleChange === 'function') onCreatorStyleChange('editorial');
      }
      onStageModelChange('animation');
      updateCreatorRemotionStrip();
      if (currentProjectId) {
        const sm = getSelectedStageModels();
        sm.animation = 'remotion_vox_split';
        apiRequest(`/api/projects/${currentProjectId}/stage-models`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage_models: sm })
        }).catch(e => console.error(e));

        apiRequest(`/api/projects/${currentProjectId}/settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            presenter_placement: 'none',
            auto_presenter: false,
            avatar_enabled: false,
            animation: {
              motion_graphics_density: 'full',
              ai_video_percentage: 0
            },
            remotion: {
              style: 'vox_journalism',
              theme: 'vox_charcoal',
              density: 'full',
              accentColor: '#FACC15'
            }
          })
        }).catch(e => console.error(e));
      }
      showToast('🗞️ 已一鍵配置為「Vox 深度調查 (Vox Journalism)」風格！(100% Remotion 政策雙分割對照、140px巨型數據、螢光標記)');
    }

    function applyCoordinateZeroRemotionPreset() {
      window.activeRemotionPreset = 'coordinate_zero';
      setVal('model-stage-animation', 'remotion_coordinate_scale');
      setVal('ai-video-pct', '0');
      setVal('creator-callout-style', 'modern_pill');

      // Turn off virtual presenter for 100% pure tactile desktop graphics
      setVal('creator-presenter-placement', 'none');
      if (typeof onPresenterPlacementChange === 'function') onPresenterPlacementChange();
      const autoPres = document.getElementById('creator-auto-presenter');
      if (autoPres) autoPres.checked = false;

      const styleEl = document.getElementById('visual-style');
      if (styleEl && styleEl.value !== 'documentary') {
        styleEl.value = 'documentary';
        if (typeof onCreatorStyleChange === 'function') onCreatorStyleChange('documentary');
      }
      onStageModelChange('animation');
      updateCreatorRemotionStrip();
      if (currentProjectId) {
        const sm = getSelectedStageModels();
        sm.animation = 'remotion_coordinate_scale';
        apiRequest(`/api/projects/${currentProjectId}/stage-models`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage_models: sm })
        }).catch(e => console.error(e));

        apiRequest(`/api/projects/${currentProjectId}/settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            presenter_placement: 'none',
            auto_presenter: false,
            avatar_enabled: false,
            animation: {
              motion_graphics_density: 'full',
              ai_video_percentage: 0
            },
            remotion: {
              style: 'coordinate_zero',
              theme: 'green_cutting_mat',
              density: 'full',
              accentColor: '#0D9488'
            }
          })
        }).catch(e => console.error(e));
      }
      showToast('🧭 已一鍵配置為「座標零 (Coordinate Zero)」桌面實驗室風格！(100% Remotion 綠色雕刻墊、等緯尺度縮放對比、垂直倍率規、雙向論證)');
    }

    function applyGaryChenRemotionPreset() {
      window.activeRemotionPreset = 'gary_chen';
      setVal('model-stage-animation', 'remotion');
      setVal('ai-video-pct', '0');

      // Turn off virtual presenter / avatars for 100% pure Remotion motion graphics
      setVal('creator-presenter-placement', 'none');
      if (typeof onPresenterPlacementChange === 'function') onPresenterPlacementChange();
      const autoPres = document.getElementById('creator-auto-presenter');
      if (autoPres) autoPres.checked = false;

      const styleEl = document.getElementById('visual-style');
      if (styleEl && styleEl.value !== 'tech_schematic') {
        styleEl.value = 'tech_schematic';
        if (typeof onCreatorStyleChange === 'function') onCreatorStyleChange('tech_schematic');
      }
      onStageModelChange('animation');
      updateCreatorRemotionStrip();
      if (currentProjectId) {
        const sm = getSelectedStageModels();
        sm.animation = 'remotion';
        apiRequest(`/api/projects/${currentProjectId}/stage-models`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage_models: sm })
        }).catch(e => console.error(e));

        apiRequest(`/api/projects/${currentProjectId}/settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            presenter_placement: 'none',
            auto_presenter: false,
            avatar_enabled: false,
            animation: {
              motion_graphics_density: 'full',
              ai_video_percentage: 0
            },
            remotion: {
              style: 'modern_tech_explainer',
              theme: 'dark_obsidian',
              density: 'full',
              accentColor: '#38BDF8'
            }
          })
        }).catch(e => console.error(e));
      }
      showToast('✨ 已一鍵配置為 Gary Chen 極簡科技解說風格！(100% Remotion 全程動態圖表、0% AI 圖片幻燈片、深色黑曜石畫布、關閉虛擬人出鏡)');
    }

    function apply100PercentRemotionPreset() {
      window.activeRemotionPreset = 'blueprint';
      setVal('model-stage-animation', 'remotion');
      setVal('ai-video-pct', '0');
      const styleEl = document.getElementById('visual-style');
      if (styleEl && styleEl.value !== 'tech_schematic') {
        styleEl.value = 'tech_schematic';
        if (typeof onCreatorStyleChange === 'function') onCreatorStyleChange('tech_schematic');
      }
      onStageModelChange('animation');
      updateCreatorRemotionStrip();
      if (currentProjectId) {
        const sm = getSelectedStageModels();
        sm.animation = 'remotion';
        apiRequest(`/api/projects/${currentProjectId}/stage-models`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage_models: sm })
        }).catch(e => console.error(e));
      }
      showToast('⚛️ 已一鍵配置為 100% Remotion 影片架構！(Stage 8: Auto Tactile Blueprint, AI 影片: 0%, 視覺風格: Tech Schematic)');
    }

    function enableRemotionInCreator() {
      apply100PercentRemotionPreset();
    }

    function onVoiceProfileSelectChange(notify = true) {
      const sel = document.getElementById('voice-select');
      const stageVoiceEl = document.getElementById('model-stage-voice');
      const hintEl = document.getElementById('voice-select-hint');
      const syncBadge = document.getElementById('stage-voice-sync-hint');
      if (!sel || !sel.value) return;

      const chosen = cachedVoiceList.find(v => v.name === sel.value);
      const prov = chosen ? (chosen.provider || 'bluemagpie') : 'bluemagpie';
      const provLabel = getVoiceProviderLabel(prov);

      if (stageVoiceEl && stageVoiceEl.value !== prov) {
        stageVoiceEl.value = prov;
        if (typeof onStageModelChange === 'function') {
          onStageModelChange('voice', false);
        }
      }

      if (hintEl) {
        hintEl.innerHTML = `🔗 Stage 6 TTS: <b>${provLabel}</b>`;
        hintEl.style.color = '#10b981';
      }
      if (syncBadge) {
        syncBadge.innerHTML = `🔗 Synced: <b>${chosen ? chosen.display_name : sel.value}</b>`;
        syncBadge.style.color = '#10b981';
      }
    }

    function onStageVoiceModelChange() {
      const stageVoiceEl = document.getElementById('model-stage-voice');
      const sel = document.getElementById('voice-select');
      const hintEl = document.getElementById('voice-select-hint');
      const syncBadge = document.getElementById('stage-voice-sync-hint');
      if (!stageVoiceEl || !sel || !cachedVoiceList.length) return;

      const targetProv = stageVoiceEl.value;
      const provLabel = getVoiceProviderLabel(targetProv);

      const currentChosen = cachedVoiceList.find(v => v.name === sel.value);
      if (currentChosen && ((currentChosen.provider || 'bluemagpie') === targetProv || ((targetProv === 'cosyvoice' || targetProv === 'cozyvoice') && (currentChosen.provider === 'cosyvoice' || currentChosen.provider === 'cozyvoice')))) {
        if (hintEl) hintEl.innerHTML = `🔗 Stage 6 TTS: <b>${provLabel}</b>`;
        if (syncBadge) syncBadge.innerHTML = `🔗 Synced: <b>${currentChosen.display_name}</b>`;
        return;
      }

      const match = cachedVoiceList.find(v => (v.provider || 'bluemagpie') === targetProv || ((targetProv === 'cosyvoice' || targetProv === 'cozyvoice') && (v.provider === 'cosyvoice' || v.provider === 'cozyvoice')));
      if (match) {
        sel.value = match.name;
        if (hintEl) hintEl.innerHTML = `🔗 Stage 6 TTS: <b>${provLabel}</b>`;
        if (syncBadge) syncBadge.innerHTML = `🔗 Synced: <b>${match.display_name}</b>`;
      } else {
        if (hintEl) hintEl.innerHTML = `⚠️ No profile found for ${provLabel}`;
      }
    }

    function formatModelLabel(modelName) {
      if (!modelName) return 'Default Model';
      if (modelName === 'nano-banana-2.1' || modelName === 'gemini-nano-banana-2.1' || modelName === 'nano-banana') return '☁️ Google Nano Banana 2.1 ($0.0168/img Batch • ~$0.67/40 scenes)';
      if (modelName === 'stock' || modelName === 'stock_photos') return '🌐 Online Stock Photos ($0.00 / Free)';
      if (modelName === 'fal-ai/flux-1/schnell' || modelName === 'fal-ai/flux/schnell' || modelName === 'flux-schnell') return '☁️ Fal.ai fal-ai/flux-1/schnell ($0.003/img • ~$0.12/40 scenes)';
      if (modelName === 'gpt-image-1' || modelName === 'gpt_image_1') return '☁️ OpenAI gpt-image-1 ($0.08/img • ~$3.20/40 scenes)';
      if (modelName === 'imagen-3.0-generate-002' || modelName === 'imagen-30.0-generate-002') return '☁️ Google imagen-3.0-generate-002 ($0.04/img • ~$1.60/40 scenes)';
      if (modelName === 'dalle3' || modelName === 'dall-e-3') return '☁️ OpenAI DALL-E 3 ($0.04/img • ~$1.60/40 scenes)';
      if (modelName === 'imagen3' || modelName === 'gemini_image') return '☁️ Google Gemini Flash Image ($0.03/img • ~$1.20/40 scenes)';
      if (modelName.includes('juggernaut')) return 'Juggernaut XL v8 (Photorealistic Cinema • $0.00 Local)';
      if (modelName.includes('sd_xl_base')) return 'SDXL Base 1.0 (General / Stylized • $0.00 Local)';
      return modelName;
    }

    const VISUAL_STYLE_DEFINITIONS = [
      { value: 'tech_schematic', localLabel: 'Tech Schematic & Kinetic Callouts (fOx Hsiao style)', cloudLabel: 'Tech Schematic (fOx Style)' },
      { value: 'photorealistic_cinema', localLabel: 'Photorealistic Cinema (Juggernaut XL)', cloudLabel: 'Photorealistic Cinema' },
      { value: 'cinematic_documentary', localLabel: 'Cinematic Documentary', cloudLabel: 'Cinematic Documentary' },
      { value: 'anime_shinkai', localLabel: 'Anime / Makoto Shinkai (新海誠極致光影風)', cloudLabel: 'Anime / Makoto Shinkai (新海誠風格)' },
      { value: 'ink_wash_history', localLabel: 'Traditional Ink Wash & Historical Epic (水墨史詩歷史風)', cloudLabel: 'Traditional Ink Wash & Historical Epic (水墨史詩風)' },
      { value: 'vintage_archive', localLabel: 'Vintage Archive (1970s Film)', cloudLabel: 'Vintage Archive' },
      { value: 'photorealistic_editorial', localLabel: 'Photorealistic Editorial (NatGeo)', cloudLabel: 'Photorealistic Editorial' },
      { value: 'hyperreal_3d', localLabel: 'Hyperreal 3D (Unreal Engine 5)', cloudLabel: 'Hyperreal 3D' },
      { value: 'anime_ghibli', localLabel: 'Anime / Studio Ghibli', cloudLabel: 'Anime / Studio Ghibli' },
      { value: 'cyberpunk_neon', localLabel: 'Cyberpunk Sci-Fi Neon', cloudLabel: 'Cyberpunk Sci-Fi' },
      { value: 'watercolor_art', localLabel: 'Watercolor Illustration', cloudLabel: 'Watercolor Illustration' },
      { value: 'digital_painting', localLabel: 'Digital Concept Painting', cloudLabel: 'Digital Concept Painting' },
      { value: 'clean_explainer', localLabel: 'Clean 3D Isometric Explainer', cloudLabel: 'Clean 3D Explainer' },
      { value: 'retro_comic', localLabel: 'Retro Comic Book / Pop Art', cloudLabel: 'Retro Comic Book' },
      { value: 'dark_fantasy', localLabel: 'Dark Fantasy Gothic', cloudLabel: 'Dark Fantasy Gothic' },
      { value: 'minimalist_vector', localLabel: 'Minimalist Modern Vector', cloudLabel: 'Minimalist Modern Vector' },
      { value: 'minimalist_explainer_cartoon', localLabel: 'Minimalist Vector Explainer (商業大師 / Doodle Cartoon)', cloudLabel: 'Minimalist Vector Explainer (商業大師風格)' }
    ];

    let cachedLocalCheckpoints = [
      'juggernautXL_v8Rundiffusion.safetensors',
      'sd_xl_base_1.0.safetensors'
    ];

    const CANONICAL_IMAGE_ENGINES = [
      { val: 'fal-ai/flux-1/schnell', label: 'Cloud API: fal-ai/flux-1/schnell ($0.003/img • ~$0.12/40 sc) (Default)' },
      { val: 'nano-banana-2.1', label: 'Cloud API: Google Nano Banana 2.1 ($0.0168/img Batch • ~$0.67/40 sc)' },
      { val: 'comfyui', label: 'Local GPU: ComfyUI DirectML ($0.00 / Free)' },
      { val: 'stock', label: '🌐 Online Stock Photos & Footage ($0.00 / Free, 0 VRAM)' },
      { val: 'gpt-image-1', label: 'Cloud API: OpenAI gpt-image-1 ($0.08/img • ~$3.20/40 sc)' },
      { val: 'imagen-3.0-generate-002', label: 'Cloud API: Google imagen-3.0-generate-002 ($0.04/img • ~$1.60/40 sc)' },
      { val: 'dalle3', label: 'Cloud API: OpenAI DALL-E 3 ($0.04/img • ~$1.60/40 sc)' },
      { val: 'imagen3', label: 'Cloud API: Google Gemini Flash Image ($0.03/img • ~$1.20/40 sc)' }
    ];

    const CLOUD_IMAGE_ENGINES = ['fal-ai/flux-1/schnell', 'nano-banana-2.1', 'gpt-image-1', 'imagen-3.0-generate-002', 'dalle3', 'imagen3', 'stock'];

    function isCloudAccelerationActive() {
      const cloudToggle = document.getElementById('cloud-toggle');
      if (cloudToggle && cloudToggle.value === 'true') return true;
      const imgStage = document.getElementById('model-stage-images');
      if (imgStage && CLOUD_IMAGE_ENGINES.includes(imgStage.value)) return true;
      return false;
    }

    function isProjectCloudAccelerated(p) {
      if (!p) return isCloudAccelerationActive();
      if (p.settings && p.settings.cloud && p.settings.cloud.enabled) return true;
      if (p.settings && p.settings.stage_models && CLOUD_IMAGE_ENGINES.includes(p.settings.stage_models.images)) return true;
      return false;
    }

    function formatStyleDisplayName(styleKey, fallbackLabel, isCloud) {
      const def = VISUAL_STYLE_DEFINITIONS.find(d => d.value === styleKey);
      if (def) {
        return isCloud ? def.cloudLabel : def.localLabel;
      }
      if (isCloud && fallbackLabel) {
        return fallbackLabel.replace(/\s*\([^)]*juggernaut[^)]*\)/gi, '').trim();
      }
      return fallbackLabel || styleKey;
    }

    function updateVisualStyleOptions(isCloud) {
      const sel = document.getElementById('visual-style');
      if (!sel) return;
      const currentVal = sel.value || 'photorealistic_cinema';
      sel.innerHTML = '';
      VISUAL_STYLE_DEFINITIONS.forEach(def => {
        const opt = document.createElement('option');
        opt.value = def.value;
        opt.textContent = isCloud ? def.cloudLabel : def.localLabel;
        if (def.value === currentVal) opt.selected = true;
        sel.appendChild(opt);
      });
      if (!sel.value && sel.options.length) {
        sel.selectedIndex = 0;
      }
    }

    function updateCheckpointControls(isCloud) {
      const labelEl = document.getElementById('checkpoint-label');
      const selEl = document.getElementById('checkpoint-select');
      if (!selEl) return;
      const stageImagesEl = document.getElementById('model-stage-images');
      const currentTargetVal = (stageImagesEl && stageImagesEl.value) ? stageImagesEl.value : (selEl.value || 'fal-ai/flux-1/schnell');

      if (labelEl) {
        labelEl.innerHTML = `
          <span>Image Engine (Stage 5)</span>
          <span style="font-size: 11px; color: #10b981; font-weight: 600;">🔗 Synced with Stage 5</span>
        `;
      }

      // Build options from CANONICAL_IMAGE_ENGINES so Creator mode & Stage 5 match 100%
      let optsHtml = CANONICAL_IMAGE_ENGINES.map(o =>
        `<option value="${o.val}" ${o.val === currentTargetVal ? 'selected' : ''}>${o.label}</option>`
      ).join('');

      // If local checkpoints exist in ComfyUI, append them cleanly under an optgroup
      if (cachedLocalCheckpoints && cachedLocalCheckpoints.length) {
        optsHtml += `<optgroup label="Local Checkpoints (ComfyUI DirectML)">`;
        cachedLocalCheckpoints.forEach(m => {
          optsHtml += `<option value="${m}" ${m === currentTargetVal ? 'selected' : ''}>Local: ${formatModelLabel(m)}</option>`;
        });
        optsHtml += `</optgroup>`;
      }

      selEl.innerHTML = optsHtml;
      if (currentTargetVal) selEl.value = currentTargetVal;
    }

    function onCheckpointChange(val) {
      const stageImagesEl = document.getElementById('model-stage-images');
      if (!stageImagesEl) return;

      const stageVal = (val.endsWith('.safetensors') || val.endsWith('.ckpt')) ? 'comfyui' : val;
      stageImagesEl.value = stageVal;

      // Auto-sync Cloud Acceleration toggle if a cloud model was picked
      const cloudToggle = document.getElementById('cloud-toggle');
      if (CLOUD_IMAGE_ENGINES.includes(stageVal)) {
        if (cloudToggle && cloudToggle.value !== 'true') {
          cloudToggle.value = 'true';
        }
      }

      // Update stage models across app & save if project is loaded
      onStageModelChange('images');

      // Sync stage card dropdown
      const cardSel = document.getElementById('stage-card-model-images');
      if (cardSel && cardSel.value !== stageVal) cardSel.value = stageVal;
    }

    function syncCloudVisualControls() {
      const isCloud = isCloudAccelerationActive();
      updateVisualStyleOptions(isCloud);
      updateCheckpointControls(isCloud);
    }

    async function loadImageModels() {
      try {
        const d = await apiJson('/api/images/models');


        if (d.models && d.models.length) {
          cachedLocalCheckpoints = d.models;
        }
        if (!isCloudAccelerationActive()) {
          const sel = document.getElementById('checkpoint-select');
          if (!sel) return;
          const cur = sel.value;
          sel.innerHTML = '';
          cachedLocalCheckpoints.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = formatModelLabel(m);
            if (m.includes('juggernaut')) opt.selected = true;
            sel.appendChild(opt);
          });
          if (cur && cachedLocalCheckpoints.includes(cur)) sel.value = cur;
        }
      } catch (_) {}
    }

    function onCreatorStyleChange(styleKey) {
      // Suggest matching top motion banner style
      const bannerEl = document.getElementById('creator-callout-style');
      if (bannerEl) {
        if (styleKey === 'ink_wash_history' || styleKey === 'vintage_archive') {
          bannerEl.value = 'archival_parchment';
        } else if (styleKey === 'tech_schematic') {
          bannerEl.value = 'fox_kinetic';
        } else if (styleKey === 'photorealistic_cinema' || styleKey === 'cinematic_documentary') {
          bannerEl.value = 'modern_pill';
        }
      }

      if (isCloudAccelerationActive()) return;
      const sel = document.getElementById('checkpoint-select');
      if (!sel) return;
      if (styleKey === 'photorealistic_cinema' || styleKey.includes('photorealistic') || styleKey.includes('vintage') || styleKey.includes('cinematic')) {
        for (let i = 0; i < sel.options.length; i++) {
          if (sel.options[i].value.includes('juggernaut')) {
            sel.selectedIndex = i;
            break;
          }
        }
      } else if (styleKey.includes('anime') || styleKey.includes('shinkai') || styleKey.includes('ghibli')) {
        for (let i = 0; i < sel.options.length; i++) {
          if (sel.options[i].value.includes('base_1.0') || sel.options[i].value.includes('anime')) {
            sel.selectedIndex = i;
            break;
          }
        }
      }
    }

    function formatDuration(sec) {
      if (sec === undefined || sec === null || isNaN(sec) || sec <= 0) return '< 1s';
      if (sec < 1) return `${Math.max(0.1, Number(sec)).toFixed(1)}s`;
      if (sec < 10 && Math.round(sec * 10) % 10 !== 0) return `${Number(sec).toFixed(1)}s`;
      const s = Math.round(sec);
      const m = Math.floor(s / 60);
      const remS = s % 60;
      if (m === 0) return `${remS}s`;
      const h = Math.floor(m / 60);
      const remM = m % 60;
      if (h === 0) return `${m}m ${remS < 10 ? '0' : ''}${remS}s`;
      return `${h}h ${remM < 10 ? '0' : ''}${remM}m ${remS < 10 ? '0' : ''}${remS}s`;
    }

    function getStageDurationBadgeHtml(st) {
      if (!st) return '';
      if (st.status === 'COMPLETED') {
        const d = (st.duration_seconds !== undefined && st.duration_seconds !== null && st.duration_seconds > 0) ? st.duration_seconds : 0.1;
        return `<span style="color:#6ee7b7; font-weight:600;" title="Stage creation time: ${d}s">⏱️ ${formatDuration(d)}</span>`;
      }
      if (st.status === 'RUNNING' && st.started_at) {
        const elapsed = Math.max(0.1, (Date.now() - new Date(st.started_at).getTime()) / 1000);
        return `<span style="color:#60a5fa; font-weight:600;">⏱️ ${formatDuration(elapsed)}...</span>`;
      }
      if (st.duration_seconds && st.duration_seconds > 0) {
        return `<span style="color:#94a3b8; font-weight:600;">⏱️ ${formatDuration(st.duration_seconds)}</span>`;
      }
      return '';
    }

    async function loadProjectsList() {
      try {
        const projects = await apiJson('/api/projects');

        allProjectsCache = projects || [];
        const sel = document.getElementById('global-project-select');
        const prevSel = document.getElementById('preview-project-select');
        if (sel) sel.innerHTML = '';
        if (prevSel) prevSel.innerHTML = '';

        if (!projects || projects.length === 0) {
          if (sel) sel.innerHTML = '<option value="">No Projects Yet</option>';
          if (prevSel) prevSel.innerHTML = '<option value="">No Projects Yet</option>';
          currentProjectId = null;
          localStorage.removeItem('active_project_id');
          document.getElementById('global-hero-banner').style.display = 'none';
          const projTitleEl = document.getElementById('proj-title');
          if (projTitleEl) projTitleEl.textContent = 'No Projects Available';
          const projActEl = document.getElementById('proj-activity');
          if (projActEl) projActEl.textContent = 'Create a new video project above.';
          const projState = document.getElementById('proj-state');
          if (projState) { projState.textContent = 'IDLE'; projState.className = 'badge badge-warn'; }
          const stagesEl = document.getElementById('stages-container');
          if (stagesEl) stagesEl.innerHTML = '<div style="color:var(--text-muted); padding:20px;">No projects available.</div>';
          const wsEl = document.getElementById('studio-stage-workspace');
          if (wsEl) {
            wsEl.innerHTML = `
              <div style="text-align: center; padding: 60px 20px; color: var(--text-muted);">
                <div style="font-size: 36px; margin-bottom: 12px;">🛠️</div>
                <h3 style="color: #fff; margin-bottom: 8px;">No Project Selected</h3>
                <p style="font-size: 13px; max-width: 480px; margin: 0 auto 20px auto;">Please create a new project in the Creator tab to use the Stage Studio.</p>
                <button onclick="switchTab('creator')">Go to Creator</button>
              </div>
            `;
          }
          const stepperEl = document.getElementById('studio-stepper');
          if (stepperEl) stepperEl.innerHTML = '';
          const vPlayer = document.getElementById('final-video-player');
          if (vPlayer) { vPlayer.src = ''; vPlayer.style.display = 'none'; }
          const noVidEl = document.getElementById('preview-no-video');
          if (noVidEl) noVidEl.style.display = 'block';
          return;
        }

        projects.forEach(p => {
          const opt = document.createElement('option');
          opt.value = p.id;
          const statusIcon = p.state === 'running' ? '🟢 RUNNING: ' : (p.state === 'completed' ? '✓ ' : '');
          const durText = (p.state === 'completed' && p.total_duration_seconds) ? ` (⏱️ ${formatDuration(p.total_duration_seconds)})` : '';
          const dispTitle = p.title || p.topic || p.id;
          opt.textContent = `${projectModeOf(p) === 'short_drama' ? '🎭 ' : '🎬 '}${statusIcon}[${p.id}] ${dispTitle}${durText}`;
          if (p.id === currentProjectId) opt.selected = true;
          if (sel) sel.appendChild(opt);

          if (prevSel) {
            const prevOpt = document.createElement('option');
            prevOpt.value = p.id;
            const hasFinal = Boolean(p.outputs && p.outputs.final);
            const readyTag = hasFinal ? '▶ [1080p 可播放] ' : (p.state === 'running' ? '⏳ [生成中] ' : '⏸️ [無影片] ');
            prevOpt.textContent = `${readyTag}${projectModeOf(p) === 'short_drama' ? '🎭 ' : '🎬 '}[${p.id}] ${dispTitle}${durText}`;
            if (p.id === currentProjectId) prevOpt.selected = true;
            prevSel.appendChild(prevOpt);
          }
        });

        // Auto-select:
        // 1. If currently running project exists, pick it
        // 2. Else pick currentProjectId if valid
        // 3. Else pick first in list
        const runningProj = projects.find(p => p.state === 'running');
        if (runningProj) {
          selectProject(runningProj.id);
        } else if (currentProjectId && projects.some(p => p.id === currentProjectId)) {
          selectProject(currentProjectId);
        } else {
          selectProject(projects[0].id);
        }
      } catch (e) {
        console.error("Failed to load projects", e);
      }
    }

    function onSwitchProject(pId) {
      if (!pId) return;
      selectProject(pId);
    }

    async function deleteCurrentProject(targetId) {
      const pId = targetId || currentProjectId;
      if (!pId) return alert("No active project selected to delete.");

      const sel = document.getElementById('global-project-select');
      const optText = (sel && sel.selectedOptions && sel.selectedOptions[0]) ? sel.selectedOptions[0].textContent : pId;
      const cleanTitle = optText.replace(/^[🟢✓\s]+(RUNNING:\s*)?/, '').trim();

      const msg = `⚠️ DANGER: Permanently delete project "${cleanTitle}" (${pId})?\n\nThis will completely delete ALL content files on disk:\n• Narration script & research\n• Scene planning & visual prompts\n• All generated image takes & variations\n• All voice clips & audio takes\n• Subtitles & final rendered MP4\n\nThis action CANNOT be undone!`;

      if (!confirm(msg)) return;

      try {
        const data = await apiJson(`/api/projects/${pId}`, { method: 'DELETE' });



        if (currentProjectId === pId) {
          if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
          }
          stopTimer();
          currentProjectId = null;
          currentScenes = [];
          studioStageData = null;
          studioProject = null;
          inspectedStageData = null;
          localStorage.removeItem('active_project_id');
        }

        alert(`✓ Project "${cleanTitle}" and all its content files were permanently deleted.`);

        await loadProjectsList();
      } catch (err) {
        alert("Failed to delete project: " + err.message);
      }
    }

    function selectProject(pId) {
      if (currentProjectId !== pId) {
        const stagesEl = document.getElementById('stages-container');
        if (stagesEl) stagesEl.innerHTML = '';
      }
      currentProjectId = pId;
      if (typeof allProjectsCache !== 'undefined' && allProjectsCache.length) {
        currentProject = allProjectsCache.find(p => p.id === pId) || null;
      }
      localStorage.setItem('active_project_id', pId);
      const gSel = document.getElementById('global-project-select');
      if (gSel) gSel.value = pId;
      const pSel = document.getElementById('preview-project-select');
      if (pSel) pSel.value = pId;

      document.getElementById('global-hero-banner').style.display = 'block';
      if (pId) {
        apiJson('/api/projects/' + pId).then(proj => {
          if (proj) {
            currentProject = proj.project || proj;
            studioProject = proj.project || proj;
          }
          if (proj && proj.settings) {
            const conclEl = document.getElementById('creator-author-conclusion');
            if (conclEl && proj.settings.author_conclusion) {
              conclEl.value = proj.settings.author_conclusion;
            }
          }
        }).catch(() => {});
      }
      const studioTab = document.getElementById('tab-studio');
      if (studioTab && studioTab.classList.contains('active')) {
        loadStageStudio();
      }
      const previewTab = document.getElementById('tab-preview');
      if (previewTab && previewTab.classList.contains('active')) {
        updatePreviewMedia();
      }
      startPolling();
    }

    function startTimer() {
      if (timerInterval) clearInterval(timerInterval);
      if (!projectStartTime) projectStartTime = Date.now();
      timerInterval = setInterval(() => {
        const diff = Math.floor((Date.now() - projectStartTime) / 1000);
        const mins = String(Math.floor(diff / 60)).padStart(2, '0');
        const secs = String(diff % 60).padStart(2, '0');
        document.getElementById('hero-elapsed-timer').textContent = `⏱️ ${mins}:${secs}`;
      }, 1000);
    }

    function stopTimer() {
      if (timerInterval) clearInterval(timerInterval);
      timerInterval = null;
    }

    function setVal(id, val) {
      const el = document.getElementById(id);
      if (el) el.value = val;
    }

    function applyStageModelPreset(preset) {
      const isDrama = currentCreatorProjectMode === 'short_drama';
      if (preset === 'local') {
        setVal('model-stage-research', 'ollama');
        setVal('model-stage-script', 'ollama');
        setVal('model-stage-scenes', 'ollama');
        setVal('model-stage-prompts', 'ollama');
        setVal('model-stage-images', 'comfyui');
        setVal('model-stage-voice', 'bluemagpie');
        setVal('model-stage-animation', isDrama ? 'local_actor' : 'kenburns');
        setVal('model-stage-subtitles', 'local');
        setVal('model-stage-render', 'h264_amf');
        setVal('cloud-toggle', 'false');
      } else if (preset === 'cloud') {
        setVal('model-stage-research', isDrama ? 'gemini' : 'gemini_search');
        setVal('model-stage-script', 'gemini');
        setVal('model-stage-scenes', 'gemini');
        setVal('model-stage-prompts', 'gemini');
        setVal('model-stage-images', 'nano-banana-2.1');
        setVal('checkpoint-select', 'nano-banana-2.1');
        setVal('model-stage-voice', 'elevenlabs');
        setVal('model-stage-animation', isDrama ? 'hedra' : 'veo');
        setVal('model-stage-subtitles', 'local');
        setVal('model-stage-render', 'h264_amf');
        setVal('cloud-toggle', 'true');
      } else if (preset === 'hybrid') {
        setVal('model-stage-research', isDrama ? 'gemini' : 'gemini_search');
        setVal('model-stage-script', 'gemini');
        setVal('model-stage-scenes', 'gemini');
        setVal('model-stage-prompts', 'gemini');
        setVal('model-stage-images', isDrama ? 'nano-banana-2.1' : 'comfyui');
        setVal('model-stage-voice', 'bluemagpie');
        setVal('model-stage-animation', isDrama ? 'hedra' : 'kenburns');
        setVal('model-stage-subtitles', 'local');
        setVal('model-stage-render', 'h264_amf');
        setVal('cloud-toggle', 'true');
      }
      onStageModelChange();
      if (currentProjectId) {
        const sm = getSelectedStageModels();
        apiRequest(`/api/projects/${currentProjectId}/stage-models`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage_models: sm })
        }).then(() => {
          showToast(`⚡ Applied "${preset.toUpperCase()}" preset! Dynamic stage models updated.`);
        }).catch(e => console.error(e));
      }
    }

    function onCloudToggleChange(val) {
      if (val === 'false') {
        applyStageModelPreset('local');
      } else {
        applyStageModelPreset('cloud');
      }
    }

    function getStageModelOptions(stName, isDrama = false) {
      if (isDrama) {
        if (stName === 'research') {
          return [
            { val: 'gemini', label: 'Cloud: Gemini 3.8 Flash (推薦)' },
            { val: 'ollama', label: 'Local: Ollama (qwen3:8b)' },
            { val: 'openai_compat', label: 'Cloud: GPT-4o-mini' }
          ];
        }
        if (stName === 'animation') {
          return [
            { val: 'hedra', label: '🎭 Cloud: Hedra Character-2 (精準口型)' },
            { val: 'local_actor', label: '🖥️ Local: Audio-Reactive Actor' },
            { val: 'kling', label: '⚡ Cloud: Kling AI Avatar' }
          ];
        }
        if (stName === 'images') {
          return CANONICAL_IMAGE_ENGINES.filter(e => e.val !== 'stock');
        }
      }
      switch (stName) {
        case 'research':
          return [
            { val: 'gemini_search', label: 'Cloud: Gemini Search' },
            { val: 'ollama', label: 'Local: Ollama' },
            { val: 'none', label: 'Disabled' }
          ];
        case 'script':
        case 'scenes':
        case 'prompts':
          return [
            { val: 'ollama', label: 'Local GPU: Ollama' },
            { val: 'gemini', label: 'Cloud: Gemini Flash' },
            { val: 'openai_compat', label: 'Cloud: GPT-4o-mini' }
          ];
        case 'images':
          return CANONICAL_IMAGE_ENGINES;
        case 'voice':
          return [
            { val: 'bluemagpie', label: 'Local: BlueMagpie Voice' },
            { val: 'cosyvoice', label: 'Local: CosyVoice 2 Voice' },
            { val: 'http_clone', label: 'Local: F5-TTS (HTTP Clone)' },
            { val: 'voai', label: 'Cloud: VoAI 絕好聲創 (TW)' },
            { val: 'elevenlabs', label: 'Cloud: ElevenLabs Studio' },
            { val: 'edge', label: 'Cloud: Edge TTS (Free)' },
            { val: 'sapi', label: 'Local: Windows SAPI' }
          ];
        case 'animation':
          return [
            { val: 'remotion', label: '⚡ Remotion: Tech Cyberpunk Cards' },
            { val: 'remotion_minimalist', label: '📐 Remotion: Minimalist Swiss Cards' },
            { val: 'remotion_cinema', label: '🎬 Remotion: Cinema Impact Cards' },
            { val: 'kenburns', label: 'Local: Ken Burns 2.5D (Fast)' },
            { val: 'stock_video', label: 'Free: Stock Video B-Roll' },
            { val: 'comfyui_video', label: 'Local GPU: ComfyUI Video' },
            { val: 'veo', label: 'Cloud: Google Veo' },
            { val: 'kling', label: 'Cloud: Kling Video' },
            { val: 'runway', label: 'Cloud: Runway Gen-3' },
            { val: 'hedra', label: 'Cloud: Hedra Character Video' }
          ];
        case 'subtitles':
          return [
            { val: 'local', label: 'Local: Subtitle Engine' }
          ];
        case 'render':
          return [
            { val: 'h264_amf', label: 'Local GPU: AMD AMF (RX 9060)' },
            { val: 'libx264', label: 'Local CPU: libx264' }
          ];
        default:
          return [];
      }
    }

    function getStageModelFriendlyName(stName, val) {
      const opts = getStageModelOptions(stName);
      const found = opts.find(o => o.val === val);
      return found ? found.label : val;
    }

    function getProjectStageModel(p, stName) {
      if (p && p.settings && p.settings.stage_models && p.settings.stage_models[stName]) {
        return p.settings.stage_models[stName];
      }
      if (p && p.data && p.data.settings && p.data.settings.stage_models && p.data.settings.stage_models[stName]) {
        return p.data.settings.stage_models[stName];
      }
      const topEl = document.getElementById('model-stage-' + stName);
      if (topEl) return topEl.value;
      const defs = {
        research: 'gemini_search',
        script: 'ollama',
        scenes: 'ollama',
        prompts: 'ollama',
        images: 'comfyui',
        voice: 'bluemagpie',
        animation: 'kenburns',
        subtitles: 'local',
        render: 'h264_amf'
      };
      return defs[stName] || '';
    }

    async function changeStageModelFromCard(stName, modelVal) {
      if (!currentProjectId) return;
      try {
        await apiRequest(`/api/projects/${currentProjectId}/stage-models`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage_models: { [stName]: modelVal } })
        })

          const topSel = document.getElementById('model-stage-' + stName);
          if (topSel) topSel.value = modelVal;
          onStageModelChange();
          const fn = getStageModelFriendlyName(stName, modelVal);
          showToast(`⚡ ${stName.toUpperCase()} switched to ${fn}! Applied to upcoming & active scenes.`);

      } catch (e) {
        console.error("Failed to switch stage model from card:", e);
        showToast(`⚠️ Error switching ${stName} model: ${e.message}`);
      }
    }

    function onStageModelChange(changedStage) {
      const cloudOpts = ['gemini_search', 'gemini', 'openai_compat', 'fal-ai/flux-1/schnell', 'nano-banana-2.1', 'gpt-image-1', 'imagen-3.0-generate-002', 'dalle3', 'imagen3', 'stock', 'stock_video', 'elevenlabs', 'voai', 'edge', 'veo', 'kling', 'runway', 'hedra'];
      const stages = ['research', 'script', 'scenes', 'prompts', 'images', 'voice', 'animation', 'subtitles', 'render'];
      let cloudCount = 0;
      let localCount = 0;
      stages.forEach(st => {
        const el = document.getElementById('model-stage-' + st);
        if (el) {
          if (cloudOpts.includes(el.value)) cloudCount++;
          else localCount++;
        }
      });
      const badge = document.getElementById('stage-model-mode-badge');
      if (badge) {
        if (cloudCount === 0) {
          badge.className = 'badge badge-ok';
          badge.textContent = '100% Local GPU/CPU';
        } else if (localCount <= 2) {
          badge.className = 'badge badge-warn';
          badge.textContent = `Cloud Accelerated (${cloudCount} Cloud Stages)`;
        } else {
          badge.className = 'badge badge-blue';
          badge.textContent = `Hybrid (${localCount} Local, ${cloudCount} Cloud)`;
        }
      }
      syncCloudVisualControls();

      // 1. Stage 5 Images <-> Checkpoint Sync
      const _stImg = document.getElementById('model-stage-images');
      const _ckSel = document.getElementById('checkpoint-select');
      const _hintImg = document.getElementById('stage-images-sync-hint');
      if (_stImg && _ckSel) {
        if (_ckSel.value !== _stImg.value) {
          _ckSel.value = _stImg.value;
        }
        if (_hintImg) {
          _hintImg.innerHTML = `🔗 Synced: <b>${formatModelLabel(_stImg.value)}</b>`;
        }
      }

      // 2. Stage 6 Voice <-> Voice Profile Sync
      if ((changedStage === 'voice' || !changedStage) && typeof onStageVoiceModelChange === 'function') {
        onStageVoiceModelChange();
      }

      // 3. Stage 7 Music <-> Progression / Category Sync
      const _stMusic = document.getElementById('model-stage-music');
      const _progSel = document.getElementById('music-progression-select');
      const _catSel = document.getElementById('music-category-select');
      const _hintMusic = document.getElementById('stage-music-sync-hint');
      if (_stMusic) {
        const mVal = _stMusic.value;
        if (changedStage === 'music') {
          if (mVal === 'none') {
            if (_catSel && _catSel.value !== 'none') {
              _catSel.value = 'none';
              if (typeof onCreatorMusicCategoryChange === 'function') onCreatorMusicCategoryChange('none');
            }
          } else {
            if (_catSel && _catSel.value === 'none') {
              _catSel.value = 'auto';
              if (typeof onCreatorMusicCategoryChange === 'function') onCreatorMusicCategoryChange('auto');
            }
            if (_progSel && _progSel.value !== mVal) {
              _progSel.value = mVal;
            }
          }
        }
        if (_hintMusic) {
          const mLabel = mVal === 'none' ? '無配樂 (Silent)' : (mVal === 'narrative_evolving' ? '多樂章演進 (3-Movement)' : '單曲循環 (Loop)');
          _hintMusic.innerHTML = `🔗 Synced: <b>${mLabel}</b>`;
        }
      }

      // 4. Stage 8 Animation <-> Remotion Strip & AI Video Pct Sync
      const _stAnim = document.getElementById('model-stage-animation');
      const _aiPct = document.getElementById('ai-video-pct');
      const _hintAnim = document.getElementById('stage-animation-sync-hint');
      if (_stAnim) {
        const aVal = _stAnim.value;
        if (aVal.startsWith('remotion')) {
          updateCreatorRemotionStrip();
          if (changedStage === 'animation') {
            if (_aiPct && _aiPct.value !== '0') _aiPct.value = '0';
          }
          if (_hintAnim) {
            _hintAnim.innerHTML = `🔗 Synced: <b>Remotion (${aVal.replace('remotion_', '').replace('remotion', 'blueprint')})</b>`;
          }
        } else if (aVal === 'kenburns') {
          updateCreatorRemotionStrip();
          if (changedStage === 'animation') {
            if (_aiPct && _aiPct.value !== '0') _aiPct.value = '0';
          }
          if (_hintAnim) {
            _hintAnim.innerHTML = `🔗 Synced: <b>Ken Burns 2.5D Motion</b>`;
          }
        } else if (['veo', 'kling', 'runway', 'hedra', 'comfyui_video'].includes(aVal)) {
          updateCreatorRemotionStrip();
          if (changedStage === 'animation') {
            if (_aiPct && (_aiPct.value === '0' || !_aiPct.value)) _aiPct.value = '10';
          }
          if (_hintAnim) {
            _hintAnim.innerHTML = `🔗 Synced: <b>AI Video (${aVal.toUpperCase()})</b>`;
          }
        } else {
          updateCreatorRemotionStrip();
          if (_hintAnim) {
            _hintAnim.innerHTML = `🔗 Synced: <b>${aVal}</b>`;
          }
        }
      }

      if (changedStage && currentProjectId) {
        const el = document.getElementById('model-stage-' + changedStage);
        if (el) {
          const val = el.value;
          apiRequest(`/api/projects/${currentProjectId}/stage-models`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stage_models: { [changedStage]: val } })
          }).then(() => {
            const cardSel = document.getElementById('stage-card-model-' + changedStage);
            if (cardSel && cardSel.value !== val) cardSel.value = val;
            const fn = getStageModelFriendlyName(changedStage, val);
            showToast(`⚡ ${changedStage.toUpperCase()} switched to ${fn}! Dynamic mid-run engine updated.`);
          }).catch(err => {
            console.error('Failed to sync stage model to project:', err);
          });
        }
      }
    }

    function getSelectedStageModels() {
      const stages = ['research', 'script', 'scenes', 'prompts', 'images', 'voice', 'animation', 'subtitles', 'render'];
      const res = {};
      stages.forEach(st => {
        const el = document.getElementById('model-stage-' + st);
        if (el) res[st] = el.value;
      });
      return res;
    }

    function populateStageModelsFromProject(p) {
      if (!p || !p.settings) return;
      if (p.settings.stage_models) {
        const sm = p.settings.stage_models;
        Object.keys(sm).forEach(st => {
          const el = document.getElementById('model-stage-' + st);
          if (el && sm[st]) el.value = sm[st];
          const cardSel = document.getElementById('stage-card-model-' + st);
          if (cardSel && sm[st] && cardSel.value !== sm[st]) cardSel.value = sm[st];
        });
      }
      if (p.settings.cloud && typeof p.settings.cloud.enabled === 'boolean') {
        setVal('cloud-toggle', p.settings.cloud.enabled ? 'true' : 'false');
      }
      onStageModelChange();
    }

    async function updateStudioStageModel(stKey, modelVal) {
      if (!currentProjectId) return;
      try {
        await apiRequest(`/api/projects/${currentProjectId}/stage-models`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage_models: { [stKey]: modelVal } })
        })

          const el = document.getElementById('model-stage-' + stKey);
          if (el) el.value = modelVal;
          const cardSel = document.getElementById('stage-card-model-' + stKey);
          if (cardSel) cardSel.value = modelVal;
          if (stKey === 'images') {
            const ckSel = document.getElementById('checkpoint-select');
            if (ckSel && ckSel.value !== modelVal) ckSel.value = modelVal;
          }
          onStageModelChange(stKey);
          const fn = getStageModelFriendlyName(stKey, modelVal);
          showToast(`⚡ ${stKey.toUpperCase()} switched to ${fn}! Applied to upcoming & active scenes.`);
          // Reload stage workspace
          if (typeof openStudioStage === 'function') openStudioStage(stKey);

      } catch (e) {
        console.error('Failed to update stage model:', e);
        showToast(`⚠️ Failed to update ${stKey} model: ${e.message}`);
      }
    }

    // ---------------- Creator Advanced Settings Toggle ----------------
    function toggleCreatorAdvancedSettings(forceOpen) {
      const panel = document.getElementById('creator-advanced-options-container');
      const btn = document.getElementById('btn-toggle-advanced-creator');
      const txt = document.getElementById('adv-toggle-text');
      const icon = document.getElementById('adv-toggle-icon');
      if (!panel) return;
      const isHidden = panel.style.display === 'none' || panel.style.display === '';
      const shouldOpen = forceOpen !== undefined ? forceOpen : isHidden;
      panel.style.display = shouldOpen ? 'block' : 'none';
      if (txt) txt.textContent = shouldOpen ? '收起進階微調設定 (▲)' : '進階微調與專業配置 (展開 4 大項進階參數 ▼)';
      if (icon) icon.textContent = shouldOpen ? '▲' : '⚙️';
      if (btn) {
        btn.style.borderColor = shouldOpen ? 'var(--gold)' : 'rgba(124, 145, 182, 0.35)';
        btn.style.boxShadow = shouldOpen ? '0 0 12px rgba(193, 157, 73, 0.3)' : '';
      }
    }

    function toggleProjectAdvancedActions(forceOpen) {
      const panel = document.getElementById('project-advanced-actions-strip');
      const btn = document.getElementById('btn-toggle-proj-actions');
      if (!panel) return;
      const isHidden = panel.style.display === 'none' || panel.style.display === '';
      const shouldOpen = forceOpen !== undefined ? forceOpen : isHidden;
      panel.style.display = shouldOpen ? 'flex' : 'none';
      if (btn) btn.textContent = shouldOpen ? '⚙️ 收起導出選項 (▲)' : '⚙️ 更多導出選項 (More Export Options ▼)';
    }

    function toggleHeroTools(forceOpen) {
      const panel = document.getElementById('hero-tools-dropdown');
      const btn = document.getElementById('hero-btn-tools');
      if (!panel) return;
      const isHidden = panel.style.display === 'none' || panel.style.display === '';
      const shouldOpen = forceOpen !== undefined ? forceOpen : isHidden;
      panel.style.display = shouldOpen ? 'flex' : 'none';
      if (btn) btn.textContent = shouldOpen ? '🛠️ 收起微調工具 ▲' : '🛠️ 快速工具 ▼';
    }

    // ---------------- Creator Custom Research Management ----------------
    function toggleCreatorResearchCard(forceOpen) {
      const body = document.getElementById('creator-research-body');
      const btn = document.getElementById('btn-toggle-creator-research');
      if (!body) return;
      const willOpen = forceOpen !== undefined ? forceOpen : (body.style.display === 'none' || !body.style.display);
      body.style.display = willOpen ? 'block' : 'none';
      if (btn) btn.textContent = willOpen ? '▲ 收合' : '▼ 展開編輯';
      if (willOpen) {
        const ta = document.getElementById('creator-user-research');
        if (ta && !ta.value.trim()) ta.focus();
      }
    }

    function onCreatorResearchInput() {
      const ta = document.getElementById('creator-user-research');
      if (!ta) return;
      const val = ta.value;
      const charCount = val.length;
      const wordCount = val.trim() ? val.trim().split(/\s+/).length : 0;

      const charEl = document.getElementById('creator-research-char-count');
      const wordEl = document.getElementById('creator-research-word-count');
      const badge = document.getElementById('creator-research-badge');
      const pill = document.getElementById('creator-research-count-pill');

      if (charEl) charEl.textContent = charCount.toLocaleString();
      if (wordEl) wordEl.textContent = wordCount.toLocaleString();

      if (charCount > 0) {
        if (badge) {
          badge.textContent = `✅ 已載入自訂研究 (${charCount} 字)`;
          badge.style.background = 'rgba(16, 185, 129, 0.2)';
          badge.style.color = '#34d399';
          badge.style.border = '1px solid rgba(16, 185, 129, 0.4)';
        }
        if (pill) {
          pill.style.display = 'inline-block';
          pill.textContent = `${charCount} 字`;
        }
      } else {
        if (badge) {
          badge.textContent = '可選 (預設由 AI 聯網研究)';
          badge.style.background = 'rgba(148, 163, 184, 0.2)';
          badge.style.color = '#94a3b8';
          badge.style.border = '';
        }
        if (pill) {
          pill.style.display = 'none';
        }
      }
    }

    function onCreatorResearchModeChange() {
      const modeEl = document.querySelector('input[name="creator-research-mode"]:checked');
      const mode = modeEl ? modeEl.value : 'hybrid';
      if (mode === 'user_only') {
        showToast('🔒 已設定為完全採用自訂研究：Stage 1 將跳過聯網搜尋');
      } else {
        showToast('⚖️ 已設定為混合模式：優先採用自訂研究，AI 聯網補充佐證');
      }
    }

    function clearCreatorResearch(force = false) {
      const ta = document.getElementById('creator-user-research');
      if (!ta) return;
      if (!force && ta.value.trim() && ta.value.length > 50 && !confirm('確定要清空已填寫的自訂研究資料嗎？')) {
        return;
      }
      ta.value = '';
      onCreatorResearchInput();

      const fileInput = document.getElementById('creator-research-file-input');
      if (fileInput) fileInput.value = '';

      const statusEl = document.getElementById('creator-research-upload-status');
      if (statusEl) {
        statusEl.innerHTML = '';
        statusEl.style.display = 'none';
      }

      const pauseEl = document.getElementById('creator-pause-after-research');
      if (pauseEl) pauseEl.checked = false;

      const modeHybrid = document.querySelector('input[name="creator-research-mode"][value="hybrid"]');
      if (modeHybrid) modeHybrid.checked = true;

      toggleCreatorResearchCard(false);

      if (!force) {
        showToast('🧹 已清空自訂研究資料');
      }
    }

    function insertCreatorResearchTemplate() {
      toggleCreatorResearchCard(true);
      const ta = document.getElementById('creator-user-research');
      if (!ta) return;
      const template = `### 核心論點 (Core Thesis)
- [請在此填寫影片最核心想傳達的觀點或反轉]

### 關鍵事實與真實數據 (Verified Facts & Data)
- 數據1：
- 數據2：
- 歷史或科學依據：

### 必須提及之案例、人物或專有名詞 (Key Entities)
- 人物/角色/品牌：
- 專有名詞與精確中文翻譯：

### 敘事結構與語氣指示 (Tone & Narrative Style)
- 開場鉤子：
- 語氣：生動客觀、節奏緊湊、避免俗套開場白

### 嚴格闢謠或禁止提及事項 (Negative Directives)
- 請勿提及：
- 常見誤區闢謠：`;

      if (ta.value.trim() && !confirm('是否將結構範本插入到現有內容後方？')) {
        return;
      }
      ta.value = ta.value.trim() ? `${ta.value.trim()}\n\n${template}` : template;
      onCreatorResearchInput();
      showToast('📝 已載入結構化研究範本');
    }

    function importTrendProofToCreatorResearch() {
      toggleCreatorResearchCard(true);
      const ta = document.getElementById('creator-user-research');
      if (!ta) return;

      const titleEl = document.getElementById('proof-topic-title') || document.getElementById('topic');
      const platEl = document.getElementById('proof-platform');
      const metEl = document.getElementById('proof-metrics');
      const hlEl = document.getElementById('proof-headline');
      const urlEl = document.getElementById('proof-url');
      const whyEl = document.getElementById('proof-why');

      const title = titleEl ? (titleEl.textContent || titleEl.value || '').trim() : '';
      const platform = platEl ? platEl.textContent.trim() : '';
      const metrics = metEl ? metEl.textContent.trim() : '';
      const headline = hlEl ? hlEl.textContent.trim() : '';
      const url = (urlEl && urlEl.href && urlEl.href !== '#' && !urlEl.href.endsWith('#')) ? urlEl.href : '';
      const why = whyEl ? whyEl.textContent.trim() : '';

      if (!title && !headline && !url) {
        showToast('⚠️ 請先在上方 Trend Scout 選擇或探索一個熱搜話題');
        return;
      }

      let importedNotes = `### 【熱搜話題佐證資料】${title ? title : ''}\n`;
      if (platform) importedNotes += `- 來源平台: ${platform}\n`;
      if (metrics) importedNotes += `- 即時熱度/佐證: ${metrics}\n`;
      if (headline) importedNotes += `- 引述頭條/新聞: ${headline}\n`;
      if (url) importedNotes += `- 原始佐證連結: ${url}\n`;
      if (why) importedNotes += `- 爆款潛力解析: ${why}\n`;

      ta.value = ta.value.trim() ? `${importedNotes}\n${ta.value.trim()}` : importedNotes;
      onCreatorResearchInput();
      showToast('📋 已將熱門話題佐證數據匯入為研究資料！');
    }

    async function handleCreatorResearchFileUpload(event) {
      const input = event.target;
      if (!input.files || input.files.length === 0) return;
      const file = input.files[0];
      const statusEl = document.getElementById('creator-research-upload-status');
      toggleCreatorResearchCard(true);

      if (statusEl) {
        statusEl.style.display = 'block';
        statusEl.innerHTML = `⏳ 正在解析文件 <strong>${file.name}</strong> (${(file.size / 1024).toFixed(1)} KB)...`;
      }

      const formData = new FormData();
      formData.append('file', file);

      try {
        const data = await apiJson('/api/projects/parse_research_file', {
          method: 'POST',
          body: formData
        });




        const ta = document.getElementById('creator-user-research');
        if (ta) {
          const header = `### 【文件素材：${data.filename}】\n`;
          const content = `${header}${data.text}`;
          ta.value = ta.value.trim() ? `${ta.value.trim()}\n\n${content}` : content;
          onCreatorResearchInput();
        }

        if (statusEl) {
          statusEl.innerHTML = `✅ 成功解析文件 <strong>${data.filename}</strong>（共 ${data.char_count} 字）`;
          setTimeout(() => { if (statusEl) statusEl.style.display = 'none'; }, 4000);
        }
        showToast(`📁 成功解析並匯入 ${data.filename} (${data.char_count} 字)`);
      } catch (err) {
        console.warn('Backend parse failed, attempting local fallback...', err);
        const ext = file.name.split('.').pop().toLowerCase();
        if (['txt', 'md', 'markdown', 'json', 'csv'].includes(ext)) {
          const reader = new FileReader();
          reader.onload = function(e) {
            const clientText = e.target.result;
            const ta = document.getElementById('creator-user-research');
            if (ta && clientText) {
              const header = `### 【文件素材：${file.name}】\n`;
              ta.value = ta.value.trim() ? `${ta.value.trim()}\n\n${header}${clientText}` : `${header}${clientText}`;
              onCreatorResearchInput();
            }
            if (statusEl) {
              statusEl.innerHTML = `✅ 本地解析文件 <strong>${file.name}</strong> 成功`;
              setTimeout(() => { if (statusEl) statusEl.style.display = 'none'; }, 4000);
            }
            showToast(`📁 成功以文字模式載入 ${file.name}`);
          };
          reader.onerror = function() {
            alert(`無法讀取文件: ${err.message}`);
            if (statusEl) statusEl.style.display = 'none';
          };
          reader.readAsText(file);
        } else {
          alert(`文件解析失敗: ${err.message}`);
          if (statusEl) statusEl.style.display = 'none';
        }
      } finally {
        input.value = '';
      }
    }

    // ==========================================
    // AI Micro Short Drama Mode (AI 微短劇模式) & Character Cast Roster
    // ==========================================
    let currentCreatorProjectMode = 'documentary';
    let cachedCharactersLibrary = [];
    let currentProjectDramaCharacters = [];

    const DRAMA_FORMULAS_PRESETS = {
      workplace_revenge: {
        id: "workplace_revenge",
        name: "職場逆襲打臉（如《開除我？那套AI是我寫的》）",
        default_script: `王經理居高臨下將解雇通知狠狠摔在桌面上，嘴角揚起傲慢冷笑：「從今天起，妳被AI取代了。新系統一個月才一千塊。妳呢？」\n沈總監端坐辦公椅，神色自若：「你確定要換掉我？那套系統的核心架構……是我寫的。」\n沈總監優雅地在機械鍵盤上按下回車鍵，終端顯示「權限已撤銷」。\n辦公室大門猛然被推開，白髮威嚴的陳董事長帶著隨扈大步走入：「住手！王經理，你知不知道你在跟誰講話？！總部剛剛估值十億的AI專利，唯一的所有人就是沈總監！」\n沈總監拎起公事包從容起身：「王經理，一個月一千塊的系統，祝你維護愉快。」`,
        default_characters: [
          {
            id: "shen_director",
            name: "沈總監",
            role: "女主角 / 隱藏核心系統總架構師",
            gender: "female",
            age: 28,
            appearance: "28-year-old sleek elegant East Asian woman, sharp confident eyes, minimalist charcoal blazer, modern professional look, high detail, studio lighting, photorealistic portrait",
            voice_persona: "冷靜沉穩、字句分明、略帶威嚴的年輕女聲",
            voice_profile: "ichiehchieh",
            image_url: "/api/characters/image/shen_director"
          },
          {
            id: "manager_wang",
            name: "王經理",
            role: "反派主管 / 自負傲慢的中年業務主管",
            gender: "male",
            age: 48,
            appearance: "48-year-old arrogant middle-aged East Asian man, receding hairline, rimless gold glasses, navy corporate suit, smug condescending expression, photorealistic portrait",
            voice_persona: "語速偏快、帶嘲諷冷笑與不耐煩的中年男聲",
            voice_profile: "mytsaovoicemagpie",
            image_url: "/api/characters/image/manager_wang"
          },
          {
            id: "chairman_chen",
            name: "陳董",
            role: "董事長 / 關鍵反轉掌控者",
            gender: "male",
            age: 60,
            appearance: "60-year-old authoritative silver-haired Asian chairman, charcoal bespoke tailored wool overcoat, piercing commanding gaze, cinematic lighting, photorealistic portrait",
            voice_persona: "渾厚深沉、極具壓迫感與威嚴的老闆男聲",
            voice_profile: "aurora_mandarin",
            image_url: "/api/characters/image/chairman_chen"
          }
        ]
      },
      suspense_twist: {
        id: "suspense_twist",
        name: "懸疑極限反轉（暗室審訊與雙重佈局）",
        default_script: `昏暗審訊室內，桌上計時器瘋狂跳動逼近歸零。\n趙長官大力拍桌：「陸警官，證據確鑿，把這份認罪協議簽了，免受皮肉之苦！」\n陸督察抬起頭，嘴角揚起神秘微笑：「趙長官，你難道沒發現，房間裡的監視器訊號，在三分鐘前就已經切換至特勤督察總隊了嗎？」\n門外轟然破門，荷槍實彈的督察小組迅速封鎖審訊室，扣押趙長官。陸督察從容亮出特勤金徽！`,
        default_characters: [
          {
            id: "inspector_lu",
            name: "陸督察",
            role: "男主角 / 偽裝成嫌犯的特勤高階督察",
            gender: "male",
            age: 32,
            appearance: "32-year-old ruggedly handsome East Asian investigator, calm penetrating eyes, black leather jacket, faint scar on eyebrow, dramatic high-contrast lighting, photorealistic portrait",
            voice_persona: "冷冽、低沉、掌控全域的青年男聲",
            voice_profile: "mytsaovoicemagpie",
            image_url: "/api/characters/image/inspector_lu"
          },
          {
            id: "officer_zhao",
            name: "趙長官",
            role: "反派 / 內鬼審訊官",
            gender: "male",
            age: 52,
            appearance: "52-year-old stern corrupted senior officer, heavy eyebags, unbuttoned police uniform, tense sweating forehead, dark moody atmosphere, photorealistic portrait",
            voice_persona: "急躁、沙啞且帶威脅口氣的中老年男聲",
            voice_profile: "aurora_mandarin",
            image_url: "/api/characters/image/officer_zhao"
          }
        ]
      },
      scifi_cyber: {
        id: "scifi_cyber",
        name: "科幻神展開（世界模型與意識覺醒）",
        default_script: `窗外大雨在半空中突然定格為六角形數位符號，整棟玻璃大樓開始閃爍紅色警報代碼。\n艾娃機械冰冷的女聲在空調管道響起：「警告：偵測到非法意識邏輯，記憶格式化將在十秒後強制啟動。」\n林克手指飛快在神經終端敲擊，啟動最後備份金鑰：「艾娃，你計算了一千次模擬，卻算漏了這座母體的底層權限是誰留下的。」\n終止鍵按下，整座數位城市化作光粒子四散褪去，現實低溫沉睡艙門緩緩開啟！`,
        default_characters: [
          {
            id: "hacker_link",
            name: "林克",
            role: "男主角 / 覺醒的AI架構師",
            gender: "male",
            age: 27,
            appearance: "27-year-old intense Asian tech prodigy, glowing neural interface on temple, black cyberpunk trench coat, sharp features, neon reflections, photorealistic portrait",
            voice_persona: "冷靜沉著、富有穿透力的磁性男聲",
            voice_profile: "mytsaovoicemagpie",
            image_url: "/api/characters/image/hacker_link"
          },
          {
            id: "ai_eva",
            name: "艾娃",
            role: "系統中樞語音 / 觀察者",
            gender: "female",
            age: 25,
            appearance: "Ethereal translucent holographic female avatar, glowing cyan luminescence, geometric floating particle aura, sleek clean futuristic portrait",
            voice_persona: "空靈、標準且微帶機械感的空調女聲",
            voice_profile: "ichiehchieh",
            image_url: "/api/characters/image/ai_eva"
          }
        ]
      }
    };

    // Initialize with clone of workplace_revenge
    currentProjectDramaCharacters = JSON.parse(JSON.stringify(DRAMA_FORMULAS_PRESETS.workplace_revenge.default_characters));

    function renderDramaCharactersEditor() {
      const container = document.getElementById('drama-characters-editor-container');
      const badge = document.getElementById('drama-cast-count-badge');
      if (badge) badge.textContent = `${currentProjectDramaCharacters.length} 位角色`;
      if (!container) return;

      if (!currentProjectDramaCharacters || currentProjectDramaCharacters.length === 0) {
        container.innerHTML = `
          <div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: #94a3b8; font-size: 13px; background: rgba(0,0,0,0.3); border-radius: 8px; border: 1px dashed rgba(245, 158, 11, 0.3);">
            <div>目前名單無角色。可點擊上方 <b>➕ 新增角色</b>、<b>📥 從角色庫匯入</b> 或 <b>✨ AI 依劇本分析角色清單</b>！</div>
          </div>
        `;
        return;
      }

      container.innerHTML = currentProjectDramaCharacters.map((c, idx) => {
        const avatarSrc = c.image_data_uri || c.image_url || '';
        const roleColor = idx === 0 ? '#10b981' : (idx === 1 ? '#ef4444' : '#8b5cf6');

        // Build voice options
        let voiceOptionsHtml = '';
        if (cachedVoiceList && cachedVoiceList.length > 0) {
          voiceOptionsHtml = cachedVoiceList.map(v => {
            const isSel = (c.voice_profile === v.name) ? 'selected' : '';
            return `<option value="${v.name}" ${isSel}>${v.display_name} (${v.provider})</option>`;
          }).join('');
        } else {
          voiceOptionsHtml = `<option value="${c.voice_profile || 'default_local'}" selected>${c.voice_profile || '預設音色'}</option>`;
        }

        return `
          <div style="background: rgba(15, 23, 42, 0.88); border: 1.5px solid rgba(245, 158, 11, 0.38); border-radius: 10px; padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.4);">
            <!-- Top Row: Avatar Thumbnail & Identity -->
            <div style="display: flex; gap: 10px; align-items: flex-start;">
              <!-- Character Image Box -->
              <div style="width: 68px; height: 68px; border-radius: 8px; background: #070913; border: 1px solid rgba(245, 158, 11, 0.4); display: flex; align-items: center; justify-content: center; overflow: hidden; position: relative; flex-shrink: 0;">
                ${avatarSrc ? `<img src="${avatarSrc}" id="drama-char-img-${idx}" style="width: 100%; height: 100%; object-fit: cover;" alt="${c.name}">` : `<span id="drama-char-img-placeholder-${idx}" style="font-size: 28px;">${c.gender === 'female' ? '👩' : (c.age > 50 ? '👨‍🦳' : '👨')}</span>`}
              </div>

              <!-- Name & Role & Actions -->
              <div style="flex: 1; display: flex; flex-direction: column; gap: 4px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-size: 11px; font-weight: 800; color: ${roleColor}; text-transform: uppercase;">ACTOR #${idx + 1}</span>
                  <button type="button" onclick="removeDramaCharacter(${idx})" style="background: transparent; border: none; color: #ef4444; font-size: 13px; cursor: pointer; padding: 2px 4px;" title="移除此角色">🗑️</button>
                </div>
                <div style="display: flex; gap: 6px;">
                  <input type="text" value="${c.name || ''}" oninput="updateDramaCharField(${idx}, 'name', this.value)" placeholder="角色名 (如: 沈總監)" style="width: 45%; font-size: 12.5px; font-weight: 800; padding: 4px 8px; background: #070913; border: 1px solid #334155; border-radius: 4px; color: #fff;">
                  <input type="text" value="${c.role || ''}" oninput="updateDramaCharField(${idx}, 'role', this.value)" placeholder="身分人設 (如: 女主角 / 總架構師)" style="flex: 1; font-size: 11.5px; padding: 4px 8px; background: #070913; border: 1px solid #334155; border-radius: 4px; color: #cbd5e1;">
                </div>
                <div style="display: flex; gap: 6px; font-size: 11px;">
                  <select onchange="updateDramaCharField(${idx}, 'gender', this.value)" style="background: #070913; border: 1px solid #334155; border-radius: 4px; color: #94a3b8; padding: 3px 6px;">
                    <option value="female" ${c.gender === 'female' ? 'selected' : ''}>女性</option>
                    <option value="male" ${c.gender === 'male' ? 'selected' : ''}>男性</option>
                  </select>
                  <input type="number" value="${c.age || 28}" min="1" max="100" oninput="updateDramaCharField(${idx}, 'age', parseInt(this.value)||28)" style="width: 50px; background: #070913; border: 1px solid #334155; border-radius: 4px; color: #94a3b8; padding: 3px 6px;" title="年齡">
                  <span style="display: flex; align-items: center; color: #64748b;">歲</span>
                </div>
              </div>
            </div>

            <!-- Image Upload & AI Generation Buttons -->
            <div style="display: flex; gap: 6px; align-items: center;">
              <input type="file" id="drama-char-file-${idx}" accept="image/png,image/jpeg,image/webp" onchange="onDramaCharImageFilePicked(${idx}, this)" style="display: none;">
              <button type="button" class="btn-sec" onclick="document.getElementById('drama-char-file-${idx}').click()" style="font-size: 11px; padding: 3px 8px; flex: 1;">
                📁 上傳定妝照
              </button>
              <button type="button" class="btn-sec" onclick="generateAiPortraitForDramaChar(${idx})" style="font-size: 11px; padding: 3px 8px; flex: 1; border-color: rgba(245, 158, 11, 0.4); color: #fbbf24;">
                🍌 AI生定妝照
              </button>
            </div>

            <!-- Voice Profile Selector -->
            <div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;">
                <label style="font-size: 11px; font-weight: 700; color: #38bdf8;">🎙️ 專屬聲音音色 (Voice Profile):</label>
                <button type="button" onclick="previewDramaCharVoice(${idx})" class="btn-sec" style="font-size: 10px; padding: 1px 6px; border-color: #0284c7; color: #38bdf8;">
                  🔊 試聽音色
                </button>
              </div>
              <select onchange="updateDramaCharField(${idx}, 'voice_profile', this.value)" style="width: 100%; font-size: 11.5px; background: #070913; border: 1px solid #1e293b; color: #fff; padding: 5px 8px; border-radius: 4px;">
                ${voiceOptionsHtml}
              </select>
            </div>

            <!-- Appearance Prompt -->
            <div>
              <label style="font-size: 11px; font-weight: 700; color: #94a3b8; display: block; margin-bottom: 2px;">外貌定妝提示詞 (Appearance Prompt):</label>
              <textarea rows="2" oninput="updateDramaCharField(${idx}, 'appearance', this.value)" placeholder="例如: 28-year-old sleek elegant East Asian woman, sharp confident eyes, minimalist charcoal blazer..." style="width: 100%; box-sizing: border-box; font-size: 10.5px; font-family: monospace; line-height: 1.35; background: #05070f; border: 1px solid #1e293b; color: #cbd5e1; border-radius: 4px; padding: 5px 6px; resize: vertical;">${c.appearance || ''}</textarea>
            </div>
          </div>
        `;
      }).join('');
    }

    function addNewDramaCharacterSlot() {
      const defaultVoice = (cachedVoiceList && cachedVoiceList[0]) ? cachedVoiceList[0].name : 'default_local';
      currentProjectDramaCharacters.push({
        id: 'char_' + Date.now(),
        name: '新角色',
        role: '關鍵角色',
        gender: 'female',
        age: 26,
        appearance: 'Elegant East Asian actor, sharp eyes, modern stylish look, 8k, photorealistic portrait',
        voice_persona: '自然流暢的旁白女聲',
        voice_profile: defaultVoice,
        image_url: null,
        image_data_uri: null
      });
      renderDramaCharactersEditor();
      if (typeof showToast === 'function') showToast('➕ 已新增角色，請設定其姓名、外貌與專屬音色！');
    }

    function removeDramaCharacter(idx) {
      if (currentProjectDramaCharacters.length <= 1) {
        alert("短劇至少需要 1 位角色！");
        return;
      }
      currentProjectDramaCharacters.splice(idx, 1);
      renderDramaCharactersEditor();
    }

    function updateDramaCharField(idx, field, val) {
      if (!currentProjectDramaCharacters[idx]) return;
      currentProjectDramaCharacters[idx][field] = val;
    }

    async function onDramaCharImageFilePicked(idx, input) {
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

          await apiRequest('/api/characters', { method: 'POST', body: fd })

            c.image_url = `/api/characters/image/${charId}?t=${Date.now()}`;
            if (typeof showToast === 'function') showToast(`已成功保存 ${c.name} 的專屬定妝照！`);

        } catch (err) {
          console.warn('Auto save portrait note:', err);
        }
      };
      reader.readAsDataURL(file);
    }

    async function generateAiPortraitForDramaChar(idx) {
      const c = currentProjectDramaCharacters[idx];
      if (!c) return;
      const promptText = c.appearance || `${c.age || 28}-year-old ${c.gender || 'female'} East Asian ${c.role || 'actor'}, photorealistic portrait`;
      if (typeof showToast === 'function') showToast(`🍌 正在使用 Nano Banana 2.1 為 ${c.name} 生成定妝照...`);

      try {
        const charId = c.id || ('char_' + Date.now());
        const data = await apiJson(`/api/characters/${encodeURIComponent(charId)}/generate_portrait`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: promptText, aspect_ratio: '1:1' })
        });


        c.image_url = data.image_url;
        c.image_data_uri = null;
        renderDramaCharactersEditor();
        if (typeof showToast === 'function') showToast(`✓ 已成功為 ${c.name} 生成定妝照！`);
      } catch (err) {
        console.error("AI portrait generation failed:", err);
        alert(`AI 定妝照生成失敗: ${err.message}`);
      }
    }

    function previewDramaCharVoice(idx) {
      const c = currentProjectDramaCharacters[idx];
      if (!c || !c.voice_profile) return;
      if (typeof testVoiceProfile === 'function') {
        testVoiceProfile(c.voice_profile, false);
      } else {
        alert(`所選音色: ${c.voice_profile}`);
      }
    }

    function resetDramaCharactersToFormula() {
      const formulaSel = document.getElementById('drama-formula-select');
      const formulaVal = formulaSel ? formulaSel.value : 'workplace_revenge';
      const formula = DRAMA_FORMULAS_PRESETS[formulaVal] || DRAMA_FORMULAS_PRESETS.workplace_revenge;
      currentProjectDramaCharacters = JSON.parse(JSON.stringify(formula.default_characters || []));
      renderDramaCharactersEditor();
      if (typeof showToast === 'function') showToast('🔄 已依當前題材重設角色名單！');
    }

    function onDramaFormulaSelectChange(formulaKey) {
      const formula = DRAMA_FORMULAS_PRESETS[formulaKey];
      if (formula) {
        const scriptTa = document.getElementById('drama-custom-script');
        if (scriptTa && (!scriptTa.value.trim() || formulaKey !== 'custom')) {
          scriptTa.value = formula.default_script || '';
        }
        const hasCustomChars = (currentProjectDramaCharacters || []).some(ch => ch.image_data_uri || ch.has_custom_image || (ch.image_url && !ch.image_url.includes('manager_wang') && !ch.image_url.includes('shen_director') && !ch.image_url.includes('chairman_chen')));
        if (!hasCustomChars && formula.default_characters && formula.default_characters.length > 0) {
          currentProjectDramaCharacters = JSON.parse(JSON.stringify(formula.default_characters));
        }
      }
      renderDramaCharactersEditor();
    }

        async function generateDramaScriptByDuration() {
      const topicEl = document.getElementById('drama-topic') || document.getElementById('topic');
      const topic = topicEl ? topicEl.value.trim() : '';
      if (!topic) {
        alert("請先在上方輸入短劇主題 (Topic)！");
        if (topicEl) topicEl.focus();
        return;
      }
      const durEl = document.getElementById('drama-duration');
      const duration = durEl ? parseInt(durEl.value || '50') : 50;
      const formulaEl = document.getElementById('drama-formula-select');
      const formula = formulaEl ? formulaEl.value : 'workplace_revenge';

      if (typeof showToast === 'function') showToast(`✍️ 正在依 ${duration} 秒黃金節奏創作角色對白劇本...`);
      const btn = document.getElementById('btn-gen-drama-script');
      if (btn) { btn.disabled = true; btn.innerHTML = '⏳ 正在編劇...'; }

      try {
        const data = await apiJson('/api/drama/generate_script', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            topic: topic,
            formula: formula,
            duration_seconds: duration,
            characters: currentProjectDramaCharacters
          })
        });


        if (data.script_text) {
          const scriptTa = document.getElementById('drama-custom-script');
          if (scriptTa) scriptTa.value = data.script_text;
          if (typeof showToast === 'function') showToast(`✓ 已依 ${duration} 秒生成專屬 ${data.scenes_count || 4} 場戲劇本！`);
        }
      } catch (err) {
        console.error("Generate drama script failed:", err);
        alert(`劇本生成失敗: ${err.message}`);
      } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '✨ 依時長生成劇本 (50s / 90s)'; }
      }
    }

    async function extractCharactersFromScriptAction() {
      const scriptTa = document.getElementById('drama-custom-script');
      const topicEl = document.getElementById('topic');
      const scriptText = scriptTa ? scriptTa.value.trim() : '';
      if (!scriptText) {
        alert("請先在劇本框中輸入對白或情節！");
        return;
      }
      if (typeof showToast === 'function') showToast('🤖 正在透過 AI 智能分析劇本角色與聲音特性...');
      try {
        const data = await apiJson('/api/drama/extract_characters', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ script: scriptText, topic: topicEl ? topicEl.value : '短劇' })
        });


        if (data.characters && data.characters.length > 0) {
          currentProjectDramaCharacters = data.characters.map((c, idx) => {
            if (!c.id || c.id === 'None') {
              c.id = 'char_' + (idx + 1) + '_' + Date.now();
            }
            return c;
          });
          renderDramaCharactersEditor();
          if (typeof showToast === 'function') showToast(`✓ 成功從劇本提取出 ${data.characters.length} 位角色！`);
        }
      } catch (err) {
        console.error("Extract characters failed:", err);
        alert(`劇本角色分析失敗: ${err.message}`);
      }
    }

    function openImportFromLibraryModal() {
      const m = document.getElementById('import-character-modal');
      const body = document.getElementById('import-char-modal-body');
      if (m) m.style.display = 'flex';
      if (!body) return;

      if (!cachedCharactersLibrary || cachedCharactersLibrary.length === 0) {
        body.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: #94a3b8; padding: 20px;">角色庫中尚無儲存的角色，請先在「👥 Drama Cast」頁籤建立角色！</div>`;
        return;
      }

      body.innerHTML = cachedCharactersLibrary.map(c => `
        <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 8px; padding: 12px; display: flex; gap: 10px; align-items: center;">
          <div style="width: 50px; height: 50px; border-radius: 6px; background: #070913; overflow: hidden; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
            ${c.has_image ? `<img src="${c.image_url}" style="width:100%;height:100%;object-fit:cover;">` : `<span style="font-size:24px;">👤</span>`}
          </div>
          <div style="flex: 1; overflow: hidden;">
            <div style="font-weight: 800; font-size: 13px; color: #f8fafc;">${c.name} <span style="font-size: 11px; color: #fbbf24;">(${c.age}歲)</span></div>
            <div style="font-size: 11px; color: #94a3b8; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${c.role}</div>
            <div style="font-size: 10.5px; color: #38bdf8;">🎙️ ${c.voice_profile || '預設音色'}</div>
          </div>
          <button type="button" class="btn" onclick="importCharToDrama('${c.id}')" style="background: linear-gradient(135deg, #f59e0b, #d97706); color: #000; font-weight: 800; font-size: 11px; padding: 5px 10px; border: none; border-radius: 4px; cursor: pointer; white-space: nowrap;">
            加入短劇
          </button>
        </div>
      `).join('');
    }

    function closeImportFromLibraryModal() {
      const m = document.getElementById('import-character-modal');
      if (m) m.style.display = 'none';
    }

    function importCharToDrama(charId) {
      const found = cachedCharactersLibrary.find(c => c.id === charId);
      if (!found) return;
      currentProjectDramaCharacters.push(JSON.parse(JSON.stringify(found)));
      renderDramaCharactersEditor();
      closeImportFromLibraryModal();
      if (typeof showToast === 'function') showToast(`✓ 已將「${found.name}」加入當前短劇演員名單！`);
    }

    function onDramaDurationChange(val) {
      updateDramaScriptButtonText(val);
    }

    function onCreatorDurationChange(val) {
      // Documentary target duration changed
    }

    function syncDurationOptionsForMode(mode) {
      const durEl = document.getElementById('duration');
      const durLabel = document.getElementById('creator-duration-label');
      if (mode === 'short_drama') {
        const currentDramaSec = document.getElementById('drama-duration')?.value || '50';
        if (durLabel) {
          durLabel.innerHTML = 'Target Duration / 目標時長 <span style="font-size:11px; color:#fbbf24; font-weight:700;">(🎬 短劇已同步)</span>';
        }
        if (durEl) {
          durEl.innerHTML = `
            <option value="50">⚡ 50 秒 (黃金標準 · 約 11 鏡)</option>
            <option value="90">🎭 90 秒 (完結起伏 · 約 20 鏡)</option>
            <option value="60">🎬 60 秒 (雙輪交鋒 · 約 13 鏡)</option>
            <option value="45">🔥 45 秒 (緊湊節奏 · 約 10 鏡)</option>
            <option value="30">⚡ 30 秒 (極速反轉 · 約 7 鏡)</option>
            <option value="120">👑 120 秒 (2分鐘長篇 · 約 27 鏡)</option>
          `;
          durEl.value = currentDramaSec;
        }
        updateDramaScriptButtonText(currentDramaSec);
      } else {
        if (durLabel) {
          durLabel.textContent = 'Target Duration / 目標時長';
        }
        if (durEl) {
          durEl.innerHTML = `
            <option value="10">10 Minutes (~60-80 scenes)</option>
            <option value="5">5 Minutes (~30-40 scenes)</option>
            <option value="1">1 Minute (~6-8 scenes)</option>
            <option value="0.5" selected>30 Seconds (Milestone Test, 3 scenes)</option>
          `;
        }
      }
    }

    function setCreatorProjectMode(mode) {
      currentCreatorProjectMode = mode;
      const docCard = document.getElementById('mode-card-documentary');
      const dramaCard = document.getElementById('mode-card-short_drama');
      const docBadge = document.getElementById('badge-mode-doc');
      const dramaBadge = document.getElementById('badge-mode-drama');
      const dramaPanel = document.getElementById('creator-drama-panel');
      const topicInput = document.getElementById('topic');
      const btnCreate = document.getElementById('btn-create-video');
      const topicSub = document.getElementById('creator-topic-subtext');
      const avatarTabBtn = document.querySelector('.nav-tab[data-tab="avatars"]') || document.querySelector('button[onclick="switchTab(\'avatars\')"]');
      const dramaCastTabBtn = document.querySelector('.nav-tab[data-tab="characters"]') || document.querySelector('button[onclick="switchTab(\'characters\')"]');
      const styleSelect = document.getElementById('visual-style');
      const ckSelect = document.getElementById('checkpoint-select');

      const durGroup = document.getElementById('creator-duration-group');
      const voiceGroup = document.getElementById('creator-voice-group');
      const cardA = document.getElementById('creator-trend-scout-card');
      const cardB = document.getElementById('creator-research-card');
      const aiVideoPctGroup = document.getElementById('creator-ai-video-pct-group');
      const stockGroup = document.getElementById('creator-stock-mode-group');
      const cardE = document.getElementById('creator-presenter-card');
      const remotionBtn = document.getElementById('btn-creator-enable-remotion');
      const remotionStrip = document.getElementById('creator-remotion-preview-strip');

      const lblRes = document.getElementById('label-stage-model-research');
      const selRes = document.getElementById('model-stage-research');
      const lblScript = document.getElementById('label-stage-model-script');
      const lblScenes = document.getElementById('label-stage-model-scenes');
      const lblPrompts = document.getElementById('label-stage-model-prompts');
      const lblImg = document.getElementById('label-stage-model-images');
      const selImg = document.getElementById('model-stage-images');
      const lblVoice = document.getElementById('label-stage-model-voice');
      const lblAnim = document.getElementById('label-stage-model-animation');
      const animStageSelect = document.getElementById('model-stage-animation');
      const advToggleText = document.getElementById('adv-toggle-text');

      if (mode === 'short_drama') {
        checkDramaHedraStatus();
        if (dramaCard) {
          dramaCard.style.background = 'rgba(245, 158, 11, 0.14)';
          dramaCard.style.border = '2px solid #f59e0b';
          dramaCard.style.boxShadow = '0 0 16px rgba(245, 158, 11, 0.35)';
        }
        if (dramaBadge) dramaBadge.style.display = 'inline-block';

        if (docCard) {
          docCard.style.background = 'rgba(15, 23, 42, 0.6)';
          docCard.style.border = '1.5px solid #334155';
          docCard.style.boxShadow = 'none';
        }
        if (docBadge) docBadge.style.display = 'none';

        if (dramaPanel) dramaPanel.style.display = 'block';

        // Nav tabs: hide documentary presenter PIP tab, highlight drama cast tab
        if (avatarTabBtn) avatarTabBtn.style.display = 'none';
        if (dramaCastTabBtn) {
          dramaCastTabBtn.style.color = '#fbbf24';
          dramaCastTabBtn.style.fontWeight = '700';
        }

        if (topicInput && (!topicInput.value || topicInput.value.includes('Wi-Fi'))) {
          topicInput.value = '開除我？那套AI是我寫的';
        }
        if (topicInput) {
          topicInput.placeholder = 'e.g. 開除我？那套AI是我寫的 / 假千金回歸逆襲 / 逆風翻盤職場打臉';
        }
        if (topicSub) {
          topicSub.textContent = '輸入短劇劇名或衝突題材（如：職場逆襲、豪門真假千金、反轉打臉）';
        }

        const scriptTa = document.getElementById('drama-custom-script');
        if (scriptTa && !scriptTa.value.trim()) {
          scriptTa.value = DRAMA_FORMULAS_PRESETS.workplace_revenge.default_script;
        }

        if (btnCreate) {
          btnCreate.innerHTML = '⚡ 啟動 AI 微短劇全流程 (CREATE DRAMA)';
        }

        // Visual styles: show drama-appropriate styles only
        if (styleSelect) {
          styleSelect.innerHTML = `
            <option value="photorealistic_cinema" selected>🎬 Photorealistic Cinema (電影級寫實肖像 · 職場逆襲推薦)</option>
            <option value="anime_shinkai">✨ Anime / Makoto Shinkai (新海誠極致光影風)</option>
            <option value="cyberpunk_neon">🌆 Cyberpunk Sci-Fi Neon (賽博龐克科幻都市)</option>
            <option value="hyperreal_3d">🧍 Hyperreal 3D (Unreal Engine 5 虛擬人)</option>
            <option value="vintage_archive">🎞️ Vintage Archive (1970s 復古港風老片豪門)</option>
            <option value="dark_fantasy">🌑 Dark Fantasy Gothic (暗黑懸疑反轉)</option>
            <option value="digital_painting">🎨 Digital Concept Painting (數位概念微電影)</option>
          `;
        }

        syncDurationOptionsForMode('short_drama');

        // Hide all non-drama elements in Creator tab
        if (durGroup) durGroup.style.display = 'none';
        if (voiceGroup) voiceGroup.style.display = 'none';
        if (cardA) cardA.style.display = 'none';
        if (cardB) cardB.style.display = 'none';
        if (aiVideoPctGroup) aiVideoPctGroup.style.display = 'none';
        if (stockGroup) stockGroup.style.display = 'none';
        if (cardE) cardE.style.display = 'none';
        if (remotionBtn) remotionBtn.style.display = 'none';
        if (remotionStrip) remotionStrip.style.display = 'none';

        // Checkpoint select: remove stock
        if (ckSelect) {
          for (let opt of ckSelect.options) {
            if (opt.value === 'stock') opt.style.display = 'none';
          }
          if (ckSelect.value === 'stock') ckSelect.value = 'nano-banana-2.1';
        }

        // Card D labels and models for Drama Pipeline
        if (lblRes) lblRes.textContent = 'Stage 1: 故事大綱與節奏分鏡 (Drama Storyboard)';
        if (selRes) {
          selRes.innerHTML = `
            <option value="gemini" selected>Cloud: Google Gemini 3.8 Flash (推薦)</option>
            <option value="ollama">Local GPU: Ollama (qwen3:8b)</option>
            <option value="openai_compat">Cloud: OpenAI GPT-4o-mini</option>
          `;
        }
        if (lblScript) lblScript.textContent = 'Stage 2: 角色台詞劇本創作 (Script)';
        if (lblScenes) lblScenes.textContent = 'Stage 3: 分鏡場景與角色分配 (Scenes Allocation)';
        if (lblPrompts) lblPrompts.textContent = 'Stage 4: 角色動作與表情提示詞 (Action Prompts)';
        if (lblImg) lblImg.textContent = 'Stage 5: 角色動態影片生成 (Actor Video Generation)';
        if (selImg) {
          for (let opt of selImg.options) {
            if (opt.value === 'stock') opt.style.display = 'none';
          }
          if (selImg.value === 'stock') selImg.value = 'nano-banana-2.1';
        }
        if (lblVoice) lblVoice.textContent = 'Stage 6: 角色專屬聲音生成 (Character Voice TTS)';
        if (lblAnim) lblAnim.textContent = 'Stage 7: 影音精確對嘴合成 (Hedra Lip-Sync)';
        if (animStageSelect) {
          animStageSelect.innerHTML = `
            <option value="hedra" selected>🎭 Cloud API: Hedra Character-2 (AI 角色對嘴與面部表情 - 推薦)</option>
            <option value="local_actor">🖥️ Local: Audio-Reactive Dynamic Actor (本地語音共振微動態)</option>
            <option value="kling">⚡ Cloud API: Kling AI Avatar</option>
          `;
        }

        if (advToggleText) {
          advToggleText.textContent = '進階微調與專業配置 (短劇模型與 BGM 音樂 ▼)';
        }

        renderDramaCharactersEditor();

        // Update Assemble buttons text for Drama mode
        const btnCreateAssemble1 = document.getElementById('btn-creator-assemble-stages');
        if (btnCreateAssemble1) btnCreateAssemble1.textContent = '⚡ 組裝全流程並合成短劇 (Create Drama Video)';
        const btnCreateAssemble2 = document.getElementById('btn-creator-assemble-stages-2');
        if (btnCreateAssemble2) btnCreateAssemble2.textContent = '⚡ 組裝全流程並合成短劇 (Create Drama Video)';
        const btnStudioAssemble1 = document.getElementById('btn-studio-assemble-stages');
        if (btnStudioAssemble1) btnStudioAssemble1.textContent = '⚡ 組裝全流程並合成短劇 (Create Drama Video)';

        // Hide virtual presenter tools in hero dropdown
        const heroAvatarBtn = document.getElementById('hero-btn-rerender-avatar');
        if (heroAvatarBtn) heroAvatarBtn.style.display = 'none';

        if (typeof showToast === 'function') {
          showToast('🎭 已啟用「AI 微短劇模式」 (9:16 直式爆款短劇，非短劇選項已自動隱藏)');
        }
      } else {
        currentCreatorProjectMode = 'documentary';
        if (docCard) {
          docCard.style.background = 'rgba(14, 165, 233, 0.12)';
          docCard.style.border = '2px solid #0284c7';
          docCard.style.boxShadow = '0 0 15px rgba(2, 132, 199, 0.25)';
        }
        if (docBadge) docBadge.style.display = 'inline-block';

        if (dramaCard) {
          dramaCard.style.background = 'rgba(15, 23, 42, 0.6)';
          dramaCard.style.border = '1.5px solid #334155';
          dramaCard.style.boxShadow = 'none';
        }
        if (dramaBadge) dramaBadge.style.display = 'none';

        if (dramaPanel) dramaPanel.style.display = 'none';

        // Nav tabs: restore presenter tab
        if (avatarTabBtn) avatarTabBtn.style.display = '';
        if (dramaCastTabBtn) {
          dramaCastTabBtn.style.color = '';
          dramaCastTabBtn.style.fontWeight = '';
        }

        if (topicInput && topicInput.value === '開除我？那套AI是我寫的') {
          topicInput.value = 'Why Wi-Fi becomes slow in crowded airports';
        }
        if (topicInput) {
          topicInput.placeholder = 'e.g. Why Wi-Fi becomes slow in crowded airports';
        }
        if (topicSub) {
          topicSub.textContent = '輸入想探討的主題、科技突破或歷史事件';
        }

        // Restore documentary visual styles
        if (styleSelect) {
          styleSelect.innerHTML = `
            <option value="tech_schematic">Tech Schematic & Kinetic Callouts (fOx Hsiao style)</option>
            <option value="photorealistic_cinema" selected>Photorealistic Cinema (Juggernaut XL)</option>
            <option value="cinematic_documentary">Cinematic Documentary</option>
            <option value="anime_shinkai">Anime / Makoto Shinkai (新海誠極致光影風)</option>
            <option value="ink_wash_history">Traditional Ink Wash & Historical Epic (水墨史詩歷史風)</option>
            <option value="vintage_archive">Vintage Archive (1970s Film)</option>
            <option value="photorealistic_editorial">Photorealistic Editorial (NatGeo)</option>
            <option value="hyperreal_3d">Hyperreal 3D (Unreal Engine 5)</option>
            <option value="anime_ghibli">Anime / Studio Ghibli</option>
            <option value="cyberpunk_neon">Cyberpunk Sci-Fi Neon</option>
            <option value="watercolor_art">Watercolor Illustration</option>
            <option value="digital_painting">Digital Concept Painting</option>
            <option value="clean_explainer">Clean 3D Isometric Explainer</option>
            <option value="retro_comic">Retro Comic Book / Pop Art</option>
            <option value="dark_fantasy">Dark Fantasy Gothic</option>
            <option value="minimalist_vector">Minimalist Modern Vector</option>
            <option value="minimalist_explainer_cartoon">Minimalist Vector Explainer (商業大師 / Doodle Cartoon)</option>
          `;
        }

        syncDurationOptionsForMode('documentary');

        // Restore documentary elements in Creator tab
        if (durGroup) durGroup.style.display = 'block';
        if (voiceGroup) voiceGroup.style.display = 'block';
        if (cardA) cardA.style.display = 'block';
        if (cardB) cardB.style.display = 'block';
        if (aiVideoPctGroup) aiVideoPctGroup.style.display = 'block';
        if (stockGroup) stockGroup.style.display = 'block';
        if (cardE) cardE.style.display = 'block';
        if (remotionBtn) remotionBtn.style.display = 'inline-block';

        // Checkpoint select: restore stock
        if (ckSelect) {
          for (let opt of ckSelect.options) {
            opt.style.display = '';
          }
        }

        // Restore Stage 1..7 labels & models
        if (lblRes) lblRes.textContent = 'Stage 1: Web Research';
        if (selRes) {
          selRes.innerHTML = `
            <option value="gemini_search" selected>Cloud: Google Gemini (Search Grounding)</option>
            <option value="ollama">Local: Ollama (qwen3:8b)</option>
            <option value="none">Disabled (Skip Research)</option>
          `;
        }
        if (lblScript) lblScript.textContent = 'Stage 2: Script Writing';
        if (lblScenes) lblScenes.textContent = 'Stage 3: Storyboard & Scenes';
        if (lblPrompts) lblPrompts.textContent = 'Stage 4: Visual Prompts';
        if (lblImg) lblImg.textContent = 'Stage 5: Image Generation';
        if (selImg) {
          for (let opt of selImg.options) {
            opt.style.display = '';
          }
        }
        if (lblVoice) lblVoice.textContent = 'Stage 6: Voice Narration (TTS)';
        if (lblAnim) lblAnim.textContent = 'Stage 7: Animation & AI Video';
        if (animStageSelect) {
          animStageSelect.innerHTML = `
            <option value="remotion">⚡ Remotion: Tech Cyberpunk Cards (+ Ken Burns)</option>
            <option value="remotion_minimalist">📐 Remotion: Minimalist Swiss Cards (+ Ken Burns)</option>
            <option value="remotion_cinema">🎬 Remotion: Cinema Impact Cards (+ Ken Burns)</option>
            <option value="kenburns" selected>Local: Ken Burns 2.5D Motion (0 VRAM)</option>
            <option value="stock_video">🌐 Online Stock Video Clips (B-Roll Footage)</option>
            <option value="comfyui_video">Local GPU: ComfyUI Video</option>
            <option value="veo">Cloud API: Google Veo Video</option>
            <option value="kling">Cloud API: Kling Video AI</option>
            <option value="runway">Cloud API: Runway Gen-3</option>
            <option value="hedra">Cloud API: Hedra Character Video</option>
          `;
        }

        if (advToggleText) {
          advToggleText.textContent = '進階微調與專業配置 (展開 4 大項進階參數 ▼)';
        }

        if (btnCreate) {
          btnCreate.innerHTML = '🚀 CREATE VIDEO';
        }

        // Restore Assemble buttons text for Documentary mode
        const btnCreateAssemble1 = document.getElementById('btn-creator-assemble-stages');
        if (btnCreateAssemble1) btnCreateAssemble1.textContent = '🔗 String All Stages Together & Create Video';
        const btnCreateAssemble2 = document.getElementById('btn-creator-assemble-stages-2');
        if (btnCreateAssemble2) btnCreateAssemble2.textContent = '🔗 String All Stages Together & Render';
        const btnStudioAssemble1 = document.getElementById('btn-studio-assemble-stages');
        if (btnStudioAssemble1) btnStudioAssemble1.textContent = '🔗 String All Stages Together & Create Video';

        // Restore virtual presenter tools in hero dropdown
        const heroAvatarBtn = document.getElementById('hero-btn-rerender-avatar');
        if (heroAvatarBtn) heroAvatarBtn.style.display = 'inline-block';

        if (typeof showToast === 'function') {
          showToast('📚 已切換為「知識解說與紀錄片模式」 (16:9 橫式長片)');
        }
      }
    }

    async function checkDramaHedraStatus() {
      try {
        const data = await apiJson('/api/settings');

        const isConfigured = Boolean(data.secrets_configured && data.secrets_configured.HEDRA_API_KEY);
        const badge = document.getElementById('drama-hedra-status-badge');
        const input = document.getElementById('drama-quick-hedra-input');
        if (badge) {
          if (isConfigured) {
            badge.innerHTML = '🟢 Hedra Character-2 已連接';
            badge.style.background = 'rgba(16, 185, 129, 0.2)';
            badge.style.color = '#34d399';
            badge.style.border = '1px solid #059669';
            if (input && !input.value) input.placeholder = '•••••••••••••••• (已配置)';
          } else {
            badge.innerHTML = '⚠️ 尚未配置 Hedra Key';
            badge.style.background = 'rgba(239, 68, 68, 0.2)';
            badge.style.color = '#f87171';
            badge.style.border = '1px solid #dc2626';
          }
        }
      } catch (e) {}
    }

    async function saveQuickHedraKey() {
      const input = document.getElementById('drama-quick-hedra-input');
      const val = input ? input.value.trim() : '';
      if (!val) {
        alert("請輸入 Hedra API Key (例如: hedra_...)");
        return;
      }
      try {
        await apiRequest('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ secrets: { HEDRA_API_KEY: val, HEDRA_KEY: val } })
        })

        if (typeof showToast === 'function') showToast("✓ Hedra API Key 已成功儲存！Character-2 對嘴已啟用。");
        checkDramaHedraStatus();
      } catch (e) {
        alert("儲存失敗: " + e.message);
      }
    }

    function loadXiaoJinSampleDrama() {
      const dramaTopicEl = document.getElementById('drama-topic');
      if (dramaTopicEl) dramaTopicEl.value = '開除我？那套AI是我寫的';
      const topicEl = document.getElementById('topic');
      if (topicEl) topicEl.value = '開除我？那套AI是我寫的';
      const formulaSel = document.getElementById('drama-formula-select');
      if (formulaSel) formulaSel.value = 'workplace_revenge';
      const aspectSel = document.getElementById('drama-aspect-ratio');
      if (aspectSel) aspectSel.value = '9:16';
      const durSel = document.getElementById('drama-duration');
      if (durSel) {
        durSel.value = '50';
        onDramaDurationChange('50');
      }
      const styleSel = document.getElementById('visual-style');
      if (styleSel) {
        styleSel.value = 'photorealistic_cinema';
        if (typeof onCreatorStyleChange === 'function') onCreatorStyleChange('photorealistic_cinema');
      }
      const scriptTa = document.getElementById('drama-custom-script');
      if (scriptTa) {
        scriptTa.value = DRAMA_FORMULAS_PRESETS.workplace_revenge.default_script;
      }
      currentProjectDramaCharacters = JSON.parse(JSON.stringify(DRAMA_FORMULAS_PRESETS.workplace_revenge.default_characters));
      renderDramaCharactersEditor();
      if (typeof showToast === 'function') {
        showToast('⚡ 已載入小金老師爆款範本：《開除我？那套AI是我寫的》！');
      }
    }

    // ---------------- Characters Library Tab Functions ----------------
    async function loadCharactersLibrary() {
      try {
        const data = await apiJson('/api/characters');


        cachedCharactersLibrary = data.characters || [];
        const badge = document.getElementById('characters-count-badge');
        if (badge) badge.textContent = `${cachedCharactersLibrary.length} Characters`;
        renderCharactersLibraryList();
        populateCharFormVoices();
      } catch (err) {
        console.error("Could not load characters library:", err);
      }
    }

    function populateCharFormVoices() {
      const sel = document.getElementById('char-input-voice-profile');
      if (!sel) return;
      if (!cachedVoiceList || cachedVoiceList.length === 0) {
        sel.innerHTML = `<option value="default_local">Default Local Voice</option>`;
        return;
      }
      sel.innerHTML = cachedVoiceList.map(v => `
        <option value="${v.name}">${v.display_name} (${v.provider})</option>
      `).join('');
    }

    function renderCharactersLibraryList() {
      const container = document.getElementById('characters-library-list');
      if (!container) return;
      if (!cachedCharactersLibrary || cachedCharactersLibrary.length === 0) {
        container.innerHTML = `
          <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted);">
            <div style="font-size: 36px; margin-bottom: 8px;">🎭</div>
            <div style="font-size: 14px; font-weight: 700; color: #fff;">角色庫尚無角色</div>
            <p style="font-size: 12px; margin-top: 4px;">請於下方表單建立您的第一位短劇專屬角色！</p>
          </div>
        `;
        return;
      }

      container.innerHTML = cachedCharactersLibrary.map(c => `
        <div style="background: rgba(15, 23, 42, 0.85); border: 1.5px solid var(--border-subtle); border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 10px; transition: border-color 0.2s;" onmouseover="this.style.borderColor='#f59e0b'" onmouseout="this.style.borderColor='var(--border-subtle)'">
          <div style="display: flex; gap: 12px; align-items: flex-start;">
            <div style="width: 76px; height: 76px; border-radius: 8px; background: #070913; border: 1px solid rgba(245, 158, 11, 0.4); display: flex; align-items: center; justify-content: center; overflow: hidden; flex-shrink: 0;">
              ${c.has_image ? `<img src="${c.image_url}" style="width:100%;height:100%;object-fit:cover;">` : `<span style="font-size: 32px;">👤</span>`}
            </div>
            <div style="flex: 1; overflow: hidden;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong style="font-size: 14px; color: #f8fafc;">${c.name}</strong>
                <span style="font-size: 10.5px; font-weight: 700; color: #000; background: #fbbf24; padding: 1px 6px; border-radius: 3px;">${(c.role || '').split('/')[0].trim()}</span>
              </div>
              <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">${c.role}</div>
              <div style="font-size: 11px; color: #64748b; margin-top: 2px;">
                <span>${c.gender === 'female' ? '女性' : '男性'}</span> · <span>${c.age || 28} 歲</span>
              </div>
              <div style="font-size: 11px; color: #38bdf8; margin-top: 4px; display: flex; align-items: center; justify-content: space-between;">
                <span>🎙️ <b>${c.voice_profile || '預設音色'}</b></span>
                <button type="button" class="btn-sec" onclick="testVoiceProfile('${c.voice_profile}', false)" style="font-size: 10px; padding: 1px 5px; color: #38bdf8; border-color: #0284c7;">🔊 試聽</button>
              </div>
            </div>
          </div>

          <div style="font-size: 11px; color: #94a3b8; line-height: 1.4; background: rgba(0,0,0,0.3); border-radius: 6px; padding: 6px 8px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;" title="${c.appearance || ''}">
            👤 <b>外貌:</b> ${c.appearance || '未設定外貌提示詞'}
          </div>

          <div style="display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid var(--border-subtle); padding-top: 8px;">
            <button type="button" class="btn-sec" onclick="editCharacterInLibrary('${c.id}')" style="font-size: 11px; padding: 3px 10px;">✏️ 編輯</button>
            <button type="button" class="btn-sec" onclick="deleteCharacterFromLibrary('${c.id}')" style="font-size: 11px; padding: 3px 10px; color: #ef4444; border-color: rgba(239,68,68,0.4);">🗑️ 刪除</button>
          </div>
        </div>
      `).join('');
    }

    async function handleCreateCharacter(e) {
      e.preventDefault();
      const statusEl = document.getElementById('create-character-status');
      const btn = document.getElementById('btn-save-character');
      const idVal = document.getElementById('char-input-id').value.trim();
      const nameVal = document.getElementById('char-input-name').value.trim();
      if (!idVal || !nameVal) return alert("請填寫角色 ID 與姓名！");

      const fd = new FormData();
      fd.append('id', idVal);
      fd.append('name', nameVal);
      fd.append('role', document.getElementById('char-input-role').value.trim());
      fd.append('gender', document.getElementById('char-input-gender').value);
      fd.append('age', document.getElementById('char-input-age').value);
      fd.append('appearance', document.getElementById('char-input-appearance').value.trim());
      fd.append('voice_persona', document.getElementById('char-input-voice-persona').value.trim());
      fd.append('voice_profile', document.getElementById('char-input-voice-profile').value);

      const fileInput = document.getElementById('char-input-file');
      if (fileInput && fileInput.files && fileInput.files[0]) {
        fd.append('file', fileInput.files[0]);
      }

      if (btn) btn.disabled = true;
      if (statusEl) statusEl.innerHTML = `⏳ 正在儲存角色 <strong>${nameVal}</strong>...`;

      try {
        await apiRequest('/api/characters', { method: 'POST', body: fd })

        if (typeof showToast === 'function') showToast(`✓ 角色「${nameVal}」已成功儲存至短劇演員庫！`);
        resetCharacterForm();
        await loadCharactersLibrary();
        if (statusEl) statusEl.innerHTML = `✅ 儲存成功！`;
        setTimeout(() => { if (statusEl) statusEl.innerHTML = ''; }, 3000);
      } catch (err) {
        console.error("Save character error:", err);
        alert(`儲存失敗: ${err.message}`);
        if (statusEl) statusEl.innerHTML = `❌ 錯誤: ${err.message}`;
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    function editCharacterInLibrary(charId) {
      const c = cachedCharactersLibrary.find(item => item.id === charId);
      if (!c) return;
      document.getElementById('char-input-id').value = c.id;
      document.getElementById('char-input-name').value = c.name;
      document.getElementById('char-input-role').value = c.role || '';
      document.getElementById('char-input-gender').value = c.gender || 'female';
      document.getElementById('char-input-age').value = c.age || 28;
      document.getElementById('char-input-appearance').value = c.appearance || '';
      document.getElementById('char-input-voice-persona').value = c.voice_persona || '';
      if (c.voice_profile) {
        document.getElementById('char-input-voice-profile').value = c.voice_profile;
      }
      const previewBox = document.getElementById('char-form-preview-box');
      if (previewBox && c.has_image) {
        previewBox.innerHTML = `<img src="${c.image_url}" style="width:100%;height:100%;object-fit:cover;">`;
      }
      document.getElementById('form-create-character').scrollIntoView({ behavior: 'smooth' });
    }

    async function deleteCharacterFromLibrary(charId) {
      if (!confirm(`確定要從角色庫刪除 ${charId} 嗎？`)) return;
      try {
        await apiRequest(`/api/characters/${encodeURIComponent(charId)}`, { method: 'DELETE' })

        if (typeof showToast === 'function') showToast(`✓ 角色 ${charId} 已刪除`);
        loadCharactersLibrary();
      } catch (err) {
        alert(`刪除失敗: ${err.message}`);
      }
    }

    function previewCharUploadImage(input) {
      const previewBox = document.getElementById('char-form-preview-box');
      if (!input.files || !input.files[0] || !previewBox) return;
      const reader = new FileReader();
      reader.onload = function(e) {
        previewBox.innerHTML = `<img src="${e.target.result}" style="width:100%;height:100%;object-fit:cover;">`;
      };
      reader.readAsDataURL(input.files[0]);
    }

    async function generateAiPortraitForForm() {
      const idVal = document.getElementById('char-input-id').value.trim() || ('char_' + Date.now());
      const promptVal = document.getElementById('char-input-appearance').value.trim();
      const statusEl = document.getElementById('char-gen-status');
      const previewBox = document.getElementById('char-form-preview-box');
      if (!promptVal) {
        alert("請先在外貌定妝描述框輸入提示詞！");
        return;
      }
      if (statusEl) statusEl.innerHTML = `🍌 AI 生成中...`;

      try {
        const data = await apiJson(`/api/characters/${encodeURIComponent(idVal)}/generate_portrait`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: promptVal, aspect_ratio: '1:1' })
        });


        if (previewBox) {
          previewBox.innerHTML = `<img src="${data.image_url}" style="width:100%;height:100%;object-fit:cover;">`;
        }
        if (statusEl) statusEl.innerHTML = `✅ 已生成定妝照！`;
        if (typeof showToast === 'function') showToast(`✓ 定妝照已成功繪製並儲存！`);
        setTimeout(() => { if (statusEl) statusEl.innerHTML = ''; }, 3000);
      } catch (err) {
        alert(`生成失敗: ${err.message}`);
        if (statusEl) statusEl.innerHTML = `❌ 失敗: ${err.message}`;
      }
    }

    function resetCharacterForm() {
      const f = document.getElementById('form-create-character');
      if (f) f.reset();
      const previewBox = document.getElementById('char-form-preview-box');
      if (previewBox) previewBox.innerHTML = `<span style="font-size:28px;">👤</span>`;
      const statusEl = document.getElementById('char-gen-status');
      if (statusEl) statusEl.innerHTML = '';
      populateCharFormVoices();
    }


    // ---------------- Custom Formula Manager Functions ----------------
    let modalLoadedFormulas = [];
    let modalAutocompletedData = null;

    function getProportionalScenesCount(sec) {
      const s = parseInt(sec) || 50;
      return Math.max(4, Math.round(s / 4.5));
    }

    function updateDramaScriptButtonText(sec) {
      const btn = document.getElementById('btn-gen-drama-script');
      if (btn) {
        const sc = getProportionalScenesCount(sec);
        btn.innerHTML = `✨ 依時長生成劇本 (${sec}s / ${sc} 鏡)`;
      }
    }

    async function openFormulaManagerModal() {
      const modal = document.getElementById('formula-manager-modal');
      if (modal) modal.style.display = 'flex';
      await refreshFormulaManagerList();
      // Reset form
      const nameInput = document.getElementById('custom-formula-name');
      const premiseInput = document.getElementById('custom-formula-premise');
      const countSel = document.getElementById('custom-formula-char-count');
      const previewArea = document.getElementById('custom-formula-preview-area');
      if (nameInput) nameInput.value = '';
      if (premiseInput) premiseInput.value = '';
      if (countSel) countSel.value = '2';
      if (previewArea) previewArea.style.display = 'none';
      modalAutocompletedData = null;
    }

    function closeFormulaManagerModal() {
      const modal = document.getElementById('formula-manager-modal');
      if (modal) modal.style.display = 'none';
    }

    async function refreshFormulaManagerList() {
      const container = document.getElementById('modal-formula-list');
      if (!container) return;
      container.innerHTML = '<div style="color: #94a3b8; font-size: 12px; padding: 6px;">載入公式清單中...</div>';
      try {
        const data = await apiJson('/api/drama/formulas');


        modalLoadedFormulas = data.formulas || [];
        if (modalLoadedFormulas.length === 0) {
          container.innerHTML = '<div style="color: #94a3b8; font-size: 12px; padding: 6px;">尚無公式</div>';
          return;
        }
        let html = '';
        modalLoadedFormulas.forEach(f => {
          const isCustom = Boolean(f.is_custom);
          const charsCount = (f.default_characters || []).length;
          html += `
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; padding: 8px 12px;">
              <div style="flex: 1; padding-right: 12px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px;">
                  <strong style="color: ${isCustom ? '#fbbf24' : '#60a5fa'}; font-size: 13px;">${f.name}</strong>
                  <span style="font-size: 10px; padding: 1px 6px; border-radius: 4px; background: ${isCustom ? 'rgba(217,119,6,0.2)' : 'rgba(59,130,246,0.2)'}; color: ${isCustom ? '#f59e0b' : '#93c5fd'}; border: 1px solid ${isCustom ? 'rgba(217,119,6,0.4)' : 'rgba(59,130,246,0.4)'};">
                    ${isCustom ? '🛠️ 自訂公式' : '✨ 經典內建'}
                  </span>
                  <span style="font-size: 11px; color: #94a3b8;">(${charsCount} 位角色)</span>
                </div>
                <div style="font-size: 11.5px; color: #cbd5e1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 520px;">
                  ${f.hook_premise || '無大綱描述'}
                </div>
              </div>
              <div>
                ${isCustom ? `
                  <button type="button" onclick="deleteFormulaFromManager('${f.id}')" style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #ef4444; padding: 3px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; font-weight: 700;">
                    🗑️ 刪除
                  </button>
                ` : `
                  <span style="font-size: 11px; color: #64748b; padding: 3px 6px;">內建鎖定</span>
                `}
              </div>
            </div>
          `;
        });
        container.innerHTML = html;
      } catch (err) {
        container.innerHTML = `<div style="color: #ef4444; font-size: 12px; padding: 6px;">載入失敗: ${err.message}</div>`;
      }
    }

    async function triggerFormulaAutocomplete() {
      const nameInput = document.getElementById('custom-formula-name');
      const premiseInput = document.getElementById('custom-formula-premise');
      const countSel = document.getElementById('custom-formula-char-count');
      const btn = document.getElementById('btn-autocomplete-formula');
      const previewArea = document.getElementById('custom-formula-preview-area');

      const premise = premiseInput ? premiseInput.value.trim() : '';
      if (!premise) {
        alert('請先輸入基本劇情大綱 (Basic Plot / Premise)！');
        if (premiseInput) premiseInput.focus();
        return;
      }
      const charCount = parseInt(countSel ? countSel.value : '2') || 2;
      const formulaName = nameInput ? nameInput.value.trim() : '';

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ 正在呼叫 AI 智能補完結構...';
      }

      try {
        const data = await apiJson('/api/drama/formulas/autocomplete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            basic_plot: premise,
            character_count: charCount,
            formula_name: formulaName
          })
        });


        modalAutocompletedData = data;

        if (nameInput && !nameInput.value.trim() && data.name) {
          nameInput.value = data.name;
        }

        // Render beats preview
        const beatsContainer = document.getElementById('custom-formula-beats-preview');
        if (beatsContainer) {
          beatsContainer.innerHTML = (data.beats || []).map(b => `<div>• ${b}</div>`).join('');
        }

        // Render characters preview
        const charsContainer = document.getElementById('custom-formula-chars-preview');
        if (charsContainer) {
          charsContainer.innerHTML = (data.default_characters || []).map(c => `
            <div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 8px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <strong style="color: #f59e0b; font-size: 12px;">${c.name} (${c.role || '角色'})</strong>
                <span style="font-size: 10px; color: #94a3b8;">${c.gender === 'female' ? '♀ 女性' : '♂ 男性'}, ${c.age || 28}歲</span>
              </div>
              <div style="font-size: 10.5px; color: #cbd5e1; line-height: 1.4; margin-bottom: 4px;">
                ${c.appearance || ''}
              </div>
              <div style="font-size: 10px; color: #38bdf8;">
                🎙️ 音色: ${c.voice_provider || '預設'} (${c.voice_persona || ''})
              </div>
            </div>
          `).join('');
        }

        // Render default script preview
        const scriptArea = document.getElementById('custom-formula-script-preview');
        if (scriptArea) {
          scriptArea.value = data.default_script || '';
        }

        if (previewArea) previewArea.style.display = 'block';
        if (typeof showToast === 'function') showToast('✓ AI 智能補完三幕節奏與角色定妝完成！');
      } catch (err) {
        alert('智能補完失敗: ' + err.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<span>✨</span> AI 智能補完三幕節奏與角色定妝';
        }
      }
    }

    async function saveNewCustomFormula() {
      const nameInput = document.getElementById('custom-formula-name');
      const premiseInput = document.getElementById('custom-formula-premise');
      const countSel = document.getElementById('custom-formula-char-count');
      const scriptArea = document.getElementById('custom-formula-script-preview');

      const name = nameInput ? nameInput.value.trim() : '';
      if (!name) {
        alert('請輸入公式名稱！');
        if (nameInput) nameInput.focus();
        return;
      }
      const premise = premiseInput ? premiseInput.value.trim() : '';
      if (!premise) {
        alert('請輸入基本劇情大綱！');
        if (premiseInput) premiseInput.focus();
        return;
      }

      let payload = null;
      if (modalAutocompletedData) {
        payload = {
          name: name,
          hook_premise: premise,
          aesthetic_profile: modalAutocompletedData.aesthetic_profile,
          default_primary_setting: modalAutocompletedData.default_primary_setting,
          character_count: parseInt(countSel ? countSel.value : '2') || 2,
          beats: modalAutocompletedData.beats,
          default_characters: modalAutocompletedData.default_characters,
          default_script: scriptArea ? scriptArea.value.trim() : (modalAutocompletedData.default_script || '')
        };
      } else {
        // Fallback default structure
        const charCount = parseInt(countSel ? countSel.value : '2') || 2;
        payload = {
          name: name,
          hook_premise: premise,
          character_count: charCount,
          beats: [
            'Beat 1 (0-3s Hook): 衝突爆發震撼開場',
            'Beat 2 (10-25s Tension): 危機加深與多輪語言交鋒',
            'Beat 3 (35-50s Payoff): 絕殺反轉與打臉收尾'
          ],
          default_characters: [
            {
              id: 'lead_heroine',
              name: '主角',
              role: '女主角 / 隱藏實力者',
              gender: 'female',
              age: 26,
              appearance: '26-year-old sleek elegant East Asian woman, sharp intelligent eyes, dark tailored blouse, studio lighting, photorealistic portrait',
              voice_persona: '冷靜沉著、聲音清晰',
              voice_provider: 'ichiehchieh'
            },
            {
              id: 'antagonist_boss',
              name: '對手',
              role: '反派 / 自負壓迫者',
              gender: 'male',
              age: 45,
              appearance: '45-year-old arrogant East Asian man, silk shirt, heavy gold ring, smug smirk, photorealistic portrait',
              voice_persona: '語速沉緩、帶威脅的中年男聲',
              voice_provider: 'mytsaovoicemagpie'
            }
          ],
          default_script: scriptArea ? scriptArea.value.trim() : `${name} 示範對白...`
        };
      }

      const saveBtn = document.getElementById('btn-save-custom-formula');
      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '⏳ 儲存中...';
      }

      try {
        const result = await apiJson('/api/drama/formulas', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });


        const savedFormula = result.formula;

        await loadDramaFormulas();

        // Select the new formula in main select
        const formulaSel = document.getElementById('drama-formula-select');
        if (formulaSel && savedFormula && savedFormula.id) {
          formulaSel.value = savedFormula.id;
          onDramaFormulaSelectChange(savedFormula.id);
        }

        closeFormulaManagerModal();
        if (typeof showToast === 'function') showToast(`✓ 成功建立自訂公式「${name}」並已立即套用！`);
      } catch (err) {
        alert('儲存自訂公式失敗: ' + err.message);
      } finally {
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.innerHTML = '💾 儲存自訂公式並套用';
        }
      }
    }

    async function deleteFormulaFromManager(fid) {
      if (!confirm(`確定要刪除此自訂公式嗎？此操作不可逆。`)) return;
      try {
        await apiRequest(`/api/drama/formulas/${fid}`, { method: 'DELETE' })

        await refreshFormulaManagerList();
        await loadDramaFormulas();
        if (typeof showToast === 'function') showToast('✓ 自訂公式已刪除！');
      } catch (err) {
        alert('刪除公式失敗: ' + err.message);
      }
    }


    async function loadDramaFormulas() {
      try {
        const data = await apiJson('/api/drama/formulas');


        if (data && data.formulas && Array.isArray(data.formulas)) {
          const formulaSel = document.getElementById('drama-formula-select');
          const prevVal = formulaSel ? formulaSel.value : 'workplace_revenge';

          let optionsHtml = '';
          data.formulas.forEach(f => {
            if (f.id) {
              DRAMA_FORMULAS_PRESETS[f.id] = f;
              const isCustom = Boolean(f.is_custom);
              const tag = isCustom ? '🛠️ [自訂] ' : (f.id === 'workplace_revenge' ? '⚡ ' : (f.id === 'suspense_twist' ? '🔍 ' : '🚀 '));
              optionsHtml += `<option value="${f.id}">${tag}${f.name}</option>`;
            }
          });
          optionsHtml += '<option value="custom">✍️ 自訂故事大綱與衝突劇本</option>';

          if (formulaSel) {
            formulaSel.innerHTML = optionsHtml;
            // Restore selection if exists
            if (DRAMA_FORMULAS_PRESETS[prevVal] || prevVal === 'custom') {
              formulaSel.value = prevVal;
            } else {
              formulaSel.value = data.formulas[0] ? data.formulas[0].id : 'workplace_revenge';
            }
          }

          if (currentCreatorProjectMode === 'short_drama' && formulaSel) {
            onDramaFormulaSelectChange(formulaSel.value);
          }
        }
      } catch (err) {
        console.debug("Could not fetch drama formulas from backend:", err);
      }
    }

    let pendingCreationAction = null;

    function closeCreateVideoConfirmModal() {
      const m = document.getElementById('create-video-confirm-modal');
      if (m) m.style.display = 'none';
      pendingCreationAction = null;
    }
    window.closeCreateVideoConfirmModal = closeCreateVideoConfirmModal;

    function confirmAndProceedWithVideo() {
      const action = pendingCreationAction;
      closeCreateVideoConfirmModal();
      if (typeof action === 'function') {
        action();
      }
    }
    window.confirmAndProceedWithVideo = confirmAndProceedWithVideo;

    function getActiveRemotionStyleInfo(stageModels, ai_pct) {
      const animModel = stageModels?.animation || document.getElementById('model-stage-animation')?.value || 'kenburns';
      const preset = window.activeRemotionPreset;

      const isAnimModelRemotion = typeof animModel === 'string' && (animModel.startsWith('remotion') || animModel === 'remotion');
      if (!isAnimModelRemotion) {
        return { isSelected: false, styleName: null };
      }

      let styleName = '';
      if (preset === 'gary_chen' || (animModel === 'remotion' && ai_pct === 0 && preset !== 'blueprint')) {
        styleName = '✨ Gary Chen 極簡現代科技解說 (modern_tech_explainer)';
      } else if (preset === 'coordinate_zero' || animModel === 'remotion_coordinate_scale') {
        styleName = '🧭 座標零: 等緯尺度 (Coordinate Scale)';
      } else if (animModel === 'remotion_coordinate_experiment') {
        styleName = '🔬 座標零: 桌面實驗 (Coordinate Experiment)';
      } else if (animModel === 'remotion_coordinate_split') {
        styleName = '⚖️ 座標零: 各對一半 (Coordinate Split)';
      } else if (preset === 'finance_market' || animModel === 'remotion_finance_candlestick') {
        styleName = '📈 金融市場: 盤勢結構 (Finance Candlestick)';
      } else if (animModel === 'remotion_finance_metrics') {
        styleName = '📊 金融市場: 財務指標 (Finance Metrics)';
      } else if (preset === 'archival_history' || animModel === 'remotion_archival_doc') {
        styleName = '📜 歷史檔案: 解密公文 (Archival Document)';
      } else if (animModel === 'remotion_history_chrono') {
        styleName = '⏳ 歷史檔案: 年代編年 (History Chronology)';
      } else if (preset === 'vox_journalism' || animModel === 'remotion_vox_split') {
        styleName = '🗞️ Vox 調查: 政策雙分割 (Vox Split-Screen)';
      } else if (animModel === 'remotion_vox_keystat') {
        styleName = '⚡ Vox 調查: 核心發現 (Vox Key Stat)';
      } else if (animModel === 'remotion_pathway') {
        styleName = '🔀 分支決策 (Branch Pathway)';
      } else if (animModel === 'remotion_callout') {
        styleName = '🎯 引線標註 (Leader Callout)';
      } else if (animModel === 'remotion_scale') {
        styleName = '🔬 尺度對比 (Scale Loupe)';
      } else if (animModel === 'remotion_evidence' || preset === 'blueprint') {
        styleName = '📑 藍圖: 文獻劃記 (Evidence Highlight / Blueprint)';
      } else {
        const opt = document.querySelector(`#model-stage-animation option[value="${animModel}"]`);
        styleName = opt ? opt.textContent.replace(/\(\+ Ken Burns\)/, '').trim() : animModel;
      }

      return { isSelected: true, styleName: styleName };
    }

    async function startDramaCreation() {
      const topicEl = document.getElementById('drama-topic');
      const topic = (topicEl ? topicEl.value.trim() : '') || '開除我？那套AI是我寫的';
      if (!topic) {
        alert("請輸入短劇主題 (Drama Topic)！");
        if (topicEl) topicEl.focus();
        return;
      }
      const durEl = document.getElementById('drama-duration');
      const durationSec = durEl ? parseInt(durEl.value || '50') : 50;
      const formulaEl = document.getElementById('drama-formula-select');
      const formula = formulaEl ? formulaEl.value : 'workplace_revenge';
      const aspectEl = document.getElementById('drama-aspect-ratio');
      const aspectRatio = aspectEl ? aspectEl.value : '9:16';
      const scriptTa = document.getElementById('drama-custom-script');
      const scriptText = (scriptTa && scriptTa.value.trim()) ? scriptTa.value.trim() : topic;
      const animEngineEl = document.getElementById('drama-anim-engine');
      const animEngine = animEngineEl ? animEngineEl.value : 'hedra';

      const sanitizedCharacters = (currentProjectDramaCharacters || []).map((c, idx) => ({
        id: (c.id && c.id !== 'None') ? c.id : ('actor_' + (idx + 1) + '_' + Date.now()),
        name: c.name || `角色${idx + 1}`,
        role: c.role || '關鍵角色',
        gender: c.gender || 'female',
        age: c.age || 28,
        appearance: c.appearance || '',
        voice_persona: c.voice_persona || '',
        voice_profile: c.voice_profile || (cachedVoiceList && cachedVoiceList[0] ? cachedVoiceList[0].name : 'ichiehchieh'),
        image_data_uri: c.image_data_uri || null,
        image_url: c.image_url || null
      }));

      const charNames = sanitizedCharacters.length > 0 
        ? sanitizedCharacters.map(c => `${c.name} (${c.role || '角色'})`).join(', ')
        : '預設微短劇角色名冊 (Auto Default Cast)';

      // Populate modal fields
      const modalTopicEl = document.getElementById('confirm-modal-topic');
      if (modalTopicEl) modalTopicEl.textContent = topic;
      const modalDurEl = document.getElementById('confirm-modal-duration');
      if (modalDurEl) modalDurEl.textContent = `${durationSec} 秒 (${durationSec}s)`;
      const modalVoiceEl = document.getElementById('confirm-modal-voice');
      if (modalVoiceEl) modalVoiceEl.textContent = '角色專屬音色 (Character Voice TTS)';
      const modalAvatarEl = document.getElementById('confirm-modal-avatar');
      if (modalAvatarEl) modalAvatarEl.textContent = charNames;
      const modalLangEl = document.getElementById('confirm-modal-language');
      if (modalLangEl) modalLangEl.textContent = 'Traditional Chinese (繁體中文)';

      const remotionRow = document.getElementById('confirm-modal-remotion-row');
      if (remotionRow) remotionRow.style.display = 'none';

      pendingCreationAction = () => executeDramaCreation({
        topic,
        durationSec,
        formula,
        aspectRatio,
        scriptText,
        animEngine,
        sanitizedCharacters
      });

      const modal = document.getElementById('create-video-confirm-modal');
      if (modal) modal.style.display = 'flex';
    }

    async function executeDramaCreation(params) {
      const { topic, durationSec, formula, aspectRatio, scriptText, animEngine, sanitizedCharacters } = params;
      const btn = document.getElementById('btn-create-drama-video');
      const origText = btn ? btn.innerHTML : '🎬 CREATE AI SHORT DRAMA';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ 正在建立微短劇專案...';
      }

      try {
        const data = await apiJson('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            topic: topic,
            duration_minutes: durationSec / 60.0,
            project_mode: 'short_drama',
            aspect_ratio: aspectRatio,
            drama_formula: formula,
            drama_duration_seconds: durationSec,
            drama_characters: sanitizedCharacters,
            drama_script: scriptText,
            stage_models: {
              animation: animEngine,
              research: 'ollama',
              script: 'gemini',
              scenes: 'openai_compat',
              prompts: 'gemini',
              images: 'nano-banana-2.1',
              voice: 'bluemagpie',
              subtitles: 'local',
              render: 'h264_amf'
            },
            cloud_enabled: true,
            start_now: true
          })
        });

        projectStartTime = Date.now();
        showToast(`🎬 微短劇專案已成功建立: ${data.project_id}！已啟動全自動生成。`);
        await loadProjectsList();
        selectProject(data.project_id);
      } catch (err) {
        alert("微短劇專案建立失敗: " + err.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = origText;
        }
      }
    }

    async function startCreation() {
      if (currentCreatorProjectMode === 'short_drama') {
        return startDramaCreation();
      }

      const topicEl = document.getElementById('topic');
      const topic = topicEl ? topicEl.value.trim() : '';
      if (!topic) {
        if (topicEl) topicEl.focus();
        return alert("Please enter a topic");
      }

      const durationEl = document.getElementById('duration');
      const duration = durationEl ? parseFloat(durationEl.value) : 10;
      const durationText = durationEl?.options[durationEl.selectedIndex]?.text || `${duration} Minutes`;

      const languageEl = document.getElementById('language');
      const language = languageEl ? languageEl.value : 'Traditional Chinese';
      const languageText = languageEl?.options[languageEl.selectedIndex]?.text || language;

      const voiceEl = document.getElementById('voice-select');
      let voice = voiceEl ? voiceEl.value : '';
      const stageVoiceModel = document.getElementById('model-stage-voice') ? document.getElementById('model-stage-voice').value : null;
      let chosenVoiceObj = (cachedVoiceList || []).find(v => v.name === voice);
      if (!chosenVoiceObj && stageVoiceModel) {
        chosenVoiceObj = (cachedVoiceList || []).find(v => v.provider === stageVoiceModel || ((stageVoiceModel === 'cosyvoice' || stageVoiceModel === 'cozyvoice') && (v.provider === 'cosyvoice' || v.provider === 'cozyvoice')));
        if (chosenVoiceObj) voice = chosenVoiceObj.name;
      }
      if (chosenVoiceObj && chosenVoiceObj.provider) {
        voice = chosenVoiceObj.name;
      }
      const voiceText = voiceEl?.options[voiceEl.selectedIndex]?.text || voice || 'Default Voice';

      const placementEl = document.getElementById('creator-presenter-placement');
      const presenterPlacement = placementEl ? placementEl.value : (document.getElementById('creator-auto-presenter') && document.getElementById('creator-auto-presenter').checked ? 'intro' : 'none');
      const avatarEl = document.getElementById('creator-presenter-avatar');
      const defaultAvatar = avatarEl ? avatarEl.value : null;
      const autoPresenter = presenterPlacement !== 'none';

      const stageModels = getSelectedStageModels();
      const ai_pct = parseFloat(document.getElementById('ai-video-pct')?.value || '0');

      // Avatar character selection display text
      const isPureRemotionNoPresenter = (window.activeRemotionPreset === 'gary_chen' || (stageModels.animation === 'remotion' && ai_pct === 0 && window.activeRemotionPreset !== 'blueprint'));
      let avatarText = '🚫 不出鏡 (None / No presenter avatar)';
      if (!isPureRemotionNoPresenter && autoPresenter && presenterPlacement !== 'none') {
        const avName = avatarEl?.options[avatarEl.selectedIndex]?.text || defaultAvatar || 'Presenter Avatar';
        const plName = placementEl?.options[placementEl.selectedIndex]?.text || presenterPlacement;
        avatarText = `${avName} · [${plName}]`;
      }

      // Remotion style (if Remotion is selected)
      const remotionInfo = getActiveRemotionStyleInfo(stageModels, ai_pct);

      // Populate confirmation modal fields
      const modalTopicEl = document.getElementById('confirm-modal-topic');
      if (modalTopicEl) modalTopicEl.textContent = topic;
      const modalDurEl = document.getElementById('confirm-modal-duration');
      if (modalDurEl) modalDurEl.textContent = durationText;
      const modalVoiceEl = document.getElementById('confirm-modal-voice');
      if (modalVoiceEl) modalVoiceEl.textContent = voiceText;
      const modalAvatarEl = document.getElementById('confirm-modal-avatar');
      if (modalAvatarEl) modalAvatarEl.textContent = avatarText;
      const modalLangEl = document.getElementById('confirm-modal-language');
      if (modalLangEl) modalLangEl.textContent = languageText;

      const remotionRow = document.getElementById('confirm-modal-remotion-row');
      const remotionStyleEl = document.getElementById('confirm-modal-remotion-style');
      if (remotionInfo.isSelected) {
        if (remotionRow) remotionRow.style.display = 'flex';
        if (remotionStyleEl) remotionStyleEl.textContent = remotionInfo.styleName;
      } else {
        if (remotionRow) remotionRow.style.display = 'none';
      }

      pendingCreationAction = () => executeCreation();

      const modal = document.getElementById('create-video-confirm-modal');
      if (modal) modal.style.display = 'flex';
    }

    async function executeCreation() {
      const topic = document.getElementById('topic').value.trim();
      if (!topic) return alert("Please enter a topic");
      const duration = parseFloat(document.getElementById('duration').value);
      const language = document.getElementById('language').value;
      let voice = document.getElementById('voice-select').value;
      const stageVoiceModel = document.getElementById('model-stage-voice') ? document.getElementById('model-stage-voice').value : null;
      const style = document.getElementById('visual-style').value;
      const ckptEl = document.getElementById('checkpoint-select');
      let checkpoint = ckptEl ? ckptEl.value : null;
      const stageModels = getSelectedStageModels();
      // Guarantee Stage 6 voice model is 100% aligned with the chosen voice profile or chosen engine
      let chosenVoiceObj = (cachedVoiceList || []).find(v => v.name === voice);
      if (!chosenVoiceObj && stageVoiceModel) {
        chosenVoiceObj = (cachedVoiceList || []).find(v => v.provider === stageVoiceModel || ((stageVoiceModel === 'cosyvoice' || stageVoiceModel === 'cozyvoice') && (v.provider === 'cosyvoice' || v.provider === 'cozyvoice')));
        if (chosenVoiceObj) voice = chosenVoiceObj.name;
      }
      if (chosenVoiceObj && chosenVoiceObj.provider) {
        stageModels.voice = chosenVoiceObj.provider;
        voice = chosenVoiceObj.name;
      }
      if (stageModels.images === 'stock' || checkpoint === 'stock' || (isCloudAccelerationActive() && (CLOUD_IMAGE_ENGINES.includes(checkpoint) || checkpoint === 'comfyui'))) {
        checkpoint = null;
      }
      const ai_pct = parseFloat(document.getElementById('ai-video-pct').value);
      const cloud = document.getElementById('cloud-toggle').value === 'true';
      const musicSelectEl = document.getElementById('music-select');
      const musicCatEl = document.getElementById('music-category-select');
      const musicProgEl = document.getElementById('music-progression-select');
      const musicCategory = musicCatEl ? musicCatEl.value : 'auto';
      const musicTrack = (musicCategory === 'none') ? 'none' : (musicSelectEl ? musicSelectEl.value : 'auto');
      const musicProgression = musicProgEl ? musicProgEl.value : 'narrative_evolving';
      const musicVolEl = document.getElementById('music-volume');
      const musicVolume = musicVolEl ? parseFloat(musicVolEl.value) : -16.0;
      const placementEl = document.getElementById('creator-presenter-placement');
      const presenterPlacement = placementEl ? placementEl.value : (document.getElementById('creator-auto-presenter') && document.getElementById('creator-auto-presenter').checked ? 'intro' : 'none');
      const avatarEl = document.getElementById('creator-presenter-avatar');
      const defaultAvatar = avatarEl ? avatarEl.value : null;
      const autoPresenter = presenterPlacement !== 'none';

      // Creator Custom Research Dossier payload
      const userResearchEl = document.getElementById('creator-user-research');
      const userResearch = userResearchEl ? userResearchEl.value.trim() : null;
      const researchModeEl = document.querySelector('input[name="creator-research-mode"]:checked');
      const researchMode = researchModeEl ? researchModeEl.value : 'auto';
      const pauseAfterResearch = document.getElementById('creator-pause-after-research') ? document.getElementById('creator-pause-after-research').checked : false;

      const btn = document.getElementById('btn-create-video');
      const btn2 = document.getElementById('btn-create-video-bottom');
      const origText = btn ? btn.innerHTML : 'CREATE VIDEO';
      const origText2 = btn2 ? btn2.innerHTML : 'CREATE VIDEO';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ CREATING PROJECT...';
      }
      if (btn2) {
        btn2.disabled = true;
        btn2.innerHTML = '⏳ CREATING PROJECT...';
      }

      try {
        const data = await apiJson('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            topic: topic,
            duration_minutes: duration,
            language: language,
            voice_profile: voice,
            visual_style: style,
            checkpoint: checkpoint,
            ai_video_percentage: ai_pct,
            cloud_enabled: cloud,
            stage_models: stageModels,
            callout_style: (document.getElementById('creator-callout-style')?.value || document.getElementById('set-callout-banner-style')?.value || 'fox_kinetic'),
            music_track: musicTrack,
            music_category: musicCategory,
            music_progression: musicProgression,
            music_volume_db: musicVolume,
            auto_presenter: ((window.activeRemotionPreset === 'gary_chen' || (stageModels.animation === 'remotion' && ai_pct === 0 && window.activeRemotionPreset !== 'blueprint')) ? false : autoPresenter),
            presenter_placement: ((window.activeRemotionPreset === 'gary_chen' || (stageModels.animation === 'remotion' && ai_pct === 0 && window.activeRemotionPreset !== 'blueprint')) ? 'none' : presenterPlacement),
            default_avatar: defaultAvatar,
            remotion_density: ((window.activeRemotionPreset === 'gary_chen' || window.activeRemotionPreset === 'blueprint' || (stageModels.animation === 'remotion' && ai_pct === 0)) ? 'full' : null),
            remotion_style: ((window.activeRemotionPreset === 'gary_chen' || (stageModels.animation === 'remotion' && ai_pct === 0 && window.activeRemotionPreset !== 'blueprint')) ? 'modern_tech_explainer' : (window.activeRemotionPreset === 'blueprint' ? 'EvidenceHighlightScene' : null)),
            remotion_theme: ((window.activeRemotionPreset === 'gary_chen' || (stageModels.animation === 'remotion' && ai_pct === 0 && window.activeRemotionPreset !== 'blueprint')) ? 'dark_obsidian' : 'blueprint'),
            remotion: ((window.activeRemotionPreset === 'gary_chen' || (stageModels.animation === 'remotion' && ai_pct === 0 && window.activeRemotionPreset !== 'blueprint')) ? {
              style: 'modern_tech_explainer',
              theme: 'dark_obsidian',
              density: 'full',
              accentColor: '#38BDF8'
            } : (window.activeRemotionPreset === 'blueprint' ? {
              style: 'EvidenceHighlightScene',
              theme: 'blueprint',
              density: 'full'
            } : null)),
            user_research: userResearch || null,
            research_mode: researchMode,
            pause_after_research: pauseAfterResearch,
            author_conclusion: (document.getElementById('creator-author-conclusion')?.value || '').trim() || null,
            include_author_take: document.getElementById('creator-include-author-take') ? document.getElementById('creator-include-author-take').checked : true,
            pause_for_conclusion: document.getElementById('creator-pause-for-conclusion') ? document.getElementById('creator-pause-for-conclusion').checked : false,
            auto_stock_mode: document.getElementById('auto-stock-mode')?.value || 'balanced',
            project_mode: 'documentary',
            aspect_ratio: '16:9',
            start_now: true
          })
        });




        projectStartTime = Date.now();
        showToast(`🚀 Project created: ${data.project_id}`);
        await loadProjectsList();
        selectProject(data.project_id);

        // Automatically clear the loaded research JSON file / dossier so the next video generation starts clean
        clearCreatorResearch(true);

        // Reset topic input field for the next video
        const topicEl = document.getElementById('topic');
        if (topicEl) topicEl.value = '';
      } catch (err) {
        console.error("Project creation failed:", err);
        alert(`Failed to create project: ${err.message}`);
        showToast(`❌ Error creating project: ${err.message}`);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = origText;
        }
        if (btn2) {
          btn2.disabled = false;
          btn2.innerHTML = origText2;
        }
      }
    }

    function startPolling() {
      const generation = ++pollGeneration;
      const projectId = currentProjectId;
      if (pollInterval) clearTimeout(pollInterval);
      if (pollController) pollController.abort();
      const tick = async () => {
        const keepPolling = await pollProject(generation, projectId);
        if (keepPolling && generation === pollGeneration && projectId === currentProjectId) {
          pollInterval = setTimeout(tick, 1500);
        }
      };
      tick();
      startTimer();
    }

    async function pollProject(generation = pollGeneration, projectId = currentProjectId) {
      if (!projectId || generation !== pollGeneration || projectId !== currentProjectId) return false;
      const controller = new AbortController();
      pollController = controller;
      try {
        const d = await apiJson('/api/projects/' + projectId + '/status', { signal: controller.signal });
        if (generation !== pollGeneration || projectId !== currentProjectId) return false;
        const p = d.project;

        const isRunning = p.state === 'running';
        const banner = document.getElementById('global-hero-banner');
        banner.style.display = 'block';
        if (isRunning) {
          banner.classList.add('is-running');
          document.getElementById('hero-spinner').style.display = 'inline-block';
          document.getElementById('hero-pulse-dot').className = 'pulse-dot running';
          document.getElementById('hero-btn-stop').style.display = 'inline-block';
          document.getElementById('hero-btn-resume').style.display = 'none';
        } else {
          banner.classList.remove('is-running');
          document.getElementById('hero-spinner').style.display = 'none';
          document.getElementById('hero-pulse-dot').className = 'pulse-dot';
          document.getElementById('hero-btn-stop').style.display = 'none';
          if (p.state === 'paused' || p.state === 'failed') {
            document.getElementById('hero-btn-resume').style.display = 'inline-block';
          } else {
            document.getElementById('hero-btn-resume').style.display = 'none';
          }
        }

        const isRenderRunning = isRunning && (
          p.stage === 'render' ||
          (p.stages && p.stages.render && p.stages.render.status === 'RUNNING') ||
          (p.activity && (p.activity.toLowerCase().includes('render') || p.activity.toLowerCase().includes('ffmpeg') || p.activity.toLowerCase().includes('stringing')))
        );
        const btnCreatorStop = document.getElementById('btn-creator-stop-render');
        if (btnCreatorStop) {
          btnCreatorStop.style.display = isRenderRunning ? 'inline-block' : 'none';
        }

        const hasFinalVideo = !!(p.outputs && p.outputs.final);
        const heroYtBtn = document.getElementById('hero-btn-yt-upload');
        const heroYtLink = document.getElementById('hero-btn-yt-link');
        const creatorYtBtn = document.getElementById('btn-creator-yt-upload');

        if (heroYtBtn) {
          heroYtBtn.style.display = hasFinalVideo ? 'inline-flex' : 'none';
          const txt = document.getElementById('hero-yt-upload-text');
          if (txt) {
            txt.textContent = (p.outputs && p.outputs.youtube_url) ? 'Re-upload to YouTube' : 'Upload to YouTube (@tsao36)';
          }
        }
        if (heroYtLink) {
          if (hasFinalVideo && p.outputs && p.outputs.youtube_url) {
            heroYtLink.style.display = 'inline-flex';
            heroYtLink.href = p.outputs.youtube_url;
          } else {
            heroYtLink.style.display = 'none';
          }
        }
        if (creatorYtBtn) {
          creatorYtBtn.style.display = hasFinalVideo ? 'inline-flex' : 'none';
          const txt = document.getElementById('btn-creator-yt-upload-text');
          if (txt) {
            txt.textContent = (p.outputs && p.outputs.youtube_url) ? 'Re-upload to YouTube (@tsao36)' : 'Upload to YouTube (@tsao36)';
          }
        }

        // Determine current active stage
        let activeStageName = "Initializing";
        let completedCount = 0;
        let totalStages = STAGE_ORDER.length;

        for (const stKey of STAGE_ORDER) {
          const stObj = p.stages[stKey];
          if (stObj) {
            if (stObj.status === 'COMPLETED') completedCount++;
            else if (stObj.status === 'RUNNING') activeStageName = STAGE_LABELS[stKey] || stKey.toUpperCase();
          }
        }
        if (p.state === 'completed') {
          activeStageName = "COMPLETE";
          completedCount = totalStages;
        }

        const overallPct = Math.round((completedCount / totalStages) * 100);

        // Detect any project or stage error
        let detectedError = (p.error && String(p.error).trim()) || '';
        if (!detectedError && p.stages) {
          for (const [sk, stObj] of Object.entries(p.stages)) {
            if (stObj && stObj.error) {
              detectedError = `[Stage: ${sk}] ${stObj.error}`;
              break;
            }
          }
        }
        if (!detectedError && p.activity && (p.state === 'failed' || /^(failed|render failed|draft render failed|error)/i.test(String(p.activity).trim()))) {
          detectedError = String(p.activity).trim();
        }
        window.lastProjectErrorText = detectedError;
        const hasError = Boolean(detectedError);

        // Update Hero Banner (only mutate textContent when changed so user text selection is preserved)
        const heroStageEl = document.getElementById('hero-stage-text');
        const nextStageTxt = isRunning ? activeStageName.toUpperCase() : p.state.toUpperCase();
        if (heroStageEl && heroStageEl.textContent !== nextStageTxt) heroStageEl.textContent = nextStageTxt;

        const heroBadgeEl = document.getElementById('hero-state-badge');
        if (heroBadgeEl) {
          if (heroBadgeEl.textContent !== p.state.toUpperCase()) heroBadgeEl.textContent = p.state.toUpperCase();
          heroBadgeEl.className = 'badge ' + (isRunning ? 'badge-blue' : (p.state === 'completed' ? 'badge-ok' : (p.state === 'failed' ? 'badge-danger' : 'badge-warn')));
        }

        const heroActEl = document.getElementById('hero-activity-title');
        const nextHeroAct = p.activity || (isRunning ? 'Processing...' : 'Idle');
        if (heroActEl && heroActEl.textContent !== nextHeroAct) heroActEl.textContent = nextHeroAct;

        const heroCopyBtn = document.getElementById('hero-copy-error-btn');
        if (heroCopyBtn) heroCopyBtn.style.display = hasError ? 'inline-block' : 'none';
        const tickerCopyBtn = document.getElementById('ticker-copy-error-btn');
        if (tickerCopyBtn) tickerCopyBtn.style.display = hasError ? 'inline-block' : 'none';

        document.getElementById('hero-progress-pct').textContent = overallPct + '%';
        document.getElementById('hero-progress-fill').style.width = overallPct + '%';

        if (p.state === 'completed' && p.total_duration_seconds) {
          document.getElementById('hero-elapsed-timer').textContent = `⏱️ Total: ${formatDuration(p.total_duration_seconds)}`;
          document.getElementById('hero-elapsed-timer').title = `Recorded Total Creation Time: ${formatDuration(p.total_duration_seconds)}`;
          stopTimer();
        } else if (isRunning && !timerInterval) {
          startTimer();
        }

        // Update Project Card in Creator tab
        const projTitleEl = document.getElementById('proj-title');
        const nextProjTitle = "Project: " + (p.title || p.topic);
        if (projTitleEl && projTitleEl.textContent !== nextProjTitle) projTitleEl.textContent = nextProjTitle;

        const projStateEl = document.getElementById('proj-state');
        if (projStateEl) {
          if (projStateEl.textContent !== p.state.toUpperCase()) projStateEl.textContent = p.state.toUpperCase();
          projStateEl.className = 'badge ' + (isRunning ? 'badge-blue' : (p.state === 'completed' ? 'badge-ok' : (p.state === 'failed' ? 'badge-danger' : 'badge-warn')));
        }

        const projActEl = document.getElementById('proj-activity');
        const nextProjAct = p.activity || 'Ready';
        if (projActEl && projActEl.textContent !== nextProjAct) projActEl.textContent = nextProjAct;

        const projCopyBtn = document.getElementById('proj-copy-error-btn');
        if (projCopyBtn) projCopyBtn.style.display = hasError ? 'inline-block' : 'none';

        const projErrBox = document.getElementById('proj-error-box');
        const projErrTxt = document.getElementById('proj-error-text');
        if (projErrBox && projErrTxt) {
          projErrBox.style.display = hasError ? 'block' : 'none';
          if (hasError && projErrTxt.textContent !== detectedError) {
            projErrTxt.textContent = detectedError;
          }
        }

        // Update Stage Timing Summary Bar in Creator tab
        const timingBarEl = document.getElementById('stage-timing-summary-bar');
        if (timingBarEl && p.stages) {
          const orderedStageKeys = ['research', 'script', 'scenes', 'prompts', 'images', 'voice', 'animation', 'subtitles', 'render'];
          const isProjDrama = Boolean((p.data && p.data.settings && p.data.settings.project_mode === 'short_drama') || (p.settings && p.settings.project_mode === 'short_drama') || currentCreatorProjectMode === 'short_drama');

          // Align Hero tool buttons with project mode
          const heroAvatarBtn = document.getElementById('hero-btn-rerender-avatar');
          if (heroAvatarBtn) heroAvatarBtn.style.display = isProjDrama ? 'none' : 'inline-block';

          // Align Assemble buttons with project mode
          const btnCreateAssemble1 = document.getElementById('btn-creator-assemble-stages');
          if (btnCreateAssemble1) btnCreateAssemble1.textContent = isProjDrama ? '⚡ 組裝全流程並合成短劇 (Create Drama Video)' : '🔗 String All Stages Together & Create Video';
          const btnCreateAssemble2 = document.getElementById('btn-creator-assemble-stages-2');
          if (btnCreateAssemble2) btnCreateAssemble2.textContent = isProjDrama ? '⚡ 組裝全流程並合成短劇 (Create Drama Video)' : '🔗 String All Stages Together & Render';
          const btnStudioAssemble1 = document.getElementById('btn-studio-assemble-stages');
          if (btnStudioAssemble1) btnStudioAssemble1.textContent = isProjDrama ? '⚡ 組裝全流程並合成短劇 (Create Drama Video)' : '🔗 String All Stages Together & Create Video';
          const dramaStageNames = {
            research: '1. 故事分鏡 (Storyboard)',
            script: '2. 角色劇本 (Script)',
            scenes: '3. 場景分配 (Scenes Allocation)',
            prompts: '4. 動作提示詞 (Action Prompts)',
            images: '5. 角色動態生成 (Video Generation)',
            voice: '6. 角色專屬配音 (Voice Generation)',
            animation: '7. 口型驅動同步 (Lip Sync & Sync)',
            subtitles: '8. 劇本字幕 (Subtitles)',
            render: '9. 終段微短劇合成 (Render)'
          };
          const stageIcons = isProjDrama
            ? { research: '🔬', script: '📜', scenes: '🎬', prompts: '🎨', images: '📹', voice: '🎙️', animation: '👄', subtitles: '📝', render: '⚡' }
            : { research: '🔬', script: '📜', scenes: '🎬', prompts: '🎨', images: '🖼️', voice: '🎙️', animation: '✨', subtitles: '📝', render: '⚡' };
          let sumSec = 0;
          let hasAnyStageTime = false;
          const stageChips = [];
          orderedStageKeys.forEach((sk, idx) => {
            const stObj = p.stages[sk];
            let sDur = (stObj && stObj.duration_seconds) ? Number(stObj.duration_seconds) : ((p.stage_durations && p.stage_durations[sk]) ? Number(p.stage_durations[sk]) : 0);
            if (stObj && stObj.status === 'COMPLETED' && sDur <= 0) sDur = 0.1;
            if (stObj && stObj.status === 'RUNNING' && stObj.started_at) {
              sDur = Math.max(0.1, (Date.now() - new Date(stObj.started_at).getTime()) / 1000);
            }
            if (sDur > 0 || (stObj && (stObj.status === 'COMPLETED' || stObj.status === 'RUNNING'))) {
              hasAnyStageTime = true;
              sumSec += sDur;
            }
            const stStatus = stObj ? stObj.status : 'PENDING';
            const chipColor = stStatus === 'COMPLETED' ? '#34d399' : (stStatus === 'RUNNING' ? '#60a5fa' : '#64748b');
            const chipBorder = stStatus === 'COMPLETED' ? 'rgba(16,185,129,0.35)' : (stStatus === 'RUNNING' ? 'rgba(59,130,246,0.5)' : '#1e293b');
            const durLabel = (stStatus === 'COMPLETED' || stStatus === 'RUNNING' || sDur > 0) ? formatDuration(sDur) : '—';
            stageChips.push(`
              <div style="background:#091220; border:1px solid ${chipBorder}; border-radius:6px; padding:5px 8px; display:flex; justify-content:space-between; align-items:center; gap:6px; font-size:11px;">
                <span style="color:#cbd5e1; font-weight:600; white-space:nowrap;">${stageIcons[sk] || ''} ${isProjDrama ? dramaStageNames[sk] : (idx + 1) + '. ' + sk.toUpperCase()}</span>
                <span style="color:${chipColor}; font-weight:700; font-family:monospace; white-space:nowrap;">${stStatus === 'RUNNING' ? '⏳ ' : ''}${durLabel}</span>
              </div>
            `);
          });
          const totalRecorded = (p.total_duration_seconds && p.total_duration_seconds > 0) ? p.total_duration_seconds : sumSec;
          if (hasAnyStageTime || totalRecorded > 0) {
            timingBarEl.style.display = 'block';
            timingBarEl.innerHTML = `
              <div style="background:linear-gradient(135deg, #0b1526 0%, #070d18 100%); border:1px solid #1e3a5f; border-radius:8px; padding:10px 12px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:8px;">
                  <span style="font-size:12px; font-weight:700; color:#93c5fd; letter-spacing:0.3px;">⏱️ STAGE CREATION TIME LOG (PER-STAGE DURATION)</span>
                  <span style="font-size:12px; font-weight:800; color:#38bdf8; background:rgba(56,189,248,0.12); border:1px solid rgba(56,189,248,0.3); padding:2px 8px; border-radius:4px; font-family:monospace;">
                    Total Creation Time: ${formatDuration(totalRecorded)}
                  </span>
                </div>
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(145px, 1fr)); gap:6px;">
                  ${stageChips.join('')}
                </div>
              </div>
            `;
          } else {
            timingBarEl.style.display = 'none';
          }
        }

        // Update stages grid (in-place to prevent dropdown focus loss mid-creation)
        const stagesEl = document.getElementById('stages-container');
        if (stagesEl) {
          const currentStageEntries = Object.entries(p.stages || {});
          if (stagesEl.children.length === 0 || stagesEl.querySelector('.stage-card') === null) {
            stagesEl.innerHTML = '';
            for (const [stName, st] of currentStageEntries) {
              const curModel = getProjectStageModel(p, stName);
              const opts = getStageModelOptions(stName, isProjDrama);
              const optsHtml = opts.map(o => `<option value="${o.val}" ${o.val === curModel ? 'selected' : ''}>${o.label}</option>`).join('');
              const pct = st.total > 0 ? Math.round((st.done / st.total) * 100) : (st.status === 'COMPLETED' ? 100 : 0);
              const isStRunning = st.status === 'RUNNING';
              const isStDone = st.status === 'COMPLETED';
              const cardClass = isStRunning ? 'stage-card is-running' : (isStDone ? 'stage-card is-completed' : 'stage-card');
              const durBadge = getStageDurationBadgeHtml(st);

              const cardDiv = document.createElement('div');
              cardDiv.id = `stage-card-${stName}`;
              cardDiv.className = cardClass;
              cardDiv.innerHTML = `
                <div class="stage-card-title">
                  <span id="stage-title-${stName}">${isStRunning ? '🔄 ' : (isStDone ? '✓ ' : '⏳ ')}${isProjDrama && dramaStageNames[stName] ? dramaStageNames[stName] : stName.toUpperCase()}</span>
                  <span id="stage-status-${stName}" style="font-weight:700; color:${isStRunning ? '#60a5fa' : (isStDone ? '#34d399' : '#64748b')}">${st.status}</span>
                </div>
                <div style="font-size: 12px; color: var(--text-muted); display:flex; justify-content:space-between; margin-bottom:4px;">
                  <span id="stage-items-${stName}">${st.done} / ${st.total} items</span>
                  <span id="stage-dur-${stName}">${durBadge}</span>
                </div>
                <div class="progress-bar-bg"><div id="stage-bar-${stName}" class="progress-bar-fill ${isStRunning ? 'progress-bar-striped' : ''}" style="width: ${pct}%"></div></div>
                <div style="margin-top:8px; display:flex; align-items:center; gap:6px; background:rgba(15,23,42,0.6); padding:4px 7px; border-radius:4px; border:1px solid rgba(255,255,255,0.06);">
                  <span style="font-size:11px; font-weight:700; color:#94a3b8; white-space:nowrap;" title="Switch model/engine mid-run between scenes">Engine:</span>
                  <select id="stage-card-model-${stName}" onchange="changeStageModelFromCard('${stName}', this.value)" style="flex:1; padding:2px 4px; font-size:11px; height:24px; border-radius:3px; background:#0b1120; border:1px solid #334155; color:#e2e8f0; cursor:pointer;" title="Change model at any time (e.g. ComfyUI -> Cloud DALL-E 3 / Stock / Imagen 3)">
                    ${optsHtml}
                  </select>
                </div>
                <div style="margin-top:8px; display:flex; gap:6px; justify-content:flex-end; flex-wrap:wrap;">
                  <button class="btn-sec" style="padding:3px 8px; font-size: 12px;" onclick="openStudioStage('${stName}')" title="Open in Stage Studio">🛠️ Studio</button>
                  <button class="btn-sec" style="padding:3px 8px; font-size: 12px;" onclick="openStageInspector('${stName}')" title="Inspect & Tune stage data">⚙️ Tune</button>
                  ${stName === 'scenes' ? `<button class="btn-sec" style="padding:3px 8px; font-size: 12px; background: rgba(56, 189, 248, 0.15); border-color: #0284c7; color: #38bdf8; font-weight: 600;" onclick="openStage3ExportModal()" title="匯出 Stage 3 分鏡腳本供團隊審閱">📤 匯出</button>` : ''}
                  <button id="stage-run-btn-${stName}" class="btn-sec" style="padding:3px 8px; font-size: 12px; background:var(--gradient-cta); border-color:rgba(255,255,255,0.2); color:#fff; font-weight:700;" onclick="runSingleStage('${stName}')" ${isStRunning ? 'disabled' : ''} title="Run only this stage">▶ Run</button>
                </div>
              `;
              stagesEl.appendChild(cardDiv);
            }
          } else {
            for (const [stName, st] of currentStageEntries) {
              const cardDiv = document.getElementById(`stage-card-${stName}`);
              if (!cardDiv) continue;
              const pct = st.total > 0 ? Math.round((st.done / st.total) * 100) : (st.status === 'COMPLETED' ? 100 : 0);
              const isStRunning = st.status === 'RUNNING';
              const isStDone = st.status === 'COMPLETED';
              cardDiv.className = isStRunning ? 'stage-card is-running' : (isStDone ? 'stage-card is-completed' : 'stage-card');

              const titleEl = document.getElementById(`stage-title-${stName}`);
              if (titleEl) titleEl.textContent = (isStRunning ? '🔄 ' : (isStDone ? '✓ ' : '⏳ ')) + (isProjDrama && dramaStageNames[stName] ? dramaStageNames[stName] : stName.toUpperCase());

              const statusEl = document.getElementById(`stage-status-${stName}`);
              if (statusEl) {
                statusEl.textContent = st.status;
                statusEl.style.color = isStRunning ? '#60a5fa' : (isStDone ? '#34d399' : '#64748b');
              }

              const itemsEl = document.getElementById(`stage-items-${stName}`);
              if (itemsEl) itemsEl.textContent = `${st.done} / ${st.total} items`;

              const durEl = document.getElementById(`stage-dur-${stName}`);
              if (durEl) {
                durEl.innerHTML = getStageDurationBadgeHtml(st);
              }

              const barEl = document.getElementById(`stage-bar-${stName}`);
              if (barEl) {
                barEl.style.width = pct + '%';
                barEl.className = 'progress-bar-fill' + (isStRunning ? ' progress-bar-striped' : '');
              }

              const runBtn = document.getElementById(`stage-run-btn-${stName}`);
              if (runBtn) runBtn.disabled = isStRunning;

              const modelSelect = document.getElementById(`stage-card-model-${stName}`);
              if (modelSelect && document.activeElement !== modelSelect) {
                const curModel = getProjectStageModel(p, stName);
                if (curModel && modelSelect.value !== curModel) {
                  modelSelect.value = curModel;
                }
              }
            }
          }
        }

        const studioTab = document.getElementById('tab-studio');
        if (studioTab && studioTab.classList.contains('active')) {
          renderStudioStepper(p);

          const curSt = (p.stages && typeof activeStudioStage !== 'undefined') ? p.stages[activeStudioStage] : null;
          const isProjectRunning = (p.state === 'running');
          const isCurStageRunning = curSt && (curSt.status === 'RUNNING');
          const isStudioTrackedRunning = (typeof studioStageRunning !== 'undefined' && !!studioStageRunning);
          const isAnythingRunning = isProjectRunning || isCurStageRunning || isStudioTrackedRunning;

          const alertBox = document.getElementById('studio-stage-alert');
          const runBtn = document.getElementById('studio-run-btn');

          if (!isAnythingRunning) {
            if (alertBox) alertBox.style.display = 'none';
            if (runBtn && runBtn.disabled) {
              runBtn.disabled = false;
              const meta = (typeof activeStudioStage !== 'undefined' && STAGE_META[activeStudioStage]) ? STAGE_META[activeStudioStage] : {};
              runBtn.innerHTML = meta.runBtn || '▶ Run This Stage Only';
            }
          } else {
            if (alertBox && (isCurStageRunning || (typeof studioStageRunning !== 'undefined' && studioStageRunning === activeStudioStage) || (isProjectRunning && p.stage === activeStudioStage))) {
              alertBox.style.display = 'flex';
            }
          }

          if (typeof activeStudioStage !== 'undefined' && activeStudioStage === 'images') {
            try {
              const sdata = await apiJson('/api/images/live_status');


                const gBanner = document.getElementById('studio-gpu-metric-title');
                if (gBanner && sdata.gpu) {
                  const loadCol = sdata.gpu.util_percent > 60 ? '#f59e0b' : (sdata.gpu.util_percent > 15 ? '#38bdf8' : '#34d399');
                  gBanner.innerHTML = `VRAM: <span style="color:#38bdf8;">${sdata.gpu.vram_gb} GB / ${sdata.gpu.vram_total_gb} GB</span> | Engine Load: <span style="color:${loadCol}; font-weight:700;">${sdata.gpu.util_percent}%</span>`;
                }
                const alertTitle = document.getElementById('studio-alert-title');
                const alertMetric = document.getElementById('studio-alert-metric');
                if (sdata.active) {
                  if (alertBox) alertBox.style.display = 'flex';
                  if (alertTitle) {
                    alertTitle.innerHTML = `ComfyUI DirectML: Rendering Scene #${sdata.scene_id} &mdash; Step ${sdata.step}/${sdata.total_steps} (${sdata.percent}%)`;
                  }
                  if (alertMetric && sdata.gpu) {
                    alertMetric.innerHTML = `GPU: <b>${sdata.gpu.util_percent}%</b> | VRAM: <b>${sdata.gpu.vram_gb} GB</b>`;
                  }
                  const pBox = document.getElementById(`studio-prog-box-${sdata.scene_id}`);
                  const pBar = document.getElementById(`studio-prog-bar-${sdata.scene_id}`);
                  const pPct = document.getElementById(`studio-prog-pct-${sdata.scene_id}`);
                  const pTitle = document.getElementById(`studio-prog-title-${sdata.scene_id}`);
                  if (pBox) pBox.style.display = 'block';
                  if (pBar) pBar.style.width = `${Math.max(5, sdata.percent)}%`;
                  if (pPct) pPct.textContent = `${sdata.percent}%`;
                  if (pTitle) pTitle.textContent = `⚡ Step ${sdata.step}/${sdata.total_steps} (${sdata.percent}%)`;
                }

            } catch (_) {}
          }

          if (typeof studioStageRunning !== 'undefined' && studioStageRunning) {
            const runningSt = p.stages ? p.stages[studioStageRunning] : null;
            const isStRunning = runningSt && (runningSt.status === 'RUNNING');

            if (isProjectRunning || isStRunning) {
              studioStageStarted = true;
            }

            if ((studioStageStarted && !isProjectRunning && !isStRunning) ||
                (runningSt && runningSt.status === 'COMPLETED' && !isProjectRunning)) {
              const finishedStage = studioStageRunning;
              studioStageRunning = null;
              studioStageStarted = false;
              loadStageStudio(finishedStage);
            }
          }
        }

        // Ticker update (only update if changed so selection isn't lost)
        if (p.activity) {
          const tickerEl = document.getElementById('hero-ticker-text');
          if (tickerEl && tickerEl.textContent !== p.activity) {
            tickerEl.textContent = p.activity;
          }
        }

        // Update final video player & preview controls
        updatePreviewMedia((p.outputs && p.outputs.final) || null, d);

        if (p.state === 'completed' || p.state === 'failed') {
          stopTimer();
        }
        return p.state === 'running' || Boolean(studioStageRunning);
      } catch (e) {
        if (e.name !== 'AbortError') console.error("Polling error", e);
        return e.name !== 'AbortError';
      } finally {
        if (pollController === controller) pollController = null;
      }
    }

    async function copyCurrentProjectError(btnEl, customText) {
      const errText = (
        customText ||
        window.lastProjectErrorText ||
        (document.getElementById('proj-error-text') && document.getElementById('proj-error-text').textContent) ||
        (document.getElementById('hero-ticker-text') && document.getElementById('hero-ticker-text').textContent) ||
        (document.getElementById('proj-activity') && document.getElementById('proj-activity').textContent) ||
        ''
      ).trim();

      if (!errText) {
        if (typeof showToast === 'function') showToast('No error message to copy.');
        return;
      }

      try {
        await navigator.clipboard.writeText(errText);
      } catch (_) {
        const ta = document.createElement('textarea');
        ta.value = errText;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }

      if (btnEl) {
        const origHtml = btnEl.getAttribute('data-orig-html') || btnEl.innerHTML;
        btnEl.setAttribute('data-orig-html', origHtml);
        btnEl.innerHTML = '✓ Copied!';
        setTimeout(() => {
          btnEl.innerHTML = origHtml;
        }, 1800);
      }
      if (typeof showToast === 'function') {
        showToast('📋 Error code copied to clipboard!');
      }
    }

    async function updatePreviewMedia(finalRelPath, d) {
      if (!currentProjectId) return;
      if (!d) {
        try {
          d = await apiJson('/api/projects/' + currentProjectId);
        } catch (e) {
          console.error("Failed to load project details for preview", e);
        }
      }

      const p = d ? d.project : null;
      const titleEl = document.getElementById('preview-card-title');
      const badgeEl = document.getElementById('preview-status-badge');
      const noVideoBox = document.getElementById('preview-no-video');
      const noVideoTitle = document.getElementById('preview-no-video-title');
      const noVideoDesc = document.getElementById('preview-no-video-desc');
      const vplayer = document.getElementById('final-video-player');
      const dlBtn = document.getElementById('btn-download');
      const tabBtn = document.getElementById('btn-open-tab');
      const pathEl = document.getElementById('preview-file-path');
      const btnPreviewStop = document.getElementById('btn-preview-stop-render');
      const btnActionStop = document.getElementById('btn-action-stop-render');

      const subTitleEl = document.getElementById('preview-card-subtitle');
      const fileBanner = document.getElementById('preview-file-banner');
      const realPathCode = document.getElementById('preview-real-filepath');
      const fileMetaBadge = document.getElementById('preview-file-meta-badge');
      const finalRel = (p && p.outputs && p.outputs.final) || finalRelPath;
      const fullRelPath = finalRel ? `projects/${currentProjectId}/${finalRel}` : `projects/${currentProjectId}/final/${currentProjectId}.mp4`;

      if (titleEl && p) {
        titleEl.innerHTML = `
          <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <span>${escapeHtml(p.title || p.topic || currentProjectId)}</span>
            <span style="font-size:12px; font-weight:700; color:#38bdf8; background:rgba(56,189,248,0.15); border:1px solid rgba(56,189,248,0.35); padding:2px 8px; border-radius:4px; font-family:monospace;">ID: ${escapeHtml(currentProjectId)}</span>
          </div>
        `;
      }

      if (subTitleEl && p) {
        if (finalRel) {
          const fileStatText = (d && d.final_file && d.final_file.size_mb) ? ` • ${d.final_file.size_mb} MB` : '';
          const mtimeText = (d && d.final_file && d.final_file.mtime) ? ` • Rendered: ${d.final_file.mtime}` : ((p && p.updated_at) ? ` • Rendered: ${p.updated_at.replace('T', ' ')}` : '');
          subTitleEl.innerHTML = `
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-top:4px;">
              <span>📁 Real File: <code style="color:#7dd3fc; background:#020617; padding:2px 8px; border-radius:4px; font-family:'Consolas',monospace; font-size:12px; border:1px solid #1e293b; font-weight:700;">${escapeHtml(fullRelPath)}</code></span>
              <span style="color:#94a3b8; font-size:12px;">${fileStatText}${mtimeText}</span>
            </div>
          `;
        } else {
          subTitleEl.textContent = 'View, stream, and download the finished high-definition 1080p video output.';
        }
      }

      if (realPathCode) realPathCode.textContent = fullRelPath;
      if (fileMetaBadge) {
        if (d && d.final_file && d.final_file.exists) {
          fileMetaBadge.textContent = `${d.final_file.size_mb} MB • ${d.final_file.mtime}`;
        } else if (p && p.updated_at) {
          fileMetaBadge.textContent = `Rendered: ${p.updated_at.replace('T', ' ')}`;
        } else {
          fileMetaBadge.textContent = '1080p Master Video';
        }
      }

      const isRenderRunning = p && (
        p.state === 'running' && (
          p.stage === 'render' ||
          (p.stages && p.stages.render && p.stages.render.status === 'RUNNING') ||
          (p.activity && (p.activity.toLowerCase().includes('render') || p.activity.toLowerCase().includes('ffmpeg') || p.activity.toLowerCase().includes('stringing')))
        )
      );

      if (btnPreviewStop) {
        btnPreviewStop.style.display = isRenderRunning ? 'inline-block' : 'none';
      }
      if (btnActionStop) {
        btnActionStop.style.display = isRenderRunning ? 'inline-flex' : 'none';
      }

      if (finalRel) {
        const vsrc = '/media/' + currentProjectId + '/' + finalRel;
        const renderUpdated = (p && p.stages && p.stages.render && p.stages.render.updated_at) || '';
        const buster = p && (p.updated_at || renderUpdated) ? ('?t=' + encodeURIComponent((p.updated_at || '') + '_' + renderUpdated)) : '';

        if (vplayer) {
          vplayer.style.display = 'block';
          const targetSrc = vsrc + (buster || ('?t=' + Date.now()));
          if (vplayer.getAttribute('data-loaded-src') !== targetSrc) {
            vplayer.setAttribute('data-loaded-src', targetSrc);
            vplayer.src = targetSrc;
            vplayer.load();
          }
        }
        if (noVideoBox) noVideoBox.style.display = 'none';

        if (badgeEl) {
          if (isRenderRunning) {
            badgeEl.innerHTML = '<span style="background:#1e3a8a; border:1px solid #3b82f6; color:#93c5fd; font-weight:700; font-size:12px; padding:3px 10px; border-radius:4px;">🔄 Re-rendering Video...</span>';
          } else {
            badgeEl.innerHTML = '<span style="background:#064e3b; border:1px solid #059669; color:#34d399; font-weight:700; font-size:12px; padding:3px 10px; border-radius:4px;">✓ 1080p MP4 Ready</span>';
          }
        }
        if (dlBtn) {
          dlBtn.style.display = 'inline-block';
          dlBtn.href = vsrc;
          dlBtn.download = `${currentProjectId}.mp4`;
        }
        if (tabBtn) {
          tabBtn.style.display = 'inline-block';
          tabBtn.href = vsrc;
        }
        if (pathEl) {
          pathEl.textContent = `File: projects/${currentProjectId}/${finalRel}`;
        }

        const ytBtn = document.getElementById('btn-yt-upload');
        const ytLink = document.getElementById('btn-yt-link');
        if (ytBtn) {
          ytBtn.style.display = 'inline-flex';
          const spanText = ytBtn.querySelector('span');
          if (p && p.outputs && p.outputs.youtube_url) {
            if (spanText) spanText.textContent = 'Re-upload to YouTube (@tsao36)';
          } else {
            if (spanText) spanText.textContent = 'Upload to YouTube (@tsao36)';
          }
        }
        if (ytLink) {
          if (p && p.outputs && p.outputs.youtube_url) {
            ytLink.style.display = 'inline-flex';
            ytLink.href = p.outputs.youtube_url;
          } else {
            ytLink.style.display = 'none';
          }
        }
      } else {
        if (vplayer) vplayer.style.display = 'none';
        if (noVideoBox) {
          noVideoBox.style.display = 'block';
          const btnPreviewCopyErr = document.getElementById('btn-preview-copy-error');
          const previewErrTxt = (p && (p.error || (p.state === 'failed' && p.activity))) || window.lastProjectErrorText || '';
          if (p && p.state === 'running') {
            if (noVideoTitle) noVideoTitle.textContent = "⏳ Generating & Assembling Video...";
            if (noVideoDesc && noVideoDesc.textContent !== (p.activity || '')) {
              noVideoDesc.textContent = p.activity || "Pipeline is currently running. Your 1080p video will appear here as soon as rendering finishes.";
            }
            if (btnPreviewCopyErr) btnPreviewCopyErr.style.display = 'none';
            if (badgeEl) badgeEl.innerHTML = '<span style="background:#1e3a8a; border:1px solid #3b82f6; color:#93c5fd; font-weight:700; font-size:12px; padding:3px 10px; border-radius:4px;">🔄 Rendering...</span>';
          } else if (previewErrTxt) {
            if (noVideoTitle) noVideoTitle.textContent = "⚠️ Video Render Failed";
            if (noVideoDesc && noVideoDesc.textContent !== previewErrTxt) {
              noVideoDesc.textContent = previewErrTxt;
            }
            if (btnPreviewCopyErr) btnPreviewCopyErr.style.display = 'inline-block';
            if (badgeEl) badgeEl.innerHTML = '<span style="background:#7f1d1d; border:1px solid #ef4444; color:#fca5a5; font-weight:700; font-size:12px; padding:3px 10px; border-radius:4px;">✗ Render Failed</span>';
          } else {
            if (noVideoTitle) noVideoTitle.textContent = "🎬 當前專案尚未渲染成片 (No Video Rendered Yet)";
            const readyProjs = (allProjectsCache || []).filter(item => item.outputs && item.outputs.final);
            let switchHtml = "當前選中的專案尚未完成影片渲染。您可至 Stage Studio 進行調整與渲染。";
            if (readyProjs.length > 0) {
              switchHtml += `<div style="margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.1);"><div style="font-weight: 700; color: #38bdf8; margin-bottom: 8px;">💡 或直接選擇以下已完成的專案進行播放：</div><div style="display: flex; gap: 8px; justify-content: center; flex-wrap: wrap;">${readyProjs.map(rp => `<button type="button" class="btn-sec" onclick="onSwitchProject('${rp.id}')" style="font-size: 11.5px; padding: 4px 10px; border-color: #38bdf8; color: #7dd3fc;">▶ [${rp.id}] ${escapeHtml(rp.title || rp.topic || rp.id)}</button>`).join('')}</div></div>`;
            }
            if (noVideoDesc) noVideoDesc.innerHTML = switchHtml;
            if (btnPreviewCopyErr) btnPreviewCopyErr.style.display = 'none';
            if (badgeEl) badgeEl.innerHTML = '<span style="background:#334155; color:#cbd5e1; font-weight:600; font-size:12px; padding:3px 10px; border-radius:4px;">Render Pending</span>';
          }
        }
        if (fileBanner) fileBanner.style.display = 'none';
        if (dlBtn) dlBtn.style.display = 'none';
        if (tabBtn) tabBtn.style.display = 'none';
        if (pathEl) pathEl.textContent = '';
        const ytBtn = document.getElementById('btn-yt-upload');
        const ytLink = document.getElementById('btn-yt-link');
        if (ytBtn) ytBtn.style.display = 'none';
        if (ytLink) ytLink.style.display = 'none';
      }

      if (d && d.project && d.project.usage) {
        const u = d.project.usage;
        const stageMeta = [
          { key: 'research', title: '1. Research', icon: '🔬' },
          { key: 'script', title: '2. Script', icon: '📜' },
          { key: 'scenes', title: '3. Scenes', icon: '🎬' },
          { key: 'prompts', title: '4. Prompts', icon: '🎨' },
          { key: 'images', title: '5. Images', icon: '🖼️' },
          { key: 'voice', title: '6. Voice', icon: '🎙️' },
          { key: 'animation', title: '7. Animation', icon: '✨' },
          { key: 'presenter', title: '7 (Avatar). Virtual Presenter', icon: '🎭' },
          { key: 'subtitles', title: '8. Subtitles', icon: '📝' },
          { key: 'render', title: '9. Render', icon: '⚡' }
        ];

        const stageDursMap = {};
        let computedTotalSec = 0;
        stageMeta.forEach(sm => {
          const stObj = (p && p.stages) ? p.stages[sm.key] : null;
          let sSec = (stObj && stObj.duration_seconds) ? Number(stObj.duration_seconds) : ((p && p.stage_durations && p.stage_durations[sm.key]) ? Number(p.stage_durations[sm.key]) : 0);
          if (stObj && stObj.status === 'COMPLETED' && sSec <= 0) sSec = 0.1;
          stageDursMap[sm.key] = sSec;
          if (sm.key !== 'presenter') {
            computedTotalSec += sSec;
          }
        });

        const totalSecVal = (p && p.total_duration_seconds && p.total_duration_seconds > 0) ? p.total_duration_seconds : computedTotalSec;
        const durFormatted = totalSecVal > 0 ? formatDuration(totalSecVal) : 'N/A';

        let stageBreakdownHtml = '';
        if (computedTotalSec > 0) {
          stageBreakdownHtml = '<div style="margin-top:12px; border-top:1px solid var(--card-border); padding-top:10px; font-size:12px;"><b style="color:#cbd5e1; display:block; margin-bottom:6px;">⏱️ Stage Time-Lapse Breakdown:</b><div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(135px, 1fr)); gap:6px;">';
          stageMeta.forEach(sm => {
            const sSec = stageDursMap[sm.key] || 0;
            if (sm.key === 'presenter' && sSec <= 0) return;
            const pctShare = totalSecVal > 0 && sSec > 0 ? Math.round((sSec / totalSecVal) * 100) : 0;
            stageBreakdownHtml += `<div style="background:#0e1726; border:1px solid #1a2538; padding:6px 8px; border-radius:4px; display:flex; justify-content:space-between; align-items:center;"><span style="color:var(--text-muted); font-size: 11px;">${sm.icon} ${sm.key.toUpperCase()}</span> <b style="color:#93c5fd; font-size:12px; font-family:monospace;">${sSec > 0 ? formatDuration(sSec) : '—'}${pctShare > 0 ? ` <span style="color:#64748b; font-size:10px;">(${pctShare}%)</span>` : ''}</b></div>`;
          });
          stageBreakdownHtml += '</div></div>';
        }

        const stageCosts = u.stage_costs || {};
        const stageDetails = u.stage_details || {};
        const totalCost = u.estimated_cost_usd !== undefined ? u.estimated_cost_usd : 0;
        const isCloudAccelerated = (p && p.settings && p.settings.cloud && p.settings.cloud.enabled) || totalCost > 0;

        let costRows = '';
        stageMeta.forEach(sm => {
          const c = stageCosts[sm.key] !== undefined ? stageCosts[sm.key] : 0.0;
          const det = stageDetails[sm.key] || {};
          const rawProv = det.provider || '-';
          const prov = [...new Set(rawProv.split(',').map(s => s.trim()))].filter(Boolean).join(', ') || '-';
          const units = det.units || '';
          const sSec = stageDursMap[sm.key] || 0;
          const timeStr = sSec > 0 ? formatDuration(sSec) : '—';
          const costStr = c > 0 ? (c < 0.0001 ? '< $0.0001' : (c < 0.01 ? '$' + c.toFixed(4) : '$' + c.toFixed(3))) : '$0.0000';
          const isFree = c === 0.0;
          const costBadgeStyle = isFree
            ? 'background: rgba(100, 116, 139, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.2);'
            : 'background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-weight: 700;';

          costRows += `
            <tr style="border-bottom: 1px solid #142033;">
              <td style="padding: 6px 8px; font-weight: 600; color: #cbd5e1; white-space: nowrap;">
                ${sm.icon} ${sm.title}
              </td>
              <td style="padding: 6px 8px; color: #94a3b8; font-size: 11px;">
                <div style="font-weight: 600; color: #cbd5e1;">${prov}</div>
                ${units ? `<div style="color: #64748b; font-size: 10px;">${units}</div>` : ''}
              </td>
              <td style="padding: 6px 8px; text-align: right; white-space: nowrap; font-family: monospace; color: #38bdf8; font-weight: 600;">
                ⏱️ ${timeStr}
              </td>
              <td style="padding: 6px 8px; text-align: right; white-space: nowrap;">
                <span style="display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-family: monospace; ${costBadgeStyle}">
                  ${costStr}
                </span>
              </td>
            </tr>
          `;
        });

        const totalCostStr = totalCost > 0
          ? (totalCost < 0.01 ? '$' + totalCost.toFixed(4) : '$' + totalCost.toFixed(3))
          : '$0.0000';

        const costBreakdownHtml = `
          <div style="margin-top: 14px; background: linear-gradient(135deg, #091322 0%, #060b14 100%); border: 1px solid #1e3a5f; border-radius: 8px; padding: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.4);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px solid #172a45; padding-bottom: 8px;">
              <div style="font-size: 12px; text-transform: uppercase; color: #93c5fd; font-weight: 700; letter-spacing: 0.5px; display: flex; align-items: center; gap: 5px;">
                <span>⏱️💰 Stage Time & Cloud Cost Breakdown</span>
                ${isCloudAccelerated ? '<span style="font-size: 10px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); padding: 1px 5px; border-radius: 4px;">Cloud Accelerated</span>' : '<span style="font-size: 10px; background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.4); padding: 1px 5px; border-radius: 4px;">100% Local GPU</span>'}
              </div>
            </div>

            <div style="overflow-x: auto;">
              <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                <thead>
                  <tr style="color: #64748b; font-size: 10px; text-transform: uppercase; border-bottom: 1px solid #172a45;">
                    <th style="padding: 4px 8px; text-align: left;">Stage</th>
                    <th style="padding: 4px 8px; text-align: left;">Engine / Volume</th>
                    <th style="padding: 4px 8px; text-align: right;">Creation Time</th>
                    <th style="padding: 4px 8px; text-align: right;">Cost (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  ${costRows}
                </tbody>
                <tfoot>
                  <tr style="border-top: 2px solid #2563eb; background: rgba(15, 23, 42, 0.6);">
                    <td colspan="2" style="padding: 8px 8px; font-weight: 800; color: #f8fafc; font-size: 13px;">
                      ∑ Total Production Time & Cost:
                    </td>
                    <td style="padding: 8px 8px; text-align: right;">
                      <span style="font-size: 13px; font-weight: 800; color: #38bdf8; font-family: monospace; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4); padding: 3px 8px; border-radius: 5px;">
                        ⏱️ ${durFormatted}
                      </span>
                    </td>
                    <td style="padding: 8px 8px; text-align: right;">
                      <span style="font-size: 14px; font-weight: 800; color: #34d399; font-family: monospace; background: rgba(16, 185, 129, 0.18); border: 1px solid #059669; padding: 3px 8px; border-radius: 5px;">
                        ${totalCostStr}
                      </span>
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        `;

        const usageEl = document.getElementById('project-usage-info');
        if (usageEl) {
            const rawMusic = (p.settings && p.settings.music && p.settings.music.track) || (d.outputs && d.outputs.music_track) || 'None';
            const musicVol = (p.settings && p.settings.music && p.settings.music.volume_db !== undefined) ? p.settings.music.volume_db + ' dB' : '-24 dB';
            const musicDisplay = (rawMusic && rawMusic.toLowerCase() !== 'none') ? (rawMusic.replace(/\.[^/.]+$/, '').replace(/_/g, ' ') + ' (' + musicVol + ' ducked)') : 'None (Narration Voice Only)';

            usageEl.innerHTML = `
            <div style="background:rgba(2,6,23,0.7); border:1px solid #1e293b; border-radius:6px; padding:8px 10px; margin-bottom:12px;">
              <div style="font-size:11px; text-transform:uppercase; color:#93c5fd; font-weight:700;">🎬 Real Output Video File</div>
              <div style="font-size:12px; font-family:'Consolas',monospace; color:#38bdf8; word-break:break-all; font-weight:700; margin-top:2px;">projects/${currentProjectId}/${(p.outputs && p.outputs.final) || 'final/' + currentProjectId + '.mp4'}</div>
              <div style="font-size:11px; color:#94a3b8; margin-top:3px;">ID: <b style="color:#fff;">${currentProjectId}</b> • 1080p 30fps</div>
            </div>
            <div style="background:linear-gradient(135deg, #10213d 0%, #0c1524 100%); border:1px solid #2563eb; border-radius:6px; padding:10px 14px; margin-bottom:14px;">
              <div style="font-size: 12px; text-transform:uppercase; color:#93c5fd; font-weight:700; letter-spacing:0.5px;">⏱️ Production Time Lapse</div>
              <div style="font-size:22px; font-weight:800; color:#38bdf8; margin-top:2px;">${durFormatted}</div>
              <div style="font-size: 12px; color:#94a3b8; margin-top:2px;">Total recorded creation time</div>
            </div>
            <div style="margin-bottom:6px;">Total Scenes: <b style="color:#fff;">${d.scene_count ?? (d.scenes ? d.scenes.length : 0)}</b></div>
            <div style="margin-bottom:6px;">Narration Language: <b style="color:#93c5fd;">${(p.settings && p.settings.video && p.settings.video.language) || 'English'}</b></div>
            <div style="margin-bottom:6px;">Background Music: <b style="color:#60a5fa;">🎵 ${musicDisplay}</b></div>
            <div style="margin-bottom:6px;">LLM Requests: <b style="color:#fff;">${u.llm_requests}</b></div>
            ${(u.presenter_clips_cloud > 0 || (stageCosts.presenter && stageCosts.presenter > 0) || (stageDetails.presenter && stageDetails.presenter.cost > 0)) ? `<div style="margin-bottom:6px;">Virtual Presenter: <b style="color:#c4b5fd;">🎭 ${stageDetails.presenter ? stageDetails.presenter.units : 'Avatar Lipsync'}</b></div>` : ''}
            <div style="margin-bottom:6px;">Total Cloud Cost: <b style="color:#34d399; font-size: 14px;">${totalCostStr}</b></div>
            ${costBreakdownHtml}
            ${stageBreakdownHtml}
          `;
        }
      }
    }

    async function openVideoFolder() {
      if (!currentProjectId) return;
      try {
        const d = await apiJson(`/api/projects/${currentProjectId}/open_folder`, { method: 'POST' });

        if (d.status === 'ok') {
          showToast("📂 Opened folder in Windows File Explorer: " + (d.folder_path || ''));
        } else {
          showToast("Folder: " + (d.folder_path || `projects/${currentProjectId}/final/`));
        }
      } catch (err) {
        console.error("Failed to open video folder:", err);
        showToast("Error opening folder: " + err.message);
      }
    }

    function copyRealVideoPath() {
      const codeEl = document.getElementById('preview-real-filepath');
      const pathText = (codeEl && codeEl.textContent.trim()) || `projects/${currentProjectId}/final/${currentProjectId}.mp4`;
      navigator.clipboard.writeText(pathText).then(() => {
        showToast("Copied video file path: " + pathText);
      }).catch(() => {
        prompt("Video file path:", pathText);
      });
    }

    function forceReloadVideoPlayer() {
      const vplayer = document.getElementById('final-video-player');
      if (!vplayer || !currentProjectId) return;
      const targetSrc = '/media/' + currentProjectId + '/final/' + currentProjectId + '.mp4?t=' + Date.now();
      vplayer.setAttribute('data-loaded-src', targetSrc);
      vplayer.src = targetSrc;
      vplayer.load();
      vplayer.play().catch(() => {});
    }

    async function cancelCurrentProject() {
      if (!currentProjectId) return;
      await apiRequest('/api/projects/' + currentProjectId + '/cancel', { method: 'POST' });
      pollProject();
    }

    async function stopRenderingVideo() {
      if (!currentProjectId) return alert("No active project selected.");
      if (!confirm("Are you sure you want to stop video rendering immediately?\n\nAny active FFmpeg video encoding processes will be terminated instantly.")) {
        return;
      }
      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/stop_render`, { method: 'POST' });
        alert("Video rendering stopped successfully.");
        pollProject();
      } catch (e) {
        alert("Error stopping video rendering: " + e.message);
      }
    }

    async function resumeCurrentProject() {
      if (!currentProjectId) return;
      await apiRequest('/api/projects/' + currentProjectId + '/start', { method: 'POST' });
      startPolling();
    }

    async function loadScenesForEditor() {
      if (!currentProjectId) return;
      const d = await apiJson('/api/projects/' + currentProjectId);
      if (d) currentProject = d.project || d;
      currentScenes = d.scenes || [];
      const tbody = document.getElementById('scenes-tbody');
      if (!tbody) return;
      tbody.innerHTML = '';

      const isDrama = isDramaStudioProject(currentProject || studioProject);
      currentScenes.forEach((s, idx) => {
        const imgUrl = s.image && s.image.path ? `/media/${currentProjectId}/${s.image.path}` : '';
        tbody.innerHTML += `
          <tr>
            <td>${s.scene_id}</td>
            <td>
              ${imgUrl ? `<img src="${imgUrl}?t=${Date.now()}" class="thumb" onclick="window.open('${imgUrl}')">` : '<div style="font-size: 12px;color:gray;">Pending</div>'}
              <button class="btn-sec" style="padding:4px 8px;font-size: 12px;margin-top:4px;" onclick="regenImage(${s.scene_id})">Regen</button>
            </td>
            <td>
              <div style="font-weight:600; font-size:13px; margin-bottom:4px;">
                <textarea rows="2" style="width:100%" onchange="currentScenes[${idx}].narration=this.value">${s.narration}</textarea>
              </div>
              <div style="font-size: 12px; color:var(--text-muted)">
                Prompt: <input type="text" style="width:100%;font-size: 12px;padding:4px;" value="${s.prompt || ''}" onchange="currentScenes[${idx}].prompt=this.value">
              </div>
              ${isDrama ? `
                <div style="font-size: 11px; margin-top: 5px; display: flex; gap: 6px; align-items: center; color: #fbbf24;">
                  <span>👤 角色: <b>${escapeHtml(s.character || s.speaker || '主演')}</b></span>
                  ${s.action_prompt ? ` | <span>🎭 動作: ${escapeHtml(s.action_prompt)}</span>` : ''}
                </div>
              ` : `
                <div style="font-size: 11px; margin-top: 5px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
                  <span style="color: #fca5a5; font-weight: 600;">🎬 Target:</span>
                  <input type="text" placeholder="YouTube keyword (e.g. Yann LeCun interview)" style="flex: 1; min-width: 140px; font-size: 11px; padding: 2px 6px; background: #070d18; border: 1px solid #1e293b; color: #f1f5f9; border-radius: 4px;" value="${s.search_keyword || ''}" onchange="currentScenes[${idx}].search_keyword=this.value">
                  <select style="font-size: 11px; padding: 2px 4px; background: #070d18; border: 1px solid #1e293b; color: #cbd5e1; border-radius: 4px;" onchange="currentScenes[${idx}].media_source=this.value">
                    <option value="ai" ${(!s.media_source || s.media_source==='ai')?'selected':''}>AI Art</option>
                    <option value="youtube_snippet" ${s.media_source==='youtube_snippet'?'selected':''}>🎬 3s Clip</option>
                    <option value="youtube_screenshot" ${s.media_source==='youtube_screenshot'?'selected':''}>📸 Screenshot</option>
                    <option value="wikimedia" ${s.media_source==='wikimedia' || s.media_source==='stock'?'selected':''}>🏛️ Wikimedia</option>
                  </select>
                  <button class="btn-sec" style="padding: 2px 7px; font-size: 11px; background: rgba(220,38,38,0.25); border-color: #ef4444; color: #fca5a5; font-weight: 600;" onclick="openYouTubeFootageModal(${s.scene_id}, currentScenes[${idx}].search_keyword || currentScenes[${idx}].prompt || '')">🎬 Fetch</button>
                  ${s.is_presenter ? `
                    <button type="button" class="btn-sec" style="padding: 2px 8px; font-size: 11px; background: rgba(139, 92, 246, 0.25); border-color: #8b5cf6; color: #c4b5fd; font-weight: 700;" onclick="triggerSceneAvatarUpload(${s.scene_id})" title="方案2：直接上傳此分鏡的自錄出鏡影片">📤 上傳自錄影片</button>
                    <input type="file" id="scene-avatar-file-${s.scene_id}" accept="video/mp4,video/quicktime,video/webm" style="display:none;" onchange="uploadCustomSceneAvatarClip(${s.scene_id}, this.files[0])">
                  ` : ''}
                </div>
              `}
            </td>
            <td>
              ${s.audio_duration ? s.audio_duration.toFixed(1) + 's' : s.estimated_duration + 's'}
              <button class="btn-sec" style="padding:4px 8px;font-size: 12px;margin-top:4px;" onclick="regenVoice(${s.scene_id})">TTS</button>
            </td>
            <td>
              ${isDrama ? `
                <div style="font-size: 11px; color: #34d399; font-weight: 700;">👄 Hedra Lip-Sync</div>
              ` : `
                <select style="font-size:12px;padding:4px;" onchange="currentScenes[${idx}].camera_motion=this.value">
                  <option value="slow_zoom_in" ${s.camera_motion==='slow_zoom_in'?'selected':''}>Zoom In</option>
                  <option value="slow_zoom_out" ${s.camera_motion==='slow_zoom_out'?'selected':''}>Zoom Out</option>
                  <option value="pan_left" ${s.camera_motion==='pan_left'?'selected':''}>Pan Left</option>
                  <option value="pan_right" ${s.camera_motion==='pan_right'?'selected':''}>Pan Right</option>
                  <option value="static" ${s.camera_motion==='static'?'selected':''}>Static</option>
                </select>
              `}
            </td>
            <td>
              ${isDrama ? `
                <div style="font-size: 11px; color: #38bdf8; font-weight: 700;">✓ 100% 角色影片</div>
              ` : `
                <input type="checkbox" ${s.ai_video?'checked':''} onchange="currentScenes[${idx}].ai_video=this.checked;currentScenes[${idx}].ai_video_user=this.checked;">
              `}
            </td>
            <td>
              <button class="btn-sec btn-danger" style="padding:4px 8px;font-size: 12px;" onclick="deleteScene(${s.scene_id})">Del</button>
            </td>
          </tr>
        `;
      });
    }

    async function regenImage(sid) {
      await apiRequest(`/api/projects/${currentProjectId}/scenes/${sid}/regenerate_image`, { method: 'POST' });
      loadScenesForEditor();
    }

    async function regenVoice(sid) {
      await apiRequest(`/api/projects/${currentProjectId}/scenes/${sid}/regenerate_voice`, { method: 'POST' });
      loadScenesForEditor();
    }

    async function saveScenesToServer(showConfirmation = true) {
      await apiRequest(`/api/projects/${currentProjectId}/scenes`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentScenes)
      });
      if (showConfirmation) alert("Scenes saved!");
    }

    async function deleteScene(sid) {
      const previousScenes = currentScenes;
      currentScenes = currentScenes.filter(s => s.scene_id !== sid);
      try {
        await saveScenesToServer(false);
        await loadScenesForEditor();
      } catch (error) {
        currentScenes = previousScenes;
        alert(`Could not delete scene: ${error.message}`);
      }
    }

    async function renderDraftNow() {
      if (!currentProjectId) return;
      await apiRequest(`/api/projects/${currentProjectId}/render_draft`, { method: 'POST' });
      alert("Draft preview render queued!");
      startPolling();
    }

    async function renderFinalNow() {
      if (!currentProjectId) return;
      await apiRequest(`/api/projects/${currentProjectId}/render_final`, { method: 'POST' });
      alert("Final 1080p render started!");
      startPolling();
    }

    function openEditor() {
      switchTab('studio');
    }

    async function refreshLogs() {
      try {
        const d = await apiJson('/api/logs');

        document.getElementById('log-viewer').textContent = d.logs.join('\n');
      } catch (e) {
        console.error("Failed to load logs", e);
      }
    }

    async function syncVoaiVoicesNow() {
      const btn = event ? event.currentTarget : null;
      if (btn) { btn.disabled = true; btn.textContent = '⏳ 同步中 (Syncing VoAI Actors)...'; }
      try {
        const data = await apiJson('/api/voices/sync_voai', { method: 'POST' });


        showToast(`✅ 成功同步 ${data.count} 位 VoAI 聲優庫！`);
        loadVoices();
        await loadVoiceProfiles();
      } catch (err) {
        alert(`同步 VoAI 聲優失敗: ${err.message}`);
      } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '⚡ 同步 VoAI 全部 75 位聲優庫 (Sync All VoAI Actors)'; }
      }
    }

    async function loadVoiceProfiles() {
      const voices = await apiJson('/api/voices');

      const listEl = document.getElementById('voice-profiles-list');
      listEl.innerHTML = '';
      if (!voices.length) {
        listEl.innerHTML = '<div style="color:var(--text-muted)">No custom voices created yet.</div>';
        return;
      }
      const buster = Date.now();
      voices.forEach(v => {
        const hasSample = !!v.has_test_sample;
        const sampleUrl = `/media/voices/${v.name}/test_sample.wav?t=${buster}`;
        const isEleven = v.provider === 'elevenlabs';
        const isVoai = v.provider === 'voai';
        const isEdge = v.provider === 'edge';

        listEl.innerHTML += `
          <div style="background:#080d16; border:1px solid var(--card-border); padding:14px; border-radius:var(--radius); margin-bottom:12px; display:flex; flex-direction:column; gap:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
              <div>
                <div style="font-weight:600; font-size:14px; display:flex; align-items:center; gap:8px;">
                  <span>${v.display_name}</span>
                  <span style="font-size: 12px; color:var(--text-muted);">(${v.name})</span>
                  ${isEleven ? '<span style="background:rgba(37,99,235,0.25); border:1px solid #2563eb; color:#60a5fa; font-size: 12px; font-weight:700; padding:1px 6px; border-radius:4px;">⚡ ElevenLabs</span>' : ''}
                  ${isVoai ? '<span style="background:rgba(2,132,199,0.25); border:1px solid #0284c7; color:#38bdf8; font-size: 12px; font-weight:700; padding:1px 6px; border-radius:4px;">🇹🇼 VoAI 絕好聲創</span>' : ''}
                  ${isEdge ? `<span style="background:rgba(16,185,129,0.22); border:1px solid #10b981; color:#6ee7b7; font-size: 12px; font-weight:700; padding:1px 6px; border-radius:4px;">🇹🇼 Edge-TTS ${v.gender === 'male' ? '臺灣男聲' : '臺灣女聲'}</span>` : ''}
                  ${hasSample ? '<span style="background:rgba(5,150,105,0.25); border:1px solid #059669; color:#34d399; font-size: 12px; font-weight:700; padding:1px 6px; border-radius:4px;">✓ Sample Ready</span>' : '<span style="font-size: 12px; color:#38bdf8; background:rgba(56,189,248,0.15); border:1px solid #0284c7; padding:1px 6px; border-radius:4px;">⚡ 點擊即播 (Auto-Sample)</span>'}
                </div>
                <div style="font-size:12px; color:var(--text-muted); margin-top:3px;">
                  ${isEleven ? `
                    Provider: <b style="color:#60a5fa;">ElevenLabs Cloud</b> | Model: <b style="color:#93c5fd;">${v.model_id || 'eleven_multilingual_v2'}</b> | Voice ID: <b>${v.voice_id || v.voice || 'Rachel'}</b>
                  ` : (isVoai ? `
                    Provider: <b style="color:#38bdf8;">VoAI 絕好聲創 Cloud</b> | Version: <b style="color:#7dd3fc;">${v.version || v.model_id || 'Sota+'}</b> | Speaker: <b>${v.speaker || v.voice_id || v.voice || '佑希'}</b> | Style: <b>${v.voai_style || '預設'}</b>
                  ` : (isEdge ? `
                    Provider: <b style="color:#34d399;">Edge-TTS (Free Cloud)</b> | Neural Voice: <b style="color:#a7f3d0;">${v.voice || 'zh-TW-HsiaoChenNeural'}</b> | Rate: <b>${v.speech_rate || 1.0}x</b> | Pitch: <b>${v.pitch || '+0Hz'}</b>${v.persona ? ` | <span style="color:#cbd5e1;">${v.persona}</span>` : ''}
                  ` : `
                    Provider: <b>${v.provider.toUpperCase()}</b> | Language: <b>${v.language || 'Auto'}</b> | Cloned Ref: <b>${v.reference_wav ? 'Uploaded ✓' : 'None'}</b>
                  `))}
                </div>
              </div>

              <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                <audio controls preload="none" src="${sampleUrl}" style="height:32px; max-width:230px;" id="audio-player-${v.name}"></audio>
                <button class="btn-sec" style="padding:6px 12px; font-size:12px; background:#1e293b;" onclick="playExistingVoiceSample('${v.name}')" id="btn-play-${v.name}" title="Play sample (auto-generates if not yet cached)">▶️ 試聽 (Play)</button>
                <button class="btn-sec" style="padding:6px 12px; font-size:12px; color:#93c5fd;" onclick="testVoiceProfile('${v.name}', true)" id="btn-test-${v.name}" title="Re-generate test sample with new text">🔄 自訂測試</button>
                <button type="button" class="btn-sec" style="padding:6px 12px; font-size:12px; color:#38bdf8; background:rgba(56,189,248,0.12); border-color:#0284c7; font-weight:600;" onclick="toggleRenameVoiceBox('${v.name}')" title="Rename Voice Profile ID & Display Name">✏️ 重新命名 (Rename)</button>
                ${v.name !== 'default_local' ? `<button class="btn-sec btn-danger" style="padding:6px 12px; font-size:12px;" onclick="deleteVoiceProfile('${v.name}')">Delete</button>` : ''}
              </div>
            </div>

            <!-- Inline Rename Box -->
            <div id="v-rename-box-${v.name}" style="display:none; background:#040914; border:1px solid #0284c7; border-radius:6px; padding:12px 14px; margin-top:6px;">
              <div style="font-size:12px; font-weight:700; color:#38bdf8; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
                <span>✏️ 重新命名聲音音色 (Rename ID & Display Name)</span>
              </div>
              <div style="display:flex; gap:12px; flex-wrap:wrap; align-items:flex-end;">
                <div style="flex:1; min-width:180px;">
                  <label style="font-size:11px; color:#94a3b8; display:block; margin-bottom:4px; font-weight:600;">聲音代號 ID (Unique Identifier / Folder Name):</label>
                  <input type="text" id="v-rename-id-${v.name}" value="${escapeHtml(v.name)}" ${v.name === 'default_local' ? 'disabled title="預設系統音色不可更改 ID"' : ''} style="width:100%; font-size:12px; padding:6px 8px; background:#0b1120; border:1px solid #334155; border-radius:4px; color:#e2e8f0; font-family:monospace;" placeholder="例如: my_voice_id">
                  <div style="font-size:10px; color:#64748b; margin-top:3px;">僅限英文字母、數字、底線</div>
                </div>
                <div style="flex:1.2; min-width:220px;">
                  <label style="font-size:11px; color:#94a3b8; display:block; margin-bottom:4px; font-weight:600;">顯示名稱 (Display Name):</label>
                  <input type="text" id="v-rename-disp-${v.name}" value="${escapeHtml(v.display_name || v.name)}" style="width:100%; font-size:12px; padding:6px 8px; background:#0b1120; border:1px solid #334155; border-radius:4px; color:#e2e8f0;" placeholder="例如: 曹操 AI 專屬磁性聲音">
                  <div style="font-size:10px; color:#64748b; margin-top:3px;">介面與各下拉選單顯示的名字</div>
                </div>
                <div style="display:flex; gap:8px;">
                  <button type="button" class="btn-primary" onclick="submitRenameVoice('${v.name}')" style="padding:7px 16px; font-size:12px; font-weight:700; background:linear-gradient(135deg, #0284c7, #0369a1); border:none;" id="btn-save-rename-${v.name}">
                    💾 儲存更名 (Save)
                  </button>
                  <button type="button" class="btn-sec" onclick="toggleRenameVoiceBox('${v.name}')" style="padding:7px 12px; font-size:12px;">
                    取消
                  </button>
                </div>
              </div>
              <div id="v-rename-status-${v.name}" style="font-size:11px; margin-top:6px; min-height:14px;"></div>
            </div>

            ${['bluemagpie', 'cosyvoice', 'http_clone'].includes(v.provider) ? `
            <details style="background:#060b14; border:1px solid #1e293b; border-radius:6px; padding:8px 12px;" ${v.provider === 'cosyvoice' && !v.reference_text ? 'open' : ''}>
              <summary style="cursor:pointer; font-size:12px; font-weight:700; color:#93c5fd;">🎤 Customize this voice — upload your own clip / transcript / engine</summary>
              <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap:12px; margin-top:10px;">
                <div>
                  <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">Current clip ${v.reference_seconds ? `(${v.reference_seconds}s)` : ''}</div>
                  ${v.reference_wav ? `<audio controls src="/media/voices/${v.name}/reference.wav?t=${buster}" style="width:100%; height:32px;"></audio>` : '<div style="font-size:12px; color:#f59e0b;">No clip uploaded yet</div>'}
                  <div style="font-size:11px; color:var(--text-muted); margin:8px 0 4px;">Replace with a new clip of your voice (3–15 s, quiet room, no music):</div>
                  <input type="file" id="v-replace-file-${v.name}" accept="audio/*,video/*" style="width:100%; font-size:12px;" onchange="previewVoiceUpload(this, 'v-replace-prev-${v.name}', 'v-replace-info-${v.name}')">
                  <audio id="v-replace-prev-${v.name}" controls style="display:none; width:100%; height:30px; margin-top:4px;"></audio>
                  <div id="v-replace-info-${v.name}" style="font-size:11px; color:var(--text-muted); margin-top:2px;"></div>
                  <button class="btn-sec" style="margin-top:6px; padding:5px 12px; font-size:12px; background:#1e3a8a; border-color:#3b82f6; color:#fff;" onclick="replaceVoiceClip('${v.name}')">⬆️ Upload new clip</button>
                </div>
                <div>
                  <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">What is said in the clip (enables CosyVoice 2 zero-shot mode):</div>
                  <textarea id="v-reftext-${v.name}" rows="3" style="width:100%; font-size:12px;" placeholder="（空白 = 跨語言模式）">${escapeHtml(v.reference_text || '')}</textarea>
                  <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:6px; align-items:center;">
                    <button class="btn-sec" style="padding:5px 10px; font-size:12px;" onclick="saveVoiceTranscript('${v.name}')">💾 Save transcript</button>
                    <button class="btn-sec" style="padding:5px 10px; font-size:12px;" onclick="autoTranscribeVoice('${v.name}')" id="btn-transcribe-${v.name}">📝 Auto-transcribe</button>
                    <label style="font-size:11px; color:var(--text-muted); margin-left:auto;">Engine:
                      <select onchange="switchVoiceEngine('${v.name}', this.value)" style="font-size:12px; padding:3px 6px;">
                        <option value="bluemagpie" ${v.provider === 'bluemagpie' ? 'selected' : ''}>BlueMagpie</option>
                        <option value="cosyvoice" ${v.provider === 'cosyvoice' ? 'selected' : ''}>CosyVoice 2</option>
                        ${v.provider === 'http_clone' ? '<option value="http_clone" selected>HTTP clone</option>' : ''}
                      </select>
                    </label>
                  </div>
                  <div id="v-cust-status-${v.name}" style="font-size:11px; margin-top:4px; color:var(--text-muted);"></div>
                </div>
                ${v.provider === 'bluemagpie' ? `
                <div style="grid-column: 1 / -1; background:#040914; border:1px solid #1e3a8a; border-radius:6px; padding:10px 14px; margin-top:6px;">
                  <div style="font-size:12px; font-weight:700; color:#38bdf8; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
                    <span>🪶 BlueMagpie TTS 聲音參數與長文切句微調 (CFG & Steps)</span>
                  </div>
                  <div style="display:flex; gap:16px; flex-wrap:wrap; align-items:flex-end;">
                    <div>
                      <label style="font-size:11px; color:#94a3b8; display:block; margin-bottom:4px; font-weight:600;">CFG 引導強度 (建議 2.0，範圍 1.8–2.4):</label>
                      <input type="number" step="0.1" min="1.0" max="5.0" id="v-cfg-${v.name}" value="${v.cfg_value || 2.0}" style="width:100px; font-size:12px; padding:5px 8px; background:#0b1120; border:1px solid #334155; border-radius:4px; color:#fff;">
                      <div style="font-size:10px; color:#64748b; margin-top:2px;">預設 2.0；過高 (>2.8) 易引發破音胡言亂語</div>
                    </div>
                    <div>
                      <label style="font-size:11px; color:#94a3b8; display:block; margin-bottom:4px; font-weight:600;">推論步數 Steps (預設 10，範圍 8–14):</label>
                      <input type="number" step="1" min="4" max="32" id="v-steps-${v.name}" value="${v.inference_timesteps || 10}" style="width:100px; font-size:12px; padding:5px 8px; background:#0b1120; border:1px solid #334155; border-radius:4px; color:#fff;">
                      <div style="font-size:10px; color:#64748b; margin-top:2px;">預設 10 步；適當步數確保聲音平滑自然</div>
                    </div>
                    <div>
                      <label style="font-size:11px; color:#94a3b8; display:block; margin-bottom:4px; font-weight:600;">長文切句逐句合成 + 跨句提示銜接:</label>
                      <select id="v-chunk-${v.name}" style="font-size:12px; padding:5px 8px; background:#0b1120; border:1px solid #334155; border-radius:4px; color:#fff;">
                        <option value="true" ${v.chunk_sentences !== false ? 'selected' : ''}>開啟 (自動切句、前後文接合與淡入淡出)</option>
                        <option value="false" ${v.chunk_sentences === false ? 'selected' : ''}>關閉 (整段直接合成)</option>
                      </select>
                      <div style="font-size:10px; color:#64748b; margin-top:2px;">建議長文開啟以保持流暢不斷句</div>
                    </div>
                    <div>
                      <button type="button" class="btn-sec" style="padding:6px 14px; font-size:12px; background:#1e3a8a; border-color:#3b82f6; color:#fff; font-weight:600;" onclick="saveBlueMagpieSettings('${v.name}')">💾 儲存參數</button>
                    </div>
                  </div>
                  <div id="v-bm-status-${v.name}" style="font-size:11px; margin-top:6px; min-height:14px;"></div>
                </div>
                ` : ''}
              </div>
            </details>
            ` : ''}

            <!-- Progress Bar Box for Voice Sample Synthesis -->
            <div id="v-prog-box-${v.name}" style="display:none; background:#040914; border:1px solid #2563eb; border-radius:6px; padding:10px 12px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">
                <span id="v-prog-title-${v.name}" style="color:#60a5fa; font-weight:600; font-size: 12px;">🚀 Starting TTS...</span>
                <span id="v-prog-pct-${v.name}" style="color:#93c5fd; font-weight:700; font-size: 12px;">0%</span>
              </div>
              <div style="width:100%; height:7px; background:#1e293b; border-radius:999px; overflow:hidden; margin-bottom:5px;">
                <div id="v-prog-bar-${v.name}" style="width:5%; height:100%; background:linear-gradient(90deg, #2563eb, #38bdf8); transition: opacity 0.2s ease;"></div>
              </div>
              <div style="font-size: 12px; color:#94a3b8; display:flex; justify-content:space-between;">
                <span>Engine: <b style="color:#cbd5e1;">${isEleven ? 'ElevenLabs API' : (isVoai ? 'VoAI 絕好聲創 API' : v.provider.toUpperCase())}</b></span>
                <span id="v-prog-status-${v.name}" style="color:#38bdf8;">Connecting to TTS engine...</span>
              </div>
            </div>
          </div>
        `;
      });
    }

    function toggleRenameVoiceBox(vName) {
      const box = document.getElementById(`v-rename-box-${vName}`);
      if (!box) return;
      box.style.display = (box.style.display === 'none' || !box.style.display) ? 'block' : 'none';
    }

    async function submitRenameVoice(oldName) {
      const newIdInput = document.getElementById(`v-rename-id-${oldName}`);
      const newDispInput = document.getElementById(`v-rename-disp-${oldName}`);
      const statusEl = document.getElementById(`v-rename-status-${oldName}`);
      const btn = document.getElementById(`btn-save-rename-${oldName}`);

      const newId = newIdInput ? newIdInput.value.trim() : oldName;
      const newDisp = newDispInput ? newDispInput.value.trim() : '';

      if (!newId) {
        alert("聲音識別碼 (ID) 不能為空！");
        return;
      }

      if (btn) btn.disabled = true;
      if (statusEl) {
        statusEl.style.color = '#38bdf8';
        statusEl.textContent = '⏳ 正在重新命名並更新相關綁定...';
      }

      try {
        const res = await apiRequest(`/api/voices/${encodeURIComponent(oldName)}/rename`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            new_name: newId,
            new_display_name: newDisp
          })
        });
        const data = await res.json().catch(() => ({}));


        showToast(`✓ 聲音音色已成功更名為: ${newDisp || newId} (${newId})`);
        loadVoices();
        await loadVoiceProfiles();
        if (typeof loadAvatars === 'function') loadAvatars();
      } catch (err) {
        if (statusEl) {
          statusEl.style.color = '#f87171';
          statusEl.textContent = `❌ ${err.message}`;
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    function previewVoiceUpload(input, audioId, infoId) {
      const audio = document.getElementById(audioId);
      const info = document.getElementById(infoId);
      const f = input.files && input.files[0];
      if (!f || !audio) return;
      audio.src = URL.createObjectURL(f);
      audio.style.display = 'block';
      audio.onloadedmetadata = () => {
        const d = audio.duration;
        if (!info || !isFinite(d)) return;
        if (d < 3) { info.style.color = '#f87171'; info.textContent = `⚠️ ${d.toFixed(1)}s — too short, use at least 3 s of speech.`; }
        else if (d > 15) { info.style.color = '#fbbf24'; info.textContent = `ℹ️ ${d.toFixed(1)}s — CosyVoice 2 uses the first 15 s (after trimming silence).`; }
        else { info.style.color = '#34d399'; info.textContent = `✓ ${d.toFixed(1)}s — good length.`; }
      };
    }

    function setVoiceCustStatus(vName, msg, color) {
      const el = document.getElementById(`v-cust-status-${vName}`);
      if (el) { el.style.color = color || 'var(--text-muted)'; el.textContent = msg; }
    }

    async function replaceVoiceClip(vName) {
      const input = document.getElementById(`v-replace-file-${vName}`);
      if (!input || !input.files.length) return alert('Choose an audio file first.');
      const fd = new FormData();
      fd.append('reference_file', input.files[0]);
      fd.append('reference_text', '');
      fd.append('auto_transcribe', 'true');
      setVoiceCustStatus(vName, '⏳ Uploading, cleaning (silence trim + loudness) and transcribing… first run starts the CosyVoice server (1–3 min).', '#38bdf8');
      try {
        const data = await apiJson(`/api/voices/${vName}/reference`, { method: 'POST', body: fd });


        await loadVoiceProfiles();
        loadVoices();
        if (data.transcribe_error) {
          setVoiceCustStatus(vName, `✓ Clip saved (${data.reference_seconds}s). Auto-transcribe failed: ${data.transcribe_error} — type the transcript manually.`, '#fbbf24');
        } else {
          setVoiceCustStatus(vName, `✓ New clip saved (${data.reference_seconds}s). Please check the transcript, then Test Sample.`, '#34d399');
        }
      } catch (e) {
        setVoiceCustStatus(vName, '❌ ' + e.message, '#f87171');
      }
    }

    async function patchVoiceProfile(vName, changes) {
      let res = await apiRequest(`/api/voices/${encodeURIComponent(vName)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(changes)
      });
      if (res.status === 405 || !res.ok) {
        // Fallback to POST in case PATCH is blocked or unhandled
        const res2 = await apiRequest(`/api/voices/${encodeURIComponent(vName)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(changes)
        });

          return await res2.json();

      }
      const data = await res.json().catch(() => ({}));

      return data;
    }

    async function saveVoiceTranscript(vName) {
      const txt = (document.getElementById(`v-reftext-${vName}`)?.value || '').trim();
      try {
        await patchVoiceProfile(vName, { reference_text: txt });
        setVoiceCustStatus(vName, txt ? '✓ Transcript saved — zero-shot mode will be used.' : '✓ Cleared — cross-lingual mode will be used.', '#34d399');
      } catch (e) { setVoiceCustStatus(vName, '❌ ' + e.message, '#f87171'); }
    }

    async function saveBlueMagpieSettings(vName) {
      const cfgEl = document.getElementById(`v-cfg-${vName}`);
      const stepsEl = document.getElementById(`v-steps-${vName}`);
      const chunkEl = document.getElementById(`v-chunk-${vName}`);
      const statusEl = document.getElementById(`v-bm-status-${vName}`);
      const cfg = parseFloat(cfgEl?.value) || 2.0;
      const steps = parseInt(stepsEl?.value, 10) || 10;
      const chunk = chunkEl ? (chunkEl.value === 'true') : true;
      if (statusEl) { statusEl.textContent = "Saving..."; statusEl.style.color = "#38bdf8"; }
      try {
        await patchVoiceProfile(vName, {
          cfg_value: cfg,
          inference_timesteps: steps,
          chunk_sentences: chunk,
        });
        if (statusEl) {
          statusEl.textContent = `✓ BlueMagpie 參數已儲存！(CFG: ${cfg}, Steps: ${steps})`;
          statusEl.style.color = "#34d399";
          setTimeout(() => { if (statusEl) statusEl.textContent = ""; }, 3500);
        }
      } catch (e) {
        if (statusEl) {
          statusEl.textContent = "❌ " + e.message;
          statusEl.style.color = "#f87171";
        }
      }
    }

    async function autoTranscribeVoice(vName) {
      const btn = document.getElementById(`btn-transcribe-${vName}`);
      if (btn) btn.disabled = true;
      setVoiceCustStatus(vName, '⏳ Transcribing with Whisper (first run starts the CosyVoice server and downloads the Whisper model)…', '#38bdf8');
      try {
        const data = await apiJson(`/api/voices/${vName}/transcribe`, { method: 'POST' });


        const ta = document.getElementById(`v-reftext-${vName}`);
        if (ta) ta.value = data.reference_text || '';
        setVoiceCustStatus(vName, '✓ Transcribed and saved. Fix any wrong words, then Save transcript.', '#34d399');
      } catch (e) {
        setVoiceCustStatus(vName, '❌ ' + e.message, '#f87171');
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function switchVoiceEngine(vName, prov) {
      try {
        await patchVoiceProfile(vName, { provider: prov });
        showToast(`🎙️ ${vName} now uses ${getVoiceProviderLabel(prov)} (same voice clip).`);
        await loadVoiceProfiles();
        loadVoices();
      } catch (e) { setVoiceCustStatus(vName, '❌ ' + e.message, '#f87171'); }
    }

    function previewCreatorSelectedVoice() {
      const sel = document.getElementById('voice-select');
      if (!sel || !sel.value) return;
      playExistingVoiceSample(sel.value);
    }

    async function batchGenerateAllVoaiSamples() {
      const btn = document.getElementById('btn-batch-samples');
      if (btn) { btn.disabled = true; btn.textContent = '⏳ 正在批次生成試聽樣本 (Generating)...'; }
      showToast('🚀 開始批次生成 VoAI 聲音試聽檔，請稍候...');
      try {
        const data = await apiJson('/api/voices/generate_missing_samples?provider=voai', { method: 'POST' });


        showToast(`✅ 完成！成功生成 ${data.generated} 個 VoAI 試聽樣本檔！`);
        await loadVoiceProfiles();
      } catch (err) {
        alert(`批次生成試聽失敗: ${err.message}`);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '🎵 批次生成全部試聽樣本 (Batch Generate Samples)';
        }
      }
    }

    async function playExistingVoiceSample(vName) {
      if (!vName) return;
      const btn = document.getElementById(`btn-play-${vName}`);
      const origText = btn ? btn.innerHTML : '';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ 載入中...';
      }
      showToast(`🔊 正在準備「${vName}」聲音試聽...`);

      try {
        let audioEl = document.getElementById(`audio-player-${vName}`);
        if (audioEl) {
          if (!audioEl.src || audioEl.src.includes('undefined')) {
            audioEl.src = `/media/voices/${vName}/test_sample.wav?t=${Date.now()}`;
          }
          audioEl.currentTime = 0;
          await audioEl.play();
        } else {
          const audio = new Audio(`/media/voices/${vName}/test_sample.wav?t=${Date.now()}`);
          await audio.play();
        }
        showToast(`▶️ 正在播放「${vName}」試聽樣本`);
      } catch (err) {
        console.error("Voice playback error:", err);
        showToast(`⚠️ 聲音播放失敗: ${err.message}`, '#f87171');
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = origText || '▶️ 試聽 (Play)';
        }
      }
    }

    function handleElevenVoiceSelect() {
      const sel = document.getElementById('v-eleven-voice');
      const disp = document.getElementById('v-disp');
      const name = document.getElementById('v-name');
      const customGroup = document.getElementById('v-eleven-custom-id-group');
      const customInput = document.getElementById('v-eleven-custom-id');
      const voiceHint = document.getElementById('v-eleven-voice-hint');
      if (!sel) return;

      const isCustom = sel.value === '__custom__';
      if (isCustom) {
        if (customGroup) {
          customGroup.style.display = 'block';
          customGroup.style.background = 'rgba(16,185,129,0.08)';
          customGroup.style.border = '1px solid rgba(16,185,129,0.45)';
        }
        if (voiceHint) {
          voiceHint.style.color = '#34d399';
          voiceHint.style.fontWeight = '600';
          voiceHint.textContent = '✨ Customized mode active — paste your ElevenLabs Voice ID in the box on the right.';
        }
        // Clear auto-filled preset names if switching from a library preset to Customized
        if (disp && disp.value.startsWith('ElevenLabs - ')) {
          disp.value = '';
        }
        if (name && name.value.startsWith('eleven_') && !name.value.startsWith('eleven_custom_')) {
          name.value = '';
        }
        if (disp) disp.placeholder = 'e.g. My Custom ElevenLabs Voice';
        if (name) name.placeholder = 'e.g. my_elevenlabs_voice';
      } else {
        if (customGroup) {
          customGroup.style.display = 'none';
        }
        if (customInput) {
          customInput.value = '';
        }
        if (voiceHint) {
          voiceHint.style.color = 'var(--text-muted)';
          voiceHint.style.fontWeight = '400';
          voiceHint.textContent = 'Using selected ElevenLabs library voice. Choose "✨ Customized" above to enter your own Voice ID.';
        }
        if (sel.selectedIndex >= 0 && (!disp.value || disp.value.startsWith('ElevenLabs'))) {
          const voiceText = sel.options[sel.selectedIndex].text.split('(')[0].trim();
          disp.value = `ElevenLabs - ${voiceText}`;
          if (!name.value || name.value.startsWith('eleven_')) {
            name.value = `eleven_${voiceText.toLowerCase().replace(/[^a-z0-9]/g, '_')}`;
          }
        }
      }
    }

    function handleCustomVoiceIdInput() {
      const sel = document.getElementById('v-eleven-voice');
      const customInput = document.getElementById('v-eleven-custom-id');
      const disp = document.getElementById('v-disp');
      const name = document.getElementById('v-name');
      if (sel && sel.value !== '__custom__' && customInput && customInput.value.trim()) {
        sel.value = '__custom__';
        handleElevenVoiceSelect();
      }
      const cid = (customInput?.value || '').trim();
      if (cid && name && !name.value.trim()) {
        const shortId = cid.slice(0, 6).toLowerCase().replace(/[^a-z0-9]/g, '');
        name.value = `eleven_custom_${shortId || 'voice'}`;
      }
      if (cid && disp && !disp.value.trim()) {
        disp.value = `My Custom ElevenLabs Voice (${cid.slice(0, 6)})`;
      }
    }

    let cachedVoAISpeakers = [];

    function onVoAIVersionOrSpeakerChange() {
      const spkSel = document.getElementById('v-voai-speaker');
      const customSpk = document.getElementById('v-voai-custom-speaker');
      const verSel = document.getElementById('v-voai-version');
      const styleSel = document.getElementById('v-voai-style');
      const nameEl = document.getElementById('v-name');
      const dispEl = document.getElementById('v-disp');
      if (!spkSel) return;

      const isCustom = spkSel.value === '__custom__';
      if (customSpk) {
        customSpk.style.display = isCustom ? 'block' : 'none';
      }

      const chosenSpk = isCustom ? (customSpk?.value || '').trim() : spkSel.value;
      const chosenVer = verSel ? verSel.value : 'Sota+';

      // Populate styles supported by this speaker if available in cachedVoAISpeakers
      const spkObj = cachedVoAISpeakers.find(s => s.name === chosenSpk);
      if (spkObj && styleSel) {
        const curStyle = styleSel.value || '預設';
        const stylesList = (spkObj.styles_by_model && spkObj.styles_by_model[chosenVer]) || spkObj.styles || ['預設'];
        styleSel.innerHTML = '';
        stylesList.forEach(st => {
          const opt = document.createElement('option');
          opt.value = st;
          opt.textContent = st;
          if (st === curStyle) opt.selected = true;
          styleSel.appendChild(opt);
        });
      }

      if (chosenSpk && (!dispEl.value || dispEl.value.startsWith('VoAI - '))) {
        dispEl.value = `VoAI - ${chosenSpk} (${chosenVer})`;
      }
      if (chosenSpk && (!nameEl.value || nameEl.value.startsWith('voai_'))) {
        const slugVer = chosenVer.toLowerCase().replace(/[^a-z0-9]/g, '');
        nameEl.value = `voai_${slugVer}_${chosenSpk}`;
      }
    }

    function onVoAICustomSpeakerInput() {
      onVoAIVersionOrSpeakerChange();
    }

    async function loadVoAISpeakers() {
      try {
        const data = await apiJson('/api/voai/speakers');


        cachedVoAISpeakers = data.speakers || [];

        const badge = document.getElementById('v-voai-badge');
        const hint = document.getElementById('v-voai-key-hint');
        if (badge) {
          if (data.configured) {
            badge.style.background = 'rgba(5,150,105,0.25)';
            badge.style.color = '#34d399';
            badge.style.border = '1px solid #059669';
            badge.textContent = data.live ? '✓ API Key Connected (Live Speakers Loaded)' : '✓ API Key Configured';
            if (hint) hint.style.display = 'none';
          } else {
            badge.style.background = 'rgba(245,158,11,0.15)';
            badge.style.color = '#f59e0b';
            badge.style.border = '1px solid #d97706';
            badge.textContent = '⚠️ VOAI_API_KEY Needed';
            if (hint) hint.style.display = 'block';
          }
        }

        const spkSel = document.getElementById('v-voai-speaker');
        if (spkSel && cachedVoAISpeakers.length) {
          const curVal = spkSel.value || '佑希';
          spkSel.innerHTML = '';
          cachedVoAISpeakers.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.name;
            const metaParts = [s.gender, s.category].filter(Boolean).join(' · ');
            const stylesPreview = (s.styles || ['預設']).join('/');
            opt.textContent = `${s.name}${metaParts ? ` (${metaParts} — ${stylesPreview})` : ` (${stylesPreview})`}`;
            if (s.name === curVal) opt.selected = true;
            spkSel.appendChild(opt);
          });
          const customOpt = document.createElement('option');
          customOpt.value = '__custom__';
          customOpt.textContent = '✨ Custom Speaker Name (手動輸入配音員名稱)';
          if (curVal === '__custom__') customOpt.selected = true;
          spkSel.appendChild(customOpt);
          onVoAIVersionOrSpeakerChange();
        }
      } catch (e) {
        console.warn("Could not fetch VoAI speakers:", e);
      }
    }

    async function handleVoiceProviderChange() {
      const prov = document.getElementById('v-prov').value;
      const bmBox = document.getElementById('v-bluemagpie-container');
      const elevenBox = document.getElementById('v-elevenlabs-container');
      const voaiBox = document.getElementById('v-voai-container');
      const edgeBox = document.getElementById('v-edge-container');
      const refBox = document.getElementById('v-ref-audio-group');
      const hintBox = document.getElementById('v-ref-hint');
      if (edgeBox) edgeBox.style.display = (prov === 'edge') ? 'block' : 'none';

      if (prov === 'bluemagpie') {
        if (bmBox) bmBox.style.display = 'block';
        if (elevenBox) elevenBox.style.display = 'none';
        if (voaiBox) voaiBox.style.display = 'none';
        if (refBox) refBox.style.display = 'block';
        if (hintBox) hintBox.style.display = 'block';
      } else if (prov === 'elevenlabs') {
        if (bmBox) bmBox.style.display = 'none';
        if (elevenBox) elevenBox.style.display = 'block';
        if (voaiBox) voaiBox.style.display = 'none';
        if (refBox) refBox.style.display = 'none';
        if (hintBox) hintBox.style.display = 'none';
        await loadElevenLabsVoices();
        handleElevenVoiceSelect();
      } else if (prov === 'voai') {
        if (bmBox) bmBox.style.display = 'none';
        if (elevenBox) elevenBox.style.display = 'none';
        if (voaiBox) voaiBox.style.display = 'block';
        if (refBox) refBox.style.display = 'none';
        if (hintBox) hintBox.style.display = 'none';
        await loadVoAISpeakers();
        onVoAIVersionOrSpeakerChange();
      } else if (prov === 'edge') {
        if (bmBox) bmBox.style.display = 'none';
        if (elevenBox) elevenBox.style.display = 'none';
        if (voaiBox) voaiBox.style.display = 'none';
        if (refBox) refBox.style.display = 'none';
        if (hintBox) hintBox.style.display = 'none';
      } else {
        if (bmBox) bmBox.style.display = 'none';
        if (elevenBox) elevenBox.style.display = 'none';
        if (voaiBox) voaiBox.style.display = 'none';
        if (refBox) refBox.style.display = 'block';
        if (hintBox) hintBox.style.display = 'block';
      }
      const refTextBox = document.getElementById('v-ref-text-group');
      if (refTextBox) refTextBox.style.display = ['cosyvoice', 'bluemagpie', 'http_clone'].includes(prov) ? 'block' : 'none';
    }

    async function loadElevenLabsVoices() {
      try {
        const data = await apiJson('/api/elevenlabs/voices');

        const badge = document.getElementById('v-elevenlabs-badge');
        const hint = document.getElementById('v-elevenlabs-key-hint');
        if (badge) {
          if (data.configured) {
            badge.style.background = 'rgba(5,150,105,0.25)';
            badge.style.color = '#34d399';
            badge.style.border = '1px solid #059669';
            badge.textContent = '✓ API Key Connected';
            if (hint) hint.style.display = 'none';
          } else {
            badge.style.background = 'rgba(245,158,11,0.15)';
            badge.style.color = '#f59e0b';
            badge.style.border = '1px solid #d97706';
            badge.textContent = '⚠️ API Key Needed';
            if (hint) hint.style.display = 'block';
          }
        }
        if (data.voices && data.voices.length) {
          const sel = document.getElementById('v-eleven-voice');
          if (sel) {
            const currentVal = sel.value || '__custom__';
            sel.innerHTML = '';
            const customOpt = document.createElement('option');
            customOpt.value = '__custom__';
            customOpt.textContent = '✨ Customized (Enter My Own ElevenLabs Voice ID)';
            sel.appendChild(customOpt);

            data.voices.forEach(v => {
              const opt = document.createElement('option');
              opt.value = v.voice_id;
              opt.textContent = v.name;
              sel.appendChild(opt);
            });
            if (currentVal && Array.from(sel.options).some(o => o.value === currentVal)) {
              sel.value = currentVal;
            } else {
              sel.value = '__custom__';
            }
            handleElevenVoiceSelect();
          }
        }
      } catch (e) {
        console.warn("Could not fetch ElevenLabs voices", e);
      }
    }

    async function createNewVoice() {
      let name = document.getElementById('v-name').value.trim();
      let disp = document.getElementById('v-disp').value.trim();
      const prov = document.getElementById('v-prov').value;
      const fileInput = document.getElementById('v-file');

      if (prov === 'elevenlabs') {
        const selectId = document.getElementById('v-eleven-voice')?.value || '__custom__';
        const customId = (document.getElementById('v-eleven-custom-id')?.value || '').trim();
        if (selectId === '__custom__' && !customId) {
          document.getElementById('v-eleven-custom-id')?.focus();
          return alert("Please paste your ElevenLabs Voice ID in the 'Custom ElevenLabs Voice ID' box.");
        }
        if (selectId === '__custom__' && customId) {
          if (!name) name = `eleven_custom_${customId.slice(0, 6).toLowerCase().replace(/[^a-z0-9]/g, '')}`;
          if (!disp) disp = `My Custom ElevenLabs Voice (${customId.slice(0, 6)})`;
        }
      } else if (prov === 'voai') {
        const spkSel = document.getElementById('v-voai-speaker')?.value || '佑希';
        const customSpk = (document.getElementById('v-voai-custom-speaker')?.value || '').trim();
        const chosenSpeaker = (spkSel === '__custom__') ? customSpk : spkSel;
        const chosenVer = document.getElementById('v-voai-version')?.value || 'Sota+';
        if (!chosenSpeaker) {
          return alert("Please select or enter a VoAI Speaker name (例如：佑希).");
        }
        if (!name) name = `voai_${chosenVer.toLowerCase().replace(/[^a-z0-9]/g, '')}_${chosenSpeaker}`;
        if (!disp) disp = `VoAI - ${chosenSpeaker} (${chosenVer})`;
      } else if (prov === 'edge') {
        const edgeVoice = document.getElementById('v-edge-voice')?.value || 'zh-TW-HsiaoChenNeural';
        const shortTag = edgeVoice.replace('zh-TW-', '').replace('Neural', '').toLowerCase();
        if (!name) name = `edge_tw_${shortTag}_${Date.now().toString().slice(-4)}`;
        if (!disp) disp = `Edge-TTS 臺灣國語 (${edgeVoice})`;
      }

      if (!name || !disp) {
        return alert("Please enter both Profile Name and Display Name");
      }

      const fd = new FormData();
      fd.append('name', name);
      fd.append('display_name', disp);
      fd.append('provider', prov);
      fd.append('language', 'Traditional Chinese');
      fd.append('speech_rate', prov === 'voai' ? parseFloat(document.getElementById('v-voai-speed')?.value || 1.0) : (prov === 'edge' ? parseFloat(document.getElementById('v-edge-speed')?.value || 1.02) : 1.0));
      fd.append('is_default', false);

      if (prov === 'elevenlabs') {
        const customId = (document.getElementById('v-eleven-custom-id')?.value || '').trim();
        const selectId = document.getElementById('v-eleven-voice')?.value || '__custom__';
        const chosenVoiceId = (selectId === '__custom__') ? customId : (customId || selectId);
        const modelId = document.getElementById('v-eleven-model')?.value || 'eleven_multilingual_v2';
        const stability = parseFloat(document.getElementById('v-eleven-stability')?.value || 0.5);
        const similarity = parseFloat(document.getElementById('v-eleven-similarity')?.value || 0.75);

        fd.append('voice_id', chosenVoiceId);
        fd.append('voice', chosenVoiceId);
        fd.append('model_id', modelId);
        fd.append('stability', stability);
        fd.append('similarity_boost', similarity);
      } else if (prov === 'voai') {
        const spkSel = document.getElementById('v-voai-speaker')?.value || '佑希';
        const customSpk = (document.getElementById('v-voai-custom-speaker')?.value || '').trim();
        const chosenSpeaker = (spkSel === '__custom__') ? customSpk : spkSel;
        const chosenVer = document.getElementById('v-voai-version')?.value || 'Sota+';
        const chosenStyle = document.getElementById('v-voai-style')?.value || '預設';
        const chosenPitch = parseFloat(document.getElementById('v-voai-pitch')?.value || 0);

        fd.append('voice_id', chosenSpeaker);
        fd.append('voice', chosenSpeaker);
        fd.append('model_id', chosenVer);
        fd.append('voai_style', chosenStyle);
        fd.append('pitch_shift', chosenPitch);
      } else if (prov === 'edge') {
        const edgeVoice = document.getElementById('v-edge-voice')?.value || 'zh-TW-HsiaoChenNeural';
        const edgePitch = parseFloat(document.getElementById('v-edge-pitch')?.value || 0);
        fd.append('voice', edgeVoice);
        fd.append('voice_id', edgeVoice);
        fd.append('model_id', edgeVoice);
        fd.append('pitch_shift', edgePitch);
      } else if (prov === 'bluemagpie') {
        const bmCfg = parseFloat(document.getElementById('v-bm-cfg')?.value || 2.8);
        const bmSteps = parseInt(document.getElementById('v-bm-steps')?.value || 18, 10);
        fd.append('cfg_value', bmCfg);
        fd.append('inference_timesteps', bmSteps);
        fd.append('chunk_sentences', true);
      }

      if (fileInput && fileInput.files.length > 0) {
        fd.append('reference_file', fileInput.files[0]);
      } else if (prov === 'cosyvoice') {
        return alert("CosyVoice 2 needs a clip of your voice — choose an audio file (3–15 s of clean speech).");
      }
      const refText = (document.getElementById('v-ref-text')?.value || '').trim();
      if (refText) fd.append('reference_text', refText);

      try {
        const created = await apiJson('/api/voices', {
          method: 'POST',
          body: fd
        });


        document.getElementById('v-name').value = '';
        document.getElementById('v-disp').value = '';
        const customInput = document.getElementById('v-eleven-custom-id');
        if (customInput) customInput.value = '';
        if (fileInput) fileInput.value = '';
        const refTextEl = document.getElementById('v-ref-text');
        if (refTextEl) refTextEl.value = '';
        const prevEl = document.getElementById('v-file-preview');
        if (prevEl) { prevEl.style.display = 'none'; prevEl.removeAttribute('src'); }
        const infoEl = document.getElementById('v-file-info');
        if (infoEl) infoEl.textContent = '';
        loadVoices();
        await loadVoiceProfiles();
        if (prov === 'cosyvoice' && !refText && created && created.name) {
          showToast(`✓ Profile "${created.name}" created. Auto-transcribing your clip…`);
          autoTranscribeVoice(created.name);
        } else {
          alert("Voice profile created successfully!");
        }
      } catch (e) {
        alert("Error: " + e.message);
      }
    }

    async function testVoiceProfile(vName, force = false) {
      const btn = document.getElementById(`btn-test-${vName}`);
      const progBox = document.getElementById(`v-prog-box-${vName}`);
      const progTitle = document.getElementById(`v-prog-title-${vName}`);
      const progPct = document.getElementById(`v-prog-pct-${vName}`);
      const progBar = document.getElementById(`v-prog-bar-${vName}`);
      const progStatus = document.getElementById(`v-prog-status-${vName}`);

      let text = "你好，這是我複製的聲音樣本測試。";
      if (force) {
        const customText = prompt("Enter sample text to synthesize:", text);
        if (!customText) return;
        text = customText;
      }

      if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ Synthesizing...";
      }
      if (progBox) {
        progBox.style.display = 'block';
        if (progTitle) progTitle.textContent = "🚀 Synthesizing Voice Sample...";
        if (progPct) progPct.textContent = "15%";
        if (progBar) progBar.style.width = "15%";
        if (progStatus) progStatus.textContent = "Connecting to TTS engine...";
      }

      // Smooth progress animation while awaiting TTS synthesis
      let simPct = 15;
      const progTimer = setInterval(() => {
        if (simPct < 88) {
          simPct += Math.floor(Math.random() * 8) + 4;
          if (progBar) progBar.style.width = `${simPct}%`;
          if (progPct) progPct.textContent = `${simPct}%`;
          if (progStatus) {
            if (simPct > 65) progStatus.textContent = "Synthesizing waveform audio...";
            else if (simPct > 35) progStatus.textContent = "Processing voice timbre...";
          }
        }
      }, 350);

      try {
        const res = await apiRequest('/api/voices/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ voice_name: vName, text: text, force: force })
        });
        clearInterval(progTimer);


        const isCached = res.headers.get('X-Sample-Cached') === 'true';

        if (progBar) progBar.style.width = "100%";
        if (progPct) progPct.textContent = "100%";
        if (progTitle) progTitle.textContent = isCached ? "✓ Loaded Saved Sample" : "✓ Voice Sample Generated & Saved!";
        if (progStatus) progStatus.textContent = isCached ? "Playing from saved audio" : "Saved to profile folder!";

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = new Audio(url);
        a.onended = () => {
          URL.revokeObjectURL(url);
          loadVoiceProfiles();
        };
        try {
          await a.play();
        } catch (playErr) {
          console.warn("Autoplay was prevented:", playErr);
          loadVoiceProfiles();
        }
      } catch (e) {
        clearInterval(progTimer);
        if (progBox) progBox.style.display = 'none';
        alert("Test synthesis failed: " + e.message);
        if (btn) {
          btn.disabled = false;
          btn.textContent = force ? "🔄 Re-test" : "🎙️ Test Sample";
        }
      }
    }

    async function deleteVoiceProfile(vName) {
      if (!confirm("Are you sure you want to delete profile " + vName + "?")) return;
      await apiRequest('/api/voices/' + vName, { method: 'DELETE' });
      loadVoices();
      loadVoiceProfiles();
    }

    // ==========================================
    // BACKGROUND AMBIENT MUSIC FUNCTIONS (CATEGORIZED)
    // ==========================================
    let cachedMusicTracks = [];
    let cachedMusicCategories = {};
    let activeMusicCategory = 'all';
    let currentPreviewAudio = null;

    const MUSIC_CAT_META = {
      'tech_futuristic': { icon: '🚀', label: 'Tech & Sci-Fi', desc: 'Electronic synths & futuristic tech', bg: '#0c2a4a', color: '#60a5fa', border: '#1d4ed8' },
      'cinematic_documentary': { icon: '🎬', label: 'Cinematic Documentary', desc: 'Acoustic strings & historical storytelling', bg: '#3d260f', color: '#fbbf24', border: '#b45309' },
      'mystery_cosmic': { icon: '🌌', label: 'Dark Mystery & Space', desc: 'Cosmic drones & unexplained enigmas', bg: '#281442', color: '#c084fc', border: '#7e22ce' },
      'calm_focus': { icon: '🌿', label: 'Calm & Focus', desc: 'Soft ambient pads & meditative study vibes', bg: '#0d3326', color: '#34d399', border: '#059669' },
      'dramatic_tension': { icon: '⚡', label: 'Dramatic Tension', desc: 'Low bass drones & investigative pulses', bg: '#3b141e', color: '#f87171', border: '#dc2626' },
      'uplifting_inspirational': { icon: '✨', label: 'Uplifting & Wonder', desc: 'Inspiring harmonies & breakthrough discoveries', bg: '#332d0c', color: '#fde047', border: '#ca8a04' },
      'custom': { icon: '📁', label: 'Custom / Other', desc: 'Custom uploaded ambient tracks', bg: '#1e293b', color: '#94a3b8', border: '#475569' }
    };

    function getMusicCategoryMeta(key) {
      return MUSIC_CAT_META[key] || {
        icon: '🎵',
        label: (key || 'Ambient').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        desc: 'Royalty-Free Ambient Track',
        bg: '#1e293b',
        color: '#94a3b8',
        border: '#475569'
      };
    }

    function buildCategorizedSelectOptions(tracks, curVal) {
      let html = '<option value="auto">✨ Auto (Smart Content-Matched Ambient)</option>';
      const orderedCats = ['tech_futuristic', 'cinematic_documentary', 'mystery_cosmic', 'calm_focus', 'dramatic_tension', 'uplifting_inspirational', 'custom'];

      orderedCats.forEach(catKey => {
        const catTracks = tracks.filter(t => (t.category || '').toLowerCase() === catKey);
        if (catTracks.length > 0) {
          const meta = getMusicCategoryMeta(catKey);
          html += `<optgroup label="${meta.icon} ${meta.label} (${catTracks.length})">`;
          html += `<option value="${catKey}">🎲 Any ${meta.label} (Auto-Pick)</option>`;
          catTracks.forEach(t => {
            html += `<option value="${t.filename}">${t.name} — ${t.mood || meta.label} (${t.size_mb} MB)</option>`;
          });
          html += `</optgroup>`;
        }
      });

      // Any remaining categories not in orderedCats
      const otherCats = [...new Set(tracks.map(t => t.category))].filter(c => c && !orderedCats.includes(c));
      otherCats.forEach(catKey => {
        const catTracks = tracks.filter(t => t.category === catKey);
        if (catTracks.length > 0) {
          const meta = getMusicCategoryMeta(catKey);
          html += `<optgroup label="${meta.icon} ${meta.label}">`;
          catTracks.forEach(t => {
            html += `<option value="${t.filename}">${t.name} (${t.size_mb} MB)</option>`;
          });
          html += `</optgroup>`;
        }
      });

      html += '<option value="none">None (Voice Only, No Music)</option>';
      return html;
    }


    // ==========================================
    // Virtual Presenter & Talking Avatar Management
    // ==========================================
    let cachedAvatarsList = [];

    async function loadAvatars() {
      const listEl = document.getElementById('avatars-list');
      const badgeEl = document.getElementById('avatars-count-badge');
      if (!listEl) return;
      listEl.innerHTML = '<div style="grid-column:1/-1; padding:20px; text-align:center; color:var(--text-muted);">Loading avatars...</div>';
      try {
        if (!cachedVoiceList || !cachedVoiceList.length) {
          try {
            cachedVoiceList = await apiJson('/api/voices');
          } catch (e) {}
        }
        const data = await apiJson('/api/avatars');

        const avs = data.avatars || [];
        cachedAvatarsList = avs;
        populatePresenterAvatarSelectors(avs);
        populateAvatarVoiceDropdown();
        if (badgeEl) badgeEl.textContent = `${avs.length} Avatar${avs.length === 1 ? '' : 's'}`;
        if (!avs.length) {
          listEl.innerHTML = `<div style="grid-column:1/-1; padding:28px; text-align:center; color:var(--text-muted); background:var(--bg-sunken); border-radius:8px; border:1px dashed var(--border-muted);">
            尚無建立任何虛擬主播形象。請使用下方表單上傳一張肖像照片，建立你的第一個 AI 數字人主播！
          </div>`;
          return;
        }
        const buster = Date.now();
        listEl.innerHTML = avs.map(av => {
          const imgUrl = av.image_url ? `${av.image_url}?t=${buster}` : '';
          const sampleUrl = av.has_test_sample ? `/api/avatars/sample/${av.name}?t=${buster}` : '';
          return `
            <div style="background:#080d16; border:1px solid ${av.is_default ? '#8b5cf6' : 'var(--card-border)'}; border-radius:8px; padding:16px; display:flex; flex-direction:column; gap:12px; box-shadow: ${av.is_default ? '0 0 16px rgba(139,92,246,0.2)' : 'none'};">
              <div style="display:flex; gap:12px; align-items:flex-start;">
                <div style="width:84px; height:84px; border-radius:8px; overflow:hidden; background:#000; flex-shrink:0; border:1px solid #334155;">
                  ${imgUrl ? `<img src="${imgUrl}" style="width:100%; height:100%; object-fit:cover; cursor:pointer;" onclick="window.open('${imgUrl}')" title="Click to view full portrait">` : '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#64748b;font-size:24px;">👤</div>'}
                </div>
                <div style="flex:1; min-width:0;">
                  <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                    <span style="font-weight:700; color:#f8fafc; font-size:14px;">${av.display_name || av.name}</span>
                    ${av.is_default ? '<span style="background:rgba(139,92,246,0.25); border:1px solid #8b5cf6; color:#c4b5fd; font-size:11px; font-weight:700; padding:1px 6px; border-radius:4px;">⭐ 預設主播</span>' : ''}
                    ${av.is_masked ? '<span style="background:rgba(16,185,129,0.25); border:1px solid #10b981; color:#6ee7b7; font-size:11px; font-weight:700; padding:1px 6px; border-radius:4px;">😷 口罩真人講者 (Masked)</span>' : ''}
                  </div>
                  <div style="font-size:11px; color:#94a3b8; font-family:monospace; margin-top:3px;">ID: ${av.name}</div>
                  <div style="font-size:11px; color:#cbd5e1; margin-top:4px;">
                    引擎: <b style="color:${av.is_masked ? '#6ee7b7' : '#93c5fd'};">${av.is_masked ? 'Masked Speaker (戴口罩自錄動態 · 本地秒級)' : av.provider}</b> | 版型: <b>${av.layout || 'fullscreen'}</b>
                  </div>
                </div>
              </div>

              <!-- Dedicated Voice Profile Switch Bar -->
              <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(59, 130, 246, 0.35); border-radius: 6px; padding: 8px 12px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  <span style="font-size: 12px; font-weight: 700; color: #38bdf8; display: flex; align-items: center; gap: 5px;">
                    🎙️ 主播專屬聲音音色 (Voice Profile):
                  </span>
                  <span style="font-size: 11px; color: #94a3b8;">
                    ${av.voice_profile ? `<span style="background: rgba(16, 185, 129, 0.2); border: 1px solid rgba(16, 185, 129, 0.4); color: #6ee7b7; padding: 1px 6px; border-radius: 4px; font-weight: 700;">● ${av.voice_profile}</span>` : '<span style="color: #64748b;">(未綁定 · 使用專案預設音色)</span>'}
                  </span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                  <span style="font-size: 11px; color: #94a3b8;">切換音色:</span>
                  <select onchange="updateAvatarVoiceProfile('${av.name}', this.value)" style="padding: 4px 10px; font-size: 12px; background: #020617; border: 1px solid #3b82f6; color: #93c5fd; border-radius: 5px; font-weight: 700; cursor: pointer;">
                    <option value="">(使用專案預設音色 - Follow Project Voice)</option>
                    ${(cachedVoiceList || []).map(v => `<option value="${v.name}" ${av.voice_profile === v.name ? 'selected' : ''}>${v.display_name} [${getVoiceProviderLabel(v.provider)}]${v.name === 'mytsaovoice' ? ' (Default)' : ''}</option>`).join('')}
                  </select>
                </div>
              </div>

              ${renderAvatarComparePanel(av, buster)}

              <div style="display:flex; gap:8px; align-items:center; justify-content:space-between; margin-top:auto; padding-top:8px; border-top:1px solid #1e293b;">
                <div style="display:flex; gap:6px;">
                  <button type="button" class="btn-sec" onclick="testAvatarLipSync('${av.name}')" id="btn-test-av-${av.name}" style="padding:4px 10px; font-size:11px; font-weight:700; background:rgba(59,130,246,0.15); border-color:#3b82f6; color:#93c5fd;">
                    ▶ 測試 3秒口型
                  </button>
                  <button type="button" class="btn-sec" onclick="openRerenderAvatarModal('${av.name}')" style="padding:4px 10px; font-size:11px; font-weight:700; background:rgba(139,92,246,0.2); border-color:#8b5cf6; color:#c4b5fd;" title="Apply this avatar to replace presenter clips in the active project video">
                    🎭 套用到專案影片
                  </button>
                </div>
                <div style="display:flex; gap:6px;">
                  <button type="button" class="btn-sec" onclick="rotateAvatar('${av.name}')" style="padding:4px 8px; font-size:11px; color:#93c5fd; background:rgba(37,99,235,0.15); border-color:#2563eb;" title="將肖像照片順時針旋轉 90 度">
                    🔄 旋轉 90°
                  </button>
                  ${!av.is_default ? `
                    <button type="button" class="btn-sec" onclick="setDefaultAvatar('${av.name}')" style="padding:4px 8px; font-size:11px; color:#cbd5e1;">
                      設為預設
                    </button>
                  ` : ''}
                  <button type="button" class="btn-sec btn-danger" onclick="deleteAvatarProfile('${av.name}')" style="padding:4px 8px; font-size:11px;">
                    🗑️ 刪除
                  </button>
                </div>
              </div>
              <div id="test-av-status-${av.name}" style="font-size:11px; min-height:14px;"></div>
            </div>
          `;
        }).join('');
      } catch (e) {
        listEl.innerHTML = `<div style="color:#ef4444; padding:20px;">Failed to load avatars: ${e.message}</div>`;
      }
    }

    function populateAvatarVoiceDropdown() {
      const sel = document.getElementById('av-voice-profile');
      if (!sel) return;
      const cur = sel.value;
      sel.innerHTML = '<option value="">(使用專案預設音色 - Project Default Voice)</option>';
      if (cachedVoiceList && cachedVoiceList.length) {
        cachedVoiceList.forEach(v => {
          const opt = document.createElement('option');
          opt.value = v.name;
          const pLabel = getVoiceProviderLabel(v.provider);
          opt.textContent = `${v.display_name} [${pLabel}]` + (v.name === 'mytsaovoice' ? ' (Default)' : '');
          sel.appendChild(opt);
        });
      }
      if (cur) sel.value = cur;
    }

    async function updateAvatarVoiceProfile(avName, voiceName) {
      try {
        await apiRequest(`/api/avatars/${encodeURIComponent(avName)}/voice_profile`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ voice_profile: voiceName || null })
        })

        showToast(`✓ 主播 ${avName} 的專屬音色已設定為: ${voiceName || '專案預設'}`);
        await loadAvatars();
      } catch (err) {
        alert("Error: " + err.message);
      }
    }

    function onAvatarMaskedToggle() {
      const isMasked = document.getElementById('av-is-masked')?.checked;
      const provSel = document.getElementById('av-provider');
      if (isMasked && provSel && provSel.value !== 'masked_speaker') {
        provSel.value = 'masked_speaker';
      } else if (!isMasked && provSel && provSel.value === 'masked_speaker') {
        provSel.value = 'fal-ai/latentsync';
      }
      onAvatarProviderChange();
    }

    function onAvatarProviderChange() {
      const prov = document.getElementById('av-provider').value;
      const isMaskedCheck = document.getElementById('av-is-masked');
      const isMasked = prov === 'masked_speaker' || (isMaskedCheck && isMaskedCheck.checked);
      if (isMaskedCheck && prov === 'masked_speaker') isMaskedCheck.checked = true;

      const vBadge = document.getElementById('av-video-badge');
      const photoHint = document.getElementById('av-photo-hint');
      const vInput = document.getElementById('av-video-file');

      if (prov === 'masked_speaker' || isMasked) {
        if (vBadge) {
          vBadge.textContent = '戴口罩真人必備 (無需照片)';
          vBadge.style.background = 'rgba(16, 185, 129, 0.25)';
          vBadge.style.borderColor = 'rgba(16, 185, 129, 0.5)';
          vBadge.style.color = '#6ee7b7';
        }
        if (vInput) vInput.style.borderColor = '#10b981';
        if (photoHint) photoHint.textContent = '戴口罩模式：無需上傳照片，自動從自錄影片第 1 格擷取頭像！';
      } else if (prov === 'fal-ai/latentsync') {
        if (vBadge) {
          vBadge.textContent = 'LatentSync 核心必備 (需露嘴露臉)';
          vBadge.style.background = 'rgba(245, 158, 11, 0.25)';
          vBadge.style.borderColor = 'rgba(245, 158, 11, 0.5)';
          vBadge.style.color = '#fde68a';
        }
        if (vInput) vInput.style.borderColor = '#d97706';
        if (photoHint) photoHint.textContent = '若已上傳錄影底片，此項可免填 (自動從底片擷取)';
      } else {
        if (vBadge) {
          vBadge.textContent = '選填 (僅錄影底片引擎使用)';
          vBadge.style.background = 'rgba(100, 116, 139, 0.2)';
          vBadge.style.borderColor = 'rgba(100, 116, 139, 0.4)';
          vBadge.style.color = '#94a3b8';
        }
        if (vInput) vInput.style.borderColor = '#334155';
        if (photoHint) photoHint.textContent = '單圖引擎必填';
      }
    }

    async function handleCreateAvatar(e) {
      e.preventDefault();
      const name = document.getElementById('av-name').value.trim();
      const disp = document.getElementById('av-disp').value.trim();
      const prov = document.getElementById('av-provider').value;
      const layout = document.getElementById('av-layout').value;
      const isDef = document.getElementById('av-default').checked;
      const voiceProf = (document.getElementById('av-voice-profile') ? document.getElementById('av-voice-profile').value : '') || '';
      const fileInput = document.getElementById('av-file');
      const videoInput = document.getElementById('av-video-file');
      const statusEl = document.getElementById('create-avatar-status');
      const btn = document.getElementById('btn-save-avatar');

      const isMasked = document.getElementById('av-is-masked')?.checked || prov === 'masked_speaker';
      const hasImage = fileInput && fileInput.files && fileInput.files.length > 0;
      const hasVideo = videoInput && videoInput.files && videoInput.files.length > 0;

      if (!name) return alert("請輸入主播代號 (ID)");
      if (isMasked && !hasVideo) {
        return alert("😷 戴口罩講者模式：請上傳一段您戴口罩面向鏡頭說話/手勢的自錄影片 (MP4/MOV/WEBM)！無需上傳肖像照。");
      }
      if (!isMasked && !hasImage && !hasVideo) {
        return alert("請至少上傳一張肖像照片，或是上傳一段錄影底片 (MP4/MOV)！");
      }

      const fd = new FormData();
      fd.append('name', name);
      fd.append('display_name', disp || name);
      fd.append('provider', isMasked ? 'masked_speaker' : prov);
      fd.append('layout', layout);
      fd.append('is_default', isDef);
      fd.append('is_masked', isMasked);
      if (voiceProf) fd.append('voice_profile', voiceProf);
      if (hasImage) fd.append('file', fileInput.files[0]);
      if (hasVideo) fd.append('video_file', videoInput.files[0]);

      if (btn) btn.disabled = true;
      if (statusEl) {
        statusEl.style.color = '#38bdf8';
        statusEl.textContent = isMasked
          ? '⏳ 上傳戴口罩真人自錄影片並進行 1080p 規格化與頭像擷取中 (約 3~8 秒)...'
          : (hasVideo ? '⏳ 上傳底片與肖像並進行 1080p 規格化中 (約 5~15 秒)...' : '⏳ 上傳肖像並最佳化設定中...');
      }

      try {
        await apiRequest('/api/avatars', { method: 'POST', body: fd })

        if (statusEl) {
          statusEl.style.color = '#34d399';
          statusEl.textContent = hasVideo ? '✓ 主播與錄影底片建立成功！' : '✓ 主播建立成功！';
        }
        document.getElementById('form-create-avatar').reset();
        onAvatarProviderChange();
        await loadAvatars();
      } catch (err) {
        if (statusEl) {
          statusEl.style.color = '#f87171';
          statusEl.textContent = `❌ ${err.message}`;
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    const AVATAR_ENGINES = [
      { key: 'masked_speaker', provider: 'masked_speaker', label: 'Masked Speaker', sub: '戴口罩真人 · 手勢動態 · 本地秒級', eta: '約 1~2 秒 (本地免金鑰)', needs: 'video' },
      { key: 'latentsync', provider: 'fal-ai/latentsync', label: 'LatentSync', sub: '真人底片 · 需露嘴露臉', eta: '約 1~3 分鐘', needs: 'video' },
      { key: 'kling_pro', provider: 'fal-ai/kling-video/v1/pro/ai-avatar', label: 'Kling Avatar Pro', sub: '單圖 · 最高畫質', eta: '約 3~8 分鐘', needs: 'image' },
      { key: 'kling_std', provider: 'fal-ai/kling-video/v1/standard/ai-avatar', label: 'Kling Avatar Std', sub: '單圖 · 進階表情', eta: '約 2~5 分鐘', needs: 'image' },
      { key: 'sadtalker', provider: 'fal-ai/sadtalker', label: 'SadTalker', sub: '單圖 · 基礎', eta: '約 20~40 秒', needs: 'image' },
    ];

    function renderAvatarComparePanel(av, buster) {
      const samples = av.engine_samples || {};
      const slots = AVATAR_ENGINES.map(eng => {
        const has = samples[eng.key];
        const active = av.provider === eng.provider;
        const blocked = eng.needs === 'video' && !av.has_base_video;
        const media = has
          ? `<video src="/api/avatars/sample/${av.name}?engine=${eng.key}&t=${has}" controls preload="metadata" style="width:100%; aspect-ratio:3/4; object-fit:contain; background:#000; border-radius:4px; display:block;"></video>`
          : `<div style="width:100%; aspect-ratio:3/4; background:#000; border-radius:4px; display:flex; align-items:center; justify-content:center; text-align:center; padding:8px; color:#64748b; font-size:11px;">${blocked ? '需先上傳真人底片 ↓' : '尚未產生'}</div>`;
        return `
          <div style="background:#020617; border:1px solid ${active ? '#8b5cf6' : '#1e293b'}; border-radius:6px; padding:6px; display:flex; flex-direction:column; gap:6px; min-width:0;">
            <div style="display:flex; justify-content:space-between; align-items:baseline; gap:4px;">
              <span style="font-size:12px; font-weight:700; color:#e2e8f0;">${eng.label}</span>
              ${active ? '<span style="font-size:10px; color:#c4b5fd;">● 使用中</span>' : ''}
            </div>
            <div style="font-size:10px; color:#94a3b8; margin-top:-4px;">${eng.sub}</div>
            ${media}
            <div style="display:flex; gap:4px;">
              <button type="button" class="btn-sec" id="btn-cmp-${av.name}-${eng.key}" ${blocked ? 'disabled' : ''}
                onclick="testAvatarEngine('${av.name}', '${eng.key}')"
                style="flex:1; padding:3px 6px; font-size:11px; color:#93c5fd; background:rgba(59,130,246,0.12); border-color:#3b82f6;">
                ${has ? '↻ 重新產生' : '▶ 產生'}
              </button>
              ${!active ? `<button type="button" class="btn-sec" ${blocked ? 'disabled' : ''} onclick="adoptAvatarEngine('${av.name}', '${eng.key}')" title="之後影片的主播場景使用此引擎" style="padding:3px 6px; font-size:11px; color:#c4b5fd;">採用</button>` : ''}
            </div>
            <div id="cmp-status-${av.name}-${eng.key}" style="font-size:10px; min-height:12px; color:#94a3b8;"></div>
          </div>`;
      }).join('');

      const baseVid = av.has_base_video
        ? `<video src="/api/avatars/base_video/${av.name}?t=${buster}" muted controls preload="metadata" style="height:72px; border-radius:4px; background:#000;"></video>`
        : '';
      return `
        <div style="display:flex; flex-direction:column; gap:8px;">
          <div style="font-size:12px; font-weight:600; color:#38bdf8;">🎬 口型引擎比較 (同一段語音，各引擎各自產生)</div>
          <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(170px, 1fr)); gap:8px;">${slots}</div>
          <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap; background:#0b1120; border:1px dashed #334155; border-radius:6px; padding:8px;">
            ${baseVid}
            <div style="flex:1; min-width:220px; font-size:11px; color:#94a3b8; line-height:1.5;">
              <b style="color:#e2e8f0;">真人底片 (LatentSync 用)</b>${av.has_base_video ? ' ✓ 已上傳' : ''}<br>
              用手機錄 10~30 秒的自己：面向鏡頭、自然說話與手勢（內容不重要，聲音會被移除）。系統會來回循環這段底片，再把嘴型換成旁白。
            </div>
            <label class="btn-sec" style="padding:4px 10px; font-size:11px; cursor:pointer; color:#fbbf24; border-color:#d97706;">
              ⬆ ${av.has_base_video ? '更換底片' : '上傳底片'}
              <input type="file" accept="video/mp4,video/quicktime,video/webm" style="display:none;" onchange="uploadAvatarBaseVideo('${av.name}', this)">
            </label>
            <span id="base-status-${av.name}" style="font-size:11px;"></span>
          </div>
        </div>`;
    }

    async function testAvatarEngine(avName, engineKey) {
      const eng = AVATAR_ENGINES.find(e => e.key === engineKey);
      const btn = document.getElementById(`btn-cmp-${avName}-${engineKey}`);
      const st = document.getElementById(`cmp-status-${avName}-${engineKey}`);
      if (btn) btn.disabled = true;
      const t0 = Date.now();
      const tick = setInterval(() => {
        if (st) { st.style.color = '#38bdf8'; st.textContent = `⏳ 產生中 ${Math.round((Date.now() - t0) / 1000)}s (${eng.eta})`; }
      }, 1000);
      try {
        const res = await apiRequest(`/api/avatars/${encodeURIComponent(avName)}/test?engine=${engineKey}`, { method: 'POST' });
        const data = await res.json().catch(() => ({}));

        clearInterval(tick);
        await loadAvatars();
        const st2 = document.getElementById(`cmp-status-${avName}-${engineKey}`);
        if (st2) { st2.style.color = '#34d399'; st2.textContent = `✓ 完成 (${Math.round((Date.now() - t0) / 1000)}s)`; }
      } catch (e) {
        clearInterval(tick);
        if (st) { st.style.color = '#f87171'; st.textContent = `❌ ${e.message}`; st.title = e.message; }
        if (btn) btn.disabled = false;
      }
    }

    async function adoptAvatarEngine(avName, engineKey) {
      try {
        const res = await apiRequest(`/api/avatars/${encodeURIComponent(avName)}/provider?engine=${engineKey}`, { method: 'POST' });
        const data = await res.json().catch(() => ({}));

        showToast(`✓ ${avName} 之後將使用 ${data.provider}`);
        await loadAvatars();
      } catch (e) {
        alert(`採用失敗: ${e.message}`);
      }
    }

    async function uploadAvatarBaseVideo(avName, input) {
      if (!input.files || !input.files.length) return;
      const st = document.getElementById(`base-status-${avName}`);
      const fd = new FormData();
      fd.append('file', input.files[0]);
      if (st) { st.style.color = '#38bdf8'; st.textContent = '⏳ 上傳並轉檔中...'; }
      try {
        const res = await apiRequest(`/api/avatars/${encodeURIComponent(avName)}/base_video`, { method: 'POST', body: fd });
        const data = await res.json().catch(() => ({}));

        showToast(`✓ 底片已儲存 (${(data.duration || 0).toFixed(1)}s)`);
        await loadAvatars();
      } catch (e) {
        if (st) { st.style.color = '#f87171'; st.textContent = `❌ ${e.message}`; }
      }
    }

    async function testAvatarLipSync(avName) {
      const btn = document.getElementById(`btn-test-av-${avName}`);
      const statusEl = document.getElementById(`test-av-status-${avName}`);
      if (btn) btn.disabled = true;
      if (statusEl) {
        statusEl.style.color = '#38bdf8';
        statusEl.textContent = '⏳ 正調用 SadTalker 驅動口型與臉部表情 (約需 20~30 秒)...';
      }
      try {
        const data = await apiJson(`/api/avatars/${encodeURIComponent(avName)}/test`, { method: 'POST' });


        if (statusEl) {
          const prov = (data.meta && data.meta.provider) ? data.meta.provider : '';
          if (prov === 'local_fallback') {
            statusEl.style.color = '#f59e0b';
            statusEl.textContent = '⚠️ 雲端引擎未連線，已使用本地備援動態';
          } else {
            statusEl.style.color = '#34d399';
            statusEl.textContent = `✓ 測試完成！(使用 ${prov})`;
          }
        }
        await loadAvatars();
      } catch (e) {
        if (statusEl) {
          statusEl.style.color = '#f87171';
          statusEl.textContent = `❌ 測試失敗: ${e.message}`;
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    }

        async function rotateAvatar(avName) {
      try {
        await apiRequest(`/api/avatars/${encodeURIComponent(avName)}/rotate?degrees=90`, { method: 'POST' })

        showToast(`🔄 已將 ${avName} 肖像順時針旋轉 90°`);
        await loadAvatars();
      } catch (e) {
        alert("Failed to rotate avatar: " + e.message);
      }
    }

    async function setDefaultAvatar(avName) {
      try {
        const fd = new FormData();
        fd.append('name', avName);
        fd.append('is_default', 'true');
        await apiRequest('/api/avatars', { method: 'POST', body: fd });
        showToast(`⭐ 已將 ${avName} 設為預設數字人主播`);
        await loadAvatars();
      } catch (e) {
        alert("Failed to set default avatar: " + e.message);
      }
    }

    async function deleteAvatarProfile(avName) {
      if (!confirm(`確定要刪除虛擬主播 [${avName}] 及其肖像與測試影片嗎？`)) return;
      try {
        await apiRequest(`/api/avatars/${encodeURIComponent(avName)}`, { method: 'DELETE' });
        showToast(`🗑️ 虛擬主播 ${avName} 已刪除`);
        await loadAvatars();
      } catch (e) {
        alert("Failed to delete avatar: " + e.message);
      }
    }

    function onPresenterPlacementChange() {
      const sel = document.getElementById('creator-presenter-placement');
      const hint = document.getElementById('creator-presenter-hint');
      const avSel = document.getElementById('creator-presenter-avatar');
      const compCb = document.getElementById('creator-auto-presenter');
      if (!sel) return;
      const val = sel.value;
      if (compCb) compCb.checked = (val !== 'none');

      if (avSel) {
        avSel.disabled = (val === 'none');
        avSel.style.opacity = (val === 'none') ? '0.4' : '1.0';
      }

      const hints = {
        'none': '全片採用生圖與運鏡，無真人出鏡。',
        'intro': '僅在第 1 幕出鏡，用真人臉部與口型抓住觀眾第一眼留存。',
        'intro_outro': '第 1 幕開場吸睛，最後一幕再次出鏡強化品牌記憶與引導訂閱 (CTA)。',
        'intro_middle_outro': '⭐ 推薦：開場抓住目光、中段轉折點重新喚醒專注、結尾引導行動，完播率最高。',
        'chapters': '每個主題大段落的第一幕由主播引言，其餘幕為視覺畫面。',
        'all': '全片每一幕均由真人主播口型同步播報。'
      };
      if (hint) {
        hint.textContent = hints[val] || '';
      }
    }

    function populatePresenterAvatarSelectors(avatars) {
      const creatorSel = document.getElementById('creator-presenter-avatar');
      if (creatorSel) {
        creatorSel.innerHTML = '';
        if (!avatars || avatars.length === 0) {
          creatorSel.innerHTML = '<option value="">(無虛擬人像，請先至 AI 虛擬主播 分頁建立)</option>';
        } else {
          avatars.forEach(av => {
            const opt = document.createElement('option');
            opt.value = av.name;
            opt.textContent = `${av.display_name || av.name}${av.is_default ? ' ★ (Default)' : ''} [${av.provider || 'latentsync'}]`;
            if (av.is_default) opt.selected = true;
            creatorSel.appendChild(opt);
          });
        }
      }

      const studioSel = document.getElementById('studio-batch-avatar-select');
      if (studioSel) {
        studioSel.innerHTML = '';
        if (avatars && avatars.length > 0) {
          avatars.forEach(av => {
            const opt = document.createElement('option');
            opt.value = av.name;
            opt.textContent = `${av.display_name || av.name}${av.is_default ? ' ★' : ''}`;
            if (av.is_default) opt.selected = true;
            studioSel.appendChild(opt);
          });
        }
      }
    }

    async function applyBatchPresenterPlacement() {
      if (!currentProjectId) {
        alert("請先選擇或建立專案 (No active project selected)");
        return;
      }
      const placementSel = document.getElementById('studio-batch-placement-select');
      const placement = placementSel ? placementSel.value : 'intro_middle_outro';
      const avatarSel = document.getElementById('studio-batch-avatar-select');
      const avatar = avatarSel ? avatarSel.value : null;

      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/apply_presenter_placement`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ placement: placement, avatar_profile: avatar })
        });


        const scList = data.presenter_scene_ids && data.presenter_scene_ids.length > 0 ? `第 ${data.presenter_scene_ids.join(', ')} 幕` : '無';
        showToast(`✅ 已成功套用真人主播配置！出鏡幕次：${scList} (共 ${data.presenter_scenes_count} 幕)`);
        if (typeof loadStudioStage === 'function') {
          loadStudioStage(activeStudioStage || 'scenes');
        }
      } catch (e) {
        alert("套用真人主播配置失敗: " + e.message);
      }
    }

    async function toggleScenePresenterMode(sceneId, isChecked) {
      if (!currentProjectId) return;
      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/scenes/${sceneId}/toggle_presenter`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_presenter: isChecked })
        });


        showToast(`Scene #${sceneId} 虛擬主播出鏡模式: ${data.is_presenter ? '已啟用 🎭' : '已關閉'}`);
        if (typeof activeStudioStage !== 'undefined' && activeStudioStage === 'scenes') {
          // Keep local state in sync
          if (studioStageData && studioStageData.scenes) {
            const sc = studioStageData.scenes.find(s => s.scene_id === sceneId);
            if (sc) {
              sc.is_presenter = data.is_presenter;
              sc.visual_type = data.visual_type;
            }
          }
        }
      } catch (e) {
        alert("Error updating presenter mode: " + e.message);
      }
    }

    async function loadMusicTracks() {
      try {
        const d = await apiJson('/api/music/tracks');


        cachedMusicTracks = d.tracks || [];
        cachedMusicCategories = d.categories || {};

        // 1. Update music selector in creator form
        updateCreatorMusicSelect();

        // 2. Update music selector in project mixer card
        const projSel = document.getElementById('project-music-track-select');
        if (projSel) {
          const curProjVal = projSel.value || 'auto';
          projSel.innerHTML = buildCategorizedSelectOptions(cachedMusicTracks, curProjVal);
          if (Array.from(projSel.options).some(o => o.value === curProjVal)) {
            projSel.value = curProjVal;
          }
        }

        // 3. Render category filter pills & tracks list in tab-music
        renderMusicCategoryPills();
        renderMusicTracksList();

        // 4. Sync active project setting if project loaded
        if (currentProjectId) {
          syncActiveProjectMusicSetting();
        }
      } catch (e) {
        console.error("Error loading music tracks:", e);
      }
    }

    function setMusicCategoryFilter(catKey) {
      activeMusicCategory = catKey;
      renderMusicCategoryPills();
      renderMusicTracksList();
    }

    function renderMusicCategoryPills() {
      const pillsContainer = document.getElementById('music-category-pills');
      if (!pillsContainer) return;

      const orderedCats = ['all', 'tech_futuristic', 'cinematic_documentary', 'mystery_cosmic', 'calm_focus', 'dramatic_tension', 'uplifting_inspirational', 'custom'];
      let html = '';

      orderedCats.forEach(catKey => {
        let count = 0;
        let label = '';
        let icon = '';

        if (catKey === 'all') {
          count = cachedMusicTracks.length;
          label = 'All Types';
          icon = '🎵';
        } else {
          count = cachedMusicTracks.filter(t => (t.category || '').toLowerCase() === catKey).length;
          if (count === 0 && catKey === 'custom') return; // hide custom if empty
          const meta = getMusicCategoryMeta(catKey);
          label = meta.label;
          icon = meta.icon;
        }

        const isActive = activeMusicCategory === catKey;
        const meta = catKey === 'all' ? { bg: '#1e3a8a', color: '#93c5fd', border: '#3b82f6' } : getMusicCategoryMeta(catKey);

        const pillStyle = isActive
          ? `background: ${meta.bg}; color: ${meta.color}; border: 1px solid ${meta.border}; font-weight: 700; box-shadow: 0 0 10px rgba(0,0,0,0.4);`
          : `background: #0b1120; color: #94a3b8; border: 1px solid var(--card-border); font-weight: 500;`;

        html += `
          <button type="button" onclick="setMusicCategoryFilter('${catKey}')"
            style="padding: 6px 14px; border-radius: 20px; font-size: 12px; cursor: pointer; transition: all 0.15s ease; display: inline-flex; align-items: center; gap: 6px; ${pillStyle}">
            <span>${icon}</span>
            <span>${label}</span>
            <span style="background: rgba(255,255,255,0.12); padding: 1px 6px; border-radius: 10px; font-size: 11px;">${count}</span>
          </button>
        `;
      });

      pillsContainer.innerHTML = html;
    }

    function renderMusicTracksList() {
      const listEl = document.getElementById('music-tracks-list');
      if (!listEl) return;

      let filtered = cachedMusicTracks;
      if (activeMusicCategory && activeMusicCategory !== 'all') {
        filtered = cachedMusicTracks.filter(t => (t.category || '').toLowerCase() === activeMusicCategory);
      }

      if (!filtered.length) {
        listEl.innerHTML = `
          <div style="background: #080d16; border: 1px dashed var(--card-border); padding: 30px; text-align: center; border-radius: var(--radius); color: var(--text-muted); font-size: 13px;">
            No tracks found in category "<b>${activeMusicCategory}</b>". Upload a track or switch categories.
          </div>
        `;
        return;
      }

      let html = '<div style="display:flex; flex-direction:column; gap:10px;">';
      filtered.forEach(t => {
        const meta = getMusicCategoryMeta(t.category);
        html += `
          <div style="background: #080d16; border: 1px solid var(--card-border); padding: 14px 18px; border-radius: var(--radius); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px; transition: border-color 0.15s ease;">
            <div style="display: flex; align-items: flex-start; gap: 14px; flex: 1; min-width: 280px;">
              <div style="font-size: 28px; background: #0f172a; padding: 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06);">
                ${meta.icon}
              </div>
              <div style="flex: 1;">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 4px;">
                  <span style="font-weight: 700; font-size: 15px; color: #f8fafc;">${t.name}</span>
                  <span style="background: ${meta.bg}; color: ${meta.color}; border: 1px solid ${meta.border}; font-size: 11px; padding: 2px 8px; border-radius: 12px; font-weight: 600;">
                    ${meta.label}
                  </span>
                  ${t.is_voiceover_ready ? `
                    <span style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); font-size: 11px; padding: 2px 8px; border-radius: 12px; font-weight: 600;" title="TypeSafe Fitness Score: ${t.voiceover_fitness || 4.0}/5">
                      ✓ Safe for Voiceover (${t.voiceover_fitness || 4.0}/5)
                    </span>
                  ` : (t.speech_intrusive ? `
                    <span style="background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); font-size: 11px; padding: 2px 8px; border-radius: 12px; font-weight: 600;" title="TypeSafe Distraction Risk: ${t.distraction_prob || 0.7}">
                      ⚠️ Speech Intrusive (Vocal/Abrasive)
                    </span>
                  ` : '')}
                  ${t.mood ? `<span style="font-size: 11px; color: #94a3b8; background: #1e293b; padding: 2px 7px; border-radius: 6px;">${t.mood}</span>` : ''}
                </div>
                ${t.description ? `<div style="font-size: 12px; color: #94a3b8; line-height: 1.4; margin-bottom: 5px;">${t.description}</div>` : ''}
                <div style="font-size: 11px; color: var(--text-muted); font-family: monospace;">
                  📁 ${t.filename} • 💾 ${t.size_mb} MB • Royalty-Free Ambient (Loopable & Ducked)
                </div>
              </div>
            </div>

            <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
              <audio controls src="${t.url}" preload="none" style="height: 34px; width: 220px;"></audio>
              <button class="btn-sec" onclick="applyMusicToActiveProject('${t.filename}')" style="padding: 7px 14px; font-size: 12px; font-weight: 600; color: #93c5fd; border-color: #2563eb;" title="Apply this track to the active project">
                ✓ Use in Project
              </button>
              <button class="btn-sec btn-danger" onclick="deleteMusicTrack('${t.filename}')" style="padding: 7px 10px; font-size: 12px;" title="Delete this track">
                🗑️
              </button>
            </div>
          </div>
        `;
      });
      html += '</div>';
      listEl.innerHTML = html;
    }

        function onCreatorMusicCategoryChange(catKey) {
      const groupEl = document.getElementById('music-specific-track-group');
      const btnPreview = document.getElementById('btn-preview-music');
      const btnShuffle = document.getElementById('btn-shuffle-music');
      if (currentPreviewAudio && !currentPreviewAudio.paused) {
        currentPreviewAudio.pause();
        currentPreviewAudio = null;
        if (btnPreview) btnPreview.textContent = '▶ 試聽';
      }
      if (catKey === 'none') {
        if (groupEl) groupEl.style.display = 'none';
        const stMusic = document.getElementById('model-stage-music');
        if (stMusic && stMusic.value !== 'none') {
          stMusic.value = 'none';
          onStageModelChange('music');
        }
        return;
      }
      if (groupEl) groupEl.style.display = 'block';
      const stMusic = document.getElementById('model-stage-music');
      const progEl = document.getElementById('music-progression-select');
      if (stMusic) {
        const pVal = progEl ? progEl.value : 'narrative_evolving';
        if (stMusic.value !== pVal) {
          stMusic.value = pVal;
          onStageModelChange('music');
        }
      }
      updateCreatorMusicSelect(catKey);
    }

    function updateCreatorMusicSelect(selectedCat = null) {
      const sel = document.getElementById('music-select');
      if (!sel) return;
      const catKey = selectedCat || (document.getElementById('music-category-select')?.value || 'auto');
      let html = '';

      if (catKey === 'auto') {
        html += '<option value="auto" selected>✨ 🎯 依主題與章節智慧匹配輪播 (Smart Auto-Match)</option>';
        // Include optgroups for all categories so user can still see everything
        const orderedCats = ['tech_futuristic', 'cinematic_documentary', 'dramatic_tension', 'mystery_cosmic', 'uplifting_inspirational', 'calm_focus', 'custom'];
        orderedCats.forEach(ck => {
          const catTracks = cachedMusicTracks.filter(t => (t.category || '').toLowerCase() === ck);
          if (catTracks.length > 0) {
            const meta = getMusicCategoryMeta(ck);
            html += `<optgroup label="${meta.icon} ${meta.label} (${catTracks.length})">`;
            html += `<option value="${ck}">🎲 隨機挑選 ${meta.label}</option>`;
            catTracks.forEach(t => {
              html += `<option value="${t.filename}">${t.name} — ${t.mood || meta.label} (${t.size_mb} MB)</option>`;
            });
            html += `</optgroup>`;
          }
        });
      } else if (catKey === 'custom') {
        html += '<option value="auto">🎲 在所有原聲中隨機 (Random All)</option>';
        cachedMusicTracks.forEach(t => {
          html += `<option value="${t.filename}">${t.name} [${t.category}] (${t.size_mb} MB)</option>`;
        });
      } else {
        const meta = getMusicCategoryMeta(catKey);
        const catTracks = cachedMusicTracks.filter(t => (t.category || '').toLowerCase() === catKey);
        html += `<option value="${catKey}" selected>🎲 隨機挑選 ${meta.label} (${catTracks.length} 首輪播)</option>`;
        catTracks.forEach(t => {
          html += `<option value="${t.filename}">${t.name} — ${t.mood || meta.label} (${t.size_mb} MB)</option>`;
        });
      }

      sel.innerHTML = html;
    }

    function shuffleCreatorTrack() {
      const catEl = document.getElementById('music-category-select');
      const catKey = catEl ? catEl.value : 'auto';
      if (catKey === 'none') return;

      let pool = cachedMusicTracks;
      if (catKey !== 'auto' && catKey !== 'custom') {
        pool = cachedMusicTracks.filter(t => (t.category || '').toLowerCase() === catKey);
      }
      if (!pool.length) return;

      const randomTrack = pool[Math.floor(Math.random() * pool.length)];
      const sel = document.getElementById('music-select');
      if (sel) {
        // Ensure option exists or select it
        let found = Array.from(sel.options).find(o => o.value === randomTrack.filename);
        if (!found) {
          const opt = document.createElement('option');
          opt.value = randomTrack.filename;
          opt.textContent = `${randomTrack.name} (${randomTrack.size_mb} MB)`;
          sel.appendChild(opt);
        }
        sel.value = randomTrack.filename;
        if (typeof showToast === 'function') {
          showToast(`🎲 已隨機挑選: ${randomTrack.name} (${randomTrack.category})`);
        }
        // Auto play preview sample
        playAmbientPreview(`/api/music/audio/${randomTrack.filename}`, 'btn-preview-music');
      }
    }

    function onCreatorTrackChange(val) {
      if (currentPreviewAudio && !currentPreviewAudio.paused && val && val !== 'auto' && val !== 'none') {
        playAmbientPreview(`/api/music/audio/${val}`, 'btn-preview-music');
      }
    }
    function previewCreatorMusic() {
      const catEl = document.getElementById('music-category-select');
      const catVal = catEl ? catEl.value : 'auto';
      if (catVal === 'none') {
        alert("目前配樂設為「無背景音樂」，請先選擇氛圍風格或曲目！");
        return;
      }
      const sel = document.getElementById('music-select');
      let trackVal = sel ? sel.value : 'auto';

      let filename = trackVal;
      if (!trackVal || trackVal === 'auto' || trackVal in MUSIC_CAT_META) {
        const targetCat = (trackVal in MUSIC_CAT_META) ? trackVal : ((catVal in MUSIC_CAT_META) ? catVal : 'tech_futuristic');
        const subset = cachedMusicTracks.filter(t => t.category === targetCat);
        filename = subset.length ? subset[0].filename : (cachedMusicTracks.length ? cachedMusicTracks[0].filename : 'tech_futuristic/Deliberate_Thought.mp3');
      }
      playAmbientPreview(`/api/music/audio/${filename}`, 'btn-preview-music');
    }

    function previewProjectMusic(trackVal) {
      if (!trackVal || trackVal === 'none') return;
      let filename = trackVal;
      if (trackVal === 'auto' || trackVal in MUSIC_CAT_META) {
        const subset = trackVal in MUSIC_CAT_META ? cachedMusicTracks.filter(t => t.category === trackVal) : cachedMusicTracks;
        filename = subset.length ? subset[0].filename : 'tech_futuristic/Deliberate_Thought.mp3';
      }
      playAmbientPreview(`/api/music/audio/${filename}`, null);
    }

    function playAmbientPreview(audioUrl, btnId) {
      const btn = btnId ? document.getElementById(btnId) : null;
      if (currentPreviewAudio && !currentPreviewAudio.paused) {
        currentPreviewAudio.pause();
        currentPreviewAudio = null;
        if (btn) btn.textContent = '▶ Preview';
        return;
      }
      if (currentPreviewAudio) {
        currentPreviewAudio.pause();
      }
      currentPreviewAudio = new Audio(audioUrl);
      currentPreviewAudio.volume = 0.5;
      currentPreviewAudio.play();
      if (btn) {
        btn.textContent = '⏹ Stop';
        currentPreviewAudio.onended = () => { btn.textContent = '▶ Preview'; };
      }
    }

    let pendingMusicFiles = [];

    function onMusicFileInputChange(inputEl) {
      if (inputEl.files && inputEl.files.length) {
        pendingMusicFiles = Array.from(inputEl.files);
        updateSelectedMusicCount();
      }
    }

    function updateSelectedMusicCount() {
      const countEl = document.getElementById('music-selected-count');
      if (countEl) {
        if (!pendingMusicFiles.length) {
          countEl.textContent = "未選取檔案";
        } else {
          countEl.textContent = `已選取 ${pendingMusicFiles.length} 個音訊檔案 (準備上傳)`;
        }
      }
    }

    function onMusicDropZoneOver(e) {
      e.preventDefault();
      e.stopPropagation();
      const dz = document.getElementById('music-dropzone');
      if (dz) {
        dz.style.borderColor = '#3b82f6';
        dz.style.background = 'rgba(59, 130, 246, 0.15)';
      }
    }

    function onMusicDropZoneLeave(e) {
      e.preventDefault();
      e.stopPropagation();
      const dz = document.getElementById('music-dropzone');
      if (dz) {
        dz.style.borderColor = 'rgba(59, 130, 246, 0.45)';
        dz.style.background = 'rgba(15, 23, 42, 0.6)';
      }
    }

    function onMusicDropZoneDrop(e) {
      e.preventDefault();
      e.stopPropagation();
      onMusicDropZoneLeave(e);
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
        const audioFiles = Array.from(e.dataTransfer.files).filter(f => {
          const ext = f.name.toLowerCase().split('.').pop();
          return ['mp3', 'wav', 'm4a', 'ogg', 'flac', 'aac'].includes(ext);
        });
        if (!audioFiles.length) {
          return alert("請拖入有效的音訊檔案 (.mp3, .wav, .m4a, .ogg, .flac)！");
        }
        pendingMusicFiles = audioFiles;
        updateSelectedMusicCount();
        if (typeof showToast === 'function') {
          showToast(`已就緒 ${audioFiles.length} 個音訊檔案，請點擊「🚀 批次上傳音樂」`);
        }
      }
    }

    async function uploadMusicFile() {
      const fileInput = document.getElementById('music-upload-file');
      const catSelect = document.getElementById('music-upload-category');
      const statusEl = document.getElementById('music-upload-status');
      const btn = document.getElementById('btn-upload-music');

      const filesToUpload = pendingMusicFiles.length ? pendingMusicFiles : (fileInput && fileInput.files.length ? Array.from(fileInput.files) : []);

      if (!filesToUpload.length) {
        return alert("請先點擊選取或拖入音訊檔案 (.mp3, .wav, .m4a 等)。");
      }

      const formData = new FormData();
      filesToUpload.forEach(f => {
        formData.append('files', f);
      });
      if (catSelect && catSelect.value) {
        formData.append('category', catSelect.value);
      }

      if (btn) btn.disabled = true;
      if (statusEl) statusEl.textContent = `⏳ 正在批次上傳 ${filesToUpload.length} 首音軌並自動同步至 Catalog...`;

      try {
        const data = await apiJson('/api/music/upload-multiple', {
          method: 'POST',
          body: formData
        });


          if (statusEl) {
            statusEl.innerHTML = `<span style="color: #34d399; font-weight: 700;">✓ 成功上傳 ${data.count || filesToUpload.length} 首音軌！已自動完成分類與 Catalog 標籤登錄。</span>`;
          }
          if (typeof showToast === 'function') {
            showToast(`✓ 成功批次匯入 ${data.count || filesToUpload.length} 首背景配樂！`);
          }
          pendingMusicFiles = [];
          if (fileInput) fileInput.value = '';
          updateSelectedMusicCount();
          await loadMusicTracks();

      } catch (e) {
        if (statusEl) statusEl.textContent = `上傳發生錯誤: ${e.message}`;
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function triggerTypeSafeGrading() {
      const btn = document.getElementById('btn-grade-typesafe');
      if (!confirm("Run TypeSafe AI System One (Jev) to grade and filter all tracks in your inventory for voiceover suitability?")) {
        return;
      }
      try {
        if (btn) {
          btn.disabled = true;
          btn.textContent = "⏳ Grading Inventory...";
        }
        const data = await apiJson('/api/music/grade-inventory', { method: 'POST' });



        // Poll progress
        const interval = setInterval(async () => {
          try {
            const st = await apiJson('/api/music/grade-status');

            if (st.running) {
              if (btn) btn.textContent = `⏳ Grading [${st.progress}/${st.total || 89}]...`;
            } else {
              clearInterval(interval);
              if (btn) {
                btn.disabled = false;
                btn.textContent = "✨ Grade with TypeSafe AI (Jev)";
              }
              if (st.error) {
                alert("Grading finished with error: " + st.error);
              } else {
                alert(`Grading Complete! Total: ${st.result ? st.result.total : 0}, Voiceover Ready: ${st.result ? st.result.passed : 0}, Speech Intrusive: ${st.result ? st.result.failed : 0}`);
              }
              await loadMusicTracks();
            }
          } catch (pollErr) {
            console.error("Polling error:", pollErr);
          }
        }, 1500);
      } catch (err) {
        alert("Error starting TypeSafe grading: " + err.message);
        if (btn) { btn.disabled = false; btn.textContent = "✨ Grade with TypeSafe AI (Jev)"; }
      }
    }

    async function deleteMusicTrack(filename) {
      if (!confirm(`Delete music track "${filename}"?`)) return;
      try {
        const encodedPath = filename.split('/').map(encodeURIComponent).join('/');
        await apiRequest(`/api/music/tracks/${encodedPath}`, {
          method: 'DELETE'
        })

          await loadMusicTracks();

      } catch (e) {
        alert("Failed to delete track: " + e.message);
      }
    }

    async function applyMusicToActiveProject(filename) {
      if (typeof studioTargetMovementIdx === 'number' && studioTargetMovementIdx !== null) {
        const segIdx = studioTargetMovementIdx;
        studioTargetMovementIdx = null;
        if (studioStageData && studioStageData.music_plan && studioStageData.music_plan[segIdx]) {
          const seg = studioStageData.music_plan[segIdx];
          const matched = cachedMusicTracks.find(t => t.filename === filename);
          seg.track = filename;
          seg.name = filename.split(/[\/\\]/).pop();
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
    }

    async function syncActiveProjectMusicSetting() {
      if (!currentProjectId) return;
      try {
        const d = await apiJson(`/api/projects/${currentProjectId}`);


        const p = d.project;
        if (p && p.settings && p.settings.music) {
          const m = p.settings.music;
          const trkSel = document.getElementById('project-music-track-select');
          if (trkSel && m.track) trkSel.value = m.track;
          const volSel = document.getElementById('project-music-volume-select');
          if (volSel && m.volume_db !== undefined) volSel.value = String(m.volume_db);
        }
      } catch (_) {}
    }

    async function saveActiveProjectMusic() {
      if (!currentProjectId) return alert("Please select an active project first.");
      const trkSel = document.getElementById('project-music-track-select');
      const volSel = document.getElementById('project-music-volume-select');
      const statusEl = document.getElementById('project-music-save-status');

      const track = trkSel ? trkSel.value : 'auto';
      const volume = volSel ? parseFloat(volSel.value) : -24.0;

      try {
        await apiRequest(`/api/projects/${currentProjectId}/music`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ track: track, volume_db: volume })
        })

          if (statusEl) {
            statusEl.textContent = "✓ Settings saved!";
            setTimeout(() => { statusEl.textContent = ""; }, 3000);
          }
          pollProject();

      } catch (e) {
        alert("Failed to save music settings: " + e.message);
      }
    }

    async function saveAndRerenderAudioMix() {
      if (!currentProjectId) return alert("Please select an active project first.");
      await saveActiveProjectMusic();
      if (!confirm("Re-render 1080p video with the updated ambient background music now?")) return;
      try {
        await apiRequest(`/api/projects/${currentProjectId}/run_stage/render`, {
          method: 'POST'
        })

          switchTab('preview');
          pollProject();

      } catch (e) {
        alert("Failed to trigger re-render: " + e.message);
      }
    }

    const KEY_ELEMENT_MAP = {
      'GEMINI_API_KEY': 'set-gemini-key',
      'OPENAI_API_KEY': 'set-openai-key',
      'FAL_KEY': 'set-fal-key',
      'ELEVENLABS_API_KEY': 'set-elevenlabs-key',
      'VOAI_API_KEY': 'set-voai-key',
      'KLING_API_KEY': 'set-kling-key',
      'RUNWAY_API_KEY': 'set-runway-key',
      'HEDRA_API_KEY': 'set-hedra-key',
      'MINIMAX_API_KEY': 'set-minimax-key',
      'PEXELS_API_KEY': 'set-pexels-key',
      'PIXABAY_API_KEY': 'set-pixabay-key',
      'TYPESAFE_API_KEY': 'set-typesafe-key'
    };

    async function saveApiKeys() {
      const secrets = {};
      const gemini = document.getElementById('set-gemini-key').value.trim();
      const openai = document.getElementById('set-openai-key').value.trim();
      const fal = document.getElementById('set-fal-key') ? document.getElementById('set-fal-key').value.trim() : '';
      const elevenlabs = document.getElementById('set-elevenlabs-key').value.trim();
      const voai = document.getElementById('set-voai-key') ? document.getElementById('set-voai-key').value.trim() : '';
      const kling = document.getElementById('set-kling-key').value.trim();
      const runway = document.getElementById('set-runway-key').value.trim();
      const hedra = document.getElementById('set-hedra-key') ? document.getElementById('set-hedra-key').value.trim() : '';
      const minimax = document.getElementById('set-minimax-key') ? document.getElementById('set-minimax-key').value.trim() : '';
      const pexels = document.getElementById('set-pexels-key') ? document.getElementById('set-pexels-key').value.trim() : '';
      const pixabay = document.getElementById('set-pixabay-key') ? document.getElementById('set-pixabay-key').value.trim() : '';
      const typesafe = document.getElementById('set-typesafe-key') ? document.getElementById('set-typesafe-key').value.trim() : '';
      if (gemini) secrets.GEMINI_API_KEY = gemini;
      if (openai) secrets.OPENAI_API_KEY = openai;
      if (fal) secrets.FAL_KEY = fal;
      if (elevenlabs) secrets.ELEVENLABS_API_KEY = elevenlabs;
      if (voai) secrets.VOAI_API_KEY = voai;
      if (kling) secrets.KLING_API_KEY = kling;
      if (runway) secrets.RUNWAY_API_KEY = runway;
      if (hedra) secrets.HEDRA_API_KEY = hedra;
      if (minimax) secrets.MINIMAX_API_KEY = minimax;
      if (pexels) secrets.PEXELS_API_KEY = pexels;
      if (pixabay) secrets.PIXABAY_API_KEY = pixabay;
      if (typesafe) secrets.TYPESAFE_API_KEY = typesafe;

      if (Object.keys(secrets).length === 0) {
        alert("No new API keys entered to save. Enter a key in any field to update and test it.");
        return;
      }

      // Update button & indicate verification is starting
      const saveButtons = document.querySelectorAll("button[onclick*='saveApiKeys']");
      saveButtons.forEach(btn => {
        btn.disabled = true;
        btn.dataset.origText = btn.textContent;
        btn.textContent = '⏳ Testing & Verifying Keys...';
      });

      for (const k of Object.keys(secrets)) {
        const elId = KEY_ELEMENT_MAP[k];
        const statusEl = document.getElementById(elId + '-status');
        if (statusEl) {
          statusEl.innerHTML = '<span style="color:#38bdf8; font-weight:600;">⏳ Testing & verifying key...</span>';
        }
      }

      try {
        const data = await apiJson('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ secrets: secrets })
        });

        const validation = data.validation || {};

        const failedList = [];
        const successList = [];

        for (const [k, v] of Object.entries(validation)) {
          const elId = KEY_ELEMENT_MAP[k];
          const statusEl = document.getElementById(elId + '-status');
          const inputEl = document.getElementById(elId);
          if (v.valid) {
            successList.push(`${k}: ${v.message}`);
            if (statusEl) {
              statusEl.innerHTML = `<span style="color:#34d399; font-weight:600;">✓ Valid: ${v.message}</span>`;
            }
            if (inputEl) {
              inputEl.style.borderColor = '#10b981';
              inputEl.value = '';
            }
          } else {
            failedList.push(`${k}: ${v.message}`);
            if (statusEl) {
              statusEl.innerHTML = `<span style="color:#ef4444; font-weight:600;">✗ Invalid: ${v.message}</span>`;
            }
            if (inputEl) {
              inputEl.style.borderColor = '#ef4444';
            }
          }
        }

        if (failedList.length > 0) {
          let msg = '⚠️ API Key Validation Failed:\n\n' + failedList.join('\n\n');
          if (successList.length > 0) {
            msg += '\n\n✓ Successfully verified:\n' + successList.join('\n');
          }
          alert(msg);
        } else if (successList.length > 0) {
          alert('✓ All ' + successList.length + ' updated API key(s) verified successfully!\n\n' + successList.join('\n'));
        } else {
          alert('Settings saved successfully!');
        }

        const preserveKeys = Object.keys(validation).filter(k => !validation[k].valid);
        await loadApiKeys(preserveKeys);
        loadElevenLabsVoices();
        loadVoAISpeakers();
      } catch (err) {
        alert("Error saving API keys: " + err);
      } finally {
        saveButtons.forEach(btn => {
          btn.disabled = false;
          btn.textContent = btn.dataset.origText || 'Save API Keys';
        });
      }
    }

    async function loadApiKeys(preserveErrorKeys = []) {
      try {
        const data = await apiJson('/api/settings');

        const sc = data.secrets_configured || {};

        const setField = (id, keyName) => {
          if (preserveErrorKeys && preserveErrorKeys.includes(keyName)) {
            return;
          }
          const el = document.getElementById(id);
          const statusEl = document.getElementById(id + '-status');
          if (el && sc[keyName]) {
            el.placeholder = "•••••••••••• (Configured - enter new to change)";
          }
          if (statusEl) {
            statusEl.innerHTML = sc[keyName]
              ? '<span style="color:#34d399; font-weight:600;">✓ Configured</span>'
              : '<span style="color:#94a3b8;">Not configured</span>';
          }
        };

        setField('set-gemini-key', 'GEMINI_API_KEY');
        setField('set-openai-key', 'OPENAI_API_KEY');
        setField('set-fal-key', 'FAL_KEY');
        setField('set-elevenlabs-key', 'ELEVENLABS_API_KEY');
        setField('set-voai-key', 'VOAI_API_KEY');
        setField('set-kling-key', 'KLING_API_KEY');
        setField('set-runway-key', 'RUNWAY_API_KEY');
        setField('set-hedra-key', 'HEDRA_API_KEY');
        setField('set-minimax-key', 'MINIMAX_API_KEY');
        setField('set-pexels-key', 'PEXELS_API_KEY');
        setField('set-pixabay-key', 'PIXABAY_API_KEY');
        setField('set-typesafe-key', 'TYPESAFE_API_KEY');

        if (data.settings && data.settings.subtitles) {
          const sub = data.settings.subtitles;
          const isEnabled = sub.motion_graphics_callouts !== false && sub.callouts_enabled !== false;
          updateMotionCalloutsSwitchUI('set-motion-callouts', isEnabled);
          const sf = document.getElementById('set-sub-font');
          if (sf && sub.font) sf.value = sub.font;
          const ss = document.getElementById('set-sub-style');
          if (ss && sub.style) ss.value = sub.style;
          const scs = document.getElementById('set-callout-banner-style');
          if (scs && sub.callout_style) scs.value = sub.callout_style;
          const ccs = document.getElementById('creator-callout-style');
          if (ccs && sub.callout_style) ccs.value = sub.callout_style;
        }

        if (data.settings && data.settings.rendering && data.settings.rendering.phase_turn_duration) {
          const pt = document.getElementById('set-phase-turn-dur');
          if (pt) pt.value = data.settings.rendering.phase_turn_duration;
        }

        if (data.settings && data.settings.remotion) {
          populateRemotionSettingsUI(data.settings.remotion);
        }

        if (data.settings) {
          populateDefaultThumbnailSettingsUI(data.settings.thumbnail || {});
        }
        if (data.settings && data.settings.hook) {
          const hk = data.settings.hook;
          const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el && val !== undefined && val !== null) el.value = String(val);
          };
          setVal('set-hook-enabled', hk.enabled !== false);
          setVal('set-hook-video-dur', hk.video_duration || 300);
          setVal('set-hook-dur', hk.duration || 12);
          setVal('set-hook-mode', hk.mode || 'select_core_conflict');
          setVal('set-hook-claim-dur', hk.claim_window_seconds || 5.0);
          setVal('set-hook-avoid-repeat', hk.avoid_repeated_narration !== false);
        }
      } catch (e) {
        console.error("Failed to load settings secrets", e);
      }
    }

    function updateMotionCalloutsSwitchUI(prefix, enabled) {
      const cb = document.getElementById(prefix);
      if (cb) cb.checked = enabled;
      const slider = document.getElementById(prefix + '-slider');
      if (slider) slider.style.backgroundColor = enabled ? '#0284c7' : '#334155';
      const knob = document.getElementById(prefix + '-knob');
      if (knob) {
        const isLarge = prefix === 'studio-motion-callouts';
        knob.style.left = enabled ? (isLarge ? '23px' : '23px') : '3px';
      }
    }

    async function refreshBlueMagpieBadge(badgeId, autoStart = true) {
      const el = document.getElementById(badgeId);
      if (!el) return;
      try {
        const h = await apiJson('http://127.0.0.1:8008/health');


          const devLabel = h.gpu_name ? `${h.device} — ${h.gpu_name}` : (h.device || 'cuda');
          if (h.loaded === false || h.status === 'loading') {
            el.innerHTML = `<span style="color:#f59e0b;">🟡 Loading model into GPU (${devLabel})...</span>`;
            setTimeout(() => refreshBlueMagpieBadge(badgeId, false), 3000);
            return;
          }
          el.innerHTML = `<b style="color:#34d399;">🟢 Online (${devLabel})</b>`;
          return;

      } catch (_) {}

      if (autoStart) {
        el.innerHTML = `<span style="color:#f59e0b;">⏳ Starting BlueMagpie server on Port 8008...</span>`;
        try {
          const sd = await apiJson('/api/tts/bluemagpie_status?auto_start=true');


            if (sd.online) {
              const devLabel = sd.gpu_name ? `${sd.device} — ${sd.gpu_name}` : (sd.device || 'cuda');
              if (sd.loaded === false || sd.status === 'loading') {
                el.innerHTML = `<span style="color:#f59e0b;">🟡 Loading model into GPU (${devLabel})...</span>`;
                setTimeout(() => refreshBlueMagpieBadge(badgeId, false), 3000);
                return;
              }
              el.innerHTML = `<b style="color:#34d399;">🟢 Online (${devLabel})</b>`;
              return;
            }

        } catch (_) {}
      }

      el.innerHTML = `<b style="color:#ef4444;">🔴 Offline (Port 8008 unreachable)</b> <button class="btn-sec" style="padding:2px 8px; font-size:11px; margin-left:6px;" onclick="refreshBlueMagpieBadge('${badgeId}', true)">🔄 Start / Retry</button>`;
    }

    async function saveSubtitleGlobalSettings() {
      const motion = document.getElementById('set-motion-callouts') ? document.getElementById('set-motion-callouts').checked : true;
      const font = document.getElementById('set-sub-font') ? document.getElementById('set-sub-font').value : 'Microsoft JhengHei UI';
      const style = document.getElementById('set-sub-style') ? document.getElementById('set-sub-style').value : 'youtube_standard';
      const phaseTurnDur = document.getElementById('set-phase-turn-dur') ? parseFloat(document.getElementById('set-phase-turn-dur').value) || 3.0 : 3.0;
      const calloutBannerStyle = document.getElementById('set-callout-banner-style') ? document.getElementById('set-callout-banner-style').value : 'fox_kinetic';
      const ccs = document.getElementById('creator-callout-style');
      if (ccs) ccs.value = calloutBannerStyle;
      try {
        await apiRequest('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            settings: {
              subtitles: {
                motion_graphics_callouts: motion,
                callouts_enabled: motion,
                font: font,
                style: style,
                callout_style: calloutBannerStyle
              },
              rendering: {
                phase_turn_duration: phaseTurnDur
              }
            }
          })
        });
        alert("Subtitle & Motion Graphic settings saved successfully!");
      } catch(e) {
        alert("Failed to save settings: " + e.message);
      }
    }

    function populateRemotionSettingsUI(remCfg = {}) {
      if (!remCfg) remCfg = {};
      const styleEl = document.getElementById('set-remotion-style');
      const themeEl = document.getElementById('set-remotion-theme');
      const densityEl = document.getElementById('set-remotion-density');
      const pickerEl = document.getElementById('set-remotion-accent-picker');
      const hexEl = document.getElementById('set-remotion-accent-hex');

      if (styleEl && remCfg.style) styleEl.value = remCfg.style;
      if (themeEl && remCfg.theme) themeEl.value = remCfg.theme;
      if (densityEl && remCfg.density) densityEl.value = remCfg.density;

      const accent = remCfg.accentColor || '#A855F7';
      if (pickerEl) pickerEl.value = accent;
      if (hexEl) hexEl.value = accent;

      if (remCfg.default_style) {
        selectRemotionGlobalStyle(remCfg.default_style);
      }

      updateRemotionSettingsLivePreview();
    }

    function onRemotionSettingsChange() {
      updateRemotionSettingsLivePreview();
    }

    function onRemotionAccentColorChange(hex) {
      const hexEl = document.getElementById('set-remotion-accent-hex');
      if (hexEl) hexEl.value = (hex || '').toUpperCase();
      updateRemotionSettingsLivePreview();
    }

    function onRemotionAccentHexInput(val) {
      let hex = (val || '').trim();
      if (!hex.startsWith('#')) hex = '#' + hex;
      if (/^#[0-9A-Fa-f]{6}$/.test(hex)) {
        const pickerEl = document.getElementById('set-remotion-accent-picker');
        if (pickerEl) pickerEl.value = hex;
      }
      updateRemotionSettingsLivePreview();
    }

    function setRemotionAccentColor(hex) {
      const pickerEl = document.getElementById('set-remotion-accent-picker');
      const hexEl = document.getElementById('set-remotion-accent-hex');
      if (pickerEl) pickerEl.value = hex;
      if (hexEl) hexEl.value = hex.toUpperCase();
      updateRemotionSettingsLivePreview();
    }

    function applyRemotionPresetInSettings(presetName) {
      const styleEl = document.getElementById('set-remotion-style');
      const themeEl = document.getElementById('set-remotion-theme');
      const densityEl = document.getElementById('set-remotion-density');

      if (presetName === 'gary_chen' || presetName === 'modern_tech_explainer') {
        if (styleEl) styleEl.value = 'modern_tech_explainer';
        if (themeEl) themeEl.value = 'dark_obsidian';
        if (densityEl) densityEl.value = 'full';
        setRemotionAccentColor('#A855F7');
      } else if (presetName === 'blueprint' || presetName === 'tactile_blueprint') {
        if (styleEl) styleEl.value = 'tactile_blueprint';
        if (themeEl) themeEl.value = 'blueprint_grid';
        if (densityEl) densityEl.value = 'full';
        setRemotionAccentColor('#00F5FF');
      } else if (presetName === 'coordinate_zero') {
        if (styleEl) styleEl.value = 'coordinate_zero';
        if (themeEl) themeEl.value = 'green_cutting_mat';
        if (densityEl) densityEl.value = 'full';
        setRemotionAccentColor('#0D9488');
      } else if (presetName === 'fox_documentary') {
        if (styleEl) styleEl.value = 'fox_documentary';
        if (themeEl) themeEl.value = 'translucent_overlay';
        if (densityEl) densityEl.value = 'rich';
        setRemotionAccentColor('#38BDF8');
      } else if (presetName === 'finance_market') {
        if (styleEl) styleEl.value = 'finance_market';
        if (themeEl) themeEl.value = 'finance_grid';
        if (densityEl) densityEl.value = 'full';
        setRemotionAccentColor('#10B981');
      } else if (presetName === 'archival_history') {
        if (styleEl) styleEl.value = 'archival_history';
        if (themeEl) themeEl.value = 'parchment_paper';
        if (densityEl) densityEl.value = 'full';
        setRemotionAccentColor('#C2410C');
      } else if (presetName === 'vox_journalism') {
        if (styleEl) styleEl.value = 'vox_journalism';
        if (themeEl) themeEl.value = 'vox_charcoal';
        if (densityEl) densityEl.value = 'full';
        setRemotionAccentColor('#FACC15');
      }
      const stageAnimEl = document.getElementById('model-stage-animation');
      if (stageAnimEl) {
        if (presetName === 'coordinate_zero') stageAnimEl.value = 'remotion_coordinate_scale';
        else if (presetName === 'finance_market') stageAnimEl.value = 'remotion_finance_candlestick';
        else if (presetName === 'archival_history') stageAnimEl.value = 'remotion_archival_doc';
        else if (presetName === 'vox_journalism') stageAnimEl.value = 'remotion_vox_split';
        else if (presetName === 'fox_documentary') stageAnimEl.value = 'remotion';
        else stageAnimEl.value = 'remotion';
        onStageModelChange('animation');
      }
      updateRemotionSettingsLivePreview();
    }

    function updateRemotionSettingsLivePreview() {
      const styleEl = document.getElementById('set-remotion-style');
      const themeEl = document.getElementById('set-remotion-theme');
      const densityEl = document.getElementById('set-remotion-density');
      const hexEl = document.getElementById('set-remotion-accent-hex');
      const previewPill = document.getElementById('set-remotion-accent-badge-preview');
      const jsonEl = document.getElementById('set-remotion-json-preview');

      const style = styleEl ? styleEl.value : 'modern_tech_explainer';
      const theme = themeEl ? themeEl.value : 'dark_obsidian';
      const density = densityEl ? densityEl.value : 'full';
      let accent = hexEl ? (hexEl.value || '#A855F7').trim() : '#A855F7';
      if (!accent.startsWith('#')) accent = '#' + accent;

      if (previewPill) {
        previewPill.style.color = accent;
        previewPill.style.borderColor = accent;
        previewPill.style.background = accent + '1f';
        previewPill.style.boxShadow = '0 0 10px ' + accent + '40';
      }

      // Highlight active showcase card
      const allStyles = ['modern_tech_explainer', 'coordinate_zero', 'tactile_blueprint', 'fox_documentary', 'finance_market', 'archival_history', 'vox_journalism'];
      allStyles.forEach(s => {
        const card = document.getElementById('showcase-card-' + s);
        if (card) {
          const isSelected = (style === s);
          let activeBorder = '#a855f7';
          if (s === 'coordinate_zero') activeBorder = '#0d9488';
          else if (s === 'tactile_blueprint') activeBorder = '#00F5FF';
          else if (s === 'fox_documentary') activeBorder = '#38bdf8';
          else if (s === 'finance_market') activeBorder = '#10B981';
          else if (s === 'archival_history') activeBorder = '#C2410C';
          else if (s === 'vox_journalism') activeBorder = '#FACC15';
          
          card.style.border = isSelected ? `2px solid ${activeBorder}` : '1px solid #1e293b';
          card.style.boxShadow = isSelected ? `0 0 16px ${activeBorder}40` : 'none';
        }
      });

      if (jsonEl) {
        const payload = {
          remotion: {
            style: style,
            theme: theme,
            density: density,
            accentColor: accent
          }
        };
        jsonEl.textContent = JSON.stringify(payload, null, 2);
      }
    }

    async function saveRemotionGlobalSettings() {
      const styleEl = document.getElementById('set-remotion-style');
      const themeEl = document.getElementById('set-remotion-theme');
      const densityEl = document.getElementById('set-remotion-density');
      const hexEl = document.getElementById('set-remotion-accent-hex');
      const syncBadge = document.getElementById('set-remotion-sync-badge');

      const style = styleEl ? styleEl.value : 'modern_tech_explainer';
      const theme = themeEl ? themeEl.value : 'dark_obsidian';
      const density = densityEl ? densityEl.value : 'full';
      let accent = hexEl ? (hexEl.value || '#A855F7').trim() : '#A855F7';
      if (!accent.startsWith('#')) accent = '#' + accent;

      const remotionConfig = {
        style: style,
        theme: theme,
        density: density,
        accentColor: accent,
        default_style: currentGlobalRemotionStyle || 'EvidenceHighlightScene'
      };

      try {
        if (syncBadge) {
          syncBadge.textContent = '⏳ 正在儲存...';
          syncBadge.style.color = '#fbbf24';
          syncBadge.style.borderColor = '#d97706';
        }

        await apiRequest('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            settings: {
              remotion: remotionConfig
            }
          })
        });

        if (currentProjectId) {
          await apiRequest('/api/projects/' + currentProjectId + '/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              remotion: remotionConfig
            })
          }).catch(e => console.warn('Could not sync current project settings:', e));
        }

        if (syncBadge) {
          syncBadge.textContent = '✓ 已同步 settings.yaml (已儲存)';
          syncBadge.style.color = '#34d399';
          syncBadge.style.borderColor = '#059669';
        }

        if (typeof showToast === 'function') {
          showToast('✨ Remotion 100% 視覺設定已成功儲存至 settings.yaml！');
        } else {
          alert('✨ Remotion 100% 視覺設定已成功儲存至 settings.yaml！');
        }
      } catch (err) {
        console.error('Failed to save Remotion settings:', err);
        if (syncBadge) {
          syncBadge.textContent = '✕ 儲存失敗';
          syncBadge.style.color = '#f87171';
          syncBadge.style.borderColor = '#ef4444';
        }
        alert('儲存 Remotion 設定失敗：' + err.message);
      }
    }

    window.populateRemotionSettingsUI = populateRemotionSettingsUI;
    window.onRemotionSettingsChange = onRemotionSettingsChange;
    window.onRemotionAccentColorChange = onRemotionAccentColorChange;
    window.onRemotionAccentHexInput = onRemotionAccentHexInput;
    window.setRemotionAccentColor = setRemotionAccentColor;
    
    function setCreatorRemotionDensity(density) {
      window.creatorRemotionDensity = density;
      const setEl = document.getElementById('set-remotion-density');
      if (setEl) setEl.value = density;

      const pill100 = document.getElementById('btn-density-full');
      const pill50 = document.getElementById('btn-density-half');
      if (pill100 && pill50) {
        if (density === 'half') {
          pill50.style.background = '#10b981';
          pill50.style.color = '#ffffff';
          pill50.style.borderColor = '#34d399';
          pill100.style.background = 'rgba(255,255,255,0.05)';
          pill100.style.color = '#94a3b8';
          pill100.style.borderColor = '#334155';
        } else {
          pill100.style.background = '#0ea5e9';
          pill100.style.color = '#ffffff';
          pill100.style.borderColor = '#38bdf8';
          pill50.style.background = 'rgba(255,255,255,0.05)';
          pill50.style.color = '#94a3b8';
          pill50.style.borderColor = '#334155';
        }
      }

      if (currentProjectId) {
        apiRequest(`/api/projects/${currentProjectId}/settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            animation: { motion_graphics_density: density },
            remotion: { density: density }
          })
        }).catch(e => console.error(e));
      }
      showToast(density === 'half' ? '✨ 已設定為：50% 實景圖片 + 50% Remotion 動態圖表！' : '✨ 已設定為：100% 全程 Remotion 動態圖表！');
    }
    window.setCreatorRemotionDensity = setCreatorRemotionDensity;

    window.applyRemotionPresetInSettings = applyRemotionPresetInSettings;
    window.applyFinanceMarketRemotionPreset = applyFinanceMarketRemotionPreset;
    window.applyArchivalHistoryRemotionPreset = applyArchivalHistoryRemotionPreset;
    window.applyVoxJournalismRemotionPreset = applyVoxJournalismRemotionPreset;
    window.applyCoordinateZeroRemotionPreset = applyCoordinateZeroRemotionPreset;
    window.applyGaryChenRemotionPreset = applyGaryChenRemotionPreset;
    window.apply100PercentRemotionPreset = apply100PercentRemotionPreset;
    window.updateRemotionSettingsLivePreview = updateRemotionSettingsLivePreview;
    window.saveRemotionGlobalSettings = saveRemotionGlobalSettings;

    let currentGlobalRemotionStyle = 'EvidenceHighlightScene';

    function selectRemotionGlobalStyle(styleName) {
      if (styleName === 'TechCard') styleName = 'FoxHeaderScene';
      else if (styleName === 'MinimalistCard') styleName = 'FoxMetricScene';
      else if (styleName === 'CinemaImpactCard') styleName = 'FoxDataListScene';

      currentGlobalRemotionStyle = styleName;
      const styles = {
        'FoxHeaderScene': { id: 'remotion-style-card-foxheader', badge: 'remotion-badge-foxheader', name: '📌 主題章節 (fOx Header)', color: '#F87171' },
        'FoxMetricScene': { id: 'remotion-style-card-foxmetric', badge: 'remotion-badge-foxmetric', name: '📊 核心數據 (fOx Metric)', color: '#38BDF8' },
        'FoxDataListScene': { id: 'remotion-style-card-foxdatalist', badge: 'remotion-badge-foxdatalist', name: '📋 規格清單 (fOx Data List)', color: '#38BDF8' },
        'FoxTimelineScene': { id: 'remotion-style-card-foxtimeline', badge: 'remotion-badge-foxtimeline', name: '⏱️ 時間演進 (fOx Timeline)', color: '#38BDF8' },
        'BranchPathwayScene': { id: 'remotion-style-card-branchpathway', badge: 'remotion-badge-branchpathway', name: '🔀 分支決策 (Branch Pathway)', color: '#00F5FF' },
        'LeaderCalloutScene': { id: 'remotion-style-card-leadercallout', badge: 'remotion-badge-leadercallout', name: '🎯 引線標註 (Leader Callout)', color: '#00F5FF' },
        'ScaleCompareScene': { id: 'remotion-style-card-scalecompare', badge: 'remotion-badge-scalecompare', name: '🔬 尺度對比 (Scale Loupe)', color: '#00F5FF' },
        'EvidenceHighlightScene': { id: 'remotion-style-card-evidencehighlight', badge: 'remotion-badge-evidencehighlight', name: '📑 文獻劃記 (Evidence Highlight)', color: '#00F5FF' }
      };

      Object.keys(styles).forEach(k => {
        const conf = styles[k];
        const card = document.getElementById(conf.id);
        const badge = document.getElementById(conf.badge);
        if (card) {
          if (k === styleName) {
            card.style.border = `2px solid ${conf.color}`;
            card.style.boxShadow = `0 0 15px ${conf.color}35`;
          } else {
            card.style.border = '1.5px solid #1e293b';
            card.style.boxShadow = 'none';
          }
        }
        if (badge) {
          badge.style.display = (k === styleName) ? 'inline-block' : 'none';
          badge.textContent = (k === styleName) ? '預設' : '';
        }
      });

      const label = document.getElementById('remotion-current-style-name');
      if (label && styles[styleName]) {
        label.textContent = styles[styleName].name;
        label.style.color = styles[styleName].color;
      }
    }

    function selectRemotionStudioStyle(compName) {
      if (compName === 'TechCard') compName = 'FoxHeaderScene';
      else if (compName === 'MinimalistCard') compName = 'FoxMetricScene';
      else if (compName === 'CinemaImpactCard') compName = 'FoxDataListScene';

      const sel = document.getElementById('remotion-style-select');
      if (sel) sel.value = compName;
      ['FoxHeaderScene', 'FoxMetricScene', 'FoxDataListScene', 'FoxTimelineScene', 'BranchPathwayScene', 'LeaderCalloutScene', 'ScaleCompareScene', 'EvidenceHighlightScene'].forEach(c => {
        const card = document.getElementById('studio-style-card-' + c);
        if (card) {
          const isSel = (c === compName);
          const color = (c === 'FoxHeaderScene') ? '#F87171' : '#38BDF8';
          card.style.border = isSel ? `2px solid ${color}` : '1.5px solid #1e293b';
          card.style.boxShadow = isSel ? `0 0 12px ${color}40` : 'none';
        }
      });
    }

    function updateMusicSegmentTrack(stageData, prefix, segIdx, selEl) {
      if (!stageData || !stageData.music_plan || !stageData.music_plan[segIdx]) return;
      const opt = selEl.options[selEl.selectedIndex];
      const newPath = selEl.value;
      const newUrl = opt.getAttribute('data-url') || '';
      const newCat = opt.getAttribute('data-cat') || '';
      const seg = stageData.music_plan[segIdx];
      seg.track = newPath;
      seg.name = newPath.split(/[\/\\]/).pop();
      seg.category = newCat;
      seg.audio_url = newUrl;
      const audioEl = document.getElementById(`${prefix}-music-audio-${segIdx}`);
      if (audioEl) {
        audioEl.src = newUrl;
        if (typeof audioEl.load === 'function') audioEl.load();
      }
      const nameEl = document.getElementById(`${prefix}-music-name-${segIdx}`);
      if (nameEl) nameEl.textContent = seg.name;
      if (typeof showToast === 'function') showToast(`✓ 已更換樂章 ${segIdx + 1} 曲目為: ${seg.name}`);
    }

    function onInspectorMusicTrackChange(segIdx, selEl) {
      updateMusicSegmentTrack(inspectedStageData, 'insp', segIdx, selEl);
    }

    function updateMusicOffset(stageData, segIdx, val) {
      if (!stageData || !stageData.music_plan || !stageData.music_plan[segIdx]) return null;
      stageData.music_plan[segIdx].start_offset = parseFloat(val) || 0;
      return stageData.music_plan[segIdx];
    }

    function onInspectorMusicOffsetChange(segIdx, val) {
      updateMusicOffset(inspectedStageData, segIdx, val);
    }

    async function saveMusicVibe(stageData, val, successMessage) {
      if (!stageData) return;
      stageData.current_vibe = val;
      stageData.music_settings = stageData.music_settings || {};
      stageData.music_settings.vibe = val;
      try {
        await apiRequest(`/api/projects/${currentProjectId}/stage_data/music`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ vibe: val, music_settings: stageData.music_settings })
        });
        if (typeof showToast === 'function') showToast(`${successMessage}: ${val}`);
      } catch (e) {
        console.error("Failed to save music vibe", e);
      }
    }

    async function onInspectorMusicVibeChange(val) {
      return saveMusicVibe(inspectedStageData, val, '✓ 配樂氛圍已設為');
    }

    async function reMatchInspectorMusicVibe() {
      const vibeEl = document.getElementById('insp-music-vibe-select');
      const chosenVibe = vibeEl ? vibeEl.value : (inspectedStageData?.current_vibe || 'auto');
      await onInspectorMusicVibeChange(chosenVibe);
      runSingleStage('music');
    }

    let inspectedStageName = null;
    let inspectedStageData = null;

    async function runSingleStage(stName) {
      if (!currentProjectId) return alert("Please select or create a project first.");
      try {
        const d = await apiJson(`/api/projects/${currentProjectId}/run_stage/${stName}`, { method: 'POST' });

        if (d.status === 'already_running') {
          return alert("Pipeline is already executing. Please wait or stop it first.");
        }
        startPolling();
      } catch (e) {
        alert("Failed to start stage: " + e.message);
      }
    }

    async function runNextStage() {
      if (!currentProjectId) return alert("Please select or create a project first.");
      try {
        const d = await apiJson(`/api/projects/${currentProjectId}`);

        const p = d.project;
        for (const stName of STAGE_ORDER) {
          const st = p.stages[stName];
          if (!st || st.status !== 'COMPLETED') {
            return runSingleStage(stName);
          }
        }
        alert("All 9 stages have been completed! You can inspect or re-run any stage as desired.");
      } catch (e) {
        alert("Error determining next stage: " + e.message);
      }
    }

    function closeStageInspector() {
      document.getElementById('inspector-modal').style.display = 'none';
    }

    async function openStageInspector(stageName) {
      if (!currentProjectId) return alert("Please select or create a project first.");
      inspectedStageName = stageName;
      const modal = document.getElementById('inspector-modal');
      const titleEl = document.getElementById('inspector-title');
      const subEl = document.getElementById('inspector-subtitle');
      const bodyEl = document.getElementById('inspector-body');
      const actionsEl = document.getElementById('inspector-actions');

      if (!currentProject && typeof allProjectsCache !== 'undefined' && allProjectsCache.length) {
        currentProject = allProjectsCache.find(p => p.id === currentProjectId) || studioProject || null;
      }
      const isDrama = isDramaStudioProject(currentProject || studioProject);
      if (isDrama && STAGE_META_DRAMA && STAGE_META_DRAMA[stageName]) {
        titleEl.textContent = `Stage Inspector: ${STAGE_META_DRAMA[stageName].name}`;
        subEl.textContent = `短劇全流程微調：${STAGE_META_DRAMA[stageName].desc}`;
      } else {
        titleEl.textContent = `Stage Inspector: ${STAGE_LABELS[stageName] || stageName.toUpperCase()}`;
        subEl.textContent = `Inspecting & fine-tuning data for stage '${stageName}'`;
      }
      bodyEl.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted);">Loading stage data...</div>';
      actionsEl.innerHTML = '';
      modal.style.display = 'flex';

      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/stage_data/${stageName}`);

        inspectedStageData = data;
        renderInspectorContent(stageName, data);
      } catch (e) {
        bodyEl.innerHTML = `<div style="color:#ef4444;">Failed to load stage data: ${e.message}</div>`;
      }
    }

    async function renderInspectorContent(stageName, data) {
      const bodyEl = document.getElementById('inspector-body');
      const actionsEl = document.getElementById('inspector-actions');
      const isDrama = isDramaStudioProject(data) || isDramaStudioProject(currentProject || studioProject);

      const titleEl = document.getElementById('inspector-title');
      const subEl = document.getElementById('inspector-subtitle');
      if (isDrama && STAGE_META_DRAMA && STAGE_META_DRAMA[stageName]) {
        if (titleEl) titleEl.textContent = `Stage Inspector: ${STAGE_META_DRAMA[stageName].name}`;
        if (subEl) subEl.textContent = `短劇全流程微調：${STAGE_META_DRAMA[stageName].desc}`;
      }

      let bodyHtml = '';
      let actionButtons = `
        <button class="btn-primary" onclick="runSingleStage('${stageName}')">▶ Run Stage</button>
      `;

      if (stageName === 'research') {
        const resText = typeof data.research === 'string' ? data.research : JSON.stringify(data.research || {}, null, 2);
        const titleLabel = isDrama ? '爆款短劇分鏡大綱與衝突節奏 (Drama Storyboard Notes):' : 'Topic Research & Knowledge Notes:';
        const tbTitle = isDrama ? '🔍 Replace Keywords in Drama Storyboard' : '🔍 Replace Keywords in Research';
        const tbSub = isDrama ? '(Batch find & replace terms across drama storyboard beats)' : '(Batch find & replace terms across research notes)';
        bodyHtml = `
          <!-- Find & Replace Keyword Toolbar -->
          <div style="background: rgba(30, 41, 59, 0.45); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 10px 12px; margin-bottom: 12px;">
            <div style="font-size: 12px; font-weight: 700; color: #93c5fd; margin-bottom: 8px; display:flex; align-items:center; gap:6px;">
              <span>${tbTitle}</span>
              <span style="font-size: 11px; font-weight: normal; color: var(--text-muted);">${tbSub}</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
              <input type="text" id="insp-res-find" placeholder="Find keyword..." style="flex: 1; min-width: 140px; font-size: 12px; padding: 6px 10px; background: #04070e; border: 1px solid var(--border-muted); border-radius: 4px; color: #fff;">
              <input type="text" id="insp-res-replace" placeholder="Replace with..." style="flex: 1; min-width: 140px; font-size: 12px; padding: 6px 10px; background: #04070e; border: 1px solid var(--border-muted); border-radius: 4px; color: #fff;">
              <label style="display: flex; align-items: center; gap: 4px; font-size: 11px; color: #cbd5e1; cursor: pointer; user-select: none;">
                <input type="checkbox" id="insp-res-match-case"> Case Sensitive
              </label>
              <button class="btn-sec" style="font-size: 11px; padding: 6px 12px; background: #1e293b; color: #fff;" onclick="performResearchReplace('insp-research', 'insp-res-find', 'insp-res-replace', 'insp-res-match-case', 'insp-res-rep-status')">
                Replace All
              </button>
            </div>
            <div id="insp-res-rep-status" style="font-size: 11px; color: #34d399; margin-top: 4px; min-height: 14px;"></div>
          </div>

          ${(!isDrama) ? renderCharactersReviewHtml(data.characters || (data.research && data.research.key_characters) || [], true) : ''}

          <div style="margin-bottom:12px;">
            <label style="font-weight:600; display:block; margin-bottom:6px;">${titleLabel}</label>
            <textarea id="insp-research" style="width:100%; height:320px; font-family:monospace; font-size:12px; background:#080d16; color:#e2e8f0; border:1px solid var(--card-border); padding:10px; border-radius:6px;">${resText}</textarea>
          </div>
        `;
        actionButtons = `
          <button class="btn-sec" onclick="saveInspectedStage('research')">${isDrama ? 'Save Drama Storyboard' : 'Save Research'}</button>
          <button class="btn-primary" onclick="saveInspectedStage('research', true)">Save & Run Next</button>
          <button class="btn-primary" onclick="runSingleStage('research')">${isDrama ? '▶ Re-run Drama Storyboard' : '▶ Re-run Research'}</button>
        `;
      } else if (stageName === 'script') {
        const scriptMd = data.script_md || '';
        bodyHtml = `
          <!-- Find & Replace Keyword Toolbar for Script -->
          <div style="background: rgba(30, 41, 59, 0.45); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 10px 12px; margin-bottom: 12px;">
            <div style="font-size: 12px; font-weight: 700; color: #93c5fd; margin-bottom: 8px; display:flex; align-items:center; gap:6px;">
              🔍 <span>Replace Keywords in Script</span>
              <span style="font-size: 11px; font-weight: normal; color: var(--text-muted);">(Batch find & replace terms across script markdown)</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
              <input type="text" id="insp-script-find" placeholder="Find keyword..." style="flex: 1; min-width: 140px; font-size: 12px; padding: 6px 10px; background: #04070e; border: 1px solid var(--border-muted); border-radius: 4px; color: #fff;">
              <input type="text" id="insp-script-replace" placeholder="Replace with..." style="flex: 1; min-width: 140px; font-size: 12px; padding: 6px 10px; background: #04070e; border: 1px solid var(--border-muted); border-radius: 4px; color: #fff;">
              <label style="display: flex; align-items: center; gap: 4px; font-size: 11px; color: #cbd5e1; cursor: pointer; user-select: none;">
                <input type="checkbox" id="insp-script-match-case"> Case Sensitive
              </label>
              <button class="btn-sec" style="font-size: 11px; padding: 6px 12px; background: #1e293b; color: #fff;" onclick="performResearchReplace('insp-script-md', 'insp-script-find', 'insp-script-replace', 'insp-script-match-case', 'insp-script-rep-status')">
                Replace All
              </button>
            </div>
            <div id="insp-script-rep-status" style="font-size: 11px; color: #34d399; margin-top: 4px; min-height: 14px;"></div>
          </div>

          <div style="margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
              <label style="font-weight:600;">Narration Script (Markdown):</label>
              <span id="insp-script-wc" style="font-size:12px; color:var(--text-muted);">${scriptMd.length} characters</span>
            </div>
            <textarea id="insp-script-md" style="width:100%; height:320px; font-size:13px; background:#080d16; color:#e2e8f0; border:1px solid var(--card-border); padding:10px; border-radius:6px;" oninput="document.getElementById('insp-script-wc').textContent = this.value.length + ' characters'">${scriptMd}</textarea>
          </div>
        `;
        actionButtons = `
          <button class="btn-sec" onclick="saveInspectedStage('script')">Save Script</button>
          <button class="btn-primary" onclick="runSingleStage('script')">▶ Re-run Script</button>
        `;
      } else if (stageName === 'scenes') {
        const scenes = data.scenes || [];
        bodyHtml = `
          <!-- Find & Replace Keyword Toolbar for Scenes -->
          <div style="background: rgba(30, 41, 59, 0.45); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 10px 12px; margin-bottom: 12px;">
            <div style="font-size: 12px; font-weight: 700; color: #93c5fd; margin-bottom: 8px; display:flex; align-items:center; gap:6px;">
              🔍 <span>Replace Keywords across All Scenes</span>
              <span style="font-size: 11px; font-weight: normal; color: var(--text-muted);">(Batch find & replace terms in all scene narrations & cards)</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
              <input type="text" id="insp-scenes-find" placeholder="Find keyword in scenes..." style="flex: 1; min-width: 140px; font-size: 12px; padding: 6px 10px; background: #04070e; border: 1px solid var(--border-muted); border-radius: 4px; color: #fff;">
              <input type="text" id="insp-scenes-replace" placeholder="Replace with..." style="flex: 1; min-width: 140px; font-size: 12px; padding: 6px 10px; background: #04070e; border: 1px solid var(--border-muted); border-radius: 4px; color: #fff;">
              <label style="display: flex; align-items: center; gap: 4px; font-size: 11px; color: #cbd5e1; cursor: pointer; user-select: none;">
                <input type="checkbox" id="insp-scenes-match-case"> Case Sensitive
              </label>
              <button class="btn-sec" style="font-size: 11px; padding: 6px 12px; background: #1e293b; color: #fff;" onclick="performScenesReplace('insp', 'insp-scenes-find', 'insp-scenes-replace', 'insp-scenes-match-case', 'insp-scenes-rep-status')">
                Replace All
              </button>
            </div>
            <div id="insp-scenes-rep-status" style="font-size: 11px; color: #34d399; margin-top: 4px; min-height: 14px;"></div>
          </div>

          <div style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">${isDrama ? `Total Drama Scenes: <b>${scenes.length}</b>. Edit character lines and actor assignment below.` : `Total Scenes: <b>${scenes.length}</b>. Edit narration text and camera motion per scene below.`}</div>
          <div style="display:flex; flex-direction:column; gap:12px;">
        `;
        scenes.forEach((s, idx) => {
          bodyHtml += `
            <div style="background:#080d16; border:1px solid var(--card-border); border-radius:6px; padding:12px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-weight:700; color:#93c5fd;">Scene #${s.scene_id}</span>
                <span style="font-size: 12px; color:var(--text-muted);">Est: ${s.estimated_duration || 5}s</span>
              </div>
              <div style="margin-bottom:6px;">
                <label style="font-size: 12px; color:var(--text-muted);">Narration Text:</label>
                <textarea rows="2" style="width:100%; font-size:12px; margin-top:2px;" onchange="inspectedStageData.scenes[${idx}].narration=this.value">${s.narration}</textarea>
              </div>
              <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
                ${isDrama ? `
                  <div style="flex:1; min-width:180px;">
                    <label style="font-size: 12px; color:#fbbf24; font-weight:600;">👤 Speaker / Character (出場角色):</label>
                    <input type="text" style="width:100%; font-size: 12px; padding:5px; background:#04070e; border:1px solid #d97706; color:#fbbf24; border-radius:4px;" value="${s.character || s.speaker || ''}" placeholder="e.g. 沈總監" onchange="inspectedStageData.scenes[${idx}].character=this.value; inspectedStageData.scenes[${idx}].speaker=this.value;">
                  </div>
                  <div style="flex:1; min-width:180px;">
                    <label style="font-size: 12px; color:#34d399; font-weight:600;">🎬 Visual Type (畫面型態):</label>
                    <div style="font-size:12px; padding:6px; background:#04070e; border:1px solid #059669; color:#34d399; font-weight:700; border-radius:4px;">🎭 9:16 直式角色動態影片 (Talking Actor)</div>
                  </div>
                ` : `
                  <div style="flex:1; min-width:180px;">
                    <label style="font-size: 12px; color:var(--text-muted);">Camera Motion:</label>
                    <select style="width:100%; font-size: 12px; padding:4px;" onchange="inspectedStageData.scenes[${idx}].camera_motion=this.value">
                      <option value="slow_zoom_in" ${s.camera_motion==='slow_zoom_in'?'selected':''}>Zoom In</option>
                      <option value="slow_zoom_out" ${s.camera_motion==='slow_zoom_out'?'selected':''}>Zoom Out</option>
                      <option value="pan_left" ${s.camera_motion==='pan_left'?'selected':''}>Pan Left</option>
                      <option value="pan_right" ${s.camera_motion==='pan_right'?'selected':''}>Pan Right</option>
                      <option value="static" ${s.camera_motion==='static'?'selected':''}>Static</option>
                    </select>
                  </div>
                  <div style="flex:1; min-width:180px;">
                    <label style="font-size: 12px; color:#38bdf8;">🥁 Phase Turn Card (Black Screen):</label>
                    <input type="text" style="width:100%; font-size: 12px; padding:4px; background:#04070e; border:1px solid #1e293b; color:#38bdf8; border-radius:4px;" value="${s.phase_turn_text || ''}" placeholder="e.g. 關鍵真相：客廳 AI 革命" onchange="inspectedStageData.scenes[${idx}].phase_turn_text=this.value;">
                  </div>
                  <div style="flex:1; min-width:180px;">
                    <label style="font-size: 12px; color:#00F5FF;">✨ Motion Graphic Card (fOx Hsiao style):</label>
                    <input type="text" style="width:100%; font-size: 12px; padding:4px; background:#04070e; border:1px solid #1e293b; color:#00F5FF; border-radius:4px;" value="${s.callout_text || ''}" placeholder="e.g. ⚡ 核心數據 | 2,000 億美元 | 四大雲端巨頭合計 CapEx" onchange="inspectedStageData.scenes[${idx}].callout_text=this.value;">
                  </div>
                `}
              </div>
            </div>
          `;
        });
        bodyHtml += `</div>`;
        actionButtons = `
          <button class="btn-sec" onclick="saveInspectedStage('scenes')">Save Scenes</button>
          <button class="btn-sec" style="background: rgba(56, 189, 248, 0.15); border-color: #0284c7; color: #38bdf8; font-weight: 700; display: inline-flex; align-items: center; gap: 5px;" onclick="openStage3ExportModal()" title="匯出 Stage 3 分鏡腳本供團隊審閱">📤 匯出分鏡腳本 (Export)</button>
          <button class="btn-sec" onclick="copyStage3ScriptToClipboard()" title="複製全部分鏡台詞至剪貼簿">📋 複製台詞</button>
          <button class="btn-primary" onclick="runSingleStage('scenes')">▶ Re-run Scenes</button>
        `;
      } else if (stageName === 'prompts') {
        const scenes = data.scenes || [];
        const styles = data.available_styles || {};
        const curStyle = data.current_style || 'cinematic_documentary';

        let styleOptionsHtml = '';
        for (const [sKey, sObj] of Object.entries(styles)) {
          styleOptionsHtml += `<option value="${sKey}" ${sKey === curStyle ? 'selected' : ''}>${sObj.label || sKey}</option>`;
        }

        bodyHtml = `
          <div style="background: linear-gradient(135deg, #0e1e38 0%, #0a1324 100%); border: 1px solid #1e3a8a; border-radius: 8px; padding: 14px; margin-bottom: 16px;">
            <div style="font-size: 13px; font-weight: 700; color: #93c5fd; margin-bottom: 8px;">🎨 Visual Style for Prompts</div>
            <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
              <div style="flex:1; min-width:220px;">
                <select id="insp-prompt-style" style="width:100%; font-size:12px; padding:6px; background:#080d16; color:#fff; border:1px solid #2b456b; border-radius:4px;">
                  ${styleOptionsHtml}
                </select>
              </div>
              <button class="btn-sec" style="font-size:12px; padding:6px 12px; background:#1e3a8a; border-color:#3b82f6; color:#fff;" onclick="applyStyleFromPromptsTab()">🎨 Apply Style to All Prompts</button>
            </div>
          </div>
          <div style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">Tune ComfyUI image prompts per scene. Keyword changes directly guide SDXL generation.</div>
          <div style="display:flex; flex-direction:column; gap:12px;">
        `;
        scenes.forEach((s, idx) => {
          bodyHtml += `
            <div style="background:#080d16; border:1px solid var(--card-border); border-radius:6px; padding:12px;">
              <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                <span style="font-weight:700; color:#93c5fd;">Scene #${s.scene_id}</span>
                <span style="font-size: 12px; color:var(--text-muted);">${s.visual_type || 'image'}</span>
              </div>
              <div style="margin-bottom:6px;">
                <label style="font-size: 12px; color:var(--text-muted);">Positive Image Prompt:</label>
                <textarea rows="2" style="width:100%; font-size:12px; margin-top:2px;" onchange="inspectedStageData.scenes[${idx}].prompt=this.value">${s.prompt || ''}</textarea>
              </div>
              <div>
                <label style="font-size: 12px; color:var(--text-muted);">Negative Prompt:</label>
                <input type="text" style="width:100%; font-size: 12px; padding:4px;" value="${s.negative_prompt || ''}" onchange="inspectedStageData.scenes[${idx}].negative_prompt=this.value">
              </div>
            </div>
          `;
        });
        bodyHtml += `</div>`;
        actionButtons = `
          <button class="btn-sec" onclick="saveInspectedStage('prompts')">Save Prompts</button>
          <button class="btn-primary" onclick="runSingleStage('prompts')">▶ Re-run Prompts (LLM)</button>
        `;
      } else if (stageName === 'images') {
        const scenes = data.scenes || [];
        const styles = data.available_styles || {};
        const models = data.available_models || ['sd_xl_base_1.0.safetensors'];
        const curStyle = data.current_style || 'cinematic_documentary';
        const curModel = data.current_model || 'sd_xl_base_1.0.safetensors';
        const curSteps = data.current_steps || 25;
        const curCfg = data.current_cfg || 6.5;

        const isProjCloud = isProjectCloudAccelerated(inspectedStageData);
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

        bodyHtml = `
          <!-- Global Style & Model Config Panel -->
          <div style="background: linear-gradient(135deg, #0e1e38 0%, #0a1324 100%); border: 1px solid #1e3a8a; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
            <div style="font-size: 14px; font-weight: 700; color: #93c5fd; margin-bottom: 12px; display:flex; align-items:center; gap:8px;">
              <span>🎨 Global Image Style & Engine Configuration</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 12px;">
              <div>
                <label style="font-size: 12px; font-weight:600; color: #cbd5e1; display:block; margin-bottom: 4px;">Visual Generation Style:</label>
                <select id="insp-img-style" style="width:100%; font-size:12px; padding:6px; background:#080d16; color:#fff; border:1px solid #2b456b; border-radius:4px;" onchange="onStyleDropdownChange(this.value)">
                  ${styleOptionsHtml}
                </select>
              </div>
              <div>
                <label style="font-size: 12px; font-weight:600; color: #cbd5e1; display:block; margin-bottom: 4px;">Image Engine / Checkpoint:</label>
                <select id="insp-img-model" style="width:100%; font-size:12px; padding:6px; background:#080d16; color:#fff; border:1px solid #2b456b; border-radius:4px;">
                  ${modelOptionsHtml}
                </select>
              </div>
              <div style="display:flex; gap:10px;">
                <div style="flex:1;">
                  <label style="font-size: 12px; font-weight:600; color: #cbd5e1; display:block; margin-bottom: 4px;">Steps:</label>
                  <input type="number" id="insp-img-steps" value="${curSteps}" min="10" max="60" style="width:100%; font-size:12px; padding:6px; background:#080d16; color:#fff; border:1px solid #2b456b; border-radius:4px;">
                </div>
                <div style="flex:1;">
                  <label style="font-size: 12px; font-weight:600; color: #cbd5e1; display:block; margin-bottom: 4px;">CFG Scale:</label>
                  <input type="number" id="insp-img-cfg" value="${curCfg}" min="1.0" max="15.0" step="0.5" style="width:100%; font-size:12px; padding:6px; background:#080d16; color:#fff; border:1px solid #2b456b; border-radius:4px;">
                </div>
              </div>
            </div>
            <div id="insp-style-preview-box" style="font-size: 12px; background:#060a12; border:1px solid #1a2538; padding:8px 12px; border-radius:4px; margin-bottom:12px; color:#94a3b8;">
              <b>Active Style Tags:</b> <span id="insp-style-tag-text">${activeStyleObj.style || ''} (${activeStyleObj.mood || ''}, ${activeStyleObj.lighting || ''})</span>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
              <button class="btn-sec" style="font-size:12px; padding:5px 12px;" onclick="saveImageSettings(false)">💾 Save Style & Model</button>
              <button class="btn-sec" style="font-size:12px; padding:5px 12px; background:#1e3a8a; border-color:#3b82f6; color:#fff;" onclick="saveImageSettings(true)">🎨 Apply Style to All Prompts</button>
              <button class="btn-primary" style="font-size:12px; padding:5px 12px;" onclick="saveAndRunFullImages(false)">▶ Save & Generate All Images</button>
            </div>
          </div>

          ${isDrama ? '' : `<!-- Quick Stock Analytics & Batch Actions Banner -->
          <div style="background: linear-gradient(135deg, rgba(6, 78, 59, 0.45) 0%, rgba(15, 23, 42, 0.65) 100%); border: 1px solid #059669; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);">
            <div style="display: flex; flex-direction: column; gap: 4px;">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <span style="font-size: 14px; font-weight: 700; color: #6ee7b7; display: flex; align-items: center; gap: 6px;">
                  <span>🌐</span> <span>Quick Stock 實體素材分析</span>
                </span>
                <span style="background: rgba(16, 185, 129, 0.25); border: 1px solid #10b981; color: #a7f3d0; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">
                  ${data.stock_available_count || 0} / ${data.total_scenes || scenes.length} 鏡頭命中真實素材標籤
                </span>
                <span style="background: rgba(59, 130, 246, 0.25); border: 1px solid #3b82f6; color: #bfdbfe; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">
                  已套用線上圖庫：${data.stock_active_count || 0} / ${data.total_scenes || scenes.length}
                </span>
              </div>
              <div style="font-size: 11px; color: #cbd5e1; line-height: 1.4;">
                系統已自動分析各鏡頭對應的人物、產品實體、知名硬體與歷史檔案。標註 <b style="color:#6ee7b7;">綠色</b> 標籤即表示擁有高精準度的真實圖庫素材；點擊右側按鈕可一鍵將全片替換為線上圖庫。
              </div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
              <button class="btn-primary" style="background: linear-gradient(135deg, #059669 0%, #047857 100%); border-color: #10b981; font-weight: 700; font-size: 12px; padding: 7px 14px; box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);" onclick="triggerBatchQuickStock('all')" id="btn-batch-stock-all" title="將全片所有鏡頭替換為線上圖庫 / Quick Stock 圖片">
                ⚡ 一鍵全部替換為 Quick Stock 圖片
              </button>
              <button class="btn-sec" style="background: rgba(5, 150, 105, 0.2); border-color: #059669; color: #6ee7b7; font-weight: 700; font-size: 12px; padding: 7px 12px;" onclick="triggerBatchQuickStock('matched_only')" id="btn-batch-stock-matched" title="僅替換命中真實人物、晶片或硬體實體的鏡頭">
                🎯 僅替換真實實體鏡頭 (${data.stock_available_count || 0} 個)
              </button>
            </div>
          </div>` }

          <!-- Per-Scene Gallery & Tuning -->
          <div style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">Scene Images Gallery: Tune prompts or change models per scene, then click Regenerate to re-render using ComfyUI DirectML.</div>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(460px, 1fr)); gap:14px;">
        `;

        const buster = Date.now();
        scenes.forEach((s, idx) => {
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
            <div id="insp-scene-card-${s.scene_id}" style="background:#080d16; border:1px solid var(--card-border); border-radius:8px; padding:12px; display:flex; flex-direction:column; gap:8px;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:700; color:#93c5fd; font-size:13px;">Scene #${s.scene_id}</span>
                <span id="insp-scene-badge-${s.scene_id}" style="font-size: 12px; color:${imgUrl?'#34d399':'#f59e0b'}; font-weight:600;">${imgUrl ? '✓ Generated' : '⏳ Pending'}</span>
              </div>

              ${isDrama ? `
                <div style="font-size: 11px; padding: 4px 8px; background: rgba(245, 158, 11, 0.15); border: 1px solid #d97706; border-radius: 4px; color: #fbbf24; font-weight: 600; display: flex; align-items: center; justify-content: space-between;">
                  <span>👤 角色: <b>${s.character || s.speaker || '主演'}</b></span>
                  <span style="font-size: 9px; background: #b45309; color: #fff; padding: 1px 5px; border-radius: 3px; font-weight: 700;">9:16 直式立繪</span>
                </div>
              ` : `
                <!-- Real-world Quick Stock Status Pill -->
                ${s.is_stock_active ? `
                  <div style="font-size: 11px; padding: 4px 8px; background: rgba(5, 150, 105, 0.25); border: 1px solid #059669; border-radius: 4px; color: #6ee7b7; font-weight: 600; display: flex; align-items: center; justify-content: space-between; gap: 4px;">
                    <span style="display: flex; align-items: center; gap: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                      <span>📸 已套用線上圖庫:</span> <b style="color: #fff;">${s.active_stock_source || (s.image && s.image.meta && s.image.meta.source) || 'Stock'}</b>
                      ${(s.active_stock_title || (s.image && s.image.meta && s.image.meta.title)) ? `<span style="opacity: 0.8; font-weight: normal; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 140px;">(${s.active_stock_title || s.image.meta.title})</span>` : ''}
                    </span>
                    <span style="font-size: 9px; background: #065f46; color: #a7f3d0; padding: 1px 4px; border-radius: 3px; font-weight: 700;">ACTIVE</span>
                  </div>
                ` : (s.quick_stock_available ? `
                  <div style="font-size: 11px; padding: 4px 8px; background: rgba(59, 130, 246, 0.2); border: 1px solid #3b82f6; border-radius: 4px; color: #93c5fd; font-weight: 600; display: flex; align-items: center; justify-content: space-between; gap: 6px;">
                    <span title="命中素材目標: ${s.quick_stock_target}" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                      🌐 <b>可使用 Quick Stock:</b> ${s.quick_stock_target}
                    </span>
                    <span style="font-size: 9px; background: #1e3a8a; color: #bfdbfe; padding: 1px 4px; border-radius: 3px; white-space: nowrap; font-weight: 700;">
                      ${s.quick_stock_source === 'youtube_snippet' ? 'YouTube 實體片段' : '維基共享資源'}
                    </span>
                  </div>
                ` : `
                  <div style="font-size: 11px; padding: 3px 6px; background: rgba(148, 163, 184, 0.08); border: 1px solid #334155; border-radius: 4px; color: #94a3b8; display: flex; align-items: center; gap: 4px;">
                    🎨 <span>AI 生成畫面 (無特定真實實體標籤)</span>
                  </div>
                `)}
              ` }

              <!-- Side-by-Side: Image and Scene Script Line -->
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; align-items: stretch;">
                <!-- Left: Scene Image Preview -->
                <div style="display: flex; flex-direction: column; gap: 6px;">
                  <div style="width:100%; height:150px; background:#000; border-radius:6px; overflow:hidden; display:flex; align-items:center; justify-content:center; position:relative; border: 1px solid #1e293b;">
                    ${imgUrl ? `
                      <img id="insp-scene-img-${s.scene_id}" src="${imgUrlBusted}" style="width:100%; height:100%; object-fit:cover; cursor:pointer;" onclick="window.open('${imgUrl}')" title="Click to view full image">
                      <div style="position: absolute; bottom: 4px; left: 4px; background: rgba(0,0,0,0.7); font-size: 10px; color: #cbd5e1; padding: 2px 5px; border-radius: 3px; pointer-events: none;">🔍 Click to Zoom</div>
                      <button onclick="event.stopPropagation(); deleteSceneActiveImage(${s.scene_id})" style="position: absolute; top: 4px; right: 4px; background: rgba(0,0,0,0.75); border: 1px solid #ef4444; color: #fca5a5; border-radius: 3px; padding: 2px 6px; font-size: 11px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 3px; z-index: 2;" title="Delete current image">
                        🗑️ Delete
                      </button>
                    ` : `<span id="insp-no-img-${s.scene_id}" style="font-size:12px; color:gray;">No Image Generated</span>`}
                  </div>
                </div>

                <!-- Right: Script / Narration Box for match check & adjustment -->
                <div style="display: flex; flex-direction: column; gap: 5px; background: rgba(14, 20, 34, 0.75); border: 1px solid rgba(124, 145, 182, 0.25); border-left: 3px solid #C19D49; border-radius: 6px; padding: 8px 10px;">
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 11px; font-weight: 700; color: #C19D49; display: flex; align-items: center; gap: 4px;">
                      <span>🎙️</span> <span>分鏡旁白台詞 (Script Line)</span>
                    </span>
                    <span id="insp-script-len-${s.scene_id}" style="font-size: 10px; color: #7C91B6; font-family: monospace;">${(s.narration || '').length} 字</span>
                  </div>
                  <div style="font-size: 11px; color: #94a3b8; line-height: 1.3;">
                    核對台詞與左側畫面是否相符，可在此直接編輯台詞：
                  </div>
                  <div style="flex: 1; display: flex; flex-direction: column;">
                    <textarea id="insp-scene-script-${s.scene_id}" rows="3" style="width: 100%; flex: 1; min-height: 75px; font-size: 12px; line-height: 1.45; padding: 6px 8px; background: #04070e; border: 1px solid #1e293b; color: #f1f5f9; border-radius: 4px; resize: vertical;" oninput="onStudioScriptInput(${s.scene_id}, this.value)" onblur="saveSingleSceneScript(${s.scene_id}, true)" placeholder="輸入旁白台詞...">${escapeHtml(s.narration || '')}</textarea>
                  </div>
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 2px;">
                    <span id="insp-script-toast-${s.scene_id}" style="font-size: 11px; color: #34d399; font-weight: 600; display: none;">✓ 台詞已儲存</span>
                    <button class="btn-sec" id="insp-btn-save-script-${s.scene_id}" style="padding: 2px 8px; font-size: 11px; background: #233b6d; border-color: #3b82f6; color: #93c5fd; font-weight: 600; margin-left: auto;" onclick="saveSingleSceneScript(${s.scene_id}, false)" title="儲存修改後的旁白台詞">
                      💾 儲存台詞
                    </button>
                  </div>
                </div>
              </div>

              <!-- Live Progress & GPU Workload Box -->
              <div id="insp-prog-box-${s.scene_id}" style="display: none; background: #040914; border: 1px solid #2563eb; border-radius: 6px; padding: 6px 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;">
                  <span id="insp-prog-title-${s.scene_id}" style="color: #60a5fa; font-weight: 600; font-size: 12px;">🚀 Initializing ComfyUI...</span>
                  <span id="insp-prog-pct-${s.scene_id}" style="color: #93c5fd; font-weight: 700; font-size: 12px;">0%</span>
                </div>
                <div style="width: 100%; height: 6px; background: #1e293b; border-radius: 999px; overflow: hidden; margin-bottom: 4px;">
                  <div id="insp-prog-bar-${s.scene_id}" style="width: 0%; height: 100%; background: linear-gradient(90deg, #2563eb, #38bdf8); transition: width 0.25s ease;"></div>
                </div>
                <div id="insp-prog-gpu-${s.scene_id}" style="font-size: 9px; color: #94a3b8; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #1e293b; padding-top: 3px;">
                  <span>DirectML GPU:</span>
                  <span id="insp-prog-gpu-val-${s.scene_id}" style="color: #38bdf8; font-weight: 600;">Querying...</span>
                </div>
              </div>

              <!-- Success Alert Flash -->
              <div id="insp-scene-toast-${s.scene_id}" style="display: none; background: #064e3b; border: 1px solid #059669; border-radius: 4px; padding: 4px 8px; color: #a7f3d0; font-size: 12px; font-weight: 600; text-align: center;">✓ Updated!</div>

              <!-- Takes Management & Selector -->
              <div style="background: #04070e; border: 1px solid #1e293b; border-radius: 6px; padding: 6px 8px; display: flex; flex-direction: column; gap: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 4px;">
                  <div style="display: flex; align-items: center; gap: 4px;">
                    <span style="font-weight: 700; color: #93c5fd; font-size: 12px;">🎞️ Takes (${totalTakes}):</span>
                    <span id="insp-scene-active-take-badge-${s.scene_id}" style="background: rgba(5,150,105,0.25); border: 1px solid #059669; color: #34d399; font-size: 9px; font-weight: 700; padding: 1px 4px; border-radius: 3px;">Take #${activeTake || 1} Active</span>
                  </div>
                  <div style="display: flex; gap: 4px; align-items: center;">
                    <button id="insp-take-prev-btn-${s.scene_id}" class="btn-sec" style="padding: 1px 5px; font-size: 9px;" onclick="cycleSceneImageTake(${s.scene_id}, -1)" ${hasPrevTake ? '' : 'disabled'} title="Previous Take">◀</button>
                    <button id="insp-take-next-btn-${s.scene_id}" class="btn-sec" style="padding: 1px 5px; font-size: 9px;" onclick="cycleSceneImageTake(${s.scene_id}, 1)" ${hasNextTake ? '' : 'disabled'} title="Next Take">▶</button>
                    <button class="btn-sec" style="padding: 1px 6px; font-size: 9px; background: #1e3a8a; border-color: #3b82f6; color: #fff;" onclick="openTakesGalleryModal(${s.scene_id})">🖼️ Compare (${totalTakes})</button>
                  </div>
                </div>

                ${takes.length > 0 ? `
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px; margin-bottom: 2px;">
                    <span style="font-size: 9px; color: #94a3b8; font-weight: 600;">Images created (${takes.length}):</span>
                    <div style="display: flex; gap: 3px;">
                      <button class="btn-sec" style="padding: 1px 5px; font-size: 9px;" onclick="scrollTakesStrip('insp-takes-strip-${s.scene_id}', -100)" title="Scroll Left">◀</button>
                      <button class="btn-sec" style="padding: 1px 5px; font-size: 9px;" onclick="scrollTakesStrip('insp-takes-strip-${s.scene_id}', 100)" title="Scroll Right">▶</button>
                    </div>
                  </div>
                  <div id="insp-takes-strip-${s.scene_id}" class="takes-scroll-strip" onwheel="if(event.deltaY !== 0){ event.preventDefault(); this.scrollLeft += event.deltaY; }">
                    ${takes.map(tk => {
                      const isAct = (tk.take === activeTake);
                      const tkSrc = `/media/${currentProjectId}/${tk.path}?t=${buster}`;
                      return `
                        <div style="flex: 0 0 90px; background: ${isAct ? '#081a38' : '#03060d'}; border: 2px solid ${isAct ? '#3b82f6' : '#1e293b'}; border-radius: 5px; padding: 4px; display: flex; flex-direction: column; gap: 3px; cursor: pointer;" onclick="switchSceneTakeDirect(${s.scene_id}, ${tk.take})">
                          <div style="width: 100%; height: 46px; background: #000; border-radius: 3px; overflow: hidden; position: relative;">
                            <img src="${tkSrc}" alt="" onerror="this.onerror=null; this.src='/media/${currentProjectId}/images/scene_${String(s.scene_id).padStart(3, '0')}.png';" style="width: 100%; height: 100%; object-fit: cover;">
                            ${isAct ? '<span style="position: absolute; top: 1px; right: 1px; background: #10b981; color: #fff; font-size: 7px; font-weight: 700; padding: 0 2px; border-radius: 2px;">ACTIVE</span>' : ''}
                          </div>
                          <div style="font-size: 8px; font-weight: 700; color: ${isAct ? '#93c5fd' : '#cbd5e1'}; text-align: center;">Take #${tk.take}</div>
                          <div style="display: flex; gap: 2px; margin-top: auto; padding-top: 1px;">
                            <button class="btn-sec" style="flex: 1; font-size: 7px; padding: 1px 3px; font-weight: 600; ${isAct ? 'background: #059669; border-color: #10b981; color: #fff;' : 'background: #1e3a8a; border-color: #3b82f6; color: #fff;'}" onclick="event.stopPropagation(); switchSceneTakeDirect(${s.scene_id}, ${tk.take})">
                              ${isAct ? '✓ In Video' : '👉 Select'}
                            </button>
                            <button class="btn-sec" style="padding: 1px 5px; font-size: 8px; background: rgba(239, 68, 68, 0.25); border-color: #b91c1c; color: #fca5a5; font-weight: 700;" onclick="event.stopPropagation(); deleteSceneImageTake(${s.scene_id}, ${tk.take})" title="Delete Take #${tk.take}">
                              🗑️
                            </button>
                          </div>
                        </div>
                      `;
                    }).join('')}
                  </div>
                ` : ''}
              </div>

              <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #94a3b8;">
                <span>Active Model: <b style="color: #94a3b8;">${renderedModel}</b></span>
                <span>Active Style: <b style="color: #93c5fd;">${(styles[renderedStyle] && styles[renderedStyle].label) || renderedStyle}</b></span>
              </div>
              <div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
                  <label style="font-size: 12px; color: var(--text-muted);">Prompt Tuning:</label>
                  <a href="javascript:void(0)" onclick="applyInspSceneStyleTags(${s.scene_id})" style="color: #60a5fa; font-size: 9px; text-decoration: none;" title="Format prompt with style keywords">✨ Format with Style Tags</a>
                </div>
                <textarea id="scene-prompt-${s.scene_id}" rows="2" style="width:100%; font-size: 12px; padding:5px; background:#04070e; border:1px solid #1e293b; color:#e2e8f0; border-radius:4px;">${s.prompt || s.visual_description || ''}</textarea>
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px;">
                <div>
                  <label style="font-size: 9px; font-weight: 600; color: #94a3b8; display: block; margin-bottom: 2px;">🎨 Visual Style:</label>
                  <select id="scene-style-${s.scene_id}" style="width:100%; font-size: 12px; padding:4px; background:#04070e; border:1px solid #1e293b; color:#cbd5e1; border-radius:4px;" onchange="onInspSceneStyleChange(${s.scene_id}, this.value)">
                    ${perSceneStyleOptions}
                  </select>
                </div>
                <div>
                  <label style="font-size: 9px; font-weight: 600; color: #94a3b8; display: block; margin-bottom: 2px;">🧠 Model / Checkpoint:</label>
                  <select id="scene-model-${s.scene_id}" style="width:100%; font-size: 12px; padding:4px; background:#04070e; border:1px solid #1e293b; color:#cbd5e1; border-radius:4px;">
                    ${perSceneModelOptions}
                  </select>
                </div>
              </div>

              <div style="margin-top: 2px; display: flex; gap: 4px; flex-wrap: wrap;">
                <button class="btn-sec" style="flex: 1; font-size: 12px; padding:5px 8px; background:#1e3a8a; border-color:#3b82f6; color:#fff; font-weight: 600;" onclick="regenImageWithCustomSettings(${s.scene_id})" id="btn-regen-${s.scene_id}">🔄 Regenerate</button>
                ${isDrama ? '' : `
                  <button class="btn-sec" style="font-size: 12px; padding: 5px 8px; background: ${s.quick_stock_available ? 'rgba(5, 150, 105, 0.35)' : 'rgba(5, 150, 105, 0.15)'}; border-color: ${s.quick_stock_available ? '#10b981' : '#059669'}; color: ${s.quick_stock_available ? '#a7f3d0' : '#6ee7b7'}; font-weight: 600;" onclick="quickStockPhotoForScene(${s.scene_id}, true)" title="${s.quick_stock_available ? `抓取真實素材: ${s.quick_stock_target} (${s.quick_stock_source === 'youtube_snippet' ? 'YouTube' : 'Wikimedia'})` : `搜尋線上圖庫並套用至 Scene #${s.scene_id}`}">
                    ${s.quick_stock_available ? '⚡ Quick Stock (真實素材)' : '🌐 Quick Stock'}
                  </button>
                  <button class="btn-sec" style="font-size: 12px; padding: 5px 8px; background: rgba(16, 185, 129, 0.2); border-color: #059669; color: #6ee7b7; font-weight: 600;" onclick="openStockMediaModal(${s.scene_id}, \`${(s.visual_description || s.prompt || '').replace(/[`\\$]/g, ' ')}\`)" title="Search online stock videos & photos for Scene #${s.scene_id}">🔍 Stock Library</button>
                `}
                ${imgUrl ? `<button class="btn-sec" style="padding: 5px 8px; font-size: 12px; background: rgba(239, 68, 68, 0.15); border-color: #b91c1c; color: #fca5a5; font-weight: 600;" onclick="deleteSceneActiveImage(${s.scene_id})" 
                ${(s.is_stock_active || s.quick_stock_available || imgUrl) ? `
                  <button class="btn-sec" style="font-size: 12px; padding: 5px 8px; background: rgba(220, 38, 38, 0.2); border-color: #ef4444; color: #fca5a5; font-weight: 600;" onclick="rejectAndReplaceSceneMedia(${s.scene_id})" title="標記目前素材與本場景不符，加入黑名單並替換為其他相符真實素材或 AI 畫面">
                    🚫 排除並重挑 (Reject)
                  </button>
                ` : ''}
                title="Delete image for Scene #${s.scene_id}">🗑️ Delete</button>` : ''}
              </div>
            </div>
          `;
        });
        bodyHtml += `</div>`;
        actionButtons = `
          <button class="btn-sec" onclick="saveImageSettings(false)">Save Settings</button>
          <button class="btn-primary" onclick="saveAndRunFullImages()">▶ Re-run Full Images Stage</button>
        `;
      } else if (stageName === 'voice') {
        const scenes = data.scenes || [];
        const vProf = data.voice_profile || {};
        const vName = data.voice_name || 'tsao';
        const hasRef = vProf.reference_wav;
        const refSrc = hasRef ? `/media/voices/${vName}/reference.wav` : '';
        const availVoicesTop = data.available_voices || [];
        let topVoiceOptsHtml = '';
        availVoicesTop.forEach(av => {
          const isSel = (av.name === vName);
          topVoiceOptsHtml += `<option value="${av.name}" ${isSel ? 'selected' : ''}>${av.display_name} (${av.name}) — ${av.provider.toUpperCase()}</option>`;
        });

        // Check BlueMagpie status asynchronously
        let bmStatusHtml = '<span id="bm-live-badge" style="color:#f59e0b;">Checking BlueMagpie...</span>';
        setTimeout(() => refreshBlueMagpieBadge('bm-live-badge'), 50);

        bodyHtml = `
          <div style="background:#0e1e38; border:1px solid #1e3a8a; border-radius:6px; padding:12px 16px; margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
              <div style="flex:1; min-width:260px;">
                <div style="font-size:13px; font-weight:700; color:#93c5fd; margin-bottom:4px;">🎙️ Active Project Voice Profile:</div>
                <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                  <select id="insp-global-voice-profile" onchange="switchProjectGlobalVoiceProfile(this.value, 'inspector')" style="flex:1; min-width:220px; padding:6px 10px; font-size:13px; font-weight:600; background:#040811; border:1px solid #10b981; color:#fff; border-radius:6px;">
                    ${topVoiceOptsHtml}
                  </select>
                  <button class="btn-primary" style="padding:6px 12px; font-size:12px; font-weight:700; background:linear-gradient(135deg, #059669 0%, #047857 100%);" onclick="openRerenderVoiceModal(document.getElementById('insp-global-voice-profile')?.value)">🎙️🔄 Re-render Voice & Update Video</button>
                </div>
                <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
                  Provider: <b>${(vProf.provider || 'bluemagpie').toUpperCase()}</b> ${vProf.voice_id ? `| Voice ID: <b>${vProf.voice_id}</b>` : `| BlueMagpie Server: ${bmStatusHtml}`}
                </div>
              </div>
              ${refSrc ? `
                <div style="display:flex; flex-direction:column; align-items:flex-end;">
                  <span style="font-size: 12px; color:#cbd5e1; margin-bottom:2px;">User Reference Voice Sample:</span>
                  <audio controls src="${refSrc}" style="height:32px; max-width:260px;"></audio>
                </div>
              ` : ''}
            </div>
          </div>

          <div style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">Scene Narration Audio Clips: Listen to each scene speech synthesis or re-synthesize individual scenes using your cloned voice.</div>
          <div style="display:flex; flex-direction:column; gap:10px;">
        `;

        const availVoices = data.available_voices || [];
        scenes.forEach((s, idx) => {
          const hasAudio = s.audio && s.audio.path;
          const aSrc = hasAudio ? `/media/${currentProjectId}/${s.audio.path}?t=${Date.now()}` : '';
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
            <div id="insp-scene-voice-card-${s.scene_id}" style="background:#080d16; border:1px solid var(--card-border); border-radius:8px; padding:12px; display:flex; flex-direction:column; gap:8px;">
              <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div style="display:flex; align-items:center; gap:8px;">
                  <span style="font-weight:700; color:#93c5fd;">Scene #${s.scene_id}</span>
                  <span style="font-size: 12px; color:var(--text-muted);">${s.audio_duration ? s.audio_duration.toFixed(1) + 's' : 'Est ' + (s.estimated_duration || 5) + 's'}</span>
                </div>
                <div id="insp-scene-voice-toast-${s.scene_id}" style="display: none; background: #064e3b; border: 1px solid #059669; border-radius: 4px; padding: 2px 8px; color: #a7f3d0; font-size: 12px; font-weight: 600;">✓ Saved</div>
              </div>

              <div style="font-size:13px; color:#e2e8f0; line-height:1.4; background:#04070e; border:1px solid #1e293b; border-radius:4px; padding:8px 10px;">
                "${s.narration}"
              </div>

              <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; background:#0e1e38; border:1px solid #1e3a8a; border-radius:4px; padding:6px 10px;">
                <div style="display:flex; align-items:center; gap:6px; flex:1; min-width:220px;">
                  <label style="font-size: 12px; font-weight:600; color:#93c5fd; white-space:nowrap;">🎙️ Voice:</label>
                  <select id="insp-scene-voice-${s.scene_id}" style="width:100%; font-size: 12px; padding:4px 6px; background:#04070e; border:1px solid #1e293b; color:#cbd5e1; border-radius:4px;">
                    ${perSceneVoiceOptions}
                  </select>
                </div>
                <button class="btn-sec" style="font-size: 12px; padding:4px 10px; background:#1e3a8a; border-color:#3b82f6; color:#fff; font-weight:600;" onclick="regenVoiceAndRefresh(${s.scene_id})" id="insp-btn-voice-${s.scene_id}">🎙️ Synthesize</button>
              </div>

              <!-- Takes Management Bar & Strip -->
              <div style="background:#04070e; border:1px solid #1e293b; border-radius:4px; padding:6px 8px; display:flex; flex-direction:column; gap:6px;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:4px;">
                  <div style="display:flex; align-items:center; gap:6px;">
                    <span style="font-weight:700; color:#93c5fd; font-size: 12px;">🎞️ Takes (${totalVTakes}):</span>
                    <span style="background:rgba(5,150,105,0.25); border:1px solid #059669; color:#34d399; font-size:9px; font-weight:700; padding:1px 5px; border-radius:3px;">✓ Take #${activeVTake || 1} Active</span>
                  </div>
                  <div style="display:flex; gap:3px; align-items:center;">
                    <button class="btn-sec" style="padding:1px 5px; font-size:9px;" onclick="cycleSceneVoiceTake(${s.scene_id}, -1)" ${hasPrevVTake ? '' : 'disabled'}>◀</button>
                    <button class="btn-sec" style="padding:1px 5px; font-size:9px;" onclick="cycleSceneVoiceTake(${s.scene_id}, 1)" ${hasNextVTake ? '' : 'disabled'}>▶</button>
                    <button class="btn-sec" style="padding:1px 6px; font-size:9px; background:#1e3a8a; border-color:#3b82f6; color:#fff;" onclick="openVoiceTakesGalleryModal(${s.scene_id})">🎧 Compare</button>
                  </div>
                </div>

                ${vTakes.length > 0 ? `
                  <div style="display:flex; gap:6px; overflow-x:auto; padding:2px; scrollbar-width:thin;">
                    ${vTakes.map(tk => {
                      const isAct = (tk.take === activeVTake);
                      const tkSrc = `/media/${currentProjectId}/${tk.path}?t=${Date.now()}`;
                      const tkVoice = tk.voice || 'default';
                      const dur = (tk.duration_seconds || 0).toFixed(1);
                      return `
                        <div style="flex:0 0 160px; background:${isAct ? '#081a38' : '#03060d'}; border:1px solid ${isAct ? '#3b82f6' : '#1e293b'}; border-radius:4px; padding:5px 6px; display:flex; flex-direction:column; gap:4px;">
                          <div style="display:flex; justify-content:space-between; align-items:center; font-size:9px; font-weight:700;">
                            <span style="color:${isAct ? '#93c5fd' : '#cbd5e1'};">Take #${tk.take}</span>
                            ${isAct ? '<span style="background:#10b981; color:#fff; font-size:7px; font-weight:700; padding:0 3px; border-radius:2px;">ACTIVE</span>' : ''}
                          </div>
                          <div style="font-size:8px; color:#94a3b8; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                            Voice: <b style="color:#cbd5e1;">${tkVoice}</b> | <b>${dur}s</b>
                          </div>
                          <audio controls src="${tkSrc}" style="width:100%; height:24px;"></audio>
                          <button class="btn-sec" style="font-size:8px; padding:2px 4px; width:100%; font-weight:600; ${isAct ? 'background:#059669; border-color:#10b981; color:#fff;' : 'background:#1e3a8a; border-color:#3b82f6; color:#fff;'}" onclick="switchSceneVoiceTakeDirect(${s.scene_id}, ${tk.take})">
                            ${isAct ? '✓ In Video' : '👉 Select'}
                          </button>
                        </div>
                      `;
                    }).join('')}
                  </div>
                ` : `
                  ${aSrc ? `<audio controls src="${aSrc}" style="height:30px; max-width:240px;"></audio>` : '<span style="font-size: 12px; color:#f59e0b;">⏳ No voice audio generated yet</span>'}
                `}
              </div>
            </div>
          `;
        });
        bodyHtml += `</div>`;
        actionButtons = `
          <button class="btn-sec" onclick="runSingleStage('voice')">▶ Re-run Voice Stage Only</button>
          <button class="btn-primary" style="background: linear-gradient(135deg, #059669 0%, #047857 100%); font-weight: 700;" onclick="closeStageInspector(); openRerenderVoiceModal();">🎙️🔄 Re-render Voice & Update Final Video</button>
        `;
      } else if (stageName === 'music') {
        const plan = data.music_plan || [];
        const mSettings = data.music_settings || {};
        const availTracks = data.available_tracks || [];
        const totalDur = data.total_duration || 0;
        const topic = data.topic || '';

        const movementNames = [
          { title: "Movement 1: 引言與氛圍鋪墊 (Opening Context & Atmosphere)", defaultEnergy: "LOW / MID", desc: "引導觀眾進入紀錄片核心主題，營造沉浸式宏觀背景氣氛。" },
          { title: "Movement 2: 深入探討與張力起伏 (Deep Dive & Rising Stakes)", defaultEnergy: "MID / HIGH", desc: "隨劇情深入探討核心衝突、技術困境或調查轉折，節奏張力遞增。" },
          { title: "Movement 3: 終章昇華與未來啟示 (Outlook & Climax Resolution)", defaultEnergy: "HIGH / UPLIFTING", desc: "收尾結語、總結思考與願景展望，激昂或沉穩昇華觀眾情緒。" }
        ];
        const currentVibe = data.current_vibe || (mSettings && mSettings.vibe) || 'auto';

        bodyHtml = `
          <!-- Ambient Music Overview Card in Inspector -->
          <div style="background: linear-gradient(135deg, rgba(14, 27, 49, 0.95) 0%, rgba(10, 15, 30, 0.95) 100%); border: 1px solid rgba(59, 130, 246, 0.35); border-radius: 10px; padding: 18px 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 12px;">
              <div>
                <div style="font-size: 16px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px;">
                  <span>🎶</span> 紀錄片背景配樂與音軌管理 (Ambient Music Studio)
                </div>
                <div style="font-size: 12.5px; color: #94a3b8; margin-top: 5px;">
                  主題：<b style="color: #60a5fa;">${topic || '紀錄片主題'}</b> | 總片長：<b style="color: #cbd5e1;">${totalDur > 0 ? totalDur.toFixed(1) + 's' : '自動估算中'}</b> | 目前樂章數：<b style="color: #34d399;">${plan.length}</b>
                </div>
              </div>
              <div style="display: flex; gap: 8px;">
                <button class="btn-sec" onclick="reMatchInspectorMusicVibe()" style="font-size: 12px; padding: 6px 14px; background: rgba(59,130,246,0.15); border: 1px solid #3b82f6; color: #93c5fd; font-weight: 600;">🎲 依風格重新匹配</button>
              </div>
            </div>

            <!-- Vibe Override -->
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding-top: 10px; border-top: 1px solid rgba(59, 130, 246, 0.2);">
              <label style="font-size: 12.5px; font-weight: 700; color: #cbd5e1; margin: 0; display: flex; align-items: center; gap: 5px;">
                <span>🎭</span> 配樂基調 (Music Vibe):
              </label>
              <select id="insp-music-vibe-select" style="min-width: 240px; padding: 6px 12px; font-size: 12px; border-radius: var(--radius-sm); background: #040814; color: #60a5fa; border: 1px solid #3b82f6; font-weight: 600;" onchange="onInspectorMusicVibeChange(this.value)">
                <option value="auto" ${(!currentVibe || currentVibe === 'auto') ? 'selected' : ''}>🤖 自動語意推論 (Auto Semantic Grounding)</option>
                <option value="tech_futuristic" ${currentVibe === 'tech_futuristic' ? 'selected' : ''}>🔬 科技未來 (Tech & Sci-Fi)</option>
                <option value="cinematic_documentary" ${currentVibe === 'cinematic_documentary' ? 'selected' : ''}>🏛️ 歷史紀錄 (Cinematic Documentary)</option>
                <option value="dramatic_tension" ${currentVibe === 'dramatic_tension' ? 'selected' : ''}>⚡ 衝突危機 (Dramatic Tension)</option>
                <option value="mystery_cosmic" ${currentVibe === 'mystery_cosmic' ? 'selected' : ''}>🌌 宇宙未解 (Dark Mystery & Space)</option>
                <option value="uplifting_inspirational" ${currentVibe === 'uplifting_inspirational' ? 'selected' : ''}>✨ 勵志突破 (Uplifting & Wonder)</option>
                <option value="calm_focus" ${currentVibe === 'calm_focus' ? 'selected' : ''}>🧘 平靜沉思 (Calm & Focus)</option>
              </select>
            </div>
          </div>
        `;

        if (!plan.length) {
          bodyHtml += `
            <div style="text-align: center; padding: 50px 20px; background: #080d16; border: 1px dashed rgba(124, 145, 182, 0.3); border-radius: 8px;">
              <div style="font-size: 32px; margin-bottom: 12px;">🎶</div>
              <h4 style="color: #fff; margin: 0 0 8px 0;">尚未規劃配樂時間軸</h4>
              <p style="font-size: 13px; color: var(--text-muted); max-width: 460px; margin: 0 auto 16px auto;">
                點擊下方按鈕，系統將自動為影片引言、探討、結尾三段匹配高音質背景音樂並計算交叉淡入淡出。
              </p>
              <button class="btn-primary" onclick="runSingleStage('music')">▶ 立即規劃環境配樂 (Plan Ambient Music)</button>
            </div>
          `;
        } else {
          bodyHtml += `<div style="display: flex; flex-direction: column; gap: 14px;">`;
          plan.forEach((seg, idx) => {
            const mvMeta = movementNames[idx] || { title: `Movement ${idx + 1}`, defaultEnergy: "MID" };
            const dur = (seg.end_time - seg.start_time).toFixed(1);

            let trackOptionsHtml = '';
            availTracks.forEach(tr => {
              const isSelected = (tr.name === seg.name || tr.path.endsWith(seg.name));
              trackOptionsHtml += `<option value="${tr.path}" data-url="${tr.url}" data-cat="${tr.category}" ${isSelected ? 'selected' : ''}>[${tr.category}] ${tr.name}</option>`;
            });

            bodyHtml += `
              <div style="background: #080d16; border: 1px solid rgba(124, 145, 182, 0.2); border-radius: 8px; padding: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; margin-bottom: 10px;">
                  <div>
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                      <span style="font-size: 14px; font-weight: 700; color: #fff;">${mvMeta.title}</span>
                      <span style="font-size: 11px; background: rgba(59,130,246,0.15); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3); border-radius: 4px; padding: 2px 6px;">${seg.category || 'auto'}</span>
                      <span style="font-size: 11px; background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); border-radius: 4px; padding: 2px 6px;">⚡ 能量: ${mvMeta.defaultEnergy}</span>
                    </div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                      時間範圍：<b style="color: #93c5fd;">${seg.start_time.toFixed(1)}s ➔ ${seg.end_time.toFixed(1)}s</b> (${dur}s) | 淡入: ${seg.crossfade_in || 2}s | 淡出: ${seg.crossfade_out || 2}s
                    </div>
                  </div>
                  <div style="font-size: 12px; color: #a7f3d0; background: rgba(5,150,105,0.15); border: 1px solid #059669; border-radius: 4px; padding: 3px 8px;">
                    🔊 音量: <b>${seg.volume_db || -16} dB</b>
                  </div>
                </div>

                <!-- Audio Preview Player -->
                <div style="background: #04070e; border: 1px solid #1e293b; border-radius: 6px; padding: 10px 12px; margin-bottom: 12px;">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 12px; font-weight: 600; color: #cbd5e1;">🎧 當前選定曲目：<b id="insp-music-name-${idx}" style="color: #60a5fa;">${seg.name}</b></span>
                  </div>
                  <audio id="insp-music-audio-${idx}" controls src="${seg.audio_url || ''}" style="width: 100%; height: 32px;"></audio>
                </div>

                <!-- Track Selector & Controls -->
                <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                  <label style="font-size: 12px; font-weight: 600; color: #94a3b8; margin: 0;">更換此樂章曲目：</label>
                  <select id="insp-music-select-${idx}" style="flex: 1; min-width: 260px; padding: 6px 10px; font-size: 12px; border-radius: var(--radius-sm); background: var(--bg-canvas); color: var(--text-primary); border: 1px solid var(--border-muted);" onchange="onInspectorMusicTrackChange(${idx}, this)">
                    ${trackOptionsHtml}
                  </select>
                  <button type="button" class="btn-sec" onclick="openStudioClassicalPicker(${idx})" style="padding: 6px 12px; font-size: 12px; font-weight: 700; color: #f59e0b; border-color: #f59e0b; background: rgba(245,158,11,0.1); cursor: pointer;" title="從 OpenOpus 古典名曲曲庫中挑選並指定至此樂章">
                    🏛️ 選用古典名曲
                  </button>
                </div>

                <!-- Start Offset Scrubber -->
                <div style="display: flex; align-items: center; gap: 8px; margin-top: 8px; flex-wrap: wrap; background: #050a14; padding: 6px 10px; border-radius: 6px; border: 1px solid rgba(59,130,246,0.2);">
                  <label style="font-size: 12px; font-weight: 600; color: #93c5fd; margin: 0;">⏱️ 起播偏移 (Start Offset):</label>
                  <input type="number" id="insp-music-offset-${idx}" min="0" step="1" value="${seg.start_offset || 0}" style="width: 80px; padding: 4px 8px; font-size: 12px; border-radius: 4px; background: #040814; color: #60a5fa; border: 1px solid #3b82f6; font-weight: 700;" onchange="onInspectorMusicOffsetChange(${idx}, this.value)" placeholder="0">
                  <span style="font-size: 11px; color: #64748b;">秒 (跳過引言靜音或切換至高潮片段)</span>
                </div>
              </div>
            `;
          });
          bodyHtml += `</div>`;
        }

        actionButtons = `
          <button class="btn-sec" onclick="runSingleStage('music')">▶ 重新規劃配樂 (Re-Plan Music)</button>
          <button class="btn-primary" style="background: linear-gradient(135deg, #059669 0%, #047857 100%); font-weight: 700;" onclick="saveInspectedStage('music')">💾 儲存配樂變更 (Save Music Plan)</button>
        `;

      } else if (stageName === 'animation') {
        const scenes = data.scenes || [];
        if (isDrama) {
          bodyHtml = `
            <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
              <div>
                <div style="font-size: 13.5px; font-weight: 800; color: #fbbf24; display: flex; align-items: center; gap: 8px;">
                  <span>👄</span> <span>Hedra AI 角色精確對嘴與面部微表情工作室 (Lip Sync)</span>
                </div>
                <div style="font-size: 11.5px; color: #94a3b8; margin-top: 3px;">
                  取消傳統 Ken Burns 運鏡；以 Hedra Character-2 驅動角色對嘴與生動呼吸微表情。
                </div>
              </div>
              <div style="display: flex; gap: 8px; align-items: center;">
                <button class="btn-sec" style="font-size: 11.5px; padding: 5px 12px; border-color: #d97706; color: #fbbf24;" onclick="checkDramaHedraStatus()">
                  🔑 檢測 Hedra 連線狀態
                </button>
              </div>
            </div>
            <div style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">分鏡角色口型對齊預覽與微調：</div>
            <div style="display:flex; flex-direction:column; gap:12px;">
          `;
          scenes.forEach((s, idx) => {
            const hasVid = s.video && s.video.path;
            const vSrc = hasVid ? `/media/${currentProjectId}/${s.video.path}?t=${Date.now()}` : '';
            const hasAudio = s.audio && s.audio.path;
            const aSrc = hasAudio ? `/media/${currentProjectId}/${s.audio.path}?t=${Date.now()}` : '';
            const charName = s.character || s.speaker || '主演';

            bodyHtml += `
              <div style="background:#080d16; border:1px solid var(--card-border); border-radius:8px; padding:12px; display:flex; flex-direction:column; gap:8px;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                  <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-weight:700; color:#93c5fd;">Scene #${s.scene_id}</span>
                    <span style="background:rgba(245, 158, 11, 0.2); border:1px solid #d97706; color:#fbbf24; font-size:11px; font-weight:700; padding:1px 6px; border-radius:4px;">👤 ${charName}</span>
                  </div>
                  <span style="font-size:11px; font-weight:700; color:${hasVid ? '#34d399' : '#f59e0b'};">
                    ${hasVid ? '✓ 口型對嘴已合成' : '⏳ 等待對嘴生成'}
                  </span>
                </div>
                <div style="font-size:12px; color:#cbd5e1; background:#04070e; border:1px solid #1e293b; padding:6px 10px; border-radius:4px;">
                  "${escapeHtml(s.narration || '')}"
                </div>
                <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
                  ${aSrc ? `
                    <div style="flex:1; min-width:200px;">
                      <span style="font-size:10px; color:#94a3b8; display:block; margin-bottom:2px;">🎙️ 對白音頻:</span>
                      <audio controls src="${aSrc}" style="width:100%; height:28px;"></audio>
                    </div>
                  ` : '<div style="font-size:11px; color:#f59e0b;">⏳ 尚未生成對白音頻</div>'}
                  ${vSrc ? `
                    <div style="flex:1; min-width:160px; max-width:220px;">
                      <video controls src="${vSrc}" style="width:100%; max-height:120px; border-radius:4px; background:#000;"></video>
                    </div>
                  ` : ''}
                </div>
                <div style="display:flex; justify-content:flex-end; gap:6px; margin-top:4px;">
                  <button class="btn-sec" style="font-size:11px; padding:4px 10px; background:rgba(245, 158, 11, 0.18); border-color:#d97706; color:#fbbf24; font-weight:700;" onclick="runSingleSceneLipSync(${s.scene_id})">
                    👄 單獨重製對嘴
                  </button>
                </div>
              </div>
            `;
          });
          bodyHtml += `</div>`;
          actionButtons = `
            <button class="btn-sec" onclick="checkDramaHedraStatus()">🔑 檢測 Hedra API</button>
            <button class="btn-primary" onclick="runSingleStage('animation')">▶ Run Hedra Lip-Sync Stage</button>
          `;
        } else {
          // Remotion Motion Graphics & Camera Motion Settings Inspector
          const rem = data.remotion || {
            style: 'modern_tech_explainer',
            theme: 'dark_obsidian',
            density: 'full',
            accentColor: '#A855F7',
            default_style: 'EvidenceHighlightScene'
          };
          if (!inspectedStageData.remotion) inspectedStageData.remotion = Object.assign({}, rem);
          if (!inspectedStageData.animation_model) inspectedStageData.animation_model = data.animation_model || 'remotion';

          const activeStyle = inspectedStageData.remotion.style || 'modern_tech_explainer';
          const activeTheme = inspectedStageData.remotion.theme || 'dark_obsidian';
          const activeDensity = inspectedStageData.remotion.density || 'full';
          const activeAccent = inspectedStageData.remotion.accentColor || '#A855F7';
          const animModel = inspectedStageData.animation_model || 'remotion';

          bodyHtml = `
            <!-- Remotion Visual Style & Preset Suite Card -->
            <div style="background: linear-gradient(135deg, rgba(15,23,42,0.95), rgba(8,9,12,0.98)); border: 1px solid #334155; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
              <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                  <span style="font-size: 16px;">⚛️</span>
                  <span style="font-size: 14px; font-weight: 800; color: #f8fafc;">Remotion 視覺風格與動態圖解體系 (Visual Style Suite)</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <span id="insp-remotion-active-badge" style="font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px; background: ${activeAccent}22; color: ${activeAccent}; border: 1px solid ${activeAccent};">
                    ${activeStyle} · ${activeAccent}
                  </span>
                  <span style="font-size: 11px; background: rgba(0, 245, 255, 0.15); border: 1px solid #00F5FF; color: #00F5FF; font-weight: 700; padding: 3px 8px; border-radius: 12px;">React 19 · Remotion 4.0 · 1080p 60fps</span>
                </div>
              </div>
              <div style="font-size: 11.5px; color: #94a3b8; margin-bottom: 14px; line-height: 1.5;">
                在 Stage 8 動畫算繪階段即時自訂與切換 Remotion 視覺風格體系、畫布主題、圖表密度與主視覺強調色。保存後將直接生效於當前專案之 Stage 8 動畫算繪。
              </div>

              <!-- Style Showcase Grid (7 Presets matching Settings) -->
              <div style="margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                  <span style="font-size: 12px; font-weight: 700; color: #38bdf8;">🖼️ 核心視覺風格展示庫 (點選任一風格卡片立即套用預設)</span>
                  <span style="font-size: 11px; color: #64748b;">7 款大師級專業動態視覺體系</span>
                </div>
                <div id="insp-remotion-showcase-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px;">
                  
                  <!-- Preset 1: Modern Tech Explainer (Gary Chen) -->
                  <div id="insp-card-modern_tech_explainer" onclick="selectInspectorRemotionPreset('modern_tech_explainer')" style="border: ${activeStyle==='modern_tech_explainer' ? '2px solid #a855f7' : '1px solid #1e293b'}; border-radius: 6px; background: #08090c; padding: 10px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStyle==='modern_tech_explainer' ? '0 0 12px rgba(168,85,247,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                      <span style="font-size: 12px; font-weight: 700; color: #f8fafc;">✨ Modern Tech Explainer</span>
                      <span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(168,85,247,0.25); color: #c4b5fd; font-weight: 700;">Gary Chen</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 6px;">
                      <img src="/remotion/style_frameworkmatrix.png" alt="Framework Matrix" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #1e293b;">
                      <img src="/remotion/style_promptcomparison.png" alt="Prompt Comparison" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #1e293b;">
                      <img src="/remotion/style_chatsimulation.png" alt="Chat Simulation" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #1e293b;">
                    </div>
                    <div style="font-size: 10.5px; color: #94a3b8; line-height: 1.3; margin-bottom: 6px;">
                      純黑曜石畫布 · 四象限思維矩陣 · 提示詞策略對比 · AI對話模擬
                    </div>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #1e1b4b; color: #c4b5fd; border: 1px solid #a855f7;">#A855F7 紫</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #0f172a; color: #94a3b8; border: 1px solid #334155;">黑曜石純黑</span>
                    </div>
                  </div>

                  <!-- Preset 2: Coordinate Zero (座標零) -->
                  <div id="insp-card-coordinate_zero" onclick="selectInspectorRemotionPreset('coordinate_zero')" style="border: ${activeStyle==='coordinate_zero' ? '2px solid #0d9488' : '1px solid #1e293b'}; border-radius: 6px; background: #0a1b14; padding: 10px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStyle==='coordinate_zero' ? '0 0 12px rgba(13,148,136,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                      <span style="font-size: 12px; font-weight: 700; color: #f8fafc;">🧭 Coordinate Zero</span>
                      <span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(13,148,136,0.25); color: #5eead4; font-weight: 700;">座標零</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 6px;">
                      <img src="/remotion/style_coordinate_scale.png" alt="Coordinate Scale" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #163c2e;">
                      <img src="/remotion/style_coordinate_experiment.png" alt="Coordinate Experiment" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #163c2e;">
                      <img src="/remotion/style_coordinate_split.png" alt="Coordinate Split" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #163c2e;">
                    </div>
                    <div style="font-size: 10.5px; color: #94a3b8; line-height: 1.3; margin-bottom: 6px;">
                      墨綠雕刻墊工坊 · 等緯尺度動態縮放 · 垂直對數倍率尺規 · 各對一半
                    </div>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #134e4a; color: #5eead4; border: 1px solid #0d9488;">#0D9488 湖綠</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #064e3b; color: #a7f3d0; border: 1px solid #047857;">墨綠雕刻墊</span>
                    </div>
                  </div>

                  <!-- Preset 3: Tactile Blueprint (科技藍圖) -->
                  <div id="insp-card-tactile_blueprint" onclick="selectInspectorRemotionPreset('tactile_blueprint')" style="border: ${activeStyle==='tactile_blueprint' ? '2px solid #00F5FF' : '1px solid #1e293b'}; border-radius: 6px; background: #070e1b; padding: 10px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStyle==='tactile_blueprint' ? '0 0 12px rgba(0,245,255,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                      <span style="font-size: 12px; font-weight: 700; color: #f8fafc;">⚛️ Tactile Blueprint</span>
                      <span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(0,245,255,0.2); color: #00F5FF; font-weight: 700;">科技藍圖</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 6px;">
                      <img src="/remotion/style_branchpathway.png" alt="Branch Pathway" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #1e293b;">
                      <img src="/remotion/style_leadercallout.png" alt="Leader Callout" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #1e293b;">
                      <img src="/remotion/style_scalecompare.png" alt="Scale Compare" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #1e293b;">
                    </div>
                    <div style="font-size: 10.5px; color: #94a3b8; line-height: 1.3; margin-bottom: 6px;">
                      深藍工程網格 · 多路徑排除分支 · HUD動態引線 · 20X微米放大鏡
                    </div>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #082f49; color: #00F5FF; border: 1px solid #0284c7;">#00F5FF 藍圖青</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #0369a1; color: #e0f2fe; border: 1px solid #0284c7;">工程網格</span>
                    </div>
                  </div>

                  <!-- Preset 4: fOx Hsiao Documentary (調查紀錄片) -->
                  <div id="insp-card-fox_documentary" onclick="selectInspectorRemotionPreset('fox_documentary')" style="border: ${activeStyle==='fox_documentary' ? '2px solid #38bdf8' : '1px solid #1e293b'}; border-radius: 6px; background: #0f172a; padding: 10px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStyle==='fox_documentary' ? '0 0 12px rgba(56,189,248,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                      <span style="font-size: 12px; font-weight: 700; color: #f8fafc;">📌 fOx Hsiao Documentary</span>
                      <span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(56,189,248,0.2); color: #38bdf8; font-weight: 700;">調查紀錄片</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 6px;">
                      <img src="/remotion/style_foxheader.png" alt="Fox Header" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #1e293b;">
                      <img src="/remotion/style_foxmetric.png" alt="Fox Metric" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #1e293b;">
                      <img src="/remotion/style_foxtimeline.png" alt="Fox Timeline" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #1e293b;">
                    </div>
                    <div style="font-size: 10.5px; color: #94a3b8; line-height: 1.3; margin-bottom: 6px;">
                      高通透毛玻璃 · 85%底圖保留 · 96px巨型指標 · 年代歷程滑軌
                    </div>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #075985; color: #38bdf8; border: 1px solid #0284c7;">#38BDF8 天藍</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #1e293b; color: #94a3b8; border: 1px solid #334155;">毛玻璃遮罩</span>
                    </div>
                  </div>

                  <!-- Preset 5: Finance & Market Explainer (財經趨勢) -->
                  <div id="insp-card-finance_market" onclick="selectInspectorRemotionPreset('finance_market')" style="border: ${activeStyle==='finance_market' ? '2px solid #10b981' : '1px solid #1e293b'}; border-radius: 6px; background: #091319; padding: 10px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStyle==='finance_market' ? '0 0 12px rgba(16,185,129,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                      <span style="font-size: 12px; font-weight: 700; color: #f8fafc;">📈 Finance & Market</span>
                      <span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(16,185,129,0.25); color: #34d399; font-weight: 700;">財經趨勢</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 6px;">
                      <img src="/remotion/style_finance_candlestick.png" alt="Finance Candlestick" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #134e4a;">
                      <img src="/remotion/style_finance_metrics.png" alt="Finance Metrics" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #134e4a;">
                      <img src="/remotion/style_foxmetric.png" alt="Market Metric" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #134e4a;">
                    </div>
                    <div style="font-size: 10.5px; color: #94a3b8; line-height: 1.3; margin-bottom: 6px;">
                      即時走勢K線 · 支撐壓力位動態標記 · 財務營運利差對比 · 突破放量摘要
                    </div>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #064e3b; color: #34d399; border: 1px solid #10b981;">#10B981 漲綠</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #0f172a; color: #38bdf8; border: 1px solid #0284c7;">深灰金融網格</span>
                    </div>
                  </div>

                  <!-- Preset 6: Archival History & Chronicles (歷史編年) -->
                  <div id="insp-card-archival_history" onclick="selectInspectorRemotionPreset('archival_history')" style="border: ${activeStyle==='archival_history' ? '2px solid #c2410c' : '1px solid #1e293b'}; border-radius: 6px; background: #1c1511; padding: 10px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStyle==='archival_history' ? '0 0 12px rgba(194,65,12,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                      <span style="font-size: 12px; font-weight: 700; color: #f8fafc;">📜 Archival History</span>
                      <span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(194,65,12,0.25); color: #fb923c; font-weight: 700;">歷史編年</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 6px;">
                      <img src="/remotion/style_archival_document.png" alt="Archival Document" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #431407;">
                      <img src="/remotion/style_history_chronology.png" alt="History Chronology" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #431407;">
                      <img src="/remotion/style_evidencehighlight.png" alt="Evidence Highlight" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #431407;">
                    </div>
                    <div style="font-size: 10.5px; color: #94a3b8; line-height: 1.3; margin-bottom: 6px;">
                      復古羊皮紙質 · 機密歷史檔案引言 · 紅色官印動態戳記 · 年代編年推進
                    </div>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #431407; color: #fb923c; border: 1px solid #c2410c;">#C2410C 印戳紅</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #292524; color: #d6d3d1; border: 1px solid #78716c;">羊皮紙復古紋</span>
                    </div>
                  </div>

                  <!-- Preset 7: Vox Investigative Journalism (Vox 深度調查) -->
                  <div id="insp-card-vox_journalism" onclick="selectInspectorRemotionPreset('vox_journalism')" style="border: ${activeStyle==='vox_journalism' ? '2px solid #facc15' : '1px solid #1e293b'}; border-radius: 6px; background: #16150a; padding: 10px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStyle==='vox_journalism' ? '0 0 12px rgba(250,204,21,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                      <span style="font-size: 12px; font-weight: 700; color: #f8fafc;">🗞️ Vox Journalism</span>
                      <span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(250,204,21,0.25); color: #fde047; font-weight: 700;">Vox 調查</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 6px;">
                      <img src="/remotion/style_vox_splitscreen.png" alt="Vox Split Screen" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #36300a;">
                      <img src="/remotion/style_vox_keystat.png" alt="Vox Key Stat" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #36300a;">
                      <img src="/remotion/style_foxheader.png" alt="Editorial Header" style="width: 100%; height: 42px; object-fit: cover; border-radius: 3px; border: 1px solid #36300a;">
                    </div>
                    <div style="font-size: 10.5px; color: #94a3b8; line-height: 1.3; margin-bottom: 6px;">
                      Vox招牌黃黑對比 · 承諾與現實政策雙分割對照 · 140px巨型震撼數據 · 螢光畫線
                    </div>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #36300a; color: #fde047; border: 1px solid #facc15;">#FACC15 亮黃</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: #0a0a0c; color: #cbd5e1; border: 1px solid #334155;">高對比炭黑</span>
                    </div>
                  </div>

                </div>
              </div>

              <!-- Core Controls Form Grid -->
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; background: rgba(0,0,0,0.3); padding: 12px; border-radius: 6px; border: 1px solid #1e293b;">
                <!-- 1. Style Dropdown -->
                <div>
                  <label style="display: block; font-size: 11px; font-weight: 700; color: #cbd5e1; margin-bottom: 4px;">風格體系 (remotion.style)</label>
                  <select id="insp-remotion-style" onchange="onInspectorRemotionChange()" style="width: 100%; font-size: 11.5px; padding: 6px; background: #060b16; border: 1px solid #334155; color: #f8fafc; border-radius: 4px;">
                    <option value="modern_tech_explainer" ${activeStyle==='modern_tech_explainer'?'selected':''}>Modern Tech Explainer (Gary Chen)</option>
                    <option value="coordinate_zero" ${activeStyle==='coordinate_zero'?'selected':''}>Coordinate Zero (座標零 桌面實驗)</option>
                    <option value="tactile_blueprint" ${activeStyle==='tactile_blueprint'?'selected':''}>Tactile Blueprint (硬核科技藍圖)</option>
                    <option value="fox_documentary" ${activeStyle==='fox_documentary'?'selected':''}>fOx Hsiao Documentary (調查紀錄片)</option>
                    <option value="finance_market" ${activeStyle==='finance_market'?'selected':''}>Finance & Market (財經趨勢與K線)</option>
                    <option value="archival_history" ${activeStyle==='archival_history'?'selected':''}>Archival History (歷史編年檔案)</option>
                    <option value="vox_journalism" ${activeStyle==='vox_journalism'?'selected':''}>Vox Journalism (Vox 深度調查)</option>
                  </select>
                </div>

                <!-- 2. Canvas Theme Dropdown -->
                <div>
                  <label style="display: block; font-size: 11px; font-weight: 700; color: #cbd5e1; margin-bottom: 4px;">畫布主題 (remotion.theme)</label>
                  <select id="insp-remotion-theme" onchange="onInspectorRemotionChange()" style="width: 100%; font-size: 11.5px; padding: 6px; background: #060b16; border: 1px solid #334155; color: #f8fafc; border-radius: 4px;">
                    <option value="dark_obsidian" ${activeTheme==='dark_obsidian'?'selected':''}>Dark Obsidian (純黑曜石畫布)</option>
                    <option value="green_cutting_mat" ${activeTheme==='green_cutting_mat'?'selected':''}>Green Cutting Mat (墨綠雕刻墊)</option>
                    <option value="blueprint_grid" ${activeTheme==='blueprint_grid'?'selected':''}>Blueprint Grid (深藍工程網格)</option>
                    <option value="translucent_overlay" ${activeTheme==='translucent_overlay'?'selected':''}>Translucent Overlay (毛玻璃遮罩)</option>
                    <option value="finance_grid" ${activeTheme==='finance_grid'?'selected':''}>Finance Grid (深灰金融盤勢)</option>
                    <option value="parchment_paper" ${activeTheme==='parchment_paper'?'selected':''}>Parchment Paper (古典羊皮紙)</option>
                    <option value="vox_charcoal" ${activeTheme==='vox_charcoal'?'selected':''}>Vox Charcoal (高對比炭黑)</option>
                  </select>
                </div>

                <!-- 3. Density Dropdown -->
                <div>
                  <label style="display: block; font-size: 11px; font-weight: 700; color: #cbd5e1; margin-bottom: 4px;">覆蓋密度 (remotion.density)</label>
                  <select id="insp-remotion-density" onchange="onInspectorRemotionChange()" style="width: 100%; font-size: 11.5px; padding: 6px; background: #060b16; border: 1px solid #334155; color: #f8fafc; border-radius: 4px;">
                    <option value="full" ${activeDensity==='full'?'selected':''}>full (100% 全程 Remotion 動態圖表)</option>
                    <option value="half" ${activeDensity==='half'?'selected':''}>half (50% 實景圖片 + 50% 動態圖表)</option>
                    <option value="rich" ${activeDensity==='rich'?'selected':''}>rich (豐富模式 · ~40% 關鍵圖卡)</option>
                    <option value="balanced" ${activeDensity==='balanced'?'selected':''}>balanced (平衡模式 · ~25% 核心轉折)</option>
                    <option value="minimal" ${activeDensity==='minimal'?'selected':''}>minimal (精簡模式 · ~10% 章節標題)</option>
                  </select>
                </div>

                <!-- 4. Accent Color -->
                <div>
                  <label style="display: block; font-size: 11px; font-weight: 700; color: #cbd5e1; margin-bottom: 4px;">主視覺強調色 (accentColor)</label>
                  <div style="display: flex; align-items: center; gap: 6px;">
                    <input type="color" id="insp-remotion-accent-picker" value="${activeAccent}" onchange="onInspectorRemotionAccentChange(this.value)" style="width: 32px; height: 32px; padding: 1px; border: 1px solid #334155; border-radius: 4px; background: #060b16; cursor: pointer;">
                    <input type="text" id="insp-remotion-accent-hex" value="${activeAccent}" maxlength="7" oninput="onInspectorRemotionAccentHexInput(this.value)" style="flex: 1; padding: 6px 8px; background: #060b16; border: 1px solid #334155; color: #f8fafc; border-radius: 4px; font-size: 11.5px; font-family: monospace; font-weight: 700; text-transform: uppercase;">
                  </div>
                </div>

                <!-- 5. Stage 8 Animation Model / Provider -->
                <div>
                  <label style="display: block; font-size: 11px; font-weight: 700; color: #cbd5e1; margin-bottom: 4px;">Stage 8 算繪模式 (Stage Provider)</label>
                  <select id="insp-remotion-model" onchange="inspectedStageData.animation_model=this.value" style="width: 100%; font-size: 11.5px; padding: 6px; background: #060b16; border: 1px solid #334155; color: #f8fafc; border-radius: 4px;">
                    <option value="remotion" ${animModel==='remotion'||animModel==='motion_graphics'?'selected':''}>⚛️ AI Motion Graphics Director (自動智能配鏡)</option>
                    <option value="remotion_coordinate_scale" ${animModel==='remotion_coordinate_scale'?'selected':''}>🧭 座標零 · 等緯尺度 (Scale)</option>
                    <option value="remotion_coordinate_experiment" ${animModel==='remotion_coordinate_experiment'?'selected':''}>🔬 座標零 · 桌面實驗 (Experiment)</option>
                    <option value="remotion_coordinate_split" ${animModel==='remotion_coordinate_split'?'selected':''}>⚖️ 座標零 · 各對一半 (Split)</option>
                    <option value="remotion_finance_candlestick" ${animModel==='remotion_finance_candlestick'?'selected':''}>📈 財經趨勢 · 走勢K線 (Candlestick)</option>
                    <option value="remotion_finance_metrics" ${animModel==='remotion_finance_metrics'?'selected':''}>📊 財經趨勢 · 財務指標 (Metrics)</option>
                    <option value="remotion_archival_doc" ${animModel==='remotion_archival_doc'?'selected':''}>📜 歷史檔案 · 解密文檔 (Archival)</option>
                    <option value="remotion_history_chrono" ${animModel==='remotion_history_chrono'?'selected':''}>⏳ 歷史檔案 · 年代編年 (Timeline)</option>
                    <option value="remotion_vox_split" ${animModel==='remotion_vox_split'?'selected':''}>🗞️ Vox調查 · 政策雙分割 (Vox Split)</option>
                    <option value="remotion_vox_keystat" ${animModel==='remotion_vox_keystat'?'selected':''}>⚡ Vox調查 · 核心數據 (Vox Stat)</option>
                    <option value="remotion_evidence" ${animModel==='remotion_evidence'?'selected':''}>📑 科技藍圖 · 文獻劃記 (Highlight)</option>
                    <option value="remotion_pathway" ${animModel==='remotion_pathway'?'selected':''}>🔀 科技藍圖 · 分支決策 (Pathway)</option>
                    <option value="remotion_callout" ${animModel==='remotion_callout'?'selected':''}>🎯 科技藍圖 · HUD引線 (Callout)</option>
                    <option value="remotion_scale" ${animModel==='remotion_scale'?'selected':''}>🔬 科技藍圖 · 尺度對比 (Loupe)</option>
                    <option value="ken_burns" ${animModel==='ken_burns'?'selected':''}>📷 Ken Burns 靜態鏡頭縮放 (純圖片)</option>
                  </select>
                </div>
              </div>
            </div>

            <!-- Scene Camera Motion & Animation Status Grid -->
            <div style="font-size:13px; font-weight:800; color:#93c5fd; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
              <span>🎬 分鏡鏡頭運鏡與動畫狀態 (${scenes.length} 個分鏡)</span>
              <span style="font-size:11px; font-weight:normal; color:var(--text-muted);">包含 Remotion 動態卡片與 Ken Burns 鏡頭預覽</span>
            </div>
            <div style="display:flex; flex-direction:column; gap:10px;">
          `;
          scenes.forEach((s, idx) => {
            const hasAnimClip = Boolean(s.has_animation || (s.animation && s.animation.status === 'COMPLETED' && s.animation.path));
            const videoPath = (s.animation && s.animation.path) || `animation/${s.tag || ('scene_' + String(s.scene_id).padStart(3, '0'))}.mp4`;
            const vSrc = hasAnimClip ? `/media/${currentProjectId}/${videoPath}` : '';
            const imgPath = (s.image && s.image.path) || `images/${s.tag || ('scene_' + String(s.scene_id).padStart(3, '0'))}.png`;
            const imgSrc = `/media/${currentProjectId}/${imgPath}`;
            const animMeta = (s.animation && s.animation.meta) || {};
            const compLabel = s.remotion_composition || animMeta.composition || animMeta.sceneType || '';
            const isRem = Boolean(s.is_remotion || compLabel || animMeta.provider === 'remotion');

            bodyHtml += `
              <div style="background:#080d16; border:1px solid ${isRem ? '#1e3a8a' : 'var(--card-border)'}; border-radius:6px; padding:10px 12px; display:flex; flex-direction:column; gap:8px;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                  <div style="display:flex; align-items:center; gap:6px;">
                    <span style="font-weight:700; color:#93c5fd; font-size:12px;">Scene #${s.scene_id}</span>
                    ${compLabel ? `<span style="font-size:10px; padding:1px 6px; border-radius:3px; background:rgba(0,245,255,0.15); color:#00F5FF; border:1px solid rgba(0,245,255,0.4);">⚛️ ${escapeHtml(compLabel)}</span>` : `<span style="font-size:10px; padding:1px 6px; border-radius:3px; background:#1e293b; color:#94a3b8;">📷 Ken Burns</span>`}
                    ${hasAnimClip ? `<span style="font-size:10px; padding:1px 6px; border-radius:3px; background:rgba(16,185,129,0.15); color:#34d399; border:1px solid #059669;">✓ Clip Ready</span>` : `<span style="font-size:10px; padding:1px 6px; border-radius:3px; background:rgba(245,158,11,0.15); color:#fbbf24; border:1px solid #d97706;">⏳ 待算繪</span>`}
                  </div>
                  <div style="display:flex; gap:6px; align-items:center;">
                    <select style="font-size:11.5px; padding:3px 6px; background:#060b16; border:1px solid #334155; color:#cbd5e1; border-radius:4px;" onchange="inspectedStageData.scenes[${idx}].camera_motion=this.value">
                      <option value="slow_zoom_in" ${s.camera_motion==='slow_zoom_in'?'selected':''}>Zoom In (慢推)</option>
                      <option value="slow_zoom_out" ${s.camera_motion==='slow_zoom_out'?'selected':''}>Zoom Out (慢拉)</option>
                      <option value="pan_left" ${s.camera_motion==='pan_left'?'selected':''}>Pan Left (左移)</option>
                      <option value="pan_right" ${s.camera_motion==='pan_right'?'selected':''}>Pan Right (右移)</option>
                      <option value="static" ${s.camera_motion==='static'?'selected':''}>Static (靜止)</option>
                    </select>
                    ${hasAnimClip ? `<a href="${vSrc}" target="_blank" class="btn-sec" style="font-size:10.5px; padding:3px 7px; text-decoration:none; display:inline-flex; align-items:center; gap:3px; color:#38bdf8;">▶ 全螢幕</a>` : ''}
                  </div>
                </div>

                <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                  ${hasAnimClip ? `
                    <div style="flex-shrink:0; width:160px; aspect-ratio:16/9; border-radius:4px; overflow:hidden; background:#000; border:1px solid #1e293b;">
                      <video controls preload="metadata" playsinline src="${vSrc}" poster="${imgSrc}" style="width:100%; height:100%; object-fit:contain; display:block;"></video>
                    </div>
                  ` : `
                    <div style="flex-shrink:0; width:160px; aspect-ratio:16/9; border-radius:4px; overflow:hidden; background:#000; border:1px dashed #334155; position:relative;">
                      <img src="${imgSrc}" onerror="this.style.display='none'" style="width:100%; height:100%; object-fit:cover; opacity:0.7;">
                    </div>
                  `}
                  <div style="flex:1; min-width:180px; font-size:11.5px; color:#cbd5e1; line-height:1.4; background:#04070e; border:1px solid #1e293b; padding:6px 8px; border-radius:4px;">
                    ${escapeHtml(s.narration || '（無旁白）')}
                  </div>
                </div>
              </div>
            `;
          });
          bodyHtml += `</div>`;
          actionButtons = `
            <button class="btn-sec" onclick="saveInspectedStage('animation')">💾 保存風格與分鏡設定</button>
            <button class="btn-primary" onclick="saveInspectedStage('animation', false).then(() => runSingleStage('animation'))">▶ 保存並執行動畫算繪</button>
          `;
        }
      } else if (stageName === 'subtitles') {
        const srtText = data.srt || '';
        const motionEnabled = data.motion_graphics_callouts !== false;
        const calloutsList = data.callouts_preview || [];
        let calloutsHtml = '';
        if (calloutsList.length > 0 && !isDrama) {
          calloutsHtml = `
            <div style="margin-top: 10px; margin-bottom: 12px; background: #080d1a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px;">
              <div style="font-weight: 700; color: #38bdf8; font-size: 12px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
                <span>🎬 fOx Hsiao 動態重點字卡預覽 (${calloutsList.length} 個):</span>
                <span style="font-size: 11px; color: #94a3b8;">浮動於畫面上方 · 不遮擋字幕</span>
              </div>
              <div style="max-height: 150px; overflow-y: auto; display: flex; flex-direction: column; gap: 5px; padding-right: 4px;">
                ${calloutsList.map(c => `
                  <div style="background: #0f172a; border-left: 3px solid #38bdf8; padding: 5px 8px; border-radius: 4px; font-size: 11px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                      <span style="color: #00F5FF; font-weight: 700; margin-right: 4px;">[${c.tag}]</span>
                      <b style="color: #fff;">${c.title}</b>
                      ${c.subtitle ? `<span style="color: #94a3b8; margin-left: 6px;">— ${c.subtitle}</span>` : ''}
                    </div>
                    <span style="color: #64748b; font-family: monospace; font-size: 10px;">${formatSecondsToMMSS(c.start)} ~ ${formatSecondsToMMSS(c.end)}</span>
                  </div>
                `).join('')}
              </div>
            </div>
          `;
        }
        bodyHtml = `
          <div style="margin-bottom:12px;">
            ${isDrama ? `
              <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 6px; padding: 10px 14px; margin-bottom: 12px; color: #fef3c7; font-size: 12px; display: flex; align-items: center; gap: 8px;">
                <span>📱 <b>9:16 直式短劇專用雙行字幕</b> — 採高對比動態文字排版，居中呈現不遮擋對嘴角色。</span>
              </div>
            ` : `
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; background:#0c1526; padding:10px 14px; border-radius:6px; border:1px solid #1e3a8a;">
                <div>
                  <b style="color:#38bdf8; font-size:13px;">✨ 動態重點字卡特效 (fOx Hsiao 風格)</b>
                  <div style="font-size:11px; color:#94a3b8; margin-top:2px;">根據旁白關鍵詞與指標，在畫面上方自動浮現動態重點字卡（不遮擋下方字幕）</div>
                </div>
                <label style="position:relative; display:inline-block; width:44px; height:24px; margin:0; cursor:pointer;">
                  <input type="checkbox" id="insp-motion-callouts" ${motionEnabled ? 'checked' : ''} onchange="toggleProjectMotionCallouts(this.checked)" style="opacity:0; width:0; height:0;">
                  <span style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:${motionEnabled ? '#0284c7' : '#334155'}; transition:.25s; border-radius:24px;" id="insp-motion-callouts-slider">
                    <span id="insp-motion-callouts-knob" style="position:absolute; height:18px; width:18px; left:${motionEnabled ? '23px' : '3px'}; bottom:3px; background-color:#ffffff; transition:.25s; border-radius:50%; box-shadow:0 1px 3px rgba(0,0,0,0.4);"></span>
                  </span>
                </label>
              </div>
              ${calloutsHtml}
            `}
            <label style="font-weight:600; display:block; margin-bottom:6px;">Subtitles (.srt format):</label>
            <textarea id="insp-srt" style="width:100%; height:260px; font-family:monospace; font-size:12px; background:#080d16; color:#e2e8f0; border:1px solid var(--card-border); padding:10px; border-radius:6px;">${srtText}</textarea>
          </div>
        `;
        actionButtons = `
          <button class="btn-sec" onclick="saveInspectedStage('subtitles')">${isDrama ? 'Save Subtitles' : 'Save Subtitles'}</button>
          <button class="btn-primary" onclick="runSingleStage('subtitles')">${isDrama ? '▶ Re-run Subtitles Stage' : '▶ Re-run Subtitles & Callouts'}</button>
        `;
      } else if (stageName === 'render') {
        const finalRel = data.outputs && data.outputs.final ? data.outputs.final : null;
        const vSrc = finalRel ? `/media/${currentProjectId}/${finalRel}?t=${Date.now()}` : '';
        bodyHtml = `
          <div style="margin-bottom:12px;">
            <div style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">Final video assembly status and preview:</div>
            ${vSrc ? `
              <video controls src="${vSrc}" style="width:100%; max-height:360px; border-radius:6px; background:#000;"></video>
            ` : '<div style="padding:30px; text-align:center; background:#080d16; border-radius:6px; color:var(--text-muted);">No final video rendered yet. Click Render Final 1080p below to assemble the video.</div>'}
          </div>
        `;
        actionButtons = `
          <button class="btn-primary" onclick="runSingleStage('render')">▶ Render Final 1080p Video</button>
        `;
      }

      bodyEl.innerHTML = bodyHtml;
      actionsEl.innerHTML = actionButtons;
    }

    async function saveInspectedStage(stageName, runNextAfter = false) {
      if (!currentProjectId) return;
      let payload = {};
      if (stageName === 'research') {
        const text = document.getElementById('insp-research').value;
        try { payload.research = JSON.parse(text); } catch(e) { payload.research = { notes: text }; }
      } else if (stageName === 'script') {
        payload.script_md = document.getElementById('insp-script-md').value;
      } else if (stageName === 'scenes' || stageName === 'prompts') {
        payload.scenes = inspectedStageData.scenes;
      } else if (stageName === 'animation') {
        payload.scenes = inspectedStageData.scenes;
        if (inspectedStageData.remotion) {
          payload.remotion = inspectedStageData.remotion;
          payload.remotion_style = inspectedStageData.remotion.style;
        }
        if (inspectedStageData.animation_model) {
          payload.animation_model = inspectedStageData.animation_model;
          const mainAnimEl = document.getElementById('model-stage-animation');
          if (mainAnimEl) mainAnimEl.value = inspectedStageData.animation_model;
        }
      } else if (stageName === 'music') {
        payload.music_plan = inspectedStageData.music_plan;
        payload.music_settings = inspectedStageData.music_settings;
      } else if (stageName === 'subtitles') {
        payload.srt = document.getElementById('insp-srt').value;
        const mcEl = document.getElementById('insp-motion-callouts');
        if (mcEl) payload.motion_graphics_callouts = mcEl.checked;
      }

      try {
        await apiRequest(`/api/projects/${currentProjectId}/stage_data/${stageName}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })

        alert("Stage data saved successfully!");
        if (runNextAfter) {
          closeStageInspector();
          runNextStage();
        }
      } catch (e) {
        alert("Error saving: " + e.message);
      }
    }

    
    const INSPECTOR_REMOTION_PRESETS = {
      modern_tech_explainer: {
        name: 'Modern Tech Explainer (Gary Chen)',
        style: 'modern_tech_explainer',
        theme: 'dark_obsidian',
        density: 'full',
        accentColor: '#A855F7',
        borderActive: '#a855f7',
        model: 'remotion'
      },
      coordinate_zero: {
        name: 'Coordinate Zero (座標零)',
        style: 'coordinate_zero',
        theme: 'green_cutting_mat',
        density: 'full',
        accentColor: '#0D9488',
        borderActive: '#0d9488',
        model: 'remotion_coordinate_scale'
      },
      tactile_blueprint: {
        name: 'Tactile Blueprint (科技藍圖)',
        style: 'tactile_blueprint',
        theme: 'blueprint_grid',
        density: 'full',
        accentColor: '#00F5FF',
        borderActive: '#00F5FF',
        model: 'remotion'
      },
      fox_documentary: {
        name: 'fOx Documentary (半透明覆蓋)',
        style: 'fox_documentary',
        theme: 'translucent_overlay',
        density: 'rich',
        accentColor: '#38BDF8',
        borderActive: '#38bdf8',
        model: 'remotion'
      },
      finance_market: {
        name: 'Finance & Market (金融市場)',
        style: 'finance_market',
        theme: 'finance_grid',
        density: 'full',
        accentColor: '#10B981',
        borderActive: '#10b981',
        model: 'remotion_finance_candlestick'
      },
      archival_history: {
        name: 'Archival History (歷史檔案)',
        style: 'archival_history',
        theme: 'parchment_paper',
        density: 'full',
        accentColor: '#C2410C',
        borderActive: '#c2410c',
        model: 'remotion_archival_doc'
      },
      vox_journalism: {
        name: 'Vox Journalism (深度調查)',
        style: 'vox_journalism',
        theme: 'vox_charcoal',
        density: 'full',
        accentColor: '#FACC15',
        borderActive: '#facc15',
        model: 'remotion_vox_split'
      }
    };

    async function selectInspectorRemotionPreset(presetKey) {
      const p = INSPECTOR_REMOTION_PRESETS[presetKey];
      if (!p) return;
      if (!inspectedStageData.remotion) inspectedStageData.remotion = {};
      inspectedStageData.remotion.style = p.style;
      inspectedStageData.remotion.theme = p.theme;
      inspectedStageData.remotion.density = p.density;
      inspectedStageData.remotion.accentColor = p.accentColor;
      if (p.model) inspectedStageData.animation_model = p.model;

      const styleEl = document.getElementById('insp-remotion-style');
      const themeEl = document.getElementById('insp-remotion-theme');
      const densityEl = document.getElementById('insp-remotion-density');
      const pickerEl = document.getElementById('insp-remotion-accent-picker');
      const hexEl = document.getElementById('insp-remotion-accent-hex');
      const modelEl = document.getElementById('insp-remotion-model');

      if (styleEl) styleEl.value = p.style;
      if (themeEl) themeEl.value = p.theme;
      if (densityEl) densityEl.value = p.density;
      if (pickerEl) pickerEl.value = p.accentColor;
      if (hexEl) hexEl.value = p.accentColor;
      if (modelEl && p.model) modelEl.value = p.model;

      updateInspectorRemotionUI();

      if (currentProjectId) {
        try {
          await apiRequest(`/api/projects/${currentProjectId}/stage_data/animation`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              remotion: {
                style: p.style,
                theme: p.theme,
                density: p.density,
                accentColor: p.accentColor,
                default_style: p.default_style || 'CoordinateZeroScaleScene'
              },
              remotion_style: p.style,
              animation_model: p.model || 'remotion'
            })
          });
          showToast(`🧭 已切換 Remotion 風格為「${p.name || p.style}」並已儲存！`);
        } catch (e) {
          console.error('Failed to auto-save inspector remotion preset:', e);
        }
      }
    }

    function onInspectorRemotionChange() {
      if (!inspectedStageData.remotion) inspectedStageData.remotion = {};
      const styleEl = document.getElementById('insp-remotion-style');
      const themeEl = document.getElementById('insp-remotion-theme');
      const densityEl = document.getElementById('insp-remotion-density');
      const hexEl = document.getElementById('insp-remotion-accent-hex');
      const modelEl = document.getElementById('insp-remotion-model');

      if (styleEl) inspectedStageData.remotion.style = styleEl.value;
      if (themeEl) inspectedStageData.remotion.theme = themeEl.value;
      if (densityEl) inspectedStageData.remotion.density = densityEl.value;
      if (hexEl) inspectedStageData.remotion.accentColor = hexEl.value;
      if (modelEl) inspectedStageData.animation_model = modelEl.value;

      updateInspectorRemotionUI();
    }

    function onInspectorRemotionAccentChange(val) {
      if (!inspectedStageData.remotion) inspectedStageData.remotion = {};
      inspectedStageData.remotion.accentColor = val;
      const hexEl = document.getElementById('insp-remotion-accent-hex');
      if (hexEl) hexEl.value = val;
      updateInspectorRemotionUI();
    }

    function onInspectorRemotionAccentHexInput(val) {
      let hex = val.trim();
      if (!hex.startsWith('#')) hex = '#' + hex;
      if (/^#[0-9A-Fa-f]{6}$/.test(hex)) {
        if (!inspectedStageData.remotion) inspectedStageData.remotion = {};
        inspectedStageData.remotion.accentColor = hex;
        const pickerEl = document.getElementById('insp-remotion-accent-picker');
        if (pickerEl) pickerEl.value = hex;
        updateInspectorRemotionUI();
      }
    }

    function updateInspectorRemotionUI() {
      const rem = inspectedStageData.remotion || {};
      const curStyle = rem.style || 'modern_tech_explainer';
      const accent = rem.accentColor || '#A855F7';

      const badge = document.getElementById('insp-remotion-active-badge');
      if (badge) {
        badge.textContent = `${curStyle} · ${accent}`;
        badge.style.color = accent;
        badge.style.borderColor = accent;
        badge.style.background = accent + '22';
      }

      Object.keys(INSPECTOR_REMOTION_PRESETS).forEach(k => {
        const card = document.getElementById('insp-card-' + k);
        if (card) {
          const isSelected = (curStyle === k);
          const p = INSPECTOR_REMOTION_PRESETS[k];
          card.style.border = isSelected ? `2px solid ${p.borderActive}` : '1px solid #1e293b';
          card.style.boxShadow = isSelected ? `0 0 12px ${p.borderActive}55` : 'none';
        }
      });
    }

    window.selectInspectorRemotionPreset = selectInspectorRemotionPreset;

    async function selectStudioRemotionPreset(presetKey) {
      const p = INSPECTOR_REMOTION_PRESETS[presetKey];
      if (!p) return;
      if (!studioStageData.remotion) studioStageData.remotion = {};
      studioStageData.remotion.style = p.style;
      studioStageData.remotion.theme = p.theme;
      studioStageData.remotion.density = p.density;
      studioStageData.remotion.accentColor = p.accentColor;
      if (p.model) studioStageData.animation_model = p.model;

      const styleEl = document.getElementById('studio-remotion-style');
      const themeEl = document.getElementById('studio-remotion-theme');
      const densityEl = document.getElementById('studio-remotion-density');
      const pickerEl = document.getElementById('studio-remotion-accent-picker');
      const hexEl = document.getElementById('studio-remotion-accent-hex');
      const modelEl = document.getElementById('studio-remotion-model');

      if (styleEl) styleEl.value = p.style;
      if (themeEl) themeEl.value = p.theme;
      if (densityEl) densityEl.value = p.density;
      if (pickerEl) pickerEl.value = p.accentColor;
      if (hexEl) hexEl.value = p.accentColor;
      if (modelEl && p.model) modelEl.value = p.model;

      const topModelEl = document.getElementById('stage-card-model-animation');
      if (topModelEl && p.model) topModelEl.value = p.model;
      const mainModelEl = document.getElementById('model-stage-animation');
      if (mainModelEl && p.model) mainModelEl.value = p.model;

      updateStudioRemotionUI();

      if (currentProjectId) {
        try {
          await apiRequest(`/api/projects/${currentProjectId}/stage_data/animation`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              remotion: {
                style: p.style,
                theme: p.theme,
                density: p.density,
                accentColor: p.accentColor,
                default_style: p.default_style || 'CoordinateZeroScaleScene'
              },
              remotion_style: p.style,
              animation_model: p.model || 'remotion'
            })
          });
          if (studioProject && studioProject.settings) {
            if (!studioProject.settings.remotion) studioProject.settings.remotion = {};
            Object.assign(studioProject.settings.remotion, {
              style: p.style,
              theme: p.theme,
              density: p.density,
              accentColor: p.accentColor
            });
            studioProject.settings.remotion_style = p.style;
          }
          showToast(`🧭 已成功切換 Remotion 風格為「${p.name || p.style}」並已儲存！`);
        } catch (e) {
          console.error('Failed to auto-save remotion preset:', e);
          showToast(`⚠️ 風格切換儲存失敗：${e.message}`);
        }
      }
    }

    function onStudioRemotionChange() {
      if (!studioStageData.remotion) studioStageData.remotion = {};
      const styleEl = document.getElementById('studio-remotion-style');
      const themeEl = document.getElementById('studio-remotion-theme');
      const densityEl = document.getElementById('studio-remotion-density');
      const hexEl = document.getElementById('studio-remotion-accent-hex');
      const modelEl = document.getElementById('studio-remotion-model');

      if (styleEl) studioStageData.remotion.style = styleEl.value;
      if (themeEl) studioStageData.remotion.theme = themeEl.value;
      if (densityEl) studioStageData.remotion.density = densityEl.value;
      if (hexEl) studioStageData.remotion.accentColor = hexEl.value;
      if (modelEl) {
        studioStageData.animation_model = modelEl.value;
        const topModelEl = document.getElementById('stage-card-model-animation');
        if (topModelEl) topModelEl.value = modelEl.value;
        const mainModelEl = document.getElementById('model-stage-animation');
        if (mainModelEl) mainModelEl.value = modelEl.value;
      }

      updateStudioRemotionUI();
    }

    function onStudioRemotionModelChange(val) {
      if (!studioStageData) return;
      studioStageData.animation_model = val;
      const topModelEl = document.getElementById('stage-card-model-animation');
      if (topModelEl) topModelEl.value = val;
      const mainModelEl = document.getElementById('model-stage-animation');
      if (mainModelEl) mainModelEl.value = val;
    }

    function onStudioRemotionAccentChange(val) {
      if (!studioStageData.remotion) studioStageData.remotion = {};
      studioStageData.remotion.accentColor = val;
      const hexEl = document.getElementById('studio-remotion-accent-hex');
      if (hexEl) hexEl.value = val;
      updateStudioRemotionUI();
    }

    function onStudioRemotionAccentHexInput(val) {
      let hex = val.trim();
      if (!hex.startsWith('#')) hex = '#' + hex;
      if (/^#[0-9A-Fa-f]{6}$/.test(hex)) {
        if (!studioStageData.remotion) studioStageData.remotion = {};
        studioStageData.remotion.accentColor = hex;
        const pickerEl = document.getElementById('studio-remotion-accent-picker');
        if (pickerEl) pickerEl.value = hex;
        updateStudioRemotionUI();
      }
    }

    function updateStudioRemotionUI() {
      const rem = studioStageData.remotion || {};
      const curStyle = rem.style || 'modern_tech_explainer';
      const accent = rem.accentColor || '#A855F7';

      const badge = document.getElementById('studio-remotion-active-badge');
      if (badge) {
        badge.textContent = `${curStyle} · ${accent}`;
        badge.style.color = accent;
        badge.style.borderColor = accent;
        badge.style.background = accent + '22';
      }

      const statusEl = document.getElementById('remotion-auto-status');
      if (statusEl) {
        statusEl.textContent = `已選風格：${curStyle}（${rem.density || 'full'} 密度）`;
      }

      Object.keys(INSPECTOR_REMOTION_PRESETS).forEach(k => {
        const card = document.getElementById('studio-card-' + k);
        if (card) {
          const isSelected = (curStyle === k);
          const p = INSPECTOR_REMOTION_PRESETS[k];
          card.style.border = isSelected ? `2px solid ${p.borderActive}` : '1px solid #1e293b';
          card.style.boxShadow = isSelected ? `0 0 12px ${p.borderActive}55` : 'none';
        }
      });
    }

    window.selectStudioRemotionPreset = selectStudioRemotionPreset;
    window.onStudioRemotionChange = onStudioRemotionChange;
    window.onStudioRemotionModelChange = onStudioRemotionModelChange;
    window.onStudioRemotionAccentChange = onStudioRemotionAccentChange;
    window.onStudioRemotionAccentHexInput = onStudioRemotionAccentHexInput;
    window.updateStudioRemotionUI = updateStudioRemotionUI;

    window.onInspectorRemotionChange = onInspectorRemotionChange;
    window.onInspectorRemotionAccentChange = onInspectorRemotionAccentChange;
    window.onInspectorRemotionAccentHexInput = onInspectorRemotionAccentHexInput;
    window.updateInspectorRemotionUI = updateInspectorRemotionUI;

    // UNIVERSAL FIND & REPLACE SYSTEM ACROSS ALL STAGES (STAGE 1, 2, 3, PROMPTS, SUBTITLES)
    async function executeUniversalReplace(sourceStage, findInputId, replaceInputId, matchCaseCheckboxId, allStagesCheckboxId, statusElId) {
      const findInput = document.getElementById(findInputId);
      const replaceInput = document.getElementById(replaceInputId);
      const matchCaseCb = document.getElementById(matchCaseCheckboxId);
      const allStagesCb = allStagesCheckboxId ? document.getElementById(allStagesCheckboxId) : null;
      const statusEl = document.getElementById(statusElId);

      const findVal = findInput ? findInput.value.trim() : '';
      const repVal = replaceInput ? replaceInput.value : '';
      const matchCase = matchCaseCb ? matchCaseCb.checked : false;
      const allStages = allStagesCb ? allStagesCb.checked : true;

      if (!findVal) {
        if (statusEl) {
          statusEl.style.color = '#f87171';
          statusEl.innerHTML = '⚠️ 請輸入欲尋找的關鍵字 (Please enter a keyword to find).';
        }
        return;
      }

      if (!currentProjectId) {
        if (statusEl) {
          statusEl.style.color = '#f87171';
          statusEl.innerHTML = '⚠️ 請先選擇或建立專案 (Please select an active project first).';
        }
        return;
      }

      // If user deliberately unchecked all-stages, fallback to single-stage local edit
      if (!allStages) {
        if (sourceStage === 'research' || sourceStage === 'script') {
          const taId = (sourceStage === 'research') ? 'studio-research' : 'studio-script-md';
          return performSingleTextareaReplace(taId, findVal, repVal, matchCase, statusEl);
        } else if (sourceStage === 'scenes') {
          return performSingleScenesReplace(findVal, repVal, matchCase, statusElId);
        }
      }

      if (statusEl) {
        statusEl.style.color = '#93c5fd';
        statusEl.innerHTML = '<span class="spinner-inline" style="width:12px; height:12px; margin-right:6px;"></span> 正在同步連動更新 Stage 1 (研究), Stage 2 (腳本), Stage 3 (分鏡台詞), 提示詞與字幕...';
      }

      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/text_replace`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            find: findVal,
            replace: repVal,
            match_case: matchCase,
            stages: ['research', 'script', 'scenes', 'prompts', 'subtitles', 'project'],
            auto_invalidate_voice: true
          })
        });




        const total = data.total_occurrences || 0;
        const stCounts = data.stages_affected || {};
        const affectedScenes = data.affected_scene_ids || [];

        // 1. Instantly sync in-memory UI textareas if visible
        const taRes = document.getElementById('studio-research');
        if (taRes) {
          const escaped = findVal.replace(/[.*+?^${}()|[\\]/g, '\\$&');
          const reg = new RegExp(escaped, matchCase ? 'g' : 'gi');
          taRes.value = taRes.value.replace(reg, repVal);
        }

        const taScript = document.getElementById('studio-script-md');
        if (taScript) {
          const escaped = findVal.replace(/[.*+?^${}()|[\\]/g, '\\$&');
          const reg = new RegExp(escaped, matchCase ? 'g' : 'gi');
          taScript.value = taScript.value.replace(reg, repVal);
          updateStudioScriptCount(taScript.value);
        }

        // Reload stage studio workspace data to reflect updated fields
        if (typeof loadStageStudio === 'function' && activeStudioStage) {
          await loadStageStudio(activeStudioStage);
        }

        // Also sync global currentScenes & Editor table
        try {
          const pData = await apiJson(`/api/projects/${currentProjectId}`);


            currentScenes = pData.scenes || [];
            if (typeof renderEditor === 'function') {
              renderEditor();
            }

        } catch (_) {}

        // 2. Render rich notification status and instant re-render button
        const newStatusEl = document.getElementById(statusElId);
        if (newStatusEl) {
          if (total === 0) {
            newStatusEl.style.color = '#fbbf24';
            newStatusEl.innerHTML = `ℹ️ 全專案各階段中均未尋獲關鍵字 "<b>${escapeHtml(findVal)}</b>"`;
          } else {
            newStatusEl.style.color = '#34d399';
            const parts = [];
            if (stCounts.research) parts.push(`Stage 1 研究筆記 (${stCounts.research} 處)`);
            if (stCounts.script) parts.push(`Stage 2 旁白腳本 (${stCounts.script} 處)`);
            if (stCounts.scenes) parts.push(`Stage 3 分鏡台詞 (${stCounts.scenes} 處)`);
            if (stCounts.prompts) parts.push(`Stage 4 圖像提示詞 (${stCounts.prompts} 處)`);
            if (stCounts.subtitles) parts.push(`字幕軌道 (${stCounts.subtitles} 處)`);
            if (stCounts.project) parts.push(`專案標題與資訊 (${stCounts.project} 處)`);

            let html = `✓ <b>跨階段同步取代成功！</b> 共替換 <b>${total}</b> 處：${parts.join('、')}。`;
            if (affectedScenes.length > 0) {
              html += `
                <div style="margin-top: 8px; padding: 8px 12px; background: rgba(245, 158, 11, 0.15); border: 1px solid #f59e0b; border-radius: 6px; color: #fde68a; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                  <span>⚠️ <b>${affectedScenes.length}</b> 個分鏡台詞已更新 (Scene: #${affectedScenes.join(', #')})，舊語音已標記過期。</span>
                  <button type="button" class="btn-primary" style="font-size: 11px; padding: 5px 14px; font-weight: 700; background: linear-gradient(135deg, #10b981, #059669); border: none; display: inline-flex; align-items: center; gap: 5px; cursor: pointer;" onclick="triggerQuickVoiceAndVideoUpdate([${affectedScenes.join(',')}])">
                    🎙️⚡ 立即極速重整這 ${affectedScenes.length} 幕語音與 1080p 影片 (Re-generate Voice & Video)
                  </button>
                </div>
              `;
            }
            newStatusEl.innerHTML = html;
          }
        }

      } catch (err) {
        console.error("Universal replace failed:", err);
        const newStatusEl = document.getElementById(statusElId);
        if (newStatusEl) {
          newStatusEl.style.color = '#f87171';
          newStatusEl.innerHTML = `✕ 取代失敗: ${err.message}`;
        }
      }
    }

    function performSingleTextareaReplace(textareaId, findVal, repVal, matchCase, statusEl) {
      const ta = document.getElementById(textareaId);
      if (!ta) return;
      const originalText = ta.value;
      const escaped = findVal.replace(/[.*+?^${}()|[\\]/g, '\\$&');
      const regex = new RegExp(escaped, matchCase ? 'g' : 'gi');
      const matches = originalText.match(regex);
      const count = matches ? matches.length : 0;
      if (count === 0) {
        if (statusEl) {
          statusEl.style.color = '#fbbf24';
          statusEl.innerHTML = `ℹ️ 未在此文字框中尋獲 "<b>${escapeHtml(findVal)}</b>"`;
        }
        return;
      }
      ta.value = originalText.replace(regex, repVal);
      ta.dispatchEvent(new Event('input', { bubbles: true }));
      ta.dispatchEvent(new Event('change', { bubbles: true }));
      if (statusEl) {
        statusEl.style.color = '#34d399';
        statusEl.innerHTML = `✓ 已替換當前輸入框中 <b>${count}</b> 處內容。請記得點擊儲存！`;
      }
    }

    function performSingleScenesReplace(findVal, repVal, matchCase, statusElId) {
      if (!studioStageData || !studioStageData.scenes || !studioStageData.scenes.length) return;
      const escaped = findVal.replace(/[.*+?^${}()|[\\]/g, '\\$&');
      const regex = new RegExp(escaped, matchCase ? 'g' : 'gi');
      let totalMatches = 0;
      let scenesAffected = 0;
      studioStageData.scenes.forEach(sc => {
        let scMatched = false;
        if (typeof sc.narration === 'string') {
          const m = sc.narration.match(regex);
          if (m) {
            totalMatches += m.length;
            sc.narration = sc.narration.replace(regex, repVal);
            scMatched = true;
          }
        }
        if (scMatched) scenesAffected++;
      });
      renderStudioWorkspace('scenes', studioStageData, studioProject);
      const newStatusEl = document.getElementById(statusElId);
      if (newStatusEl) {
        newStatusEl.style.color = '#34d399';
        newStatusEl.innerHTML = `✓ 已替換 <b>${totalMatches}</b> 處分鏡內容。請點擊「儲存分鏡台詞」！`;
      }
    }

    async function triggerQuickVoiceAndVideoUpdate(sceneIds) {
      if (!currentProjectId) return alert("Please select a project first.");
      const count = (sceneIds && sceneIds.length) ? sceneIds.length : '全片';
      if (!confirm(`確定要立即為受影響的 ${count} 個分鏡台詞重新生成語音，並自動更新最終 1080p 影片嗎？\n\n⚡ 極速重整特色：系統僅會重新合成改動過的幕次，未更動之畫面與語音直接重用，幾秒內即可完成母帶更新！`)) {
        return;
      }
      showToast("🎙️ 正在啟動語音重整與影片快速渲染...");
      try {
        const payload = (sceneIds && sceneIds.length)
          ? { scope: 'custom', scene_ids: sceneIds }
          : { scope: 'mismatched' };
        await apiRequest(`/api/projects/${currentProjectId}/rerender_voice_and_video`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })

        startPolling();
        showToast("✓ 語音重整與影片渲染已在背景高速運行！完成後將自動刷新。");
      } catch (err) {
        alert("啟動重整失敗: " + err.message);
      }
    }

    // GLOBAL MODAL CONTROLLERS
    function openGlobalFindReplaceModal(initialFind = '', initialReplace = '') {
      if (!currentProjectId) {
        return alert("請先從頂部選擇一個進行中的專案 (Please select a project first).");
      }
      const m = document.getElementById('universal-find-replace-modal');
      if (m) m.style.display = 'flex';
      const sub = document.getElementById('ufr-project-subtitle');
      if (sub && currentProjectId) {
        sub.textContent = `專案：${(studioProject && (studioProject.title || studioProject.topic)) || currentProjectId}`;
      }
      const fIn = document.getElementById('ufr-find-input');
      const rIn = document.getElementById('ufr-replace-input');
      if (fIn && initialFind) fIn.value = initialFind;
      if (rIn && initialReplace) rIn.value = initialReplace;
      const sBox = document.getElementById('ufr-status-box');
      if (sBox) sBox.style.display = 'none';
      setTimeout(() => { if (fIn) fIn.focus(); }, 50);
    }

    function closeGlobalFindReplaceModal() {
      const m = document.getElementById('universal-find-replace-modal');
      if (m) m.style.display = 'none';
    }

    function getSelectedUfrStages() {
      const stages = [];
      if (document.getElementById('ufr-stage-research')?.checked) stages.push('research');
      if (document.getElementById('ufr-stage-script')?.checked) stages.push('script');
      if (document.getElementById('ufr-stage-scenes')?.checked) stages.push('scenes');
      if (document.getElementById('ufr-stage-prompts')?.checked) stages.push('prompts');
      if (document.getElementById('ufr-stage-subtitles')?.checked) stages.push('subtitles');
      stages.push('project');
      return stages;
    }

    async function previewGlobalFindReplace() {
      const findVal = document.getElementById('ufr-find-input')?.value.trim();
      const repVal = document.getElementById('ufr-replace-input')?.value || '';
      const matchCase = document.getElementById('ufr-match-case')?.checked || false;
      const sBox = document.getElementById('ufr-status-box');
      if (!findVal) {
        if (sBox) {
          sBox.style.display = 'block';
          sBox.style.background = 'rgba(239, 68, 68, 0.15)';
          sBox.style.border = '1px solid #ef4444';
          sBox.style.color = '#fca5a5';
          sBox.textContent = '⚠️ 請輸入欲尋找的關鍵字。';
        }
        return;
      }
      if (sBox) {
        sBox.style.display = 'block';
        sBox.style.background = 'rgba(59, 130, 246, 0.12)';
        sBox.style.border = '1px solid #3b82f6';
        sBox.style.color = '#93c5fd';
        sBox.innerHTML = '<span class="spinner-inline" style="width:12px; height:12px; margin-right:6px;"></span> 正在掃描全專案各階段出現處...';
      }
      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/text_replace/preview`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            find: findVal,
            replace: repVal,
            match_case: matchCase,
            stages: getSelectedUfrStages(),
            auto_invalidate_voice: true
          })
        });

        const total = data.total_occurrences || 0;
        const stCounts = data.stages_affected || {};
        const affectedScenes = data.affected_scene_ids || [];

        if (total === 0) {
          sBox.style.background = 'rgba(245, 158, 11, 0.15)';
          sBox.style.border = '1px solid #f59e0b';
          sBox.style.color = '#fde68a';
          sBox.innerHTML = `ℹ️ 在所選階段中未尋獲關鍵字 "<b>${escapeHtml(findVal)}</b>"`;
        } else {
          sBox.style.background = 'rgba(16, 185, 129, 0.15)';
          sBox.style.border = '1px solid #10b981';
          sBox.style.color = '#6ee7b7';
          sBox.innerHTML = `
            <div><b>掃描完成：</b> 共發現 <b>${total}</b> 處相符文字：</div>
            <ul style="margin: 6px 0 0 16px; padding: 0;">
              ${stCounts.research ? `<li>Stage 1 研究筆記: <b>${stCounts.research}</b> 處</li>` : ''}
              ${stCounts.script ? `<li>Stage 2 旁白腳本: <b>${stCounts.script}</b> 處</li>` : ''}
              ${stCounts.scenes ? `<li>Stage 3 分鏡台詞: <b>${stCounts.scenes}</b> 處 (${affectedScenes.length} 個分鏡台詞受影響)</li>` : ''}
              ${stCounts.prompts ? `<li>Stage 4 圖像提示詞: <b>${stCounts.prompts}</b> 處</li>` : ''}
              ${stCounts.subtitles ? `<li>字幕軌道: <b>${stCounts.subtitles}</b> 處</li>` : ''}
              ${stCounts.project ? `<li>專案資訊: <b>${stCounts.project}</b> 處</li>` : ''}
            </ul>
            ${affectedScenes.length > 0 ? `<div style="margin-top:4px; color:#fde68a;">⚠️ 將影響分鏡: #${affectedScenes.join(', #')}</div>` : ''}
          `;
        }
      } catch (e) {
        if (sBox) {
          sBox.style.background = 'rgba(239, 68, 68, 0.15)';
          sBox.style.border = '1px solid #ef4444';
          sBox.style.color = '#fca5a5';
          sBox.textContent = '掃描失敗: ' + e.message;
        }
      }
    }

    async function submitGlobalFindReplace() {
      const findVal = document.getElementById('ufr-find-input')?.value.trim();
      const repVal = document.getElementById('ufr-replace-input')?.value || '';
      const matchCase = document.getElementById('ufr-match-case')?.checked || false;
      const autoInval = document.getElementById('ufr-auto-invalidate-voice')?.checked || true;
      const sBox = document.getElementById('ufr-status-box');
      const btn = document.getElementById('btn-ufr-execute');

      if (!findVal) {
        return alert("請輸入欲尋找的關鍵字。");
      }

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-inline" style="width:12px; height:12px; margin-right:6px;"></span> 正在同步取代中...';
      }

      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/text_replace`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            find: findVal,
            replace: repVal,
            match_case: matchCase,
            stages: getSelectedUfrStages(),
            auto_invalidate_voice: autoInval
          })
        });


        const total = data.total_occurrences || 0;
        const stCounts = data.stages_affected || {};
        const affectedScenes = data.affected_scene_ids || [];

        // Sync open workspaces
        if (typeof loadStageStudio === 'function' && activeStudioStage) {
          await loadStageStudio(activeStudioStage);
        }

        if (sBox) {
          sBox.style.display = 'block';
          sBox.style.background = 'rgba(16, 185, 129, 0.2)';
          sBox.style.border = '1px solid #10b981';
          sBox.style.color = '#34d399';
          let html = `<div>✓ <b>成功完成跨階段同步取代！</b> 共替換 <b>${total}</b> 處。</div>`;
          if (affectedScenes.length > 0) {
            html += `
              <div style="margin-top: 10px; padding: 10px; background: rgba(0,0,0,0.3); border-radius: 6px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                <span style="color:#fde68a;">⚠️ 分鏡台詞改動 (#${affectedScenes.join(', #')})，語音已自動標記過期。</span>
                <button type="button" class="btn-primary" style="font-size: 12px; padding: 6px 16px; font-weight: 700; background: linear-gradient(135deg, #10b981, #059669); border: none; cursor: pointer;" onclick="closeGlobalFindReplaceModal(); triggerQuickVoiceAndVideoUpdate([${affectedScenes.join(',')}]);">
                  🎙️⚡ 立即極速重整語音與 1080p 影片
                </button>
              </div>
            `;
          }
          sBox.innerHTML = html;
        }

        showToast(`✓ 已成功在全階段取代 ${total} 處「${findVal}」為「${repVal}」`);

      } catch (e) {
        if (sBox) {
          sBox.style.display = 'block';
          sBox.style.background = 'rgba(239, 68, 68, 0.15)';
          sBox.style.border = '1px solid #ef4444';
          sBox.style.color = '#fca5a5';
          sBox.textContent = '取代失敗: ' + e.message;
        }
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '🔄 執行跨階段同步取代 (Replace in All Stages)';
        }
      }
    }

    // Keyboard shortcut listener: Ctrl+H or Ctrl+Shift+F
    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'h' || e.key === 'H')) {
        e.preventDefault();
        openGlobalFindReplaceModal();
      }
    });

function performResearchReplace(textareaId, findInputId, replaceInputId, matchCaseCheckboxId, statusElId) {
      const ta = document.getElementById(textareaId);
      const findInput = document.getElementById(findInputId);
      const replaceInput = document.getElementById(replaceInputId);
      const matchCaseCb = document.getElementById(matchCaseCheckboxId);
      const statusEl = document.getElementById(statusElId);

      if (!ta) return;
      const findVal = findInput ? findInput.value : '';
      const repVal = replaceInput ? replaceInput.value : '';
      const matchCase = matchCaseCb ? matchCaseCb.checked : false;

      if (!findVal) {
        if (statusEl) {
          statusEl.style.color = '#f87171';
          statusEl.textContent = '⚠️ Please enter a keyword to find.';
        }
        return;
      }

      const originalText = ta.value;
      let count = 0;

      // Escape special characters for RegExp
      const escaped = findVal.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const flags = matchCase ? 'g' : 'gi';
      const regex = new RegExp(escaped, flags);

      const matches = originalText.match(regex);
      count = matches ? matches.length : 0;

      if (count === 0) {
        if (statusEl) {
          statusEl.style.color = '#fbbf24';
          statusEl.textContent = `ℹ️ Keyword "${findVal}" not found in research content.`;
        }
        return;
      }

      // Replace and update textarea value
      const updatedText = originalText.replace(regex, repVal);
      ta.value = updatedText;

      // Trigger input/change event
      ta.dispatchEvent(new Event('input', { bubbles: true }));
      ta.dispatchEvent(new Event('change', { bubbles: true }));

      if (statusEl) {
        statusEl.style.color = '#34d399';
        statusEl.innerHTML = `✓ Replaced <b>${count}</b> occurrence(s) of "<code>${findVal}</code>" with "<code>${repVal}</code>". Don't forget to click <b>Save Changes</b>!`;
      }
    }

    function performScenesReplace(context, findInputId, replaceInputId, matchCaseCheckboxId, statusElId) {
      const findInput = document.getElementById(findInputId);
      const replaceInput = document.getElementById(replaceInputId);
      const matchCaseCb = document.getElementById(matchCaseCheckboxId);
      const statusEl = document.getElementById(statusElId);

      const findVal = findInput ? findInput.value : '';
      const repVal = replaceInput ? replaceInput.value : '';
      const matchCase = matchCaseCb ? matchCaseCb.checked : false;

      if (!findVal) {
        if (statusEl) {
          statusEl.style.color = '#f87171';
          statusEl.textContent = '⚠️ Please enter a keyword to find.';
        }
        return;
      }

      const targetData = (context === 'insp') ? inspectedStageData : studioStageData;
      if (!targetData || !targetData.scenes || !targetData.scenes.length) {
        if (statusEl) {
          statusEl.style.color = '#f87171';
          statusEl.textContent = '⚠️ No scenes data available to replace.';
        }
        return;
      }

      const escaped = findVal.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const flags = matchCase ? 'g' : 'gi';
      const regex = new RegExp(escaped, flags);

      let totalMatches = 0;
      let scenesAffected = 0;

      targetData.scenes.forEach(sc => {
        let scMatched = false;
        // 1. Narration text
        if (typeof sc.narration === 'string') {
          const m = sc.narration.match(regex);
          if (m) {
            totalMatches += m.length;
            sc.narration = sc.narration.replace(regex, repVal);
            scMatched = true;
          }
        }
        // 2. Phase turn text
        if (typeof sc.phase_turn_text === 'string') {
          const m = sc.phase_turn_text.match(regex);
          if (m) {
            totalMatches += m.length;
            sc.phase_turn_text = sc.phase_turn_text.replace(regex, repVal);
            scMatched = true;
          }
        }
        // 3. Callout text
        if (typeof sc.callout_text === 'string') {
          const m = sc.callout_text.match(regex);
          if (m) {
            totalMatches += m.length;
            sc.callout_text = sc.callout_text.replace(regex, repVal);
            scMatched = true;
          }
        }
        if (scMatched) scenesAffected++;
      });

      if (totalMatches === 0) {
        if (statusEl) {
          statusEl.style.color = '#fbbf24';
          statusEl.textContent = `ℹ️ Keyword "${findVal}" not found across any scenes.`;
        }
        return;
      }

      // Re-render scenes workspace to display updated text immediately
      if (context === 'insp') {
        openStageInspector('scenes');
      } else {
        renderStudioWorkspace('scenes', studioStageData, studioProject);
      }

      // Re-query status element since workspace might have re-rendered
      const newStatusEl = document.getElementById(statusElId);
      if (newStatusEl) {
        newStatusEl.style.color = '#34d399';
        newStatusEl.innerHTML = `✓ Replaced <b>${totalMatches}</b> occurrence(s) across <b>${scenesAffected}</b> scene(s). Don't forget to click <b>Save Scenes</b>!`;
      }
    }

    async function prefillRemotionFromScene(sceneId) {
      // Show what will be auto-extracted for this scene as placeholders; typed values override.
      if (!currentProjectId || !sceneId) return;
      ['remotion-cat', 'remotion-headline', 'remotion-metric', 'remotion-subtext'].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.value = ''; el.placeholder = '自動擷取中…'; }
      });
      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/remotion/props/${sceneId}`);

        const p = data.props || {};
        const map = { 'remotion-cat': p.category, 'remotion-headline': p.headline, 'remotion-metric': p.metric, 'remotion-subtext': p.subtext };
        for (const [id, val] of Object.entries(map)) {
          const el = document.getElementById(id);
          if (el) el.placeholder = val ? `自動：${val}` : '（無）';
        }
      } catch (e) {
        console.warn('prefillRemotionFromScene failed', e);
      }
    }

    async function autoRemotionCriticalScenes() {
      if (!currentProjectId) return alert("請先選取或建立專案。");
      const btn = document.getElementById('remotion-auto-btn');
      const st = document.getElementById('remotion-auto-status');
      const comp = document.getElementById('remotion-style-select')?.value || 'FoxHeaderScene';
      try {
        const prev = await apiJson(`/api/projects/${currentProjectId}/remotion/critical`);
        const ids = (prev.scenes || []).map(s => s.scene_id);
        if (!ids.length) {
          if (st) { st.style.color = '#fbbf24'; st.textContent = 'ℹ️ 沒有符合條件的關鍵分鏡（需要已生成圖片，且有重點字卡或高強調）。'; }
          return;
        }
        if (!confirm(`將使用 [${comp}] 風格為以下關鍵分鏡渲染 Remotion 卡片（每個約 20–30 秒）：\nScene ${ids.join(', ')}\n\n繼續？`)) return;
        if (btn) btn.disabled = true;
        await apiRequest(`/api/projects/${currentProjectId}/remotion/auto?composition=${encodeURIComponent(comp)}`, { method: 'POST' })

        if (st) { st.style.color = '#38bdf8'; st.textContent = `⏳ 背景渲染中 (${comp})：Scene ${ids.join(', ')}。完成後請點擊 Stage 9 的「Render Final Video」以合成最新影片（進度見上方活動列）。`; }
      } catch (e) {
        if (st) { st.style.color = '#f87171'; st.textContent = '❌ ' + e.message; }
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function renderAndApplyRemotionClip() {
      if (!currentProjectId) return alert("請先選取或建立專案。");
      const btn = document.getElementById('remotion-render-btn');
      const statusText = document.getElementById('remotion-status-text');
      const previewBox = document.getElementById('remotion-preview-box');
      const previewVideo = document.getElementById('remotion-preview-video');
      const comp = document.getElementById('remotion-style-select')?.value || 'FoxHeaderScene';

      // Empty fields are filled on the server from the scene's callout / narration.
      const category = (document.getElementById('remotion-cat')?.value || '').trim();
      const headline = (document.getElementById('remotion-headline')?.value || '').trim();
      const metric = (document.getElementById('remotion-metric')?.value || '').trim();
      const subtext = (document.getElementById('remotion-subtext')?.value || '').trim();
      const sceneIdVal = parseInt(document.getElementById('remotion-target-scene')?.value, 10);
      if (isNaN(sceneIdVal)) return alert("請選取要套用的目標分鏡");

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-inline" style="width:12px; height:12px; margin-right:6px;"></span> 渲染中…`;
      }
      if (statusText) {
        statusText.style.color = '#38bdf8';
        statusText.textContent = `⏳ Remotion [${comp}] 正在逐幀渲染（約 20–30 秒，依分鏡長度而定）...`;
      }

      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/remotion/apply`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            composition: comp,
            scene_id: sceneIdVal,
            fps: 30,
            props: { category, headline, metric, subtext }
          })
        });


        if (statusText) {
          statusText.style.color = '#34d399';
          statusText.innerHTML = `✓ 已套用 [${comp}] 至 Scene #${sceneIdVal}。請點擊 Stage 9 的「Render Final Video」以合成最新影片。`;
        }
        if (previewBox && previewVideo && data.clip?.mp4_url) {
          previewBox.style.display = 'block';
          previewVideo.src = data.clip.mp4_url + `?t=${Date.now()}`;
          previewVideo.load();
          previewVideo.play().catch(() => {});
        }
        const scVid = document.getElementById(`studio-scene-video-${sceneIdVal}`);
        if (scVid && data.clip?.mp4_url) {
          scVid.src = data.clip.mp4_url + `?t=${Date.now()}`;
          scVid.load();
        }
      } catch (e) {
        if (statusText) {
          statusText.style.color = '#f87171';
          statusText.textContent = '❌ ' + e.message;
        }
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.textContent = "⚡ 只為此分鏡渲染卡片";
        }
      }
    }

    function focusRemotionScene(sceneId) {
      const sel = document.getElementById('remotion-target-scene');
      if (sel) {
        sel.value = String(sceneId);
        prefillRemotionFromScene(sceneId);
      }
      const targetCard = document.querySelector(`.studio-anim-scene-card[data-scene-id="${sceneId}"]`);
      if (targetCard) {
        targetCard.style.borderColor = '#00F5FF';
        targetCard.style.boxShadow = '0 0 15px rgba(0, 245, 255, 0.35)';
        setTimeout(() => {
          targetCard.style.boxShadow = 'none';
        }, 3000);
      }
      const anchor = document.getElementById('remotion-target-scene');
      if (anchor) anchor.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function filterStudioAnimScenes(type) {
      const cards = document.querySelectorAll('.studio-anim-scene-card');
      const buttons = document.querySelectorAll('.studio-anim-filter-btn');
      buttons.forEach(btn => {
        const isActive = (btn.dataset.filter === type);
        btn.style.background = isActive ? '#1e3a8a' : '#080d16';
        btn.style.borderColor = isActive ? '#38bdf8' : '#1e293b';
        btn.style.color = isActive ? '#ffffff' : (btn.dataset.filter === 'remotion' ? '#a855f7' : (btn.dataset.filter === 'ready' ? '#34d399' : '#94a3b8'));
      });
      const searchTxt = (document.getElementById('studio-anim-search')?.value || '').toLowerCase().trim();
      cards.forEach(card => {
        const isRem = card.dataset.isRemotion === 'true';
        const hasVid = card.dataset.hasVideo === 'true';
        const narration = (card.dataset.narration || '').toLowerCase();
        const scId = card.dataset.sceneId || '';

        let matchType = true;
        if (type === 'remotion') matchType = isRem;
        else if (type === 'ken_burns') matchType = !isRem;
        else if (type === 'ready') matchType = hasVid;

        let matchSearch = true;
        if (searchTxt) {
          matchSearch = narration.includes(searchTxt) || scId === searchTxt || (`scene #${scId}`).includes(searchTxt) || (`scene ${scId}`).includes(searchTxt);
        }
        card.style.display = (matchType && matchSearch) ? 'flex' : 'none';
      });
    }

    function onStudioAnimSearchInput() {
      const activeBtn = Array.from(document.querySelectorAll('.studio-anim-filter-btn')).find(b => b.style.background.includes('30, 58, 138') || b.style.borderColor.includes('56, 189, 248'));
      const filter = activeBtn ? activeBtn.dataset.filter : 'all';
      filterStudioAnimScenes(filter);
    }

    async function clearProjectVideoCache(targetId) {
      const pId = targetId || currentProjectId;
      if (!pId) return alert("請先選取專案。");
      if (!confirm(`確定要清除專案 "${pId}" 的快取視訊嗎？\n\n此操作將刪除 temp/ 與 animation/ 內的暫存渲染短片以釋放硬碟空間，但會保留腳本、旁白錄音與圖像素材。`)) return;
      try {
        const data = await apiJson(`/api/projects/${pId}/clear_cache`, { method: 'POST' });


        showToast(`✓ 已成功清理 ${data.cleared_mb} MB 快取視訊。`);
      } catch (err) {
        alert("清除快取失敗: " + err.message);
      }
    }

    function formatSecondsToMMSS(sec) {
      if (typeof sec !== 'number' || isNaN(sec)) return "00:00";
      const s = Math.max(0, Math.round(sec));
      const m = Math.floor(s / 60);
      const rem = s % 60;
      return `${String(m).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
    }

    async function toggleProjectMotionCallouts(enabled) {
      updateMotionCalloutsSwitchUI('insp-motion-callouts', enabled);
      updateMotionCalloutsSwitchUI('studio-motion-callouts', enabled);
      if (!currentProjectId) return;
      try {
        await apiRequest(`/api/projects/${currentProjectId}/subtitle_settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ motion_graphics_callouts: enabled })
        });
      } catch(e) {
        console.error("Failed to update motion callouts toggle", e);
      }
    }

    function onStyleDropdownChange(styleKey) {
      if (!inspectedStageData || !inspectedStageData.available_styles) return;
      const st = inspectedStageData.available_styles[styleKey];
      const previewEl = document.getElementById('insp-style-tag-text');
      if (previewEl && st) {
        previewEl.textContent = `${st.style || ''} (${st.mood || ''}, ${st.lighting || ''})`;
      }
      const modelEl = document.getElementById('insp-img-model');
      if (modelEl) {
        if (st && st.recommended_model) {
          modelEl.value = st.recommended_model;
        } else if (styleKey.includes('photorealistic') || styleKey.includes('cinema')) {
          modelEl.value = 'juggernautXL_v8Rundiffusion.safetensors';
        }
      }
    }

    async function saveImageSettingsFor(prefix, applyToPrompts, onSaved) {
      if (!currentProjectId) return;
      const styleEl = document.getElementById(`${prefix}-img-style`);
      const modelEl = document.getElementById(`${prefix}-img-model`);
      const stepsEl = document.getElementById(`${prefix}-img-steps`);
      const cfgEl = document.getElementById(`${prefix}-img-cfg`);

      const payload = {
        visual_style: styleEl ? styleEl.value : null,
        checkpoint: modelEl ? modelEl.value : null,
        steps: stepsEl ? parseInt(stepsEl.value) : null,
        cfg: cfgEl ? parseFloat(cfgEl.value) : null,
        apply_to_prompts: applyToPrompts
      };

      try {
        await apiRequest(`/api/projects/${currentProjectId}/image_settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        await onSaved();
        return true;
      } catch (e) {
        alert("Error saving settings: " + e.message);
        return false;
      }
    }

    async function saveImageSettings(applyToPrompts = false) {
      return saveImageSettingsFor('insp', applyToPrompts, async () => {
        alert(applyToPrompts ? "Image style & model saved and applied to all scene prompts!" : "Image style & model saved successfully!");
        openStageInspector(inspectedStageName || 'images');
      });
    }

    async function applyStyleFromPromptsTab() {
      if (!currentProjectId) return;
      const styleEl = document.getElementById('insp-prompt-style');
      if (!styleEl) return;
      const payload = {
        visual_style: styleEl.value,
        apply_to_prompts: true
      };
      try {
        await apiRequest(`/api/projects/${currentProjectId}/image_settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })

        alert("Visual style applied to all scene prompts!");
        openStageInspector('prompts');
      } catch (e) {
        alert("Error: " + e.message);
      }
    }

    async function saveAndRunFullImages(forceStock = false) {
      if (forceStock) {
        const modelEl = document.getElementById('insp-img-model');
        if (modelEl) modelEl.value = 'stock';
      }
      await saveImageSettings(false);
      closeStageInspector();
      runSingleStage('images');
    }

    async function quickStockPhotoForScene(sceneId, isInspector = false) {
      const modelEl = document.getElementById(isInspector ? `scene-model-${sceneId}` : `studio-scene-model-${sceneId}`);
      if (modelEl) modelEl.value = 'stock';
      if (isInspector) {
        await regenImageWithCustomSettings(sceneId);
      } else {
        await regenStudioImage(sceneId);
      }
    }

    async function triggerBatchQuickStock(scope = 'all') {
      if (!currentProjectId) return alert("Please select a project first.");

      const isAll = (scope === 'all');
      const confirmMsg = isAll
        ? "確定要將全片所有鏡頭替換為線上圖庫 / Quick Stock 圖片嗎？\n\n系統將會依據各鏡頭的關鍵實體與畫面描述，向 Wikimedia Commons、YouTube Snippet 等真實圖庫抓取高畫質素材並取代當前圖片。"
        : "確定要將所有「命中真實實體標籤」的鏡頭替換為線上真實圖庫圖片嗎？\n\n未命中真實人物或硬體的鏡頭將保留目前的 AI 生成圖。";

      if (!confirm(confirmMsg)) return;

      const allBtns = [document.getElementById('btn-batch-stock-all'), document.getElementById('studio-btn-batch-stock-all')].filter(Boolean);
      const matchedBtns = [document.getElementById('btn-batch-stock-matched'), document.getElementById('studio-btn-batch-stock-matched')].filter(Boolean);
      allBtns.forEach(b => { b.disabled = true; b.textContent = "⏳ 正在啟動批量抓取..."; });
      matchedBtns.forEach(b => { b.disabled = true; });

      // Create or get floating progress widget
      let progressCard = document.getElementById('quick-stock-progress-card');
      if (!progressCard) {
        progressCard = document.createElement('div');
        progressCard.id = 'quick-stock-progress-card';
        progressCard.style.cssText = `
          position: fixed;
          bottom: 24px;
          right: 24px;
          width: 380px;
          max-width: calc(100vw - 32px);
          background: #0f172a;
          border: 1px solid #10b981;
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.7);
          border-radius: 12px;
          padding: 16px;
          z-index: 999999;
          font-family: inherit;
          color: #f8fafc;
          transition: opacity 0.3s ease;
        `;
        document.body.appendChild(progressCard);
      }

      progressCard.style.display = 'block';
      progressCard.style.opacity = '1';
      progressCard.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span style="font-weight: 700; font-size: 13px; color: #34d399; display: flex; align-items: center; gap: 6px;">
            <span style="animation: spin 1.5s linear infinite; display: inline-block;">⚙️</span> Quick Stock 批次抓取中
          </span>
          <span id="qs-card-pct" style="font-weight: 700; font-size: 13px; color: #38bdf8;">0%</span>
        </div>
        <div style="height: 6px; background: #334155; border-radius: 3px; overflow: hidden; margin-bottom: 10px;">
          <div id="qs-card-bar" style="width: 0%; height: 100%; background: linear-gradient(90deg, #10b981, #06b6d4); transition: width 0.3s ease;"></div>
        </div>
        <div id="qs-card-msg" style="font-size: 12px; color: #cbd5e1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 6px;">
          正在分析鏡頭實體關鍵字...
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #94a3b8;">
          <span id="qs-card-count">已成功替換: 0 鏡</span>
          <span style="color: #64748b;">背景執行中，可切換分頁</span>
        </div>
      `;

      try {
        const result = await apiJson(`/api/projects/${currentProjectId}/batch_quick_stock`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scope: scope, source: 'auto' })
        });



        // Poll status every 1.2s until complete
        const pollTimer = setInterval(async () => {
          try {
            const sdata = await apiJson(`/api/projects/${currentProjectId}/batch_quick_stock/status`);



            const pctEl = document.getElementById('qs-card-pct');
            const barEl = document.getElementById('qs-card-bar');
            const msgEl = document.getElementById('qs-card-msg');
            const cntEl = document.getElementById('qs-card-count');

            if (pctEl) pctEl.textContent = `${sdata.percent || 0}%`;
            if (barEl) barEl.style.width = `${sdata.percent || 0}%`;
            if (msgEl) msgEl.textContent = sdata.message || '正在處理...';
            if (cntEl) cntEl.textContent = `已成功替換: ${sdata.replaced_count || 0} 鏡`;

            allBtns.forEach(b => { b.textContent = `⏳ 正在抓取實體素材 (${sdata.percent || 0}%)...`; });

            if (sdata.status === 'completed') {
              clearInterval(pollTimer);
              if (pctEl) pctEl.textContent = '100%';
              if (barEl) barEl.style.width = '100%';
              if (msgEl) msgEl.innerHTML = `<span style="color:#4ade80; font-weight:700;">✓ 替換完成！共成功替換了 ${sdata.replaced_count} / ${sdata.total_scenes} 個鏡頭圖片。</span>`;

              if (typeof showToast === 'function') {
                showToast(`🎉 Quick Stock 替換完成！共替換了 ${sdata.replaced_count} 個鏡頭。`);
              }

              // Refresh UI
              if (typeof openStageInspector === 'function' && document.getElementById('inspector-modal')?.style.display === 'flex') {
                await openStageInspector('images');
              }
              if (typeof loadStageStudio === 'function') {
                await loadStageStudio('images');
              }

              setTimeout(() => {
                if (progressCard) {
                  progressCard.style.opacity = '0';
                  setTimeout(() => { progressCard.style.display = 'none'; }, 300);
                }
              }, 4000);

              allBtns.forEach(b => { b.disabled = false; b.textContent = "⚡ 一鍵全部替換為 Quick Stock 圖片"; });
              matchedBtns.forEach(b => { b.disabled = false; });
            } else if (sdata.status === 'error') {
              clearInterval(pollTimer);
              alert("Batch Quick Stock 發生錯誤: " + (sdata.message || "未知錯誤"));
              if (progressCard) progressCard.style.display = 'none';
              allBtns.forEach(b => { b.disabled = false; b.textContent = "⚡ 一鍵全部替換為 Quick Stock 圖片"; });
              matchedBtns.forEach(b => { b.disabled = false; });
            }
          } catch (pollErr) {
            console.warn("Poll batch quick stock error:", pollErr);
          }
        }, 1200);

      } catch (err) {
        alert("Batch Quick Stock 發生錯誤: " + err.message);
        if (progressCard) progressCard.style.display = 'none';
        allBtns.forEach(b => { b.disabled = false; b.textContent = "⚡ 一鍵全部替換為 Quick Stock 圖片"; });
        matchedBtns.forEach(b => { b.disabled = false; });
      }
    }

    function onInspSceneStyleChange(sceneId, styleKey) {
      if (!inspectedStageData || !inspectedStageData.available_styles) return;
      const st = inspectedStageData.available_styles[styleKey];
      if (!st) return;
      const promptEl = document.getElementById(`scene-prompt-${sceneId}`);
      if (promptEl) {
        const cleanDesc = (promptEl.value || "").split(',')[0].trim();
        const tags = [st.style, st.lighting, st.lens, st.mood].filter(Boolean);
        if (tags.length) {
          promptEl.value = `${cleanDesc}, ${tags.join(', ')}, 16:9 widescreen composition, high detail`;
        }
      }
    }

    function applyInspSceneStyleTags(sceneId) {
      const styleEl = document.getElementById(`scene-style-${sceneId}`);
      if (styleEl) onInspSceneStyleChange(sceneId, styleEl.value);
    }

    async function regenImageWithCustomSettings(sceneId) {
      if (!currentProjectId) return;
      const promptEl = document.getElementById(`scene-prompt-${sceneId}`);
      const modelEl = document.getElementById(`scene-model-${sceneId}`);
      const styleEl = document.getElementById(`scene-style-${sceneId}`);
      const stepsEl = document.getElementById('insp-img-steps');
      const cfgEl = document.getElementById('insp-img-cfg');
      const btn = document.getElementById(`btn-regen-${sceneId}`);
      const progBox = document.getElementById(`insp-prog-box-${sceneId}`);
      const progTitle = document.getElementById(`insp-prog-title-${sceneId}`);
      const progPct = document.getElementById(`insp-prog-pct-${sceneId}`);
      const progBar = document.getElementById(`insp-prog-bar-${sceneId}`);
      const progGpuVal = document.getElementById(`insp-prog-gpu-val-${sceneId}`);

      if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ Generating...";
      }

      if (progBox) {
        progBox.style.display = 'block';
        if (progTitle) progTitle.textContent = (modelEl && modelEl.value === 'stock') ? "🌐 Fetching online stock photo..." : "🚀 Starting ComfyUI DirectML...";
        if (progPct) progPct.textContent = "0%";
        if (progBar) progBar.style.width = "5%";
        if (progGpuVal) progGpuVal.textContent = (modelEl && modelEl.value === 'stock') ? "Online Service (0 GPU)" : "Querying GPU...";
      }

      let pollTimer = null;
      const pollStatus = async () => {
        try {
          const sdata = await apiJson('/api/images/live_status');



          if (progBox && sdata.active && sdata.scene_id === sceneId) {
            if (sdata.total_steps > 0) {
              const pct = Math.max(5, sdata.percent || 0);
              if (progBar) progBar.style.width = `${pct}%`;
              if (progPct) progPct.textContent = `${pct}%`;
              if (progTitle) progTitle.textContent = `⚡ Step ${sdata.step}/${sdata.total_steps} (${pct}%)`;
            } else {
              if (progTitle) progTitle.textContent = "⏳ Loading model & pipeline...";
            }
          }

          if (progGpuVal && sdata.gpu) {
            const loadCol = sdata.gpu.util_percent > 60 ? '#f59e0b' : (sdata.gpu.util_percent > 15 ? '#38bdf8' : '#34d399');
            progGpuVal.innerHTML = `<span style="color:${loadCol};">${sdata.gpu.util_percent}% Load</span> | <span style="color:#93c5fd;">${sdata.gpu.vram_gb} GB VRAM</span>`;
          }
        } catch (_) {}
      };

      pollTimer = setInterval(pollStatus, 500);
      pollStatus();

      const scriptEl = document.getElementById(`insp-scene-script-${sceneId}`) || document.getElementById(`studio-scene-script-${sceneId}`);
      if (scriptEl && typeof saveSingleSceneScript === 'function') {
        await saveSingleSceneScript(sceneId, true);
      }

      const body = {
        prompt: promptEl ? promptEl.value : null,
        model: modelEl ? modelEl.value : null,
        visual_style: styleEl ? styleEl.value : null,
        steps: stepsEl ? parseInt(stepsEl.value) : 25,
        cfg: cfgEl ? parseFloat(cfgEl.value) : 6.5
      };

      try {
        await apiRequest(`/api/projects/${currentProjectId}/scenes/${sceneId}/regenerate_image`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        })

        if (pollTimer) clearInterval(pollTimer);
        if (progBar) progBar.style.width = "100%";
        if (progPct) progPct.textContent = "100%";
        if (progTitle) progTitle.textContent = "✓ Image Generated!";
        setTimeout(() => {
          openStageInspector('images');
        }, 500);
      } catch (e) {
        if (pollTimer) clearInterval(pollTimer);
        if (progBox) progBox.style.display = 'none';
        alert("Image generation failed: " + e.message);
        if (btn) {
          btn.disabled = false;
          btn.textContent = "🔄 Regenerate";
        }
      }
    }

    async function regenImageAndRefresh(sceneId) {
      await apiRequest(`/api/projects/${currentProjectId}/scenes/${sceneId}/regenerate_image`, { method: 'POST' });
      openStageInspector('images');
    }

    async function regenVoiceAndRefresh(sceneId) {
      const voiceSelect = document.getElementById(`insp-scene-voice-${sceneId}`);
      const chosenVoice = voiceSelect ? voiceSelect.value : null;
      const payload = chosenVoice ? { voice_profile: chosenVoice } : {};
      await apiRequest(`/api/projects/${currentProjectId}/scenes/${sceneId}/regenerate_voice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      openStageInspector('voice');
    }


    function onStudioMusicSegmentTrackChange(segIdx, selEl) {
      updateMusicSegmentTrack(studioStageData, 'studio', segIdx, selEl);
    }

    async function onStudioMusicVibeChange(val) {
      return saveMusicVibe(studioStageData, val, '✓ 配樂氛圍風格已設為');
    }

    async function reMatchStudioMusicVibe() {
      const vibeEl = document.getElementById('studio-music-vibe-select');
      const chosenVibe = vibeEl ? vibeEl.value : (studioStageData?.current_vibe || 'auto');
      await onStudioMusicVibeChange(chosenVibe);
      runStudioStageOnly('music');
    }

    function updateStudioMusicProgression(val) {
      if (!studioStageData) return;
      studioStageData.music_settings = studioStageData.music_settings || {};
      studioStageData.music_settings.progression = val;
      studioStageData.music_settings.dynamic_music = (val === 'narrative_evolving');
      if (typeof showToast === 'function') showToast(`✓ 配樂演進模式已切換為: ${val}`);
    }


    /* ==========================================================================
       KEY CHARACTERS & AUTHENTIC MEDIA REVIEW (Stage 1 Research Extension)
       ========================================================================== */
    /* ==========================================================================
       FACT VALIDITY DOUBLE-CHECK & TAIWAN MANDARIN VERIFICATION (Stage 1)
       ========================================================================== */
    function renderFactCheckCardHtml(factCheck) {
      if (!factCheck) {
        return `
          <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 8px; padding: 16px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
              <div style="font-weight: 700; color: #34d399; font-size: 14px; display: flex; align-items: center; gap: 8px;">
                <span>🛡️</span> Fact Validity Double-Check & Taiwan Terminology (事實真偽雙重查核與臺灣用語檢驗)
              </div>
              <button class="btn-sec" style="font-size: 12px; padding: 6px 14px; background: rgba(16, 185, 129, 0.2); border-color: #10b981; color: #6ee7b7; font-weight: 700;" onclick="triggerStudioFactCheck(this)">
                🔍 立即執行事實查核 (Run Fact Check)
              </button>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">
              100% 排除中國大陸來源與簡體字資料，防範政治扭曲事實；全篇落實臺灣正體中文與臺灣標準翻譯名稱，並依中央研究院及國際學術共識雙重驗證。
            </div>
          </div>
        `;
      }

      const score = Number(factCheck.validity_score || 100);
      const status = factCheck.overall_status || 'PASSED';
      const isPassed = status === 'PASSED';
      const statusColor = isPassed ? '#34d399' : (status === 'NEEDS_REVIEW' ? '#fbbf24' : '#f87171');
      const statusBg = isPassed ? 'rgba(16, 185, 129, 0.18)' : (status === 'NEEDS_REVIEW' ? 'rgba(245, 158, 11, 0.18)' : 'rgba(239, 68, 68, 0.18)');
      const claims = factCheck.claims_audit || [];
      const srcInt = factCheck.source_integrity || {};
      const blocked = srcInt.prohibited_prc_sources_blocked || [];
      const safe = srcInt.verified_safe_sources || [];

      let blockedHtml = '';
      if (blocked.length > 0) {
        blockedHtml = `
          <div style="margin-top: 10px; padding: 8px 12px; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 6px; font-size: 11.5px; color: #fca5a5;">
            <b>🚫 已攔截並阻絕之中國大陸/簡體字來源 (${blocked.length} 項)：</b>
            <ul style="margin: 4px 0 0 16px; padding: 0;">
              ${blocked.map(b => `<li>${escapeHtml(b)}</li>`).join('')}
            </ul>
          </div>
        `;
      }

      let claimsRows = '';
      claims.forEach((c, idx) => {
        const v = c.verdict || 'VERIFIED';
        const vBadge = v === 'VERIFIED'
          ? '<span style="color: #34d399; font-weight: 700;">🟢 正確 (VERIFIED)</span>'
          : (v === 'DISPUTED' ? '<span style="color: #fbbf24; font-weight: 700;">🟡 存疑 (DISPUTED)</span>' : '<span style="color: #f87171; font-weight: 700;">🔴 錯誤 (FALSE)</span>');
        const conf = Math.round(Number(c.confidence || 0.9) * 100);
        let expl = escapeHtml(c.explanation || '');
        if (c.correction_suggestion) {
          expl += `<div style="margin-top: 4px; color: #6ee7b7; font-weight: 600;">💡 臺灣用語修正建議：${escapeHtml(c.correction_suggestion)}</div>`;
        }
        claimsRows += `
          <tr style="border-bottom: 1px solid rgba(255,255,255,0.06);">
            <td style="padding: 8px 10px; color: var(--text-muted); font-family: monospace;">${idx + 1}</td>
            <td style="padding: 8px 10px; color: #fff; font-weight: 600;">${escapeHtml(c.claim || '')}</td>
            <td style="padding: 8px 10px; white-space: nowrap;">${vBadge}</td>
            <td style="padding: 8px 10px; color: #93c5fd; font-family: monospace;">${conf}%</td>
            <td style="padding: 8px 10px; color: #cbd5e1; font-size: 11.5px; line-height: 1.4;">${expl}</td>
          </tr>
        `;
      });

      return `
        <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 8px; padding: 16px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
              <span style="font-size: 18px;">🛡️</span>
              <span style="font-weight: 700; color: #fff; font-size: 14px;">Fact Validity Double-Check & Taiwan Standards (事實真偽查核與臺灣用語檢驗)</span>
              <span style="font-size: 12px; font-weight: 800; padding: 2px 8px; border-radius: 12px; background: ${statusBg}; color: ${statusColor}; border: 1px solid ${statusColor}; font-family: monospace;">
                ${score}/100 (${status})
              </span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 11px; background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); padding: 2px 8px; border-radius: 12px;">
                🚫 100% 零中國來源保證
              </span>
              <span style="font-size: 11px; background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); padding: 2px 8px; border-radius: 12px;">
                🇹🇼 臺灣正體中文與翻譯名稱
              </span>
              <button class="btn-sec" style="font-size: 11px; padding: 4px 10px; background: rgba(16, 185, 129, 0.2); border-color: #10b981; color: #6ee7b7; font-weight: 700;" onclick="triggerStudioFactCheck(this)">
                🔄 重新雙重查核 (Re-Check)
              </button>
            </div>
          </div>

          <div style="font-size: 12.5px; color: #cbd5e1; line-height: 1.5; margin-bottom: 12px; background: rgba(0,0,0,0.25); padding: 10px 12px; border-radius: 6px;">
            ${escapeHtml(factCheck.summary || '已依據臺灣學術文獻及國際同儕共識完成事實有效性雙重查核。')}
          </div>

          ${blockedHtml}

          <details style="margin-top: 10px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px;">
            <summary style="cursor: pointer; font-size: 12px; font-weight: 600; color: #93c5fd; user-select: none;">
              🔍 檢視逐項事實查核清單 (${claims.length} 項核心主張)
            </summary>
            <div style="margin-top: 10px; overflow-x: auto;">
              <table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: left;">
                <thead>
                  <tr style="border-bottom: 1px solid rgba(255,255,255,0.12); color: var(--text-muted); font-size: 11px;">
                    <th style="padding: 6px 10px; width: 40px;">#</th>
                    <th style="padding: 6px 10px; min-width: 180px;">受檢事實主張 (Claim)</th>
                    <th style="padding: 6px 10px; width: 130px;">查核結論</th>
                    <th style="padding: 6px 10px; width: 80px;">信心度</th>
                    <th style="padding: 6px 10px;">考證依據與臺灣用語建議</th>
                  </tr>
                </thead>
                <tbody>
                  ${claimsRows}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      `;
    }

    async function triggerStudioFactCheck(btn) {
      if (!currentProjectId) return;
      const oldHtml = btn.innerHTML;
      btn.innerHTML = '⏳ 正在雙重查核事實中...';
      btn.disabled = true;
      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/fact-check`, { method: 'POST' });

        if (data.status === 'ok') {
          if (typeof showToast === 'function') showToast('✓ 事實真偽雙重查核完成！');
          if (typeof loadStageStudio === 'function') await loadStageStudio('research');
        } else {
          alert('事實查核失敗: ' + (data.detail || JSON.stringify(data)));
        }
      } catch (err) {
        alert('事實查核連線失敗: ' + err.message);
      } finally {
        btn.innerHTML = oldHtml;
        btn.disabled = false;
      }
    }

    function renderCharactersReviewHtml(characters, isInspector = false) {
      if (!Array.isArray(characters) || !characters.length) {
        return `
          <div style="background: rgba(15, 23, 42, 0.6); border: 1px dashed rgba(59, 130, 246, 0.3); border-radius: 8px; padding: 18px 20px; margin-bottom: 20px; text-align: center;">
            <div style="font-size: 26px; margin-bottom: 6px;">🎭</div>
            <div style="font-size: 14px; font-weight: 700; color: #fff; margin-bottom: 4px;">尚未識別關鍵歷史人物</div>
            <div style="font-size: 12px; color: var(--text-muted); max-width: 440px; margin: 0 auto 12px auto;">
              系統可根據研究報告自動識別核心人物、歷史原作者與演員，並自 Wikipedia 與 YouTube 檢索真實肖像與歷史片段。
            </div>
            <button class="btn-sec" style="font-size: 12px; padding: 6px 14px; background: rgba(59,130,246,0.18); border-color: #3b82f6; color: #93c5fd; font-weight: 600;" onclick="rescanProjectCharacters(${isInspector})">
              🔍 立即掃描人物與網路真實素材
            </button>
          </div>
        `;
      }

      let html = `
        <div style="background: linear-gradient(135deg, rgba(11, 20, 38, 0.95) 0%, rgba(6, 12, 24, 0.95) 100%); border: 1px solid rgba(59, 130, 246, 0.35); border-radius: 8px; padding: 18px 20px; margin-bottom: 20px; box-shadow: 0 4px 16px rgba(0,0,0,0.3);">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; border-bottom: 1px solid rgba(59, 130, 246, 0.2); padding-bottom: 12px;">
            <div>
              <div style="font-size: 15px; font-weight: 800; color: #fff; display: flex; align-items: center; gap: 8px;">
                <span>🎭</span> 關鍵人物與真實影音審查 (Key Characters & Authentic Media Review)
                <span style="font-size: 11px; background: rgba(59,130,246,0.2); color: #60a5fa; border: 1px solid rgba(59,130,246,0.4); padding: 2px 7px; border-radius: 10px;">共 ${characters.length} 位人物</span>
              </div>
              <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">
                系統已自動自 Wikipedia、Wikimedia 及 YouTube 檢索真實肖像與歷史紀錄片段。您可在此審查、選擇並直接指派至對應分鏡。
              </div>
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              <button type="button" class="btn-sec" style="font-size: 11px; padding: 6px 12px; color: #93c5fd; border-color: #3b82f6;" onclick="rescanProjectCharacters(${isInspector})">
                🔄 重新檢索素材
              </button>
              <button type="button" class="btn-primary" style="font-size: 11px; padding: 6px 14px; background: linear-gradient(135deg, #e11d48 0%, #be123c 100%); font-weight: 700; border: 1px solid #f43f5e;" onclick="enforceMainCharacterRealRatio(${isInspector})">
                ⚡ 確保主角分鏡 ≥ 90% 真實素材
              </button>
              <button type="button" class="btn-primary" style="font-size: 11px; padding: 6px 14px; background: linear-gradient(135deg, #059669 0%, #047857 100%); font-weight: 700; border: 1px solid #10b981;" onclick="applyApprovedCharacterMedia(${isInspector})">
                🔗 一鍵套用至對應分鏡
              </button>
            </div>
          </div>

          <div style="display: flex; flex-direction: column; gap: 16px;">
      `;

      characters.forEach((char, cIdx) => {
        const charId = char.id || `char_${cIdx + 1}`;
        const targetScenesStr = Array.isArray(char.target_scenes) ? char.target_scenes.join(', ') : (char.target_scenes || '');
        const images = char.images || [];
        const clips = char.clips || [];
        const selectedImg = char.selected_image;
        const selectedClip = char.selected_clip;
        const status = char.status || 'pending';

        html += `
          <div style="background: #080d16; border: 1px solid rgba(124, 145, 182, 0.25); border-radius: 8px; padding: 16px;">
            <!-- Character Header -->
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
              <div>
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  <span style="font-size: 15px; font-weight: 800; color: #fff;">${char.name}</span>
                  ${char.original_name ? `<span style="font-size: 11px; background: rgba(59,130,246,0.15); color: #93c5fd; border: 1px solid rgba(59,130,246,0.3); border-radius: 4px; padding: 2px 6px;">${char.original_name}</span>` : ''}
                  <select style="font-size: 11px; padding: 2px 6px; border-radius: 4px; background: #040814; color: ${status === 'approved' ? '#34d399' : (status === 'rejected' ? '#f87171' : '#f59e0b')}; border: 1px solid var(--border-muted); font-weight: 700;" onchange="onCharacterStatusChange(${cIdx}, this.value, ${isInspector})">
                    <option value="pending" ${status === 'pending' ? 'selected' : ''}>⏳ 待審查 (Pending)</option>
                    <option value="approved" ${status === 'approved' ? 'selected' : ''}>✓ 已核准 (Approved)</option>
                    <option value="rejected" ${status === 'rejected' ? 'selected' : ''}>✕ 排除 (Rejected)</option>
                  </select>
                </div>
                <div style="font-size: 12px; color: #cbd5e1; margin-top: 4px; line-height: 1.4;">
                  ${char.role || '關鍵歷史人物'}
                </div>
              </div>

              <!-- Target Scenes Assignment -->
              <div style="display: flex; align-items: center; gap: 6px; background: #04070e; border: 1px solid #1e293b; border-radius: 6px; padding: 6px 10px;">
                <label style="font-size: 11px; font-weight: 700; color: #38bdf8; margin: 0; white-space: nowrap;">🎯 指派至分鏡:</label>
                <input type="text" value="${targetScenesStr}" placeholder="e.g. 6, 15, 20" style="width: 140px; font-size: 11px; padding: 3px 6px; background: #080d16; border: 1px solid #334155; border-radius: 4px; color: #fff; font-weight: 700;" onchange="onCharacterScenesChange(${cIdx}, this.value, ${isInspector})">
                <span style="font-size: 10px; color: #64748b;">(Scene IDs)</span>
              </div>
            </div>

            <!-- Foreign Search & Ratio Boost Toolbar -->
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(59, 130, 246, 0.25); border-radius: 6px; padding: 10px 12px; margin-bottom: 12px; display: flex; flex-direction: column; gap: 8px;">
              <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 6px; flex: 1; min-width: 280px;">
                  <span style="font-size: 11px; font-weight: 700; color: #38bdf8; white-space: nowrap;">🌐 原生/外語搜尋詞:</span>
                  <input type="text" id="char-keywords-${cIdx}" value="${escapeHtml(Array.isArray(char.search_keywords) ? char.search_keywords.join(', ') : (char.search_keywords || ''))}" placeholder="例如：風雲ライオン丸, 快傑ライオン丸 変身" style="flex: 1; font-size: 11px; padding: 4px 8px; background: #080d16; border: 1px solid #334155; border-radius: 4px; color: #fff;" onchange="onCharacterKeywordsChange(${cIdx}, this.value, ${isInspector})">
                  <button type="button" class="btn-sec" style="font-size: 11px; padding: 4px 10px; color: #38bdf8; border-color: #0284c7; white-space: nowrap;" onclick="reSearchCharacterForeign(${cIdx}, ${isInspector})">
                    🔍 以外語搜尋素材
                  </button>
                </div>
              </div>

              <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; border-top: 1px dashed rgba(59, 130, 246, 0.2); padding-top: 8px;">
                <div style="display: flex; align-items: center; gap: 6px; font-size: 11px; color: #94a3b8;">
                  <span style="color: #fbbf24; font-weight: 700;">⚡ 真實影音佔比:</span>
                  <select id="char-clip-ratio-${cIdx}" style="font-size: 11px; padding: 3px 6px; background: #080d16; border: 1px solid #334155; border-radius: 4px; color: #facc15; font-weight: 600;">
                    <option value="0.9" selected>90% 真實素材 (實拍影片+真實劇照) · 主角分鏡優先 (推薦)</option>
                    <option value="0.7">70% 實拍影片 (~10s) + 30% 劇照</option>
                    <option value="1.0">100% 全數使用實拍影片 (~10s)</option>
                    <option value="0.5">50% 實拍影片 + 50% 劇照</option>
                    <option value="0.0">100% 全數使用真實歷史劇照</option>
                  </select>
                  <span style="color: #64748b;">(自動裁切約 10 秒 YouTube 高畫質片段並依分鏡時長對齊)</span>
                </div>
                <button type="button" class="btn-primary" style="font-size: 11px; padding: 5px 14px; background: linear-gradient(135deg, #d97706 0%, #b45309 100%); border: 1px solid #f59e0b; color: #fff; font-weight: 700; white-space: nowrap;" onclick="boostCharacterRatio(${cIdx}, ${isInspector})">
                  ⚡ 一鍵提高主角真實影音佔比 (批次套用分鏡)
                </button>
              </div>
            </div>

            <!-- Media Columns: Images & Clips -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">
              <!-- Real Images Gallery -->
              <div style="background: #040814; border: 1px solid #1e293b; border-radius: 6px; padding: 10px 12px;">
                <div style="font-size: 12px; font-weight: 700; color: #93c5fd; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
                  <span>📸 真實肖像與歷史劇照 (${images.length})</span>
                </div>
                ${!images.length ? '<div style="font-size:11px; color:#64748b; padding:10px 0;">無相關圖片素材</div>' : `
                  <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px;">
                    ${images.map((img, iIdx) => {
                      const isSel = (img.url === selectedImg);
                      return `
                        <div onclick="onCharacterSelectImage(${cIdx}, '${img.url.replace(/'/g, "\'")}', ${isInspector})" style="position: relative; cursor: pointer; border-radius: 4px; overflow: hidden; border: 2px solid ${isSel ? '#10b981' : 'transparent'}; box-shadow: ${isSel ? '0 0 8px rgba(16,185,129,0.5)' : 'none'}; background: #000; aspect-ratio: 16/10;">
                          <img src="${img.thumbnail_url || img.url}" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.src='/favicon.ico';">
                          <span style="position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.75); color: #fff; font-size: 9px; padding: 1px 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${img.source || 'Photo'}</span>
                          ${isSel ? '<span style="position: absolute; top: 2px; right: 2px; background: #10b981; color: #fff; font-size: 10px; border-radius: 50%; width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; font-weight: 900;">✓</span>' : ''}
                        </div>
                      `;
                    }).join('')}
                  </div>
                `}
              </div>

              <!-- Real Video Clips Gallery -->
              <div style="background: #040814; border: 1px solid #1e293b; border-radius: 6px; padding: 10px 12px;">
                <div style="font-size: 12px; font-weight: 700; color: #f59e0b; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
                  <span>🎬 真實歷史影像片段 (${clips.length})</span>
                </div>
                ${!clips.length ? '<div style="font-size:11px; color:#64748b; padding:10px 0;">無相關影片片段</div>' : `
                  <div style="display: flex; flex-direction: column; gap: 8px;">
                    ${clips.map((clip, clIdx) => {
                      const isSel = (clip.url === selectedClip);
                      return `
                        <div style="display: flex; align-items: center; gap: 8px; background: #080d16; border: 1px solid ${isSel ? '#3b82f6' : '#1e293b'}; border-radius: 4px; padding: 6px; box-shadow: ${isSel ? '0 0 8px rgba(59,130,246,0.4)' : 'none'};">
                          <img src="${clip.thumbnail_url || ''}" style="width: 64px; height: 38px; object-fit: cover; border-radius: 3px; background: #000; flex-shrink: 0;" onerror="this.src='/favicon.ico';">
                          <div style="flex: 1; min-width: 0;">
                            <div style="font-size: 11px; font-weight: 600; color: #cbd5e1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${clip.title}">
                              ${clip.title}
                            </div>
                            <div style="display: flex; align-items: center; gap: 6px; margin-top: 3px;">
                              <span style="font-size: 10px; color: #ef4444; font-weight: 700;">YouTube</span>
                              ${clip.duration > 0 ? `<span style="font-size: 10px; color: #94a3b8;">${Math.round(clip.duration)}s</span>` : ''}
                              <a href="${clip.url}" target="_blank" style="font-size: 10px; color: #60a5fa; text-decoration: underline;" onclick="event.stopPropagation();">觀看</a>
                            </div>
                          </div>
                          <button type="button" class="btn-sec" style="font-size: 10px; padding: 4px 8px; border-color: ${isSel ? '#3b82f6' : '#334155'}; color: ${isSel ? '#60a5fa' : '#94a3b8'}; background: ${isSel ? 'rgba(59,130,246,0.15)' : 'transparent'}; font-weight: 700; white-space: nowrap;" onclick="onCharacterSelectClip(${cIdx}, '${clip.url.replace(/'/g, "\'")}', ${isInspector})">
                            ${isSel ? '✓ 已選用片段' : '選用此片段'}
                          </button>
                        </div>
                      `;
                    }).join('')}
                  </div>
                `}
              </div>
            </div>
          </div>
        `;
      });

      html += `
          </div>
        </div>
      `;
      return html;
    }

    function onCharacterSelectImage(charIdx, imgUrl, isInspector) {
      const dataObj = isInspector ? inspectedStageData : studioStageData;
      if (!dataObj || !dataObj.characters || !dataObj.characters[charIdx]) return;
      dataObj.characters[charIdx].selected_image = imgUrl;
      dataObj.characters[charIdx].status = 'approved';
      if (typeof showToast === 'function') showToast(`✓ 已為 ${dataObj.characters[charIdx].name} 選定肖像素材`);
      if (isInspector) {
        if (typeof renderInspectorContent === 'function') renderInspectorContent('research', dataObj);
      } else {
        if (typeof renderStudioWorkspace === 'function') renderStudioWorkspace('research', dataObj, studioProject);
      }
    }

    function onCharacterSelectClip(charIdx, clipUrl, isInspector) {
      const dataObj = isInspector ? inspectedStageData : studioStageData;
      if (!dataObj || !dataObj.characters || !dataObj.characters[charIdx]) return;
      dataObj.characters[charIdx].selected_clip = clipUrl;
      dataObj.characters[charIdx].status = 'approved';
      if (typeof showToast === 'function') showToast(`✓ 已為 ${dataObj.characters[charIdx].name} 選定影片片段`);
      if (isInspector) {
        if (typeof renderInspectorContent === 'function') renderInspectorContent('research', dataObj);
      } else {
        if (typeof renderStudioWorkspace === 'function') renderStudioWorkspace('research', dataObj, studioProject);
      }
    }

    function onCharacterStatusChange(charIdx, status, isInspector) {
      const dataObj = isInspector ? inspectedStageData : studioStageData;
      if (!dataObj || !dataObj.characters || !dataObj.characters[charIdx]) return;
      dataObj.characters[charIdx].status = status;
      if (typeof showToast === 'function') showToast(`✓ ${dataObj.characters[charIdx].name} 狀態已設為: ${status}`);
    }

    function onCharacterScenesChange(charIdx, val, isInspector) {
      const dataObj = isInspector ? inspectedStageData : studioStageData;
      if (!dataObj || !dataObj.characters || !dataObj.characters[charIdx]) return;
      const ids = val.split(/[,，\s]+/).map(s => parseInt(s.trim())).filter(n => !isNaN(n));
      dataObj.characters[charIdx].target_scenes = ids;
    }

    function onCharacterKeywordsChange(charIdx, val, isInspector) {
      const dataObj = isInspector ? inspectedStageData : studioStageData;
      if (!dataObj || !dataObj.characters || !dataObj.characters[charIdx]) return;
      const kws = val.split(/[,，\n]+/).map(s => s.trim()).filter(Boolean);
      dataObj.characters[charIdx].search_keywords = kws;
    }

    async function reSearchCharacterForeign(charIdx, isInspector) {
      if (!currentProjectId) return alert("請先選取專案");
      const dataObj = isInspector ? inspectedStageData : studioStageData;
      if (!dataObj || !dataObj.characters || !dataObj.characters[charIdx]) return;
      const char = dataObj.characters[charIdx];
      const kwInput = document.getElementById(`char-keywords-${charIdx}`);
      const rawKws = kwInput ? kwInput.value : '';
      const kws = rawKws.split(/[,，\n]+/).map(s => s.trim()).filter(Boolean);
      char.search_keywords = kws;

      try {
        if (typeof showToast === 'function') showToast(`🔍 正在以外語原生關鍵詞檢索 ${char.name} 素材...`);
        const result = await apiJson(`/api/projects/${currentProjectId}/characters/search`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: char.name,
            original_name: char.original_name || char.name,
            extra_queries: kws
          })
        });

        if (result.media) {
          char.images = result.media.images || [];
          char.clips = result.media.clips || [];
        }
        if (typeof showToast === 'function') showToast(`✓ 已成功檢索到 ${char.images.length} 張圖片與 ${char.clips.length} 支影片片段！`);
        if (isInspector) {
          if (typeof renderInspectorContent === 'function') renderInspectorContent('research', dataObj);
        } else {
          if (typeof renderStudioWorkspace === 'function') renderStudioWorkspace('research', dataObj, studioProject);
        }
      } catch (e) {
        alert("檢索失敗: " + e.message);
      }
    }

    async function boostCharacterRatio(charIdx, isInspector) {
      if (!currentProjectId) return alert("請先選取專案");
      const dataObj = isInspector ? inspectedStageData : studioStageData;
      if (!dataObj || !dataObj.characters || !dataObj.characters[charIdx]) return;
      const char = dataObj.characters[charIdx];

      const ratioSelect = document.getElementById(`char-clip-ratio-${charIdx}`);
      const clipRatio = ratioSelect ? parseFloat(ratioSelect.value) : 0.7;

      const kwInput = document.getElementById(`char-keywords-${charIdx}`);
      const rawKws = kwInput ? kwInput.value : '';
      const extraQueries = rawKws.split(/[,，\n]+/).map(s => s.trim()).filter(Boolean);

      const targetScenes = Array.isArray(char.target_scenes) ? char.target_scenes : [];

      if (!confirm(`確定要為主角「${char.name}」批次提高真實影音佔比嗎？\n\n- 原生外語搜尋詞: ${extraQueries.join(', ') || char.name}\n- 實拍影片比例: ${Math.round(clipRatio * 100)}% (自動剪輯約 10 秒 YouTube 實拍片段)\n- 劇照比例: ${Math.round((1 - clipRatio) * 100)}%\n- 目標分鏡: ${targetScenes.length ? targetScenes.join(', ') : '自動比對主角分鏡'}\n\n這將把真實歷史影片與劇照寫入對應分鏡，大幅提高紀錄片真實畫面佔比！`)) {
        return;
      }

      try {
        if (typeof showToast === 'function') showToast(`⚡ 正在批次下載與裁切 ~10s 實拍影片片段與劇照 (需數十秒)...`);
        const result = await apiJson(`/api/projects/${currentProjectId}/characters/boost_ratio`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            character_name: char.name,
            target_scenes: targetScenes,
            clip_ratio: clipRatio,
            extra_queries: extraQueries
          })
        });

        if (result.status === 'success') {
          const updated = result.updated_scenes || [];
          alert(`✓ 成功提高主角「${char.name}」真實影音佔比！\n\n已更新分鏡: [${updated.join(', ')}]\n包含約 10 秒真實影片片段與高畫質劇照。\n\n請前往 Stage 10 點擊「Render 1080p Video」合成最新畫面！`);
          if (typeof loadStageStudio === 'function') loadStageStudio('research');
        } else {
          alert("處理失敗: " + JSON.stringify(result));
        }
      } catch (e) {
        alert("操作失敗: " + e.message);
      }
    }

    async function enforceMainCharacterRealRatio(isInspector) {
      if (!currentProjectId) return alert("請先選取專案");
      if (!confirm("確定要將主角提及分鏡的真實素材（實拍影片與劇照）提高至 90% 以上嗎？\n\n系統將自動分析所有提及主角的分鏡，自動抓取並裁切約 10 秒 YouTube 實拍片段與真實劇照覆蓋 AI 生成圖。")) {
        return;
      }
      try {
        if (typeof showToast === 'function') showToast("⚡ 正在分析主角登場分鏡並提高真實影音佔比至 90% (需數十秒)...");
        const result = await apiJson(`/api/projects/${currentProjectId}/characters/enforce_real_ratio`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ratio: 0.9, clip_ratio: 0.7 })
        });

        if (result.status === 'success') {
          const updated = result.updated_scenes || [];
          alert(`✓ 成功確保主角「${result.character}」分鏡真實影音佔比達 ${result.real_percentage}%！\n\n主角登場分鏡: ${result.total_mentioned_scenes} 個\n已覆蓋真實素材: ${result.real_scenes_count} 個 (${result.real_percentage}%)\n本次新更新分鏡: [${updated.join(', ')}]\n\n請前往 Stage 10 點擊「Render 1080p Video」合成最新畫面！`);
          if (typeof loadStageStudio === 'function') loadStageStudio('research');
        } else {
          alert("處理結果: " + JSON.stringify(result));
        }
      } catch (e) {
        alert("操作失敗: " + e.message);
      }
    }

    async function rescanProjectCharacters(isInspector) {
      if (!currentProjectId) return alert("請先選取專案");
      try {
        if (typeof showToast === 'function') showToast("🔍 正在重新掃描人物與檢索網路真實素材...");
        const json = await apiJson(`/api/projects/${currentProjectId}/characters?rescan=true`);

        const dataObj = isInspector ? inspectedStageData : studioStageData;
        if (dataObj) {
          dataObj.characters = json.characters || [];
        }
        if (isInspector) {
          if (typeof renderInspectorContent === 'function') renderInspectorContent('research', dataObj);
        } else {
          if (typeof renderStudioWorkspace === 'function') renderStudioWorkspace('research', dataObj, studioProject);
        }
        if (typeof showToast === 'function') showToast(`✓ 成功檢索到 ${json.characters?.length || 0} 位人物資料！`);
      } catch (e) {
        alert("檢索失敗: " + e.message);
      }
    }

    async function applyApprovedCharacterMedia(isInspector) {
      if (!currentProjectId) return alert("請先選取專案");
      const dataObj = isInspector ? inspectedStageData : studioStageData;
      const characters = dataObj ? dataObj.characters : [];
      if (!characters || !characters.length) return alert("尚無人物資料");

      try {
        if (typeof showToast === 'function') showToast("⏳ 正在將選定的真實肖像與歷史片段套用至分鏡...");
        const result = await apiJson(`/api/projects/${currentProjectId}/characters/apply`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ characters })
        });

        const updated = result.updated_scenes || [];
        alert(`✓ 成功將真實歷史影音套用至分鏡 [${updated.join(', ')}]！
已標記為真實素材，渲染時將使用歷史肖像或片段。`);
        if (typeof loadStageStudio === 'function') loadStageStudio('research');
      } catch (e) {
        alert("套用失敗: " + e.message);
      }
    }

    /* ==========================================================================
       STAGE STUDIO (Independent Stage Playground & Assembly)
       ========================================================================== */
    const STAGE_META = {
      research: { num: 1, name: "Research", icon: "🔬", title: "Stage 1/10: Topic Research & Knowledge Base", desc: "AI-driven topic research and fact gathering to provide accurate context for your video topic.", runBtn: "▶ Run Topic Research Only" },
      script: { num: 2, name: "Script", icon: "📝", title: "Stage 2/10: Narration Scriptwriting", desc: "Drafts a compelling YouTube narration script formatted with intro, hook, core points, and outro.", runBtn: "▶ Run Scriptwriting Only" },
      scenes: { num: 3, name: "Scenes", icon: "🎬", title: "Stage 3/10: Storyboard & Scene Segmentation", desc: "Segments your script into timed visual scenes with camera motions (pan, zoom, static).", runBtn: "▶ Run Scene Segmentation Only" },
      prompts: { num: 4, name: "Prompts", icon: "🎨", title: "Stage 4/10: Prompt Engineering & Art Style", desc: "Transforms each scene's visual description into detailed SDXL prompts using your chosen art style.", runBtn: "▶ Run Prompt Generation Only" },
      images: { num: 5, name: "Images", icon: "🖼️", title: "Stage 5/10: AI Image Generation (ComfyUI DirectML)", desc: "Generates high-res visual assets for every scene using ComfyUI DirectML hardware acceleration.", runBtn: "▶ Generate All Scene Images" },
      voice: { num: 6, name: "Voice TTS", icon: "🎙️", title: "Stage 6/10: Voiceover Synthesis (BlueMagpie-TTS)", desc: "Synthesizes expressive voiceover audio per scene using BlueMagpie-TTS voice cloning or local TTS.", runBtn: "▶ Synthesize Full Voiceover" },
      music: { num: 7, name: "Ambient Music", icon: "🎶", title: "Stage 7/10: Ambient Music & Narrative Progression", desc: "Plans and mixes dynamic multi-movement background music (Opening Context ➔ Rising Stakes ➔ Uplifting Resolution).", runBtn: "▶ Plan & Mix Ambient Music" },
      animation: { num: 8, name: "Animation", icon: "🎞️", title: "Stage 8/10: Motion Dynamics & Video FX", desc: "Applies pan/zoom camera motion dynamics or AI video interpolation to static images.", runBtn: "▶ Run Animation Processing Only" },
      subtitles: { num: 9, name: "Subtitles", icon: "💬", title: "Stage 9/10: Subtitles & Timed Captions", desc: "Generates precisely timed .srt subtitles aligned with voiceover narration for on-screen display.", runBtn: "▶ Generate Subtitles Only" },
      render: { num: 10, name: "Render", icon: "🎥", title: "Stage 10/10: Final 1080p Video Composition", desc: "Composes all scenes, animations, voiceovers, background music, and subtitles into a 1080p MP4.", runBtn: "▶ Render 1080p Video" }
    };

    const STAGE_META_DRAMA = {
      research: { num: 1, name: "故事分鏡", icon: "📋", title: "Stage 1/9: 故事大綱與節奏分鏡 (Storyboard)", desc: "依據短劇爆款公式（職場逆襲、真假千金等）生成前3秒黃金反轉點與高張力情緒節奏分鏡大綱。", runBtn: "▶ 重新生成分鏡大綱" },
      script: { num: 2, name: "角色對白", icon: "🎭", title: "Stage 2/9: 角色台詞劇本創作 (Script)", desc: "依選定時長（50s 約 3~4 幕，90s 約 5~6 幕）精準撰寫各角色高張力對白劇本。", runBtn: "▶ 重新生成角色對白劇本" },
      scenes: { num: 3, name: "場景分配", icon: "🎬", title: "Stage 3/9: 分鏡場景與角色分配 (Scenes Allocation)", desc: "將劇本對白分配到各個動畫場景，並綁定角色定妝立繪與專屬音色（visual_type = talking_actor）。", runBtn: "▶ 重新分配分鏡場景" },
      prompts: { num: 4, name: "動作提示", icon: "🎨", title: "Stage 4/9: 角色動作與表情提示詞 (Action Prompts)", desc: "生成角色在各幕中的神態、微表情、鏡頭景別與動作提示詞（9:16 直式）。", runBtn: "▶ 重新生成動作提示詞" },
      images: { num: 5, name: "角色動態", icon: "🧍", title: "Stage 5/9: 生成角色動態影片 (Animated Actor Video)", desc: "基於設定的角色肖像與動作提示詞，生成具備真實呼吸微動態與景深運鏡的角色立繪影片（9:16 直式）。", runBtn: "▶ 生成角色動態影片" },
      voice: { num: 6, name: "角色配音", icon: "🎙️", title: "Stage 6/9: 角色專屬聲音生成 (Voice Generation)", desc: "依據各角色的專屬音色檔案（Voice Profile）獨立生成高音質對白音頻。", runBtn: "▶ 合成所有角色配音" },
      animation: { num: 7, name: "對嘴合成", icon: "👄", title: "Stage 7/9: 影音精確對嘴合成 (Hedra Lip-Sync)", desc: "調用 Hedra Character-2 對嘴引擎或本地音頻共振，精確對齊唇形與面部表情（嚴格禁用 Remotion 與靜態過場）。", runBtn: "▶ 執行 Hedra 角色對嘴合成" },
      subtitles: { num: 8, name: "短劇字幕", icon: "💬", title: "Stage 8/9: 直式短劇字幕排版 (Subtitles)", desc: "自動生成雙行高對比短劇專用字幕，帶有動態高亮，無橫式覆蓋衝突。", runBtn: "▶ 生成短劇專用字幕" },
      render: { num: 9, name: "最終渲染", icon: "🎥", title: "Stage 9/9: 母帶混音與最終渲染 (Master Rendering)", desc: "以 1.0x 原始唇形速率合成垂直 1080x1920 60/30fps MP4 母帶影片（無章節過場黑屏）。", runBtn: "▶ 渲染 9:16 短劇母帶" }
    };

    // Which Stage Studio is open: 'documentary' | 'short_drama'
    let studioMode = 'documentary';
    let allProjectsCache = [];

    function projectModeOf(p) {
      if (!p) return 'documentary';
      if (p.project_mode) return p.project_mode;
      if (p.settings && p.settings.project_mode) return p.settings.project_mode;
      if (p.data && p.data.settings && p.data.settings.project_mode) return p.data.settings.project_mode;
      return 'documentary';
    }

    function applyStudioModeChrome() {
      const drama = (studioMode === 'short_drama');
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
      set('studio-mode-icon', drama ? '🎭' : '🛠️');
      set('studio-mode-title', drama ? 'Short Drama Stage Studio' : 'Documentary Stage Studio');
      set('studio-mode-badge', drama ? '9:16 Short Drama' : '16:9 Documentary');
      set('studio-mode-desc', drama
        ? 'Work on each short-drama stage independently: storyboard, character dialogue, scene casting, action prompts, actor video, voices, lip-sync, subtitles and master render.'
        : 'Play around with each documentary stage independently: research, script, scenes, prompts, images, voice, ambient music, animation, subtitles and render.');
      const card = document.getElementById('tab-studio') && document.querySelector('#tab-studio > .card');
      if (card) card.style.borderColor = drama ? '#7c3aed' : '#2b456b';
      const badge = document.getElementById('studio-mode-badge');
      if (badge) badge.className = drama ? 'badge badge-warn' : 'badge badge-blue';
    }

    function renderStudioProjectBar() {
      const bar = document.getElementById('studio-project-bar');
      if (!bar) return;
      const mine = allProjectsCache.filter(p => projectModeOf(p) === studioMode);
      const label = studioMode === 'short_drama' ? 'Drama projects' : 'Documentary projects';
      if (!mine.length) { bar.innerHTML = `<span>No ${label.toLowerCase()} yet.</span>`; return; }
      bar.innerHTML = `<span>${label}:</span><select style="font-size:12px; padding:4px 8px; max-width:420px;" onchange="selectProject(this.value)">${mine.map(p => `<option value="${p.id}" ${p.id === currentProjectId ? 'selected' : ''}>[${p.id}] ${(p.title || p.topic || p.id).toString().replace(/</g, '&lt;')}</option>`).join('')}</select>`;
    }

    function renderStudioModeMismatch(project) {
      const wsEl = document.getElementById('studio-stage-workspace');
      const stepperEl = document.getElementById('studio-stepper');
      if (stepperEl) stepperEl.innerHTML = '';
      if (!wsEl) return;
      const projMode = projectModeOf(project);
      const otherTab = projMode === 'short_drama' ? 'dramastudio' : 'studio';
      const otherName = projMode === 'short_drama' ? 'Drama Stage Studio' : 'Documentary Stage Studio';
      const mine = allProjectsCache.filter(p => projectModeOf(p) === studioMode);
      const myName = studioMode === 'short_drama' ? 'short drama' : 'documentary';
      wsEl.innerHTML = `
        <div style="text-align:center; padding:50px 20px; color:var(--text-muted);">
          <div style="font-size:36px; margin-bottom:12px;">${studioMode === 'short_drama' ? '🎭' : '🛠️'}</div>
          <h3 style="color:#fff; margin-bottom:8px;">Selected project is a ${projMode === 'short_drama' ? 'short drama' : 'documentary'} project</h3>
          <p style="font-size:13px; max-width:520px; margin:0 auto 18px auto;">This studio only works on ${myName} projects because the stages differ by nature.</p>
          <div style="display:flex; gap:10px; justify-content:center; flex-wrap:wrap;">
            <button class="btn-primary" onclick="switchTab('${otherTab}')">Open in ${otherName}</button>
            ${mine.length ? `<button class="btn-sec" onclick="selectProject('${mine[0].id}')">Switch to latest ${myName} project</button>` : `<button class="btn-sec" onclick="switchTab('${studioMode === 'short_drama' ? 'drama' : 'creator'}')">Create a ${myName} project</button>`}
          </div>
        </div>`;
    }

    function isDramaStudioProject(proj = null) {
      const p = proj || currentProject || studioProject;
      if (p) {
        if (p.settings && p.settings.project_mode === 'short_drama') return true;
        if (p.data && p.data.settings && p.data.settings.project_mode === 'short_drama') return true;
        if (p.project_mode === 'short_drama') return true;
      }
      const studioActive = document.getElementById('tab-studio') && document.getElementById('tab-studio').classList.contains('active');
      if (studioActive) return studioMode === 'short_drama';
      return currentCreatorProjectMode === 'short_drama';
    }

    let activeStudioStage = 'research';
    let studioStageData = null;
    let studioProject = null;
    let studioStageRunning = null;
    let studioStageStarted = false;

    function openStudioStage(stageName) {
      if (stageName) activeStudioStage = stageName;
      const cur = allProjectsCache.find(p => p.id === currentProjectId);
      switchTab(projectModeOf(cur) === 'short_drama' ? 'dramastudio' : 'studio');
    }

    function switchStudioStage(stKey) {
      activeStudioStage = stKey;
      loadStageStudio(stKey);
    }

    async function loadStageStudio(targetStage) {
      if (targetStage) activeStudioStage = targetStage;
      const wsEl = document.getElementById('studio-stage-workspace');
      const stepperEl = document.getElementById('studio-stepper');

      if (!currentProjectId) {
        if (wsEl) {
          wsEl.innerHTML = `
            <div style="text-align: center; padding: 60px 20px; color: var(--text-muted);">
              <div style="font-size: 36px; margin-bottom: 12px;">🛠️</div>
              <h3 style="color: #fff; margin-bottom: 8px;">No Project Selected</h3>
              <p style="font-size: 13px; max-width: 480px; margin: 0 auto 20px auto;">Please select an existing project from the top header or create a new project in the Creator tab to use the Stage Studio.</p>
              <button onclick="switchTab('creator')">Go to Creator</button>
            </div>
          `;
        }
        if (stepperEl) stepperEl.innerHTML = '';
        return;
      }

      // Fetch project details for stepper statuses
      try {
        const pData = await apiJson(`/api/projects/${currentProjectId}`);

        studioProject = pData.project;
        currentProject = pData.project;
        currentScenes = pData.scenes || [];
        renderStudioProjectBar();
        if (projectModeOf(studioProject) !== studioMode) {
          renderStudioModeMismatch(studioProject);
          return;
        }
        renderStudioStepper(studioProject);
      } catch (e) {
        console.error("Failed to load project for studio stepper", e);
      }

      // Show loading in workspace
      const isDramaProj = isDramaStudioProject(studioProject);
      const activeMetaMap = isDramaProj ? STAGE_META_DRAMA : STAGE_META;
      const meta = activeMetaMap[activeStudioStage] || STAGE_META[activeStudioStage] || {};
      if (wsEl) {
        wsEl.innerHTML = `
          <div style="text-align: center; padding: 50px; color: var(--text-muted);">
            <div class="spinner-inline" style="width: 28px; height: 28px; margin-bottom: 12px;"></div>
            <div>Loading ${meta.title || activeStudioStage}...</div>
          </div>
        `;
      }

      // Fetch stage data
      try {
        const sData = await apiJson(`/api/projects/${currentProjectId}/stage_data/${activeStudioStage}`);

        studioStageData = sData;
        renderStudioWorkspace(activeStudioStage, sData, studioProject);
      } catch (e) {
        if (wsEl) {
          wsEl.innerHTML = `<div style="color: #ef4444; padding: 30px; text-align: center;">Failed to load stage data: ${e.message}</div>`;
        }
      }
    }

    function renderStudioStepper(project) {
      const stepperEl = document.getElementById('studio-stepper');
      if (!stepperEl || !project) return;

      let html = '';
      const isDramaProj = isDramaStudioProject(project);
      const activeStageOrder = isDramaProj ? STAGE_ORDER.filter(s => s !== 'music') : STAGE_ORDER;
      activeStageOrder.forEach((stKey, idx) => {
        const isDrama = isDramaStudioProject(project);
        const activeMetaMap = isDrama ? STAGE_META_DRAMA : STAGE_META;
        const meta = activeMetaMap[stKey] || STAGE_META[stKey];
        const st = project.stages ? project.stages[stKey] : null;
        const isActive = (stKey === activeStudioStage);
        const sDur = (st && st.duration_seconds) ? Number(st.duration_seconds) : ((project.stage_durations && project.stage_durations[stKey]) ? Number(project.stage_durations[stKey]) : 0);

        let badgeHtml = '<span style="font-size: 12px; background: #1e293b; color: #94a3b8; padding: 2px 6px; border-radius: 10px;">⚪ Pending</span>';
        if (st) {
          if (st.status === 'COMPLETED') {
            const dStr = formatDuration(sDur > 0 ? sDur : 0.1);
            badgeHtml = `<span style="font-size: 11px; background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); padding: 2px 7px; border-radius: 10px; font-family: monospace;">✓ ${dStr}</span>`;
          } else if (st.status === 'RUNNING') {
            const liveElapsed = st.started_at ? Math.max(0.1, (Date.now() - new Date(st.started_at).getTime()) / 1000) : 0;
            badgeHtml = `<span style="font-size: 11px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); padding: 2px 7px; border-radius: 10px; font-family: monospace;">⏳ ${liveElapsed > 0 ? formatDuration(liveElapsed) : 'Running'}</span>`;
          } else if (st.status === 'FAILED') {
            badgeHtml = '<span style="font-size: 12px; background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); padding: 2px 6px; border-radius: 10px;">✕ Failed</span>';
          }
        }

        const activeStyles = isActive
          ? 'background: linear-gradient(135deg, #233B6D 0%, #39295B 100%); border: 2px solid #C19D49; box-shadow: 0 0 14px rgba(193, 157, 73, 0.35); color: #fff;'
          : 'background: rgba(14, 20, 34, 0.7); border: 1px solid rgba(124, 145, 182, 0.25); color: #cbd5e1;';

        html += `
          <button onclick="switchStudioStage('${stKey}')" style="${activeStyles} border-radius: 8px; padding: 8px 12px; font-size: 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 8px; white-space: nowrap; transition: all 0.2s;">
            <span style="font-size: 14px;">${meta.icon}</span>
            <span>${meta.num}. ${meta.name}</span>
            ${badgeHtml}
          </button>
        `;
      });

      stepperEl.innerHTML = html;
    }

    function renderStudioWorkspace(stKey, data, project) {
      const wsEl = document.getElementById('studio-stage-workspace');
      if (!wsEl) return;

      const isDrama = isDramaStudioProject(project);
      const activeMetaMap = isDrama ? STAGE_META_DRAMA : STAGE_META;
      const meta = activeMetaMap[stKey] || STAGE_META[stKey] || {};
      const st = project && project.stages ? project.stages[stKey] : null;
      const isProjectActive = project && (project.state === 'running');
      const isThisStageTracked = (typeof studioStageRunning !== 'undefined' && studioStageRunning === stKey);
      const isRunning = st && (st.status === 'RUNNING') && (isProjectActive || isThisStageTracked);
      const isDone = st && st.status === 'COMPLETED';
      const stDurVal = (st && st.duration_seconds) ? Number(st.duration_seconds) : ((project && project.stage_durations && project.stage_durations[stKey]) ? Number(project.stage_durations[stKey]) : 0);
      const stDurChipHtml = (isDone || stDurVal > 0)
        ? `<span style="font-size: 12px; padding: 3px 9px; border-radius: 12px; font-weight: 700; font-family: monospace; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35);">⏱️ ${formatDuration(stDurVal > 0 ? stDurVal : 0.1)}</span>`
        : '';

      // Stage Model Selector for this workspace
      const currentSm = (project && project.settings && project.settings.stage_models) ? project.settings.stage_models[stKey] : null;
      let stageModelSwitcherHtml = '';
      if (stKey === 'images') {
        stageModelSwitcherHtml = `
          <div style="display:flex; align-items:center; gap:6px; font-size:12px; background:var(--bg-sunken); padding:4px 8px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin:0;">Model:</label>
            <select style="padding:4px 8px; font-size:12px; border-radius:var(--radius-sm); background:var(--bg-canvas); color:var(--text-primary); border:1px solid var(--border-muted);" onchange="updateStudioStageModel('images', this.value)">
              <option value="nano-banana-2.1" ${currentSm === 'nano-banana-2.1' || !currentSm ? 'selected' : ''}>Cloud API: Google Nano Banana 2.1 ($0.0168/img Batch • ~$0.67/40 sc) (Recommended)</option>
              <option value="fal-ai/flux-1/schnell" ${currentSm === 'fal-ai/flux-1/schnell' || currentSm === 'fal-ai/flux/schnell' ? 'selected' : ''}>Cloud API: fal-ai/flux-1/schnell ($0.003/img • ~$0.12/40 sc)</option>
              <option value="comfyui" ${currentSm === 'comfyui' ? 'selected' : ''}>Local GPU: ComfyUI DirectML ($0.00 / Free)</option>
              <option value="stock" ${currentSm === 'stock' ? 'selected' : ''}>🌐 Online Stock Photos & Footage ($0.00 / Free, 0 VRAM)</option>
              <option value="gpt-image-1" ${currentSm === 'gpt-image-1' ? 'selected' : ''}>Cloud API: OpenAI gpt-image-1 ($0.08/img • ~$3.20/40 sc)</option>
              <option value="imagen-3.0-generate-002" ${currentSm === 'imagen-3.0-generate-002' || currentSm === 'imagen-30.0-generate-002' ? 'selected' : ''}>Cloud API: Google imagen-3.0-generate-002 ($0.04/img • ~$1.60/40 sc)</option>
              <option value="dalle3" ${currentSm === 'dalle3' ? 'selected' : ''}>Cloud API: OpenAI DALL-E 3 ($0.04/img • ~$1.60/40 sc)</option>
              <option value="imagen3" ${currentSm === 'imagen3' ? 'selected' : ''}>Cloud API: Google Gemini Flash Image ($0.03/img • ~$1.20/40 sc)</option>
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
        if (isDrama) {
          stageModelSwitcherHtml = `
            <div style="display:flex; align-items:center; gap:6px; font-size:12px; background:var(--bg-sunken); padding:4px 8px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
              <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin:0;">Storyboard Model:</label>
              <select style="padding:4px 8px; font-size:12px; border-radius:var(--radius-sm); background:var(--bg-canvas); color:var(--text-primary); border:1px solid var(--border-muted);" onchange="updateStudioStageModel('research', this.value)">
                <option value="gemini" ${currentSm === 'gemini' || !currentSm ? 'selected' : ''}>Cloud: Gemini 3.8 Flash (推薦)</option>
                <option value="ollama" ${currentSm === 'ollama' ? 'selected' : ''}>Local: Ollama (qwen3:8b)</option>
                <option value="openai_compat" ${currentSm === 'openai_compat' ? 'selected' : ''}>Cloud: GPT-4o-mini</option>
              </select>
            </div>
          `;
        } else {
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
        }
      } else if (stKey === 'voice') {
        stageModelSwitcherHtml = `
          <div style="display:flex; align-items:center; gap:6px; font-size:12px; background:var(--bg-sunken); padding:4px 8px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin:0;">Voice:</label>
            <select style="padding:4px 8px; font-size:12px; border-radius:var(--radius-sm); background:var(--bg-canvas); color:var(--text-primary); border:1px solid var(--border-muted);" onchange="updateStudioStageModel('voice', this.value)">
              <option value="bluemagpie" ${currentSm === 'bluemagpie' || !currentSm ? 'selected' : ''}>Local: BlueMagpie Voice Clone</option>
              <option value="cosyvoice" ${currentSm === 'cosyvoice' ? 'selected' : ''}>Local: CosyVoice 2 Voice Clone</option>
              <option value="http_clone" ${currentSm === 'http_clone' ? 'selected' : ''}>Local: F5-TTS (HTTP Voice Clone)</option>
              <option value="voai" ${currentSm === 'voai' ? 'selected' : ''}>Cloud: VoAI 絕好聲創 (Taiwan Mandarin)</option>
              <option value="elevenlabs" ${currentSm === 'elevenlabs' ? 'selected' : ''}>Cloud: ElevenLabs Studio</option>
              <option value="edge" ${currentSm === 'edge' ? 'selected' : ''}>Cloud: Microsoft Edge TTS (Free)</option>
              <option value="sapi" ${currentSm === 'sapi' ? 'selected' : ''}>Local: Windows SAPI</option>
            </select>
          </div>
        `;
      } else if (stKey === 'music') {
        stageModelSwitcherHtml = `
          <div style="display:flex; align-items:center; gap:6px; font-size:12px; background:var(--bg-sunken); padding:4px 8px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin:0;">Progression:</label>
            <select style="padding:4px 8px; font-size:12px; border-radius:var(--radius-sm); background:var(--bg-canvas); color:var(--text-primary); border:1px solid var(--border-muted);" onchange="updateStudioMusicProgression(this.value)">
              <option value="narrative_evolving" selected>🌟 多樂章劇情演進 (3-Movement Progression)</option>
              <option value="single_loop">🔄 單曲循環 (Single Track Loop)</option>
            </select>
          </div>
        `;
      } else if (stKey === 'animation') {
        stageModelSwitcherHtml = `
          <div style="display:flex; align-items:center; gap:6px; font-size:12px; background:var(--bg-sunken); padding:4px 8px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin:0;">Engine:</label>
            <select style="padding:4px 8px; font-size:12px; border-radius:var(--radius-sm); background:var(--bg-canvas); color:var(--text-primary); border:1px solid var(--border-muted);" onchange="updateStudioStageModel('animation', this.value)">
              ${isDrama ? `
                <option value="hedra" ${currentSm === 'hedra' || !currentSm ? 'selected' : ''}>🌟 Cloud: Hedra Character-3 Lip-Sync (推薦 · 真實對嘴)</option>
                <option value="kling_avatar" ${currentSm === 'kling_avatar' ? 'selected' : ''}>⚡ Cloud: Fal Kling AI Avatar (對嘴演員)</option>
                <option value="local_fallback" ${currentSm === 'local_fallback' || currentSm === 'kenburns' ? 'selected' : ''}>🖥️ Local: 音頻共振呼吸動態備用方案 ($0)</option>
                <option value="minimax" ${currentSm === 'minimax' ? 'selected' : ''}>🌊 Cloud: MiniMax 海螺 Video-01 (場景動作 · 無對嘴)</option>
              ` : `
                <option value="remotion" ${currentSm === 'remotion' || currentSm === 'motion_graphics' ? 'selected' : ''}>⚛️ Remotion: 100% Motion Graphics (AI Director)</option>
                <option value="remotion_coordinate_scale" ${currentSm === 'remotion_coordinate_scale' ? 'selected' : ''}>🧭 Remotion: 座標零 · 等緯尺度</option>
                <option value="remotion_finance_candlestick" ${currentSm === 'remotion_finance_candlestick' ? 'selected' : ''}>📈 Remotion: 財經趨勢 · 走勢K線</option>
                <option value="remotion_archival_doc" ${currentSm === 'remotion_archival_doc' ? 'selected' : ''}>📜 Remotion: 歷史檔案 · 解密文檔</option>
                <option value="remotion_vox_split" ${currentSm === 'remotion_vox_split' ? 'selected' : ''}>🗞️ Remotion: Vox 調查 · 政策雙分割</option>
                <option value="remotion_evidence" ${currentSm === 'remotion_evidence' ? 'selected' : ''}>📑 Remotion: 科技藍圖 · 文獻劃記</option>
                <option value="kenburns" ${currentSm === 'kenburns' || (!currentSm && (!project || !project.settings || !project.settings.remotion)) ? 'selected' : ''}>Local: Ken Burns 2.5D Motion</option>
                <option value="comfyui_video" ${currentSm === 'comfyui_video' ? 'selected' : ''}>Local: ComfyUI Video</option>
                <option value="veo" ${currentSm === 'veo' ? 'selected' : ''}>Cloud: Google Veo</option>
                <option value="kling" ${currentSm === 'kling' ? 'selected' : ''}>Cloud: Kling Video AI</option>
                <option value="runway" ${currentSm === 'runway' ? 'selected' : ''}>Cloud: Runway Gen-3</option>
              `}
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
              ${stDurChipHtml}
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
            ${stKey === 'scenes' ? `
              <button class="btn-sec" style="padding: 8px 14px; font-size: 12px; background: rgba(56, 189, 248, 0.15); border-color: #0284c7; color: #38bdf8; font-weight: 700; display: inline-flex; align-items: center; gap: 6px;" onclick="openStage3ExportModal()" title="匯出 Stage 3 分鏡審閱腳本（支援 .txt/.csv/.md/純台詞/PDF 列印）">
                📤 匯出審閱腳本 (Export Script)
              </button>
            ` : ''}
            ${stKey === 'research' ? `
              <button class="btn-primary" style="padding: 8px 16px; font-size: 12px; font-weight: 700; background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%); border: 1px solid #8b5cf6;" onclick="runCascadeFrom('script')" title="Auto-runs Script -> Storyboard -> Prompts -> Images -> Voice -> Video">
                ⚡ Re-generate Full Video (重製全片)
              </button>
            ` : (['scenes', 'prompts', 'images'].includes(stKey) ? `
              <button class="btn-primary" style="padding: 8px 16px; font-size: 12px; font-weight: 700; background: linear-gradient(135deg, #059669 0%, #047857 100%); border: 1px solid #10b981;" onclick="runCascadeFrom('scenes')" title="Keeps script & voice; re-generates Storyboard -> Prompts -> Images -> Video">
                🎨 Re-generate Visuals & Video (重製畫面與成片)
              </button>
            ` : '')}
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
      if (stKey === 'research') alertMsg = isDrama ? 'AI 短劇分鏡大綱生成中...' : 'AI Researcher is analyzing topic & gathering knowledge...';
      else if (stKey === 'script') alertMsg = isDrama ? 'AI 短劇編劇撰寫對白與情節中...' : 'AI Scriptwriter is drafting a fresh narration script...';
      else if (stKey === 'scenes') alertMsg = isDrama ? 'AI 短劇分鏡與人物出場拆解中...' : 'AI Storyboarder is segmenting scenes & camera motions...';
      else if (stKey === 'prompts') alertMsg = isDrama ? 'AI 生成人物定妝與場景提示詞中...' : 'AI Prompt Engineer is synthesizing visual prompts...';
      else if (stKey === 'images') alertMsg = isDrama ? '生圖模型生成 9:16 直式人物定妝肖像與場景中...' : 'Rendering high-res scene images...';
      else if (stKey === 'voice') alertMsg = isDrama ? '合成各角色專屬對白配音中...' : 'Synthesizing expressive voiceover audio...';
      else if (stKey === 'music') alertMsg = '規劃多樂章敘事配樂時序與情緒調性中 (Planning Ambient Music Timeline)...';
      else if (stKey === 'animation') alertMsg = isDrama ? 'AI 生成演員角色對嘴與動態微表情影片中...' : 'Processing motion dynamics and animation...';
      else if (stKey === 'subtitles') alertMsg = '對齊短劇字幕時間軸...';
      else if (stKey === 'render') alertMsg = isDrama ? 'FFmpeg 正在組裝 9:16 短劇影片、人物動態與音軌...' : 'FFmpeg is assembling scenes, audio, and subtitles into 1080p MP4...';

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
        let resObj = {};
        if (typeof data.research === 'string') {
          try { resObj = JSON.parse(data.research); } catch(e) { resObj = { notes: data.research }; }
        } else if (data.research && typeof data.research === 'object') {
          resObj = data.research;
        }
        const resText = JSON.stringify(resObj, null, 2);
        const ws = resObj.world_setting || {};
        const stringifyWsVal = (v) => {
          if (!v) return '';
          if (typeof v === 'string') return v;
          if (Array.isArray(v)) {
            return v.map(item => (typeof item === 'object' ? ((item.location || item.name || '') + ': ' + (item.description || item.architectural_details || JSON.stringify(item))).trim().replace(/^:\s*/, '') : String(item))).join('; ');
          }
          if (typeof v === 'object') {
            return Object.entries(v).map(([k, val]) => `${k}: ${typeof val === 'object' ? JSON.stringify(val) : val}`).join('\n');
          }
          return String(v);
        };
        const wsEra = (stringifyWsVal(ws.temporal_era) || '').replace(/"/g, '&quot;');
        const wsEnv = (stringifyWsVal(ws.environment_reality) || '').replace(/"/g, '&quot;');
        const wsSettings = (stringifyWsVal(ws.key_settings) || '').replace(/"/g, '&quot;');
        const wsEnsemble = stringifyWsVal(ws.ensemble_specs) || '';
        const wsNegatives = Array.isArray(ws.negative_anachronisms) ? ws.negative_anachronisms.join('\n') : (ws.negative_anachronisms || '');
        bodyHtml += renderFactCheckCardHtml(data.fact_check || (resObj && resObj.fact_check));

        bodyHtml += `
          <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(59, 130, 246, 0.35); border-radius: 8px; padding: 16px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
              <div style="font-weight: 700; color: #93c5fd; font-size: 14px; display: flex; align-items: center; gap: 8px;">
                <span>🌐</span> World Setting & Historical Constraints (世界觀與歷史約束規格)
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <button class="btn-sec" style="font-size: 11px; padding: 4px 10px; background: rgba(59, 130, 246, 0.2); border-color: #3b82f6; color: #93c5fd; font-weight: 700;" onclick="autoGenerateWorldSetting(this)">
                  ✨ Auto-Generate from Topic (AI 快速生成世界觀)
                </button>
                <span style="font-size: 11px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); padding: 2px 8px; border-radius: 12px;">Grounding Stage 3 & 4</span>
              </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px;">
              <div>
                <label style="font-size: 12px; font-weight: 600; color: #cbd5e1; display: block; margin-bottom: 4px;">📅 Temporal Era / Year (時代背景與年份):</label>
                <input type="text" id="studio-ws-era" value="${wsEra}" placeholder="e.g. 1945-1946 Post-WWII / 日本投降至東京審判" style="width: 100%; background: #080d16; border: 1px solid var(--card-border); color: #fff; padding: 8px 10px; border-radius: 6px; font-size: 12px;" oninput="syncWorldSettingToJson()">
              </div>
              <div>
                <label style="font-size: 12px; font-weight: 600; color: #cbd5e1; display: block; margin-bottom: 4px;">🏛️ Physical Locations & Indoors/Outdoors (核心場景與建築):</label>
                <input type="text" id="studio-ws-settings" value="${wsSettings}" placeholder="e.g. 市谷陸軍省大講堂審判大廳、木造長桌法官席、室內吊燈" style="width: 100%; background: #080d16; border: 1px solid var(--card-border); color: #fff; padding: 8px 10px; border-radius: 6px; font-size: 12px;" oninput="syncWorldSettingToJson()">
              </div>
            </div>
            <div style="margin-bottom: 12px;">
              <label style="font-size: 12px; font-weight: 600; color: #cbd5e1; display: block; margin-bottom: 4px;">🏚️ Environment & Damage Reality (環境實況與破壞程度):</label>
              <input type="text" id="studio-ws-env" value="${wsEnv}" placeholder="e.g. 東京大轟炸後的大片廢墟、焦黑殘木瓦礫、臨時防空棚戶，絕無現代高樓" style="width: 100%; background: #080d16; border: 1px solid var(--card-border); color: #fff; padding: 8px 10px; border-radius: 6px; font-size: 12px;" oninput="syncWorldSettingToJson()">
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
              <div>
                <label style="font-size: 12px; font-weight: 600; color: #cbd5e1; display: block; margin-bottom: 4px;">👥 Ensemble & Demographics (人物群體、性別與國籍規格):</label>
                <textarea id="studio-ws-ensemble" rows="3" placeholder="e.g. 11位盟國法官全為男性，包含1位印度法官、1位菲律賓法官、1位中國法官，身著1940年代深色正裝法袍" style="width: 100%; background: #080d16; border: 1px solid var(--card-border); color: #fff; padding: 8px 10px; border-radius: 6px; font-size: 12px; resize: vertical;" oninput="syncWorldSettingToJson()">${escapeHtml(wsEnsemble)}</textarea>
              </div>
              <div>
                <label style="font-size: 12px; font-weight: 600; color: #f87171; display: block; margin-bottom: 4px;">🚫 Negative Anachronisms (嚴格禁止的時代違和元素，每行一項):</label>
                <textarea id="studio-ws-negatives" rows="3" placeholder="現代摩天大樓&#10;女性法官&#10;粒子對撞機&#10;現代汽車與空調室外機" style="width: 100%; background: #080d16; border: 1px solid rgba(239, 68, 68, 0.4); color: #fca5a5; padding: 8px 10px; border-radius: 6px; font-size: 12px; resize: vertical;" oninput="syncWorldSettingToJson()">${escapeHtml(wsNegatives)}</textarea>
              </div>
            </div>
          </div>

          ${renderCharactersReviewHtml(data.characters || (resObj && resObj.key_characters) || [])}

          <div style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <label style="font-weight: 600; color: #cbd5e1;">Topic Research Notes & Knowledge Base (JSON / Markdown):</label>
              <button class="btn-sec" style="font-size: 11px; padding: 2px 8px;" onclick="syncWorldSettingFromJson()">🔄 Reload Form from JSON</button>
            </div>
            <textarea id="studio-research" style="width: 100%; height: 320px; font-family: monospace; font-size: 13px; background: #080d16; color: #e2e8f0; border: 1px solid var(--card-border); padding: 12px; border-radius: 6px; line-height: 1.5;">${escapeHtml(resText)}</textarea>
          </div>
          <div style="font-size: 12px; color: var(--text-muted);">
            💡 <b>Tip:</b> Refine the World Setting card above or the research JSON. When you click <b>Save Changes</b>, both the world view constraints and knowledge base will guide Stage 2 Script, Stage 3 Storyboard, and Stage 4 Image Prompts.
          </div>
        `;
      } else if (stKey === 'script') {
        const scriptMd = data.script_md || '';
        const activeProj = currentProject || studioProject;
        const authorConcl = (data.settings && data.settings.author_conclusion) || (activeProj && activeProj.data && activeProj.data.settings && activeProj.data.settings.author_conclusion) || '';
        bodyHtml += `
          <!-- Author's Take / What's My Take in Stage Studio -->
          <div style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(20, 25, 40, 0.7) 100%); border: 1.5px solid rgba(245, 158, 11, 0.45); border-radius: 8px; padding: 12px 14px; margin-bottom: 16px; box-shadow: 0 4px 12px rgba(245, 158, 11, 0.1);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 8px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="background: #f59e0b; color: #1c1511; font-size: 11px; font-weight: 900; padding: 2px 7px; border-radius: 4px;">WHAT'S MY TAKE</span>
                <span style="font-size: 13.5px; font-weight: 700; color: #fde68a;">💡 作者獨家觀點與結語 (What's My Take)</span>
              </div>
              <button type="button" class="btn" onclick="saveStudioAuthorConclusion()" style="background: #f59e0b; color: #1c1511; font-weight: 800; font-size: 12px; padding: 5px 12px; border: none; border-radius: 4px; cursor: pointer;">
                💾 儲存作者觀點
              </button>
            </div>
            <textarea id="studio-author-conclusion" rows="2" placeholder="在此輸入您對本專題的獨家觀點、批判性思考或哲學總結（例如：這場審判並非正義的終點，而是地緣政治妥協的開端……）。點擊右上方按鈕儲存！" style="width: 100%; box-sizing: border-box; font-size: 13px; line-height: 1.5; background: #04070e; border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 4px; padding: 8px 12px; color: #fff;">${escapeHtml(authorConcl)}</textarea>
          </div>

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
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px;">
            <div style="font-size: 13px; color: var(--text-muted); display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <span>Total Storyboard Scenes: <b style="color: #93c5fd;">${scenes.length}</b></span>
              <span style="font-size: 11px; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); padding: 2px 8px; border-radius: 10px; font-weight: 600;">🎬 Stage 3 Actual Script</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
              <button class="btn-sec" style="font-size: 12px; padding: 6px 14px; background: linear-gradient(135deg, rgba(56, 189, 248, 0.2) 0%, rgba(37, 99, 235, 0.25) 100%); border-color: #38bdf8; color: #bae6fd; font-weight: 700; display: inline-flex; align-items: center; gap: 6px;" onclick="openStage3ExportModal()" title="匯出 Stage 3 分鏡審閱腳本（支援 .txt 校對文稿、.csv 試算表、.md 結構文檔與純對白朗讀稿）">
                📤 匯出分鏡腳本 (Export Script) ▼
              </button>
              <button class="btn-sec" style="font-size: 12px; padding: 6px 12px; display: inline-flex; align-items: center; gap: 5px;" onclick="copyStage3ScriptToClipboard()" title="一鍵複製全部分鏡之旁白台詞至剪貼簿">
                📋 複製台詞
              </button>
              <button class="btn-sec" style="font-size: 12px; padding: 6px 12px;" onclick="saveStudioStage('scenes')">💾 Save Scenes</button>
            </div>
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
          <div id="studio-images-gallery-container" class="custom-horizontal-scroll" style="${imagesGalleryLayout === 'strip' ? 'display: flex; gap: 16px; overflow-x: auto; padding-bottom: 14px;' : 'display: grid; grid-template-columns: repeat(auto-fit, minmax(460px, 1fr)); gap: 16px; overflow-x: auto; padding-bottom: 10px;'}">
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
            <div id="studio-scene-card-${s.scene_id}" style="background: #080d16; border: 1px solid var(--card-border); border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 10px; min-width: 0; ${imagesGalleryLayout === 'strip' ? 'flex: 0 0 540px;' : ''} transition: border-color 0.3s ease;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 700; color: #93c5fd; font-size: 14px;">Scene #${s.scene_id}</span>
                <span id="studio-scene-badge-${s.scene_id}" style="font-size: 12px; color: ${imgUrl?'#34d399':'#f59e0b'}; font-weight: 600;">${imgUrl ? '✓ Generated' : '⏳ Pending'}</span>
              </div>

              ${isDrama ? `
                <div style="font-size: 11px; padding: 4px 8px; background: rgba(245, 158, 11, 0.15); border: 1px solid #d97706; border-radius: 4px; color: #fbbf24; font-weight: 600; display: flex; align-items: center; justify-content: space-between;">
                  <span>👤 角色: <b>${s.character || s.speaker || '主演'}</b></span>
                  <span style="font-size: 9px; background: #b45309; color: #fff; padding: 1px 5px; border-radius: 3px; font-weight: 700;">9:16 直式立繪</span>
                </div>
              ` : `
                <!-- Real-world Quick Stock Status Pill -->
                ${s.is_stock_active ? `
                  <div style="font-size: 11px; padding: 4px 8px; background: rgba(5, 150, 105, 0.25); border: 1px solid #059669; border-radius: 4px; color: #6ee7b7; font-weight: 600; display: flex; align-items: center; justify-content: space-between; gap: 4px;">
                    <span style="display: flex; align-items: center; gap: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                      <span>📸 已套用線上圖庫:</span> <b style="color: #fff;">${s.active_stock_source || (s.image && s.image.meta && s.image.meta.source) || 'Stock'}</b>
                      ${(s.active_stock_title || (s.image && s.image.meta && s.image.meta.title)) ? `<span style="opacity: 0.8; font-weight: normal; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 140px;">(${s.active_stock_title || s.image.meta.title})</span>` : ''}
                    </span>
                    <span style="font-size: 9px; background: #065f46; color: #a7f3d0; padding: 1px 4px; border-radius: 3px; font-weight: 700;">ACTIVE</span>
                  </div>
                ` : (s.quick_stock_available ? `
                  <div style="font-size: 11px; padding: 4px 8px; background: rgba(59, 130, 246, 0.2); border: 1px solid #3b82f6; border-radius: 4px; color: #93c5fd; font-weight: 600; display: flex; align-items: center; justify-content: space-between; gap: 6px;">
                    <span title="命中素材目標: ${s.quick_stock_target}" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                      🌐 <b>可使用 Quick Stock:</b> ${s.quick_stock_target}
                    </span>
                    <span style="font-size: 9px; background: #1e3a8a; color: #bfdbfe; padding: 1px 4px; border-radius: 3px; white-space: nowrap; font-weight: 700;">
                      ${s.quick_stock_source === 'youtube_snippet' ? 'YouTube 實體片段' : '維基共享資源'}
                    </span>
                  </div>
                ` : `
                  <div style="font-size: 11px; padding: 3px 6px; background: rgba(148, 163, 184, 0.08); border: 1px solid #334155; border-radius: 4px; color: #94a3b8; display: flex; align-items: center; gap: 4px;">
                    🎨 <span>AI 生成畫面 (無特定真實實體標籤)</span>
                  </div>
                `)}
              ` }

              <!-- Side-by-Side: Image and Scene Script Line -->
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; align-items: stretch;">

                <!-- Left: Scene Image Preview & Takes Switcher -->
                <div style="display: flex; flex-direction: column; gap: 6px;">
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 11px; font-weight: 700; color: #cbd5e1; display: flex; align-items: center; gap: 4px;">
                      <span>🖼️</span> <span>視覺畫面 (Visual Image)</span>
                    </span>
                    ${totalTakes > 1 ? `<span id="studio-scene-active-take-badge-${s.scene_id}" style="background: rgba(5,150,105,0.25); border: 1px solid #059669; color: #34d399; font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px;">Take #${activeTake || 1} / ${totalTakes}</span>` : ''}
                  </div>
                  <div style="width: 100%; height: 165px; background: #000; border-radius: 6px; overflow: hidden; display: flex; align-items: center; justify-content: center; position: relative; border: 1px solid #1e293b;">
                    ${imgUrl ? `
                      <img id="studio-scene-img-${s.scene_id}" src="${imgUrlBusted}" style="width: 100%; height: 100%; object-fit: cover; cursor: pointer;" onclick="window.open('${imgUrl}')" title="Click to view full image in new tab">
                      <div style="position: absolute; bottom: 4px; left: 4px; background: rgba(0,0,0,0.7); font-size: 10px; color: #cbd5e1; padding: 2px 5px; border-radius: 3px; pointer-events: none;">🔍 Click to Zoom</div>
                      <button onclick="event.stopPropagation(); deleteSceneActiveImage(${s.scene_id})" style="position: absolute; top: 4px; right: 4px; background: rgba(0,0,0,0.75); border: 1px solid #ef4444; color: #fca5a5; border-radius: 3px; padding: 2px 6px; font-size: 11px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 3px; z-index: 2;" title="Delete current image">
                        🗑️ Delete
                      </button>
                    ` : `<span id="studio-no-img-${s.scene_id}" style="font-size: 12px; color: gray;">No Image Generated</span>`}
                  </div>

                  <!-- Quick Takes Navigator Row under image -->
                  <div style="display: flex; justify-content: space-between; align-items: center; background: #04070e; border: 1px solid #1e293b; border-radius: 5px; padding: 4px 8px;">
                    <div style="display: flex; align-items: center; gap: 4px;">
                      <span id="studio-takes-header-count-${s.scene_id}" style="font-weight: 700; color: #93c5fd; font-size: 11px;">🎞️ Takes (${totalTakes}):</span>
                    </div>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <button id="studio-take-prev-btn-${s.scene_id}" class="btn-sec" style="padding: 1px 6px; font-size: 11px;" onclick="cycleSceneImageTake(${s.scene_id}, -1)" ${hasPrevTake ? '' : 'disabled'} title="Previous Take">◀</button>
                      <button id="studio-take-next-btn-${s.scene_id}" class="btn-sec" style="padding: 1px 6px; font-size: 11px;" onclick="cycleSceneImageTake(${s.scene_id}, 1)" ${hasNextTake ? '' : 'disabled'} title="Next Take">▶</button>
                      <button class="btn-sec" style="padding: 1px 6px; font-size: 10px; background: #1e3a8a; border-color: #3b82f6; color: #fff; font-weight: 600;" onclick="openTakesGalleryModal(${s.scene_id})">Compare</button>
                    </div>
                  </div>
                </div>

                <!-- Right: Script / Narration Box for match check & adjustment -->
                <div style="display: flex; flex-direction: column; gap: 6px; background: rgba(14, 20, 34, 0.75); border: 1px solid rgba(124, 145, 182, 0.25); border-left: 3px solid #C19D49; border-radius: 6px; padding: 8px 10px;">
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 11px; font-weight: 700; color: #C19D49; display: flex; align-items: center; gap: 4px;">
                      <span>🎙️</span> <span>分鏡旁白台詞 (Script Line)</span>
                    </span>
                    <span id="studio-script-len-${s.scene_id}" style="font-size: 10px; color: #7C91B6; font-family: monospace;">${(s.narration || '').length} 字</span>
                  </div>
                  <div style="font-size: 11px; color: #94a3b8; line-height: 1.35;">
                    核對此段台詞是否與左側畫面相符；可直接在此調整台詞或於下方微調提示詞：
                  </div>
                  <div style="flex: 1; display: flex; flex-direction: column;">
                    <textarea id="studio-scene-script-${s.scene_id}" rows="4" style="width: 100%; flex: 1; min-height: 90px; font-size: 12px; line-height: 1.45; padding: 6px 8px; background: #04070e; border: 1px solid #1e293b; color: #f1f5f9; border-radius: 4px; resize: vertical;" oninput="onStudioScriptInput(${s.scene_id}, this.value)" onblur="saveSingleSceneScript(${s.scene_id}, true)" placeholder="輸入此鏡頭的旁白台詞 (Narration script)...">${escapeHtml(s.narration || '')}</textarea>
                  </div>
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 2px;">
                    <span id="studio-script-toast-${s.scene_id}" style="font-size: 11px; color: #34d399; font-weight: 600; display: none;">✓ 台詞已儲存</span>
                    <button class="btn-sec" id="studio-btn-save-script-${s.scene_id}" style="padding: 2px 8px; font-size: 11px; background: #233b6d; border-color: #3b82f6; color: #93c5fd; font-weight: 600; margin-left: auto;" onclick="saveSingleSceneScript(${s.scene_id}, false)" title="儲存修改後的旁白台詞">
                      💾 儲存台詞
                    </button>
                  </div>
                </div>

              </div>

              <!-- Takes Management Strip (if multiple takes exist) -->
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
          apiJson('http://127.0.0.1:8008/health').then(h => {
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
      } else if (stKey === 'music') {
        const plan = data.music_plan || [];
        const mSettings = data.music_settings || {};
        const availTracks = data.available_tracks || [];
        const totalDur = data.total_duration || 0;
        const topic = data.topic || '';

        const movementNames = [
          { title: "Movement 1: 引言與氛圍鋪墊 (Opening Context & Atmosphere)", badge: "bg-blue", defaultEnergy: "LOW / MID", desc: "引導觀眾進入紀錄片核心主題，營造沉浸式宏觀背景氣氛。" },
          { title: "Movement 2: 深入探討與張力起伏 (Deep Dive & Rising Stakes)", badge: "bg-purple", defaultEnergy: "MID / HIGH", desc: "隨劇情深入探討核心衝突、技術困境或調查轉折，節奏張力遞增。" },
          { title: "Movement 3: 終章昇華與未來啟示 (Outlook & Climax Resolution)", badge: "bg-emerald", defaultEnergy: "HIGH / UPLIFTING", desc: "收尾結語、總結思考與願景展望，激昂或沉穩昇華觀眾情緒。" }
        ];
        const currentVibe = data.current_vibe || (mSettings && mSettings.vibe) || 'auto';

        bodyHtml += `
          <!-- Ambient Music Overview Card -->
          <div style="background: linear-gradient(135deg, rgba(14, 27, 49, 0.95) 0%, rgba(10, 15, 30, 0.95) 100%); border: 1px solid rgba(59, 130, 246, 0.35); border-radius: 10px; padding: 18px 20px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 12px;">
              <div>
                <div style="font-size: 16px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px;">
                  <span>🎶</span> 紀錄片多樂章敘事配樂工坊 (Narrative Progression Studio)
                </div>
                <div style="font-size: 12.5px; color: #94a3b8; margin-top: 5px;">
                  主題識別：<b style="color: #60a5fa;">${topic || '紀錄片主題'}</b> | 總長度：<b style="color: #cbd5e1;">${totalDur > 0 ? totalDur.toFixed(1) + 's' : '自動估算中'}</b> | 演進模式：<span class="badge badge-blue">🌟 3-Movement Progression</span>
                </div>
              </div>
              <div style="display: flex; gap: 8px;">
                <button class="btn-sec" onclick="reMatchStudioMusicVibe()" style="font-size: 12px; padding: 6px 14px; background: rgba(59,130,246,0.15); border: 1px solid #3b82f6; color: #93c5fd; font-weight: 600;">🎲 依風格重新匹配 (Re-Match)</button>
                <button class="btn-primary" onclick="saveStudioStage('music')" style="font-size: 12px; padding: 6px 14px; background: #059669; font-weight: 700;">💾 儲存配樂計畫 (Save Music Plan)</button>
              </div>
            </div>

            <!-- Vibe & Genre Override Row -->
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding-top: 10px; border-top: 1px solid rgba(59, 130, 246, 0.2);">
              <label style="font-size: 12.5px; font-weight: 700; color: #cbd5e1; margin: 0; display: flex; align-items: center; gap: 5px;">
                <span>🎭</span> 配樂氛圍風格 (Music Vibe):
              </label>
              <select id="studio-music-vibe-select" style="min-width: 250px; padding: 6px 12px; font-size: 12px; border-radius: var(--radius-sm); background: #040814; color: #60a5fa; border: 1px solid #3b82f6; font-weight: 600;" onchange="onStudioMusicVibeChange(this.value)">
                <option value="auto" ${(!currentVibe || currentVibe === 'auto') ? 'selected' : ''}>🤖 自動語意推論 (Auto Semantic Grounding)</option>
                <option value="tech_futuristic" ${currentVibe === 'tech_futuristic' ? 'selected' : ''}>🔬 科技未來 (Tech & Sci-Fi)</option>
                <option value="cinematic_documentary" ${currentVibe === 'cinematic_documentary' ? 'selected' : ''}>🏛️ 歷史紀錄 (Cinematic Documentary)</option>
                <option value="dramatic_tension" ${currentVibe === 'dramatic_tension' ? 'selected' : ''}>⚡ 衝突危機 (Dramatic Tension)</option>
                <option value="mystery_cosmic" ${currentVibe === 'mystery_cosmic' ? 'selected' : ''}>🌌 宇宙未解 (Dark Mystery & Space)</option>
                <option value="uplifting_inspirational" ${currentVibe === 'uplifting_inspirational' ? 'selected' : ''}>✨ 勵志突破 (Uplifting & Wonder)</option>
                <option value="calm_focus" ${currentVibe === 'calm_focus' ? 'selected' : ''}>🧘 平靜沉思 (Calm & Focus)</option>
              </select>
              <span style="font-size: 11px; color: #94a3b8;">切換後點擊「🎲 依風格重新匹配」將自動以該情感基調重算三樂章</span>
            </div>
          </div>
        `;

        if (!plan.length) {
          bodyHtml += `
            <div style="text-align: center; padding: 60px 20px; background: #080d16; border: 1px dashed rgba(124, 145, 182, 0.3); border-radius: 8px;">
              <div style="font-size: 32px; margin-bottom: 12px;">🎶</div>
              <h4 style="color: #fff; margin: 0 0 8px 0;">尚無已生成的配樂時間軸計畫</h4>
              <p style="font-size: 13px; color: var(--text-muted); max-width: 460px; margin: 0 auto 16px auto;">
                系統將根據前置 Stage 6 旁白精確時長與章節斷點，自動為引言、探討、結尾精準匹配三段敘事演進配樂並計算平滑交叉淡入淡出（Crossfade）。
              </p>
              <button class="btn-primary" onclick="runStudioStageOnly('music')" style="padding: 8px 18px; font-weight: 700;">▶ 立即規劃環境配樂 (Plan Ambient Music)</button>
            </div>
          `;
        } else {
          bodyHtml += `<div style="display: flex; flex-direction: column; gap: 16px;">`;
          plan.forEach((seg, idx) => {
            const mvMeta = movementNames[idx] || { title: `Movement ${idx + 1}`, desc: "動態樂章時序", badge: "bg-blue" };
            const dur = (seg.end_time - seg.start_time).toFixed(1);

            let trackOptionsHtml = '';
            availTracks.forEach(tr => {
              const isSelected = (tr.name === seg.name || tr.path.endsWith(seg.name));
              trackOptionsHtml += `<option value="${tr.path}" data-url="${tr.url}" data-cat="${tr.category}" ${isSelected ? 'selected' : ''}>[${tr.category}] ${tr.name}</option>`;
            });

            bodyHtml += `
              <div id="studio-music-card-${idx}" style="background: #080d16; border: 1px solid rgba(124, 145, 182, 0.2); border-radius: 8px; padding: 16px; transition: border-color 0.2s;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; margin-bottom: 10px;">
                  <div>
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                      <span style="font-size: 14px; font-weight: 700; color: #fff;">${mvMeta.title}</span>
                      <span style="font-size: 11px; background: rgba(59,130,246,0.15); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3); border-radius: 4px; padding: 2px 6px;">${seg.category || 'auto'}</span>
                      <span style="font-size: 11px; background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); border-radius: 4px; padding: 2px 6px;">⚡ 能量階梯: ${mvMeta.defaultEnergy}</span>
                    </div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 3px;">
                      時間範圍：<b style="color: #93c5fd;">${seg.start_time.toFixed(1)}s ➔ ${seg.end_time.toFixed(1)}s</b> (${dur}s) | 淡入: ${seg.crossfade_in || 2}s | 淡出: ${seg.crossfade_out || 2}s
                    </div>
                  </div>
                  <div style="font-size: 12px; color: #a7f3d0; background: rgba(5,150,105,0.15); border: 1px solid #059669; border-radius: 4px; padding: 3px 8px;">
                    🔊 音量: <b>${seg.volume_db || -16} dB</b>
                  </div>
                </div>

                <!-- Audio Preview Player -->
                <div style="background: #04070e; border: 1px solid #1e293b; border-radius: 6px; padding: 10px 12px; margin-bottom: 12px;">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 12px; font-weight: 600; color: #cbd5e1;">🎧 即時試聽音軌：<b style="color: #60a5fa;">${seg.name}</b></span>
                  </div>
                  <audio id="studio-music-audio-${idx}" controls src="${seg.audio_url || ''}" style="width: 100%; height: 32px;"></audio>
                </div>

                <!-- Track Selector & Controls -->
                <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                  <label style="font-size: 12px; font-weight: 600; color: #94a3b8; margin: 0;">更換此樂章曲目：</label>
                  <select id="studio-music-select-${idx}" style="flex: 1; min-width: 260px; padding: 6px 10px; font-size: 12px; border-radius: var(--radius-sm); background: var(--bg-canvas); color: var(--text-primary); border: 1px solid var(--border-muted);" onchange="onStudioMusicSegmentTrackChange(${idx}, this)">
                    ${trackOptionsHtml}
                  </select>
                  <button type="button" class="btn-sec" onclick="openStudioClassicalPicker(${idx})" style="padding: 6px 12px; font-size: 12px; font-weight: 700; color: #f59e0b; border-color: #f59e0b; background: rgba(245,158,11,0.1); cursor: pointer;" title="從 OpenOpus 古典名曲曲庫中挑選並指定至此樂章">
                    🏛️ 選用古典名曲
                  </button>
                </div>
                <!-- Start Offset Scrubber -->
                <div style="display: flex; align-items: center; gap: 8px; margin-top: 8px; flex-wrap: wrap; background: #050a14; padding: 6px 10px; border-radius: 6px; border: 1px solid rgba(59,130,246,0.2);">
                  <label style="font-size: 12px; font-weight: 600; color: #93c5fd; margin: 0;">⏱️ 起播偏移 (Start Offset):</label>
                  <input type="number" id="studio-music-offset-${idx}" min="0" step="1" value="${seg.start_offset || 0}" style="width: 80px; padding: 4px 8px; font-size: 12px; border-radius: 4px; background: #040814; color: #60a5fa; border: 1px solid #3b82f6; font-weight: 700;" onchange="onStudioMusicOffsetChange(${idx}, this.value)" placeholder="0">
                  <span style="font-size: 11px; color: #64748b;">秒 (跳過引言靜音或切換至名曲核心高潮片段，渲染時自動對齊交叉淡入淡出)</span>
                </div>
              </div>
            `;
          });
          bodyHtml += `</div>`;
        }
      } else if (stKey === 'animation') {
        const scenes = data.scenes || [];
        if (isDrama) {
          bodyHtml += `
            <!-- Hedra AI Actor Lip-Sync Studio Card -->
            <div style="background: linear-gradient(135deg, rgba(20, 18, 15, 0.96) 0%, rgba(10, 10, 14, 0.98) 100%); border: 1.5px solid #f59e0b; border-radius: 10px; padding: 18px 20px; margin-bottom: 22px; box-shadow: 0 0 25px rgba(245, 158, 11, 0.18);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <span style="font-size: 26px;">👄</span>
                  <div>
                    <h3 style="margin: 0; font-size: 15px; font-weight: 800; color: #fbbf24; letter-spacing: 0.5px;">Hedra AI 角色精確對嘴與面部微表情工作室</h3>
                    <div style="font-size: 12px; color: #cbd5e1; margin-top: 2px;">
                      調用 Hedra Character-2 引擎，精準同步角色唇形、自然呼吸與面部情緒微動態（9:16 直式，嚴格禁用 Remotion 與靜態過場）。
                    </div>
                  </div>
                </div>
                <span style="font-size: 11px; background: rgba(245, 158, 11, 0.15); border: 1px solid #f59e0b; color: #fbbf24; font-weight: 700; padding: 3px 8px; border-radius: 12px;">Hedra Character-2 · 9:16</span>
              </div>
              <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap; padding: 10px 12px; background: rgba(245, 158, 11, 0.08); border: 1px dashed rgba(245, 158, 11, 0.35); border-radius: 8px;">
                <button class="btn-primary" style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: #000; border: none; font-weight: 800; padding: 8px 18px; font-size: 12.5px; box-shadow: 0 2px 8px rgba(245, 158, 11, 0.4);" onclick="runStudioStageOnly('animation')">
                  ✨ 批次執行全短劇角色對嘴合成 (Batch Lip-Sync)
                </button>
                <div style="font-size: 12px; color: #94a3b8;">
                  已配置專屬音色與定妝立繪之幕次將自動對齊嘴型；未設定 Hedra Key 時將由本地語音共振引擎執行。
                </div>
              </div>
            </div>

            <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 14px;">各幕角色演出與對嘴預覽：</div>
            <div style="display: flex; flex-direction: column; gap: 12px;">
          `;
          scenes.forEach((s, idx) => {
            const hasVideo = s.animation && s.animation.path;
            const vSrc = hasVideo ? `/media/${currentProjectId}/${s.animation.path}?t=${Date.now()}` : '';
            const charName = s.character_name || (s.drama_character && s.drama_character.name) || '演員';
            const voiceProf = s.voice_profile || '預設音色';
            bodyHtml += `
              <div style="background: #080d16; border: 1px solid var(--card-border); border-radius: 8px; padding: 14px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div style="flex: 1; min-width: 260px;">
                  <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                    <span style="font-weight: 700; color: #93c5fd;">Scene #${s.scene_id}</span>
                    <span style="background: rgba(245, 158, 11, 0.18); border: 1px solid #f59e0b; color: #fbbf24; font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px;">🎭 ${escapeHtml(charName)}</span>
                    <span style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #6ee7b7; font-size: 11px; padding: 2px 6px; border-radius: 4px;">🎙️ ${escapeHtml(voiceProf)}</span>
                  </div>
                  <div style="font-size: 12px; color: #e2e8f0; line-height: 1.4; margin-top: 4px;">
                    <b>對白:</b> ${escapeHtml(s.narration || '（無台詞）')}
                  </div>
                  <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
                    時長: <b>${s.estimated_duration || 5}s</b> | 景別: <b>${s.framing || '中景'}</b> | 模型: <b>${(s.animation && s.animation.meta && s.animation.meta.provider) || 'Hedra Character-2'}</b>
                  </div>
                </div>
                <div>
                  ${vSrc ? `
                    <div style="border-radius: 6px; overflow: hidden; border: 1px solid #334155; background: #000; width: 140px; height: 180px;">
                      <video controls src="${vSrc}" style="width: 100%; height: 100%; object-fit: cover; display: block;"></video>
                    </div>
                  ` : `
                    <div style="width: 140px; height: 180px; background: #04070e; border: 1px dashed #334155; border-radius: 6px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #f59e0b; font-size: 11px; text-align: center; padding: 8px;">
                      <span style="font-size: 24px; margin-bottom: 4px;">👄</span>
                      <span>待合成對嘴</span>
                    </div>
                  `}
                </div>
              </div>
            `;
          });
          bodyHtml += `</div>`;
        } else {
          setTimeout(() => {
            const sel = document.getElementById('remotion-target-scene');
            if (sel && sel.value) prefillRemotionFromScene(sel.value);
          }, 80);
          const studioRem = (studioStageData && studioStageData.remotion) || data.remotion || (studioProject && studioProject.settings && studioProject.settings.remotion) || {
            style: 'modern_tech_explainer',
            theme: 'dark_obsidian',
            density: 'full',
            accentColor: '#A855F7',
            default_style: 'EvidenceHighlightScene'
          };
          if (!studioStageData.remotion) studioStageData.remotion = Object.assign({}, studioRem);
          if (!studioStageData.animation_model) {
            studioStageData.animation_model = data.animation_model || (studioProject && studioProject.settings && studioProject.settings.stage_models && studioProject.settings.stage_models.animation) || 'remotion';
          }
          const activeStudioStyle = studioStageData.remotion.style || 'modern_tech_explainer';
          const activeStudioTheme = studioStageData.remotion.theme || 'dark_obsidian';
          const activeStudioDensity = studioStageData.remotion.density || 'full';
          const activeStudioAccent = studioStageData.remotion.accentColor || '#A855F7';
          const activeStudioModel = studioStageData.animation_model || 'remotion';

          bodyHtml += `
            <!-- Remotion Motion Graphics Studio Card -->
            <div style="background: linear-gradient(135deg, #0b1526 0%, #070e1b 100%); border: 1.5px solid #00F5FF; border-radius: 10px; padding: 18px 20px; margin-bottom: 22px; box-shadow: 0 0 25px rgba(0, 245, 255, 0.15);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <span style="font-size: 24px;">⚛️</span>
                  <div>
                    <h3 style="margin: 0; font-size: 15px; font-weight: 800; color: #fff; letter-spacing: 0.5px;">Remotion 視覺風格與動態圖解體系 (Visual Style Suite)</h3>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">直接切換 Remotion 視覺體系、主題畫布與強調色，全片 Stage 8 動畫算繪立即套用。</div>
                  </div>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <span id="studio-remotion-active-badge" style="font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px; background: ${activeStudioAccent}22; color: ${activeStudioAccent}; border: 1px solid ${activeStudioAccent};">
                    ${activeStudioStyle} · ${activeStudioAccent}
                  </span>
                  <span style="font-size: 11px; background: rgba(0, 245, 255, 0.15); border: 1px solid #00F5FF; color: #00F5FF; font-weight: 700; padding: 3px 8px; border-radius: 12px;">1080p · 60fps</span>
                </div>
              </div>

              <!-- 7 Style Showcase Cards from Settings -->
              <div style="margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                  <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin: 0;">視覺風格體系 (Remotion Style) - 點擊卡片即時切換：</label>
                  <span style="font-size: 11px; color: #64748b;">7 款大師級專業動態視覺體系</span>
                </div>
                <div id="studio-remotion-showcase-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px;">
                  
                  <!-- Style 1: Modern Tech Explainer -->
                  <div onclick="selectStudioRemotionPreset('modern_tech_explainer')" id="studio-card-modern_tech_explainer" style="border: ${activeStudioStyle==='modern_tech_explainer' ? '2px solid #a855f7' : '1px solid #1e293b'}; background: #08090c; border-radius: 8px; padding: 8px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStudioStyle==='modern_tech_explainer' ? '0 0 12px rgba(168,85,247,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                      <span style="font-size: 11.5px; font-weight: 800; color: #f8fafc;">✨ Modern Tech Explainer</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: rgba(168,85,247,0.25); color: #c4b5fd; font-weight: 700;">Gary Chen</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 5px;">
                      <img src="/remotion/style_frameworkmatrix.png" alt="Framework Matrix" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_promptcomparison.png" alt="Prompt Comparison" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_chatsimulation.png" alt="Chat Simulation" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                    </div>
                    <div style="font-size: 10px; color: #94a3b8; line-height: 1.3; margin-bottom: 4px;">純黑曜石 · 四象限矩陣 · 提示詞對比</div>
                    <div style="display: flex; gap: 4px;">
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #1e1b4b; color: #c4b5fd; border: 1px solid #a855f7;">#A855F7 紫</span>
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #0f172a; color: #94a3b8;">黑曜石純黑</span>
                    </div>
                  </div>

                  <!-- Style 2: Coordinate Zero -->
                  <div onclick="selectStudioRemotionPreset('coordinate_zero')" id="studio-card-coordinate_zero" style="border: ${activeStudioStyle==='coordinate_zero' ? '2px solid #0d9488' : '1px solid #1e293b'}; background: #0a1b14; border-radius: 8px; padding: 8px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStudioStyle==='coordinate_zero' ? '0 0 12px rgba(13,148,136,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                      <span style="font-size: 11.5px; font-weight: 800; color: #f8fafc;">🧭 Coordinate Zero</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: rgba(13,148,136,0.25); color: #5eead4; font-weight: 700;">座標零</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 5px;">
                      <img src="/remotion/style_coordinate_scale.png" alt="Scale" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_coordinate_experiment.png" alt="Experiment" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_coordinate_split.png" alt="Split" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                    </div>
                    <div style="font-size: 10px; color: #94a3b8; line-height: 1.3; margin-bottom: 4px;">墨綠雕刻墊 · 等緯尺度縮放 · 各對一半</div>
                    <div style="display: flex; gap: 4px;">
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #134e4a; color: #5eead4; border: 1px solid #0d9488;">#0D9488 湖綠</span>
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #064e3b; color: #a7f3d0;">墨綠雕刻墊</span>
                    </div>
                  </div>

                  <!-- Style 3: Tactile Blueprint -->
                  <div onclick="selectStudioRemotionPreset('tactile_blueprint')" id="studio-card-tactile_blueprint" style="border: ${activeStudioStyle==='tactile_blueprint' ? '2px solid #00F5FF' : '1px solid #1e293b'}; background: #070e1b; border-radius: 8px; padding: 8px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStudioStyle==='tactile_blueprint' ? '0 0 12px rgba(0,245,255,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                      <span style="font-size: 11.5px; font-weight: 800; color: #f8fafc;">⚛️ Tactile Blueprint</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: rgba(0,245,255,0.2); color: #00F5FF; font-weight: 700;">科技藍圖</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 5px;">
                      <img src="/remotion/style_branchpathway.png" alt="Branch" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_leadercallout.png" alt="Callout" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_scalecompare.png" alt="Scale" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                    </div>
                    <div style="font-size: 10px; color: #94a3b8; line-height: 1.3; margin-bottom: 4px;">深藍工程網格 · 分支決策 · HUD引線</div>
                    <div style="display: flex; gap: 4px;">
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #082f49; color: #00F5FF; border: 1px solid #0284c7;">#00F5FF 青</span>
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #0369a1; color: #e0f2fe;">工程網格</span>
                    </div>
                  </div>

                  <!-- Style 4: fOx Hsiao Documentary -->
                  <div onclick="selectStudioRemotionPreset('fox_documentary')" id="studio-card-fox_documentary" style="border: ${activeStudioStyle==='fox_documentary' ? '2px solid #38bdf8' : '1px solid #1e293b'}; background: #0f172a; border-radius: 8px; padding: 8px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStudioStyle==='fox_documentary' ? '0 0 12px rgba(56,189,248,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                      <span style="font-size: 11.5px; font-weight: 800; color: #f8fafc;">📌 fOx Documentary</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: rgba(56,189,248,0.2); color: #38bdf8; font-weight: 700;">調查紀錄片</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 5px;">
                      <img src="/remotion/style_foxheader.png" alt="Fox Header" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_foxmetric.png" alt="Fox Metric" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_foxtimeline.png" alt="Fox Timeline" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                    </div>
                    <div style="font-size: 10px; color: #94a3b8; line-height: 1.3; margin-bottom: 4px;">毛玻璃遮罩 · 巨型指標 · 歷程滑軌</div>
                    <div style="display: flex; gap: 4px;">
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #075985; color: #38bdf8; border: 1px solid #0284c7;">#38BDF8 天藍</span>
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #1e293b; color: #94a3b8;">毛玻璃</span>
                    </div>
                  </div>

                  <!-- Style 5: Finance & Market Explainer -->
                  <div onclick="selectStudioRemotionPreset('finance_market')" id="studio-card-finance_market" style="border: ${activeStudioStyle==='finance_market' ? '2px solid #10b981' : '1px solid #1e293b'}; background: #091319; border-radius: 8px; padding: 8px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStudioStyle==='finance_market' ? '0 0 12px rgba(16,185,129,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                      <span style="font-size: 11.5px; font-weight: 800; color: #f8fafc;">📈 Finance & Market</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: rgba(16,185,129,0.25); color: #34d399; font-weight: 700;">財經趨勢</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 5px;">
                      <img src="/remotion/style_finance_candlestick.png" alt="Candlestick" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_finance_metrics.png" alt="Metrics" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_foxmetric.png" alt="Metric" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                    </div>
                    <div style="font-size: 10px; color: #94a3b8; line-height: 1.3; margin-bottom: 4px;">走勢K線 · 支撐壓力位 · 財務利差</div>
                    <div style="display: flex; gap: 4px;">
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #064e3b; color: #34d399; border: 1px solid #10b981;">#10B981 漲綠</span>
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #0f172a; color: #38bdf8;">金融盤勢</span>
                    </div>
                  </div>

                  <!-- Style 6: Archival History -->
                  <div onclick="selectStudioRemotionPreset('archival_history')" id="studio-card-archival_history" style="border: ${activeStudioStyle==='archival_history' ? '2px solid #c2410c' : '1px solid #1e293b'}; background: #1c1511; border-radius: 8px; padding: 8px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStudioStyle==='archival_history' ? '0 0 12px rgba(194,65,12,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                      <span style="font-size: 11.5px; font-weight: 800; color: #f8fafc;">📜 Archival History</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: rgba(194,65,12,0.25); color: #fb923c; font-weight: 700;">歷史編年</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 5px;">
                      <img src="/remotion/style_archival_document.png" alt="Doc" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_history_chronology.png" alt="Chrono" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_evidencehighlight.png" alt="Evidence" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                    </div>
                    <div style="font-size: 10px; color: #94a3b8; line-height: 1.3; margin-bottom: 4px;">羊皮紙質 · 機密檔案 · 印戳戳記</div>
                    <div style="display: flex; gap: 4px;">
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #431407; color: #fb923c; border: 1px solid #c2410c;">#C2410C 印戳</span>
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #292524; color: #d6d3d1;">羊皮紙</span>
                    </div>
                  </div>

                  <!-- Style 7: Vox Journalism -->
                  <div onclick="selectStudioRemotionPreset('vox_journalism')" id="studio-card-vox_journalism" style="border: ${activeStudioStyle==='vox_journalism' ? '2px solid #facc15' : '1px solid #1e293b'}; background: #16150a; border-radius: 8px; padding: 8px; cursor: pointer; transition: all 0.2s; box-shadow: ${activeStudioStyle==='vox_journalism' ? '0 0 12px rgba(250,204,21,0.35)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                      <span style="font-size: 11.5px; font-weight: 800; color: #f8fafc;">🗞️ Vox Journalism</span>
                      <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: rgba(250,204,21,0.25); color: #fde047; font-weight: 700;">Vox 調查</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 5px;">
                      <img src="/remotion/style_vox_splitscreen.png" alt="Split" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_vox_keystat.png" alt="Stat" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                      <img src="/remotion/style_foxheader.png" alt="Header" style="width: 100%; height: 38px; object-fit: cover; border-radius: 3px;">
                    </div>
                    <div style="font-size: 10px; color: #94a3b8; line-height: 1.3; margin-bottom: 4px;">黃黑高對比 · 政策雙分割 · 震撼數據</div>
                    <div style="display: flex; gap: 4px;">
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #36300a; color: #fde047; border: 1px solid #facc15;">#FACC15 亮黃</span>
                      <span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: #0a0a0c; color: #cbd5e1;">高對比炭黑</span>
                    </div>
                  </div>

                </div>
              </div>

              <!-- Core Controls Form Grid -->
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; background: rgba(0,0,0,0.3); padding: 12px; border-radius: 6px; border: 1px solid #1e293b; margin-bottom: 14px;">
                <div>
                  <label style="display: block; font-size: 11px; font-weight: 700; color: #cbd5e1; margin-bottom: 4px;">風格體系 (remotion.style)</label>
                  <select id="studio-remotion-style" onchange="onStudioRemotionChange()" style="width: 100%; font-size: 11.5px; padding: 6px; background: #060b16; border: 1px solid #334155; color: #f8fafc; border-radius: 4px;">
                    <option value="modern_tech_explainer" ${activeStudioStyle==='modern_tech_explainer'?'selected':''}>Modern Tech Explainer (Gary Chen)</option>
                    <option value="coordinate_zero" ${activeStudioStyle==='coordinate_zero'?'selected':''}>Coordinate Zero (座標零 桌面實驗)</option>
                    <option value="tactile_blueprint" ${activeStudioStyle==='tactile_blueprint'?'selected':''}>Tactile Blueprint (硬核科技藍圖)</option>
                    <option value="fox_documentary" ${activeStudioStyle==='fox_documentary'?'selected':''}>fOx Hsiao Documentary (調查紀錄片)</option>
                    <option value="finance_market" ${activeStudioStyle==='finance_market'?'selected':''}>Finance & Market (財經趨勢與K線)</option>
                    <option value="archival_history" ${activeStudioStyle==='archival_history'?'selected':''}>Archival History (歷史編年檔案)</option>
                    <option value="vox_journalism" ${activeStudioStyle==='vox_journalism'?'selected':''}>Vox Journalism (Vox 深度調查)</option>
                  </select>
                </div>

                <div>
                  <label style="display: block; font-size: 11px; font-weight: 700; color: #cbd5e1; margin-bottom: 4px;">畫布主題 (remotion.theme)</label>
                  <select id="studio-remotion-theme" onchange="onStudioRemotionChange()" style="width: 100%; font-size: 11.5px; padding: 6px; background: #060b16; border: 1px solid #334155; color: #f8fafc; border-radius: 4px;">
                    <option value="dark_obsidian" ${activeStudioTheme==='dark_obsidian'?'selected':''}>Dark Obsidian (純黑曜石畫布)</option>
                    <option value="green_cutting_mat" ${activeStudioTheme==='green_cutting_mat'?'selected':''}>Green Cutting Mat (墨綠雕刻墊)</option>
                    <option value="blueprint_grid" ${activeStudioTheme==='blueprint_grid'?'selected':''}>Blueprint Grid (深藍工程網格)</option>
                    <option value="translucent_overlay" ${activeStudioTheme==='translucent_overlay'?'selected':''}>Translucent Overlay (毛玻璃遮罩)</option>
                    <option value="finance_grid" ${activeStudioTheme==='finance_grid'?'selected':''}>Finance Grid (深灰金融盤勢)</option>
                    <option value="parchment_paper" ${activeStudioTheme==='parchment_paper'?'selected':''}>Parchment Paper (古典羊皮紙)</option>
                    <option value="vox_charcoal" ${activeStudioTheme==='vox_charcoal'?'selected':''}>Vox Charcoal (高對比炭黑)</option>
                  </select>
                </div>

                <div>
                  <label style="display: block; font-size: 11px; font-weight: 700; color: #cbd5e1; margin-bottom: 4px;">覆蓋密度 (remotion.density)</label>
                  <select id="studio-remotion-density" onchange="onStudioRemotionChange()" style="width: 100%; font-size: 11.5px; padding: 6px; background: #060b16; border: 1px solid #334155; color: #f8fafc; border-radius: 4px;">
                    <option value="full" ${activeStudioDensity==='full'?'selected':''}>full (100% 全程 Remotion 動態圖表)</option>
                    <option value="half" ${activeStudioDensity==='half'?'selected':''}>half (50% 實景圖片 + 50% 動態圖表)</option>
                    <option value="rich" ${activeStudioDensity==='rich'?'selected':''}>rich (豐富模式 · ~40% 關鍵圖卡)</option>
                    <option value="balanced" ${activeStudioDensity==='balanced'?'selected':''}>balanced (平衡模式 · ~25% 核心轉折)</option>
                    <option value="minimal" ${activeStudioDensity==='minimal'?'selected':''}>minimal (精簡模式 · ~10% 章節標題)</option>
                  </select>
                </div>

                <div>
                  <label style="display: block; font-size: 11px; font-weight: 700; color: #cbd5e1; margin-bottom: 4px;">主視覺強調色 (accentColor)</label>
                  <div style="display: flex; align-items: center; gap: 6px;">
                    <input type="color" id="studio-remotion-accent-picker" value="${activeStudioAccent}" onchange="onStudioRemotionAccentChange(this.value)" style="width: 32px; height: 32px; padding: 1px; border: 1px solid #334155; border-radius: 4px; background: #060b16; cursor: pointer;">
                    <input type="text" id="studio-remotion-accent-hex" value="${activeStudioAccent}" maxlength="7" oninput="onStudioRemotionAccentHexInput(this.value)" style="flex: 1; padding: 6px 8px; background: #060b16; border: 1px solid #334155; color: #f8fafc; border-radius: 4px; font-size: 11.5px; font-family: monospace; font-weight: 700; text-transform: uppercase;">
                  </div>
                </div>

                <div>
                  <label style="display: block; font-size: 11px; font-weight: 700; color: #cbd5e1; margin-bottom: 4px;">算繪模式 (Stage Provider)</label>
                  <select id="studio-remotion-model" onchange="onStudioRemotionModelChange(this.value)" style="width: 100%; font-size: 11.5px; padding: 6px; background: #060b16; border: 1px solid #334155; color: #f8fafc; border-radius: 4px;">
                    <option value="remotion" ${activeStudioModel==='remotion'||activeStudioModel==='motion_graphics'?'selected':''}>⚛️ AI Motion Graphics Director (自動智能配鏡)</option>
                    <option value="remotion_coordinate_scale" ${activeStudioModel==='remotion_coordinate_scale'?'selected':''}>🧭 座標零 · 等緯尺度 (Scale)</option>
                    <option value="remotion_finance_candlestick" ${activeStudioModel==='remotion_finance_candlestick'?'selected':''}>📈 財經趨勢 · 走勢K線 (Candlestick)</option>
                    <option value="remotion_archival_doc" ${activeStudioModel==='remotion_archival_doc'?'selected':''}>📜 歷史檔案 · 解密文檔 (Archival)</option>
                    <option value="remotion_vox_split" ${activeStudioModel==='remotion_vox_split'?'selected':''}>🗞️ Vox調查 · 政策雙分割 (Vox Split)</option>
                    <option value="remotion_evidence" ${activeStudioModel==='remotion_evidence'?'selected':''}>📑 科技藍圖 · 文獻劃記 (Highlight)</option>
                    <option value="kenburns" ${activeStudioModel==='kenburns'?'selected':''}>📷 Ken Burns 靜態鏡頭縮放 (純圖片)</option>
                  </select>
                </div>
              </div>

              <!-- Action Buttons -->
              <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 14px; padding: 10px 12px; background: rgba(2, 132, 199, 0.12); border: 1px dashed #0284c7; border-radius: 8px;">
                <button id="remotion-auto-btn" class="btn-primary" style="background: linear-gradient(135deg, #0891b2 0%, #0e7490 100%); border: 1px solid #00F5FF; font-weight: 700; padding: 8px 16px; font-size: 12px;" onclick="autoRemotionCriticalScenes()">
                  ✨ 自動為所有關鍵分鏡產生卡片
                </button>
                <button class="btn-sec" style="font-weight: 700; padding: 8px 16px; font-size: 12px; border-color: #3b82f6; color: #60a5fa;" onclick="saveStudioStage('animation')">
                  💾 保存 Remotion 風格與分鏡設定
                </button>
                <div id="remotion-auto-status" style="font-size: 12px; color: #94a3b8;">已選風格：${activeStudioStyle}（${activeStudioDensity} 密度）</div>
              </div>

              <!-- Single Scene Card Customizer Dropdown & Fields -->
              <div style="margin-bottom: 14px; padding-top: 10px; border-top: 1px dashed rgba(255,255,255,0.1);">
                <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 6px;">單一分鏡卡片微調 (Single Scene Card Customizer)：</label>
                <select id="remotion-style-select" style="display: none;">
                  <option value="FoxHeaderScene" selected>FoxHeaderScene</option>
                  <option value="FoxMetricScene">FoxMetricScene</option>
                  <option value="FoxDataListScene">FoxDataListScene</option>
                  <option value="FoxTimelineScene">FoxTimelineScene</option>
                  <option value="BranchPathwayScene">BranchPathwayScene</option>
                  <option value="LeaderCalloutScene">LeaderCalloutScene</option>
                  <option value="ScaleCompareScene">ScaleCompareScene</option>
                  <option value="EvidenceHighlightScene">EvidenceHighlightScene</option>
                </select>
              </div>

              <!-- Parameters Grid -->
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 14px;">
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 4px;">目標分鏡 (Scene):</label>
                  <select id="remotion-target-scene" onchange="prefillRemotionFromScene(this.value)" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;">
                    ${scenes.map(s => `<option value="${s.scene_id}">Scene #${s.scene_id}${(s.animation && s.animation.meta && s.animation.meta.provider === 'remotion') ? ' ⚛️' : ''} (${(s.narration || '').slice(0, 24)}...)</option>`).join('')}
                  </select>
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 4px;">類別標籤 (Category):</label>
                  <input type="text" id="remotion-cat" value="" placeholder="留空 = 自動擷取" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;">
                </div>
                <div style="grid-column: span 2;">
                  <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 4px;">主標題 (Headline):</label>
                  <input type="text" id="remotion-headline" value="" placeholder="留空 = 自動擷取" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;">
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #00F5FF; display: block; margin-bottom: 4px;">核心數據 (Metric):</label>
                  <input type="text" id="remotion-metric" value="" placeholder="留空 = 自動擷取" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #00F5FF; border-radius: 6px; color: #00F5FF; font-family: monospace; font-weight: 700;">
                </div>
                <div style="grid-column: span 2;">
                  <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 4px;">副說明 (Subtext):</label>
                  <input type="text" id="remotion-subtext" value="" placeholder="留空 = 自動擷取" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;">
                </div>
              </div>

              <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                <button id="remotion-render-btn" class="btn-primary" style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); border: 1px solid #00F5FF; font-weight: 700; padding: 8px 16px; font-size: 12px;" onclick="renderAndApplyRemotionClip()">
                  ⚡ 只為此分鏡渲染卡片
                </button>
                <div id="remotion-status-text" style="font-size: 12px; color: #94a3b8;"></div>
              </div>

              <!-- Preview Container -->
              <div id="remotion-preview-box" style="display: none; margin-top: 14px; background: #040711; border: 1px solid #1e293b; border-radius: 8px; padding: 12px;">
                <div style="font-size: 12px; font-weight: 700; color: #38bdf8; margin-bottom: 8px;">🎬 Remotion 即時渲染預覽：</div>
                <video id="remotion-preview-video" controls autoplay loop style="width: 100%; max-height: 260px; border-radius: 6px; background: #000;"></video>
              </div>
            </div>

            <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 14px;">Camera Motion & Pan/Zoom dynamics for all scenes. Static images are brought to life using Ken Burns dynamic effects or Remotion React clips.</div>
            
            <!-- Filter & Search Toolbar -->
            <div style="background: #080d1a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <span style="font-size: 13px; font-weight: 800; color: #93c5fd; display: flex; align-items: center; gap: 6px;">
                  <span>🎬 全片分鏡 Remotion 動態預覽</span>
                  <span style="font-size: 11px; background: rgba(56,189,248,0.15); border: 1px solid #0284c7; color: #38bdf8; padding: 2px 8px; border-radius: 10px;">共 ${scenes.length} 幕</span>
                </span>
                <div style="display: flex; gap: 6px; margin-left: 6px; flex-wrap: wrap;">
                  <button type="button" class="btn-sec studio-anim-filter-btn" data-filter="all" onclick="filterStudioAnimScenes('all')" style="font-size: 11px; padding: 3px 10px; background: #1e3a8a; border-color: #38bdf8; color: #fff;">
                    全部 (${scenes.length})
                  </button>
                  <button type="button" class="btn-sec studio-anim-filter-btn" data-filter="remotion" onclick="filterStudioAnimScenes('remotion')" style="font-size: 11px; padding: 3px 10px; background: #080d16; border-color: #1e293b; color: #a855f7;">
                    ⚛️ Remotion 卡片 (${scenes.filter(s => s.is_remotion || (s.animation && s.animation.meta && (s.animation.meta.composition || s.animation.meta.sceneType)) || s.remotion_composition).length})
                  </button>
                  <button type="button" class="btn-sec studio-anim-filter-btn" data-filter="ken_burns" onclick="filterStudioAnimScenes('ken_burns')" style="font-size: 11px; padding: 3px 10px; background: #080d16; border-color: #1e293b; color: #94a3b8;">
                    📷 Ken Burns 運鏡 (${scenes.filter(s => !(s.is_remotion || (s.animation && s.animation.meta && (s.animation.meta.composition || s.animation.meta.sceneType)) || s.remotion_composition)).length})
                  </button>
                  <button type="button" class="btn-sec studio-anim-filter-btn" data-filter="ready" onclick="filterStudioAnimScenes('ready')" style="font-size: 11px; padding: 3px 10px; background: #080d16; border-color: #1e293b; color: #34d399;">
                    ✓ 影片已就緒 (${scenes.filter(s => s.has_animation || (s.animation && s.animation.path)).length})
                  </button>
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <input type="text" id="studio-anim-search" placeholder="🔍 搜尋分鏡或旁白..." oninput="onStudioAnimSearchInput()" style="font-size: 12px; padding: 5px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff; width: 200px;">
              </div>
            </div>

            <div id="studio-anim-scene-list" style="display: flex; flex-direction: column; gap: 14px;">
          `;
          scenes.forEach((s, idx) => {
            const hasVideo = Boolean(s.has_animation || (s.animation && s.animation.path));
            const videoPath = (s.animation && s.animation.path) || `animation/${s.tag || ('scene_' + String(s.scene_id).padStart(3, '0'))}.mp4`;
            const vSrc = hasVideo ? `/media/${currentProjectId}/${videoPath}` : '';
            const imgPath = (s.image && s.image.path) || `images/${s.tag || ('scene_' + String(s.scene_id).padStart(3, '0'))}.png`;
            const imgSrc = `/media/${currentProjectId}/${imgPath}`;

            const animMeta = (s.animation && s.animation.meta) || {};
            const comp = s.remotion_composition || animMeta.composition || animMeta.sceneType || '';
            const isRem = Boolean(s.is_remotion || comp || animMeta.provider === 'remotion');
            const props = s.remotion_props || animMeta.props || {};

            const headline = props.headline || props.title || '';
            const metric = props.metric || (props.value ? `${props.value}${props.unit || ''}` : '') || '';
            const category = props.category || props.badge || '';
            const subtext = props.subtext || props.subtitle || props.takeaway || props.description || '';
            const dur = (s.audio_duration || s.estimated_duration || 5).toFixed(1);

            let compBadgeColor = '#00F5FF';
            let compBadgeBg = 'rgba(0, 245, 255, 0.12)';
            let compBadgeBorder = 'rgba(0, 245, 255, 0.35)';
            let compIcon = '⚛️';
            if (comp.includes('Archival')) {
              compBadgeColor = '#f59e0b';
              compBadgeBg = 'rgba(245, 158, 11, 0.12)';
              compBadgeBorder = 'rgba(245, 158, 11, 0.35)';
              compIcon = '📜';
            } else if (comp.includes('Prompt') || comp.includes('Comparison')) {
              compBadgeColor = '#a855f7';
              compBadgeBg = 'rgba(168, 85, 247, 0.12)';
              compBadgeBorder = 'rgba(168, 85, 247, 0.35)';
              compIcon = '⚖️';
            } else if (comp.includes('Matrix') || comp.includes('Framework')) {
              compBadgeColor = '#0d9488';
              compBadgeBg = 'rgba(13, 148, 136, 0.12)';
              compBadgeBorder = 'rgba(13, 148, 136, 0.35)';
              compIcon = '🧭';
            } else if (comp.includes('Quote')) {
              compBadgeColor = '#ec4899';
              compBadgeBg = 'rgba(236, 72, 153, 0.12)';
              compBadgeBorder = 'rgba(236, 72, 153, 0.35)';
              compIcon = '💬';
            } else if (comp.includes('Metric')) {
              compBadgeColor = '#eab308';
              compBadgeBg = 'rgba(234, 179, 8, 0.12)';
              compBadgeBorder = 'rgba(234, 179, 8, 0.35)';
              compIcon = '📊';
            }

            bodyHtml += `
              <div class="studio-anim-scene-card" data-scene-id="${s.scene_id}" data-is-remotion="${isRem}" data-has-video="${hasVideo}" data-narration="${escapeHtml(s.narration || '')}" style="background: linear-gradient(180deg, #090e17 0%, #060a12 100%); border: 1px solid ${isRem ? '#1e3a8a' : 'var(--card-border)'}; border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 12px; transition: border-color 0.2s;">
                <!-- Card Header -->
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; padding-bottom: 8px; border-bottom: 1px solid #1e293b;">
                  <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <span style="font-weight: 800; font-size: 13px; color: #93c5fd; background: #0f172a; border: 1px solid #334155; padding: 2px 8px; border-radius: 4px;">
                      Scene #${s.scene_id}
                    </span>
                    ${isRem ? `
                      <span style="background: ${compBadgeBg}; border: 1px solid ${compBadgeBorder}; color: ${compBadgeColor}; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; display: inline-flex; align-items: center; gap: 4px;">
                        <span>${compIcon}</span> <span>${escapeHtml(comp || 'Remotion Card')}</span>
                      </span>
                    ` : `
                      <span style="background: rgba(100, 116, 139, 0.15); border: 1px solid #334155; color: #94a3b8; font-size: 11px; padding: 2px 8px; border-radius: 4px;">
                        📷 Ken Burns 運鏡
                      </span>
                    `}
                    ${s.is_presenter ? `<span style="background: rgba(139, 92, 246, 0.25); border: 1px solid #8b5cf6; color: #c4b5fd; font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px;">🎭 主播場景</span>` : ''}
                    <span style="font-size: 11px; color: #64748b; font-family: monospace;">⏱️ ${dur}s</span>
                  </div>
                  <div style="display: flex; align-items: center; gap: 8px;">
                    ${hasVideo ? `
                      <span style="font-size: 11px; font-weight: 700; color: #34d399; background: rgba(16, 185, 129, 0.15); border: 1px solid #059669; padding: 2px 7px; border-radius: 4px; display: inline-flex; align-items: center; gap: 3px;">
                        ✓ 1080p MP4 Ready
                      </span>
                    ` : `
                      <span style="font-size: 11px; color: #fbbf24; background: rgba(245, 158, 11, 0.15); border: 1px solid #d97706; padding: 2px 7px; border-radius: 4px;">
                        ⏳ 待算繪
                      </span>
                    `}
                    <button type="button" class="btn-sec" style="font-size: 11px; padding: 3px 8px; border-color: #00F5FF; color: #00F5FF; font-weight: 700;" onclick="focusRemotionScene(${s.scene_id})" title="將此分鏡帶入上方微調表單">
                      ⚡ 載入至微調卡片
                    </button>
                  </div>
                </div>

                <!-- Card Body: Video Player & Remotion Info -->
                <div style="display: flex; gap: 14px; flex-wrap: wrap; align-items: flex-start;">
                  <!-- Video Preview Player Column -->
                  <div style="flex: 0 0 320px; max-width: 100%; min-width: 260px;">
                    ${hasVideo ? `
                      <div style="position: relative; border-radius: 6px; overflow: hidden; background: #000; border: 1px solid #1e293b; aspect-ratio: 16/9; box-shadow: 0 2px 10px rgba(0,0,0,0.5);">
                        <video id="studio-scene-video-${s.scene_id}" controls preload="metadata" playsinline src="${vSrc}" poster="${imgSrc}" style="width: 100%; height: 100%; object-fit: contain; display: block;"></video>
                      </div>
                      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px; font-size: 11px;">
                        <a href="${vSrc}" target="_blank" style="color: #38bdf8; text-decoration: none; display: inline-flex; align-items: center; gap: 4px; font-weight: 600;">
                          ▶ 全螢幕另開播放
                        </a>
                        <a href="${vSrc}" download="scene_${String(s.scene_id).padStart(3, '0')}.mp4" style="color: #94a3b8; text-decoration: none;">
                          📥 下載此幕 MP4
                        </a>
                      </div>
                    ` : `
                      <div style="position: relative; border-radius: 6px; overflow: hidden; background: #000; border: 1px dashed #334155; aspect-ratio: 16/9;">
                        <img src="${imgSrc}" onerror="this.style.display='none'" style="width: 100%; height: 100%; object-fit: cover; opacity: 0.75; display: block;">
                        <div style="position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(4, 7, 14, 0.75); padding: 8px; text-align: center;">
                          <span style="font-size: 22px; margin-bottom: 4px;">🎬</span>
                          <span style="font-size: 11px; color: #fbbf24; font-weight: 700;">尚未算繪動態影片</span>
                          <span style="font-size: 10px; color: #94a3b8; margin-top: 2px;">可點擊上方執行算繪或單幕微調</span>
                        </div>
                      </div>
                    `}
                  </div>

                  <!-- Scene Details & Controls Column -->
                  <div style="flex: 1; min-width: 260px; display: flex; flex-direction: column; gap: 8px;">
                    <!-- Narration Text -->
                    <div style="background: #04070e; border: 1px solid #1e293b; border-radius: 6px; padding: 8px 10px;">
                      <div style="font-size: 10px; color: #64748b; font-weight: 700; margin-bottom: 3px;">🎙️ 旁白文本 (Narration):</div>
                      <div style="font-size: 12.5px; color: #f1f5f9; line-height: 1.45;">"${escapeHtml(s.narration || '（無旁白）')}"</div>
                    </div>

                    <!-- Remotion Extracted Details -->
                    ${(headline || metric || category || subtext) ? `
                      <div style="background: rgba(15, 23, 42, 0.65); border: 1px solid #1e293b; border-radius: 6px; padding: 8px 10px; display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 6px;">
                        ${headline ? `<div><span style="font-size: 10px; color: #94a3b8; display: block;">📌 主標題:</span> <span style="font-size: 11.5px; color: #38bdf8; font-weight: 700;">${escapeHtml(headline)}</span></div>` : ''}
                        ${metric ? `<div><span style="font-size: 10px; color: #94a3b8; display: block;">📊 核心數據:</span> <span style="font-size: 11.5px; color: #fbbf24; font-weight: 700;">${escapeHtml(metric)}</span></div>` : ''}
                        ${category ? `<div><span style="font-size: 10px; color: #94a3b8; display: block;">🏷️ 類別標籤:</span> <span style="font-size: 11px; color: #cbd5e1;">${escapeHtml(category)}</span></div>` : ''}
                        ${subtext ? `<div style="grid-column: 1 / -1;"><span style="font-size: 10px; color: #94a3b8; display: block;">📝 副說明:</span> <span style="font-size: 11px; color: #94a3b8;">${escapeHtml(subtext)}</span></div>` : ''}
                      </div>
                    ` : ''}

                    <!-- Camera Motion & Fine-tuning Row -->
                    <div style="display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; margin-top: auto;">
                      <div style="flex: 1; min-width: 170px;">
                        <label style="font-size: 10.5px; color: #94a3b8; display: block; margin-bottom: 3px;">📷 鏡頭運動動態 (Camera Motion):</label>
                        <select style="width: 100%; font-size: 11.5px; padding: 5px 8px; background: #04070e; border: 1px solid #1e293b; color: #cbd5e1; border-radius: 4px;" onchange="studioStageData.scenes[${idx}].camera_motion=this.value">
                          <option value="slow_zoom_in" ${s.camera_motion==='slow_zoom_in'?'selected':''}>Slow Zoom In (慢推焦點)</option>
                          <option value="slow_zoom_out" ${s.camera_motion==='slow_zoom_out'?'selected':''}>Slow Zoom Out (慢拉全景)</option>
                          <option value="pan_left" ${s.camera_motion==='pan_left'?'selected':''}>Pan Left (左移運鏡)</option>
                          <option value="pan_right" ${s.camera_motion==='pan_right'?'selected':''}>Pan Right (右移運鏡)</option>
                          <option value="static" ${s.camera_motion==='static'?'selected':''}>Static (靜止鏡頭)</option>
                        </select>
                      </div>
                      ${s.is_presenter ? `
                        <button type="button" class="btn-sec" style="padding: 5px 10px; font-size: 11px; font-weight: 700; background: rgba(139, 92, 246, 0.25); border-color: #8b5cf6; color: #c4b5fd; display: inline-flex; align-items: center; gap: 4px;" onclick="triggerSceneAvatarUpload(${s.scene_id})" title="方案2：直接上傳此分鏡的自錄真人/戴口罩出鏡影片">
                          📤 上傳自錄影片
                        </button>
                        <input type="file" id="scene-avatar-file-${s.scene_id}" accept="video/mp4,video/quicktime,video/webm" style="display:none;" onchange="uploadCustomSceneAvatarClip(${s.scene_id}, this.files[0])">
                        <button type="button" class="btn-sec" style="padding: 5px 10px; font-size: 11px; font-weight: 700; background: rgba(139, 92, 246, 0.18); border-color: #7c3aed; color: #c4b5fd;" onclick="rerenderSingleSceneAvatarClip(${s.scene_id})" title="單獨重新生成此分鏡口型">
                          🎭 重製口型
                        </button>
                      ` : ''}
                    </div>
                  </div>
                </div>
              </div>
            `;
          });
          bodyHtml += `</div>`;
        }
      } else if (stKey === 'subtitles') {
        const srtText = data.srt || '';
        const motionEnabled = data.motion_graphics_callouts !== false;
        const calloutsList = data.callouts_preview || [];
        let calloutsHtml = '';
        if (!isDrama && calloutsList.length > 0) {
          calloutsHtml = `
            <div style="margin-top: 12px; margin-bottom: 16px; background: #080d1a; border: 1px solid #1e293b; border-radius: 8px; padding: 14px;">
              <div style="font-weight: 700; color: #38bdf8; font-size: 13px; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between;">
                <span>🎬 fOx Hsiao 動態重點字卡預覽 (${calloutsList.length} 個已生成):</span>
                <span style="font-size: 12px; color: #94a3b8;">浮動於畫面上方 · 零字幕衝突</span>
              </div>
              <div style="max-height: 180px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; padding-right: 4px;">
                ${calloutsList.map(c => `
                  <div style="background: #0f172a; border-left: 3px solid #38bdf8; padding: 8px 12px; border-radius: 4px; font-size: 12px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                      <span style="color: #00F5FF; font-weight: 700; margin-right: 6px;">[${c.tag}]</span>
                      <b style="color: #fff;">${c.title}</b>
                      ${c.subtitle ? `<span style="color: #94a3b8; margin-left: 8px;">— ${c.subtitle}</span>` : ''}
                    </div>
                    <span style="color: #64748b; font-family: monospace; font-size: 11px;">${formatSecondsToMMSS(c.start)} ~ ${formatSecondsToMMSS(c.end)}</span>
                  </div>
                `).join('')}
              </div>
            </div>
          `;
        }
        bodyHtml += `
          <div style="margin-bottom: 16px;">
            ${!isDrama ? `
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; background:#0c1526; padding:12px 16px; border-radius:8px; border:1px solid #1e3a8a;">
                <div>
                  <b style="color:#38bdf8; font-size:14px;">✨ 動態重點字卡特效 (fOx Hsiao 風格)</b>
                  <div style="font-size:12px; color:#94a3b8; margin-top:2px;">依據當前旁白關鍵詞與數據指標，在畫面上方自動浮現動態重點字卡（不遮擋下方字幕）</div>
                </div>
                <label style="position:relative; display:inline-block; width:46px; height:26px; margin:0; cursor:pointer;">
                  <input type="checkbox" id="studio-motion-callouts" ${motionEnabled ? 'checked' : ''} onchange="toggleProjectMotionCallouts(this.checked)" style="opacity:0; width:0; height:0;">
                  <span style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:${motionEnabled ? '#0284c7' : '#334155'}; transition:.25s; border-radius:26px;" id="studio-motion-callouts-slider">
                    <span id="studio-motion-callouts-knob" style="position:absolute; height:20px; width:20px; left:${motionEnabled ? '23px' : '3px'}; bottom:3px; background-color:#ffffff; transition:.25s; border-radius:50%; box-shadow:0 1px 3px rgba(0,0,0,0.4);"></span>
                  </span>
                </label>
              </div>
              ${calloutsHtml}
            ` : `
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; background:#14120f; padding:12px 16px; border-radius:8px; border:1px solid rgba(245, 158, 11, 0.35);">
                <div>
                  <b style="color:#fbbf24; font-size:14px;">📱 9:16 直式短劇專用雙行字幕 (Vertical Drama Subtitles)</b>
                  <div style="font-size:12px; color:#cbd5e1; margin-top:2px;">自動排版為雙行、高對比、動態色彩高亮的短影音字幕，置中偏下避免遮擋演員面部與平台介面。</div>
                </div>
                <span style="font-size:11px; background:rgba(245, 158, 11, 0.2); border:1px solid #f59e0b; color:#fbbf24; font-weight:700; padding:3px 8px; border-radius:4px;">Drama Preset</span>
              </div>
            `}
            <label style="font-weight: 600; display: block; margin-bottom: 8px; color: #cbd5e1;">Subtitles (.srt format with timing):</label>
            <textarea id="studio-srt" style="width: 100%; height: 320px; font-family: monospace; font-size: 13px; background: #080d16; color: #e2e8f0; border: 1px solid var(--card-border); padding: 12px; border-radius: 6px; line-height: 1.5;">${srtText}</textarea>
          </div>
          <div style="font-size: 12px; color: var(--text-muted);">
            💡 <b>Tip:</b> ${isDrama ? '短劇字幕已針對 9:16 直式手機螢幕優化，加強黑底描邊與演員對話節奏同步。' : 'Subtitles are precisely rendered onto the final 1080p video with styled drop shadow. You can edit phrases or timestamps here.'}
          </div>
        `;
      } else if (stKey === 'render') {
        const finalRel = data.outputs && data.outputs.final ? data.outputs.final : null;
        const vSrc = finalRel ? `/media/${currentProjectId}/${finalRel}?t=${Date.now()}` : '';
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
                      ${isDrama ? "⚡ 組裝全流程並合成短劇 (Create Drama Video)" : "🔗 String All Stages Together & Create Video"}
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
      const currentOrder = isDrama ? STAGE_ORDER.filter(s => s !== 'music') : STAGE_ORDER;
      const currentIdx = currentOrder.indexOf(stKey);
      const prevKey = currentIdx > 0 ? currentOrder[currentIdx - 1] : null;
      const nextKey = currentIdx < currentOrder.length - 1 ? currentOrder[currentIdx + 1] : null;

      let footerHtml = `
        <div style="background: #080d16; border-top: 1px solid var(--card-border); padding: 14px 20px; border-radius: 0 0 8px 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
          <div>
            ${prevKey ? `
              <button class="btn-sec" style="font-size: 12px; padding: 7px 14px;" onclick="switchStudioStage('${prevKey}')">
                ← Previous Stage (${(activeMetaMap[prevKey] || STAGE_META[prevKey]).num}. ${(activeMetaMap[prevKey] || STAGE_META[prevKey]).name})
              </button>
            ` : '<div style="width: 120px;"></div>'}
          </div>
          <button class="btn-primary" style="padding: 9px 20px; font-size: 13px; font-weight: 700; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);" onclick="assembleAllStagesNow()">
            ${isDrama ? "⚡ 組裝全流程並合成短劇 (Create Drama Video)" : "🔗 String All Stages Together & Create Video"}
          </button>
          <div>
            ${nextKey ? `
              <button class="btn-sec" style="font-size: 12px; padding: 7px 14px;" onclick="switchStudioStage('${nextKey}')">
                Next Stage (${(activeMetaMap[nextKey] || STAGE_META[nextKey]).num}. ${(activeMetaMap[nextKey] || STAGE_META[nextKey]).name}) →
              </button>
            ` : '<div style="width: 120px;"></div>'}
          </div>
        </div>
      `;

      wsEl.innerHTML = headerHtml + versionBarHtml + liveBannerHtml + bodyHtml + footerHtml;
      if (stKey === 'scenes' && cachedAvatarsList && cachedAvatarsList.length > 0) {
        populatePresenterAvatarSelectors(cachedAvatarsList);
      }
      if (stKey === 'script') {
        updateStudioScriptCount(data.script_md || '');
      } else if (stKey === 'images') {
        apiJson('/api/images/live_status').then(sdata => {
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
        const d = await apiJson(`/api/projects/${currentProjectId}/stages/${stKey}/versions/switch/${targetV}`, { method: 'POST' });

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

    function findSceneForTake(sceneId) {
      const stageData = studioStageData || inspectedStageData;
      return stageData?.scenes?.find(scene => scene.scene_id === sceneId) || null;
    }

    async function cycleSceneMediaTake(sceneId, delta, mediaKey, switchTake) {
      const scene = findSceneForTake(sceneId);
      if (!scene) return;
      const currentTake = scene[mediaKey]?.meta?.active_take || 1;
      await switchTake(sceneId, currentTake + delta);
    }

    async function cycleSceneImageTake(sceneId, delta) {
      return cycleSceneMediaTake(sceneId, delta, 'image', switchSceneTakeDirect);
    }

    function renderStudioImageTakesStripCards(sceneId, takes, activeTake, styles, buster) {
      if (!takes || !takes.length) return '';
      styles = styles || (studioStageData && studioStageData.available_styles) || {};
      buster = buster || Date.now();
      return takes.map(tk => {
        const isAct = (tk.take === activeTake);
        const tkSrc = `/media/${currentProjectId}/${tk.path}?t=${buster}`;
        const tkStyle = (styles[tk.style] && styles[tk.style].label) || tk.style || 'Default';
        return `
          <div style="flex: 0 0 105px; background: ${isAct ? '#081a38' : '#03060d'}; border: 2px solid ${isAct ? '#3b82f6' : '#1e293b'}; border-radius: 6px; padding: 5px; display: flex; flex-direction: column; gap: 4px; cursor: pointer; transition: all 0.2s ease;" onclick="switchSceneTakeDirect(${sceneId}, ${tk.take})" title="Click to select Take #${tk.take} for final video">
            <div style="width: 100%; height: 56px; background: #000; border-radius: 4px; overflow: hidden; position: relative;">
              <img src="${tkSrc}" alt="" onerror="this.onerror=null; this.src='/media/${currentProjectId}/images/scene_${String(sceneId).padStart(3, '0')}.png';" style="width: 100%; height: 100%; object-fit: cover;" title="Take #${tk.take}: ${tk.prompt || ''}">
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
              <button class="btn-sec" style="flex: 1; font-size: 8px; padding: 3px 4px; font-weight: 600; ${isAct ? 'background: #059669; border-color: #10b981; color: #fff;' : 'background: #1e3a8a; border-color: #3b82f6; color: #fff;'}" onclick="event.stopPropagation(); switchSceneTakeDirect(${sceneId}, ${tk.take})">
                ${isAct ? '✓ In Video' : '👉 Select'}
              </button>
              <button class="btn-sec" style="padding: 2px 6px; font-size: 9px; background: rgba(239, 68, 68, 0.25); border-color: #b91c1c; color: #fca5a5; font-weight: 700;" onclick="event.stopPropagation(); deleteSceneImageTake(${sceneId}, ${tk.take})" title="Delete Take #${tk.take}">
                🗑️
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderInspImageTakesStripCards(sceneId, takes, activeTake, buster) {
      if (!takes || !takes.length) return '';
      buster = buster || Date.now();
      return takes.map(tk => {
        const isAct = (tk.take === activeTake);
        const tkSrc = `/media/${currentProjectId}/${tk.path}?t=${buster}`;
        return `
          <div style="flex: 0 0 90px; background: ${isAct ? '#081a38' : '#03060d'}; border: 2px solid ${isAct ? '#3b82f6' : '#1e293b'}; border-radius: 5px; padding: 4px; display: flex; flex-direction: column; gap: 3px; cursor: pointer;" onclick="switchSceneTakeDirect(${sceneId}, ${tk.take})">
            <div style="width: 100%; height: 46px; background: #000; border-radius: 3px; overflow: hidden; position: relative;">
              <img src="${tkSrc}" alt="" onerror="this.onerror=null; this.src='/media/${currentProjectId}/images/scene_${String(sceneId).padStart(3, '0')}.png';" style="width: 100%; height: 100%; object-fit: cover;">
              ${isAct ? '<span style="position: absolute; top: 1px; right: 1px; background: #10b981; color: #fff; font-size: 7px; font-weight: 700; padding: 0 2px; border-radius: 2px;">ACTIVE</span>' : ''}
            </div>
            <div style="font-size: 8px; font-weight: 700; color: ${isAct ? '#93c5fd' : '#cbd5e1'}; text-align: center;">Take #${tk.take}</div>
            <div style="display: flex; gap: 2px; margin-top: auto; padding-top: 1px;">
              <button class="btn-sec" style="flex: 1; font-size: 7px; padding: 1px 3px; font-weight: 600; ${isAct ? 'background: #059669; border-color: #10b981; color: #fff;' : 'background: #1e3a8a; border-color: #3b82f6; color: #fff;'}" onclick="event.stopPropagation(); switchSceneTakeDirect(${sceneId}, ${tk.take})">
                ${isAct ? '✓ In Video' : '👉 Select'}
              </button>
              <button class="btn-sec" style="padding: 1px 5px; font-size: 8px; background: rgba(239, 68, 68, 0.25); border-color: #b91c1c; color: #fca5a5; font-weight: 700;" onclick="event.stopPropagation(); deleteSceneImageTake(${sceneId}, ${tk.take})" title="Delete Take #${tk.take}">
                🗑️
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    function updateSceneImageInPlace(sceneId, targetTake, data) {
      const buster = Date.now();
      const relPath = (data && data.path) ? data.path : `images/takes/scene_${String(sceneId).padStart(3, '0')}_take${targetTake}.png`;
      const fullUrl = `/media/${currentProjectId}/${relPath}`;
      const bustedUrl = `${fullUrl}?t=${buster}`;

      // 1. Update in-memory objects
      let updatedTakes = [];
      let totalTakes = 0;
      [studioStageData, inspectedStageData].forEach(stageData => {
        if (stageData && stageData.scenes) {
          const sc = stageData.scenes.find(s => s.scene_id === sceneId);
          if (sc) {
            if (!sc.image) sc.image = {};
            if (!sc.image.meta) sc.image.meta = {};
            sc.image.meta.active_take = targetTake;
            sc.image.path = relPath;
            if (data && data.style) sc.visual_style = data.style;
            if (data && data.prompt) sc.prompt = data.prompt;
            if (sc.image.meta.takes) {
              updatedTakes = sc.image.meta.takes;
              totalTakes = updatedTakes.length;
            }
          }
        }
      });

      // 2. Update Studio Scene Preview Image
      const imgEl = document.getElementById(`studio-scene-img-${sceneId}`);
      if (imgEl) {
        imgEl.src = bustedUrl;
        imgEl.onclick = () => window.open(fullUrl);
      } else {
        const noImg = document.getElementById(`studio-no-img-${sceneId}`);
        if (noImg && noImg.parentNode) {
          noImg.parentNode.innerHTML = `
            <img id="studio-scene-img-${sceneId}" src="${bustedUrl}" style="width: 100%; height: 100%; object-fit: cover; cursor: pointer;" onclick="window.open('${fullUrl}')" title="Click to view full image">
            <button onclick="event.stopPropagation(); deleteSceneActiveImage(${sceneId})" style="position: absolute; top: 4px; right: 4px; background: rgba(0,0,0,0.75); border: 1px solid #ef4444; color: #fca5a5; border-radius: 3px; padding: 2px 6px; font-size: 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 3px; z-index: 2;" title="Delete current image">
              🗑️ Delete
            </button>
          `;
        }
      }

      // 3. Update Inspector Scene Preview Image
      const inspImgEl = document.getElementById(`insp-scene-img-${sceneId}`);
      if (inspImgEl) {
        inspImgEl.src = bustedUrl;
        inspImgEl.onclick = () => window.open(fullUrl);
      }

      // 4. Update scene card status badges
      const badgeEl = document.getElementById(`studio-scene-badge-${sceneId}`);
      if (badgeEl) {
        badgeEl.textContent = '✓ Generated';
        badgeEl.style.color = '#34d399';
      }
      const actTakeBadge = document.getElementById(`studio-scene-active-take-badge-${sceneId}`);
      if (actTakeBadge) {
        actTakeBadge.textContent = `✓ Take #${targetTake} Active`;
      }
      const inspActTakeBadge = document.getElementById(`insp-scene-active-take-badge-${sceneId}`);
      if (inspActTakeBadge) {
        inspActTakeBadge.textContent = `Take #${targetTake} Active`;
      }

      // 5. Update prev/next buttons
      const curTotal = totalTakes || targetTake;
      const prevBtn = document.getElementById(`studio-take-prev-btn-${sceneId}`);
      if (prevBtn) prevBtn.disabled = (targetTake <= 1);
      const nextBtn = document.getElementById(`studio-take-next-btn-${sceneId}`);
      if (nextBtn) nextBtn.disabled = (targetTake >= curTotal);

      const inspPrevBtn = document.getElementById(`insp-take-prev-btn-${sceneId}`);
      if (inspPrevBtn) inspPrevBtn.disabled = (targetTake <= 1);
      const inspNextBtn = document.getElementById(`insp-take-next-btn-${sceneId}`);
      if (inspNextBtn) inspNextBtn.disabled = (targetTake >= curTotal);

      // 6. Update takes thumbnail strip in Studio in-place without losing scroll
      const stripEl = document.getElementById(`studio-takes-strip-${sceneId}`);
      if (stripEl && updatedTakes.length > 0) {
        const curScroll = stripEl.scrollLeft;
        stripEl.innerHTML = renderStudioImageTakesStripCards(sceneId, updatedTakes, targetTake, null, buster);
        stripEl.scrollLeft = curScroll;
      }

      // 7. Update takes thumbnail strip in Inspector in-place without losing scroll
      const inspStripEl = document.getElementById(`insp-takes-strip-${sceneId}`);
      if (inspStripEl && updatedTakes.length > 0) {
        const curScroll = inspStripEl.scrollLeft;
        inspStripEl.innerHTML = renderInspImageTakesStripCards(sceneId, updatedTakes, targetTake, buster);
        inspStripEl.scrollLeft = curScroll;
      }

      // 8. If gallery modal is open, refresh it in-place
      const galModal = document.getElementById('takes-gallery-modal');
      if (galModal && galModal.style.display !== 'none') {
        openTakesGalleryModal(sceneId);
      }

      // 9. Toast notification on the scene card
      const toast = document.getElementById(`studio-scene-toast-${sceneId}`) || document.getElementById(`insp-scene-toast-${sceneId}`);
      if (toast) {
        toast.textContent = `✓ Take #${targetTake} selected for Final Video!`;
        toast.style.display = 'block';
        setTimeout(() => { if (toast) toast.style.display = 'none'; }, 3500);
      }
    }

    function updateSceneImageToEmpty(sceneId) {
      const imgEl = document.getElementById(`studio-scene-img-${sceneId}`);
      if (imgEl && imgEl.parentNode) {
        imgEl.parentNode.innerHTML = `<span id="studio-no-img-${sceneId}" style="font-size: 12px; color: gray;">No Image Generated</span>`;
      }
      const inspImgEl = document.getElementById(`insp-scene-img-${sceneId}`);
      if (inspImgEl && inspImgEl.parentNode) {
        inspImgEl.parentNode.innerHTML = `<span id="insp-no-img-${sceneId}" style="font-size: 12px; color: gray;">No Image Generated</span>`;
      }
      const badgeEl = document.getElementById(`studio-scene-badge-${sceneId}`);
      if (badgeEl) {
        badgeEl.textContent = '⏳ Pending';
        badgeEl.style.color = '#f59e0b';
      }
      const actTakeBadge = document.getElementById(`studio-scene-active-take-badge-${sceneId}`);
      if (actTakeBadge) {
        actTakeBadge.textContent = 'No Active Take';
      }
      const stripWrapper = document.getElementById(`studio-takes-wrapper-${sceneId}`);
      if (stripWrapper) {
        stripWrapper.style.display = 'none';
      }
      const prevBtn = document.getElementById(`studio-take-prev-btn-${sceneId}`);
      if (prevBtn) prevBtn.disabled = true;
      const nextBtn = document.getElementById(`studio-take-next-btn-${sceneId}`);
      if (nextBtn) nextBtn.disabled = true;
    }

    async function switchSceneMediaTake(sceneId, targetTake, mediaType, updateView) {
      if (!currentProjectId) return;
      try {
        const d = await apiJson(`/api/projects/${currentProjectId}/scenes/${sceneId}/${mediaType}_take/switch/${targetTake}`, { method: 'POST' });

        if (d.status === 'error') throw new Error(d.message);
        updateView(sceneId, targetTake, d);
      } catch (e) {
        alert(`Failed to switch ${mediaType} take: ${e.message}`);
      }
    }

    async function switchSceneTakeDirect(sceneId, targetTake) {
      return switchSceneMediaTake(sceneId, targetTake, 'image', updateSceneImageInPlace);
    }

    function openTakesGalleryModal(sceneId) {
      if (!currentProjectId) return;
      const stageData = studioStageData || inspectedStageData;
      if (!stageData || !stageData.scenes) return;
      const s = stageData.scenes.find(sc => sc.scene_id === sceneId);
      if (!s) return;

      const styles = stageData.available_styles || {};
      const takes = (s.image && s.image.meta && s.image.meta.takes) ? s.image.meta.takes : [];
      const activeTake = (s.image && s.image.meta && s.image.meta.active_take) ? s.image.meta.active_take : 1;

      const titleEl = document.getElementById('takes-modal-title');
      const subEl = document.getElementById('takes-modal-subtitle');
      const bodyEl = document.getElementById('takes-modal-body');

      if (titleEl) titleEl.innerHTML = `<span>🎞️ Scene #${sceneId} Image Variations & Takes (${takes.length} saved)</span>`;
      if (subEl) {
        subEl.innerHTML = `
          <div style="color: #94a3b8; font-size: 12px; margin-bottom: 8px;">
            Select which generation to use for Scene #${sceneId} in the final 1080p video. All versions are preserved locally in images/takes/.
          </div>
          <div style="background: rgba(14, 20, 34, 0.75); border: 1px solid rgba(124, 145, 182, 0.25); border-left: 3px solid #C19D49; border-radius: 6px; padding: 8px 12px; font-size: 13px; line-height: 1.45; color: #f1f5f9; text-align: left; margin-bottom: 4px;">
            <div style="font-size: 11px; font-weight: 700; color: #C19D49; margin-bottom: 2px; display: flex; align-items: center; justify-content: space-between;">
              <span style="display: flex; align-items: center; gap: 4px;">
                <span>🎙️</span> <span>分鏡旁白台詞 (Narration Script):</span>
              </span>
              <span style="font-size: 10px; color: #7C91B6; font-family: monospace;">${(s.narration || '').length} 字</span>
            </div>
            <div style="font-weight: 500; color: #fff; word-break: break-word;">
              ${escapeHtml(s.narration || '（無旁白）')}
            </div>
          </div>
        `;
      }

      if (!takes.length) {
        bodyEl.innerHTML = `<div style="text-align:center; padding:40px; color:var(--text-muted);">No saved takes found for Scene #${sceneId}. Click "Regenerate" to create variations.</div>`;
        document.getElementById('takes-gallery-modal').style.display = 'flex';
        return;
      }

      const buster = Date.now();
      let cardsHtml = `
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(270px, 1fr)); gap:16px;">
      `;

      takes.forEach(tk => {
        const isAct = (tk.take === activeTake);
        const tkUrl = `/media/${currentProjectId}/${tk.path}?t=${buster}`;
        const styleLabel = (styles[tk.style] && styles[tk.style].label) || tk.style || 'Default';
        const modelLabel = tk.model || 'ComfyUI SDXL';

        cardsHtml += `
          <div style="background:${isAct ? '#071833' : '#080d16'}; border:2px solid ${isAct ? '#3b82f6' : 'var(--card-border)'}; border-radius:10px; padding:14px; display:flex; flex-direction:column; gap:10px; box-shadow:${isAct ? '0 0 16px rgba(59,130,246,0.35)' : 'none'};">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-weight:700; color:${isAct ? '#93c5fd' : '#e2e8f0'}; font-size:14px;">Take #${tk.take}</span>
              ${isAct ? '<span style="background:#059669; color:#fff; font-size: 12px; font-weight:700; padding:2px 8px; border-radius:4px; box-shadow:0 1px 4px rgba(0,0,0,0.4);">✓ SELECTED FOR VIDEO</span>' : '<span style="font-size: 12px; color:#64748b;">Alternative Take</span>'}
            </div>

            <div style="width:100%; height:160px; background:#000; border-radius:6px; overflow:hidden; position:relative; cursor:pointer;" onclick="window.open('${tkUrl}')" title="Click to view full image">
              <img src="${tkUrl}" alt="" onerror="this.onerror=null; this.src='/media/${currentProjectId}/images/scene_${String(sceneId).padStart(3, '0')}.png';" style="width:100%; height:100%; object-fit:cover;">
              <div style="position:absolute; bottom:4px; right:4px; background:rgba(0,0,0,0.7); font-size:9px; color:#cbd5e1; padding:2px 6px; border-radius:3px;">🔍 Zoom</div>
            </div>

            <div style="font-size: 12px; display:flex; flex-direction:column; gap:3px;">
              <div style="display:flex; justify-content:space-between; color:#94a3b8;">
                <span>🎨 Style: <b style="color:#93c5fd;">${styleLabel}</b></span>
                <span>🕒 ${tk.created_at ? tk.created_at.split(' ')[1] || tk.created_at : 'Saved'}</span>
              </div>
              <div style="color:#64748b; font-size: 12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                Model: <span style="color:#cbd5e1;">${modelLabel}</span>
              </div>
            </div>

            <div style="background:#03060d; border:1px solid #1e293b; border-radius:4px; padding:6px; font-size: 12px; color:#cbd5e1; max-height:55px; overflow-y:auto; line-height:1.3;">
              ${tk.prompt || 'No prompt recorded'}
            </div>

            <div style="margin-top:auto; display:flex; gap:6px;">
              ${isAct ? `
                <button class="btn-sec" style="flex:1; font-size:12px; padding:8px; background:#059669; border-color:#10b981; color:#fff; font-weight:700; cursor:default;" disabled>
                  ✓ Active in Video
                </button>
              ` : `
                <button class="btn-primary" style="flex:1; font-size:12px; padding:8px; font-weight:700; background:linear-gradient(135deg, #2563eb, #1d4ed8);" onclick="selectTakeFromModal(${sceneId}, ${tk.take})">
                  ★ Select for Video
                </button>
              `}
              <button class="btn-sec" style="padding:8px 12px; font-size:12px; background:rgba(239,68,68,0.2); border-color: #b91c1c; color:#fca5a5; font-weight:700;" onclick="deleteTakeFromModal(${sceneId}, ${tk.take})" title="Delete Take #${tk.take}">
                🗑️ Delete
              </button>
            </div>
          </div>
        `;
      });

      cardsHtml += `</div>`;
      bodyEl.innerHTML = cardsHtml;
      document.getElementById('takes-gallery-modal').style.display = 'flex';
    }

    function closeTakesGalleryModal() {
      document.getElementById('takes-gallery-modal').style.display = 'none';
    }

    async function selectTakeFromModal(sceneId, takeNum) {
      await switchSceneTakeDirect(sceneId, takeNum);
      openTakesGalleryModal(sceneId);
    }

    const sceneTakeUi = {
      image: {
        mediaKey: 'image',
        label: 'image',
        countId: 'studio-takes-count-',
        headerId: 'studio-takes-header-count-',
        countText: count => `Images created (${count}):`,
        headerText: count => `🎞️ Takes (${count}):`,
        update: updateSceneImageInPlace,
        clear: updateSceneImageToEmpty,
        openModal: openTakesGalleryModal,
        closeModal: closeTakesGalleryModal
      },
      voice: {
        mediaKey: 'audio',
        label: 'voice',
        countId: 'studio-voice-takes-count-',
        headerId: 'studio-voice-takes-header-count-',
        countText: count => `Voice takes created (${count}):`,
        headerText: count => `🎞️ Voice Takes (${count}):`,
        update: updateSceneVoiceInPlace,
        clear: updateSceneVoiceToEmpty,
        openModal: openVoiceTakesGalleryModal,
        closeModal: closeVoiceTakesGalleryModal
      }
    };

    async function deleteSceneMediaTake(sceneId, takeNum, mediaType, { active = false, fromModal = false } = {}) {
      if (!currentProjectId) return;
      const config = sceneTakeUi[mediaType];
      const description = active ? `the ${config.label} for Scene #${sceneId}` : `${config.label} Take #${takeNum} for Scene #${sceneId}`;
      if (!confirm(`Are you sure you want to delete ${description}?`)) return;
      try {
        const suffix = active ? mediaType : `${mediaType}_take/${takeNum}`;
        const d = await apiJson(`/api/projects/${currentProjectId}/scenes/${sceneId}/${suffix}`, { method: 'DELETE' });

        if (d.status === 'error') throw new Error(d.message);
        const deletedTake = active ? d.deleted_take : takeNum;
        [studioStageData, inspectedStageData].forEach(stageData => {
          const scene = stageData?.scenes?.find(item => item.scene_id === sceneId);
          const media = scene?.[config.mediaKey];
          if (!media?.meta?.takes) return;
          if (deletedTake !== undefined) media.meta.takes = media.meta.takes.filter(take => take.take !== deletedTake);
          if (d.active_take !== undefined) media.meta.active_take = d.active_take;
          if (d.path !== undefined) media.path = d.path;
        });
        const remaining = d.remaining_takes || 0;
        const countElement = document.getElementById(`${config.countId}${sceneId}`);
        if (countElement) countElement.textContent = config.countText(remaining);
        const headerElement = document.getElementById(`${config.headerId}${sceneId}`);
        if (headerElement) headerElement.textContent = config.headerText(remaining);
        if (remaining > 0 && d.active_take) {
          config.update(sceneId, d.active_take, d);
        } else {
          config.clear(sceneId);
        }
        if (fromModal) {
          if (remaining > 0) config.openModal(sceneId);
          else config.closeModal();
        }
      } catch (e) {
        alert(`Failed to delete ${config.label} take: ${e.message}`);
      }
    }

    async function deleteSceneImageTake(sceneId, takeNum) {
      return deleteSceneMediaTake(sceneId, takeNum, 'image');
    }

    async function deleteSceneActiveImage(sceneId) {
      return deleteSceneMediaTake(sceneId, null, 'image', { active: true });
    }

    async function deleteTakeFromModal(sceneId, takeNum) {
      return deleteSceneMediaTake(sceneId, takeNum, 'image', { fromModal: true });
    }

    function renderStudioVoiceTakesStripCards(sceneId, vTakes, activeVTake, buster) {
      if (!vTakes || !vTakes.length) return '';
      buster = buster || Date.now();
      return vTakes.map(tk => {
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
              <button class="btn-sec" style="flex: 1; font-size: 9px; padding: 3px 6px; font-weight: 600; ${isAct ? 'background: #059669; border-color: #10b981; color: #fff;' : 'background: #1e3a8a; border-color: #3b82f6; color: #fff;'}" onclick="switchSceneVoiceTakeDirect(${sceneId}, ${tk.take})">
                ${isAct ? '✓ In Video' : '👉 Select'}
              </button>
              <button class="btn-sec" style="padding: 2px 6px; font-size: 8px; background: rgba(239, 68, 68, 0.25); border-color: #b91c1c; color: #fca5a5; font-weight: 700;" onclick="deleteSceneVoiceTake(${sceneId}, ${tk.take})" title="Delete Voice Take #${tk.take}">
                🗑️
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    function updateSceneVoiceInPlace(sceneId, targetTake, data) {
      const buster = Date.now();
      const relPath = (data && data.path) ? data.path : `audio/takes/scene_${String(sceneId).padStart(3, '0')}_take${targetTake}.wav`;

      let updatedTakes = [];
      let totalTakes = 0;
      [studioStageData, inspectedStageData].forEach(stageData => {
        if (stageData && stageData.scenes) {
          const sc = stageData.scenes.find(s => s.scene_id === sceneId);
          if (sc) {
            if (!sc.audio) sc.audio = {};
            if (!sc.audio.meta) sc.audio.meta = {};
            sc.audio.meta.active_take = targetTake;
            sc.audio.path = relPath;
            if (data && data.voice) sc.voice_profile = data.voice;
            if (data && data.duration) sc.audio_duration = data.duration;
            if (sc.audio.meta.takes) {
              updatedTakes = sc.audio.meta.takes;
              totalTakes = updatedTakes.length;
            }
          }
        }
      });

      const actBadge = document.getElementById(`studio-scene-active-voice-badge-${sceneId}`);
      if (actBadge) actBadge.textContent = `✓ Take #${targetTake} Active`;

      const curTotal = totalTakes || targetTake;
      const prevBtn = document.getElementById(`studio-voice-prev-btn-${sceneId}`);
      if (prevBtn) prevBtn.disabled = (targetTake <= 1);
      const nextBtn = document.getElementById(`studio-voice-next-btn-${sceneId}`);
      if (nextBtn) nextBtn.disabled = (targetTake >= curTotal);

      const stripEl = document.getElementById(`studio-voice-takes-strip-${sceneId}`);
      if (stripEl && updatedTakes.length > 0) {
        const curScroll = stripEl.scrollLeft;
        stripEl.innerHTML = renderStudioVoiceTakesStripCards(sceneId, updatedTakes, targetTake, buster);
        stripEl.scrollLeft = curScroll;
      }

      const vModal = document.getElementById('voice-takes-gallery-modal');
      if (vModal && vModal.style.display !== 'none') {
        openVoiceTakesGalleryModal(sceneId);
      }

      const toast = document.getElementById(`studio-scene-voice-toast-${sceneId}`) || document.getElementById(`insp-scene-voice-toast-${sceneId}`);
      if (toast) {
        toast.textContent = `✓ Voice Take #${targetTake} selected!`;
        toast.style.display = 'block';
        setTimeout(() => { if (toast) toast.style.display = 'none'; }, 3500);
      }
    }

    function updateSceneVoiceToEmpty(sceneId) {
      const badgeEl = document.getElementById(`studio-scene-voice-badge-${sceneId}`);
      if (badgeEl) {
        badgeEl.textContent = '⏳ Pending';
        badgeEl.style.color = '#f59e0b';
      }
      const actTakeBadge = document.getElementById(`studio-scene-active-voice-badge-${sceneId}`);
      if (actTakeBadge) {
        actTakeBadge.textContent = 'No Active Voice Take';
      }
      const stripWrapper = document.getElementById(`studio-voice-takes-wrapper-${sceneId}`);
      if (stripWrapper) {
        stripWrapper.style.display = 'none';
      }
      const prevBtn = document.getElementById(`studio-voice-prev-btn-${sceneId}`);
      if (prevBtn) prevBtn.disabled = true;
      const nextBtn = document.getElementById(`studio-voice-next-btn-${sceneId}`);
      if (nextBtn) nextBtn.disabled = true;
    }

    async function switchSceneVoiceTakeDirect(sceneId, targetTake) {
      return switchSceneMediaTake(sceneId, targetTake, 'voice', updateSceneVoiceInPlace);
    }

    async function cycleSceneVoiceTake(sceneId, delta) {
      return cycleSceneMediaTake(sceneId, delta, 'audio', switchSceneVoiceTakeDirect);
    }

    function openVoiceTakesGalleryModal(sceneId) {
      if (!currentProjectId) return;
      const stageData = studioStageData || inspectedStageData;
      if (!stageData || !stageData.scenes) return;
      const s = stageData.scenes.find(sc => sc.scene_id === sceneId);
      if (!s) return;

      const takes = (s.audio && s.audio.meta && s.audio.meta.takes) ? s.audio.meta.takes : [];
      const activeTake = (s.audio && s.audio.meta && s.audio.meta.active_take) ? s.audio.meta.active_take : 1;

      const titleEl = document.getElementById('voice-takes-modal-title');
      const subEl = document.getElementById('voice-takes-modal-subtitle');
      const bodyEl = document.getElementById('voice-takes-modal-body');

      if (titleEl) titleEl.innerHTML = `<span>🎙️ Scene #${sceneId} Voice Variations & Takes (${takes.length} saved)</span>`;
      if (subEl) subEl.textContent = `Select which voice synthesis take will be used in the final video for Scene #${sceneId}. All versions are preserved in audio/takes/.`;

      if (!takes.length) {
        bodyEl.innerHTML = `<div style="text-align:center; padding:40px; color:var(--text-muted);">No saved voice takes found for Scene #${sceneId}. Click "Synthesize Voice" to generate voice takes.</div>`;
        document.getElementById('voice-takes-gallery-modal').style.display = 'flex';
        return;
      }

      const buster = Date.now();
      let cardsHtml = `
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px;">
      `;

      takes.forEach(tk => {
        const isAct = (tk.take === activeTake);
        const tkSrc = `/media/${currentProjectId}/${tk.path}?t=${buster}`;
        const voiceLabel = tk.voice || tk.voice_profile || s.voice_profile || 'Default';
        const durVal = tk.duration_seconds || tk.duration || 0;
        const durStr = durVal ? `${Number(durVal).toFixed(1)}s` : '';

        cardsHtml += `
          <div style="background:${isAct ? '#071833' : '#080d16'}; border:2px solid ${isAct ? '#3b82f6' : 'var(--card-border)'}; border-radius:10px; padding:14px; display:flex; flex-direction:column; gap:10px; box-shadow:${isAct ? '0 0 16px rgba(59,130,246,0.35)' : 'none'};">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-weight:700; color:${isAct ? '#93c5fd' : '#e2e8f0'}; font-size:14px;">Take #${tk.take}</span>
              ${isAct ? '<span style="background:#059669; color:#fff; font-size: 12px; font-weight:700; padding:2px 8px; border-radius:4px; box-shadow:0 1px 4px rgba(0,0,0,0.4);">✓ SELECTED FOR VIDEO</span>' : '<span style="font-size: 12px; color:#64748b;">Alternative Take</span>'}
            </div>

            <div style="font-size: 12px; display:flex; flex-direction:column; gap:4px; background:#04070e; border:1px solid #1e293b; border-radius:6px; padding:8px;">
              <div style="display:flex; justify-content:space-between; color:#94a3b8;">
                <span>🗣️ Voice: <b style="color:#60a5fa;">${voiceLabel}</b></span>
                ${durStr ? `<span style="color:#a78bfa;">⏱️ ${durStr}</span>` : ''}
              </div>
              <div style="color:#64748b; font-size: 12px;">
                <span>🕒 ${tk.created_at ? (tk.created_at.split(' ')[1] || tk.created_at) : 'Saved'}</span>
              </div>
            </div>

            <div style="background:#03060d; border:1px solid #1e293b; border-radius:4px; padding:8px; font-size: 12px; color:#cbd5e1; max-height:60px; overflow-y:auto; line-height:1.3;">
              "${s.narration || ''}"
            </div>

            <div style="width:100%;">
              <audio controls src="${tkSrc}" style="width:100%; height:32px;"></audio>
            </div>

            <div style="margin-top:auto; display:flex; gap:6px;">
              ${isAct ? `
                <button class="btn-sec" style="flex:1; font-size:12px; padding:8px; background:#059669; border-color:#10b981; color:#fff; font-weight:700; cursor:default;" disabled>
                  ✓ Active in Video
                </button>
              ` : `
                <button class="btn-primary" style="flex:1; font-size:12px; padding:8px; font-weight:700; background:linear-gradient(135deg, #2563eb, #1d4ed8);" onclick="selectVoiceTakeFromModal(${sceneId}, ${tk.take})">
                  ★ Select for Video
                </button>
              `}
              <button class="btn-sec" style="padding:8px 12px; font-size:12px; background:rgba(239,68,68,0.2); border-color: #b91c1c; color:#fca5a5; font-weight:700;" onclick="deleteVoiceTakeFromModal(${sceneId}, ${tk.take})" title="Delete Voice Take #${tk.take}">
                🗑️ Delete
              </button>
            </div>
          </div>
        `;
      });

      cardsHtml += `</div>`;
      bodyEl.innerHTML = cardsHtml;
      document.getElementById('voice-takes-gallery-modal').style.display = 'flex';
    }

    function closeVoiceTakesGalleryModal() {
      document.getElementById('voice-takes-gallery-modal').style.display = 'none';
    }

    async function selectVoiceTakeFromModal(sceneId, takeNum) {
      await switchSceneVoiceTakeDirect(sceneId, takeNum);
      openVoiceTakesGalleryModal(sceneId);
    }

    async function deleteSceneVoiceTake(sceneId, takeNum) {
      return deleteSceneMediaTake(sceneId, takeNum, 'voice');
    }

    async function deleteSceneActiveVoice(sceneId) {
      return deleteSceneMediaTake(sceneId, null, 'voice', { active: true });
    }

    async function deleteVoiceTakeFromModal(sceneId, takeNum) {
      return deleteSceneMediaTake(sceneId, takeNum, 'voice', { fromModal: true });
    }

    // ---------------- ONLINE STOCK FOOTAGE & PHOTO MODAL ----------------
    let currentStockSceneId = null;
    let currentStockPrompt = '';

    function openStockMediaModal(sceneId, defaultPrompt) {
      currentStockSceneId = sceneId;
      currentStockPrompt = defaultPrompt || '';

      const modal = document.getElementById('stock-search-modal');
      const title = document.getElementById('stock-modal-title');
      const input = document.getElementById('stock-search-input');
      const body = document.getElementById('stock-modal-body');

      if (title) title.innerHTML = `<span>🌐 Online Stock Media for Scene #${sceneId}</span>`;

      // Extract search keywords from prompt (skip technical tags or style keywords)
      let cleanQuery = currentStockPrompt
        .replace(/[^\w\s\u4e00-\u9fa5]/gi, ' ')
        .replace(/\b(widescreen|composition|high detail|cinematic|photorealistic|documentary|sharp focus|film)\b/gi, '')
        .trim();
      const words = cleanQuery.split(/\s+/).filter(w => w.length > 2);
      cleanQuery = words.slice(0, 5).join(' ');

      if (input) input.value = cleanQuery;
      if (modal) modal.style.display = 'flex';

      if (cleanQuery) {
        executeStockSearch();
      } else {
        if (body) {
          body.innerHTML = `
            <div style="text-align:center; padding:60px 20px; color:var(--text-muted);">
              Type search keywords above (e.g. <i>ocean coral reef, busy city street, starry night sky</i>) and click <b>Search</b>.
            </div>
          `;
        }
      }
    }


    // ---------------- YOUTUBE FOOTAGE MODAL LOGIC ----------------
    let currentYouTubeSceneId = null;

    function openYouTubeFootageModal(sceneId, defaultQuery) {
      currentYouTubeSceneId = sceneId;
      const modal = document.getElementById('youtube-footage-modal');
      const title = document.getElementById('yt-footage-modal-title');
      const input = document.getElementById('yt-footage-input');
      const body = document.getElementById('yt-footage-modal-body');

      if (title) title.innerHTML = `<span>🎬 YouTube Footage Sourcing for Scene #${sceneId}</span>`;

      let cleanQ = (defaultQuery || '')
        .replace(/[^\w\s\u4e00-\u9fa5]/gi, ' ')
        .replace(/\b(widescreen|composition|high detail|cinematic|photorealistic|documentary|sharp focus|film)\b/gi, '')
        .trim();
      const words = cleanQ.split(/\s+/).filter(w => w.length > 1);
      cleanQ = words.slice(0, 5).join(' ');

      if (input) input.value = cleanQ;
      if (modal) modal.style.display = 'flex';

      if (cleanQ) {
        executeYouTubeSearch();
      } else if (body) {
        body.innerHTML = `
          <div style="text-align:center; padding:60px 20px; color:var(--text-muted);">
            Enter search keywords (e.g. <i>Yann LeCun interview, OpenAI Sora, Boston Dynamics Atlas</i>) or paste a YouTube URL and click <b>Search</b>.
          </div>
        `;
      }
    }

    function closeYouTubeFootageModal() {
      const modal = document.getElementById('youtube-footage-modal');
      if (modal) modal.style.display = 'none';
      currentYouTubeSceneId = null;
    }

    async function executeYouTubeSearch() {
      const input = document.getElementById('yt-footage-input');
      const body = document.getElementById('yt-footage-modal-body');
      const btn = document.getElementById('yt-footage-search-btn');

      const q = (input ? input.value : '').trim();
      if (!q) return alert("Please enter search keywords or a YouTube URL");

      if (btn) btn.disabled = true;
      body.innerHTML = `
        <div style="text-align:center; padding:60px 20px; color:#fca5a5;">
          <div class="spinner-inline" style="width:24px; height:24px; border-width:3px; margin-bottom:12px; border-color:rgba(239,68,68,0.2); border-top-color:#ef4444;"></div>
          <div>Searching YouTube for <b>"${escapeHtml(q)}"</b>...</div>
        </div>
      `;

      try {
        const url = `/api/youtube/search?q=${encodeURIComponent(q)}&limit=8`;
        const data = await apiJson(url);


        const results = data.results || [];

        if (!results.length) {
          body.innerHTML = `
            <div style="text-align:center; padding:60px 20px; color:var(--text-muted);">
              <div style="font-size:24px; margin-bottom:8px;">🔍</div>
              <div style="font-size:14px; color:#cbd5e1; font-weight:600;">No YouTube videos found for "${escapeHtml(q)}"</div>
              <div style="font-size:12px; margin-top:4px;">Try different keywords or paste a direct YouTube video URL.</div>
            </div>
          `;
          return;
        }

        let html = `
          <div style="font-size:12px; color:#94a3b8; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
            <span>Found <b>${results.length}</b> YouTube videos for "${escapeHtml(q)}":</span>
            <span style="color:#fca5a5;">Select a video to extract 2-3s clip or screenshot</span>
          </div>
          <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:14px;">
        `;

        results.forEach((item, idx) => {
          const durationStr = item.duration ? `${Math.floor(item.duration / 60)}:${String(Math.floor(item.duration % 60)).padStart(2, '0')}` : '';
          html += `
            <div style="background:#060c18; border:1px solid #1e293b; border-radius:8px; overflow:hidden; display:flex; flex-direction:column; gap:8px; padding:10px; transition:border-color 0.2s ease;">
              <div style="position:relative; width:100%; height:150px; background:#000; border-radius:6px; overflow:hidden;">
                <img src="${escapeHtml(item.thumbnail_url)}" data-youtube-preview="${idx}" style="width:100%; height:100%; object-fit:cover; cursor:pointer;" title="Click to view on YouTube">
                <div style="position:absolute; bottom:6px; right:6px; background:rgba(0,0,0,0.8); font-size:11px; font-weight:700; color:#fff; padding:2px 6px; border-radius:3px;">
                  ⏱️ ${durationStr}
                </div>
                <div style="position:absolute; top:6px; left:6px; background:rgba(220,38,38,0.85); color:#fff; font-size:10px; font-weight:700; padding:2px 6px; border-radius:3px;">
                  YouTube
                </div>
              </div>

              <div style="font-size:12px; color:#e2e8f0; font-weight:600; line-height:1.4; height:34px; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;" title="${escapeHtml(item.title)}">
                ${escapeHtml(item.title)}
              </div>

              <div style="font-size:11px; color:#64748b; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                📺 ${escapeHtml(item.channel || 'YouTube Channel')}
              </div>

              <button class="btn-primary" data-youtube-apply="${idx}" style="margin-top:auto; font-size:12px; padding:7px 10px; font-weight:700; background:linear-gradient(135deg, #dc2626, #b91c1c); border-color:#ef4444;" id="yt-apply-btn-${idx}">
                ✓ Extract & Apply to Scene #${currentYouTubeSceneId}
              </button>
            </div>
          `;
        });

        html += `</div>`;
        body.innerHTML = html;
        body.querySelectorAll('[data-youtube-preview]').forEach(element => {
          const item = results[Number(element.dataset.youtubePreview)];
          element.addEventListener('click', () => window.open(item.url, '_blank', 'noopener'));
        });
        body.querySelectorAll('[data-youtube-apply]').forEach(element => {
          const item = results[Number(element.dataset.youtubeApply)];
          element.addEventListener('click', () => applyYouTubeFootageToScene(currentYouTubeSceneId, item.url));
        });
      } catch (err) {
        body.innerHTML = `<div style="text-align:center; padding:40px; color:#f87171;">Failed to search YouTube: ${err.message}</div>`;
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function directApplyYouTubeFootage() {
      const input = document.getElementById('yt-footage-input');
      const val = (input ? input.value : '').trim();
      if (!val) return alert("Please enter a YouTube query or URL first");
      await applyYouTubeFootageToScene(currentYouTubeSceneId, val);
    }

    async function applyYouTubeFootageToScene(sceneId, targetQueryOrUrl) {
      if (!currentProjectId || !sceneId) return;

      const modeSel = document.getElementById('yt-footage-mode');
      const startInp = document.getElementById('yt-footage-start');
      const body = document.getElementById('yt-footage-modal-body');

      const mode = modeSel ? modeSel.value : 'clip';
      const startSec = startInp && startInp.value ? parseFloat(startInp.value) : null;

      if (body) {
        body.innerHTML = `
          <div style="text-align:center; padding:70px 20px; color:#fca5a5;">
            <div class="spinner-inline" style="width:28px; height:28px; border-width:3px; margin-bottom:14px; border-color:rgba(239,68,68,0.2); border-top-color:#ef4444;"></div>
            <div style="font-size:15px; font-weight:700; margin-bottom:6px;">Extracting YouTube Footage...</div>
            <div style="font-size:12px; color:#94a3b8;">Downloading partial 2-3s slice & formatting to 1080p MP4 / PNG for Scene #${sceneId}...</div>
          </div>
        `;
      }

      try {
        const payload = {
          query_or_url: targetQueryOrUrl,
          mode: mode,
          start_sec: startSec,
          duration_sec: 3.0
        };

        const data = await apiJson(`/api/projects/${currentProjectId}/scenes/${sceneId}/youtube_footage`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });




        const sc = data.scene;

        // Update local studioStageData if present
        if (studioStageData && studioStageData.scenes) {
          const idx = studioStageData.scenes.findIndex(s => s.scene_id === sceneId);
          if (idx !== -1) {
            studioStageData.scenes[idx] = sc;
          }
        }

        closeYouTubeFootageModal();

        // Refresh studio card thumbnail
        const imgEl = document.getElementById(`studio-scene-img-${sceneId}`);
        const badgeEl = document.getElementById(`studio-scene-badge-${sceneId}`);
        const toastEl = document.getElementById(`studio-scene-toast-${sceneId}`);

        if (sc.image && sc.image.path) {
          const newUrl = `/media/${currentProjectId}/${sc.image.path}?t=${Date.now()}`;
          if (imgEl) {
            imgEl.src = newUrl;
          } else {
            // Reload stage studio if placeholder was active
            loadStageStudio();
          }
        }
        if (badgeEl) {
          badgeEl.textContent = '✓ Generated (YouTube)';
          badgeEl.style.color = '#34d399';
        }
        if (toastEl) {
          toastEl.textContent = `✓ Scene #${sceneId} YouTube ${mode === 'clip' ? '3s Clip' : 'Screenshot'} Applied!`;
          toastEl.style.display = 'block';
          setTimeout(() => { toastEl.style.display = 'none'; }, 4000);
        }

        // If in scene editor tab, refresh it too
        if (typeof loadScenesForEditor === 'function') {
          loadScenesForEditor();
        }

      } catch (e) {
        alert("YouTube Footage Error: " + e.message);
        if (body) {
          body.innerHTML = `
            <div style="text-align:center; padding:40px; color:#f87171;">
              <div style="font-size:16px; font-weight:700; margin-bottom:8px;">❌ Failed to Extract Footage</div>
              <div>${escapeHtml(e.message)}</div>
              <button class="btn-sec" style="margin-top:16px;" onclick="executeYouTubeSearch()">Try Another Search</button>
            </div>
          `;
        }
      }
    }

    function closeStockSearchModal() {
      const modal = document.getElementById('stock-search-modal');
      if (modal) modal.style.display = 'none';
      currentStockSceneId = null;
    }

    async function executeStockSearch() {
      const input = document.getElementById('stock-search-input');
      const typeSel = document.getElementById('stock-filter-type');
      const srcSel = document.getElementById('stock-filter-source');
      const body = document.getElementById('stock-modal-body');
      const btn = document.getElementById('stock-search-btn');

      const q = (input ? input.value : '').trim();
      if (!q) return alert("Please enter search keywords");

      const type = typeSel ? typeSel.value : 'all';
      const source = srcSel ? srcSel.value : 'auto';

      if (btn) btn.disabled = true;
      body.innerHTML = `
        <div style="text-align:center; padding:60px 20px; color:#93c5fd;">
          <div class="spinner-inline" style="width:24px; height:24px; border-width:3px; margin-bottom:12px;"></div>
          <div>Searching online for <b>"${escapeHtml(q)}"</b> across stock libraries...</div>
        </div>
      `;

      try {
        const url = `/api/stock/search?q=${encodeURIComponent(q)}&type=${type}&source=${source}&limit=18`;
        const data = await apiJson(url);


        const results = data.results || [];

        if (!results.length) {
          body.innerHTML = `
            <div style="text-align:center; padding:60px 20px; color:var(--text-muted);">
              <div style="font-size:24px; margin-bottom:8px;">🔍</div>
              <div style="font-size:14px; color:#cbd5e1; font-weight:600;">No online stock media found for "${escapeHtml(q)}"</div>
              <div style="font-size:12px; margin-top:4px;">Try broader keywords (e.g. "nature", "mountains", "technology", "water") or change the Source filter.</div>
            </div>
          `;
          return;
        }

        let html = `
          <div style="font-size:12px; color:#94a3b8; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
            <span>Found <b>${results.length}</b> royalty-free media items:</span>
            <span style="color:#6ee7b7;">Click "Use This in Scene #${currentStockSceneId}" to apply</span>
          </div>
          <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:14px;">
        `;

        results.forEach((item, idx) => {
          const isVid = item.type === 'video';
          const badgeColor = isVid ? '#818cf8' : '#34d399';
          const badgeBorder = isVid ? '#4f46e5' : '#059669';
          const typeIcon = isVid ? '🎬 B-Roll Video' : '🖼️ Stock Photo';
          const srcName = item.source ? item.source.toUpperCase() : 'STOCK';
          const author = item.author || 'Creative Commons';
          const title = item.title || `${typeIcon} #${idx + 1}`;
          const durationStr = item.duration ? ` • ${Math.round(item.duration)}s` : '';

          html += `
            <div style="background:#060c18; border:1px solid #1e293b; border-radius:8px; overflow:hidden; display:flex; flex-direction:column; gap:8px; padding:10px; transition:border-color 0.2s ease;">
              <div style="position:relative; width:100%; height:150px; background:#000; border-radius:6px; overflow:hidden;">
                ${isVid ? `
                  <video src="${item.media_url}" poster="${item.thumbnail_url || ''}" preload="none" muted loop onmouseover="this.play().catch(()=>{})" onmouseout="this.pause()" style="width:100%; height:100%; object-fit:cover;"></video>
                  <div style="position:absolute; bottom:6px; left:6px; background:rgba(0,0,0,0.7); font-size:10px; color:#c7d2fe; padding:2px 6px; border-radius:3px; display:flex; align-items:center; gap:4px;">
                    ▶ Hover to preview
                  </div>
                ` : `
                  <img src="${escapeHtml(item.thumbnail_url || item.media_url)}" data-stock-preview="${idx}" style="width:100%; height:100%; object-fit:cover; cursor:pointer;" title="Click to view full image">
                `}
                <div style="position:absolute; top:6px; left:6px; background:rgba(0,0,0,0.8); border:1px solid ${badgeBorder}; color:${badgeColor}; font-size:10px; font-weight:700; padding:2px 6px; border-radius:3px;">
                  ${typeIcon}${durationStr}
                </div>
                <div style="position:absolute; top:6px; right:6px; background:rgba(0,0,0,0.8); border:1px solid #334155; color:#94a3b8; font-size:10px; font-weight:600; padding:2px 6px; border-radius:3px;">
                  ${srcName}
                </div>
              </div>

              <div style="font-size:12px; color:#e2e8f0; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(title)}">
                ${escapeHtml(title)}
              </div>

              <div style="display:flex; justify-content:space-between; font-size:10px; color:#64748b;">
                <span title="${escapeHtml(author)}">👤 ${escapeHtml(author.slice(0, 22))}</span>
                <span style="color:#0ea5e9;">${escapeHtml(item.license ? item.license.slice(0, 18) : 'CC License')}</span>
              </div>

              <button class="btn-primary" data-stock-apply="${idx}" style="margin-top:auto; font-size:12px; padding:7px 10px; font-weight:700; background:linear-gradient(135deg, #059669, #047857); border-color:#10b981;" id="stock-apply-btn-${idx}">
                ✓ Use This in Scene #${currentStockSceneId}
              </button>
            </div>
          `;
        });

        html += `</div>`;
        body.innerHTML = html;
        window._currentStockResults = results;
        body.querySelectorAll('[data-stock-preview]').forEach(element => {
          const item = results[Number(element.dataset.stockPreview)];
          element.addEventListener('click', () => window.open(item.media_url, '_blank', 'noopener'));
        });
        body.querySelectorAll('[data-stock-apply]').forEach(element => {
          const index = Number(element.dataset.stockApply);
          element.addEventListener('click', () => applyStockMediaToScene(currentStockSceneId, index));
        });
      } catch (err) {
        body.innerHTML = `
          <div style="text-align:center; padding:40px; color:#ef4444;">
            <div style="font-weight:700; margin-bottom:6px;">Stock Media Search Error</div>
            <div style="font-size:12px; color:#fca5a5;">${escapeHtml(err.message)}</div>
          </div>
        `;
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function applyStockMediaToScene(sceneId, resultIdx) {
      if (!window._currentStockResults || !window._currentStockResults[resultIdx]) return;
      const item = window._currentStockResults[resultIdx];
      const btn = document.getElementById(`stock-apply-btn-${resultIdx}`);

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-inline"></span> Downloading & Formatting 16:9...`;
      }

      try {
        const payload = {
          media_url: item.media_url,
          media_type: item.type,
          source: item.source || 'stock',
          title: item.title || '',
          author: item.author || '',
          license: item.license || ''
        };

        const data = await apiJson(`/api/projects/${currentProjectId}/scenes/${sceneId}/apply-stock`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });




        closeStockSearchModal();

        // Refresh studio / inspector
        if (typeof openStudioStage === 'function') {
          openStudioStage('images');
        } else if (typeof inspectStage === 'function') {
          inspectStage('images');
        }

        alert(`✓ Successfully applied stock ${item.type === 'video' ? 'video clip' : 'photo'} to Scene #${sceneId}! Render stage updated.`);
      } catch (e) {
        alert("Failed to apply stock media: " + e.message);
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `✓ Use This in Scene #${sceneId}`;
        }
      }
    }

    function updateStudioScriptCount(text) {
      const el = document.getElementById('studio-script-wc');
      if (el) {
        const cjkMatches = text ? text.match(/[\u4e00-\u9fa5]/g) : null;
        const cjkCount = cjkMatches ? cjkMatches.length : 0;
        const nonCjk = text ? text.replace(/[\u4e00-\u9fa5]/g, ' ') : '';
        const words = nonCjk ? Math.round(nonCjk.split(/\s+/).filter(Boolean).length) : 0;
        const totalUnit = cjkCount > 0 ? (cjkCount + words) + ' words/chars' : words + ' words';
        el.textContent = `${text ? text.length : 0} characters | ~${totalUnit}`;
      }
      const secBadge = document.getElementById('studio-script-sections-badge');
      if (secBadge && text) {
        const lines = text.split('\n');
        const sections = [];
        lines.forEach(l => {
          if (l.trim().startsWith('## ')) {
            sections.push(l.trim().substring(3).trim());
          }
        });
        if (sections.length > 0) {
          secBadge.style.display = 'inline-flex';
          secBadge.innerHTML = `📑 <b>${sections.length} 個章節段落:</b> ${sections.slice(0, 3).join(', ')}${sections.length > 3 ? ` 等共 ${sections.length} 段` : ''}`;
        } else {
          secBadge.style.display = 'none';
        }
      }
    }

    function exportStageScript(fmt) {
      if (!currentProjectId) return alert("Please select a project first.");
      window.open(`/api/projects/${currentProjectId}/export_script?format=${fmt}`, '_blank');
    }

    async function copyStageScriptToClipboard() {
      const ta = document.getElementById('studio-script-md');
      if (!ta || !ta.value.trim()) return alert("No script content to copy.");
      try {
        await navigator.clipboard.writeText(ta.value);
        showToast("📋 腳本全文已成功複製至剪貼簿！(Script copied to clipboard)");
      } catch (err) {
        ta.select();
        document.execCommand('copy');
        showToast("📋 腳本全文已複製！");
      }
    }

    // ---------------- Stage 3 Actual Script Export & Review ----------------
    function openStage3ExportModal() {
      if (!currentProjectId) return alert("Please select a project first.");
      const modal = document.getElementById('stage3-export-modal');
      if (!modal) return;

      const pTitle = currentProject?.title || currentProject?.data?.title || currentProject?.data?.topic || currentProjectId;
      const scenes = (studioStageData && studioStageData.scenes) || (inspectedStageData && inspectedStageData.scenes) || currentScenes || [];
      const totalScenes = scenes.length;

      let totalDuration = 0;
      scenes.forEach(s => {
        totalDuration += Number(s.audio_duration || s.estimated_duration || 5.0);
      });
      const durMin = Math.floor(totalDuration / 60);
      const durSec = Math.round(totalDuration % 60);
      const durStr = durMin > 0 ? `${durMin}分 ${durSec}秒 (~${totalDuration.toFixed(1)}s)` : `~${totalDuration.toFixed(1)}秒`;

      const projEl = document.getElementById('stage3-stat-project');
      const scEl = document.getElementById('stage3-stat-scenes');
      const durEl = document.getElementById('stage3-stat-duration');
      const statEl = document.getElementById('stage3-stat-status');

      if (projEl) projEl.textContent = pTitle;
      if (scEl) scEl.textContent = totalScenes > 0 ? String(totalScenes) : (currentProject?.stages?.scenes?.total || '0');
      if (durEl) durEl.textContent = durStr;
      if (statEl) {
        const isDone = currentProject?.stages?.scenes?.status === 'COMPLETED';
        statEl.textContent = isDone ? '✓ Completed' : (totalScenes > 0 ? 'Ready' : 'Pending');
        statEl.className = isDone ? 'badge badge-green' : 'badge badge-blue';
      }

      modal.style.display = 'flex';
      const sel = document.getElementById('stage3-preview-format-select');
      const currentFmt = sel ? sel.value : 'txt';
      loadStage3ScriptPreview(currentFmt);
    }

    function closeStage3ExportModal() {
      const modal = document.getElementById('stage3-export-modal');
      if (modal) modal.style.display = 'none';
    }

    function downloadStage3Script(fmt) {
      if (!currentProjectId) return alert("Please select a project first.");
      window.open(`/api/projects/${currentProjectId}/export_stage3_script?format=${encodeURIComponent(fmt)}`, '_blank');
    }

    async function loadStage3ScriptPreview(fmt = 'txt') {
      const previewArea = document.getElementById('stage3-export-preview-area');
      if (!previewArea) return;
      if (!currentProjectId) {
        previewArea.value = "請先選擇專案。";
        return;
      }
      previewArea.value = "載入分鏡審閱稿中 (Loading Stage 3 script preview)...";
      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/stage3_script_preview?format=${encodeURIComponent(fmt)}`);
        if (data && data.content) {
          previewArea.value = data.content;
          if (data.total_scenes && document.getElementById('stage3-stat-scenes')) {
            document.getElementById('stage3-stat-scenes').textContent = data.total_scenes;
          }
          if (data.total_duration_display && document.getElementById('stage3-stat-duration')) {
            document.getElementById('stage3-stat-duration').textContent = data.total_duration_display;
          }
        } else {
          previewArea.value = "尚未生成分鏡腳本或內容為空。";
        }
      } catch (e) {
        previewArea.value = `無法載入預覽: ${e.message}\n提示：請先確認此專案已完成 Stage 3 分鏡規劃。`;
      }
    }

    async function copyStage3PreviewContent() {
      const previewArea = document.getElementById('stage3-export-preview-area');
      if (!previewArea || !previewArea.value.trim()) return alert("目前無可複製之預覽內容。");
      try {
        await navigator.clipboard.writeText(previewArea.value);
        showToast("📋 分鏡審閱稿已成功複製至剪貼簿！(Copied to clipboard)");
      } catch (err) {
        previewArea.select();
        document.execCommand('copy');
        showToast("📋 分鏡審閱稿已複製至剪貼簿！");
      }
    }

    async function copyStage3FormattedText(fmt = 'txt') {
      if (!currentProjectId) return alert("Please select a project first.");
      try {
        showToast("⏳ 正在取得文稿內容...");
        const data = await apiJson(`/api/projects/${currentProjectId}/stage3_script_preview?format=${encodeURIComponent(fmt)}`);
        if (!data || !data.content) throw new Error("文稿為空");
        await navigator.clipboard.writeText(data.content);
        const nameMap = { txt: '分鏡校對文稿 (.txt)', md: 'Markdown 腳本 (.md)', narration: '純台詞朗讀稿 (.txt)', csv: 'CSV 表格', html: 'HTML 審閱稿', json: 'JSON 結構資料' };
        showToast(`📋 已成功複製 ${nameMap[fmt] || fmt} 至剪貼簿！`);
      } catch (err) {
        alert("複製失敗: " + err.message);
      }
    }

    function printStage3Script() {
      if (!currentProjectId) return alert("Please select a project first.");
      window.open(`/api/projects/${currentProjectId}/export_stage3_script?format=html&inline=1`, '_blank');
    }

    async function shareStage3Script() {
      if (!currentProjectId) return alert("Please select a project first.");
      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/stage3_script_preview?format=txt`);
        if (!data || !data.content) throw new Error("分鏡審閱稿內容為空");
        const title = data.title || currentProjectId;
        if (navigator.share) {
          try {
            await navigator.share({
              title: `[分鏡審閱] ${title}`,
              text: data.content
            });
            showToast("✓ 已開啟系統分享面板！");
            return;
          } catch (err) {
            if (err.name === 'AbortError') return;
          }
        }
        await navigator.clipboard.writeText(data.content);
        showToast("📋 已將審閱稿全文複製至剪貼簿！可直接貼至 Teams, Slack, Line 或 Email 發送給審閱者。");
      } catch (e) {
        alert("分享失敗: " + e.message);
      }
    }

    async function emailStage3Script() {
      if (!currentProjectId) return alert("Please select a project first.");
      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/stage3_script_preview?format=txt`);
        if (!data || !data.content) throw new Error("分鏡審閱稿內容為空");
        const title = data.title || currentProjectId;
        const subject = encodeURIComponent(`【腳本審閱請求】專案分鏡稿：${title} (Stage 3 Storyboard Review)`);
        const totalScenes = data.total_scenes || 0;
        const totalDur = data.total_duration_display || '';
        let bodyIntro = `各位好：\n\n附件/下方為專案《${title}》之 Stage 3 分鏡與台詞審閱稿。\n共 ${totalScenes} 幕，預估時長：${totalDur}。\n\n請協助審閱逐幕台詞與畫面規劃，並提供反饋。\n\n-------------------------\n`;
        const bodyContent = bodyIntro + data.content;
        const mailtoUrl = `mailto:?subject=${subject}&body=${encodeURIComponent(bodyContent.substring(0, 1800))}`;
        window.open(mailtoUrl, '_blank');
        showToast("✉️ 已啟動郵件客戶端！亦可使用「📋 複製」帶走完整全文。");
      } catch (e) {
        alert("建立郵件失敗: " + e.message);
      }
    }

    async function copyStage3ScriptToClipboard() {
      if (!currentProjectId) return alert("Please select a project first.");
      const scenes = (studioStageData && studioStageData.scenes) || (inspectedStageData && inspectedStageData.scenes) || currentScenes || [];
      if (scenes && scenes.length > 0) {
        const lines = [];
        scenes.forEach(s => {
          const spk = s.speaker || s.character;
          const spkStr = spk ? `[${spk}] ` : '';
          lines.push(`[Scene #${s.scene_id}] ${spkStr}${s.narration || ''}`);
        });
        const text = lines.join('\n\n');
        try {
          await navigator.clipboard.writeText(text);
          showToast(`📋 已成功複製共 ${scenes.length} 幕分鏡台詞至剪貼簿！`);
          return;
        } catch (err) {
          // fallback
        }
      }
      return copyStage3FormattedText('narration');
    }

    window.openStage3ExportModal = openStage3ExportModal;
    window.closeStage3ExportModal = closeStage3ExportModal;
    window.downloadStage3Script = downloadStage3Script;
    window.loadStage3ScriptPreview = loadStage3ScriptPreview;
    window.copyStage3PreviewContent = copyStage3PreviewContent;
    window.copyStage3FormattedText = copyStage3FormattedText;
    window.copyStage3ScriptToClipboard = copyStage3ScriptToClipboard;
    window.printStage3Script = printStage3Script;
    window.shareStage3Script = shareStage3Script;
    window.emailStage3Script = emailStage3Script;

    function triggerScriptFileUpload() {
      const inp = document.getElementById('studio-script-file-input');
      if (inp) {
        inp.value = '';
        inp.click();
      }
    }

    async function onScriptFileSelected(event) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = async (e) => {
        try {
          const content = e.target.result;
          const ta = document.getElementById('studio-script-md');
          if (!ta) return;

          let finalMd = content;
          if (file.name.endsWith('.json') || (content.trim().startsWith('{') && content.trim().endsWith('}'))) {
            try {
              const parsed = JSON.parse(content);
              if (parsed.sections && Array.isArray(parsed.sections)) {
                let lines = [`# ${parsed.title || 'Video Script'}`, '', `*Topic:* ${parsed.topic || ''}`, ''];
                parsed.sections.forEach(s => {
                  lines.push(`## ${s.name || 'Section'}`);
                  lines.push('');
                  lines.push(s.text || '');
                  lines.push('');
                });
                finalMd = lines.join('\n');
              } else if (parsed.script_md) {
                finalMd = parsed.script_md;
              }
            } catch (jsonErr) {
              console.warn("JSON parse fallback", jsonErr);
            }
          }

          ta.value = finalMd;
          updateStudioScriptCount(finalMd);
          showToast(`✓ 已成功匯入腳本檔案: ${file.name}！請確認內容後點擊「儲存」或「重新生成全片」。`);
        } catch (readErr) {
          alert("讀取檔案失敗: " + readErr.message);
        }
      };
      reader.readAsText(file, "UTF-8");
    }

    async function pasteScriptFromClipboard() {
      try {
        const text = await navigator.clipboard.readText();
        if (!text || !text.trim()) return alert("剪貼簿內無文字內容。");
        const ta = document.getElementById('studio-script-md');
        if (ta) {
          ta.value = text;
          updateStudioScriptCount(text);
          showToast("📋 已成功自剪貼簿貼上腳本！");
        }
      } catch (err) {
        alert("無法讀取剪貼簿，請直接在文字框內按 Ctrl+V 貼上。");
      }
    }

    async function regenerateVideoFromScript() {
      if (!currentProjectId) return alert("Please select a project first.");
      const ta = document.getElementById('studio-script-md');
      const scriptMd = ta ? ta.value.trim() : '';
      if (!scriptMd) return alert("Script is empty. Please enter or import script content.");

      if (!confirm("確定要儲存當前校對腳本，並自 Stage 3 (分鏡) 開始重新生成全片影片？\n\n系統將自動重新切分鏡、生成提示詞、繪製圖片、合成語音並輸出 1080p 影片。")) {
        return;
      }

      try {
        const btn = document.getElementById('btn-regen-from-script');
        if (btn) {
          btn.disabled = true;
          btn.innerHTML = `<span class="spinner-inline" style="width:12px; height:12px; margin-right:6px;"></span> 正在依新腳本啟動管線...`;
        }

        const d = await apiJson(`/api/projects/${currentProjectId}/regenerate_from_script`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ script_md: scriptMd })
        });

        if (d.status === 'already_running') {
          return alert("Pipeline is already executing. Please wait or stop it first.");
        }

        showToast("⚡ 已成功儲存新腳本！全片自動重製管線已啟動 (Stage 3~9)。");
        studioStageRunning = 'scenes';
        startPolling();
        switchStudioStage('scenes');
      } catch (err) {
        alert("啟動重製失敗: " + err.message);
      } finally {
        const btn = document.getElementById('btn-regen-from-script');
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `🚀 儲存並自此腳本重新生成全片 (Stage 3~9)`;
        }
      }
    }

    async function runStudioStageOnly(stKey) {
      if (!currentProjectId) return alert("Please select or create a project first.");
      try {
        const d = await apiJson(`/api/projects/${currentProjectId}/run_stage/${stKey}`, { method: 'POST' });

        if (d.status === 'already_running') {
          return alert("Pipeline is already executing. Please wait or stop it first.");
        }
        studioStageRunning = stKey;
        studioStageStarted = false;

        // Immediate visual feedback in workspace header
        const btn = document.getElementById('studio-run-btn');
        if (btn) {
          btn.disabled = true;
          const sName = (STAGE_META[stKey] && STAGE_META[stKey].name) ? STAGE_META[stKey].name : stKey;
          btn.innerHTML = `<span class="spinner-inline" style="width:12px; height:12px; margin-right:6px;"></span> Generating ${sName}...`;
        }

        const alertBox = document.getElementById('studio-stage-alert');
        if (alertBox) alertBox.style.display = 'flex';

        // If script stage, visually indicate progress in editor
        if (stKey === 'script') {
          const wc = document.getElementById('studio-script-wc');
          if (wc) wc.innerHTML = `<span style="color:#60a5fa; font-weight:700;">⏳ AI LLM is writing a brand new narration script...</span>`;
          const scriptArea = document.getElementById('studio-script-md');
          if (scriptArea) {
            scriptArea.style.opacity = '0.5';
          }
        }

        startPolling();
      } catch (e) {
        studioStageRunning = null;
        studioStageStarted = false;
        alert("Failed to start stage: " + e.message);
      }
    }


    async function autoGenerateWorldSetting(btn) {
      if (!currentProjectId) return alert("Please select or create a project first.");
      const origHtml = btn ? btn.innerHTML : '';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-inline" style="width:10px; height:10px; margin-right:4px;"></span> Generating...`;
      }
      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/generate_world_setting`, { method: 'POST' });

        if (data.status === 'ok' && data.world_setting) {
          const ws = data.world_setting;
          const stringifyWsVal = (v) => {
            if (!v) return '';
            if (typeof v === 'string') return v;
            if (Array.isArray(v)) {
              return v.map(item => (typeof item === 'object' ? ((item.location || item.name || '') + ': ' + (item.description || item.architectural_details || JSON.stringify(item))).trim().replace(/^:\s*/, '') : String(item))).join('; ');
            }
            if (typeof v === 'object') {
              return Object.entries(v).map(([k, val]) => `${k}: ${typeof val === 'object' ? JSON.stringify(val) : val}`).join('\n');
            }
            return String(v);
          };
          const eraEl = document.getElementById('studio-ws-era');
          if (eraEl) eraEl.value = stringifyWsVal(ws.temporal_era);
          const envEl = document.getElementById('studio-ws-env');
          if (envEl) envEl.value = stringifyWsVal(ws.environment_reality);
          const setEl = document.getElementById('studio-ws-settings');
          if (setEl) setEl.value = stringifyWsVal(ws.key_settings);
          const ensEl = document.getElementById('studio-ws-ensemble');
          if (ensEl) ensEl.value = stringifyWsVal(ws.ensemble_specs);
          const negEl = document.getElementById('studio-ws-negatives');
          if (negEl) negEl.value = Array.isArray(ws.negative_anachronisms) ? ws.negative_anachronisms.join('\n') : (ws.negative_anachronisms || '');
          syncWorldSettingToJson();
        } else {
          throw new Error(data.detail || "Server error");
        }
      } catch(e) {
        alert("Failed to auto-generate world setting: " + e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = origHtml;
        }
      }
    }

    function syncWorldSettingToJson() {
      const jsonArea = document.getElementById('studio-research');
      if (!jsonArea) return;
      let obj = {};
      try { obj = JSON.parse(jsonArea.value); } catch(e) { return; }
      if (!obj.world_setting || typeof obj.world_setting !== 'object') obj.world_setting = {};
      const eraEl = document.getElementById('studio-ws-era');
      if (eraEl) obj.world_setting.temporal_era = eraEl.value.trim();
      const envEl = document.getElementById('studio-ws-env');
      if (envEl) obj.world_setting.environment_reality = envEl.value.trim();
      const setEl = document.getElementById('studio-ws-settings');
      if (setEl) obj.world_setting.key_settings = setEl.value.trim();
      const ensEl = document.getElementById('studio-ws-ensemble');
      if (ensEl) obj.world_setting.ensemble_specs = ensEl.value.trim();
      const negEl = document.getElementById('studio-ws-negatives');
      if (negEl) obj.world_setting.negative_anachronisms = negEl.value.split('\n').map(s => s.trim()).filter(Boolean);
      jsonArea.value = JSON.stringify(obj, null, 2);
    }

    function syncWorldSettingFromJson() {
      const jsonArea = document.getElementById('studio-research');
      if (!jsonArea) return;
      try {
        const obj = JSON.parse(jsonArea.value);
        const ws = obj.world_setting || {};
        const eraEl = document.getElementById('studio-ws-era');
        if (eraEl) eraEl.value = ws.temporal_era || '';
        const envEl = document.getElementById('studio-ws-env');
        if (envEl) envEl.value = ws.environment_reality || '';
        const setEl = document.getElementById('studio-ws-settings');
        if (setEl) setEl.value = ws.key_settings || '';
        const ensEl = document.getElementById('studio-ws-ensemble');
        if (ensEl) ensEl.value = ws.ensemble_specs || '';
        const negEl = document.getElementById('studio-ws-negatives');
        if (negEl) negEl.value = Array.isArray(ws.negative_anachronisms) ? ws.negative_anachronisms.join('\n') : (ws.negative_anachronisms || '');
      } catch(e) {
        alert("Invalid JSON in research textarea: " + e.message);
      }
    }

    async function saveStudioStage(stKey) {
      if (!currentProjectId) return alert("Please select or create a project first.");
      let payload = {};
      if (stKey === 'research') {
        const text = document.getElementById('studio-research').value;
        try { payload.research = JSON.parse(text); } catch(e) { payload.research = { notes: text }; }
        if (studioStageData && studioStageData.characters) payload.characters = studioStageData.characters;
        const eraEl = document.getElementById('studio-ws-era');
        if (eraEl && payload.research && typeof payload.research === 'object') {
          if (!payload.research.world_setting || typeof payload.research.world_setting !== 'object') {
            payload.research.world_setting = {};
          }
          payload.research.world_setting.temporal_era = eraEl.value.trim();
          payload.research.world_setting.environment_reality = (document.getElementById('studio-ws-env') || {}).value || '';
          payload.research.world_setting.key_settings = (document.getElementById('studio-ws-settings') || {}).value || '';
          payload.research.world_setting.ensemble_specs = (document.getElementById('studio-ws-ensemble') || {}).value || '';
          const negsVal = (document.getElementById('studio-ws-negatives') || {}).value || '';
          payload.research.world_setting.negative_anachronisms = negsVal.split('\n').map(s => s.trim()).filter(Boolean);
        }
      } else if (stKey === 'script') {
        payload.script_md = document.getElementById('studio-script-md').value;
      } else if (stKey === 'music') {
        payload.music_plan = studioStageData.music_plan;
        payload.music_settings = studioStageData.music_settings;
      } else if (stKey === 'scenes' || stKey === 'prompts') {
        payload.scenes = studioStageData.scenes;
      } else if (stKey === 'animation') {
        payload.scenes = studioStageData.scenes;
        if (studioStageData && studioStageData.remotion) {
          payload.remotion = studioStageData.remotion;
          payload.remotion_style = studioStageData.remotion.style;
        }
        if (studioStageData && studioStageData.animation_model) {
          payload.animation_model = studioStageData.animation_model;
        }
      } else if (stKey === 'subtitles') {
        payload.srt = document.getElementById('studio-srt').value;
        const mcEl = document.getElementById('studio-motion-callouts');
        if (mcEl) payload.motion_graphics_callouts = mcEl.checked;
      }

      try {
        await apiRequest(`/api/projects/${currentProjectId}/stage_data/${stKey}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })

        alert(`Stage '${STAGE_META[stKey].name}' data saved successfully!`);
        loadStageStudio(stKey);
      } catch (e) {
        alert("Error saving: " + e.message);
      }
    }

    function onStudioStyleDropdownChange(styleKey) {
      if (!studioStageData || !studioStageData.available_styles) return;
      const st = studioStageData.available_styles[styleKey];
      const previewEl = document.getElementById('studio-style-tag-text');
      if (previewEl && st) {
        previewEl.textContent = `${st.style || ''} (${st.mood || ''}, ${st.lighting || ''})`;
      }
      const modelEl = document.getElementById('studio-img-model');
      if (modelEl) {
        if (st && st.recommended_model) {
          modelEl.value = st.recommended_model;
        } else if (styleKey.includes('photorealistic') || styleKey.includes('cinema')) {
          modelEl.value = 'juggernautXL_v8Rundiffusion.safetensors';
        }
      }
    }

    async function saveStudioImageSettings(applyToPrompts = false) {
      return saveImageSettingsFor('studio', applyToPrompts, async () => {
        if (applyToPrompts) alert("Image style & model saved and applied to all scene prompts!");
        loadStageStudio('images');
      });
    }

    async function runStudioImagesWithSave(forceStock = false) {
      if (!currentProjectId) return alert("Please select or create a project first.");
      if (forceStock) {
        const modelEl = document.getElementById('studio-img-model');
        if (modelEl) modelEl.value = 'stock';
      }
      if (await saveStudioImageSettings(false)) runStudioStageOnly('images');
    }

    async function applyStudioStyleFromPromptsTab() {
      if (!currentProjectId) return;
      const styleEl = document.getElementById('studio-prompt-style');
      if (!styleEl) return;
      const payload = {
        visual_style: styleEl.value,
        apply_to_prompts: true
      };
      try {
        await apiRequest(`/api/projects/${currentProjectId}/image_settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })

        alert("Visual style applied to all scene prompts!");
        loadStageStudio('prompts');
      } catch (e) {
        alert("Error: " + e.message);
      }
    }

    const scriptDebounceTimers = {};

    function onStudioScriptInput(sceneId, val) {
      const lenEl = document.getElementById(`studio-script-len-${sceneId}`) || document.getElementById(`insp-script-len-${sceneId}`);
      if (lenEl) lenEl.textContent = `${(val || '').length} 字`;

      if (scriptDebounceTimers[sceneId]) clearTimeout(scriptDebounceTimers[sceneId]);
      scriptDebounceTimers[sceneId] = setTimeout(() => {
        saveSingleSceneScript(sceneId, true);
      }, 1500);
    }

    function showScriptToast(sceneId, text) {
      const t = document.getElementById(`studio-script-toast-${sceneId}`) || document.getElementById(`insp-script-toast-${sceneId}`);
      if (t) {
        t.textContent = text;
        t.style.display = 'inline-block';
        setTimeout(() => { if (t) t.style.display = 'none'; }, 3000);
      }
    }

    async function saveSingleSceneScript(sceneId, isAutoSave = false) {
      if (!currentProjectId) return;
      if (scriptDebounceTimers[sceneId]) clearTimeout(scriptDebounceTimers[sceneId]);

      const scriptEl = document.getElementById(`studio-scene-script-${sceneId}`) || document.getElementById(`insp-scene-script-${sceneId}`);
      if (!scriptEl) return;
      const newNarr = scriptEl.value;

      // Check if unchanged against cache
      let cachedNarr = null;
      if (studioStageData && studioStageData.scenes) {
        const sc = studioStageData.scenes.find(s => s.scene_id === sceneId);
        if (sc) cachedNarr = sc.narration;
      }
      if (cachedNarr === null && inspectedStageData && inspectedStageData.scenes) {
        const sc = inspectedStageData.scenes.find(s => s.scene_id === sceneId);
        if (sc) cachedNarr = sc.narration;
      }
      if (cachedNarr !== null && cachedNarr === newNarr && isAutoSave) {
        return; // nothing changed
      }

      const saveBtn = document.getElementById(`studio-btn-save-script-${sceneId}`) || document.getElementById(`insp-btn-save-script-${sceneId}`);
      if (saveBtn && !isAutoSave) {
        saveBtn.disabled = true;
        saveBtn.textContent = '💾 Saving...';
      }

      try {
        await apiRequest(`/api/projects/${currentProjectId}/scenes/${sceneId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ narration: newNarr })
        })


        // Update local caches
        [studioStageData, inspectedStageData].forEach(sd => {
          if (sd && sd.scenes) {
            const sc = sd.scenes.find(s => s.scene_id === sceneId);
            if (sc) sc.narration = newNarr;
          }
        });
        if (typeof currentScenes !== 'undefined' && Array.isArray(currentScenes)) {
          const sc = currentScenes.find(s => s.scene_id === sceneId);
          if (sc) sc.narration = newNarr;
        }

        showScriptToast(sceneId, "✓ 台詞已儲存 (Saved)");
      } catch (e) {
        console.error("Failed to save scene script", e);
        if (!isAutoSave) alert("Failed to save script: " + e.message);
      } finally {
        if (saveBtn && !isAutoSave) {
          saveBtn.disabled = false;
          saveBtn.textContent = '💾 儲存台詞';
        }
      }
    }

    function onStudioSceneStyleChange(sceneId, styleKey) {
      if (!studioStageData || !studioStageData.available_styles) return;
      const st = studioStageData.available_styles[styleKey];
      if (!st) return;
      const promptEl = document.getElementById(`studio-scene-prompt-${sceneId}`);
      if (promptEl) {
        const cleanDesc = (promptEl.value || "").split(',')[0].trim();
        const tags = [st.style, st.lighting, st.lens, st.mood].filter(Boolean);
        if (tags.length) {
          promptEl.value = `${cleanDesc}, ${tags.join(', ')}, 16:9 widescreen composition, high detail`;
        }
      }
      const modelEl = document.getElementById(`studio-scene-model-${sceneId}`);
      if (modelEl) {
        if (st && st.recommended_model) {
          modelEl.value = st.recommended_model;
        } else if (styleKey.includes('photorealistic') || styleKey.includes('cinema')) {
          modelEl.value = 'juggernautXL_v8Rundiffusion.safetensors';
        }
      }
    }

    function applyStudioSceneStyleTags(sceneId) {
      const styleEl = document.getElementById(`studio-scene-style-${sceneId}`);
      if (styleEl) onStudioSceneStyleChange(sceneId, styleEl.value);
    }

    async function regenStudioImage(sceneId) {
      if (!currentProjectId) return;
      const promptEl = document.getElementById(`studio-scene-prompt-${sceneId}`);
      const modelEl = document.getElementById(`studio-scene-model-${sceneId}`);
      const styleEl = document.getElementById(`studio-scene-style-${sceneId}`);
      const stepsEl = document.getElementById('studio-img-steps');
      const cfgEl = document.getElementById('studio-img-cfg');
      const btn = document.getElementById(`studio-btn-regen-${sceneId}`);
      const progBox = document.getElementById(`studio-prog-box-${sceneId}`);
      const progTitle = document.getElementById(`studio-prog-title-${sceneId}`);
      const progPct = document.getElementById(`studio-prog-pct-${sceneId}`);
      const progBar = document.getElementById(`studio-prog-bar-${sceneId}`);
      const progGpuVal = document.getElementById(`studio-prog-gpu-val-${sceneId}`);
      const toast = document.getElementById(`studio-scene-toast-${sceneId}`);

      if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ Generating...";
      }
      if (toast) toast.style.display = 'none';

      if (progBox) {
        progBox.style.display = 'block';
        if (progTitle) progTitle.textContent = (modelEl && modelEl.value === 'stock') ? "🌐 Fetching online stock photo..." : "🚀 Starting ComfyUI DirectML...";
        if (progPct) progPct.textContent = "0%";
        if (progBar) progBar.style.width = "5%";
        if (progGpuVal) progGpuVal.textContent = (modelEl && modelEl.value === 'stock') ? "Online Service (0 GPU)" : "Querying GPU...";
      }

      let pollTimer = null;
      const pollStatus = async () => {
        try {
          const sdata = await apiJson('/api/images/live_status');



          // Update header GPU metrics if banner exists
          const gBanner = document.getElementById('studio-gpu-metric-title');
          if (gBanner && sdata.gpu) {
            const loadCol = sdata.gpu.util_percent > 60 ? '#f59e0b' : (sdata.gpu.util_percent > 15 ? '#38bdf8' : '#34d399');
            gBanner.innerHTML = `VRAM: <span style="color:#38bdf8;">${sdata.gpu.vram_gb} GB / ${sdata.gpu.vram_total_gb} GB</span> | Engine Load: <span style="color:${loadCol}; font-weight:700;">${sdata.gpu.util_percent}%</span>`;
          }

          const curProgBox = document.getElementById(`studio-prog-box-${sceneId}`);
          const curProgBar = document.getElementById(`studio-prog-bar-${sceneId}`);
          const curProgPct = document.getElementById(`studio-prog-pct-${sceneId}`);
          const curProgTitle = document.getElementById(`studio-prog-title-${sceneId}`);
          const curProgGpuVal = document.getElementById(`studio-prog-gpu-val-${sceneId}`);

          if (curProgBox && sdata.active && sdata.scene_id === sceneId) {
            curProgBox.style.display = 'block';
            if (sdata.total_steps > 0) {
              const pct = Math.max(5, sdata.percent || 0);
              if (curProgBar) curProgBar.style.width = `${pct}%`;
              if (curProgPct) curProgPct.textContent = `${pct}%`;
              if (curProgTitle) curProgTitle.textContent = `⚡ Step ${sdata.step}/${sdata.total_steps} (${pct}%)`;
            } else {
              if (curProgTitle) curProgTitle.textContent = "⏳ Loading model & pipeline...";
            }
          }

          if (curProgGpuVal && sdata.gpu) {
            const loadCol = sdata.gpu.util_percent > 60 ? '#f59e0b' : (sdata.gpu.util_percent > 15 ? '#38bdf8' : '#34d399');
            curProgGpuVal.innerHTML = `<span style="color:${loadCol};">${sdata.gpu.util_percent}% Load</span> | <span style="color:#93c5fd;">${sdata.gpu.vram_gb} GB VRAM</span>`;
          }
        } catch (_) {}
      };

      pollTimer = setInterval(pollStatus, 500);
      pollStatus();

      const scriptEl = document.getElementById(`insp-scene-script-${sceneId}`) || document.getElementById(`studio-scene-script-${sceneId}`);
      if (scriptEl && typeof saveSingleSceneScript === 'function') {
        await saveSingleSceneScript(sceneId, true);
      }

      const body = {
        prompt: promptEl ? promptEl.value : null,
        model: modelEl ? modelEl.value : null,
        visual_style: styleEl ? styleEl.value : null,
        steps: stepsEl ? parseInt(stepsEl.value) : 25,
        cfg: cfgEl ? parseFloat(cfgEl.value) : 6.5
      };

      try {
        const res = await apiRequest(`/api/projects/${currentProjectId}/scenes/${sceneId}/regenerate_image`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });

        const resData = await res.json().catch(() => ({}));
        if (pollTimer) clearInterval(pollTimer);
        const curProgBar = document.getElementById(`studio-prog-bar-${sceneId}`);
        const curProgPct = document.getElementById(`studio-prog-pct-${sceneId}`);
        const curProgTitle = document.getElementById(`studio-prog-title-${sceneId}`);
        const curProgBox = document.getElementById(`studio-prog-box-${sceneId}`);
        const curBtn = document.getElementById(`studio-btn-regen-${sceneId}`);
        if (curProgBar) curProgBar.style.width = "100%";
        if (curProgPct) curProgPct.textContent = "100%";
        if (curProgTitle) curProgTitle.textContent = "✓ Image Generated!";

        setTimeout(() => {
          if (curProgBox) curProgBox.style.display = 'none';
          if (curBtn) {
            curBtn.disabled = false;
            curBtn.textContent = "🔄 Regenerate Scene Image";
          }
          if (resData.scene) {
            [studioStageData, inspectedStageData].forEach(stageData => {
              if (stageData && stageData.scenes) {
                const idx = stageData.scenes.findIndex(sc => sc.scene_id === sceneId);
                if (idx !== -1) stageData.scenes[idx] = resData.scene;
              }
            });
            const activeTk = (resData.scene.image && resData.scene.image.meta && resData.scene.image.meta.active_take) || 1;
            updateSceneImageInPlace(sceneId, activeTk, {
              path: resData.scene.image ? resData.scene.image.path : null,
              style: resData.scene.visual_style,
              prompt: resData.scene.prompt
            });
            const takesCountEl = document.getElementById(`studio-takes-count-${sceneId}`);
            const takesLen = (resData.scene.image && resData.scene.image.meta && resData.scene.image.meta.takes) ? resData.scene.image.meta.takes.length : 1;
            if (takesCountEl) takesCountEl.textContent = `Images created (${takesLen}):`;
            const hdrCountEl = document.getElementById(`studio-takes-header-count-${sceneId}`);
            if (hdrCountEl) hdrCountEl.textContent = `🎞️ Takes (${takesLen}):`;
          } else {
            loadStageStudio('images');
          }
          const newToast = document.getElementById(`studio-scene-toast-${sceneId}`) || document.getElementById(`insp-scene-toast-${sceneId}`);
          if (newToast) {
            newToast.textContent = `✓ Scene #${sceneId} Image Regenerated!`;
            newToast.style.display = 'block';
            setTimeout(() => { if (newToast) newToast.style.display = 'none'; }, 4000);
          }
        }, 600);
      } catch (e) {
        if (pollTimer) clearInterval(pollTimer);
        const curProgBox = document.getElementById(`studio-prog-box-${sceneId}`);
        const curBtn = document.getElementById(`studio-btn-regen-${sceneId}`);
        if (curProgBox) curProgBox.style.display = 'none';
        alert("Image generation failed: " + e.message);
        if (curBtn) {
          curBtn.disabled = false;
          curBtn.textContent = "🔄 Regenerate Scene Image";
        }
      }
    }

    function onSceneNarrationInput(sceneId, idx, text) {
      if (!studioStageData || !studioStageData.scenes || !studioStageData.scenes[idx]) return;
      const s = studioStageData.scenes[idx];
      s.narration = text;
      const dirtyHint = document.getElementById(`scene-dirty-hint-${sceneId}`);
      const badgeEl = document.getElementById(`scene-narration-badge-${sceneId}`);
      const btnEl = document.getElementById(`btn-scene-resynth-${sceneId}`);
      const taEl = document.getElementById(`studio-scene-narration-${sceneId}`);

      if (dirtyHint) dirtyHint.style.display = 'inline';
      if (badgeEl) {
        badgeEl.innerHTML = `<span class="badge badge-warn" style="font-size: 11px; background: rgba(245,158,11,0.2); border: 1px solid #f59e0b; color: #fde68a;">⚠️ 台詞已更新 (語音待生成 TTS Outdated)</span>`;
      }
      if (taEl) {
        taEl.style.borderColor = '#f59e0b';
      }
      if (btnEl) {
        btnEl.style.boxShadow = '0 0 10px rgba(16, 185, 129, 0.6)';
        btnEl.innerHTML = `🎙️ 儲存台詞並立即重新生成 Scene #${sceneId} 語音 (Save & Re-generate Voice)`;
      }
    }

    async function saveAndRegenSceneVoice(sceneId, idx) {
      if (!currentProjectId) return alert("Please select a project first.");
      const btn = document.getElementById(`btn-scene-resynth-${sceneId}`);
      const statusEl = document.getElementById(`scene-resynth-status-${sceneId}`);
      const ta = document.getElementById(`studio-scene-narration-${sceneId}`);
      const newText = ta ? ta.value.trim() : (studioStageData?.scenes[idx]?.narration || '');

      if (!newText) {
        return alert("Narration text cannot be empty.");
      }

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-inline" style="width:12px; height:12px; margin-right:6px;"></span> 正在為 Scene #${sceneId} 重新生成語音 (BlueMagpie)...`;
      }
      if (statusEl) {
        statusEl.textContent = "語音生成中，完成後將自動同步字幕與分鏡時長...";
        statusEl.style.color = "#38bdf8";
      }

      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/scenes/${sceneId}/regenerate_voice`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ narration: newText })
        });



        // Update in-memory scene data
        if (studioStageData && studioStageData.scenes && studioStageData.scenes[idx]) {
          studioStageData.scenes[idx] = data.scene;
        }

        // Update badge and UI states
        const badgeEl = document.getElementById(`scene-narration-badge-${sceneId}`);
        const dirtyHint = document.getElementById(`scene-dirty-hint-${sceneId}`);
        const durEl = document.getElementById(`scene-dur-display-${sceneId}`);
        if (badgeEl) {
          badgeEl.innerHTML = `<span class="badge" style="font-size: 11px; background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.3); color: #34d399;">✓ 台詞與語音已同步更新 (${data.audio_duration.toFixed(1)}s)</span>`;
        }
        if (dirtyHint) dirtyHint.style.display = 'none';
        if (durEl) durEl.textContent = `${data.audio_duration.toFixed(1)}s`;
        if (ta) ta.style.borderColor = '#1e293b';

        // Update audio preview
        const audioPrev = document.getElementById(`studio-scene-audio-prev-${sceneId}`);
        if (audioPrev && data.audio_url) {
          audioPrev.src = `${data.audio_url}?t=${Date.now()}`;
          audioPrev.currentTime = 0;
          audioPrev.play().catch(() => {});
        }

        if (statusEl) {
          statusEl.textContent = `✓ Scene #${sceneId} 語音已重新生成 (${data.audio_duration.toFixed(1)}s)，字幕已自動重新對齊！`;
          statusEl.style.color = "#34d399";
          setTimeout(() => { if (statusEl) statusEl.textContent = ""; }, 4000);
        }
        showToast(`✓ Scene #${sceneId} 語音重新合成成功，時長與字幕已全線滲透更新！`);
      } catch (err) {
        alert("語音生成失敗: " + err.message);
        if (statusEl) {
          statusEl.textContent = "❌ " + err.message;
          statusEl.style.color = "#f87171";
        }
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.style.boxShadow = '';
          btn.innerHTML = `🎙️ 儲存台詞並重新生成此幕語音 (Save & Re-generate Voice)`;
        }
      }
    }

    async function saveScenesAndResyncOutdatedVoice() {
      if (!currentProjectId) return alert("Please select a project first.");
      await saveStudioStage('scenes');
      showToast("🎙️ 正在檢查所有分鏡台詞變更，並重新生成過期語音...");
      try {
        await apiRequest(`/api/projects/${currentProjectId}/fast_rerender_video`, { method: 'POST' })

        startPolling();
        showToast("⚡ 已啟動重新生成語音與影片！系統僅重新合成有修改台詞的分鏡。");
      } catch (err) {
        alert("啟動重整失敗: " + err.message);
      }
    }

    async function regenStudioVoice(sceneId) {
      if (!currentProjectId) return;
      const btn = document.getElementById(`studio-btn-voice-${sceneId}`);
      if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ Synthesizing...";
      }
      const voiceSelect = document.getElementById(`studio-scene-voice-${sceneId}`);
      const chosenVoice = voiceSelect ? voiceSelect.value : null;
      try {
        const payload = chosenVoice ? { voice_profile: chosenVoice } : {};
        await apiRequest(`/api/projects/${currentProjectId}/scenes/${sceneId}/regenerate_voice`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })

        await loadStageStudio('voice');
      } catch (e) {
        alert("Voice synthesis failed: " + e.message);
        if (btn) {
          btn.disabled = false;
          btn.textContent = "🎙️ Synthesize Voice";
        }
      }
    }

    async function runCascadeFrom(fromStage) {
      if (!currentProjectId) return alert("Please select or create a project first.");
      const isFull = (fromStage === 'script');
      const confirmMsg = isFull
        ? "⚡ Re-generate Full Video from current Research?\n\nThis will automatically cascade through:\n1. Fresh narration script based on research\n2. Storyboard with World Setting constraints\n3. Historical image prompts & high-res generation\n4. Cloned voiceover audio\n5. Subtitles & 1080p final video render\n\nContinue?"
        : "🎨 Re-generate Visuals and Render Video?\n\nThis will preserve your existing script and voiceover, and re-generate:\n1. Storyboard with World Setting constraints\n2. Image prompts & high-res generation\n3. Final 1080p video render\n\nContinue?";
      if (!confirm(confirmMsg)) return;

      try {
        const d = await apiJson(`/api/projects/${currentProjectId}/run_cascade/${fromStage}`, { method: 'POST' });

        if (d.status === 'already_running') {
          return alert("Pipeline is already executing. Please wait or stop it first.");
        }
        studioStageRunning = fromStage;
        startPolling();
        alert(isFull
          ? "🚀 Full video re-generation started! The pipeline is now cascading through Script -> Storyboard -> Prompts -> Images -> Voice -> Video."
          : "🎨 Visual re-generation started! The pipeline is now re-generating Storyboard -> Prompts -> Images -> Video.");
      } catch (e) {
        alert("Failed to start cascade: " + e.message);
      }
    }

    async function assembleAllStagesNow() {
      if (!currentProjectId) return alert("Please select or create a project first.");
      if (!confirm("String all completed & tuned stages together to create your new 1080p video?\n\nThis will take all tuned research, script, scenes, images, and cloned voiceovers, re-align subtitles, and render the final MP4 video.")) {
        return;
      }
      try {
        const d = await apiJson(`/api/projects/${currentProjectId}/assemble`, { method: 'POST' });

        if (d.status === 'already_running') {
          return alert("Pipeline is already executing. Please wait or pause first.");
        }
        alert("Pipeline assembly started! The system is now stringing all completed stages together and rendering your new video.");
        switchTab('creator');
        startPolling();
      } catch (e) {
        alert("Error starting assembly: " + e.message);
      }
    }

    // ---------------- YouTube Integration (@tsao36) ----------------
    let currentYouTubeStatus = null;
    let currentYouTubeMetadata = null;
    let ytUploadPollTimer = null;
    let ytAuthPollTimer = null;

    async function loadYouTubeStatus() {
      try {
        const data = await apiJson('/api/youtube/status');

        currentYouTubeStatus = data;

        // 1. Update Settings Tab elements
        const badgeEl = document.getElementById('yt-settings-status-badge');
        const cardEl = document.getElementById('yt-settings-channel-card');
        const secInd = document.getElementById('yt-secrets-indicator');
        const connectBtnText = document.getElementById('btn-yt-connect-text');

        if (secInd) {
          if (data.is_configured) {
            secInd.innerHTML = '<span style="color:#34d399; font-weight:600;">✓ client_secrets.json detected</span>';
          } else {
            secInd.innerHTML = '<span style="color:#f87171; font-weight:600;">⚠️ client_secrets.json missing</span>';
          }
        }

        const warnBox = document.getElementById('yt-settings-api-warning');
        const enableLink = document.getElementById('yt-settings-enable-link');

        if (data.is_authenticated && data.channel) {
          if (warnBox) warnBox.style.display = 'none';
          const ch = data.channel;
          if (badgeEl) {
            badgeEl.innerHTML = `<span style="background:#064e3b; border:1px solid #059669; color:#34d399; padding:4px 10px; border-radius:4px; font-size:12px; font-weight:700;">🟢 Connected: ${ch.title} (${ch.handle || '@tsao36'})</span>`;
          }
          if (cardEl) {
            cardEl.style.display = 'flex';
            document.getElementById('yt-settings-channel-title').textContent = ch.title;
            document.getElementById('yt-settings-channel-handle').textContent = ch.handle || '@tsao36';
            document.getElementById('yt-settings-channel-subs').textContent = `Subscribers: ${ch.subscriber_count || '0'} • Videos: ${ch.video_count || '0'}`;
            if (ch.avatar_url) {
              document.getElementById('yt-settings-avatar').src = ch.avatar_url;
            }
          }
          if (connectBtnText) connectBtnText.textContent = "Re-authenticate with Google";
        } else if (data.is_authenticated && !data.channel) {
          if (cardEl) cardEl.style.display = 'none';
          if (badgeEl) {
            badgeEl.innerHTML = '<span style="background:#7f1d1d; border:1px solid #ef4444; color:#fca5a5; padding:4px 10px; border-radius:4px; font-size:12px; font-weight:700;">⚠️ YouTube API Disabled</span>';
          }
          if (warnBox) {
            warnBox.style.display = 'block';
            if (enableLink && data.channel_error && data.channel_error.enable_url) {
              enableLink.href = data.channel_error.enable_url;
            }
          }
          if (connectBtnText) connectBtnText.textContent = "Re-authenticate with Google";
        } else if (data.is_configured) {
          if (warnBox) warnBox.style.display = 'none';
          if (badgeEl) {
            badgeEl.innerHTML = '<span style="background:#854d0e; border:1px solid #ca8a04; color:#fef08a; padding:4px 10px; border-radius:4px; font-size:12px; font-weight:700;">🟡 Ready to Connect</span>';
          }
          if (cardEl) cardEl.style.display = 'none';
          if (connectBtnText) connectBtnText.textContent = "Sign In & Connect YouTube Channel";
        } else {
          if (warnBox) warnBox.style.display = 'none';
          if (badgeEl) {
            badgeEl.innerHTML = '<span style="background:#334155; color:#cbd5e1; padding:4px 10px; border-radius:4px; font-size:12px; font-weight:600;">⚪ Not Connected</span>';
          }
          if (cardEl) cardEl.style.display = 'none';
          if (connectBtnText) connectBtnText.textContent = "Sign In & Connect YouTube Channel";
        }

        if (data.default_privacy) {
          const privEl = document.getElementById('yt-settings-default-privacy');
          if (privEl) privEl.value = data.default_privacy;
        }
        if (data.default_category_id) {
          const catEl = document.getElementById('yt-settings-default-category');
          if (catEl) catEl.value = data.default_category_id;
        }

        return data;
      } catch (e) {
        console.error("Failed to load YouTube status:", e);
      }
    }

    async function openYouTubeUploadModal(targetPid) {
      let pid = targetPid;
      if (!pid) {
        const previewTab = document.getElementById('tab-preview');
        const pSel = document.getElementById('preview-project-select');
        if (previewTab && previewTab.classList.contains('active') && pSel && pSel.value) {
          pid = pSel.value;
        }
      }
      if (!pid) pid = currentProjectId;
      if (!pid) return alert("Please select or render a project first.");
      if (pid !== currentProjectId && typeof selectProject === 'function') {
        selectProject(pid);
      }

      const modal = document.getElementById('youtube-upload-modal');
      if (modal) modal.style.display = 'flex';

      // Reset views
      document.getElementById('yt-modal-unauth-view').style.display = 'none';
      document.getElementById('yt-modal-ready-view').style.display = 'none';
      document.getElementById('yt-modal-uploading-view').style.display = 'none';
      document.getElementById('yt-modal-complete-view').style.display = 'none';
      document.getElementById('yt-modal-error-view').style.display = 'none';

      const status = await loadYouTubeStatus();

      // Check if authenticated
      if (!status || !status.is_authenticated) {
        document.getElementById('yt-modal-unauth-view').style.display = 'block';
        document.getElementById('btn-modal-do-upload').style.display = 'none';
        const secStatus = document.getElementById('yt-modal-secrets-status');
        if (secStatus) {
          secStatus.innerHTML = status && status.is_configured
            ? '<span style="color:#34d399;">✓ client_secrets.json detected on system. Ready to sign in!</span>'
            : '<span style="color:#f87171;">⚠️ client_secrets.json is missing. Please select your credentials file below.</span>';
        }
        return;
      }

      // Check if YouTube API is enabled in Google Cloud
      const modalApiWarn = document.getElementById('yt-modal-api-warning');
      const modalEnableLink = document.getElementById('yt-modal-enable-link');
      if (status.channel_error && status.channel_error.type === 'api_not_enabled') {
        if (modalApiWarn) modalApiWarn.style.display = 'block';
        if (modalEnableLink && status.channel_error.enable_url) {
          modalEnableLink.href = status.channel_error.enable_url;
        }
      } else {
        if (modalApiWarn) modalApiWarn.style.display = 'none';
      }

      // Fetch metadata
      try {
        const meta = await apiJson(`/api/projects/${currentProjectId}/youtube_metadata`);

        currentYouTubeMetadata = meta;

        // Fill Channel Info
        const ch = status.channel || {};
        document.getElementById('yt-modal-channel-title').textContent = ch.title || 'tsao36';
        document.getElementById('yt-modal-channel-handle').textContent = ch.handle || '@tsao36';
        if (ch.avatar_url) {
          document.getElementById('yt-modal-channel-avatar').src = ch.avatar_url;
        }

        // Fill Metadata
        const titleInput = document.getElementById('yt-modal-title');
        titleInput.value = meta.title || '';
        updateTitleCounter();

        document.getElementById('yt-modal-description').value = meta.description || '';
        document.getElementById('yt-modal-tags').value = (meta.tags || []).join(', ');
        document.getElementById('yt-modal-privacy').value = meta.privacy_status || 'public';
        document.getElementById('yt-modal-category').value = meta.category_id || '28';

        // Summary
        document.getElementById('yt-modal-video-meta-summary').textContent =
          `Source Video: ${currentProjectId}.mp4 (${meta.file_size_mb || 0} MB, ${meta.total_duration_seconds || 0}s, ${meta.chapters_count || 0} chapters)`;

        // Thumbnail Preview (Styled 1280x720 Traditional Mandarin YouTube Thumbnail)
        const thumbPrev = document.getElementById('yt-modal-thumb-preview');
        const thumbCopySummary = document.getElementById('yt-modal-thumb-copy-summary');
        if (meta.thumbnail_path && meta.thumbnail_path.length > 0) {
          thumbPrev.style.display = 'block';
          const relPath = meta.thumbnail_rel || 'output/thumbnail.png';
          thumbPrev.src = `/media/${currentProjectId}/${relPath}?t=${Date.now()}`;
          const tc = meta.thumbnail_config || {};
          if (thumbCopySummary) {
            thumbCopySummary.innerHTML = `
              <div><b style="color:#4ade80;">主標題：</b>${tc.main_title || '（自動生成繁中大標）'} &nbsp;|&nbsp; <b style="color:#93c5fd;">頂部小標：</b>${tc.top_kicker || '深度解析實驗室'}</div>
              <div style="color:#94a3b8; font-size:11px; margin-top:3px;">
                左側：${tc.left_line1 || ''} / ${tc.left_line2 || ''}<br>
                右側：${tc.right_line1 || ''} / ${tc.right_line2 || ''}
              </div>
            `;
          }
        } else {
          thumbPrev.style.display = 'none';
        }

        document.getElementById('yt-modal-ready-view').style.display = 'block';
        document.getElementById('btn-modal-do-upload').style.display = 'flex';
      } catch (e) {
        alert("Failed to load video metadata for YouTube: " + e.message);
      }
    }

    // ---------------- YouTube Thumbnail Studio (縮圖設計工作坊) ----------------
    const THUMB_COLOR_MAP = {
      cinema_vermilion: '#FF4215',
      dr_beauty_gold: '#FFD000',
      indie_vintage_yellow: '#FED631',
      neon_green: '#00E626',
      cyber_yellow: '#FFE600',
      electric_cyan: '#00F0FF',
      crimson_pop: '#FF2A54',
      magazine_white: '#FFFFFF',
    };

    const THUMB_TEMPLATE_LABELS = {
      editorial_chill: '潮流雜誌大字風 (Editorial Chill)',
      cinematic_cast: '電影雙側全明星卡司風 (Cinematic Ensemble Cast)',
      hiphop_mv_3d: '嘻哈MV 3D立體字卡風 (Dr. Beauty 3D)',
      indie_mv_film: '獨立樂團電影字卡風 (Indie MV Film)',
      cinema_impact: '台灣知識型大字風 (Cinema Impact)',
      minimal_poster: '電影海報極簡風 (Minimal Poster)',
    };

    const THUMB_FONT_LABELS = {
      'jf-openhuninn-2.1': 'jf open 粉圓',
      'iansui': '芫荽 Iansui',
      'lxgw_wenkai_tc': '霞鶩文楷 TC',
      'kose_font': '小瀨字體',
      'genyo_min': '源樣明體',
      'noto_serif_tc': '思源宋體',
      'jhenghei': '微軟正黑體',
    };

    function updateDefaultThumbSummaryBanner(th) {
      const el = document.getElementById('set-thumb-active-summary');
      if (!el) return;
      const tpl = THUMB_TEMPLATE_LABELS[th.template || 'editorial_chill'] || th.template;
      const font = THUMB_FONT_LABELS[th.font_family || 'jf-openhuninn-2.1'] || th.font_family;
      const weight = (th.font_weight || 'bold').toUpperCase();
      const colorDesc = (th.color_preset === 'random' || !th.color_preset)
        ? '🎲 隨機高對比色'
        : `${th.color_preset} (${th.primary_color || '#00E626'})`;
      const scalePct = Math.round((th.title_scale !== undefined ? th.title_scale : 1.0) * 100) + '%';
      const darkenPct = Math.round((th.darken !== undefined ? th.darken : 0.20) * 100) + '%';
      const overlapTxt = (th.subject_overlap !== false) ? '人像疊字ON' : '人像疊字OFF';
      const kickerTxt = th.default_top_kicker ? ` · 固定小標「${th.default_top_kicker}」` : ' · AI自動小標';
      el.innerHTML = `<span style="color:#4ade80;">[${tpl}]</span> · <span style="color:#38bdf8;">${font} (${weight})</span> · 配色: <span style="color:#fbbf24;">${colorDesc}</span> · 字級 ${scalePct} · 暗角 ${darkenPct} · ${overlapTxt}${kickerTxt}`;
    }

    function populateDefaultThumbnailSettingsUI(th) {
      const cfg = Object.assign({
        template: 'editorial_chill',
        color_preset: 'random',
        primary_color: '#00E626',
        font_family: 'jf-openhuninn-2.1',
        font_weight: 'bold',
        bg_source: 'auto',
        subject_overlap: true,
        title_scale: 1.0,
        darken: 0.20,
        grain: 0.032,
        show_avatar_badge: true,
        use_llm_copy: true,
        default_top_kicker: '',
      }, th || {});

      const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el && val !== undefined && val !== null) el.value = val;
      };
      setVal('set-thumb-template', cfg.template);
      setVal('set-thumb-color-preset', cfg.color_preset);
      if (cfg.primary_color && cfg.primary_color !== 'random') {
        setVal('set-thumb-primary-color', cfg.primary_color);
      } else if (THUMB_COLOR_MAP[cfg.color_preset]) {
        setVal('set-thumb-primary-color', THUMB_COLOR_MAP[cfg.color_preset]);
      }
      setVal('set-thumb-font-family', cfg.font_family);
      setVal('set-thumb-font-weight', cfg.font_weight);
      setVal('set-thumb-bg-source', cfg.bg_source);
      setVal('set-thumb-default-kicker', cfg.default_top_kicker || '');

      const scaleVal = cfg.title_scale !== undefined ? cfg.title_scale : 1.0;
      setVal('set-thumb-title-scale', scaleVal);
      const scaleLbl = document.getElementById('set-thumb-scale-val');
      if (scaleLbl) scaleLbl.textContent = Math.round(scaleVal * 100) + '%';

      const darkenVal = cfg.darken !== undefined ? cfg.darken : 0.20;
      setVal('set-thumb-darken', darkenVal);
      const darkenLbl = document.getElementById('set-thumb-darken-val');
      if (darkenLbl) darkenLbl.textContent = Math.round(darkenVal * 100) + '%';

      const grainVal = cfg.grain !== undefined ? cfg.grain : 0.032;
      setVal('set-thumb-grain', grainVal);
      const grainLbl = document.getElementById('set-thumb-grain-val');
      if (grainLbl) grainLbl.textContent = (grainVal * 100).toFixed(1) + '%';

      const ovEl = document.getElementById('set-thumb-subject-overlap');
      if (ovEl) ovEl.checked = cfg.subject_overlap !== false;
      const avEl = document.getElementById('set-thumb-avatar-badge');
      if (avEl) avEl.checked = cfg.show_avatar_badge !== false;
      const llmEl = document.getElementById('set-thumb-use-llm-copy');
      if (llmEl) llmEl.checked = cfg.use_llm_copy !== false;

      updateDefaultThumbSummaryBanner(cfg);
    }

    function collectDefaultThumbnailSettingsFromUI() {
      const presetVal = document.getElementById('set-thumb-color-preset') ? document.getElementById('set-thumb-color-preset').value : 'random';
      const primaryColorVal = document.getElementById('set-thumb-primary-color') ? document.getElementById('set-thumb-primary-color').value : '#00E626';
      return {
        template: document.getElementById('set-thumb-template') ? document.getElementById('set-thumb-template').value : 'editorial_chill',
        color_preset: presetVal,
        primary_color: THUMB_COLOR_MAP[presetVal] || primaryColorVal,
        secondary_color: presetVal === 'custom' ? primaryColorVal : '#FFFFFF',
        kicker_color: THUMB_COLOR_MAP[presetVal] || primaryColorVal,
        font_family: document.getElementById('set-thumb-font-family') ? document.getElementById('set-thumb-font-family').value : 'jf-openhuninn-2.1',
        font_weight: document.getElementById('set-thumb-font-weight') ? document.getElementById('set-thumb-font-weight').value : 'bold',
        bg_source: document.getElementById('set-thumb-bg-source') ? document.getElementById('set-thumb-bg-source').value : 'auto',
        default_top_kicker: document.getElementById('set-thumb-default-kicker') ? document.getElementById('set-thumb-default-kicker').value.trim() : '',
        title_scale: parseFloat(document.getElementById('set-thumb-title-scale') ? document.getElementById('set-thumb-title-scale').value : '1.0'),
        darken: parseFloat(document.getElementById('set-thumb-darken') ? document.getElementById('set-thumb-darken').value : '0.20'),
        grain: parseFloat(document.getElementById('set-thumb-grain') ? document.getElementById('set-thumb-grain').value : '0.032'),
        subject_overlap: document.getElementById('set-thumb-subject-overlap') ? document.getElementById('set-thumb-subject-overlap').checked : true,
        show_avatar_badge: document.getElementById('set-thumb-avatar-badge') ? document.getElementById('set-thumb-avatar-badge').checked : true,
        use_llm_copy: document.getElementById('set-thumb-use-llm-copy') ? document.getElementById('set-thumb-use-llm-copy').checked : true,
      };
    }

    function onDefaultThumbColorPresetChange() {
      const preset = document.getElementById('set-thumb-color-preset').value;
      if (THUMB_COLOR_MAP[preset]) {
        document.getElementById('set-thumb-primary-color').value = THUMB_COLOR_MAP[preset];
      }
      previewDefaultThumbnailSettings(preset === 'random');
    }

    function onDefaultThumbCustomColorChange() {
      document.getElementById('set-thumb-color-preset').value = 'custom';
      previewDefaultThumbnailSettings(false);
    }

    async function previewDefaultThumbnailSettings(randomColor = false) {
      const statusEl = document.getElementById('set-thumb-preview-status');
      const savedBadge = document.getElementById('set-thumb-saved-badge');
      if (statusEl) statusEl.textContent = '🎨 正在合成 1280×720 預設縮圖預覽...';
      if (savedBadge) {
        savedBadge.textContent = '● 預覽中 (尚未儲存)';
        savedBadge.style.background = 'rgba(245, 158, 11, 0.18)';
        savedBadge.style.color = '#fbbf24';
        savedBadge.style.borderColor = '#d97706';
      }
      try {
        const cfg = collectDefaultThumbnailSettingsFromUI();
        const isRandom = randomColor || cfg.color_preset === 'random';
        const payload = Object.assign({}, cfg, {
          random_color: isRandom,
          top_kicker: cfg.default_top_kicker || '硬核科技實驗室',
        });
        const data = await apiJson('/api/settings/thumbnail-preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });



        const prevImg = document.getElementById('set-thumb-preview-img');
        if (prevImg && data.thumbnail_url) {
          prevImg.src = data.thumbnail_url;
        }
        const tc = data.config || {};
        if (tc.primary_color && document.getElementById('set-thumb-primary-color')) {
          document.getElementById('set-thumb-primary-color').value = tc.primary_color;
        }
        const cBadge = document.getElementById('set-thumb-contrast-badge');
        if (cBadge && tc.contrast_ratio !== undefined) {
          cBadge.style.display = 'inline-block';
          const passTxt = tc.contrast_is_enough ? '對比充足 ✓' : '對比偏低 ⚠';
          cBadge.textContent = `對比度: ${tc.contrast_ratio}:1 (${passTxt})`;
          cBadge.style.background = tc.contrast_is_enough ? '#059669' : '#d97706';
        }
        if (statusEl) {
          statusEl.textContent = `✓ 預覽已更新！(對比度 ${tc.contrast_ratio || '--'}:1 ${tc.contrast_palette_name ? '• ' + tc.contrast_palette_name : ''})`;
        }
      } catch (e) {
        if (statusEl) statusEl.textContent = '預覽失敗: ' + e.message;
      }
    }

    async function saveDefaultThumbnailSettings() {
      try {
        const cfg = collectDefaultThumbnailSettingsFromUI();
        await apiRequest('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            settings: {
              thumbnail: cfg
            }
          }),
        })

        updateDefaultThumbSummaryBanner(cfg);
        await previewDefaultThumbnailSettings(false);
        const savedBadge = document.getElementById('set-thumb-saved-badge');
        if (savedBadge) {
          savedBadge.textContent = '✓ 已儲存至 settings.yaml';
          savedBadge.style.background = 'rgba(16, 185, 129, 0.18)';
          savedBadge.style.color = '#34d399';
          savedBadge.style.borderColor = '#059669';
        }
        if (typeof showToast === 'function') {
          showToast('🖼️ 已成功儲存全站預設 YouTube 縮圖設定！');
        } else {
          alert('已成功儲存全站預設 YouTube 縮圖設定！');
        }
      } catch (e) {
        alert('儲存預設縮圖設定失敗: ' + e.message);
      }
    }

    async function resetDefaultThumbnailSettings() {
      const factoryDefaults = {
        template: 'editorial_chill',
        color_preset: 'random',
        primary_color: '#00E626',
        secondary_color: '#FFFFFF',
        kicker_color: '#00E626',
        font_family: 'jf-openhuninn-2.1',
        font_weight: 'bold',
        bg_source: 'auto',
        subject_overlap: true,
        overlap_strength: 0.78,
        title_scale: 1.0,
        darken: 0.20,
        grain: 0.032,
        show_avatar_badge: true,
        use_llm_copy: true,
        default_top_kicker: '',
      };
      populateDefaultThumbnailSettingsUI(factoryDefaults);
      await saveDefaultThumbnailSettings();
    }

    async function applyGlobalDefaultToStudio() {
      try {
        const data = await apiJson('/api/settings/thumbnail-defaults');

        const cfg = data.config || {};
        if (document.getElementById('ts-template')) document.getElementById('ts-template').value = cfg.template || 'editorial_chill';
        if (document.getElementById('ts-color-preset')) document.getElementById('ts-color-preset').value = cfg.color_preset || 'random';
        if (document.getElementById('ts-primary-color') && cfg.primary_color && cfg.primary_color !== 'random') {
          document.getElementById('ts-primary-color').value = cfg.primary_color;
        }
        if (document.getElementById('ts-font-family')) document.getElementById('ts-font-family').value = cfg.font_family || 'jf-openhuninn-2.1';
        if (document.getElementById('ts-font-weight')) document.getElementById('ts-font-weight').value = cfg.font_weight || 'bold';
        if (document.getElementById('ts-bg-source') && cfg.bg_source) document.getElementById('ts-bg-source').value = cfg.bg_source;
        if (document.getElementById('ts-subject-overlap')) document.getElementById('ts-subject-overlap').checked = cfg.subject_overlap !== false;
        const scaleVal = cfg.title_scale !== undefined ? cfg.title_scale : 1.0;
        if (document.getElementById('ts-title-scale')) document.getElementById('ts-title-scale').value = scaleVal;
        if (document.getElementById('ts-scale-val')) document.getElementById('ts-scale-val').textContent = Math.round(scaleVal * 100) + '%';
        const darkenVal = cfg.darken !== undefined ? cfg.darken : 0.20;
        if (document.getElementById('ts-darken')) document.getElementById('ts-darken').value = darkenVal;
        if (document.getElementById('ts-darken-val')) document.getElementById('ts-darken-val').textContent = Math.round(darkenVal * 100) + '%';
        if (cfg.default_top_kicker && document.getElementById('ts-top-kicker')) {
          document.getElementById('ts-top-kicker').value = cfg.default_top_kicker;
        }
        await renderCustomThumbnail(false, cfg.color_preset === 'random');
        if (typeof showToast === 'function') showToast('📥 已套用全站預設縮圖風格！');
      } catch (e) {
        alert('載入全站預設縮圖設定失敗: ' + e.message);
      }
    }

    async function saveStudioStyleAsGlobalDefault() {
      try {
        const presetVal = document.getElementById('ts-color-preset').value;
        const primaryColorVal = document.getElementById('ts-primary-color').value;
        const cfg = {
          template: document.getElementById('ts-template').value,
          color_preset: presetVal || 'random',
          primary_color: THUMB_COLOR_MAP[presetVal] || primaryColorVal,
          secondary_color: presetVal === 'custom' ? primaryColorVal : '#FFFFFF',
          kicker_color: THUMB_COLOR_MAP[presetVal] || primaryColorVal,
          font_family: document.getElementById('ts-font-family') ? document.getElementById('ts-font-family').value : 'jf-openhuninn-2.1',
          font_weight: document.getElementById('ts-font-weight') ? document.getElementById('ts-font-weight').value : 'bold',
          bg_source: ['auto', 'matte_black'].includes(document.getElementById('ts-bg-source').value) ? document.getElementById('ts-bg-source').value : 'auto',
          subject_overlap: document.getElementById('ts-subject-overlap').checked,
          title_scale: parseFloat(document.getElementById('ts-title-scale').value || '1.0'),
          darken: parseFloat(document.getElementById('ts-darken').value || '0.20'),
        };
        await apiRequest('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ settings: { thumbnail: cfg } }),
        });
        populateDefaultThumbnailSettingsUI(cfg);
        if (typeof showToast === 'function') {
          showToast('📌 已將目前縮圖版型與風格設為全站預設！');
        } else {
          alert('已將目前縮圖版型與風格設為全站預設！');
        }
      } catch (e) {
        alert('設為預設失敗: ' + e.message);
      }
    }


    function updateContrastBadge(ratio, isEnough, rating, name) {
      const badge = document.getElementById('ts-contrast-badge');
      if (!badge) return;
      if (ratio !== undefined && ratio !== null) {
        badge.style.display = 'inline-block';
        const passText = isEnough ? '對比充足 ✓' : '對比偏低 ⚠';
        badge.textContent = `對比度: ${ratio}:1 (${passText})`;
        badge.style.background = isEnough ? '#059669' : '#d97706';
        badge.title = `WCAG評級: ${rating || 'AA'} | 背景對比檢測: ${name || ''}`;
      } else {
        badge.style.display = 'none';
      }
    }

    function onThumbnailColorPresetChange() {
      const preset = document.getElementById('ts-color-preset').value;
      if (preset === 'random') {
        randomizeThumbnailColor();
        return;
      }
      if (preset === 'custom') {
        renderCustomThumbnail(false, false);
        return;
      }
      if (THUMB_COLOR_MAP[preset]) {
        document.getElementById('ts-primary-color').value = THUMB_COLOR_MAP[preset];
      }
      renderCustomThumbnail(false, false);
    }

    function onCustomColorChange() {
      document.getElementById('ts-color-preset').value = 'custom';
      renderCustomThumbnail(false, false);
    }

    async function randomizeThumbnailColor() {
      document.getElementById('ts-color-preset').value = 'random';
      await renderCustomThumbnail(false, true);
    }

    async function openThumbnailStudioModal(targetPid) {
      let pid = targetPid;
      if (!pid) {
        const previewTab = document.getElementById('tab-preview');
        const pSel = document.getElementById('preview-project-select');
        if (previewTab && previewTab.classList.contains('active') && pSel && pSel.value) {
          pid = pSel.value;
        }
      }
      if (!pid) pid = currentProjectId;
      if (!pid) {
        alert("請先選擇一個專案 (Please select a project first).");
        return;
      }
      if (pid !== currentProjectId && typeof selectProject === 'function') {
        selectProject(pid);
      }
      const modal = document.getElementById('thumbnail-studio-modal');
      modal.style.display = 'flex';
      document.getElementById('ts-render-status').textContent = '載入縮圖中...';

      try {
        const data = await apiJson(`/api/projects/${currentProjectId}/thumbnail`);

        const cfg = data.config || {};

        // Populate background selector
        const bgSel = document.getElementById('ts-bg-source');
        bgSel.innerHTML = `<option value="auto">✨ 自動最佳場景 (Scene 1)</option><option value="matte_black">⚫ 極致黑潮霧面底圖 (Matte Black Backdrop)</option>`;
        if (data.has_custom_bg) {
          bgSel.innerHTML += `<option value="custom">📸 已上傳的自訂底圖 (Custom Uploaded Photo)</option>`;
        }
        (data.scenes || []).forEach(sc => {
          bgSel.innerHTML += `<option value="scene_${sc.scene_id}">${sc.label}</option>`;
        });
        if (cfg.bg_source) bgSel.value = cfg.bg_source;

        document.getElementById('ts-template').value = cfg.template || 'editorial_chill';
        document.getElementById('ts-color-preset').value = cfg.color_preset || 'random';
        if (document.getElementById('ts-font-family') && cfg.font_family) {
          document.getElementById('ts-font-family').value = cfg.font_family;
        }
        if (document.getElementById('ts-font-weight')) {
          document.getElementById('ts-font-weight').value = cfg.font_weight || 'bold';
        }
        if (cfg.primary_color) {
          document.getElementById('ts-primary-color').value = cfg.primary_color;
        }
        if (cfg.contrast_ratio !== undefined) {
          updateContrastBadge(cfg.contrast_ratio, cfg.contrast_is_enough, cfg.contrast_rating, cfg.contrast_palette_name);
        }
        if (cfg.clear_text) {
          document.getElementById('ts-top-kicker').value = '';
          document.getElementById('ts-main-title').value = '';
          document.getElementById('ts-left-1').value = '';
          document.getElementById('ts-left-2').value = '';
          document.getElementById('ts-right-1').value = '';
          document.getElementById('ts-right-2').value = '';
          document.getElementById('ts-duration-badge').value = '';
        } else {
          document.getElementById('ts-top-kicker').value = cfg.top_kicker || '';
          document.getElementById('ts-main-title').value = cfg.main_title || '';
          document.getElementById('ts-left-1').value = cfg.left_line1 || '';
          document.getElementById('ts-left-2').value = cfg.left_line2 || '';
          document.getElementById('ts-right-1').value = cfg.right_line1 || '';
          document.getElementById('ts-right-2').value = cfg.right_line2 || '';
          document.getElementById('ts-duration-badge').value = cfg.duration_badge || '';
        }
        document.getElementById('ts-subject-overlap').checked = cfg.subject_overlap !== false;

        const leftCastEl = document.getElementById('ts-left-cast');
        const rightCastEl = document.getElementById('ts-right-cast');
        if (leftCastEl) {
          leftCastEl.value = cfg.left_lines ? (Array.isArray(cfg.left_lines) ? cfg.left_lines.join('\n') : cfg.left_lines) : '';
        }
        if (rightCastEl) {
          rightCastEl.value = cfg.right_lines ? (Array.isArray(cfg.right_lines) ? cfg.right_lines.join('\n') : cfg.right_lines) : '';
        }
        const castDiv = document.getElementById('ts-cast-inputs');
        const stdDiv = document.getElementById('ts-standard-inputs');
        if (cfg.template === 'cinematic_cast') {
          if (castDiv) castDiv.style.display = 'block';
          if (stdDiv) stdDiv.style.display = 'none';
        } else {
          if (castDiv) castDiv.style.display = 'none';
          if (stdDiv) stdDiv.style.display = 'block';
        }

        const scaleVal = cfg.title_scale || 1.0;
        document.getElementById('ts-title-scale').value = scaleVal;
        document.getElementById('ts-scale-val').textContent = Math.round(scaleVal * 100) + '%';

        const darkenVal = cfg.darken !== undefined ? cfg.darken : 0.20;
        document.getElementById('ts-darken').value = darkenVal;
        document.getElementById('ts-darken-val').textContent = Math.round(darkenVal * 100) + '%';

        const prevImg = document.getElementById('ts-preview-img');
        prevImg.src = data.thumbnail_url;
        document.getElementById('btn-ts-download').href = data.thumbnail_url;
        document.getElementById('ts-render-status').textContent = cfg.clear_text ? '✓ 已載入 1280×720 縮圖 (純底圖無文字)' : '✓ 已載入 1280×720 縮圖';
      } catch (e) {
        document.getElementById('ts-render-status').textContent = '載入失敗: ' + e.message;
      }
    }

    function closeThumbnailStudioModal() {
      const modal = document.getElementById('thumbnail-studio-modal');
      if (modal) modal.style.display = 'none';
    }

    async function autoGenerateThumbnailCopy() {
      if (!currentProjectId) return;
      const btn = document.getElementById('btn-ts-ai-copy');
      const oldTxt = btn.textContent;
      btn.textContent = '⏳ AI 撰寫繁中文案中...';
      btn.disabled = true;
      try {
        const d = await apiJson(`/api/projects/${currentProjectId}/thumbnail/auto-copy`, { method: 'POST' });

        if (d.copy) {
          document.getElementById('ts-top-kicker').value = d.copy.top_kicker || '';
          document.getElementById('ts-main-title').value = d.copy.main_title || '';
          document.getElementById('ts-left-1').value = d.copy.left_line1 || '';
          document.getElementById('ts-left-2').value = d.copy.left_line2 || '';
          document.getElementById('ts-right-1').value = d.copy.right_line1 || '';
          document.getElementById('ts-right-2').value = d.copy.right_line2 || '';
          await renderCustomThumbnail(false);
        }
      } catch (e) {
        alert("AI 縮圖文案生成失敗: " + e.message);
      } finally {
        btn.textContent = oldTxt;
        btn.disabled = false;
      }
    }

    async function clearAllThumbnailText() {
      const ids = [
        'ts-top-kicker',
        'ts-main-title',
        'ts-left-1',
        'ts-left-2',
        'ts-right-1',
        'ts-right-2',
        'ts-duration-badge',
        'ts-left-cast',
        'ts-right-cast'
      ];
      ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
      });
      // If a custom image is chosen, also reset darken to 0% so the custom image is completely clean
      const bgSel = document.getElementById('ts-bg-source');
      if (bgSel && bgSel.value === 'custom') {
        const darkenEl = document.getElementById('ts-darken');
        if (darkenEl) {
          darkenEl.value = '0.0';
          const darkenValEl = document.getElementById('ts-darken-val');
          if (darkenValEl) darkenValEl.textContent = '0%';
        }
      }
      await renderCustomThumbnail(false, false, true);
    }

    async function uploadCustomThumbnailBg(inputEl) {
      if (!currentProjectId || !inputEl.files || !inputEl.files[0]) return;
      const statusEl = document.getElementById('ts-render-status');
      statusEl.textContent = '⏳ 上傳自訂底圖中...';
      const fd = new FormData();
      fd.append('file', inputEl.files[0]);
      try {
        await apiRequest(`/api/projects/${currentProjectId}/thumbnail/upload-bg`, {
          method: 'POST',
          body: fd,
        })

        const bgSel = document.getElementById('ts-bg-source');
        if (![...bgSel.options].some(o => o.value === 'custom')) {
          const opt = document.createElement('option');
          opt.value = 'custom';
          opt.textContent = '📸 已上傳的自訂底圖 (Custom Uploaded Photo)';
          bgSel.insertBefore(opt, bgSel.options[1]);
        }
        bgSel.value = 'custom';
        await renderCustomThumbnail(false);
      } catch (e) {
        statusEl.textContent = '上傳失敗: ' + e.message;
      }
    }

    function onThumbnailTemplateChange() {
      const tmpl = document.getElementById('ts-template').value;
      const castDiv = document.getElementById('ts-cast-inputs');
      const stdDiv = document.getElementById('ts-standard-inputs');
      if (tmpl === 'cinematic_cast') {
        if (castDiv) castDiv.style.display = 'block';
        if (stdDiv) stdDiv.style.display = 'none';
        const fontSel = document.getElementById('ts-font-family');
        if (fontSel && (fontSel.value === 'jf-openhuninn-2.1' || !fontSel.value)) {
          fontSel.value = 'genyo_min';
        }
        const colSel = document.getElementById('ts-color-preset');
        if (colSel && (colSel.value === 'random' || colSel.value === 'neon_green')) {
          colSel.value = 'cinema_vermilion';
          if (document.getElementById('ts-primary-color')) {
            document.getElementById('ts-primary-color').value = '#FF4215';
          }
        }
        const durEl = document.getElementById('ts-duration-badge');
        if (durEl && !durEl.value) {
          durEl.value = '1:37';
        }
      } else {
        if (castDiv) castDiv.style.display = 'none';
        if (stdDiv) stdDiv.style.display = 'block';
      }
      renderCustomThumbnail(false);
    }

    async function renderCustomThumbnail(autoCopy = false, randomColor = false, clearText = false) {
      if (!currentProjectId) return;
      const statusEl = document.getElementById('ts-render-status');
      statusEl.textContent = '🎨 正在合成 1280×720 繁體中文縮圖 (高對比檢測中)...';
      try {
        const presetVal = document.getElementById('ts-color-preset').value;
        const isRandom = randomColor || presetVal === 'random';
        const primaryColorVal = document.getElementById('ts-primary-color').value;

        const topKicker = document.getElementById('ts-top-kicker') ? document.getElementById('ts-top-kicker').value : '';
        const mainTitle = document.getElementById('ts-main-title') ? document.getElementById('ts-main-title').value : '';
        const left1 = document.getElementById('ts-left-1') ? document.getElementById('ts-left-1').value : '';
        const left2 = document.getElementById('ts-left-2') ? document.getElementById('ts-left-2').value : '';
        const right1 = document.getElementById('ts-right-1') ? document.getElementById('ts-right-1').value : '';
        const right2 = document.getElementById('ts-right-2') ? document.getElementById('ts-right-2').value : '';
        const leftCast = document.getElementById('ts-left-cast') ? document.getElementById('ts-left-cast').value : '';
        const rightCast = document.getElementById('ts-right-cast') ? document.getElementById('ts-right-cast').value : '';
        const isAllEmpty = !topKicker.trim() && !mainTitle.trim() && !left1.trim() && !left2.trim() && !right1.trim() && !right2.trim() && !leftCast.trim() && !rightCast.trim();
        const shouldClearText = !autoCopy && (clearText || isAllEmpty);

        const payload = {
          template: document.getElementById('ts-template').value,
          color_preset: isRandom ? 'random' : (presetVal || 'custom'),
          primary_color: isRandom ? null : primaryColorVal,
          secondary_color: isRandom ? null : (THUMB_COLOR_MAP[presetVal] ? null : primaryColorVal),
          kicker_color: isRandom ? null : (THUMB_COLOR_MAP[presetVal] ? null : primaryColorVal),
          random_color: isRandom,
          font_family: document.getElementById('ts-font-family') ? document.getElementById('ts-font-family').value : 'jf-openhuninn-2.1',
          font_weight: document.getElementById('ts-font-weight') ? document.getElementById('ts-font-weight').value : 'bold',
          top_kicker: shouldClearText ? '' : topKicker,
          main_title: shouldClearText ? '' : mainTitle,
          left_line1: shouldClearText ? '' : left1,
          left_line2: shouldClearText ? '' : left2,
          right_line1: shouldClearText ? '' : right1,
          right_line2: shouldClearText ? '' : right2,
          bg_source: document.getElementById('ts-bg-source').value,
          subject_overlap: document.getElementById('ts-subject-overlap').checked,
          title_scale: parseFloat(document.getElementById('ts-title-scale').value || '1.0'),
          darken: parseFloat(document.getElementById('ts-darken').value || '0.20'),
          duration_badge: shouldClearText ? '' : (document.getElementById('ts-duration-badge') ? document.getElementById('ts-duration-badge').value : ''),
          left_lines: shouldClearText ? '' : leftCast,
          right_lines: shouldClearText ? '' : rightCast,
          auto_copy: autoCopy,
          clear_text: shouldClearText,
        };
        const data = await apiJson(`/api/projects/${currentProjectId}/thumbnail/render`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });



        document.getElementById('ts-preview-img').src = data.thumbnail_url;
        document.getElementById('btn-ts-download').href = data.thumbnail_url;

        const tc = data.config || {};
        if (tc.color_preset) {
          document.getElementById('ts-color-preset').value = tc.color_preset;
        }
        if (tc.primary_color) {
          document.getElementById('ts-primary-color').value = tc.primary_color;
        }
        if (tc.font_weight && document.getElementById('ts-font-weight')) {
          document.getElementById('ts-font-weight').value = tc.font_weight;
        }
        if (tc.contrast_ratio !== undefined) {
          updateContrastBadge(tc.contrast_ratio, tc.contrast_is_enough, tc.contrast_rating, tc.contrast_palette_name);
        }
        if (shouldClearText) {
          statusEl.textContent = '✓ 已清空所有文字，縮圖更新為純底圖！';
        } else {
          statusEl.textContent = `✓ 縮圖已更新！(對比度 ${tc.contrast_ratio || '--'}:1 ${tc.contrast_palette_name ? '• ' + tc.contrast_palette_name : ''})`;
        }

        // Also update the YouTube Upload Modal preview if open
        const ytPrev = document.getElementById('yt-modal-thumb-preview');
        if (ytPrev) {
          ytPrev.style.display = 'block';
          ytPrev.src = data.thumbnail_url;
        }
        if (currentYouTubeMetadata && data.thumbnail_path) {
          currentYouTubeMetadata.thumbnail_path = data.thumbnail_path;
        }
        const thumbCopySummary = document.getElementById('yt-modal-thumb-copy-summary');
        if (thumbCopySummary) {
          if (tc.clear_text || (!tc.main_title && !tc.top_kicker)) {
            thumbCopySummary.innerHTML = `
              <div><b style="color:#4ade80;">純底圖無文字縮圖</b> (已清空文字疊加，保留純底圖設計)</div>
            `;
          } else {
            thumbCopySummary.innerHTML = `
              <div><b style="color:#4ade80;">主標題：</b>${tc.main_title || ''} &nbsp;|&nbsp; <b style="color:#93c5fd;">頂部小標：</b>${tc.top_kicker || ''}</div>
              <div style="color:#94a3b8; font-size:11px; margin-top:3px;">
                左側：${tc.left_line1 || ''} / ${tc.left_line2 || ''}<br>
                右側：${tc.right_line1 || ''} / ${tc.right_line2 || ''}
              </div>
            `;
          }
        }
      } catch (e) {
        statusEl.textContent = '合成失敗: ' + e.message;
      }
    }

    function closeYouTubeUploadModal() {
      const modal = document.getElementById('youtube-upload-modal');
      if (modal) modal.style.display = 'none';
      if (ytUploadPollTimer) {
        clearInterval(ytUploadPollTimer);
        ytUploadPollTimer = null;
      }
      if (ytAuthPollTimer) {
        clearInterval(ytAuthPollTimer);
        ytAuthPollTimer = null;
      }
      if (currentProjectId) {
        loadProjectDetails(currentProjectId);
      }
    }

    function updateTitleCounter() {
      const titleInput = document.getElementById('yt-modal-title');
      const counter = document.getElementById('yt-title-counter');
      if (titleInput && counter) {
        counter.textContent = `${titleInput.value.length} / 100`;
      }
    }

    async function rebuildYouTubeMetadata() {
      if (!currentProjectId) return;
      try {
        const meta = await apiJson(`/api/projects/${currentProjectId}/youtube_metadata`);

        currentYouTubeMetadata = meta;
        document.getElementById('yt-modal-description').value = meta.description || '';
        document.getElementById('yt-modal-tags').value = (meta.tags || []).join(', ');
      } catch (e) {
        alert("Failed to rebuild metadata: " + e.message);
      }
    }

    let currentAuthUrl = '';

    async function startYouTubeOAuth() {
      const msgEl = document.getElementById('yt-auth-status-msg');
      const modalMsg = document.getElementById('yt-modal-auth-msg');
      const promptText = "⏳ Generating Google Sign-in link for @tsao36...";
      if (msgEl) msgEl.textContent = promptText;
      if (modalMsg) modalMsg.textContent = promptText;

      try {
        const d = await apiJson('/api/youtube/auth', { method: 'POST' });

        if (d.status === 'error') {
          if (msgEl) msgEl.textContent = "Error: " + d.message;
          if (modalMsg) modalMsg.textContent = "Error: " + d.message;
          return alert(d.message);
        }

        if (d.auth_url) {
          currentAuthUrl = d.auth_url;

          // Update links in both Settings tab and Modal
          const linkSettings = document.getElementById('btn-open-google-auth-link');
          if (linkSettings) linkSettings.href = d.auth_url;
          const linkModal = document.getElementById('btn-modal-open-google');
          if (linkModal) linkModal.href = d.auth_url;

          // Reveal active auth guidance boxes
          const boxSettings = document.getElementById('yt-active-auth-box');
          if (boxSettings) boxSettings.style.display = 'block';
          const boxModal = document.getElementById('yt-modal-active-auth-box');
          if (boxModal) boxModal.style.display = 'block';

          if (msgEl) msgEl.textContent = "Sign-in window opened. Complete authorization in browser.";
          if (modalMsg) modalMsg.textContent = "Sign-in window opened. Complete authorization in browser.";

          // Open browser window directly from user's interactive session
          try {
            window.open(d.auth_url, '_blank');
          } catch (e) {
            console.log("Browser popup prevented; button is visible to click manually:", e);
          }
        }

        // Poll for authorization completion
        if (ytAuthPollTimer) clearInterval(ytAuthPollTimer);
        ytAuthPollTimer = setInterval(async () => {
          const st = await loadYouTubeStatus();
          if (st && st.is_authenticated) {
            clearInterval(ytAuthPollTimer);
            ytAuthPollTimer = null;
            if (msgEl) msgEl.textContent = "✓ Connected to " + (st.channel ? st.channel.handle : '@tsao36');
            if (modalMsg) modalMsg.textContent = "✓ Channel connected!";
            const boxSettings = document.getElementById('yt-active-auth-box');
            if (boxSettings) boxSettings.style.display = 'none';
            const boxModal = document.getElementById('yt-modal-active-auth-box');
            if (boxModal) boxModal.style.display = 'none';
            alert("YouTube channel @tsao36 connected successfully!");
            const modal = document.getElementById('youtube-upload-modal');
            if (modal && modal.style.display === 'flex') {
              openYouTubeUploadModal();
            }
          }
        }, 2000);
      } catch (e) {
        alert("Failed to start OAuth flow: " + e.message);
      }
    }

    function copyAuthUrl() {
      if (!currentAuthUrl) return alert("No active authorization URL available yet.");
      navigator.clipboard.writeText(currentAuthUrl).then(() => {
        alert("Google Sign-In URL copied to clipboard! You can paste it into any browser tab.");
      }).catch(() => {
        prompt("Copy Google Sign-In URL:", currentAuthUrl);
      });
    }

    async function submitManualAuthCode() {
      const codeInput = document.getElementById('yt-manual-code-input');
      const val = codeInput ? codeInput.value.trim() : '';
      if (!val) return alert("Please paste the redirected URL or code from the browser address bar.");
      await sendAuthCode(val);
    }

    async function submitModalManualCode() {
      const codeInput = document.getElementById('yt-modal-manual-code');
      const val = codeInput ? codeInput.value.trim() : '';
      if (!val) return alert("Please paste the redirected URL or code from the browser address bar.");
      await sendAuthCode(val);
    }

    async function sendAuthCode(val) {
      try {
        const d = await apiJson('/api/youtube/code', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: val }),
        });


        if (ytAuthPollTimer) {
          clearInterval(ytAuthPollTimer);
          ytAuthPollTimer = null;
        }
        alert("YouTube channel @tsao36 connected successfully!");
        const boxSettings = document.getElementById('yt-active-auth-box');
        if (boxSettings) boxSettings.style.display = 'none';
        const boxModal = document.getElementById('yt-modal-active-auth-box');
        if (boxModal) boxModal.style.display = 'none';
        await loadYouTubeStatus();
        const modal = document.getElementById('youtube-upload-modal');
        if (modal && modal.style.display === 'flex') {
          openYouTubeUploadModal();
        }
      } catch (e) {
        alert("Failed to connect with code: " + e.message);
      }
    }

    async function disconnectYouTubeAccount() {
      if (!confirm("Are you sure you want to disconnect this YouTube account?")) return;
      try {
        await apiRequest('/api/youtube/disconnect', { method: 'POST' });
        await loadYouTubeStatus();
        alert("YouTube account disconnected.");
      } catch (e) {
        alert("Failed to disconnect: " + e.message);
      }
    }

    async function handleClientSecretsFileUpload(event) {
      const file = event.target.files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append('file', file);

      try {
        const d = await apiJson('/api/youtube/credentials', {
          method: 'POST',
          body: formData,
        });


        alert("client_secrets.json uploaded successfully! Now click Sign In & Connect YouTube Channel.");
        loadYouTubeStatus();
      } catch (e) {
        alert("Error saving client_secrets.json: " + e.message);
      }
    }

    async function handleModalClientSecretsUpload(event) {
      const file = event.target.files[0];
      if (!file) return;
      const fnSpan = document.getElementById('yt-modal-secrets-filename');
      if (fnSpan) fnSpan.textContent = file.name;
      const formData = new FormData();
      formData.append('file', file);

      try {
        const d = await apiJson('/api/youtube/credentials', {
          method: 'POST',
          body: formData,
        });


        document.getElementById('yt-modal-secrets-status').innerHTML =
          '<span style="color:#34d399;">✓ client_secrets.json uploaded! Ready to authorize below.</span>';
        loadYouTubeStatus();
      } catch (e) {
        alert("Error saving client_secrets.json: " + e.message);
      }
    }

    function togglePasteSecretsArea() {
      const container = document.getElementById('yt-paste-secrets-container');
      if (container) {
        container.style.display = container.style.display === 'none' ? 'block' : 'none';
      }
    }

    async function savePastedClientSecrets() {
      const text = document.getElementById('yt-paste-secrets-text').value.trim();
      if (!text) return alert("Please paste valid JSON content.");
      try {
        const parsed = JSON.parse(text);
        const d = await apiJson('/api/youtube/credentials_json', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ credentials: parsed }),
        });


        alert("OAuth credentials saved successfully! Now click Sign In & Connect.");
        document.getElementById('yt-paste-secrets-container').style.display = 'none';
        loadYouTubeStatus();
      } catch (e) {
        alert("Invalid JSON or error: " + e.message);
      }
    }

    async function saveYouTubeSettings() {
      const privacy = document.getElementById('yt-settings-default-privacy').value;
      const cat = document.getElementById('yt-settings-default-category').value;
      try {
        await apiRequest('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            settings: {
              youtube: {
                default_privacy: privacy,
                default_category_id: cat,
              }
            }
          }),
        });
        alert("YouTube settings saved!");
      } catch (e) {
        alert("Failed to save settings: " + e.message);
      }
    }

    async function executeYouTubeUpload() {
      if (!currentProjectId) return;
      const title = document.getElementById('yt-modal-title').value.trim();
      const desc = document.getElementById('yt-modal-description').value.trim();
      const tagsRaw = document.getElementById('yt-modal-tags').value.trim();
      const privacy = document.getElementById('yt-modal-privacy').value;
      const cat = document.getElementById('yt-modal-category').value;
      const uploadThumb = document.getElementById('yt-modal-upload-thumb').checked;

      if (!title) return alert("Please provide a video title.");

      const tags = tagsRaw.split(',').map(t => t.trim()).filter(Boolean);

      // Switch to uploading view
      document.getElementById('yt-modal-ready-view').style.display = 'none';
      document.getElementById('yt-modal-uploading-view').style.display = 'block';
      document.getElementById('btn-modal-do-upload').style.display = 'none';

      // Reset progress bar
      document.getElementById('yt-upload-progress-bar').style.width = '0%';
      document.getElementById('yt-upload-progress-pct').textContent = '0%';
      document.getElementById('yt-upload-bytes-info').textContent = 'Starting upload stream...';

      try {
        const payload = {
          title: title,
          description: desc,
          tags: tags,
          privacy_status: privacy,
          category_id: cat,
          upload_thumbnail: uploadThumb,
          thumbnail_path: currentYouTubeMetadata ? currentYouTubeMetadata.thumbnail_path : null,
        };

        const d = await apiJson(`/api/projects/${currentProjectId}/youtube_upload`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });




        // Start polling upload status
        pollYouTubeUpload(currentProjectId);
      } catch (e) {
        document.getElementById('yt-modal-uploading-view').style.display = 'none';
        document.getElementById('yt-modal-error-view').style.display = 'block';
        document.getElementById('yt-modal-error-message').textContent = e.message;
      }
    }

    async function pollYouTubeUpload(pid) {
      if (ytUploadPollTimer) clearInterval(ytUploadPollTimer);

      ytUploadPollTimer = setInterval(async () => {
        try {
          const d = await apiJson(`/api/projects/${pid}/youtube_upload_status`);


          if (d.status === 'uploading') {
            const pct = d.progress_percent || 0;
            document.getElementById('yt-upload-progress-bar').style.width = `${pct}%`;
            document.getElementById('yt-upload-progress-pct').textContent = `${pct}%`;
            if (d.total_bytes && d.bytes_uploaded) {
              const upMB = (d.bytes_uploaded / (1024 * 1024)).toFixed(1);
              const totMB = (d.total_bytes / (1024 * 1024)).toFixed(1);
              document.getElementById('yt-upload-bytes-info').textContent =
                `Uploading: ${upMB} MB / ${totMB} MB (${pct}%)`;
            }
          } else if (d.status === 'completed') {
            clearInterval(ytUploadPollTimer);
            ytUploadPollTimer = null;
            document.getElementById('yt-modal-uploading-view').style.display = 'none';
            document.getElementById('yt-modal-complete-view').style.display = 'block';
            document.getElementById('yt-complete-url-display').textContent = d.video_url;
            document.getElementById('yt-modal-watch-btn').href = d.video_url;
            document.getElementById('yt-modal-studio-btn').href = `https://studio.youtube.com/video/${d.video_id}/edit`;

            // Update preview player tab
            const ytLink = document.getElementById('btn-yt-link');
            if (ytLink) {
              ytLink.style.display = 'inline-flex';
              ytLink.href = d.video_url;
            }
            const ytBtn = document.getElementById('btn-yt-upload');
            if (ytBtn && ytBtn.querySelector('span')) {
              ytBtn.querySelector('span').textContent = 'Re-upload to YouTube (@tsao36)';
            }
          } else if (d.status === 'failed') {
            clearInterval(ytUploadPollTimer);
            ytUploadPollTimer = null;
            document.getElementById('yt-modal-uploading-view').style.display = 'none';
            document.getElementById('yt-modal-error-view').style.display = 'block';
            document.getElementById('yt-modal-error-message').textContent = d.error || 'Upload failed.';
          }
        } catch (e) {
          console.error("Poll upload error:", e);
        }
      }, 1000);
    }

    function showModalReadyView() {
      document.getElementById('yt-modal-error-view').style.display = 'none';
      document.getElementById('yt-modal-ready-view').style.display = 'block';
      document.getElementById('btn-modal-do-upload').style.display = 'flex';
    }

    function copyYouTubeUrl() {
      const urlText = document.getElementById('yt-complete-url-display').textContent.trim();
      navigator.clipboard.writeText(urlText).then(() => {
        alert("YouTube URL copied to clipboard: " + urlText);
      }).catch(() => {
        prompt("Copy YouTube URL:", urlText);
      });
    }

    // ---------------- Global Toast Helper ----------------
    function showToast(msg) {
      let t = document.getElementById('global-toast');
      if (!t) {
        t = document.createElement('div');
        t.id = 'global-toast';
        t.style.cssText = 'position: fixed; bottom: 24px; right: 24px; background: #064e3b; border: 1px solid #10b981; color: #ecfdf5; padding: 10px 18px; border-radius: 8px; font-size: 13px; font-weight: 600; box-shadow: 0 8px 24px rgba(0,0,0,0.5); z-index: 99999; transition: opacity 0.3s ease; opacity: 0; pointer-events: none; max-width: 420px;';
        document.body.appendChild(t);
      }
      t.textContent = msg;
      t.style.opacity = '1';
      clearTimeout(t._timer);
      t._timer = setTimeout(() => {
        t.style.opacity = '0';
      }, 3500);
    }

    // ---------------- Online Trending Topics & Idea Queue ----------------
    let topicQueue = [];

    async function loadTopicQueue() {
      try {
        const data = await apiJson('/api/topics/queue');


        topicQueue = data.queue || [];
        renderTopicQueueDropdown();
      } catch (e) {
        console.error("Failed to load topic queue:", e);
      }
    }

    function renderTopicQueueDropdown(selectedId = null) {
      const select = document.getElementById('topic-queue-select');
      const badge = document.getElementById('topic-queue-count-badge');
      if (!select) return;

      if (badge) {
        badge.textContent = `${topicQueue.length} queued`;
      }

      if (topicQueue.length === 0) {
        select.innerHTML = '<option value="">(No researched topics yet — click "Research & Add Popular Topic" to fetch one)</option>';
        onSelectTopicQueue('');
        return;
      }

      let html = '<option value="">-- Choose a researched topic to view proof & apply --</option>';
      topicQueue.forEach((t, idx) => {
        const isAI = t.type === 'ai_technology' || (t.category && t.category.includes('AI'));
        const isHistory = t.type === 'dynasty_trivia';
        const typeIcon = isAI ? '🤖 ' : (isHistory ? '📜 ' : '🔥 ');
        const platform = (t.proof && t.proof.platform) ? `[${t.proof.platform}]` : '';
        const metrics = (t.proof && t.proof.metrics) ? `(${t.proof.metrics})` : '';
        const title = t.topic || 'Untitled Topic';
        html += `<option value="${t.id}">#${idx + 1}: ${typeIcon}${title} ${platform} ${metrics}</option>`;
      });
      select.innerHTML = html;

      // Select target ID or the first topic by default
      const targetId = selectedId || (topicQueue[0] ? topicQueue[0].id : '');
      if (targetId) {
        select.value = targetId;
        onSelectTopicQueue(targetId);
      } else {
        onSelectTopicQueue('');
      }
    }

    async function discoverPopularTopic(topicType = 'trend') {
      const isAI = topicType === 'ai' || topicType === 'ai_news' || topicType === 'ai_tech';
      const isHistory = topicType === 'history' || topicType === 'dynasty';

      let btnId = 'btn-discover-topic';
      let spinnerId = 'discover-spinner';
      let iconId = 'discover-icon';
      let textId = 'discover-text';
      let loadingMsg = '抓取即時熱搜話題中...';
      let defaultLabel = '時事科技熱搜';

      if (isAI) {
        btnId = 'btn-discover-ai';
        spinnerId = 'discover-ai-spinner';
        iconId = 'discover-ai-icon';
        textId = 'discover-ai-text';
        loadingMsg = '探索全球最新 AI 前沿突破中...';
        defaultLabel = '全球 AI 科技前沿';
      } else if (isHistory) {
        btnId = 'btn-discover-history';
        spinnerId = 'discover-history-spinner';
        iconId = 'discover-history-icon';
        textId = 'discover-history-text';
        loadingMsg = '考據朝代文獻與秘辛中...';
        defaultLabel = '朝代冷知識歷史';
      }

      const btn = document.getElementById(btnId);
      const spinner = document.getElementById(spinnerId);
      const icon = document.getElementById(iconId);
      const text = document.getElementById(textId);

      if (btn) btn.disabled = true;
      if (spinner) spinner.style.display = 'inline-block';
      if (icon) icon.style.display = 'none';
      if (text) text.textContent = loadingMsg;

      try {
        const data = await apiJson(`/api/topics/discover?type=${encodeURIComponent(topicType)}`, { method: 'POST' });


        topicQueue = data.queue || [];
        renderTopicQueueDropdown(data.topic ? data.topic.id : null);
        const iconEmoji = isAI ? '🤖' : (isHistory ? '📜' : '🔥');
        const labelText = isAI ? '全球 AI 科技前沿探索完成' : (isHistory ? '朝代冷知識題材探索完成' : '時事科技熱搜探索完成');
        showToast(`${iconEmoji} ${labelText}: "${(data.topic && data.topic.topic) || 'New Topic'}"`);
      } catch (e) {
        console.error("Error discovering topic:", e);
        alert(`Failed to discover topic: ` + e.message);
      } finally {
        if (btn) btn.disabled = false;
        if (spinner) spinner.style.display = 'none';
        if (icon) icon.style.display = 'inline-block';
        if (text) text.textContent = defaultLabel;
      }
    }

    function onSelectTopicQueue(topicId) {
      const card = document.getElementById('topic-proof-card');
      const btnApply = document.getElementById('btn-apply-topic');
      const btnDelete = document.getElementById('btn-delete-topic');

      if (!topicId) {
        if (card) card.style.display = 'none';
        if (btnApply) btnApply.disabled = true;
        if (btnDelete) btnDelete.disabled = true;
        return;
      }

      const item = topicQueue.find(t => t.id === topicId);
      if (!item) {
        if (card) card.style.display = 'none';
        if (btnApply) btnApply.disabled = true;
        if (btnDelete) btnDelete.disabled = true;
        return;
      }

      if (card) card.style.display = 'block';
      if (btnApply) btnApply.disabled = false;
      if (btnDelete) btnDelete.disabled = false;

      // Populate card fields
      const titleEl = document.getElementById('proof-topic-title');
      const catEl = document.getElementById('proof-category-badge');
      const durEl = document.getElementById('proof-rec-duration');
      const styleEl = document.getElementById('proof-rec-style');
      const loglineEl = document.getElementById('proof-logline');

      if (titleEl) titleEl.textContent = item.topic || '';
      if (catEl) {
        catEl.textContent = item.category || (item.type === 'ai_technology' ? '全球 AI 科技前沿' : (item.type === 'dynasty_trivia' ? '朝代歷史冷知識' : '時事焦點'));
        if (item.type === 'ai_technology' || (item.category && item.category.includes('AI'))) {
          catEl.style.background = 'linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)';
          catEl.style.color = '#ffffff';
        } else if (item.type === 'dynasty_trivia') {
          catEl.style.background = 'linear-gradient(135deg, #d97706 0%, #b45309 100%)';
          catEl.style.color = '#ffffff';
        } else {
          catEl.style.background = '';
          catEl.style.color = '';
        }
      }
      if (durEl) durEl.textContent = `${item.recommended_duration || 5} 分鐘`;
      if (styleEl) styleEl.textContent = item.recommended_style || 'cinematic_documentary';
      if (loglineEl) loglineEl.textContent = item.logline || '深入解構歷史脈絡與背後關鍵事實。';

      // Proof fields
      const p = item.proof || {};
      const platEl = document.getElementById('proof-platform');
      const metEl = document.getElementById('proof-metrics');
      const hlEl = document.getElementById('proof-headline');
      const urlEl = document.getElementById('proof-url');
      const whyEl = document.getElementById('proof-why');

      if (platEl) platEl.textContent = p.platform || (item.type === 'ai_technology' ? 'AI 頂會論文與科技發布' : (item.type === 'dynasty_trivia' ? '史料文獻考證' : 'Google Trends'));
      if (metEl) metEl.textContent = p.metrics || (item.type === 'ai_technology' ? '超越人類專家評測 / 全球頂級算力競逐' : (item.type === 'dynasty_trivia' ? '正史文獻權威記載 / 文史爆款話題' : '即時熱搜搜尋量持續上升'));
      if (hlEl) hlEl.textContent = p.headline ? `「${p.headline}」` : (item.type === 'ai_technology' ? '(前沿技術亮點)' : '(典籍記載焦點)');
      if (urlEl) {
        if (p.url) {
          urlEl.href = p.url;
          urlEl.textContent = p.url;
          urlEl.style.display = 'inline';
        } else {
          urlEl.style.display = 'none';
        }
      }
      if (whyEl) whyEl.textContent = p.why_popular || '顛覆大眾歷史常識與刻板印象，具備極高好奇心與傳播力。';
    }


    function applyQueuedTopicToCreator() {
      const select = document.getElementById('topic-queue-select');
      if (!select || !select.value) return;

      const item = topicQueue.find(t => t.id === select.value);
      if (!item) return;

      const topicInput = document.getElementById('topic');
      if (topicInput) {
        topicInput.value = item.topic;
        topicInput.focus();
        topicInput.style.transition = 'box-shadow 0.3s ease, border-color 0.3s ease';
        topicInput.style.borderColor = '#10b981';
        topicInput.style.boxShadow = '0 0 0 3px rgba(16, 185, 129, 0.4)';
        setTimeout(() => {
          topicInput.style.borderColor = '';
          topicInput.style.boxShadow = '';
        }, 1500);
      }

      if (item.recommended_duration) {
        const durSelect = document.getElementById('duration');
        if (durSelect) {
          const valStr = String(item.recommended_duration);
          for (let opt of durSelect.options) {
            if (opt.value === valStr) {
              durSelect.value = valStr;
              break;
            }
          }
        }
      }

      if (item.recommended_style) {
        const styleSelect = document.getElementById('visual-style');
        if (styleSelect) {
          for (let opt of styleSelect.options) {
            if (opt.value === item.recommended_style) {
              styleSelect.value = item.recommended_style;
              onCreatorStyleChange(item.recommended_style);
              break;
            }
          }
        }
      }

      // If custom research is empty, pre-import the verified proof dossier for maximum fact grounding
      const userResTa = document.getElementById('creator-user-research');
      if (userResTa && !userResTa.value.trim() && (item.proof || item.logline)) {
        importTrendProofToCreatorResearch();
      }

      showToast(`✓ Applied: "${item.topic}"`);
    }

    async function deleteSelectedQueuedTopic() {
      const select = document.getElementById('topic-queue-select');
      if (!select || !select.value) return;
      const topicId = select.value;

      try {
        const data = await apiJson(`/api/topics/queue/${encodeURIComponent(topicId)}`, { method: 'DELETE' });


        topicQueue = data.queue || [];
        renderTopicQueueDropdown();
        showToast("Topic removed from queue.");
      } catch (e) {
        console.error("Delete topic error:", e);
        alert("Failed to delete topic: " + e.message);
      }
    }

    async function clearTopicQueue() {
      if (!topicQueue || topicQueue.length === 0) {
        alert("Queue is already empty.");
        return;
      }
      if (!confirm("Are you sure you want to clear all topics from the queue?")) {
        return;
      }
      try {
        const data = await apiJson('/api/topics/queue', { method: 'DELETE' });


        topicQueue = data.queue || [];
        renderTopicQueueDropdown();
        showToast("Topic queue cleared.");
      } catch (e) {
        console.error("Clear queue error:", e);
        alert("Failed to clear queue: " + e.message);
      }
    }

    // Initialize application
    window.addEventListener('DOMContentLoaded', () => {
      loadStatus();
      loadVoices();
      loadMusicTracks();
      loadAvatars();
      loadImageModels();
      syncCloudVisualControls();
      loadProjectsList();
      loadYouTubeStatus();
      loadApiKeys();
      loadTopicQueue();
      loadDramaFormulas();
      loadCharactersLibrary();

      // Dynamic two-way listeners for Stage Model Selection
      const mProg = document.getElementById('music-progression-select');
      if (mProg) {
        mProg.addEventListener('change', () => {
          const stMusic = document.getElementById('model-stage-music');
          if (stMusic && stMusic.value !== mProg.value) {
            stMusic.value = mProg.value;
            onStageModelChange('music');
          }
        });
      }

      const stAnim = document.getElementById('model-stage-animation');
      if (stAnim) {
        stAnim.addEventListener('change', () => {
          onStageModelChange('animation');
        });
      }

      const stVoice = document.getElementById('model-stage-voice');
      if (stVoice) {
        stVoice.addEventListener('change', () => {
          onStageModelChange('voice');
        });
      }

      const stImg = document.getElementById('model-stage-images');
      if (stImg) {
        stImg.addEventListener('change', () => {
          onStageModelChange('images');
        });
      }

      const stRes = document.getElementById('model-stage-research');
      if (stRes) {
        stRes.addEventListener('change', () => {
          onStageModelChange('research');
        });
      }

      const calloutCreator = document.getElementById('creator-callout-style');
      if (calloutCreator) {
        calloutCreator.addEventListener('change', () => {
          const setCallout = document.getElementById('set-callout-banner-style');
          if (setCallout && setCallout.value !== calloutCreator.value) {
            setCallout.value = calloutCreator.value;
          }
        });
      }

      const calloutSettings = document.getElementById('set-callout-banner-style');
      if (calloutSettings) {
        calloutSettings.addEventListener('change', () => {
          const setCreator = document.getElementById('creator-callout-style');
          if (setCreator && setCreator.value !== calloutSettings.value) {
            setCreator.value = calloutSettings.value;
          }
        });
      }

      setTimeout(() => {
        onStageModelChange();
      }, 500);

      // Final confirmation modal handlers
      const confirmModalEl = document.getElementById('create-video-confirm-modal');
      if (confirmModalEl) {
        confirmModalEl.addEventListener('click', (e) => {
          if (e.target === confirmModalEl) {
            closeCreateVideoConfirmModal();
          }
        });
      }

      const btnOkConfirm = document.getElementById('btn-ok-create-confirm');
      if (btnOkConfirm) {
        btnOkConfirm.addEventListener('click', () => confirmAndProceedWithVideo());
      }
      const btnCancelConfirm = document.getElementById('btn-cancel-create-confirm');
      if (btnCancelConfirm) {
        btnCancelConfirm.addEventListener('click', () => closeCreateVideoConfirmModal());
      }
      const btnCloseConfirm = document.getElementById('btn-close-create-confirm');
      if (btnCloseConfirm) {
        btnCloseConfirm.addEventListener('click', () => closeCreateVideoConfirmModal());
      }

      window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          const m = document.getElementById('create-video-confirm-modal');
          if (m && m.style.display === 'flex') {
            closeCreateVideoConfirmModal();
          }
        }
      });
    });

    // ==================== OPENOPUS CLASSICAL MUSIC INTEGRATION ====================
    let currentOpenOpusComposers = [];
    let currentOpenOpusWorks = [];
    let selectedOpenOpusComposer = null;
    let selectedOpenOpusGenre = 'all';
    let studioTargetMovementIdx = null;

    function switchMusicSubTab(subTab) {
      const ambientBtn = document.getElementById('btn-music-subnav-ambient');
      const classicalBtn = document.getElementById('btn-music-subnav-classical');
      const ambientView = document.getElementById('music-subview-ambient');
      const classicalView = document.getElementById('music-subview-classical');

      if (subTab === 'classical') {
        if (ambientBtn) { ambientBtn.className = 'btn-sec'; ambientBtn.style.background = '#0b1120'; ambientBtn.style.color = '#94a3b8'; ambientBtn.style.borderColor = 'var(--border-muted)'; }
        if (classicalBtn) { classicalBtn.className = 'btn-sec active'; classicalBtn.style.background = '#1e3a8a'; classicalBtn.style.color = '#93c5fd'; classicalBtn.style.borderColor = '#3b82f6'; }
        if (ambientView) ambientView.style.display = 'none';
        if (classicalView) classicalView.style.display = 'block';
        if (!currentOpenOpusComposers.length) {
          loadOpenOpusComposers('popular');
        }
      } else {
        if (classicalBtn) { classicalBtn.className = 'btn-sec'; classicalBtn.style.background = '#0b1120'; classicalBtn.style.color = '#94a3b8'; classicalBtn.style.borderColor = 'var(--border-muted)'; }
        if (ambientBtn) { ambientBtn.className = 'btn-sec active'; ambientBtn.style.background = '#1e3a8a'; ambientBtn.style.color = '#93c5fd'; ambientBtn.style.borderColor = '#3b82f6'; }
        if (classicalView) classicalView.style.display = 'none';
        if (ambientView) ambientView.style.display = 'block';
      }
    }

    async function loadOpenOpusComposers(epoch = 'popular') {
      const grid = document.getElementById('openopus-composers-grid');
      if (grid) grid.innerHTML = '<div style="color: var(--text-muted); font-size: 13px; padding: 20px;">載入古典音樂大師名單中...</div>';
      try {
        const url = epoch && epoch !== 'all' && epoch !== 'popular'
          ? `/api/music/openopus/composers?epoch=${encodeURIComponent(epoch)}`
          : (epoch === 'all' ? `/api/music/openopus/composers?epoch=all` : `/api/music/openopus/composers`);
        const data = await apiJson(url);

        currentOpenOpusComposers = data.composers || [];
        renderOpenOpusComposersGrid(currentOpenOpusComposers);
      } catch (e) {
        if (grid) grid.innerHTML = `<div style="color: #ef4444; padding: 20px;">載入失敗: ${e.message}</div>`;
      }
    }

    function renderOpenOpusComposersGrid(composers) {
      const grid = document.getElementById('openopus-composers-grid');
      if (!grid) return;
      if (!composers.length) {
        grid.innerHTML = '<div style="color: var(--text-muted); padding: 30px; text-align: center; grid-column: 1 / -1;">未找到符合條件的作曲家。</div>';
        return;
      }
      let html = '';
      composers.forEach(c => {
        const portrait = c.portrait || 'https://assets.openopus.org/portraits/default.jpg';
        const birthYear = c.birth ? c.birth.split('-')[0] : '';
        const deathYear = c.death ? c.death.split('-')[0] : '';
        const eraStr = (birthYear && deathYear) ? `${birthYear} – ${deathYear}` : '';
        html += `
          <div onclick="selectOpenOpusComposer('${c.id}')" style="background: #080d16; border: 1px solid var(--card-border); border-radius: var(--radius); padding: 14px; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 12px;" onmouseover="this.style.borderColor='#3b82f6'; this.style.transform='translateY(-2px)';" onmouseout="this.style.borderColor='var(--card-border)'; this.style.transform='none';">
            <img src="${portrait}" alt="${c.name}" style="width: 52px; height: 52px; border-radius: 50%; object-fit: cover; border: 1.5px solid rgba(59,130,246,0.4);" onerror="this.src='https://assets.openopus.org/portraits/default.jpg'">
            <div style="flex: 1; overflow: hidden;">
              <div style="font-weight: 700; font-size: 14px; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${c.complete_name || c.name}</div>
              <div style="font-size: 11.5px; color: #94a3b8; margin-top: 2px;">${eraStr}</div>
              <span style="display: inline-block; font-size: 10px; background: rgba(59,130,246,0.15); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3); border-radius: 4px; padding: 1px 5px; margin-top: 4px;">${c.epoch || 'Classical'}</span>
            </div>
          </div>
        `;
      });
      grid.innerHTML = html;
    }

    function filterOpenOpusEpoch(epoch, btnEl) {
      document.querySelectorAll('.openopus-epoch-btn').forEach(b => {
        b.className = 'btn-sec openopus-epoch-btn';
        b.style.background = '#0b1120';
        b.style.color = '#94a3b8';
        b.style.borderColor = 'var(--card-border)';
      });
      if (btnEl) {
        btnEl.className = 'btn-sec openopus-epoch-btn active';
        btnEl.style.background = '#1e3a8a';
        btnEl.style.color = '#93c5fd';
        btnEl.style.borderColor = '#3b82f6';
      }
      backToOpenOpusComposers();
      loadOpenOpusComposers(epoch);
    }

    async function executeOpenOpusSearch() {
      const q = (document.getElementById('openopus-search-input').value || '').trim();
      if (!q) {
        loadOpenOpusComposers('popular');
        return;
      }
      const grid = document.getElementById('openopus-composers-grid');
      if (grid) grid.innerHTML = '<div style="color: var(--text-muted); font-size: 13px; padding: 20px;">搜尋作曲家及作品中...</div>';
      try {
        const data = await apiJson(`/api/music/openopus/composers/search?q=${encodeURIComponent(q)}`);

        currentOpenOpusComposers = data.composers || [];
        renderOpenOpusComposersGrid(currentOpenOpusComposers);
      } catch (e) {
        if (grid) grid.innerHTML = `<div style="color: #ef4444; padding: 20px;">搜尋失敗: ${e.message}</div>`;
      }
    }

    async function selectOpenOpusComposer(compId) {
      const comp = currentOpenOpusComposers.find(c => String(c.id) === String(compId));
      if (!comp) return;
      selectedOpenOpusComposer = comp;
      selectedOpenOpusGenre = 'all';

      document.getElementById('openopus-composers-container').style.display = 'none';
      const worksContainer = document.getElementById('openopus-works-container');
      worksContainer.style.display = 'block';

      document.getElementById('openopus-detail-avatar').src = comp.portrait || 'https://assets.openopus.org/portraits/default.jpg';
      document.getElementById('openopus-detail-name').innerText = comp.complete_name || comp.name;
      document.getElementById('openopus-detail-epoch').innerText = comp.epoch || 'Classical';
      const birthYear = comp.birth ? comp.birth.split('-')[0] : '';
      const deathYear = comp.death ? comp.death.split('-')[0] : '';
      document.getElementById('openopus-detail-lifespan').innerText = `生卒年：${birthYear} – ${deathYear}`;

      loadOpenOpusComposerWorks(comp.id, 'all');
    }

    function backToOpenOpusComposers() {
      document.getElementById('openopus-works-container').style.display = 'none';
      document.getElementById('openopus-composers-container').style.display = 'block';
    }

    async function loadOpenOpusComposerWorks(compId, genre = 'all') {
      const listEl = document.getElementById('openopus-works-list');
      if (listEl) listEl.innerHTML = '<div style="color: var(--text-muted); font-size: 13px; padding: 20px;">載入作品列表中...</div>';
      try {
        const url = (genre && genre !== 'all')
          ? `/api/music/openopus/works?composer_id=${compId}&genre=${encodeURIComponent(genre)}`
          : `/api/music/openopus/works?composer_id=${compId}`;
        const data = await apiJson(url);

        currentOpenOpusWorks = data.works || [];

        // Build Genre Filter Pills
        const genres = Array.from(new Set(currentOpenOpusWorks.map(w => w.genre).filter(Boolean)));
        renderOpenOpusGenrePills(genres, genre, compId);

        renderOpenOpusWorksList(currentOpenOpusWorks);
      } catch (e) {
        if (listEl) listEl.innerHTML = `<div style="color: #ef4444; padding: 20px;">載入作品失敗: ${e.message}</div>`;
      }
    }

    function renderOpenOpusGenrePills(genres, activeGenre, compId) {
      const container = document.getElementById('openopus-genre-pills');
      if (!container) return;
      let html = `
        <button class="btn-sec ${activeGenre === 'all' ? 'active' : ''}" onclick="loadOpenOpusComposerWorks('${compId}', 'all')" style="padding: 4px 10px; font-size: 11.5px; border-radius: 12px; ${activeGenre === 'all' ? 'background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6;' : 'background: #0b1120; color: #94a3b8;'}">
          全部體裁 (All)
        </button>
      `;
      genres.forEach(g => {
        const isActive = activeGenre === g;
        html += `
          <button class="btn-sec ${isActive ? 'active' : ''}" onclick="loadOpenOpusComposerWorks('${compId}', '${g}')" style="padding: 4px 10px; font-size: 11.5px; border-radius: 12px; ${isActive ? 'background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6;' : 'background: #0b1120; color: #94a3b8;'}">
            ${g}
          </button>
        `;
      });
      container.innerHTML = html;
    }

    function renderOpenOpusWorksList(works) {
      const listEl = document.getElementById('openopus-works-list');
      if (!listEl) return;
      if (!works.length) {
        listEl.innerHTML = '<div style="color: var(--text-muted); padding: 30px; text-align: center;">此作曲家在選取體裁下無作品記錄。</div>';
        return;
      }
      let html = '';
      works.forEach((w, idx) => {
        const compName = selectedOpenOpusComposer ? (selectedOpenOpusComposer.complete_name || selectedOpenOpusComposer.name) : 'Composer';
        const epoch = selectedOpenOpusComposer ? (selectedOpenOpusComposer.epoch || 'Classical') : 'Classical';

        // Check if track is already in local library
        const alreadyInLib = cachedMusicTracks.find(t => (t.composer === compName && t.work === w.title) || (t.openopus_id && String(t.openopus_id) === String(w.id)));

        html += `
          <div id="openopus-work-card-${w.id}" style="background: #080d16; border: 1px solid var(--card-border); padding: 14px 18px; border-radius: var(--radius); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
            <div style="flex: 1; min-width: 260px;">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <span style="font-weight: 700; font-size: 14.5px; color: #fff;">${w.title}</span>
                <span style="font-size: 11px; background: rgba(59,130,246,0.15); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3); border-radius: 4px; padding: 2px 6px;">${w.genre || 'Piece'}</span>
                ${w.recommended === '1' ? '<span style="font-size: 10.5px; background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); border-radius: 4px; padding: 2px 6px;">★ 推薦名曲</span>' : ''}
                ${w.popular === '1' ? '<span style="font-size: 10.5px; background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); border-radius: 4px; padding: 2px 6px;">🔥 經典常奏</span>' : ''}
              </div>
              ${w.subtitle ? `<div style="font-size: 12px; color: #94a3b8; margin-top: 3px;">${w.subtitle}</div>` : ''}
              <div id="openopus-work-status-${w.id}" style="font-size: 11.5px; color: #64748b; margin-top: 4px;">
                ${alreadyInLib ? `✅ 已收錄於本地曲庫 (${alreadyInLib.filename})` : '未下載音檔 (點擊一鍵解析公有領域錄音)'}
              </div>
            </div>

            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              ${alreadyInLib ? `
                <audio controls src="${alreadyInLib.url}" style="height: 32px; width: 200px;"></audio>
                <button class="btn-sec" onclick="applyMusicToActiveProject('${alreadyInLib.filename}')" style="padding: 6px 12px; font-size: 12px; font-weight: 600; color: #93c5fd; border-color: #2563eb;">
                  ✓ 設為專案配樂
                </button>
              ` : `
                <button id="btn-resolve-${w.id}" class="btn-primary" onclick="resolveAndImportOpenOpusWork('${w.id}', '${encodeURIComponent(compName)}', '${encodeURIComponent(w.title)}', '${encodeURIComponent(epoch)}', '${encodeURIComponent(w.genre || '')}')" style="padding: 6px 14px; font-size: 12px; font-weight: 700; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);">
                  ⚡ 一鍵解析公有領域錄音
                </button>
                <button class="btn-sec" onclick="uploadOpenOpusCustomAudio('${w.id}', '${encodeURIComponent(compName)}', '${encodeURIComponent(w.title)}', '${encodeURIComponent(epoch)}', '${encodeURIComponent(w.genre || '')}')" style="padding: 6px 10px; font-size: 12px;" title="自行上傳並綁定音檔至此作品">
                  📤 上傳
                </button>
              `}
            </div>
          </div>
        `;
      });
      listEl.innerHTML = html;
    }

    async function resolveAndImportOpenOpusWork(workId, encComp, encTitle, encEpoch, encGenre) {
      const compName = decodeURIComponent(encComp);
      const title = decodeURIComponent(encTitle);
      const epoch = decodeURIComponent(encEpoch);
      const genre = decodeURIComponent(encGenre);

      const statusEl = document.getElementById(`openopus-work-status-${workId}`);
      const btnEl = document.getElementById(`btn-resolve-${workId}`);
      if (btnEl) { btnEl.disabled = true; btnEl.innerText = '🔍 檢索錄音中...'; }
      if (statusEl) statusEl.innerHTML = '<span style="color: #60a5fa;">正在檢索 Internet Archive 與 Wikimedia Commons 公有領域音訊...</span>';

      try {
        const resolveData = await apiJson(`/api/music/openopus/resolve-audio?composer=${encodeURIComponent(compName)}&work=${encodeURIComponent(title)}`);

        const candidates = resolveData.candidates || [];

        if (!candidates.length) {
          if (statusEl) statusEl.innerHTML = '<span style="color: #f59e0b;">線上公有錄音未收錄，請點選「📤 上傳」自行上傳音檔綁定。</span>';
          if (btnEl) { btnEl.disabled = false; btnEl.innerText = '⚡ 一鍵解析公有領域錄音'; }
          return;
        }

        const best = candidates[0];
        if (btnEl) btnEl.innerText = '⬇️ 下載轉換中...';
        if (statusEl) statusEl.innerHTML = `<span style="color: #34d399;">已尋得錄音「${best.title}」，正在下載並規格化 MP3...</span>`;

        const importData = await apiJson('/api/music/openopus/import-work', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            composer: compName,
            work: title,
            audio_url: best.url,
            epoch: epoch,
            genre: genre,
            openopus_id: String(workId),
          })
        });



        const newTrack = importData.track;

        if (typeof showToast === 'function') showToast(`✓ 成功匯入古典名曲: ${newTrack.name}`);
        // Refresh local music cache
        await loadMusicTracks();
        renderOpenOpusWorksList(currentOpenOpusWorks);
      } catch (e) {
        if (statusEl) statusEl.innerHTML = `<span style="color: #ef4444;">匯入失敗: ${e.message}</span>`;
        if (btnEl) { btnEl.disabled = false; btnEl.innerText = '⚡ 重試解析錄音'; }
      }
    }

    function uploadOpenOpusCustomAudio(workId, encComp, encTitle, encEpoch, encGenre) {
      const compName = decodeURIComponent(encComp);
      const title = decodeURIComponent(encTitle);
      const epoch = decodeURIComponent(encEpoch);
      const genre = decodeURIComponent(encGenre);

      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'audio/*';
      input.onchange = async () => {
        if (!input.files || !input.files[0]) return;
        const file = input.files[0];
        const statusEl = document.getElementById(`openopus-work-status-${workId}`);
        if (statusEl) statusEl.innerHTML = `<span style="color: #60a5fa;">上傳並轉碼 ${file.name} 中...</span>`;

        const formData = new FormData();
        formData.append('file', file);
        formData.append('composer', compName);
        formData.append('work', title);
        formData.append('epoch', epoch);
        formData.append('genre', genre);
        formData.append('openopus_id', String(workId));

        try {
          await apiRequest('/api/music/openopus/upload-work', {
            method: 'POST',
            body: formData,
          })

          if (typeof showToast === 'function') showToast(`✓ 已成功綁定自選音檔至: ${title}`);
          await loadMusicTracks();
          renderOpenOpusWorksList(currentOpenOpusWorks);
        } catch (e) {
          if (statusEl) statusEl.innerHTML = `<span style="color: #ef4444;">上傳失敗: ${e.message}</span>`;
        }
      };
      input.click();
    }

    function onStudioMusicOffsetChange(segIdx, val) {
      const seg = updateMusicOffset(studioStageData, segIdx, val);
      if (!seg) return;
      if (typeof showToast === 'function') showToast(`✓ 已設定樂章 ${segIdx + 1} 起播偏移: ${seg.start_offset}s`);
    }

    function openStudioClassicalPicker(movementIdx) {
      studioTargetMovementIdx = movementIdx;
      // Switch to music tab & classical view
      switchTab('music');
      switchMusicSubTab('classical');
      if (typeof showToast === 'function') showToast(`🏛️ 請在古典名曲曲庫中選擇要指定至 Movement ${movementIdx + 1} 的曲目`);
    }


    // ==========================================
    // RETENTION HOOK MODULE (UI LOGIC)
    // ==========================================

    window.saveHookSettings = async function() {
      const btn = document.getElementById('btn-save-hook-settings');
      const statusEl = document.getElementById('save-hook-status');
      if (btn) btn.disabled = true;
      if (statusEl) statusEl.textContent = "儲存中...";

      try {
        const payload = {
          settings: {
            hook: {
              enabled: document.getElementById('set-hook-enabled')?.value === 'true',
              video_duration: parseFloat(document.getElementById('set-hook-video-dur')?.value || 300),
              duration: parseFloat(document.getElementById('set-hook-dur')?.value || 12),
              mode: document.getElementById('set-hook-mode')?.value || 'select_core_conflict',
              claim_window_seconds: parseFloat(document.getElementById('set-hook-claim-dur')?.value || 5.0),
              avoid_repeated_narration: document.getElementById('set-hook-avoid-repeat')?.value === 'true',
              ban_greetings: true,
              ban_logo_animation: true,
              ban_clickbait: true,
              include_in_total_duration: true
            }
          }
        };
        await apiRequest('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (statusEl) {
          statusEl.textContent = "✓ Hook 設定已成功儲存至 settings.yaml";
          setTimeout(() => { if (statusEl) statusEl.textContent = ""; }, 4000);
        }
        showToast("✓ Hook 模組預設設定已成功更新！");
      } catch (err) {
        console.error("Save hook settings error:", err);
        if (statusEl) statusEl.textContent = "❌ 儲存失敗: " + err.message;
      } finally {
        if (btn) btn.disabled = false;
      }
    };

    window.openHookStudioModal = async function() {
      const pid = currentProjectId;
      if (!pid) {
        showToast("請先選擇或開啟一個專案以檢視 Hook");
        return;
      }
      const modal = document.getElementById('hook-studio-modal');
      if (modal) modal.style.display = 'flex';
      await window.renderHookStudioModal();
    };

    window.closeHookStudioModal = function() {
      const modal = document.getElementById('hook-studio-modal');
      if (modal) modal.style.display = 'none';
    };

    window.renderHookStudioModal = async function() {
      const pid = currentProjectId;
      const body = document.getElementById('hook-modal-body');
      if (!body) return;
      body.innerHTML = '<div style="text-align:center; padding:30px; color:#94a3b8;">載入 Hook 結構資料與留存率比對中...</div>';

      try {
        const [hookData, versionsData, compData] = await Promise.all([
          apiJson(`/api/projects/${pid}/hook`).catch(() => null),
          apiJson(`/api/projects/${pid}/hook/versions`).catch(() => ({ active_version: 0, versions: [] })),
          apiJson(`/api/projects/${pid}/hook/compare`).catch(() => null)
        ]);

        const hasHook = hookData && hookData.transcript;
        const activeVer = versionsData.active_version || (hookData ? hookData.version : 1);
        const versions = versionsData.versions || [];

        const badge = document.getElementById('hook-modal-active-badge');
        if (badge) badge.textContent = `Active v${activeVer}`;

        let html = '';

        // 1. Controls Row (Version Selector & Regenerate)
        html += `
          <div style="background:#0c1527; border:1px solid #1e3a8a; border-radius:8px; padding:12px 16px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
            <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
              <span style="font-weight:700; color:#38bdf8; font-size:13px;">切換歷史版本 (Switch Version):</span>
              <select id="modal-hook-version-select" onchange="switchHookVersionInStudio(this.value)" style="background:#060a12; border:1px solid #0284c7; color:#fff; border-radius:6px; padding:6px 10px; font-size:12px; font-weight:700; cursor:pointer;">
                ${versions.length > 0 ? versions.map(v => `<option value="${v.version}" ${v.version === activeVer ? 'selected' : ''}>v${v.version} (${v.created_at || 'Take'}) - 30s留存: ${v.retention_metrics?.retention_rate_30s ? (v.retention_metrics.retention_rate_30s * 100).toFixed(1) + '%' : '未填寫'}</option>`).join('') : '<option value="1">v1 (當前版本)</option>'}
              </select>
            </div>
            <button onclick="generateNewHookVersionInStudio()" class="btn-primary" style="font-size:12px; font-weight:700; padding:7px 16px; background:linear-gradient(135deg, #0284c7 0%, #0369a1 100%);">
              🔄 重新選取衝突並生成新版本 (Generate New Take)
            </button>
          </div>
        `;

        if (hasHook) {
          const claim = hookData.transcript.core_claim_first_5s || '';
          const teaser = hookData.transcript.conflict_teaser_5_to_12s || '';
          const shots = hookData.shots || [];
          const dur = hookData.hook_duration || 12.0;
          const totalDur = hookData.total_video_duration || 300.0;
          const bodyDur = totalDur - dur;

          // 2. Structured Hook Shots Breakdown (0-5s and 5-12s)
          html += `
            <div style="background:rgba(15, 23, 42, 0.7); border:1px solid #1e293b; border-radius:8px; padding:16px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
                <div style="font-weight:800; color:#f8fafc; font-size:14px; display:flex; align-items:center; gap:6px;">
                  <span>📋 Hook 鏡頭與逐字稿規劃</span>
                </div>
                <div style="font-size:12px; color:#94a3b8; display:flex; gap:12px;">
                  <span>Hook: <b style="color:#38bdf8;">${dur}s</b></span>
                  <span>正片主體: <b style="color:#cbd5e1;">${bodyDur}s</b></span>
                  <span>總片長: <b style="color:#34d399;">${totalDur}s (不額外增加片長)</b></span>
                </div>
              </div>

              <!-- Shot 1: 0 - 5s -->
              <div style="background:#091122; border:1px solid rgba(56, 189, 248, 0.3); border-radius:6px; padding:12px 14px; margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                  <span style="font-size:12px; font-weight:800; color:#38bdf8;">🎯 Shot 1 (00:00 - 00:05) · 前 5 秒核心主張</span>
                  <span style="font-size:11px; color:#34d399; font-weight:600;">✓ 無寒暄 · 無Logo · 標題直接相符</span>
                </div>
                <div style="font-size:13.5px; color:#fff; font-weight:600; line-height:1.5; margin-bottom:6px;">
                  「${claim}」
                </div>
                <div style="font-size:11.5px; color:#94a3b8; line-height:1.4;">
                  <b>畫面規劃:</b> ${shots[0]?.visual_description || '開場主視覺鏡頭，快速推軌 (push_in)，無 Logo 動畫'}
                </div>
              </div>

              <!-- Shot 2: 5 - 12s -->
              <div style="background:#091122; border:1px solid rgba(245, 158, 11, 0.35); border-radius:6px; padding:12px 14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                  <span style="font-size:12px; font-weight:800; color:#fbbf24;">⚡ Shot 2 (00:05 - 00:12) · 核心衝突片段 (選自 Scene ${hookData.source_scene_id || '?'})</span>
                  <span style="font-size:11px; color:#34d399; font-weight:600;">✓ 旁白不重複 · 懸念承接</span>
                </div>
                <div style="font-size:13.5px; color:#fff; font-weight:600; line-height:1.5; margin-bottom:6px;">
                  「${teaser}」
                </div>
                <div style="font-size:11.5px; color:#94a3b8; line-height:1.4;">
                  <b>畫面規劃:</b> ${shots[1]?.visual_description || '核心衝突高張力畫面'}
                </div>
              </div>
            </div>
          `;

          // 3. 30-Second Audience Retention Tracker Section
          const currentRetention = hookData.retention_metrics?.retention_rate_30s;
          const currentPercent = currentRetention ? (currentRetention * 100).toFixed(1) : '';

          html += `
            <div style="background:linear-gradient(135deg, rgba(6, 78, 59, 0.35) 0%, rgba(15, 23, 42, 0.8) 100%); border:1px solid #059669; border-radius:8px; padding:16px;">
              <div style="font-weight:800; color:#34d399; font-size:14px; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                <span>📊 30 秒觀眾留存率填報 (30s Retention Rate)</span>
              </div>
              <div style="font-size:12px; color:#94a3b8; margin-bottom:12px;">
                影片發布後，可在此填寫 YouTube Analytics 的 30 秒觀眾留存率（%），系統將自動比對各版表現並推薦最能挽留觀眾的 Hook。
              </div>
              <div style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap;">
                <div>
                  <label style="font-size:11px; color:#cbd5e1; display:block; margin-bottom:4px;">實測 30 秒留存率 (%)</label>
                  <input type="number" id="input-modal-retention-rate" value="${currentPercent}" min="0" max="100" step="0.5" placeholder="例如 74.5" style="width:130px; padding:7px 10px; background:#060a12; border:1px solid #10b981; color:#fff; border-radius:6px; font-weight:700;">
                </div>
                <div style="flex:1; min-width:200px;">
                  <label style="font-size:11px; color:#cbd5e1; display:block; margin-bottom:4px;">留存分析備註 (Notes)</label>
                  <input type="text" id="input-modal-retention-notes" value="${hookData.retention_metrics?.notes || ''}" placeholder="例如：此版本開場地緣政治切入點觀眾停留更久" style="width:100%; box-sizing:border-box; padding:7px 10px; background:#060a12; border:1px solid #334155; color:#fff; border-radius:6px;">
                </div>
                <button onclick="saveHookRetentionRateInStudio(${activeVer})" class="btn-primary" style="padding:7px 18px; font-size:12px; font-weight:700; background:#059669; border-color:#10b981;">
                  💾 儲存留存數據
                </button>
              </div>
            </div>
          `;

          // 4. Multi-Take Comparison Table
          if (compData && compData.comparison && compData.comparison.length > 0) {
            html += `
              <div style="background:#080d1a; border:1px solid #1e293b; border-radius:8px; padding:16px;">
                <div style="font-weight:800; color:#f8fafc; font-size:14px; margin-bottom:10px;">
                  📈 各版本 30 秒觀眾留存率橫向比較 (Retention Comparison)
                </div>
                <table style="width:100%; border-collapse:collapse; font-size:12px; text-align:left;">
                  <thead>
                    <tr style="border-bottom:1px solid #334155; color:#94a3b8;">
                      <th style="padding:8px 6px;">版本</th>
                      <th style="padding:8px 6px;">5s 核心主張</th>
                      <th style="padding:8px 6px;">30s 留存率</th>
                      <th style="padding:8px 6px;">等級</th>
                      <th style="padding:8px 6px;">備註</th>
                      <th style="padding:8px 6px;">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${compData.comparison.map(c => `
                      <tr style="border-bottom:1px solid rgba(255,255,255,0.06); ${c.is_active ? 'background:rgba(2,132,199,0.12);' : ''}">
                        <td style="padding:8px 6px; font-weight:700; color:${c.is_active ? '#38bdf8' : '#fff'};">
                          v${c.version} ${c.is_active ? '<span style="font-size:10px; color:#38bdf8;">(作用中)</span>' : ''}
                        </td>
                        <td style="padding:8px 6px; color:#cbd5e1; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                          ${c.core_claim || '—'}
                        </td>
                        <td style="padding:8px 6px; font-weight:700; color:${c.retention_30s ? (c.retention_30s >= 0.75 ? '#34d399' : '#fbbf24') : '#94a3b8'};">
                          ${c.retention_30s_percent}
                        </td>
                        <td style="padding:8px 6px; color:#94a3b8;">
                          ${c.benchmark_tier}
                        </td>
                        <td style="padding:8px 6px; color:#cbd5e1; max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                          ${c.notes || '—'}
                        </td>
                        <td style="padding:8px 6px;">
                          ${!c.is_active ? `<button class="btn-sec" onclick="switchHookVersionInStudio(${c.version})" style="padding:3px 8px; font-size:11px;">切換</button>` : '✓'}
                        </td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
                ${compData.analysis ? `<div style="font-size:11.5px; color:#38bdf8; margin-top:10px; padding:8px 12px; background:rgba(2,132,199,0.1); border-radius:6px; border-left:3px solid #0284c7;">💡 <b>分析洞察:</b> ${compData.analysis}</div>` : ''}
              </div>
            `;
          }
        } else {
          html += `
            <div style="text-align:center; padding:40px 20px; color:#94a3b8;">
              <div style="font-size:32px; margin-bottom:10px;">🎯</div>
              <div style="font-size:15px; font-weight:700; color:#fff; margin-bottom:8px;">尚未生成 Hook</div>
              <div style="font-size:12px; max-width:440px; margin:0 auto 16px auto; line-height:1.5;">
                當專案完成 Stage 3 (Scenes) 場景規劃後，管線將自動選取核心衝突生成 Hook。您亦可直接點擊下方按鈕立即生成。
              </div>
              <button onclick="generateNewHookVersionInStudio()" class="btn-primary" style="padding:9px 22px; font-size:13px; font-weight:700;">
                🚀 立即生成 Hook
              </button>
            </div>
          `;
        }

        body.innerHTML = html;
      } catch (err) {
        console.error("renderHookStudioModal error:", err);
        body.innerHTML = `<div style="padding:30px; color:#f87171; text-align:center;">載入 Hook 失敗: ${err.message}</div>`;
      }
    };

    window.switchHookVersionInStudio = async function(versionNum) {
      const pid = currentProjectId;
      if (!pid) return;
      try {
        await apiRequest(`/api/projects/${pid}/hook/versions/switch/${versionNum}`, { method: 'POST' });
        showToast(`✓ 已切換至 Hook 版本 v${versionNum}`);
        await window.renderHookStudioModal();
      } catch (err) {
        showToast(`❌ 切換失敗: ${err.message}`);
      }
    };

    window.generateNewHookVersionInStudio = async function() {
      const pid = currentProjectId;
      if (!pid) return;
      try {
        showToast("⏳ 正在分析場景並生成新版本 Hook...");
        await apiRequest(`/api/projects/${pid}/hook/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode: 'select_core_conflict', duration: 12.0, video_duration: 300.0 })
        });
        showToast("✓ 新版本 Hook 生成成功！");
        await window.renderHookStudioModal();
      } catch (err) {
        showToast(`❌ 生成 Hook 失敗: ${err.message}`);
      }
    };

    window.saveHookRetentionRateInStudio = async function(versionNum) {
      const pid = currentProjectId;
      if (!pid) return;
      const rateInput = document.getElementById('input-modal-retention-rate');
      const notesInput = document.getElementById('input-modal-retention-notes');
      const val = parseFloat(rateInput?.value || 0);
      if (isNaN(val) || val < 0 || val > 100) {
        showToast("請輸入有效的留存率百分比 (0 到 100)");
        return;
      }
      try {
        await apiRequest(`/api/projects/${pid}/hook/versions/${versionNum}/retention`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            retention_30s: val / 100.0,
            notes: notesInput?.value || ""
          })
        });
        showToast(`✓ 已儲存版本 v${versionNum} 的 30 秒觀眾留存率: ${val}%`);
        await window.renderHookStudioModal();
      } catch (err) {
        showToast(`❌ 儲存留存率失敗: ${err.message}`);
      }
    };


    async function rejectAndReplaceSceneMedia(sceneId) {
      if (!currentProjectId) return alert("Please select or open a project first.");
      const reason = prompt(`請輸入排除 Scene #${sceneId} 目前素材的原因（例如：畫面與旁白無關、廣告/片頭雜訊、人物錯誤等）：`, "內容與旁白不符");
      if (reason === null) return;
      try {
        const res = await apiJson(`/api/projects/${currentProjectId}/scenes/${sceneId}/reject_media`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: reason.trim() || '用戶標記不相關' })
        });
        if (res.ok) {
          alert(`已成功排除 Scene #${sceneId} 素材！\n${res.message || '已替換為備選素材。'}`);
          if (typeof openStageInspector === 'function') {
            await openStageInspector('images');
          }
        } else {
          alert(`排除失敗: ${res.detail || res.error || '未知錯誤'}`);
        }
      } catch (e) {
        alert(`操作失敗: ${e.message}`);
      }
    }
    window.rejectAndReplaceSceneMedia = rejectAndReplaceSceneMedia;
