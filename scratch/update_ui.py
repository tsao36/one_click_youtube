# Script to update ui/index.html with new Remotion scenes, forms, and functions
from pathlib import Path

ui_path = Path("ui/index.html")
content = ui_path.read_text(encoding="utf-8")

# 1. Update selectRemotionStudioStyle
old_style_fn = """    function selectRemotionStudioStyle(compName) {

      const sel = document.getElementById('remotion-style-select');

      if (sel) sel.value = compName;

      ['TechCard', 'MinimalistCard', 'CinemaImpactCard'].forEach(c => {

        const card = document.getElementById('studio-style-card-' + c);

        if (card) {

          const isSel = (c === compName);

          const color = (c === 'TechCard') ? '#00F5FF' : (c === 'MinimalistCard' ? '#34d399' : '#fbbf24');

          card.style.border = isSel ? `2px solid ${color}` : '1.5px solid #1e293b';

          card.style.boxShadow = isSel ? `0 0 12px ${color}40` : 'none';

        }

      });

    }"""

new_style_fn = """    function selectRemotionStudioStyle(compName) {
      const sel = document.getElementById('remotion-style-select');
      if (sel) sel.value = compName;
      const styles = [
        'TechCard', 'MinimalistCard', 'CinemaImpactCard',
        'TitleScene', 'GridCompareScene', 'KCurveScene', 'StatNumberScene'
      ];
      const colorMap = {
        'TechCard': '#00F5FF',
        'MinimalistCard': '#34d399',
        'CinemaImpactCard': '#fbbf24',
        'TitleScene': '#3B82F6',
        'GridCompareScene': '#EC4899',
        'KCurveScene': '#8B5CF6',
        'StatNumberScene': '#10B981'
      };
      styles.forEach(c => {
        const card = document.getElementById('studio-style-card-' + c);
        if (card) {
          const isSel = (c === compName);
          const color = colorMap[c] || '#00F5FF';
          card.style.border = isSel ? `2px solid ${color}` : '1.5px solid #1e293b';
          card.style.boxShadow = isSel ? `0 0 14px ${color}55` : 'none';
        }
      });
      // Toggle corresponding parameters panel
      const paramGroups = ['cards', 'TitleScene', 'GridCompareScene', 'KCurveScene', 'StatNumberScene'];
      const activeGroup = ['TechCard', 'MinimalistCard', 'CinemaImpactCard'].includes(compName) ? 'cards' : compName;
      paramGroups.forEach(g => {
        const panel = document.getElementById('remotion-params-' + g);
        if (panel) {
          panel.style.display = (g === activeGroup) ? 'grid' : 'none';
        }
      });
    }"""

if old_style_fn in content:
    content = content.replace(old_style_fn, new_style_fn, 1)
    print("1. selectRemotionStudioStyle replaced successfully")
else:
    # Try normalizing CRLF / LF
    c_norm = content.replace("\r\n", "\n")
    old_norm = old_style_fn.replace("\r\n", "\n")
    if old_norm in c_norm:
        c_norm = c_norm.replace(old_norm, new_style_fn.replace("\r\n", "\n"), 1)
        content = c_norm.replace("\n", "\r\n")
        print("1. selectRemotionStudioStyle replaced via LF normalization")
    else:
        print("1. FAILED to find old_style_fn")

# 2. Update prefillRemotionFromScene and renderAndApplyRemotionClip + add previewStandaloneRemotionClip
old_helpers = """    async function prefillRemotionFromScene(sceneId) {

      // Show what will be auto-extracted for this scene as placeholders; typed values override.

      if (!currentProjectId || !sceneId) return;

      ['remotion-cat', 'remotion-headline', 'remotion-metric', 'remotion-subtext'].forEach(id => {

        const el = document.getElementById(id);

        if (el) { el.value = ''; el.placeholder = '自動擷取中…'; }

      });

      try {

        const res = await fetch(`/api/projects/${currentProjectId}/remotion/props/${sceneId}`);

        const data = await res.json();

        const p = data.props || {};

        const map = { 'remotion-cat': p.category, 'remotion-headline': p.headline, 'remotion-metric': p.metric, 'remotion-subtext': p.subtext };

        for (const [id, val] of Object.entries(map)) {

          const el = document.getElementById(id);

          if (el) el.placeholder = val ? `自動：${val}` : '（無）';

        }

      } catch (e) {

        console.warn('prefillRemotionFromScene failed', e);

      }

    }"""

new_helpers = """    async function prefillRemotionFromScene(sceneId) {
      if (!currentProjectId || !sceneId) return;
      const allFieldIds = [
        'remotion-cat', 'remotion-headline', 'remotion-metric', 'remotion-subtext',
        'remotion-title-cat', 'remotion-title-text', 'remotion-title-sub',
        'remotion-grid-left-title', 'remotion-grid-left-body', 'remotion-grid-right-title', 'remotion-grid-right-body',
        'remotion-kcurve-title', 'remotion-kcurve-upper', 'remotion-kcurve-lower',
        'remotion-stat-value', 'remotion-stat-unit', 'remotion-stat-label', 'remotion-stat-subtext'
      ];
      allFieldIds.forEach(id => {
        const el = document.getElementById(id);
        if (el && el.tagName === 'INPUT') { el.placeholder = '自動擷取中…'; }
      });

      try {
        const res = await fetch(`/api/projects/${currentProjectId}/remotion/props/${sceneId}`);
        const data = await res.json();
        const p = data.props || {};

        const map = {
          'remotion-cat': p.category,
          'remotion-headline': p.headline,
          'remotion-metric': p.metric,
          'remotion-subtext': p.subtext,
          'remotion-title-cat': p.category || '重點結論',
          'remotion-title-text': p.title || p.headline,
          'remotion-title-sub': p.subtitle || p.subtext,
          'remotion-grid-left-title': p.leftTitle || '方案 A',
          'remotion-grid-left-body': p.leftBody || p.headline,
          'remotion-grid-right-title': p.rightTitle || '方案 B',
          'remotion-grid-right-body': p.rightBody || p.subtext,
          'remotion-kcurve-title': 'K 型兩極分化趨勢',
          'remotion-kcurve-upper': p.upperText || p.headline || '領先群體',
          'remotion-kcurve-lower': p.lowerText || p.subtext || '落後群體',
          'remotion-stat-value': p.value !== undefined ? p.value : '',
          'remotion-stat-unit': p.unit || '',
          'remotion-stat-label': p.label || p.headline || '核心指標',
          'remotion-stat-subtext': p.subtext || ''
        };

        for (const [id, val] of Object.entries(map)) {
          const el = document.getElementById(id);
          if (el) {
            el.placeholder = (val !== undefined && val !== '') ? `自動：${val}` : '（無）';
          }
        }
      } catch (e) {
        console.warn('prefillRemotionFromScene failed', e);
      }
    }

    function collectCurrentRemotionProps(comp) {
      let props = {};
      if (['TechCard', 'MinimalistCard', 'CinemaImpactCard'].includes(comp)) {
        props = {
          category: (document.getElementById('remotion-cat')?.value || '').trim(),
          headline: (document.getElementById('remotion-headline')?.value || '').trim(),
          metric: (document.getElementById('remotion-metric')?.value || '').trim(),
          subtext: (document.getElementById('remotion-subtext')?.value || '').trim(),
        };
      } else if (comp === 'TitleScene') {
        props = {
          title: (document.getElementById('remotion-title-text')?.value || '').trim(),
          subtitle: (document.getElementById('remotion-title-sub')?.value || '').trim(),
          category: (document.getElementById('remotion-title-cat')?.value || '').trim(),
          accentColor: document.getElementById('remotion-title-color')?.value || '#3B82F6',
        };
      } else if (comp === 'GridCompareScene') {
        props = {
          leftTitle: (document.getElementById('remotion-grid-left-title')?.value || '').trim(),
          leftBody: (document.getElementById('remotion-grid-left-body')?.value || '').trim(),
          rightTitle: (document.getElementById('remotion-grid-right-title')?.value || '').trim(),
          rightBody: (document.getElementById('remotion-grid-right-body')?.value || '').trim(),
          comparisonLabel: (document.getElementById('remotion-grid-vs-label')?.value || 'VS').trim(),
          leftColor: document.getElementById('remotion-grid-left-color')?.value || '#3B82F6',
          rightColor: document.getElementById('remotion-grid-right-color')?.value || '#EF4444',
        };
      } else if (comp === 'KCurveScene') {
        props = {
          title: (document.getElementById('remotion-kcurve-title')?.value || '').trim(),
          upperText: (document.getElementById('remotion-kcurve-upper')?.value || '').trim(),
          lowerText: (document.getElementById('remotion-kcurve-lower')?.value || '').trim(),
          forkProgress: parseFloat(document.getElementById('remotion-kcurve-fork')?.value) || 0.35,
          upperColor: document.getElementById('remotion-kcurve-upper-color')?.value || '#10B981',
          lowerColor: document.getElementById('remotion-kcurve-lower-color')?.value || '#EF4444',
        };
      } else if (comp === 'StatNumberScene') {
        const valStr = document.getElementById('remotion-stat-value')?.value;
        props = {
          value: valStr !== '' && !isNaN(parseFloat(valStr)) ? parseFloat(valStr) : undefined,
          prefix: (document.getElementById('remotion-stat-prefix')?.value || '').trim(),
          suffix: '',
          unit: (document.getElementById('remotion-stat-unit')?.value || '').trim(),
          label: (document.getElementById('remotion-stat-label')?.value || '').trim(),
          subtext: (document.getElementById('remotion-stat-subtext')?.value || '').trim(),
          decimals: parseInt(document.getElementById('remotion-stat-decimals')?.value, 10) || 0,
          accentColor: document.getElementById('remotion-stat-color')?.value || '#10B981',
        };
      }
      return props;
    }

    async function previewStandaloneRemotionClip() {
      const btn = document.getElementById('remotion-preview-btn');
      const statusText = document.getElementById('remotion-status-text');
      const previewBox = document.getElementById('remotion-preview-box');
      const previewVideo = document.getElementById('remotion-preview-video');
      const comp = document.getElementById('remotion-style-select')?.value || 'TitleScene';
      const props = collectCurrentRemotionProps(comp);

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-inline" style="width:12px; height:12px; margin-right:6px;"></span> 預覽算繪中…`;
      }
      if (statusText) {
        statusText.style.color = '#38bdf8';
        statusText.textContent = `⏳ Remotion [${comp}] 正在算繪 MP4 預覽短片（約 15–25 秒）...`;
      }

      try {
        const res = await fetch('/api/remotion/render', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            composition: comp,
            props: props,
            fps: 30,
            duration_frames: 150
          })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "預覽算繪失敗");
        }
        const data = await res.json();
        if (statusText) {
          statusText.style.color = '#34d399';
          statusText.innerHTML = `✓ [${comp}] 預覽短片算繪完成！`;
        }
        if (previewBox && previewVideo && data.mp4_url) {
          previewBox.style.display = 'block';
          previewVideo.src = data.mp4_url + `?t=${Date.now()}`;
          previewVideo.load();
          previewVideo.play().catch(() => {});
        }
      } catch (e) {
        if (statusText) {
          statusText.style.color = '#f87171';
          statusText.textContent = '❌ ' + e.message;
        }
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '👁️ 一鍵預覽 MP4 算繪';
        }
      }
    }"""

if old_helpers in content:
    content = content.replace(old_helpers, new_helpers, 1)
    print("2. prefillRemotionFromScene replaced successfully")
else:
    c_norm = content.replace("\r\n", "\n")
    old_norm = old_helpers.replace("\r\n", "\n")
    if old_norm in c_norm:
        c_norm = c_norm.replace(old_norm, new_helpers.replace("\r\n", "\n"), 1)
        content = c_norm.replace("\n", "\r\n")
        print("2. prefillRemotionFromScene replaced via LF normalization")
    else:
        print("2. FAILED to find old_helpers")

# 3. Update renderAndApplyRemotionClip to use collectCurrentRemotionProps
old_apply_body = """      // Empty fields are filled on the server from the scene's callout / narration.

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

        const res = await fetch(`/api/projects/${currentProjectId}/remotion/apply`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            composition: comp,

            scene_id: sceneIdVal,

            fps: 30,

            props: { category, headline, metric, subtext }

          })

        });"""

new_apply_body = """      const sceneIdVal = parseInt(document.getElementById('remotion-target-scene')?.value, 10);
      if (isNaN(sceneIdVal)) return alert("請選取要套用的目標分鏡");
      const props = collectCurrentRemotionProps(comp);

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-inline" style="width:12px; height:12px; margin-right:6px;"></span> 渲染中…`;
      }
      if (statusText) {
        statusText.style.color = '#38bdf8';
        statusText.textContent = `⏳ Remotion [${comp}] 正在逐幀渲染（約 20–30 秒，依分鏡長度而定）...`;
      }

      try {
        const res = await fetch(`/api/projects/${currentProjectId}/remotion/apply`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            composition: comp,
            scene_id: sceneIdVal,
            fps: 30,
            props: props
          })
        });"""

if old_apply_body in content:
    content = content.replace(old_apply_body, new_apply_body, 1)
    print("3. renderAndApplyRemotionClip props collection replaced successfully")
else:
    c_norm = content.replace("\r\n", "\n")
    old_norm = old_apply_body.replace("\r\n", "\n")
    if old_norm in c_norm:
        c_norm = c_norm.replace(old_norm, new_apply_body.replace("\r\n", "\n"), 1)
        content = c_norm.replace("\n", "\r\n")
        print("3. renderAndApplyRemotionClip replaced via LF normalization")
    else:
        print("3. FAILED to find old_apply_body")

ui_path.write_text(content, encoding="utf-8")
print("Finished JS updates in ui/index.html")
