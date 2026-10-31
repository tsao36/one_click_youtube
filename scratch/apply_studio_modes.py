import re, io

def rw(path, fn):
    s = open(path, 'rb').read().decode('utf-8')
    crlf = '\r\n' in s
    s = s.replace('\r\n', '\n')
    s2 = fn(s)
    assert s2 != s, path
    open(path, 'wb').write((s2.replace('\n', '\r\n') if crlf else s2).encode('utf-8'))

def rep(s, old, new, count=1):
    assert s.count(old) >= 1, "missing: " + old[:80]
    return s.replace(old, new, count)

# ---------------- backend ----------------
def pm(s):
    return rep(s, '''                    out.append({k: data.get(k) for k in (
                        "id", "topic", "title", "created_at", "updated_at", "started_at", "completed_at",
                        "total_duration_seconds", "stage_durations", "state", "activity", "outputs"
                    )})''', '''                    item = {k: data.get(k) for k in (
                        "id", "topic", "title", "created_at", "updated_at", "started_at", "completed_at",
                        "total_duration_seconds", "stage_durations", "state", "activity", "outputs"
                    )}
                    # Expose creation mode so each Stage Studio lists only its own projects.
                    item["project_mode"] = (
                        (data.get("settings") or {}).get("project_mode") or "documentary"
                    )
                    out.append(item)''')
rw(r'c:\AI Project\Youtube_video\core\project_manager.py', pm)

# ---------------- UI ----------------
def ui(s):
    # 1. nav tabs
    m = re.search(r'<button class="nav-tab" onclick="switchTab\(\'studio\'\)">[^<]*Stage Studio</button>', s)
    assert m
    s = s.replace(m.group(0),
        '<button class="nav-tab" onclick="switchTab(\'studio\')">🛠️ Documentary Stage Studio</button>\n'
        '    <button class="nav-tab" onclick="switchTab(\'dramastudio\')">🎭 Drama Stage Studio</button>', 1)

    # 2. studio header: ids + mode banner
    s = rep(s, '<span style="font-size: 22px;">🛠️</span>\n            <span style="font-size: 18px; font-weight: 800; color: #fff;">Independent Stage Studio & Playground</span>',
               '<span style="font-size: 22px;" id="studio-mode-icon">🛠️</span>\n            <span style="font-size: 18px; font-weight: 800; color: #fff;" id="studio-mode-title">Documentary Stage Studio</span>\n            <span id="studio-mode-badge" class="badge badge-blue" style="font-size: 11px;">16:9 Documentary</span>')
    s = rep(s, '''          <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
            Play around with each stage independently''', '''          <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;" id="studio-mode-desc">
            Play around with each stage independently''')
    s = rep(s, '<div id="studio-stepper" style="display: flex;', '<div id="studio-project-bar" style="margin-top: 14px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 12px; color: var(--text-muted);"></div>\n\n      <div id="studio-stepper" style="display: flex;')

    # 3. switchTab
    s = rep(s, '''    function switchTab(name) {
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      const foundTab = Array.from(document.querySelectorAll('.nav-tab')).find(t => t.textContent.toLowerCase().includes(name) || t.getAttribute('onclick').includes(name));
      if (foundTab) foundTab.classList.add('active');
      const targetContent = document.getElementById('tab-' + name);
      if (targetContent) targetContent.classList.add('active');

      if (name === 'studio') loadStageStudio();''', '''    function switchTab(name) {
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      const foundTab = Array.from(document.querySelectorAll('.nav-tab')).find(t => (t.getAttribute('onclick') || '').includes(`switchTab('${name}')`));
      if (foundTab) foundTab.classList.add('active');
      // Both Stage Studios share one workspace DOM; each mode has its own tab, header and project list.
      const isStudioTab = (name === 'studio' || name === 'dramastudio');
      const targetContent = document.getElementById('tab-' + (isStudioTab ? 'studio' : name));
      if (targetContent) targetContent.classList.add('active');

      if (isStudioTab) {
        studioMode = (name === 'dramastudio') ? 'short_drama' : 'documentary';
        applyStudioModeChrome();
        loadStageStudio();
      }''')

    # 4. studio state + helpers (before isDramaStudioProject)
    s = rep(s, "    function isDramaStudioProject(proj = null) {", '''    // Which Stage Studio is open: 'documentary' | 'short_drama'
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
        : 'Play around with each documentary stage independently: research, script, scenes, prompts, images, voice, animation, subtitles and render.');
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

    function isDramaStudioProject(proj = null) {''')

    # 5. isDramaStudioProject fallback to studio mode when studio tab active
    s = rep(s, "      return currentCreatorProjectMode === 'short_drama';\n    }\n\n    let activeStudioStage",
               "      const studioActive = document.getElementById('tab-studio') && document.getElementById('tab-studio').classList.contains('active');\n      if (studioActive) return studioMode === 'short_drama';\n      return currentCreatorProjectMode === 'short_drama';\n    }\n\n    let activeStudioStage")

    # 6. openStudioStage picks the tab by project mode
    s = rep(s, '''      if (stageName) activeStudioStage = stageName;
      switchTab('studio');''', '''      if (stageName) activeStudioStage = stageName;
      const cur = allProjectsCache.find(p => p.id === currentProjectId);
      switchTab(projectModeOf(cur) === 'short_drama' ? 'dramastudio' : 'studio');''')

    # 7. loadStageStudio: mismatch guard + project bar
    s = rep(s, '''        studioProject = pData.project;
        currentScenes = pData.scenes || [];
        renderStudioStepper(studioProject);''', '''        studioProject = pData.project;
        currentScenes = pData.scenes || [];
        renderStudioProjectBar();
        if (projectModeOf(studioProject) !== studioMode) {
          renderStudioModeMismatch(studioProject);
          return;
        }
        renderStudioStepper(studioProject);''')

    # 8. loadProjectsList: cache + mode icon
    s = rep(s, '''        const projects = await res.json();
        const sel = document.getElementById('global-project-select');''', '''        const projects = await res.json();
        allProjectsCache = projects || [];
        const sel = document.getElementById('global-project-select');''')
    s = rep(s, "opt.textContent = `${statusIcon}[${p.id}] ${dispTitle}${durText}`;",
               "opt.textContent = `${projectModeOf(p) === 'short_drama' ? '🎭 ' : '🎬 '}${statusIcon}[${p.id}] ${dispTitle}${durText}`;")
    return s

rw(r'c:\AI Project\Youtube_video\ui\index.html', ui)
print("ok")

