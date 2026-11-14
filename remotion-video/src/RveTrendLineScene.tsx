import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import {
  ProceduralBackground,
  RveSceneFooter,
  RveSceneHeader,
} from "./ProceduralBackground";
import { RveTrendLineSceneProps } from "./types";
import { GlintSheen, RadarBeacon, useContinuousDrift } from "./animations";

const DEFAULT_POINTS = [
  { label: "2020", value: 25 },
  { label: "2021", value: 42 },
  { label: "2022", value: 58 },
  { label: "2023", value: 74 },
  { label: "2024", value: 92, note: "關鍵突破" },
];

export const RveTrendLineScene: React.FC<RveTrendLineSceneProps> = ({
  badge = "GROWTH TRAJECTORY",
  title = "長期趨勢演進曲線",
  subtitle = "",
  highlightStat = "",
  highlightLabel = "",
  points = DEFAULT_POINTS,
  source = "",
  accentColor = "#38BDF8",
  bgSrc = "",
  dim = 0.5,
  bgVariant = "bokeh",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { floatY, glowPulse } = useContinuousDrift(0.00015);
  const areaGradId = React.useId();
  const clipId = React.useId();

  const safePoints =
    points && points.length >= 2 ? points.slice(0, 12) : DEFAULT_POINTS;

  const minVal = Math.min(0, ...safePoints.map((p) => p.value));
  const maxVal = Math.max(10, ...safePoints.map((p) => p.value));
  const valSpan = Math.max(1, maxVal - minVal);

  const chartWidth = 1380;
  const chartHeight = 580;
  const padLeft = 90;
  const padRight = 76;
  const padTop = 76;
  const padBottom = 86;
  const plotW = chartWidth - padLeft - padRight;
  const plotH = chartHeight - padTop - padBottom;

  const xScale = (idx: number) =>
    padLeft + (idx / Math.max(1, safePoints.length - 1)) * plotW;
  const yScale = (val: number) =>
    padTop + plotH - ((val - minVal) / valSpan) * plotH;

  const coords = safePoints.map((p, i) => ({
    x: xScale(i),
    y: yScale(p.value),
    ...p,
  }));

  const polyPoints = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(" ");
  const linePath = coords
    .map((c, i) => `${i === 0 ? "M" : "L"} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`)
    .join(" ");
  const areaPath =
    `${linePath} L ${coords[coords.length - 1].x.toFixed(1)} ${(padTop + plotH).toFixed(1)} ` +
    `L ${coords[0].x.toFixed(1)} ${(padTop + plotH).toFixed(1)} Z`;

  let totalLength = 0;
  for (let i = 1; i < coords.length; i++) {
    const dx = coords[i].x - coords[i - 1].x;
    const dy = coords[i].y - coords[i - 1].y;
    totalLength += Math.sqrt(dx * dx + dy * dy);
  }
  totalLength = Math.max(1, totalLength);

  const drawProgress = interpolate(frame, [6, 50], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const dashOffset = totalLength * (1 - drawProgress);
  const clipWidth = plotW * drawProgress;

  const cardSpring = spring({
    frame: Math.max(0, frame - 2),
    fps,
    config: { damping: 16, stiffness: 110 },
  });

  const statPill = highlightStat ? (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-end",
        padding: "14px 24px",
        borderRadius: 18,
        backgroundColor: "rgba(15, 23, 42, 0.78)",
        border: `1.5px solid ${accentColor}77`,
        boxShadow: `0 0 ${24 * glowPulse}px ${accentColor}33`,
        backdropFilter: "blur(12px)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <RadarBeacon color={accentColor} size={9} />
        <span style={{ fontSize: 40, fontWeight: 900, color: "#FFFFFF" }}>
          {highlightStat}
        </span>
      </div>
      {highlightLabel && (
        <span style={{ fontSize: 16, color: accentColor, fontWeight: 700, marginTop: 4 }}>
          {highlightLabel}
        </span>
      )}
    </div>
  ) : undefined;

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
          rightSlot={statPill}
        />

        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginTop: 22,
            opacity: cardSpring,
            transform: `translateY(${floatY + (1 - cardSpring) * 24}px)`,
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
                <linearGradient id={areaGradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={accentColor} stopOpacity="0.48" />
                  <stop offset="100%" stopColor={accentColor} stopOpacity="0.02" />
                </linearGradient>
                <clipPath id={clipId}>
                  <rect x={padLeft} y={0} width={clipWidth} height={chartHeight} />
                </clipPath>
              </defs>

              {[0, 0.25, 0.5, 0.75, 1].map((r) => {
                const y = padTop + plotH * (1 - r);
                const tick = Math.round(minVal + valSpan * r);
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
                      {tick}
                    </text>
                  </g>
                );
              })}

              <line
                x1={padLeft}
                y1={padTop}
                x2={padLeft}
                y2={padTop + plotH}
                stroke="rgba(255, 255, 255, 0.2)"
                strokeWidth={2}
              />

              <path
                d={areaPath}
                fill={`url(#${areaGradId})`}
                clipPath={`url(#${clipId})`}
              />

              <polyline
                points={polyPoints}
                fill="none"
                stroke={accentColor}
                strokeWidth={5}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={totalLength}
                strokeDashoffset={dashOffset}
              />

              {coords.map((pt, i) => {
                const ptDelay = 6 + (i / Math.max(1, coords.length - 1)) * 40;
                const ptScale = spring({
                  frame: Math.max(0, frame - ptDelay),
                  fps,
                  config: { damping: 12, stiffness: 150 },
                });
                const isLast = i === coords.length - 1;
                return (
                  <g key={`pt-${i}`}>
                    <text
                      x={pt.x}
                      y={chartHeight - padBottom + 36}
                      textAnchor="middle"
                      fill="rgba(241, 245, 249, 0.85)"
                      fontSize={19}
                      fontWeight={650}
                    >
                      {pt.label}
                    </text>

                    <circle
                      cx={pt.x}
                      cy={pt.y}
                      r={(isLast ? 11 : 8) * ptScale}
                      fill={isLast ? "#F43F5E" : accentColor}
                      stroke="#FFFFFF"
                      strokeWidth={3}
                      opacity={ptScale}
                    />

                    <text
                      x={pt.x}
                      y={Math.max(36, pt.y - 20)}
                      textAnchor="middle"
                      fill="#FFFFFF"
                      fontSize={20}
                      fontWeight={800}
                      opacity={ptScale}
                    >
                      {pt.value}
                    </text>

                    {pt.note && (
                      <text
                        x={pt.x}
                        y={Math.max(18, pt.y - 44)}
                        textAnchor="middle"
                        fill={accentColor}
                        fontSize={16}
                        fontWeight={700}
                        opacity={ptScale}
                      >
                        {pt.note}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
            <GlintSheen color={`${accentColor}22`} periodFrames={115} />
          </div>
        </div>

        <RveSceneFooter source={source} accentColor={accentColor} />
      </div>
    </ProceduralBackground>
  );
};
