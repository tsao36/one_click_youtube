import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { TrackingAnchor } from "./simulationTypes";

interface SpatialTrackingAnchorProps {
  anchor: TrackingAnchor;
  delayIndex?: number;
  isHighlighted?: boolean;
}

export const SpatialTrackingAnchor: React.FC<SpatialTrackingAnchorProps> = ({
  anchor,
  delayIndex = 0,
  isHighlighted = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Staggered entrance spring
  const enterProgress = spring({
    frame: frame - delayIndex * 6,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 105 },
  });

  if (frame < delayIndex * 6) {
    return null;
  }

  // Target pulse
  const reticlePulse = Math.sin(frame / 12 + delayIndex) * 0.15 + 1.0;
  const waveRadius = (frame * 2.5 + delayIndex * 15) % 45;
  const waveOpacity = interpolate(waveRadius, [0, 45], [0.8, 0]);

  // Color mapping by status
  let cardColor = anchor.highlightColor || "#38BDF8";
  let statusText = "TRACKING ACTIVE";
  if (anchor.status === "warning") {
    cardColor = "#F59E0B";
    statusText = "CHAOS / ATTENTION";
  } else if (anchor.status === "eliminated") {
    cardColor = "#EF4444";
    statusText = "DEPLETED / EXTINCT";
  } else if (anchor.status === "completed") {
    cardColor = "#10B981";
    statusText = "STABILIZED";
  }

  // Connecting line coordinates
  const tx = anchor.targetX;
  const ty = anchor.targetY;
  const bx = anchor.boxX;
  const by = anchor.boxY;

  // Midpoint control point for curvature
  const midX = (tx + bx) / 2;
  const midY = (ty + by) / 2 - 4;

  return (
    <>
      {/* SVG Leader Line and Target Reticle */}
      <svg
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
          zIndex: isHighlighted ? 28 : 20,
        }}
      >
        <defs>
          <filter id={`anchor-glow-${anchor.id}`} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Dynamic Curved Leader Line */}
        <path
          d={`M ${tx}% ${ty}% Q ${midX}% ${midY}% ${bx}% ${by}%`}
          fill="none"
          stroke={cardColor}
          strokeWidth={isHighlighted ? 2.5 : 1.5}
          strokeDasharray="6 4"
          strokeDashoffset={-frame * 2}
          opacity={enterProgress * (isHighlighted ? 0.95 : 0.65)}
          filter={`url(#anchor-glow-${anchor.id})`}
        />

        {/* Target Reticle Crosshair at [tx, ty] */}
        <g transform={`translate(0, 0)`} opacity={enterProgress}>
          {/* Expanding Pulse Ring */}
          <circle
            cx={`${tx}%`}
            cy={`${ty}%`}
            r={waveRadius}
            fill="none"
            stroke={cardColor}
            strokeWidth="1.5"
            opacity={waveOpacity}
          />

          {/* Central Target Dot */}
          <circle
            cx={`${tx}%`}
            cy={`${ty}%`}
            r="4.5"
            fill={cardColor}
            stroke="#0F172A"
            strokeWidth="1.5"
          />

          {/* Reticle Corner Brackets */}
          <g
            style={{
              transform: `scale(${reticlePulse})`,
              transformOrigin: `${tx}% ${ty}%`,
            }}
          >
            {/* Top-Left Bracket */}
            <path
              d={`M calc(${tx}% - 14px) calc(${ty}% - 8px) L calc(${tx}% - 14px) calc(${ty}% - 14px) L calc(${tx}% - 8px) calc(${ty}% - 14px)`}
              fill="none"
              stroke={cardColor}
              strokeWidth="2"
            />
            {/* Top-Right Bracket */}
            <path
              d={`M calc(${tx}% + 8px) calc(${ty}% - 14px) L calc(${tx}% + 14px) calc(${ty}% - 14px) L calc(${tx}% + 14px) calc(${ty}% - 8px)`}
              fill="none"
              stroke={cardColor}
              strokeWidth="2"
            />
            {/* Bottom-Left Bracket */}
            <path
              d={`M calc(${tx}% - 14px) calc(${ty}% + 8px) L calc(${tx}% - 14px) calc(${ty}% + 14px) L calc(${tx}% - 8px) calc(${ty}% + 14px)`}
              fill="none"
              stroke={cardColor}
              strokeWidth="2"
            />
            {/* Bottom-Right Bracket */}
            <path
              d={`M calc(${tx}% + 8px) calc(${ty}% + 14px) L calc(${tx}% + 14px) calc(${ty}% + 14px) L calc(${tx}% + 14px) calc(${ty}% + 8px)`}
              fill="none"
              stroke={cardColor}
              strokeWidth="2"
            />
          </g>

          {/* Target Coordinate Tag */}
          <text
            x={`${tx}%`}
            y={`calc(${ty}% + 24px)`}
            fill="#CBD5E1"
            fontSize="9"
            fontFamily="monospace"
            textAnchor="middle"
            letterSpacing="0.5"
            opacity="0.8"
          >
            [{tx.toFixed(0)}%, {ty.toFixed(0)}%]
          </text>
        </g>
      </svg>

      {/* Floating Glassmorphic Telemetry Card at [bx, by] */}
      <div
        style={{
          position: "absolute",
          left: `${bx}%`,
          top: `${by}%`,
          transform: `translate(-50%, -50%) scale(${enterProgress * (isHighlighted ? 1.08 : 1)})`,
          opacity: enterProgress,
          background: "rgba(15, 23, 42, 0.92)",
          border: `1.5px solid ${isHighlighted ? cardColor : "rgba(148, 163, 184, 0.25)"}`,
          borderRadius: 10,
          padding: "10px 14px",
          minWidth: 170,
          maxWidth: 240,
          boxShadow: isHighlighted ? `0 0 25px ${cardColor}50` : "0 8px 30px rgba(0, 0, 0, 0.6)",
          backdropFilter: "blur(10px)",
          zIndex: isHighlighted ? 30 : 22,
          pointerEvents: "none",
        }}
      >
        {/* Header pill */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
          <span
            style={{
              fontSize: 8.5,
              fontFamily: "monospace",
              fontWeight: 800,
              padding: "1px 6px",
              borderRadius: 4,
              backgroundColor: `${cardColor}20`,
              color: cardColor,
              border: `1px solid ${cardColor}50`,
              letterSpacing: 0.5,
            }}
          >
            {statusText}
          </span>
          {anchor.metric && (
            <span
              style={{
                fontSize: 10,
                fontFamily: "monospace",
                fontWeight: 800,
                color: "#F8FAFC",
              }}
            >
              {anchor.metric}
            </span>
          )}
        </div>

        {/* Title */}
        <div
          style={{
            fontSize: 13,
            fontWeight: 800,
            color: "#FFFFFF",
            lineHeight: 1.2,
          }}
        >
          {anchor.label}
        </div>

        {/* Sublabel */}
        {anchor.sublabel && (
          <div
            style={{
              fontSize: 10,
              color: "#94A3B8",
              marginTop: 4,
              lineHeight: 1.3,
            }}
          >
            {anchor.sublabel}
          </div>
        )}
      </div>
    </>
  );
};
