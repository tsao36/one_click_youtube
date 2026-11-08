import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { CoordinateZeroBackground } from "./CoordinateZeroBackground";
import { CoordinateZeroExperimentSceneProps } from "./types";

export const CoordinateZeroExperimentScene: React.FC<CoordinateZeroExperimentSceneProps> = ({
  experimentNo = "03",
  experimentBadge = "實驗",
  title = "俄羅斯 vs 非洲",
  subtitle = "把俄羅斯搬到赤道做真實面積對比",
  gaugeLabel = "放大倍率",
  currentMagnification = "×4.9",
  gaugePointerPosition = 0.58, // 0 is bottom (x1), 1 is top (x33)
  measurementHeader = "量測",
  measurementTag = "地圖上",
  measurementFormula = "俄羅斯 = 非洲 × 2.5",
  measurementSubtext = "高緯度嚴重拉伸，赤道處才是真實物理尺度",
  accentColor = "#EF4444",
  bgSrc = "",
  dim = 0.15,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Entrance springs
  const cardEntrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 95 },
  });

  const gaugeEntrance = spring({
    frame: frame - 10,
    fps,
    config: { damping: 15, mass: 0.9, stiffness: 85 },
  });

  const formulaEntrance = spring({
    frame: frame - 25,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
  });

  // Pointer needle gliding animation
  const pointerAnim = spring({
    frame: frame - 35,
    fps,
    config: { damping: 18, mass: 1, stiffness: 70 },
  });

  // Calculate pointer vertical percentage (0% bottom to 100% top)
  const pointerYPct = interpolate(
    pointerAnim,
    [0, 1],
    [0.1, gaugePointerPosition],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Underline bar growth
  const barProgress = interpolate(frame, [40, 75], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Gauge ticks data
  const rulerTicks = [
    { label: "×33", pct: 0.92, isMajor: true },
    { label: "×8.5", pct: 0.74, isMajor: true, color: "#EF4444" },
    { label: "×4", pct: 0.58, isMajor: true, color: "#EF4444" },
    { label: "×2", pct: 0.42, isMajor: false },
    { label: "×1.3", pct: 0.28, isMajor: false },
    { label: "×1", pct: 0.16, isMajor: true, isBase: true },
    { label: "×1.3", pct: 0.05, isMajor: false },
  ];

  return (
    <CoordinateZeroBackground bgSrc={bgSrc} dim={dim} showPaper={false}>
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          padding: "50px 70px",
          display: "flex",
          justifyContent: "space-between",
          boxSizing: "border-box",
        }}
      >
        {/* Left Side: Experiment Card & Bottom Telemetry */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            width: "65%",
            height: "100%",
          }}
        >
          {/* Top-Left Experiment Badge Card */}
          <div
            style={{
              backgroundColor: "#FFFFFF",
              borderRadius: 12,
              padding: "16px 24px",
              boxShadow: "0 14px 35px rgba(0,0,0,0.22)",
              display: "inline-flex",
              alignItems: "center",
              gap: 20,
              maxWidth: 580,
              transform: `translateX(${(1 - cardEntrance) * -60}px)`,
              opacity: cardEntrance,
            }}
          >
            {/* Orange/Red Experiment Tag */}
            <div
              style={{
                backgroundColor: accentColor,
                color: "#FFFFFF",
                borderRadius: 8,
                padding: "8px 14px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                minWidth: 64,
              }}
            >
              <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: 1 }}>
                {experimentBadge}
              </span>
              <span style={{ fontSize: 24, fontWeight: 900, lineHeight: 1.1 }}>
                {experimentNo}
              </span>
            </div>

            {/* Title & Subtitle */}
            <div style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ fontSize: 28, fontWeight: 900, color: "#0F172A" }}>
                {title}
              </div>
              {subtitle && (
                <div style={{ fontSize: 16, fontWeight: 600, color: "#64748B", marginTop: 4 }}>
                  {subtitle}
                </div>
              )}
            </div>
          </div>

          {/* Bottom-Left Measurement Formula Card */}
          <div
            style={{
              backgroundColor: "#FFFFFF",
              borderRadius: 14,
              padding: "24px 32px",
              boxShadow: "0 16px 40px rgba(0,0,0,0.25)",
              maxWidth: 560,
              transform: `translateY(${(1 - formulaEntrance) * 50}px)`,
              opacity: formulaEntrance,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                marginBottom: 14,
              }}
            >
              <span style={{ fontSize: 15, fontWeight: 800, color: "#475569" }}>
                {measurementHeader}
              </span>
              {measurementTag && (
                <span
                  style={{
                    backgroundColor: "#FEE2E2",
                    color: "#DC2626",
                    fontSize: 13,
                    fontWeight: 800,
                    padding: "3px 10px",
                    borderRadius: 6,
                  }}
                >
                  {measurementTag}
                </span>
              )}
            </div>

            {/* Bold Formula */}
            <div
              style={{
                fontSize: 34,
                fontWeight: 900,
                color: "#0F172A",
                letterSpacing: 0.5,
                lineHeight: 1.2,
              }}
            >
              {measurementFormula}
            </div>

            {/* Accent Underline Bar */}
            <div
              style={{
                width: "100%",
                height: 5,
                backgroundColor: "#F1F5F9",
                borderRadius: 3,
                marginTop: 14,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${barProgress}%`,
                  height: "100%",
                  backgroundColor: accentColor,
                  borderRadius: 3,
                }}
              />
            </div>

            {measurementSubtext && (
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: "#64748B",
                  marginTop: 10,
                }}
              >
                {measurementSubtext}
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Magnification Gauge Ruler */}
        <div
          style={{
            position: "relative",
            width: 140,
            height: "100%",
            transform: `translateX(${(1 - gaugeEntrance) * 60}px)`,
            opacity: gaugeEntrance,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
          }}
        >
          {/* Gauge Header */}
          <div
            style={{
              fontSize: 18,
              fontWeight: 900,
              color: "#0F172A",
              marginBottom: 10,
              backgroundColor: "#FFFFFF",
              padding: "4px 14px",
              borderRadius: 6,
              boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
            }}
          >
            {gaugeLabel}
          </div>

          {/* Vertical Ruler Spine Box */}
          <div
            style={{
              position: "relative",
              flex: 1,
              width: 90,
              backgroundColor: "#FFFFFF",
              borderRadius: 20,
              border: "2px solid #CBD5E1",
              boxShadow: "0 14px 35px rgba(0,0,0,0.2)",
              padding: "24px 0",
              boxSizing: "border-box",
            }}
          >
            {/* Tick Marks along Spine */}
            {rulerTicks.map((tick, idx) => (
              <div
                key={idx}
                style={{
                  position: "absolute",
                  bottom: `${tick.pct * 100}%`,
                  right: 14,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <span
                  style={{
                    fontSize: tick.isMajor ? 16 : 13,
                    fontWeight: tick.isMajor ? 900 : 700,
                    color: tick.color || (tick.isBase ? "#0D9488" : "#334155"),
                  }}
                >
                  {tick.label}
                </span>
                <div
                  style={{
                    width: tick.isMajor ? 14 : 8,
                    height: 2,
                    backgroundColor: tick.color || (tick.isBase ? "#0D9488" : "#94A3B8"),
                  }}
                />
              </div>
            ))}

            {/* Gliding Pointer / Needle */}
            <div
              style={{
                position: "absolute",
                bottom: `${pointerYPct * 100}%`,
                left: -28,
                display: "flex",
                alignItems: "center",
                transition: "bottom 0.05s ease-out",
                zIndex: 10,
              }}
            >
              {/* Pointer Tag */}
              <div
                style={{
                  backgroundColor: accentColor,
                  color: "#FFFFFF",
                  fontSize: 15,
                  fontWeight: 900,
                  padding: "4px 10px",
                  borderRadius: 6,
                  boxShadow: "0 2px 10px rgba(239, 68, 68, 0.4)",
                  whiteSpace: "nowrap",
                }}
              >
                {currentMagnification}
              </div>
              {/* Arrow Triangle */}
              <div
                style={{
                  width: 0,
                  height: 0,
                  borderTop: "6px solid transparent",
                  borderBottom: "6px solid transparent",
                  borderLeft: `10px solid ${accentColor}`,
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </CoordinateZeroBackground>
  );
};
