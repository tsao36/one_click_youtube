import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ModernExplainerBackground } from "./ModernExplainerBackground";
import { PromptComparisonSceneProps } from "./types";

export const PromptComparisonScene: React.FC<PromptComparisonSceneProps> = ({
  badge = "PROMPT STRATEGY COMPARISON",
  title = "高度：普通人 vs 高手的提問思維",
  subtitle = "同一個 AI 工具，差別不在指令多長，而在你的要求有沒有「野心」",
  leftBadge = "一般用法 (Basic)",
  leftTitle = "交出過程，讓自己繼續做苦工",
  leftContent = "「請幫我寫一封信催客戶繳款，語氣要禮貌但堅定。」\n\n結果：AI 給了一段通用範本，你還得自己修改、複製貼上、確認進度，省下 2 分鐘，但核心問題毫無推進。",
  leftTags = ["缺乏交付標準", "局限單一動作", "被動執行者"],
  rightBadge = "高手做法 (Ambitious)",
  rightTitle = "交出成果，讓 AI 成為專案合夥人",
  rightContent = "「我們是一家 SaaS 公司，面臨 Q3 續約率下滑 15%。請以資深客戶成功總監的視角：\n1. 診斷三大流失原因\n2. 設計分級挽回話術與誘因方案\n3. 輸出完整的即戰力執行清單與指標看板。」",
  rightTags = ["設定專家角色", "明確商業成果", "端到端交付"],
  takeaway = "💡 核心轉變：從「幫我寫」到「幫我解決問題並產出最終成果」",
  accentColor = "#38BDF8",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Header spring
  const hSpring = spring({ frame, fps, config: { mass: 0.5, damping: 14, stiffness: 120 } });
  const hOpacity = interpolate(hSpring, [0, 1], [0, 1]);
  const hY = interpolate(hSpring, [0, 1], [-25, 0]);

  // Left card spring
  const lSpring = spring({ frame: Math.max(0, frame - 6), fps, config: { mass: 0.6, damping: 14, stiffness: 110 } });
  const lOpacity = interpolate(lSpring, [0, 1], [0, 1]);
  const lX = interpolate(lSpring, [0, 1], [-40, 0]);

  // Right card spring
  const rSpring = spring({ frame: Math.max(0, frame - 12), fps, config: { mass: 0.6, damping: 14, stiffness: 110 } });
  const rOpacity = interpolate(rSpring, [0, 1], [0, 1]);
  const rX = interpolate(rSpring, [0, 1], [40, 0]);

  // Bottom takeaway spring
  const bSpring = spring({ frame: Math.max(0, frame - 22), fps, config: { mass: 0.5, damping: 12, stiffness: 100 } });
  const bOpacity = interpolate(bSpring, [0, 1], [0, 1]);
  const bY = interpolate(bSpring, [0, 1], [20, 0]);

  return (
    <AbsoluteFill
      style={{
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        color: "#F8FAFC",
        overflow: "hidden",
      }}
    >
      <ModernExplainerBackground accentColor={accentColor} dim={0.45} />

      <div
        style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          width: "100%",
          height: "100%",
          padding: "60px 90px",
          boxSizing: "border-box",
        }}
      >
        {/* Header */}
        <div style={{ opacity: hOpacity, transform: `translateY(${hY}px)`, marginBottom: 32 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "5px 12px",
              borderRadius: 16,
              background: "rgba(56, 189, 248, 0.12)",
              border: `1px solid ${accentColor}50`,
              color: accentColor,
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginBottom: 10,
            }}
          >
            <span>⚖️</span>
            {badge}
          </div>

          <div style={{ fontSize: 44, fontWeight: 800, color: "#FFFFFF", letterSpacing: "-0.02em" }}>
            {title}
          </div>

          {subtitle && (
            <div style={{ fontSize: 18, color: "#94A3B8", marginTop: 6, fontWeight: 400 }}>
              {subtitle}
            </div>
          )}
        </div>

        {/* 2 Comparison Cards */}
        <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28, alignItems: "stretch" }}>
          {/* Left Card: Basic */}
          <div
            style={{
              opacity: lOpacity,
              transform: `translateX(${lX}px)`,
              display: "flex",
              flexDirection: "column",
              padding: 32,
              borderRadius: 20,
              background: "rgba(15, 23, 42, 0.65)",
              border: "1px solid rgba(248, 113, 113, 0.25)",
              boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
              backdropFilter: "blur(16px)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "4px 10px",
                  borderRadius: 10,
                  background: "rgba(239, 68, 68, 0.15)",
                  color: "#F87171",
                  border: "1px solid rgba(239, 68, 68, 0.35)",
                }}
              >
                ✕ {leftBadge}
              </span>
            </div>

            <div style={{ fontSize: 22, fontWeight: 700, color: "#F1F5F9", marginBottom: 16, lineHeight: 1.3 }}>
              {leftTitle}
            </div>

            <div
              style={{
                fontSize: 15,
                color: "#94A3B8",
                lineHeight: 1.6,
                background: "rgba(0, 0, 0, 0.3)",
                padding: "16px 18px",
                borderRadius: 12,
                border: "1px solid rgba(255, 255, 255, 0.05)",
                whiteSpace: "pre-wrap",
                fontFamily: "monospace",
                flex: 1,
              }}
            >
              {leftContent}
            </div>

            {leftTags && leftTags.length > 0 && (
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 18 }}>
                {leftTags.map((tag, i) => (
                  <span
                    key={i}
                    style={{
                      fontSize: 12,
                      color: "#EF4444",
                      background: "rgba(239, 68, 68, 0.08)",
                      padding: "4px 8px",
                      borderRadius: 6,
                    }}
                  >
                    • {tag}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Right Card: Ambitious / Pro */}
          <div
            style={{
              opacity: rOpacity,
              transform: `translateX(${rX}px)`,
              display: "flex",
              flexDirection: "column",
              padding: 32,
              borderRadius: 20,
              background: "linear-gradient(180deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%)",
              border: `1.5px solid ${accentColor}`,
              boxShadow: `0 12px 40px rgba(56, 189, 248, 0.22), inset 0 1px 0 rgba(255,255,255,0.18)`,
              backdropFilter: "blur(16px)",
              position: "relative",
            }}
          >
            {/* Top Light Accent */}
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                height: 3,
                background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,
              }}
            />

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "4px 10px",
                  borderRadius: 10,
                  background: `${accentColor}25`,
                  color: accentColor,
                  border: `1px solid ${accentColor}60`,
                }}
              >
                ✓ {rightBadge}
              </span>
            </div>

            <div style={{ fontSize: 22, fontWeight: 700, color: "#FFFFFF", marginBottom: 16, lineHeight: 1.3 }}>
              {rightTitle}
            </div>

            <div
              style={{
                fontSize: 15,
                color: "#E2E8F0",
                lineHeight: 1.6,
                background: "rgba(2, 6, 23, 0.6)",
                padding: "16px 18px",
                borderRadius: 12,
                border: `1px solid ${accentColor}30`,
                whiteSpace: "pre-wrap",
                fontFamily: "monospace",
                flex: 1,
              }}
            >
              {rightContent}
            </div>

            {rightTags && rightTags.length > 0 && (
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 18 }}>
                {rightTags.map((tag, i) => (
                  <span
                    key={i}
                    style={{
                      fontSize: 12,
                      color: "#38BDF8",
                      background: "rgba(56, 189, 248, 0.12)",
                      padding: "4px 8px",
                      borderRadius: 6,
                      fontWeight: 600,
                    }}
                  >
                    ✓ {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Bottom Takeaway */}
        {takeaway && (
          <div
            style={{
              opacity: bOpacity,
              transform: `translateY(${bY}px)`,
              marginTop: 22,
              padding: "12px 20px",
              borderRadius: 12,
              background: "rgba(30, 41, 59, 0.5)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              fontSize: 16,
              color: "#F1F5F9",
              textAlign: "center",
              fontWeight: 600,
            }}
          >
            {takeaway}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
