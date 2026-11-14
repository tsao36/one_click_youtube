import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import {
  ProceduralBackground,
  RveSceneFooter,
  RveSceneHeader,
} from "./ProceduralBackground";
import { RveBarChartSceneProps, RveBarItem } from "./types";
import { GlintSheen, useContinuousDrift } from "./animations";

const DEFAULT_BARS: RveBarItem[] = [
  { label: "項目 A", value: 45, displayValue: "45", color: "" },
  { label: "項目 B", value: 78, displayValue: "78", color: "" },
  { label: "項目 C", value: 62, displayValue: "62", color: "" },
  { label: "項目 D", value: 92, displayValue: "92", color: "" },
];

const BAR_PALETTE = [
  "#38BDF8",
  "#8B5CF6",
  "#14B8A6",
  "#F59E0B",
  "#EC4899",
  "#6366F1",
  "#10B981",
  "#F97316",
];

export const RveBarChartScene: React.FC<RveBarChartSceneProps> = ({
  badge = "DATA BREAKDOWN",
  title = "關鍵數據對比分佈",
  subtitle = "",
  bars = DEFAULT_BARS,
  source = "",
  accentColor = "#38BDF8",
  bgSrc = "",
  dim = 0.5,
  bgVariant = "grid-pulse",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { floatY } = useContinuousDrift(0.00015);
  const shadowId = React.useId();

  const safeBars = (bars && bars.length > 0 ? bars : DEFAULT_BARS).slice(0, 10);
  const maxVal = Math.max(1, ...safeBars.map((b) => Math.abs(b.value) || 0));

  const chartWidth = 1380;
  const chartHeight = 600;
  const padLeft = 84;
  const padRight = 56;
  const padTop = 70;
  const padBottom = 88;
  const plotW = chartWidth - padLeft - padRight;
  const plotH = chartHeight - padTop - padBottom;

  const slotW = plotW / safeBars.length;
  const barWidth = Math.min(130, Math.max(38, slotW * 0.56));

  const cardSpring = spring({
    frame: Math.max(0, frame - 3),
    fps,
    config: { damping: 16, stiffness: 110 },
  });

  const gridRatios = [0, 0.25, 0.5, 0.75, 1];

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
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginTop: 22,
            transform: `translateY(${floatY + (1 - cardSpring) * 24}px)`,
            opacity: cardSpring,
          }}
        >
          <div
            style={{
              position: "relative",
              width: chartWidth,
              height: chartHeight,
              borderRadius: 24,
              background: "rgba(15, 23, 42, 0.72)",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              boxShadow: "0 24px 60px rgba(0, 0, 0, 0.48)",
              backdropFilter: "blur(16px)",
              overflow: "hidden",
            }}
          >
            <svg width={chartWidth} height={chartHeight}>
              <defs>
                <filter id={shadowId} x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="6" stdDeviation="6" floodOpacity="0.35" />
                </filter>
              </defs>

              {gridRatios.map((r) => {
                const y = padTop + plotH * (1 - r);
                const tickVal = Math.round(maxVal * r);
                return (
                  <g key={`grid-${r}`}>
                    <line
                      x1={padLeft}
                      y1={y}
                      x2={chartWidth - padRight}
                      y2={y}
                      stroke="rgba(255, 255, 255, 0.1)"
                      strokeWidth={r === 0 ? 2 : 1}
                      strokeDasharray={r === 0 ? undefined : "6 6"}
                    />
                    <text
                      x={padLeft - 14}
                      y={y + 6}
                      textAnchor="end"
                      fill="rgba(226, 232, 240, 0.55)"
                      fontSize={16}
                      fontWeight={600}
                    >
                      {tickVal}
                    </text>
                  </g>
                );
              })}

              {safeBars.map((bar, i) => {
                const startF = 8 + i * 4;
                const endF = 30 + i * 4;
                const progress = interpolate(frame, [startF, endF], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                });
                const eased = 1 - Math.pow(1 - progress, 3);

                const ratio = Math.max(0.03, Math.abs(bar.value) / maxVal);
                const targetH = ratio * plotH;
                const currentH = targetH * eased;
                const centerX = padLeft + slotW * (i + 0.5);
                const barX = centerX - barWidth / 2;
                const barY = padTop + plotH - currentH;
                const fill =
                  bar.color ||
                  (i === safeBars.length - 1 ? accentColor : BAR_PALETTE[i % BAR_PALETTE.length]);
                const valText = bar.displayValue || String(bar.value);

                return (
                  <g key={`bar-${i}`}>
                    <rect
                      x={barX}
                      y={barY}
                      width={barWidth}
                      height={Math.max(4, currentH)}
                      fill={fill}
                      rx={10}
                      ry={10}
                      filter={`url(#${shadowId})`}
                    />
                    <text
                      x={centerX}
                      y={Math.max(36, barY - 14)}
                      textAnchor="middle"
                      fill="#FFFFFF"
                      fontSize={22}
                      fontWeight={800}
                      opacity={interpolate(progress, [0.55, 1], [0, 1], {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                      })}
                    >
                      {valText}
                    </text>
                    <text
                      x={centerX}
                      y={chartHeight - padBottom + 36}
                      textAnchor="middle"
                      fill="rgba(241, 245, 249, 0.9)"
                      fontSize={20}
                      fontWeight={650}
                    >
                      {bar.label.length > 10 ? `${bar.label.slice(0, 9)}…` : bar.label}
                    </text>
                  </g>
                );
              })}
            </svg>
            <GlintSheen color={`${accentColor}26`} periodFrames={110} />
          </div>
        </div>

        <RveSceneFooter source={source} accentColor={accentColor} />
      </div>
    </ProceduralBackground>
  );
};
