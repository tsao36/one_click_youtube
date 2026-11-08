import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FinanceBackground } from "./FinanceBackground";
import { FinanceMetricCompareSceneProps } from "./types";

export const FinanceMetricCompareScene: React.FC<FinanceMetricCompareSceneProps> = ({
  badge = "FINANCIAL BENCHMARK",
  title = "營收成長與獲利能力對比",
  subtitle = "各季度營運現金流與毛利率變化軌跡",
  bars = [
    { label: "2023 Q3", value: "$18.1B", growth: "+206%", heightPct: 0.35, isHighlight: false },
    { label: "2023 Q4", value: "$22.1B", growth: "+265%", heightPct: 0.48, isHighlight: false },
    { label: "2024 Q1", value: "$26.0B", growth: "+262%", heightPct: 0.65, isHighlight: false },
    { label: "2024 Q2", value: "$30.0B", growth: "+122%", heightPct: 0.82, isHighlight: false },
    { label: "2024 Q3 (預估)", value: "$35.0B", growth: "+93%", heightPct: 1.0, isHighlight: true },
  ],
  summary = "連續 5 個季度創歷史新高，資料中心算力需求持續大於供給，定價權極高",
  accentColor = "#10B981",
  bgSrc = "",
  dim = 0.35,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
  });

  return (
    <FinanceBackground bgSrc={bgSrc} dim={dim} accentColor={accentColor}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          height: "100%",
          padding: "36px 70px",
          boxSizing: "border-box",
          transform: `scale(${entrance})`,
          opacity: entrance,
          justifyContent: "space-between",
        }}
      >
        {/* Header */}
        <div>
          <div
            style={{
              display: "inline-block",
              backgroundColor: "rgba(16, 185, 129, 0.15)",
              color: accentColor,
              border: `1.5px solid ${accentColor}`,
              borderRadius: 6,
              padding: "3px 12px",
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: 1,
              marginBottom: 8,
            }}
          >
            {badge}
          </div>
          <div style={{ fontSize: 32, fontWeight: 900, color: "#FFFFFF" }}>{title}</div>
          {subtitle && (
            <div style={{ fontSize: 16, fontWeight: 600, color: "#94A3B8", marginTop: 4 }}>
              {subtitle}
            </div>
          )}
        </div>

        {/* Bar Chart Container */}
        <div
          style={{
            flex: 1,
            display: "grid",
            gridTemplateColumns: `repeat(${bars.length}, 1fr)`,
            gap: 24,
            alignItems: "flex-end",
            padding: "20px 20px 0 20px",
            maxHeight: 380,
          }}
        >
          {bars.map((b, idx) => {
            const barSpring = spring({
              frame: frame - idx * 4,
              fps,
              config: { damping: 14, stiffness: 90 },
            });

            const currentHeight = (b.heightPct || 0.5) * 260 * barSpring;
            const barColor = b.isHighlight ? accentColor : "#0284C7";

            return (
              <div
                key={idx}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  height: "100%",
                  justifyContent: "flex-end",
                }}
              >
                {/* Growth Pill */}
                <div
                  style={{
                    backgroundColor: b.isHighlight ? "rgba(16, 185, 129, 0.2)" : "rgba(30, 41, 59, 0.8)",
                    border: `1px solid ${b.isHighlight ? accentColor : "#334155"}`,
                    color: b.isHighlight ? accentColor : "#38BDF8",
                    fontSize: 13,
                    fontWeight: 800,
                    padding: "3px 8px",
                    borderRadius: 4,
                    marginBottom: 8,
                    fontFamily: "monospace",
                  }}
                >
                  {b.growth}
                </div>

                {/* Main Bar Column */}
                <div
                  style={{
                    width: "80%",
                    maxWidth: 110,
                    height: currentHeight,
                    background: b.isHighlight
                      ? `linear-gradient(180deg, ${accentColor} 0%, rgba(16, 185, 129, 0.3) 100%)`
                      : `linear-gradient(180deg, #38BDF8 0%, rgba(56, 189, 248, 0.25) 100%)`,
                    borderRadius: "8px 8px 0 0",
                    border: `1.5px solid ${b.isHighlight ? accentColor : "#38BDF8"}`,
                    boxShadow: b.isHighlight ? `0 0 24px ${accentColor}50` : "none",
                    position: "relative",
                  }}
                >
                  {/* Top value */}
                  <div
                    style={{
                      position: "absolute",
                      top: 10,
                      left: 0,
                      right: 0,
                      textAlign: "center",
                      fontSize: 16,
                      fontWeight: 900,
                      color: "#FFFFFF",
                      fontFamily: "monospace",
                    }}
                  >
                    {b.value}
                  </div>
                </div>

                {/* X-Axis Label */}
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 700,
                    color: b.isHighlight ? "#FFFFFF" : "#94A3B8",
                    marginTop: 10,
                    textAlign: "center",
                  }}
                >
                  {b.label}
                </div>
              </div>
            );
          })}
        </div>

        {/* Bottom Insight Takeaway Banner */}
        {summary && (
          <div
            style={{
              backgroundColor: "rgba(15, 23, 42, 0.85)",
              border: "1px solid rgba(56, 189, 248, 0.2)",
              borderRadius: 8,
              padding: "12px 20px",
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginTop: 16,
            }}
          >
            <span style={{ fontSize: 18 }}>📊</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#E2E8F0" }}>{summary}</span>
          </div>
        )}
      </div>
    </FinanceBackground>
  );
};
