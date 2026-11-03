import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { BlueprintBackground } from "./BlueprintBackground";
import { ScaleCompareSceneProps } from "./types";

export const ScaleCompareScene: React.FC<ScaleCompareSceneProps> = ({
  title,
  subtitle,
  macroLabel,
  macroValue,
  macroDesc,
  microLabel,
  microValue,
  microDesc,
  ratioMultiplier = "20×",
  ratioLabel = "極限尺度差距",
  magnificationFactor = "20X ZOOM",
  bgSrc,
  dim = 0.75,
  accentColor = "#00F5FF",
  badge = "PRECISION SCALE BENCHMARK",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Entrance animations
  const loupeSpring = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.9, stiffness: 100 },
  });

  const cardsSpring = spring({
    frame: frame - 10,
    fps,
    config: { damping: 15, mass: 0.8, stiffness: 110 },
  });

  const rulerProgress = interpolate(frame, [15, 45], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

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
          gridTemplateColumns: "1.1fr 0.9fr",
          gap: 48,
          height: "100%",
          alignItems: "center",
          padding: "10px 0",
        }}
      >
        {/* Left: Concentric Micro-Loupe Simulation */}
        <div
          style={{
            position: "relative",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            transform: `scale(${loupeSpring})`,
            opacity: loupeSpring,
          }}
        >
          {/* Circular Loupe Housing */}
          <div
            style={{
              position: "relative",
              width: 440,
              height: 440,
              borderRadius: "50%",
              backgroundColor: "rgba(10, 16, 26, 0.9)",
              border: `2px solid ${accentColor}`,
              boxShadow: `0 0 50px rgba(0, 245, 255, 0.2), inset 0 0 40px rgba(0, 0, 0, 0.8)`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              overflow: "hidden",
            }}
          >
            {/* Inner Grid & Measurement Ticks inside Loupe */}
            <div
              style={{
                position: "absolute",
                width: "100%",
                height: "100%",
                backgroundImage: `
                  linear-gradient(to right, rgba(0, 245, 255, 0.1) 1px, transparent 1px),
                  linear-gradient(to bottom, rgba(0, 245, 255, 0.1) 1px, transparent 1px)
                `,
                backgroundSize: "20px 20px",
                pointerEvents: "none",
              }}
            />

            {/* Crosshairs */}
            <div
              style={{
                position: "absolute",
                width: "100%",
                height: 1,
                backgroundColor: "rgba(0, 245, 255, 0.3)",
              }}
            />
            <div
              style={{
                position: "absolute",
                height: "100%",
                width: 1,
                backgroundColor: "rgba(0, 245, 255, 0.3)",
              }}
            />

            {/* Concentric Guide Rings */}
            <div
              style={{
                position: "absolute",
                width: 260,
                height: 260,
                borderRadius: "50%",
                border: "1px dashed rgba(255, 255, 255, 0.2)",
              }}
            />
            <div
              style={{
                position: "absolute",
                width: 120,
                height: 120,
                borderRadius: "50%",
                border: "1px solid rgba(0, 245, 255, 0.4)",
              }}
            />

            {/* Simulated Fiber Cross-Sections */}
            {/* Macro Object: Human Hair (100μm cylinder) */}
            <div
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                left: "32%",
                width: 76,
                background:
                  "linear-gradient(90deg, #1E293B 0%, #475569 50%, #1E293B 100%)",
                boxShadow: "0 0 20px rgba(0,0,0,0.8)",
                borderLeft: "1px solid rgba(255,255,255,0.2)",
                borderRight: "1px solid rgba(255,255,255,0.2)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <span
                style={{
                  writingMode: "vertical-rl",
                  fontSize: 12,
                  fontFamily: "monospace",
                  color: "#94A3B8",
                  letterSpacing: "0.2em",
                }}
              >
                HAIR ~ 100μm
              </span>
            </div>

            {/* Micro Object: Neuralink Thread (5μm thin strand) */}
            <div
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                left: "68%",
                width: 5,
                backgroundColor: accentColor,
                boxShadow: `0 0 16px ${accentColor}`,
                borderRadius: 2,
              }}
            />

            {/* Telemetry Reticle Badge */}
            <div
              style={{
                position: "absolute",
                bottom: 24,
                padding: "4px 12px",
                borderRadius: 4,
                backgroundColor: "rgba(0, 245, 255, 0.15)",
                border: `1px solid ${accentColor}`,
                color: accentColor,
                fontFamily: "monospace",
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.15em",
              }}
            >
              OPTICAL LOUPE // {magnificationFactor}
            </div>
          </div>

          {/* Animated Sliding Micrometer Ruler below Loupe */}
          <div
            style={{
              width: 440,
              marginTop: 20,
              padding: "12px 16px",
              backgroundColor: "rgba(10, 16, 26, 0.75)",
              borderRadius: 8,
              border: "1px solid rgba(255, 255, 255, 0.1)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 11,
                fontFamily: "monospace",
                color: "rgba(255, 255, 255, 0.5)",
                marginBottom: 6,
              }}
            >
              <span>0 μm</span>
              <span>50 μm</span>
              <span>100 μm</span>
            </div>
            {/* Ruler Ticks */}
            <div
              style={{
                position: "relative",
                height: 12,
                borderTop: "1px solid rgba(255, 255, 255, 0.3)",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  height: 10,
                  width: 1,
                  backgroundColor: "#FFFFFF",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: "50%",
                  top: 0,
                  height: 6,
                  width: 1,
                  backgroundColor: "rgba(255, 255, 255, 0.5)",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: "100%",
                  top: 0,
                  height: 10,
                  width: 1,
                  backgroundColor: "#FFFFFF",
                }}
              />
              {/* Dynamic indicator marker */}
              <div
                style={{
                  position: "absolute",
                  left: `${interpolate(rulerProgress, [0, 1], [0, 100])}%`,
                  top: -2,
                  width: 3,
                  height: 16,
                  backgroundColor: accentColor,
                  boxShadow: `0 0 6px ${accentColor}`,
                }}
              />
            </div>
          </div>
        </div>

        {/* Right: Comparative Stat Cards & Ratio Badge */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 20,
            transform: `scale(${cardsSpring})`,
            opacity: cardsSpring,
          }}
        >
          {/* Card 1: Macro Benchmark (Human Hair) */}
          <div
            style={{
              padding: "20px 24px",
              backgroundColor: "rgba(15, 23, 42, 0.8)",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              borderRadius: 10,
              boxShadow: "0 10px 25px rgba(0,0,0,0.5)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 8,
              }}
            >
              <span
                style={{
                  fontSize: 12,
                  fontFamily: "monospace",
                  color: "#94A3B8",
                  letterSpacing: "0.1em",
                }}
              >
                REFERENCE OBJECT
              </span>
              <span
                style={{
                  fontSize: 28,
                  fontWeight: 900,
                  color: "#F1F5F9",
                  fontFamily: "monospace",
                }}
              >
                {macroValue}
              </span>
            </div>
            <h3 style={{ fontSize: 20, fontWeight: 700, margin: "0 0 6px 0" }}>
              {macroLabel}
            </h3>
            {macroDesc && (
              <p style={{ fontSize: 14, color: "#94A3B8", margin: 0, lineHeight: 1.4 }}>
                {macroDesc}
              </p>
            )}
          </div>

          {/* Central Ratio Indicator */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "16px 24px",
              backgroundColor: "rgba(0, 245, 255, 0.12)",
              border: `1.5px solid ${accentColor}`,
              borderRadius: 10,
              boxShadow: `0 0 25px ${accentColor}33`,
            }}
          >
            <div>
              <div
                style={{
                  fontSize: 12,
                  fontFamily: "monospace",
                  color: accentColor,
                  fontWeight: 700,
                  letterSpacing: "0.15em",
                }}
              >
                {ratioLabel}
              </div>
              <div style={{ fontSize: 14, color: "#FFFFFF", marginTop: 4 }}>
                極細柔性結構大幅降低大腦免疫排異
              </div>
            </div>
            <div
              style={{
                fontSize: 42,
                fontWeight: 900,
                color: accentColor,
                fontFamily: "monospace",
                lineHeight: 1,
              }}
            >
              {ratioMultiplier}
            </div>
          </div>

          {/* Card 2: Micro Target (Neuralink Thread) */}
          <div
            style={{
              padding: "20px 24px",
              backgroundColor: "rgba(10, 25, 42, 0.85)",
              border: `1px solid ${accentColor}88`,
              borderRadius: 10,
              boxShadow: "0 10px 25px rgba(0,0,0,0.5)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 8,
              }}
            >
              <span
                style={{
                  fontSize: 12,
                  fontFamily: "monospace",
                  color: accentColor,
                  letterSpacing: "0.1em",
                }}
              >
                PRECISION TARGET
              </span>
              <span
                style={{
                  fontSize: 28,
                  fontWeight: 900,
                  color: accentColor,
                  fontFamily: "monospace",
                }}
              >
                {microValue}
              </span>
            </div>
            <h3 style={{ fontSize: 20, fontWeight: 700, margin: "0 0 6px 0" }}>
              {microLabel}
            </h3>
            {microDesc && (
              <p style={{ fontSize: 14, color: "#CBD5E1", margin: 0, lineHeight: 1.4 }}>
                {microDesc}
              </p>
            )}
          </div>
        </div>
      </div>
    </BlueprintBackground>
  );
};
