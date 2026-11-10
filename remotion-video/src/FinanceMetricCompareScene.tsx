import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FinanceBackground } from "./FinanceBackground";
import { FinanceMetricCompareSceneProps } from "./types";
import {
  GlintSheen,
  RadarBeacon,
  useContinuousDrift,
} from "./animations";

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
  const { floatY, glowPulse } = useContinuousDrift(0.0002);

  const entrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 95 },
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
          transform: `scale(${entrance}) translateY(${floatY}px)`,
          opacity: entrance,
          justifyContent: "space-between",
        }}
      >
        {/* Header */}
        <div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              backgroundColor: "rgba(16, 185, 129, 0.15)",
              color: accentColor,
              border: `1.5px solid ${accentColor}`,
              borderRadius: 6,
              padding: "4px 14px",
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: 1,
              marginBottom: 10,
              boxShadow: `0 0 ${10 * glowPulse}px ${accentColor}44`,
            }}
          >
            <RadarBeacon color={accentColor} size={6} />
            <span>{badge}</span>
          </div>
          <div style={{ fontSize: 34, fontWeight: 900, color: "#FFFFFF" }}>{title}</div>
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
          {bars.map((b: any, idx: number) => {
            const barSpring = spring({
              frame: frame - (8 + idx * 4),
              fps,
              config: { damping: 14, stiffness: 100 },
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
                  opacity: barSpring,
                }}
              >
                {/* Metric Growth Tag */}
                <div
                  style={{
                    backgroundColor: b.isHighlight ? `${accentColor}25` : "rgba(2, 132, 199, 0.2)",
                    border: `1px solid ${b.isHighlight ? accentColor : "rgba(2, 132, 199, 0.5)"}`,
                    color: b.isHighlight ? accentColor : "#38BDF8",
                    padding: "3px 8px",
                    borderRadius: 4,
                    fontSize: 12,
                    fontWeight: 800,
                    marginBottom: 8,
                    transform: `scale(${interpolate(barSpring, [0, 1], [0.7, 1])})`,
                  }}
                >
                  {b.growth}
                </div>

                {/* Animated Growing Bar */}
                <div
                  style={{
                    width: "100%",
                    maxWidth: 110,
                    height: Math.max(12, currentHeight),
                    backgroundColor: barColor,
                    borderRadius: "6px 6px 0 0",
                    boxShadow: b.isHighlight
                      ? `0 0 24px ${accentColor}88`
                      : "0 0 14px rgba(2, 132, 199, 0.4)",
                    position: "relative",
                  }}
                >
                  {/* Top Glowing Edge Line */}
                  <div
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      right: 0,
                      height: 3,
                      backgroundColor: "#FFFFFF",
                      borderRadius: "6px 6px 0 0",
                      opacity: 0.8,
                    }}
                  />
                </div>

                {/* Value & Label */}
                <div
                  style={{
                    marginTop: 12,
                    textAlign: "center",
                  }}
                >
                  <div
                    style={{
                      fontSize: 18,
                      fontWeight: 900,
                      color: b.isHighlight ? "#FFFFFF" : "#CBD5E1",
                      fontFamily: "monospace",
                    }}
                  >
                    {b.value}
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: "#64748B",
                      marginTop: 2,
                    }}
                  >
                    {b.label}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Summary Card with Glint Sheen */}
        <div
          style={{
            position: "relative",
            backgroundColor: "rgba(15, 23, 42, 0.85)",
            border: `1.5px solid ${accentColor}44`,
            borderRadius: 10,
            padding: "16px 24px",
            display: "flex",
            alignItems: "center",
            gap: 16,
            overflow: "hidden",
            marginTop: 16,
          }}
        >
          <GlintSheen color={`${accentColor}55`} periodFrames={90} />
          <div style={{ fontSize: 24, color: accentColor }}>💡</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#E2E8F0", lineHeight: 1.45 }}>
            {summary}
          </div>
        </div>
      </div>
    </FinanceBackground>
  );
};
