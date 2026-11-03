from pathlib import Path

html_path = Path("ui/index.html")
content = html_path.read_text(encoding="utf-8")

# 1. Update tab-music with Sub-navigation and Classical Repertoire View
old_tab_music_header = '''  <!-- TAB: MUSIC -->
  <div id="tab-music" class="tab-content">
    <div class="card">'''

new_tab_music_header = '''  <!-- TAB: MUSIC -->
  <div id="tab-music" class="tab-content">
    <!-- Sub-navigation: Ambient vs Classical (OpenOpus) -->
    <div style="display: flex; gap: 10px; margin-bottom: 18px; border-bottom: 1px solid var(--border-muted); padding-bottom: 12px; flex-wrap: wrap;">
      <button id="btn-music-subnav-ambient" class="btn-sec active" onclick="switchMusicSubTab('ambient')" style="padding: 8px 18px; font-weight: 700; border-radius: 20px; background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; display: flex; align-items: center; gap: 6px;">
        <span>🎧</span> <span>本地環境氛圍音效庫 (Ambient Library)</span>
      </button>
      <button id="btn-music-subnav-classical" class="btn-sec" onclick="switchMusicSubTab('classical')" style="padding: 8px 18px; font-weight: 700; border-radius: 20px; background: #0b1120; color: #94a3b8; border: 1px solid var(--border-muted); display: flex; align-items: center; gap: 6px;">
        <span>🏛️</span> <span>古典名曲典藏 (OpenOpus Classical Repertoire)</span>
      </button>
    </div>

    <!-- SUBVIEW 1: LOCAL AMBIENT LIBRARY -->
    <div id="music-subview-ambient">
    <div class="card">'''

if old_tab_music_header not in content:
    print("ERROR: old_tab_music_header not found!")
    exit(1)

content = content.replace(old_tab_music_header, new_tab_music_header, 1)

old_tab_music_footer = '''        <button onclick="saveAndRerenderAudioMix()" class="btn-sec" style="padding: 9px 16px; font-weight: 700; background: #065f46; color: #fff; border-color: #059669;">⚡ Re-Render 1080p Video With New Music</button>
        <span id="project-music-save-status" style="font-size: 12px; color: #34d399;"></span>
      </div>
    </div>
  </div>'''

classical_subview_html = '''        <button onclick="saveAndRerenderAudioMix()" class="btn-sec" style="padding: 9px 16px; font-weight: 700; background: #065f46; color: #fff; border-color: #059669;">⚡ Re-Render 1080p Video With New Music</button>
        <span id="project-music-save-status" style="font-size: 12px; color: #34d399;"></span>
      </div>
    </div>
    </div>
    <!-- END SUBVIEW 1: LOCAL AMBIENT LIBRARY -->

    <!-- SUBVIEW 2: OPENOPUS CLASSICAL REPERTOIRE -->
    <div id="music-subview-classical" style="display: none;">
      <!-- Search & Epoch Bar -->
      <div class="card" style="margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 14px;">
          <div>
            <div class="card-title" style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px;">
              <span>🏛️ OpenOpus 古典名曲曲庫 (Classical Music Repertoire)</span>
              <span class="badge badge-blue">REST API + Public Domain Audio</span>
            </div>
            <div style="font-size: 12px; color: var(--text-muted);">
              瀏覽自巴洛克至二十世紀的巨匠經典，支援一鍵檢索 Internet Archive 與 Wikimedia Commons 公有領域原聲無失真音檔並自動匯入影片配樂庫。
            </div>
          </div>
          <div style="display: flex; gap: 8px; align-items: center;">
            <input type="text" id="openopus-search-input" placeholder="搜尋作曲家或作品 (例: Beethoven, BWV, 命運)..." style="padding: 7px 12px; font-size: 12.5px; border-radius: var(--radius); background: var(--bg-sunken); border: 1px solid var(--border-muted); color: #fff; width: 280px;" onkeydown="if(event.key==='Enter') executeOpenOpusSearch()">
            <button class="btn-primary" onclick="executeOpenOpusSearch()" style="padding: 7px 14px; font-size: 12.5px; font-weight: 700;">🔍 搜尋</button>
          </div>
        </div>

        <!-- Epoch Filter Pills -->
        <div id="openopus-epoch-pills" style="display: flex; gap: 8px; flex-wrap: wrap;">
          <button class="btn-sec openopus-epoch-btn active" onclick="filterOpenOpusEpoch('popular', this)" style="padding: 5px 14px; border-radius: 20px; font-size: 12px; background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; font-weight: 700;">⭐ 熱門大師 (Popular)</button>
          <button class="btn-sec openopus-epoch-btn" onclick="filterOpenOpusEpoch('Baroque', this)" style="padding: 5px 14px; border-radius: 20px; font-size: 12px; background: #0b1120; color: #94a3b8; border: 1px solid var(--card-border);">巴洛克 (Baroque)</button>
          <button class="btn-sec openopus-epoch-btn" onclick="filterOpenOpusEpoch('Classical', this)" style="padding: 5px 14px; border-radius: 20px; font-size: 12px; background: #0b1120; color: #94a3b8; border: 1px solid var(--card-border);">古典主義 (Classical)</button>
          <button class="btn-sec openopus-epoch-btn" onclick="filterOpenOpusEpoch('Early Romantic', this)" style="padding: 5px 14px; border-radius: 20px; font-size: 12px; background: #0b1120; color: #94a3b8; border: 1px solid var(--card-border);">早期浪漫 (Early Romantic)</button>
          <button class="btn-sec openopus-epoch-btn" onclick="filterOpenOpusEpoch('Romantic', this)" style="padding: 5px 14px; border-radius: 20px; font-size: 12px; background: #0b1120; color: #94a3b8; border: 1px solid var(--card-border);">浪漫主義 (Romantic)</button>
          <button class="btn-sec openopus-epoch-btn" onclick="filterOpenOpusEpoch('Late Romantic', this)" style="padding: 5px 14px; border-radius: 20px; font-size: 12px; background: #0b1120; color: #94a3b8; border: 1px solid var(--card-border);">晚期浪漫 (Late Romantic)</button>
          <button class="btn-sec openopus-epoch-btn" onclick="filterOpenOpusEpoch('20th Century', this)" style="padding: 5px 14px; border-radius: 20px; font-size: 12px; background: #0b1120; color: #94a3b8; border: 1px solid var(--card-border);">二十世紀 (20th Century)</button>
        </div>
      </div>

      <!-- Composers Grid Container -->
      <div id="openopus-composers-container">
        <div id="openopus-composers-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px;">
          <div style="color: var(--text-muted); font-size: 13px; padding: 20px;">載入作曲家名錄中...</div>
        </div>
      </div>

      <!-- Composer Works Detail Container (Shown when a composer is selected) -->
      <div id="openopus-works-container" style="display: none;">
        <div class="card" style="margin-bottom: 14px; background: #060b14; border: 1px solid #1e293b;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div style="display: flex; align-items: center; gap: 14px;">
              <button class="btn-sec" onclick="backToOpenOpusComposers()" style="padding: 6px 12px; font-size: 12px; font-weight: 700; color: #93c5fd; border-color: #3b82f6;">
                ← 返回作曲家列表
              </button>
              <img id="openopus-detail-avatar" src="" style="width: 44px; height: 44px; border-radius: 50%; object-fit: cover; border: 2px solid #3b82f6;">
              <div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <h3 id="openopus-detail-name" style="margin: 0; font-size: 16px; color: #fff;"></h3>
                  <span id="openopus-detail-epoch" class="badge badge-blue"></span>
                </div>
                <div id="openopus-detail-lifespan" style="font-size: 12px; color: var(--text-muted); margin-top: 2px;"></div>
              </div>
            </div>
            <!-- Genre Filter Pills -->
            <div id="openopus-genre-pills" style="display: flex; gap: 6px; flex-wrap: wrap;"></div>
          </div>
        </div>

        <!-- Works List Cards -->
        <div id="openopus-works-list" style="display: flex; flex-direction: column; gap: 10px;">
          <div style="color: var(--text-muted); font-size: 13px; padding: 20px;">載入樂曲作品清單中...</div>
        </div>
      </div>
    </div>
    <!-- END SUBVIEW 2 -->
  </div>'''

if old_tab_music_footer not in content:
    print("ERROR: old_tab_music_footer not found!")
    exit(1)

content = content.replace(old_tab_music_footer, classical_subview_html, 1)

# 2. Update Stage 7 Movement Card in Studio with Start Offset & Classical Masterpiece button
old_studio_music_select = '''                <!-- Track Selector & Controls -->
                <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                  <label style="font-size: 12px; font-weight: 600; color: #94a3b8; margin: 0;">更換此樂章曲目：</label>
                  <select id="studio-music-select-${idx}" style="flex: 1; min-width: 260px; padding: 6px 10px; font-size: 12px; border-radius: var(--radius-sm); background: var(--bg-canvas); color: var(--text-primary); border: 1px solid var(--border-muted);" onchange="onStudioMusicSegmentTrackChange(${idx}, this)">
                    ${trackOptionsHtml}
                  </select>
                </div>'''

new_studio_music_select = '''                <!-- Track Selector & Controls -->
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
                </div>'''

if old_studio_music_select not in content:
    print("ERROR: old_studio_music_select not found!")
    exit(1)

content = content.replace(old_studio_music_select, new_studio_music_select, 1)

# 3. Add Classical Masterpiece Modal and JS functions before closing </script>
js_code_to_append = '''
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
        const res = await fetch(url);
        const data = await res.json();
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
        const res = await fetch(`/api/music/openopus/composers/search?q=${encodeURIComponent(q)}`);
        const data = await res.json();
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
        const res = await fetch(url);
        const data = await res.json();
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
        const resolveRes = await fetch(`/api/music/openopus/resolve-audio?composer=${encodeURIComponent(compName)}&work=${encodeURIComponent(title)}`);
        const resolveData = await resolveRes.json();
        const candidates = resolveData.candidates || [];

        if (!candidates.length) {
          if (statusEl) statusEl.innerHTML = '<span style="color: #f59e0b;">線上公有錄音未收錄，請點選「📤 上傳」自行上傳音檔綁定。</span>';
          if (btnEl) { btnEl.disabled = false; btnEl.innerText = '⚡ 一鍵解析公有領域錄音'; }
          return;
        }

        const best = candidates[0];
        if (btnEl) btnEl.innerText = '⬇️ 下載轉換中...';
        if (statusEl) statusEl.innerHTML = `<span style="color: #34d399;">已尋得錄音「${best.title}」，正在下載並規格化 MP3...</span>`;

        const importRes = await fetch('/api/music/openopus/import-work', {
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

        if (!importRes.ok) throw new Error("Import failed");
        const importData = await importRes.json();
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
          const res = await fetch('/api/music/openopus/upload-work', {
            method: 'POST',
            body: formData,
          });
          if (!res.ok) throw new Error("Upload failed");
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
      if (!studioStageData || !studioStageData.music_plan || !studioStageData.music_plan[segIdx]) return;
      const seg = studioStageData.music_plan[segIdx];
      seg.start_offset = parseFloat(val) || 0.0;
      if (typeof showToast === 'function') showToast(`✓ 已設定樂章 ${segIdx + 1} 起播偏移: ${seg.start_offset}s`);
    }

    function openStudioClassicalPicker(movementIdx) {
      studioTargetMovementIdx = movementIdx;
      // Switch to music tab & classical view
      switchTab('music');
      switchMusicSubTab('classical');
      if (typeof showToast === 'function') showToast(`🏛️ 請在古典名曲曲庫中選擇要指定至 Movement ${movementIdx + 1} 的曲目`);
    }
'''

# Find closing </script> in index.html and insert js
last_script_idx = content.rfind("</script>")
if last_script_idx == -1:
    print("ERROR: </script> tag not found!")
    exit(1)

content = content[:last_script_idx] + js_code_to_append + "\n" + content[last_script_idx:]
html_path.write_text(content, encoding="utf-8")
print("SUCCESS: ui/index.html updated with Classical Repertoire, Sub-navigation, and Start Offset!")
