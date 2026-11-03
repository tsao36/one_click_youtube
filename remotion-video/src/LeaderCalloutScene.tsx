import React from "react";
import {
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { BlueprintBackground } from "./BlueprintBackground";
import { LeaderCalloutSceneProps } from "./types";

export const LeaderCalloutScene: React.FC<LeaderCalloutSceneProps> = ({
  title,
  subtitle,
  callouts,
  bgSrc,
  dim = 0.65,
  accentColor = "#00F5FF",
  badge = "ANATOMICAL HUD TELEMETRY",
}) => {
  const frame = useCurrentFrame();
  const { fps, width = 1920, height = 1080 } = useVideoConfig();

  // Usable inner dimensions for relative coordinate calculations
  const innerWidth = width - 144;
  const innerHeight = height - 224;

  return (
    <BlueprintBackground
      bgSrc={bgSrc}
      dim={dim}
      badge={badge}
      title={title}
      subtitle={subtitle}
      accentColor={accentColor}
    >
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
        }}
      >
        {/* SVG Drawing Layer for Leader Lines */}
        <svg
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
            zIndex: 15,
          }}
        >
          {callouts.map((callout, idx) => {
            const startFrame = idx * 6;
            const lineProgress = spring({
              frame: frame - startFrame,
              fps,
              config: { damping: 16, mass: 0.9, stiffness: 100 },
            });

            // Map normalized coordinates (0..1) to pixel space
            const ax = (callout.anchorX || 0.4) * innerWidth;
            const ay = (callout.anchorY || 0.4 + idx * 0.15) * innerHeight;
            const bx = (callout.boxX || (ax > innerWidth / 2 ? 0.75 : 0.2)) * innerWidth;
            const by = (callout.boxY || ay) * innerHeight;

            // Intermediate elbow point for clean 90-degree or 45-degree angled leader line
            const elbowX = ax + (bx - ax) * 0.5;
            const elbowY = ay;

            // Total approximate path length for stroke dash animation
            const pathLen = Math.hypot(elbowX - ax, elbowY - ay) + Math.hypot(bx - elbowX, by - elbowY);
            const dashOffset = (1 - lineProgress) * pathLen;

            const isWarning = callout.status === "warning";
            const lineColor = isWarning ? "#EF4444" : accentColor;

            return (
              <g key={`svg-${callout.id}`}>
                {/* Pulsing Target Dot */}
                <circle
                  cx={ax}
                  cy={ay}
                  r={6 * lineProgress}
                  fill={lineColor}
                  stroke="#FFFFFF"
                  strokeWidth={2}
                />
                {/* Ripple Circle */}
                {lineProgress > 0.5 && (
                  <circle
                    cx={ax}
                    cy={ay}
                    r={14 + Math.sin(frame / 6 + idx) * 4}
                    fill="none"
                    stroke={lineColor}
                    strokeWidth={1.5}
                    opacity={0.4}
                  />
                )}

                {/* Animated Elbow Leader Path */}
                <path
                  d={`M ${ax} ${ay} L ${elbowX} ${elbowY} L ${bx} ${by}`}
                  fill="none"
                  stroke={lineColor}
                  strokeWidth={2}
                  strokeDasharray={`${pathLen} ${pathLen}`}
                  strokeDashoffset={dashOffset}
                />
              </g>
            );
          })}
        </svg>

        {/* Floating Telemetry Callout Cards */}
        {callouts.map((callout, idx) => {
          const startFrame = idx * 6 + 8;
          const boxSpring = spring({
            frame: frame - startFrame,
            fps,
            config: { damping: 15, mass: 0.8, stiffness: 110 },
          });

          const bx = (callout.boxX || 0.65) * innerWidth;
          const by = (callout.boxY || 0.3 + idx * 0.2) * innerHeight;
          const isWarning = callout.status === "warning";
          const cardAccent = isWarning ? "#EF4444" : accentColor;

          return (
            <div
              key={callout.id}
              style={{
                position: "absolute",
                left: bx,
                top: by,
                transform: `translate(-10%, -50%) scale(${boxSpring})`,
                opacity: boxSpring,
                backgroundColor: "rgba(10, 16, 26, 0.88)",
                border: `1.5px solid ${cardAccent}`,
                borderRadius: 8,
                padding: "16px 20px",
                width: 320,
                boxShadow: `0 12px 30px rgba(0,0,0,0.6), 0 0 15px ${cardAccent}33`,
                backdropFilter: "blur(12px)",
                zIndex: 20,
              }}
            >
              {/* Telemetry Tag / Metric */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 8,
                  fontSize: 12,
                  fontFamily: "monospace",
                }}
              >
                <span
                  style={{
                    color: cardAccent,
                    fontWeight: 700,
                    letterSpacing: "0.1em",
                  }}
                >
                  LAYER 0{idx + 1}
                </span>

                {callout.metric && (
                  <span
                    style={{
                      backgroundColor: `${cardAccent}22`,
                      color: cardAccent,
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontWeight: 600,
                    }}
                  >
                    {callout.metric}
                  </span>
                )}
              </div>

              {/* Title & Subtitle */}
              <h4
                style={{
                  fontSize: 18,
                  fontWeight: 800,
                  color: "#FFFFFF",
                  margin: "0 0 6px 0",
                  lineHeight: 1.3,
                }}
              >
                {callout.label}
              </h4>

              {callout.sublabel && (
                <p
                  style={{
                    fontSize: 13,
                    color: "rgba(255, 255, 255, 0.72)",
                    margin: 0,
                    lineHeight: 1.4,
                  }}
                >
                  {callout.sublabel}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </BlueprintBackground>
  );
};
