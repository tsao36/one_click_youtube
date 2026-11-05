# encoding: utf-8
with open("ui/index.html", "rb") as f:
    content = f.read().decode("utf-8")

# 1. Add enforceMainCharacterRealRatio button in header
old_hdr_btns = """              <button type="button" class="btn-primary" style="font-size: 11px; padding: 6px 14px; background: linear-gradient(135deg, #059669 0%, #047857 100%); font-weight: 700; border: 1px solid #10b981;" onclick="applyApprovedCharacterMedia(${isInspector})">
                🔗 一鍵套用至對應分鏡
              </button>"""

new_hdr_btns = """              <button type="button" class="btn-primary" style="font-size: 11px; padding: 6px 14px; background: linear-gradient(135deg, #e11d48 0%, #be123c 100%); font-weight: 700; border: 1px solid #f43f5e;" onclick="enforceMainCharacterRealRatio(${isInspector})">
                ⚡ 確保主角分鏡 ≥ 90% 真實素材
              </button>
              <button type="button" class="btn-primary" style="font-size: 11px; padding: 6px 14px; background: linear-gradient(135deg, #059669 0%, #047857 100%); font-weight: 700; border: 1px solid #10b981;" onclick="applyApprovedCharacterMedia(${isInspector})">
                🔗 一鍵套用至對應分鏡
              </button>"""

if old_hdr_btns in content:
    content = content.replace(old_hdr_btns, new_hdr_btns, 1)
else:
    old_crlf = old_hdr_btns.replace("\n", "\r\n")
    assert old_crlf in content, "old_hdr_btns not found"
    content = content.replace(old_crlf, new_hdr_btns.replace("\n", "\r\n"), 1)

# 2. Add 90% option in select
old_opt = """<option value="0.7" selected>70% 實拍影片 (~10s) + 30% 劇照 (推薦)</option>"""
new_opt = """<option value="0.9" selected>90% 真實素材 (實拍影片+真實劇照) · 主角分鏡優先 (推薦)</option>
                    <option value="0.7">70% 實拍影片 (~10s) + 30% 劇照</option>"""

assert old_opt in content or old_opt.replace("\n", "\r\n") in content, "old_opt not found"
content = content.replace(old_opt, new_opt, 1) if old_opt in content else content.replace(old_opt.replace("\n", "\r\n"), new_opt.replace("\n", "\r\n"), 1)

# 3. Add enforceMainCharacterRealRatio function
old_boost_func_end = """        } else {
          alert("處理失敗: " + JSON.stringify(result));
        }
      } catch (e) {
        alert("操作失敗: " + e.message);
      }
    }"""

new_boost_func_end = """        } else {
          alert("處理失敗: " + JSON.stringify(result));
        }
      } catch (e) {
        alert("操作失敗: " + e.message);
      }
    }

    async function enforceMainCharacterRealRatio(isInspector) {
      if (!currentProjectId) return alert("請先選取專案");
      if (!confirm("確定要將主角提及分鏡的真實素材（實拍影片與劇照）提高至 90% 以上嗎？\\n\\n系統將自動分析所有提及主角的分鏡，自動抓取並裁切約 10 秒 YouTube 實拍片段與真實劇照覆蓋 AI 生成圖。")) {
        return;
      }
      try {
        if (typeof showToast === 'function') showToast("⚡ 正在分析主角登場分鏡並提高真實影音佔比至 90% (需數十秒)...");
        const res = await fetch(`/api/projects/${currentProjectId}/characters/enforce_real_ratio`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ratio: 0.9, clip_ratio: 0.7 })
        });
        const result = await res.json();
        if (result.status === 'success') {
          const updated = result.updated_scenes || [];
          alert(`✓ 成功確保主角「${result.character}」分鏡真實影音佔比達 ${result.real_percentage}%！\\n\\n主角登場分鏡: ${result.total_mentioned_scenes} 個\\n已覆蓋真實素材: ${result.real_scenes_count} 個 (${result.real_percentage}%)\\n本次新更新分鏡: [${updated.join(', ')}]\\n\\n請前往 Stage 10 點擊「Render 1080p Video」合成最新畫面！`);
          if (typeof loadStageStudio === 'function') loadStageStudio('research');
        } else {
          alert("處理結果: " + JSON.stringify(result));
        }
      } catch (e) {
        alert("操作失敗: " + e.message);
      }
    }"""

if old_boost_func_end in content:
    content = content.replace(old_boost_func_end, new_boost_func_end, 1)
else:
    old_crlf_end = old_boost_func_end.replace("\n", "\r\n")
    assert old_crlf_end in content, "old_boost_func_end not found"
    content = content.replace(old_crlf_end, new_boost_func_end.replace("\n", "\r\n"), 1)

with open("ui/index.html", "wb") as f:
    f.write(content.encode("utf-8"))

print("ui/index.html successfully updated with 90% ratio controls!")
