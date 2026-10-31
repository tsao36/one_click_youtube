import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { KCurveSceneProps } from "./types";

export const KCurveScene: React.FC<KCurveSceneProps> = ({
  title = "K 型趨勢：全面兩極分化",
  upperText,
  lowerText,
  forkProgress = 0.35,
  upperColor = "#10B981",
  lowerColor = "#EF4444",
  bgSrc = "",
  dim = 0.8,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Progress of path animation (0 -> 1 over 45 frames)
  const drawProgress = interpolate(frame, [5, 50], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Label reveal spring after divergence
  const labelSpring = spring({
    frame: Math.max(0, frame - 35),
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 100 },
  });

  // SVG dimensions
  const svgW = 1000;
  const svgH = 500;
  const startX = 60;
  const forkX = startX + (svgW - startX - 100) * forkProgress;
  const midY = svgH / 2;
  const endX = svgW - 60;
  const upperEndY = 70;
  const lowerEndY = svgH - 70;

  // Path data
  // Base trunk
  const trunkD = `M ${startX} ${midY} L ${forkX} ${midY}`;
  // Upper branch (smooth cubic bezier)
  const upperBranchD = `M ${forkX} ${midY} C ${(forkX + endX) / 2} ${midY - 20}, ${(forkX + endX) / 2} ${upperEndY + 40}, ${endX} ${upperEndY}`;
  // Lower branch (smooth cubic bezier)
  const lowerBranchD = `M ${forkX} ${midY} C ${(forkX + endX) / 2} ${midY + 20}, ${(forkX + endX) / 2} ${lowerEndY - 40}, ${endX} ${lowerEndY}`;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0B0F19",
        color: "#FFFFFF",
        fontFamily: "'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', sans-serif",
        overflow: "hidden",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Background Dimmed Image */}
      {bgSrc ? (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <Img
            src={staticFile(bgSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${1 + frame * 0.0006})`,
            }}
          />
          <AbsoluteFill
            style={{
              backgroundColor: `rgba(11, 15, 25, ${dim})`,
              backdropFilter: "blur(14px)",
            }}
          />
        </AbsoluteFill>
      ) : null}

      <div
        style={{
          position: "relative",
          zIndex: 10,
          maxWidth: 1500,
          width: "88%",
          padding: "50px 60px",
          background: "rgba(17, 24, 39, 0.8)",
          backdropFilter: "blur(20px)",
          borderRadius: 24,
          border: "1px solid rgba(255, 255, 255, 0.12)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        {/* Title */}
        <h2
          style={{
            fontSize: 48,
            fontWeight: 800,
            margin: "0 0 30px 0",
            color: "#FFFFFF",
            letterSpacing: 1,
            alignSelf: "flex-start",
          }}
        >
          {title}
        </h2>

        {/* SVG Container with relative labels */}
        <div style={{ position: "relative", width: svgW, height: svgH }}>
          <svg width={svgW} height={svgH} viewBox={`0 0 ${svgW} ${svgH}`} style={{ overflow: "visible" }}>
            <defs>
              <linearGradient id="trunkGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#64748B" />
                <stop offset="100%" stopColor="#94A3B8" />
              </linearGradient>
            </defs>

            {/* Grid guides */}
            <line x1={startX} y1={midY} x2={endX} y2={midY} stroke="rgba(255,255,255,0.08)" strokeDasharray="6 6" strokeWidth={2} />

            {/* Trunk */}
            <path
              d={trunkD}
              stroke="url(#trunkGrad)"
              strokeWidth={7}
              fill="none"
              strokeLinecap="round"
              strokeDasharray={svgW}
              strokeDashoffset={svgW * (1 - Math.min(1, drawProgress / forkProgress))}
            />

            {/* Fork Marker Node */}
            {drawProgress >= forkProgress ? (
              <circle
                cx={forkX}
                cy={midY}
                r={7}
                fill="#FFFFFF"
                stroke="#3B82F6"
                strokeWidth={4}
              />
            ) : null}

            {/* Upper Trajectory */}
            <path
              d={upperBranchD}
              stroke={upperColor}
              strokeWidth={7}
              fill="none"
              strokeLinecap="round"
              strokeDasharray={svgW}
              strokeDashoffset={svgW * (1 - Math.max(0, (drawProgress - forkProgress) / (1 - forkProgress)))}
              style={{ filter: `drop-shadow(0 0 12px ${upperColor}88)` }}
            />

            {/* Lower Trajectory */}
            <path
              d={lowerBranchD}
              stroke={lowerColor}
              strokeWidth={7}
              fill="none"
              strokeLinecap="round"
              strokeDasharray={svgW}
              strokeDashoffset={svgW * (1 - Math.max(0, (drawProgress - forkProgress) / (1 - forkProgress)))}
              style={{ filter: `drop-shadow(0 0 12px ${lowerColor}88)` }}
            />
          </svg>

          {/* Upper Label Card */}
          <div
            style={{
              position: "absolute",
              right: 0,
              top: upperEndY - 45,
              opacity: labelSpring,
              transform: `translateX(${interpolate(labelSpring, [0, 1], [30, 0])}px)`,
              background: `${upperColor}1F`,
              border: `1.5px solid ${upperColor}88`,
              borderRadius: 12,
              padding: "12px 24px",
              boxShadow: `0 8px 20px ${upperColor}26`,
            }}
          >
            <span style={{ fontSize: 28, fontWeight: 800, color: upperColor }}>
              ▲ {upperText}
            </span>
          </div>

          {/* Lower Label Card */}
          <div
            style={{
              position: "absolute",
              right: 0,
              top: lowerEndY - 20,
              opacity: labelSpring,
              transform: `translateX(${interpolate(labelSpring, [0, 1], [30, 0])}px)`,
              background: `${lowerColor}1F`,
              border: `1.5px solid ${lowerColor}88`,
              borderRadius: 12,
              padding: "12px 24px",
              boxShadow: `0 8px 20px ${lowerColor}26`,
            }}
          >
            <span style={{ fontSize: 28, fontWeight: 800, color: lowerColor }}>
              ▼ {lowerText}
            </span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
