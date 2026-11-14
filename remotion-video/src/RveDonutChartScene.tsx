import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import {
  ProceduralBackground,
  RveSceneFooter,
  RveSceneHeader,
} from "./ProceduralBackground";
import { RveDonutChartSceneProps } from "./types";
import { GlintSheen, useContinuousDrift, useCountUp } from "./animations";

const DEFAULT_SEGMENTS = [
  { label: "核心模組", value: 45, displayValue: "45%", color: "#38BDF8" },
  { label: "系統整合", value: 28, displayValue: "28%", color: "#8B5CF6" },
  { label: "基礎架構", value: 17, displayValue: "17%", color: "#14B8A6" },
  { label: "其他支出", value: 10, displayValue: "10%", color: "#F59E0B" },
];

const SEGMENT_COLORS = ["#38BDF8", "#8B5CF6", "#14B8A6", "#F59E0B", "#EC4899", "#10B981"];

export const RveDonutChartScene: React.FC<RveDonutChartSceneProps> = ({
  badge = "COMPOSITION SHARE",
  title = "核心結構佔比解析",
  subtitle = "",
  centerValue = "78%",
  centerLabel = "核心佔比",
  segments = DEFAULT_SEGMENTS,
  source = "",
  accentColor = "#38BDF8",
  bgSrc = "",
  dim = 0.5,
  bgVariant = "geometric",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { floatY, glowPulse } = useContinuousDrift(0.00015);

  const safeSegments =
    segments && segments.length >= 2 ? segments.slice(0, 6) : DEFAULT_SEGMENTS;
  const total = Math.max(
    1,
    safeSegments.reduce((sum, s) => sum + Math.max(0, s.value), 0)
  );

  const radius = 175;
  const strokeWidth = 36;
  const svgSize = 480;
  const cx = svgSize / 2;
  const cy = svgSize / 2;
  const circumference = 2 * Math.PI * radius;

  const { display: animatedCenter, punchScale } = useCountUp(centerValue, {
    startFrame: 8,
    duration: 34,
    fps,
  });

  const ringSpring = spring({
    frame,
    fps,
    config: { damping: 15, stiffness: 105 },
  });

  let cumulativeOffset = 0;

  return (
    <ProceduralBackground
      variant={bgVariant}
      accentColor={accentColor}
      bgSrc={bgSrc}
      dim={dim}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: "100%",
          height: "100%",
          padding: "64px 110px 52px",
          boxSizing: "border-box",
        }}
      >
        <RveSceneHeader
          badge={badge}
          title={title}
          subtitle={subtitle}
          accentColor={accentColor}
        />

        <div
          style={{
            flex: 1,
            display: "grid",
            gridTemplateColumns: "540px 1fr",
            gap: 56,
            alignItems: "center",
            marginTop: 18,
            transform: `translateY(${floatY}px)`,
          }}
        >
          {/* Left Donut Ring */}
          <div
            style={{
              position: "relative",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 30,
              borderRadius: 28,
              background: "rgba(15, 23, 42, 0.72)",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              boxShadow: `0 24px 60px rgba(0, 0, 0, 0.48), 0 0 ${28 * glowPulse}px ${accentColor}1E`,
              backdropFilter: "blur(16px)",
              opacity: ringSpring,
              transform: `scale(${interpolate(ringSpring, [0, 1], [0.92, 1])})`,
              overflow: "hidden",
            }}
          >
            <svg width={svgSize} height={svgSize}>
              <circle
                cx={cx}
                cy={cy}
                r={radius}
                fill="none"
                stroke="rgba(255, 255, 255, 0.08)"
                strokeWidth={strokeWidth}
              />

              {safeSegments.map((seg, i) => {
                const segLength = (Math.max(0, seg.value) / total) * circumference;
                const currentOffset = cumulativeOffset;
                cumulativeOffset += segLength;

                const segProg = interpolate(
                  frame,
                  [6 + i * 9, 28 + i * 9],
                  [0, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
                );
                const eased = 1 - Math.pow(1 - segProg, 3);
                const animatedLen = Math.max(0, segLength * eased - 4);
                const segColor = seg.color || SEGMENT_COLORS[i % SEGMENT_COLORS.length];

                return (
                  <circle
                    key={`seg-${i}`}
                    cx={cx}
                    cy={cy}
                    r={radius}
                    fill="none"
                    stroke={segColor}
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    strokeDasharray={`${animatedLen} ${circumference}`}
                    strokeDashoffset={-currentOffset}
                    transform={`rotate(-90 ${cx} ${cy})`}
                  />
                );
              })}
            </svg>

            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                textAlign: "center",
                transform: `scale(${punchScale})`,
                pointerEvents: "none",
              }}
            >
              <div
                style={{
                  fontSize: 78,
                  fontWeight: 950,
                  color: "#FFFFFF",
                  lineHeight: 1,
                  letterSpacing: "-0.03em",
                  textShadow: `0 4px 20px rgba(0, 0, 0, 0.7), 0 0 24px ${accentColor}44`,
                }}
              >
                {animatedCenter}
              </div>
              {centerLabel && (
                <div
                  style={{
                    fontSize: 22,
                    fontWeight: 650,
                    color: "#CBD5E1",
                    marginTop: 12,
                  }}
                >
                  {centerLabel}
                </div>
              )}
            </div>

            <GlintSheen color={`${accentColor}28`} periodFrames={100} />
          </div>

          {/* Right Legend Cards */}
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            {safeSegments.map((seg, i) => {
              const cardDelay = 8 + i * 6;
              const cardProg = spring({
                frame: Math.max(0, frame - cardDelay),
                fps,
                config: { damping: 14, stiffness: 120 },
              });
              const segColor = seg.color || SEGMENT_COLORS[i % SEGMENT_COLORS.length];
              const pct = Math.round((Math.max(0, seg.value) / total) * 100);
              const valLabel = seg.displayValue || `${pct}%`;

              return (
                <div
                  key={`legend-${i}`}
                  style={{
                    opacity: cardProg,
                    transform: `translateX(${(1 - cardProg) * 32}px)`,
                    padding: "20px 26px",
                    borderRadius: 18,
                    background: "rgba(15, 23, 42, 0.74)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderLeft: `6px solid ${segColor}`,
                    backdropFilter: "blur(12px)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 16,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                      <span
                        style={{
                          width: 14,
                          height: 14,
                          borderRadius: "50%",
                          backgroundColor: segColor,
                          boxShadow: `0 0 10px ${segColor}`,
                        }}
                      />
                      <span
                        style={{
                          fontSize: 26,
                          fontWeight: 750,
                          color: "#F8FAFC",
                        }}
                      >
                        {seg.label}
                      </span>
                    </div>
                    <span
                      style={{
                        fontSize: 30,
                        fontWeight: 900,
                        color: segColor,
                      }}
                    >
                      {valLabel}
                    </span>
                  </div>

                  <div
                    style={{
                      width: "100%",
                      height: 8,
                      borderRadius: 4,
                      backgroundColor: "rgba(255, 255, 255, 0.08)",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${pct * cardProg}%`,
                        height: "100%",
                        borderRadius: 4,
                        backgroundColor: segColor,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <RveSceneFooter source={source} accentColor={accentColor} />
      </div>
    </ProceduralBackground>
  );
};
