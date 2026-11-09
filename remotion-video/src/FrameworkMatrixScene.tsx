import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ModernExplainerBackground } from "./ModernExplainerBackground";
import { FrameworkMatrixSceneProps } from "./types";

export const FrameworkMatrixScene: React.FC<FrameworkMatrixSceneProps> = ({
  badge = "THE 4-PILLAR FRAMEWORK",
  title = "用 AI 更有野心的四個維度",
  subtitle = "速度 · 高度 · 深度 · 廣度 — 打破玩具心態的關鍵架構",
  pillars = [
    {
      id: "p1",
      title: "高度 (Height)",
      subtitle: "從要過程到直接要成果",
      icon: "🎯",
      metric: "結果導向",
      points: ["不只是問寫封信，而是要求完成整個季報", "設定清晰的驗收標準與交付物"],
      isHighlighted: true,
    },
    {
      id: "p2",
      title: "深度 (Depth)",
      subtitle: "像該領域的資深專家一樣思考",
      icon: "🧠",
      metric: "思維層次",
      points: ["導入專業框架與反直覺觀點", "要求批判性挑戰而非盲目迎合"],
      isHighlighted: false,
    },
    {
      id: "p3",
      title: "廣度 (Breadth)",
      subtitle: "跨領域整合與交叉驗證",
      icon: "🌐",
      metric: "多視角覆蓋",
      points: ["從法務、行銷、技術多維度審視", "打破單一職能的信息繭房"],
      isHighlighted: false,
    },
    {
      id: "p4",
      title: "速度 (Speed)",
      subtitle: "極速迭代與並行探索",
      icon: "⚡",
      metric: "反饋迴圈",
      points: ["數分鐘內生成 10 種方向並行篩選", "降低嘗試成本，將精力放在決策"],
      isHighlighted: false,
    },
  ],
  activePillarId = "p1",
  accentColor = "#38BDF8",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Header animation with snappy spring
  const headerSpring = spring({
    frame,
    fps,
    config: { mass: 0.5, damping: 14, stiffness: 120 },
  });
  const headerOpacity = interpolate(headerSpring, [0, 1], [0, 1]);
  const headerY = interpolate(headerSpring, [0, 1], [-30, 0]);

  return (
    <AbsoluteFill
      style={{
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        color: "#F8FAFC",
        overflow: "hidden",
      }}
    >
      <ModernExplainerBackground accentColor={accentColor} dim={0.4} />

      <div
        style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          width: "100%",
          height: "100%",
          padding: "70px 100px",
          boxSizing: "border-box",
        }}
      >
        {/* Top Header Bar */}
        <div
          style={{
            opacity: headerOpacity,
            transform: `translateY(${headerY}px)`,
            marginBottom: 44,
          }}
        >
          {/* Badge */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "7px 18px",
              borderRadius: 20,
              background: "rgba(56, 189, 248, 0.14)",
              border: `1.5px solid ${accentColor}60`,
              color: accentColor,
              fontSize: 16,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginBottom: 14,
            }}
          >
            <span style={{ fontSize: 12 }}>●</span>
            {badge}
          </div>

          {/* Title */}
          <div
            style={{
              fontSize: 52,
              fontWeight: 800,
              letterSpacing: "-0.02em",
              lineHeight: 1.15,
              color: "#FFFFFF",
              textShadow: "0 2px 20px rgba(0,0,0,0.6)",
            }}
          >
            {title}
          </div>

          {subtitle && (
            <div
              style={{
                fontSize: 24,
                color: "#94A3B8",
                marginTop: 10,
                fontWeight: 500,
                lineHeight: 1.4,
              }}
            >
              {subtitle}
            </div>
          )}
        </div>

        {/* Pillars Grid */}
        <div
          style={{
            flex: 1,
            display: "grid",
            gridTemplateColumns: `repeat(${pillars.length}, 1fr)`,
            gap: 24,
            alignItems: "stretch",
          }}
        >
          {pillars.map((pillar, idx) => {
            const delay = 8 + idx * 5;
            const pSpring = spring({
              frame: Math.max(0, frame - delay),
              fps,
              config: { mass: 0.6, damping: 15, stiffness: 110 },
            });
            const pOpacity = interpolate(pSpring, [0, 1], [0, 1]);
            const pScale = interpolate(pSpring, [0, 1], [0.92, 1]);
            const pY = interpolate(pSpring, [0, 1], [40, 0]);

            const isActive = pillar.id === activePillarId || pillar.isHighlighted;
            const ptFontSize = pillars.length <= 2 ? 22 : pillars.length === 3 ? 19 : 17;

            return (
              <div
                key={pillar.id}
                style={{
                  opacity: pOpacity,
                  transform: `translateY(${pY}px) scale(${pScale})`,
                  display: "flex",
                  flexDirection: "column",
                  padding: 30,
                  borderRadius: 22,
                  background: isActive
                    ? "linear-gradient(180deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%)"
                    : "rgba(15, 23, 42, 0.65)",
                  border: isActive
                    ? `2px solid ${accentColor}`
                    : "1px solid rgba(255, 255, 255, 0.1)",
                  boxShadow: isActive
                    ? `0 14px 44px rgba(56, 189, 248, 0.22), inset 0 1px 0 rgba(255,255,255,0.2)`
                    : "0 8px 30px rgba(0,0,0,0.35)",
                  backdropFilter: "blur(16px)",
                  position: "relative",
                  overflow: "hidden",
                }}
              >
                {/* Active Indicator Top Light Bar */}
                {isActive && (
                  <div
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      right: 0,
                      height: 4,
                      background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,
                    }}
                  />
                )}

                {/* Card Header */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <span style={{ fontSize: 42 }}>{pillar.icon || "⚡"}</span>
                  {pillar.metric && (
                    <span
                      style={{
                        fontSize: 16,
                        fontWeight: 700,
                        padding: "6px 14px",
                        borderRadius: 14,
                        background: isActive ? `${accentColor}28` : "rgba(255,255,255,0.08)",
                        color: isActive ? accentColor : "#CBD5E1",
                        border: isActive ? `1.5px solid ${accentColor}55` : "1px solid rgba(255,255,255,0.12)",
                      }}
                    >
                      {pillar.metric}
                    </span>
                  )}
                </div>

                {/* Pillar Title */}
                <div
                  style={{
                    fontSize: 30,
                    fontWeight: 700,
                    color: isActive ? "#FFFFFF" : "#F1F5F9",
                    marginBottom: 8,
                    lineHeight: 1.25,
                  }}
                >
                  {pillar.title}
                </div>

                {pillar.subtitle && (
                  <div
                    style={{
                      fontSize: 18,
                      color: isActive ? "#BAE6FD" : "#94A3B8",
                      marginBottom: 18,
                      fontWeight: 500,
                      lineHeight: 1.4,
                    }}
                  >
                    {pillar.subtitle}
                  </div>
                )}

                {/* Key Bullet Points */}
                {pillar.points && pillar.points.length > 0 && (
                  <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
                    {pillar.points.map((pt, pIdx) => (
                      <div
                        key={pIdx}
                        style={{
                          fontSize: ptFontSize,
                          lineHeight: 1.5,
                          color: "#E2E8F0",
                          display: "flex",
                          alignItems: "flex-start",
                          gap: 10,
                          fontWeight: 500,
                        }}
                      >
                        <span style={{ color: accentColor, fontWeight: 800, fontSize: ptFontSize + 2, lineHeight: 1 }}>›</span>
                        <span>{pt}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
