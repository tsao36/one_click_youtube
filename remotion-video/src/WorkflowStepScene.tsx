import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ModernExplainerBackground } from "./ModernExplainerBackground";
import { WorkflowStepSceneProps } from "./types";

export const WorkflowStepScene: React.FC<WorkflowStepSceneProps> = ({
  badge = "ITERATIVE PIPELINE",
  title = "極限推進的三段式工作流程",
  subtitle = "從模糊意圖到可驗收的具體交付物",
  steps = [
    {
      stepNumber: "01",
      label: "界定成果規格 (Define Deliverable)",
      detail: "明確產出形式、目標客群、驗收指標與限制條件，拒絕模糊要求。",
      tag: "SPECIFICATION",
    },
    {
      stepNumber: "02",
      label: "專家視角挑戰 (Critical Interrogation)",
      detail: "讓 AI 扮演最嚴格的審計員或架構師，在執行前主動找出潛在致命漏洞。",
      tag: "AUDITING",
    },
    {
      stepNumber: "03",
      label: "多分支並行探索 (Parallel Divergence)",
      detail: "同步生成 3-5 種不同風格或策略原型，快速評估並進行優勢整合。",
      tag: "SYNTHESIS",
    },
  ],
  activeStepIndex = 1,
  accentColor = "#38BDF8",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Top header spring
  const hSpring = spring({ frame, fps, config: { mass: 0.5, damping: 14, stiffness: 120 } });
  const hOpacity = interpolate(hSpring, [0, 1], [0, 1]);
  const hY = interpolate(hSpring, [0, 1], [-25, 0]);

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
          padding: "65px 100px",
          boxSizing: "border-box",
        }}
      >
        {/* Header */}
        <div style={{ opacity: hOpacity, transform: `translateY(${hY}px)`, marginBottom: 40 }}>
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
              marginBottom: 12,
            }}
          >
            <span style={{ fontSize: 18 }}>🔄</span>
            {badge}
          </div>

          <div style={{ fontSize: 50, fontWeight: 800, color: "#FFFFFF", letterSpacing: "-0.02em", lineHeight: 1.2 }}>
            {title}
          </div>

          {subtitle && (
            <div style={{ fontSize: 24, color: "#94A3B8", marginTop: 10, fontWeight: 500, lineHeight: 1.4 }}>
              {subtitle}
            </div>
          )}
        </div>

        {/* Steps Pipeline Horizontal Row */}
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "stretch",
            gap: 24,
            position: "relative",
          }}
        >
          {steps.map((step, idx) => {
            const delay = 8 + idx * 7;
            const sSpring = spring({
              frame: Math.max(0, frame - delay),
              fps,
              config: { mass: 0.6, damping: 14, stiffness: 110 },
            });
            const sOpacity = interpolate(sSpring, [0, 1], [0, 1]);
            const sScale = interpolate(sSpring, [0, 1], [0.92, 1]);
            const sY = interpolate(sSpring, [0, 1], [30, 0]);

            const isActive = idx === activeStepIndex;
            const detailFontSize = step.detail.length < 50 ? 21 : 18.5;

            return (
              <React.Fragment key={idx}>
                {/* Step Card */}
                <div
                  style={{
                    flex: 1,
                    opacity: sOpacity,
                    transform: `translateY(${sY}px) scale(${sScale})`,
                    borderRadius: 22,
                    padding: 32,
                    background: isActive
                      ? "linear-gradient(180deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%)"
                      : "rgba(15, 23, 42, 0.65)",
                    border: isActive
                      ? `2px solid ${accentColor}`
                      : "1px solid rgba(255, 255, 255, 0.1)",
                    boxShadow: isActive
                      ? `0 18px 48px rgba(56, 189, 248, 0.22), inset 0 1px 0 rgba(255,255,255,0.18)`
                      : "0 8px 26px rgba(0,0,0,0.35)",
                    backdropFilter: "blur(16px)",
                    display: "flex",
                    flexDirection: "column",
                    position: "relative",
                  }}
                >
                  {/* Top Light Bar */}
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

                  {/* Number & Tag Header */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
                    <span
                      style={{
                        fontFamily: "monospace",
                        fontSize: 42,
                        fontWeight: 800,
                        color: isActive ? accentColor : "#64748B",
                        lineHeight: 1,
                      }}
                    >
                      {step.stepNumber}
                    </span>
                    {step.tag && (
                      <span
                        style={{
                          fontSize: 15,
                          fontWeight: 700,
                          padding: "5px 12px",
                          borderRadius: 10,
                          background: isActive ? `${accentColor}28` : "rgba(255,255,255,0.08)",
                          color: isActive ? accentColor : "#CBD5E1",
                          border: isActive ? `1.5px solid ${accentColor}55` : "1px solid rgba(255,255,255,0.12)",
                        }}
                      >
                        {step.tag}
                      </span>
                    )}
                  </div>

                  {/* Step Label */}
                  <div
                    style={{
                      fontSize: 28,
                      fontWeight: 700,
                      color: isActive ? "#FFFFFF" : "#F1F5F9",
                      lineHeight: 1.3,
                      marginBottom: 16,
                    }}
                  >
                    {step.label}
                  </div>

                  {/* Step Detail */}
                  <div
                    style={{
                      fontSize: detailFontSize,
                      lineHeight: 1.6,
                      color: isActive ? "#E2E8F0" : "#94A3B8",
                      fontWeight: 500,
                    }}
                  >
                    {step.detail}
                  </div>
                </div>

                {/* Arrow Connector between steps */}
                {idx < steps.length - 1 && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: accentColor,
                      fontSize: 32,
                      opacity: sOpacity * 0.8,
                    }}
                  >
                    ➔
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
