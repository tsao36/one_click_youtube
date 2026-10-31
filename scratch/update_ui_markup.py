# Update Remotion Studio markup in ui/index.html
from pathlib import Path

ui_path = Path("ui/index.html")
content = ui_path.read_text(encoding="utf-8")

old_markup = """              <!-- Visual Style Selector Thumbnails -->

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

              </div>"""

new_markup = """              <!-- Visual Style Selector Thumbnails (7 Styles) -->
              <div style="margin-bottom: 16px;">
                <label style="font-size: 12px; font-weight: 800; color: #93c5fd; display: block; margin-bottom: 8px;">
                  視覺風格 (Motion Graphic Style) - 點擊即時切換設定表單與算繪範本：
                </label>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px;">
                  <!-- 1. TitleScene -->
                  <div onclick="selectRemotionStudioStyle('TitleScene')" id="studio-style-card-TitleScene" style="border: 2px solid #3B82F6; background: #060b16; border-radius: 8px; padding: 6px; cursor: pointer; text-align: center; box-shadow: 0 0 14px rgba(59,130,246,0.35); transition: all 0.2s;">
                    <img src="/remotion/style_titlescene.png" alt="Title Scene" style="width: 100%; height: 64px; object-fit: cover; border-radius: 5px; display: block; margin-bottom: 5px;">
                    <div style="font-size: 11px; font-weight: 800; color: #60a5fa;">🏆 標題揭露</div>
                    <div style="font-size: 10px; color: #94a3b8;">重大結論微光脈衝</div>
                  </div>
                  <!-- 2. GridCompareScene -->
                  <div onclick="selectRemotionStudioStyle('GridCompareScene')" id="studio-style-card-GridCompareScene" style="border: 1.5px solid #1e293b; background: #060b16; border-radius: 8px; padding: 6px; cursor: pointer; text-align: center; transition: all 0.2s;">
                    <img src="/remotion/style_gridcompare.png" alt="Grid Compare" style="width: 100%; height: 64px; object-fit: cover; border-radius: 5px; display: block; margin-bottom: 5px;">
                    <div style="font-size: 11px; font-weight: 800; color: #f472b6;">⚖️ 雙欄比較</div>
                    <div style="font-size: 10px; color: #94a3b8;">概念對決左右對立</div>
                  </div>
                  <!-- 3. KCurveScene -->
                  <div onclick="selectRemotionStudioStyle('KCurveScene')" id="studio-style-card-KCurveScene" style="border: 1.5px solid #1e293b; background: #060b16; border-radius: 8px; padding: 6px; cursor: pointer; text-align: center; transition: all 0.2s;">
                    <img src="/remotion/style_kcurve.png" alt="K-Curve" style="width: 100%; height: 64px; object-fit: cover; border-radius: 5px; display: block; margin-bottom: 5px;">
                    <div style="font-size: 11px; font-weight: 800; color: #a78bfa;">📈 K型分化</div>
                    <div style="font-size: 10px; color: #94a3b8;">貝茲雙向分流軌跡</div>
                  </div>
                  <!-- 4. StatNumberScene -->
                  <div onclick="selectRemotionStudioStyle('StatNumberScene')" id="studio-style-card-StatNumberScene" style="border: 1.5px solid #1e293b; background: #060b16; border-radius: 8px; padding: 6px; cursor: pointer; text-align: center; transition: all 0.2s;">
                    <img src="/remotion/style_statnumber.png" alt="Stat Number" style="width: 100%; height: 64px; object-fit: cover; border-radius: 5px; display: block; margin-bottom: 5px;">
                    <div style="font-size: 11px; font-weight: 800; color: #34d399;">🔢 動態數字</div>
                    <div style="font-size: 10px; color: #94a3b8;">自適應計數跳動</div>
                  </div>
                  <!-- 5. TechCard -->
                  <div onclick="selectRemotionStudioStyle('TechCard')" id="studio-style-card-TechCard" style="border: 1.5px solid #1e293b; background: #060b16; border-radius: 8px; padding: 6px; cursor: pointer; text-align: center; transition: all 0.2s;">
                    <img src="/remotion/style_techcard.png" alt="Tech Card" style="width: 100%; height: 64px; object-fit: cover; border-radius: 5px; display: block; margin-bottom: 5px;">
                    <div style="font-size: 11px; font-weight: 800; color: #00F5FF;">⚡ Tech Card</div>
                    <div style="font-size: 10px; color: #94a3b8;">賽博青光發光</div>
                  </div>
                  <!-- 6. MinimalistCard -->
                  <div onclick="selectRemotionStudioStyle('MinimalistCard')" id="studio-style-card-MinimalistCard" style="border: 1.5px solid #1e293b; background: #060b16; border-radius: 8px; padding: 6px; cursor: pointer; text-align: center; transition: all 0.2s;">
                    <img src="/remotion/style_minimalist.png" alt="Minimalist" style="width: 100%; height: 64px; object-fit: cover; border-radius: 5px; display: block; margin-bottom: 5px;">
                    <div style="font-size: 11px; font-weight: 800; color: #10b981;">📐 Minimalist</div>
                    <div style="font-size: 10px; color: #94a3b8;">瑞士極簡綠線</div>
                  </div>
                  <!-- 7. CinemaImpactCard -->
                  <div onclick="selectRemotionStudioStyle('CinemaImpactCard')" id="studio-style-card-CinemaImpactCard" style="border: 1.5px solid #1e293b; background: #060b16; border-radius: 8px; padding: 6px; cursor: pointer; text-align: center; transition: all 0.2s;">
                    <img src="/remotion/style_cinema.png" alt="Cinema Impact" style="width: 100%; height: 64px; object-fit: cover; border-radius: 5px; display: block; margin-bottom: 5px;">
                    <div style="font-size: 11px; font-weight: 800; color: #fbbf24;">🎬 Cinema Impact</div>
                    <div style="font-size: 10px; color: #94a3b8;">電影金曜震撼</div>
                  </div>
                </div>
                <select id="remotion-style-select" style="display: none;">
                  <option value="TitleScene" selected>TitleScene</option>
                  <option value="GridCompareScene">GridCompareScene</option>
                  <option value="KCurveScene">KCurveScene</option>
                  <option value="StatNumberScene">StatNumberScene</option>
                  <option value="TechCard">TechCard</option>
                  <option value="MinimalistCard">MinimalistCard</option>
                  <option value="CinemaImpactCard">CinemaImpactCard</option>
                </select>
              </div>

              <!-- Shared Target Scene Selector -->
              <div style="margin-bottom: 14px; background: rgba(15, 23, 42, 0.6); padding: 10px 12px; border-radius: 6px; border: 1px solid #1e293b;">
                <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 4px;">🎯 套用目標分鏡 (Target Scene):</label>
                <select id="remotion-target-scene" onchange="prefillRemotionFromScene(this.value)" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;">
                  ${scenes.map(s => `<option value="${s.scene_id}">Scene #${s.scene_id}${(s.animation && s.animation.meta && s.animation.meta.provider === 'remotion') ? ' ⚛️' : ''} (${(s.narration || '').slice(0, 24)}...)</option>`).join('')}
                </select>
              </div>

              <!-- Parameter Panels (Dynamic per scene type) -->
              <!-- 1. TitleScene Form -->
              <div id="remotion-params-TitleScene" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 14px;">
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #60a5fa; display: block; margin-bottom: 4px;">類別標籤 (Category):</label>
                  <input type="text" id="remotion-title-cat" value="重點結論" placeholder="例：重點結論、核心發現" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;">
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #60a5fa; display: block; margin-bottom: 4px;">微光強調色 (Accent Color):</label>
                  <input type="color" id="remotion-title-color" value="#3B82F6" style="width: 100%; height: 35px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; cursor: pointer;">
                </div>
                <div style="grid-column: span 2;">
                  <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 4px;">結論主標題 (Title):</label>
                  <input type="text" id="remotion-title-text" value="" placeholder="例：全球供應鏈重組：技術壁壘與資本外移" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #3b82f6; border-radius: 6px; color: #fff; font-weight: 700;">
                </div>
                <div style="grid-column: span 2;">
                  <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 4px;">副說明 / 命題細節 (Subtitle):</label>
                  <input type="text" id="remotion-title-sub" value="" placeholder="例：跨國企業加速在地化佈局，帶動區域型產業生態系崛起" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;">
                </div>
              </div>

              <!-- 2. GridCompareScene Form -->
              <div id="remotion-params-GridCompareScene" style="display: none; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 14px;">
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #60a5fa; display: block; margin-bottom: 4px;">左側標題 (Left Title):</label>
                  <input type="text" id="remotion-grid-left-title" value="" placeholder="例：資產持有者 / 方案 A" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #3b82f6; border-radius: 6px; color: #60a5fa; font-weight: 700;">
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #f87171; display: block; margin-bottom: 4px;">右側標題 (Right Title):</label>
                  <input type="text" id="remotion-grid-right-title" value="" placeholder="例：薪資所得者 / 方案 B" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #ef4444; border-radius: 6px; color: #f87171; font-weight: 700;">
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #60a5fa; display: block; margin-bottom: 4px;">左側觀點/敘述 (Left Body):</label>
                  <textarea id="remotion-grid-left-body" rows="2" placeholder="例：資本報酬率長期超越整體經濟增速，持續擴大財富優勢" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;"></textarea>
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #f87171; display: block; margin-bottom: 4px;">右側觀點/敘述 (Right Body):</label>
                  <textarea id="remotion-grid-right-body" rows="2" placeholder="例：實質薪資成長停滯，面對通膨與資產價格膨脹更顯脆弱" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #7f1d1d; border-radius: 6px; color: #fff;"></textarea>
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #f472b6; display: block; margin-bottom: 4px;">對決徽章標籤 (VS Label):</label>
                  <input type="text" id="remotion-grid-vs-label" value="VS" placeholder="VS" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #ec4899; border-radius: 6px; color: #f472b6; font-weight: 800; text-align: center;">
                </div>
                <div style="display: flex; gap: 8px;">
                  <div style="flex: 1;">
                    <label style="font-size: 11px; font-weight: 700; color: #60a5fa; display: block; margin-bottom: 4px;">左側色彩:</label>
                    <input type="color" id="remotion-grid-left-color" value="#3B82F6" style="width: 100%; height: 35px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; cursor: pointer;">
                  </div>
                  <div style="flex: 1;">
                    <label style="font-size: 11px; font-weight: 700; color: #f87171; display: block; margin-bottom: 4px;">右側色彩:</label>
                    <input type="color" id="remotion-grid-right-color" value="#EF4444" style="width: 100%; height: 35px; background: #040812; border: 1px solid #7f1d1d; border-radius: 6px; cursor: pointer;">
                  </div>
                </div>
              </div>

              <!-- 3. KCurveScene Form -->
              <div id="remotion-params-KCurveScene" style="display: none; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 14px;">
                <div style="grid-column: span 2;">
                  <label style="font-size: 11px; font-weight: 700; color: #a78bfa; display: block; margin-bottom: 4px;">K曲線圖表主題 (Title):</label>
                  <input type="text" id="remotion-kcurve-title" value="K 型兩極分化趨勢" placeholder="例：K 型兩極分化趨勢" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #8b5cf6; border-radius: 6px; color: #fff; font-weight: 700;">
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #34d399; display: block; margin-bottom: 4px;">上揚軌跡文字 (Upper Label):</label>
                  <input type="text" id="remotion-kcurve-upper" value="" placeholder="例：頂尖高科技與資本 (持續暴漲)" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #10b981; border-radius: 6px; color: #34d399; font-weight: 700;">
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #f87171; display: block; margin-bottom: 4px;">下探軌跡文字 (Lower Label):</label>
                  <input type="text" id="remotion-kcurve-lower" value="" placeholder="例：傳統製造與基層勞動 (成長停滯)" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #ef4444; border-radius: 6px; color: #f87171; font-weight: 700;">
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #94a3b8; display: block; margin-bottom: 4px;">軌跡分化點進度 (0.1 ~ 0.7):</label>
                  <input type="number" id="remotion-kcurve-fork" value="0.35" step="0.05" min="0.1" max="0.7" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;">
                </div>
                <div style="display: flex; gap: 8px;">
                  <div style="flex: 1;">
                    <label style="font-size: 11px; font-weight: 700; color: #34d399; display: block; margin-bottom: 4px;">上揚色:</label>
                    <input type="color" id="remotion-kcurve-upper-color" value="#10B981" style="width: 100%; height: 35px; background: #040812; border: 1px solid #10b981; border-radius: 6px; cursor: pointer;">
                  </div>
                  <div style="flex: 1;">
                    <label style="font-size: 11px; font-weight: 700; color: #f87171; display: block; margin-bottom: 4px;">下探色:</label>
                    <input type="color" id="remotion-kcurve-lower-color" value="#EF4444" style="width: 100%; height: 35px; background: #040812; border: 1px solid #ef4444; border-radius: 6px; cursor: pointer;">
                  </div>
                </div>
              </div>

              <!-- 4. StatNumberScene Form -->
              <div id="remotion-params-StatNumberScene" style="display: none; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 14px;">
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #34d399; display: block; margin-bottom: 4px;">核心數值 (Value):</label>
                  <input type="number" id="remotion-stat-value" value="" placeholder="例：2000" step="any" style="width: 100%; font-size: 13px; padding: 7px 10px; background: #040812; border: 1.5px solid #10b981; border-radius: 6px; color: #34d399; font-weight: 800; font-family: monospace;">
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 4px;">前綴 (Prefix):</label>
                  <input type="text" id="remotion-stat-prefix" value="" placeholder="例：超過、突破" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;">
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 4px;">單位 / 後綴 (Unit):</label>
                  <input type="text" id="remotion-stat-unit" value="" placeholder="例：億美元、%、萬人" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;">
                </div>
                <div>
                  <label style="font-size: 11px; font-weight: 700; color: #94a3b8; display: block; margin-bottom: 4px;">小數位數 (Decimals):</label>
                  <input type="number" id="remotion-stat-decimals" value="0" min="0" max="3" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;">
                </div>
                <div style="grid-column: span 2;">
                  <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 4px;">指標名稱 (Label):</label>
                  <input type="text" id="remotion-stat-label" value="" placeholder="例：四大科技巨頭年度資本支出" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff; font-weight: 700;">
                </div>
                <div style="grid-column: span 2;">
                  <label style="font-size: 11px; font-weight: 700; color: #93c5fd; display: block; margin-bottom: 4px;">說明敘述 (Subtext):</label>
                  <input type="text" id="remotion-stat-subtext" value="" placeholder="例：創下歷史新高，AI 運算硬體投入持續擴張" style="width: 100%; font-size: 12px; padding: 7px 10px; background: #040812; border: 1px solid #1e3a8a; border-radius: 6px; color: #fff;">
                </div>
              </div>

              <!-- 5. Legacy Cards Form (TechCard, MinimalistCard, CinemaImpactCard) -->
              <div id="remotion-params-cards" style="display: none; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 14px;">
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

              <!-- Action Buttons -->
              <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                <button id="remotion-render-btn" class="btn-primary" style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); border: 1px solid #38bdf8; font-weight: 700; padding: 9px 18px; font-size: 12px; border-radius: 6px; cursor: pointer; display: flex; align-items: center; gap: 6px;" onclick="renderAndApplyRemotionClip()">
                  ⚡ 算繪並套用至分鏡
                </button>
                <button id="remotion-preview-btn" class="btn-secondary" style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #818cf8; color: #c7d2fe; font-weight: 700; padding: 9px 18px; font-size: 12px; border-radius: 6px; cursor: pointer; display: flex; align-items: center; gap: 6px;" onclick="previewStandaloneRemotionClip()">
                  👁️ 一鍵預覽 MP4 算繪
                </button>
                <div id="remotion-status-text" style="font-size: 12px; color: #94a3b8;"></div>
              </div>"""

if old_markup in content:
    content = content.replace(old_markup, new_markup, 1)
    print("Markup replaced successfully!")
else:
    c_norm = content.replace("\r\n", "\n")
    old_norm = old_markup.replace("\r\n", "\n")
    if old_norm in c_norm:
        c_norm = c_norm.replace(old_norm, new_markup.replace("\r\n", "\n"), 1)
        content = c_norm.replace("\n", "\r\n")
        print("Markup replaced via LF normalization!")
    else:
        print("FAILED to find old_markup")

ui_path.write_text(content, encoding="utf-8")
print("Done writing ui/index.html")
