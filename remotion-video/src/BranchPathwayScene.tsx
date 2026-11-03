import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { BlueprintBackground } from "./BlueprintBackground";
import { BranchPathwaySceneProps } from "./types";

export const BranchPathwayScene: React.FC<BranchPathwaySceneProps> = ({
  title,
  subtitle,
  paths,
  selectedId,
  bgSrc,
  dim = 0.75,
  accentColor = "#00F5FF",
  badge = "ROUTE DECISION MATRIX",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // 3-Phase Dramatic Timeline Boundaries
  const phase1End = Math.floor(durationInFrames * 0.3);
  const phase2End = Math.floor(durationInFrames * 0.65);

  const phase2Progress = interpolate(
    frame,
    [phase1End, phase1End + 15],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const phase3Progress = interpolate(
    frame,
    [phase2End, phase2End + 20],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

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
          display: "grid",
          gridTemplateColumns: `repeat(${Math.min(paths.length, 4)}, 1fr)`,
          gap: 24,
          height: "100%",
          alignItems: "stretch",
          paddingTop: 10,
        }}
      >
        {paths.map((path, idx) => {
          // Staggered entrance for Phase 1
          const cardSpring = spring({
            frame: frame - idx * 4,
            fps,
            config: { damping: 14, mass: 0.8, stiffness: 120 },
          });

          const isSelected =
            path.id === selectedId ||
            path.status === "selected" ||
            (!selectedId && idx === paths.length - 1);

          const isEliminated =
            path.status === "eliminated" || (!isSelected && selectedId);

          // Phase 2 transition values
          const activeScale = isSelected
            ? interpolate(phase2Progress, [0, 1], [1, 1.03])
            : interpolate(phase2Progress, [0, 1], [1, 0.97]);

          const cardOpacity = isEliminated
            ? interpolate(phase2Progress, [0, 1], [1, 0.4])
            : 1;

          const strikeWidth = isEliminated
            ? interpolate(phase2Progress, [0, 1], [0, 100])
            : 0;

          // Subtle tactile rotation jitter
          const rotJitter = [-0.8, 0.6, -0.5, 0.8][idx % 4];

          return (
            <div
              key={path.id}
              style={{
                position: "relative",
                display: "flex",
                flexDirection: "column",
                transform: `scale(${cardSpring * activeScale}) translateY(${interpolate(
                  cardSpring,
                  [0, 1],
                  [50, 0]
                )}px) rotate(${rotJitter}deg)`,
                opacity: cardSpring * cardOpacity,
                backgroundColor: isSelected
                  ? "rgba(10, 25, 42, 0.85)"
                  : "rgba(15, 20, 30, 0.75)",
                border: isSelected
                  ? `2px solid ${accentColor}`
                  : "1px solid rgba(255, 255, 255, 0.12)",
                boxShadow: isSelected
                  ? `0 20px 50px rgba(0, 245, 255, 0.25), 0 0 20px ${accentColor}33`
                  : "0 15px 35px rgba(0, 0, 0, 0.5)",
                borderRadius: 12,
                padding: "24px 20px",
                backdropFilter: "blur(12px)",
                transition: "border 0.2s ease",
              }}
            >
              {/* Elimination Strike-Through Line */}
              {isEliminated && strikeWidth > 0 && (
                <div
                  style={{
                    position: "absolute",
                    top: "35%",
                    left: "5%",
                    width: `${strikeWidth * 0.9}%`,
                    height: 3,
                    backgroundColor: "#EF4444",
                    boxShadow: "0 0 8px #EF4444",
                    zIndex: 20,
                    borderRadius: 2,
                    transform: "rotate(-3deg)",
                  }}
                />
              )}

              {/* Top Category & Route Index */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 16,
                  fontFamily: "monospace",
                  fontSize: 12,
                }}
              >
                <span
                  style={{
                    padding: "3px 8px",
                    borderRadius: 4,
                    backgroundColor: isSelected
                      ? accentColor
                      : "rgba(255, 255, 255, 0.1)",
                    color: isSelected ? "#070B12" : "rgba(255, 255, 255, 0.7)",
                    fontWeight: 700,
                  }}
                >
                  ROUTE 0{idx + 1}
                </span>

                {path.category && (
                  <span style={{ color: "rgba(255, 255, 255, 0.5)" }}>
                    {path.category}
                  </span>
                )}
              </div>

              {/* Route Name */}
              <h3
                style={{
                  fontSize: 22,
                  fontWeight: 800,
                  margin: "0 0 12px 0",
                  color: isSelected ? "#FFFFFF" : "rgba(255, 255, 255, 0.9)",
                  lineHeight: 1.3,
                }}
              >
                {path.name}
              </h3>

              {/* Description / Resolution Detail */}
              <p
                style={{
                  fontSize: 15,
                  lineHeight: 1.5,
                  color: "rgba(255, 255, 255, 0.7)",
                  margin: "0 0 16px 0",
                  flex: 1,
                }}
              >
                {path.detail}
              </p>

              {/* Elimination Reason Badge */}
              {isEliminated && path.eliminationReason && phase2Progress > 0.4 && (
                <div
                  style={{
                    marginTop: "auto",
                    padding: "8px 10px",
                    borderRadius: 6,
                    backgroundColor: "rgba(239, 68, 68, 0.15)",
                    border: "1px solid rgba(239, 68, 68, 0.35)",
                    color: "#FCA5A5",
                    fontSize: 12,
                    lineHeight: 1.4,
                  }}
                >
                  <strong>排除原因:</strong> {path.eliminationReason}
                </div>
              )}

              {/* Winner Selected Badge in Phase 2 & 3 */}
              {isSelected && (
                <div
                  style={{
                    marginTop: "auto",
                    padding: "12px",
                    borderRadius: 8,
                    backgroundColor: "rgba(0, 245, 255, 0.15)",
                    border: `1px solid ${accentColor}`,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 6,
                    }}
                  >
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        backgroundColor: accentColor,
                        boxShadow: `0 0 8px ${accentColor}`,
                      }}
                    />
                    <span
                      style={{
                        color: accentColor,
                        fontSize: 12,
                        fontWeight: 800,
                        fontFamily: "monospace",
                        letterSpacing: "0.1em",
                      }}
                    >
                      {path.highlightTag || "OPTIMAL TARGET"}
                    </span>
                  </div>

                  {/* Phase 3 Telemetry Expansion */}
                  {phase3Progress > 0 && (
                    <div
                      style={{
                        fontSize: 13,
                        color: "#E2E8F0",
                        lineHeight: 1.4,
                        opacity: phase3Progress,
                        transform: `translateY(${interpolate(
                          phase3Progress,
                          [0, 1],
                          [8, 0]
                        )}px)`,
                      }}
                    >
                      極高頻寬 × 單一神經元級解析度
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </BlueprintBackground>
  );
};
