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
          bodyHtml += `
            <!-- Remotion Motion Graphics Studio Card -->
            <div style="background: linear-gradient(135deg, #0b1526 0%, #070e1b 100%); border: 1.5px solid #00F5FF; border-radius: 10px; padding: 18px 20px; margin-bottom: 22px; box-shadow: 0 0 25px rgba(0, 245, 255, 0.15);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <span style="font-size: 24px;">⚛️</span>
                  <div>
                    <h3 style="margin: 0; font-size: 15px; font-weight: 800; color: #fff; letter-spacing: 0.5px;">Remotion 重點分鏡動態卡片</h3>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">卡片疊加在該分鏡圖片上（背景自動調暗、模糊）；文字取自分鏡的重點字卡與旁白。只建議用於關鍵分鏡。</div>
                  </div>
                </div>
                <span style="font-size: 11px; background: rgba(0, 245, 255, 0.15); border: 1px solid #00F5FF; color: #00F5FF; font-weight: 700; padding: 3px 8px; border-radius: 12px;">1080p · 30fps</span>
              </div>

              <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 14px; padding: 10px 12px; background: rgba(2, 132, 199, 0.12); border: 1px dashed #0284c7; border-radius: 8px;">
                <button id="remotion-auto-btn" class="btn-primary" style="background: linear-gradient(135deg, #0891b2 0%, #0e7490 100%); border: 1px solid #00F5FF; font-weight: 700; padding: 8px 16px; font-size: 12px;" onclick="autoRemotionCriticalScenes()">
                  ✨ 自動為所有關鍵分鏡產生卡片
                </button>
                <div id="remotion-auto-status" style="font-size: 12px; color: #94a3b8;">自動挑選有重點字卡 / 高強調的分鏡（約 20%，最多 8 個，不連續）</div>
              </div>

              <!-- Visual Style Selector Thumbnails -->
              <div style="margin-bottom: 14px;">
                <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 6px;">視覺風格 (Card Style) - 點擊縮圖即時切換：</label>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px;">
                  <div onclick="selectRemotionStudioStyle('TechCard')" id="studio-style-card-TechCard" style="border: 2px solid #00F5FF; background: #060b16; border-radius: 8px; padding: 6px; cursor: pointer; text-align: center; box-shadow: 0 0 12px rgba(0,245,255,0.25); transition: all 0.2s;">
                    <img src="/remotion/style_techcard.png" alt="Tech Card" style="width: 100%; height: 68px; object-fit: cover; border-radius: 5px; display: block; margin-bottom: 5px;">
                    <div style="font-size: 11px; font-weight: 800; color: #00F5FF;">⚡ Tech Card</div>
                    <div style="font-size: 10px; color: #94a3b8;">賽博青光發光</div>
                  </div>
                  <div onclick="selectRemotionStudioStyle('MinimalistCard')" id="studio-style-card-MinimalistCard" style="border: 1.5px solid #1e293b; background: #060b16; border-radius: 8px; padding: 6px; cursor: pointer; text-align: center; transition: all 0.2s;">
                    <img src="/remotion/style_minimalist.png" alt="Minimalist" style="width: 100%; height: 68px; object-fit: cover; border-radius: 5px; display: block; margin-bottom: 5px;">
                    <div style="font-size: 11px; font-weight: 800; color: #34d399;">📐 Minimalist</div>
                    <div style="font-size: 10px; color: #94a3b8;">瑞士極簡綠線</div>
                  </div>
                  <div onclick="selectRemotionStudioStyle('CinemaImpactCard')" id="studio-style-card-CinemaImpactCard" style="border: 1.5px solid #1e293b; background: #060b16; border-radius: 8px; padding: 6px; cursor: pointer; text-align: center; transition: all 0.2s;">
                    <img src="/remotion/style_cinema.png" alt="Cinema Impact" style="width: 100%; height: 68px; object-fit: cover; border-radius: 5px; display: block; margin-bottom: 5px;">
                    <div style="font-size: 11px; font-weight: 800; color: #fbbf24;">🎬 Cinema Impact</div>
                    <div style="font-size: 10px; color: #94a3b8;">電影金曜震撼</div>
                  </div>
                </div>
                <select id="remotion-style-select" style="display: none;">
                  <option value="TechCard" selected>TechCard</option>
                  <option value="MinimalistCard">MinimalistCard</option>
                  <option value="CinemaImpactCard">CinemaImpactCard</option>
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
            <div style="display: flex; flex-direction: column; gap: 12px;">
          `;
          scenes.forEach((s, idx) => {
            bodyHtml += `
              <div style="background: #080d16; border: 1px solid var(--card-border); border-radius: 8px; padding: 14px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div>
                  <span style="font-weight: 700; color: #93c5fd;">Scene #${s.scene_id}</span>
                  ${s.is_presenter ? `<span style="background: rgba(139, 92, 246, 0.25); border: 1px solid #8b5cf6; color: #c4b5fd; font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px; margin-left: 6px;">🎭 主播場景</span>` : ''}
                  <div style="font-size: 12px; color: #cbd5e1; margin-top: 2px;">Motion: <b>${s.camera_motion || 'slow_zoom_in'}</b> | Duration: <b>${s.estimated_duration || 5}s</b></div>
                </div>
                <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                  ${s.is_presenter ? `
                    <button type="button" class="btn-sec" style="padding: 5px 10px; font-size: 11px; font-weight: 700; background: rgba(139, 92, 246, 0.25); border-color: #8b5cf6; color: #c4b5fd; display: inline-flex; align-items: center; gap: 4px;" onclick="triggerSceneAvatarUpload(${s.scene_id})" title="方案2：直接上傳此分鏡的自錄真人/戴口罩出鏡影片">
                      📤 上傳自錄影片 (Upload Custom Video)
                    </button>
                    <input type="file" id="scene-avatar-file-${s.scene_id}" accept="video/mp4,video/quicktime,video/webm" style="display:none;" onchange="uploadCustomSceneAvatarClip(${s.scene_id}, this.files[0])">
                    <button type="button" class="btn-sec" style="padding: 5px 10px; font-size: 11px; font-weight: 700; background: rgba(139, 92, 246, 0.18); border-color: #7c3aed; color: #c4b5fd;" onclick="rerenderSingleSceneAvatarClip(${s.scene_id})" title="單獨重新生成此分鏡口型">
                      🎭 重製口型
                    </button>
                  ` : ''}
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
