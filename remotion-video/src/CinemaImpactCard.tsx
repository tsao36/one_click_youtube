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

export interface CinemaImpactProps {
  category?: string;
  headline: string;
  metric?: string;
  metricLabel?: string;
  subtext?: string;
  accentColor?: string;
  bgSrc?: string;
  dim?: number;
  bgBlur?: number;
}

export const CinemaImpactCard: React.FC<CinemaImpactProps> = ({
  category = "",
  headline = "",
  metric = "",
  metricLabel = "",
  subtext = "",
  accentColor = "#f59e0b", // Golden Amber
  bgSrc = "",
  dim = 0.72,
  bgBlur = 2,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Dramatic snap spring with slight punch overshoot
  const punchSpring = spring({
    frame: frame - 5,
    fps,
    config: { damping: 11, stiffness: 120, mass: 0.7 },
  });
  const cardScale = interpolate(punchSpring, [0, 1], [0.85, 1]);
  const cardOpacity = interpolate(punchSpring, [0, 1], [0, 1]);

  // Metric dramatic punch in
  const metricSpring = spring({
    frame: frame - 20,
    fps,
    config: { damping: 12, stiffness: 140, mass: 0.6 },
  });
  const metricScale = interpolate(metricSpring, [0, 1], [0.75, 1]);
  const metricOpacity = interpolate(metricSpring, [0, 1], [0, 1]);

  // Background slow dramatic push
  const dimIn = interpolate(frame, [0, Math.round(fps * 0.4)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const bgScale = interpolate(frame, [0, durationInFrames], [1.0, 1.12]);

  // Card exit
  const cardExit = interpolate(
    frame,
    [durationInFrames - 12, durationInFrames - 2],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#050505",
        fontFamily: "'Impact', 'Microsoft JhengHei', 'Segoe UI', sans-serif",
      }}
    >
      {/* Background Image with dramatic push */}
      {bgSrc ? (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <Img
            src={staticFile(bgSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${bgScale})`,
              filter: `blur(${bgBlur * dimIn}px) contrast(110%)`,
            }}
          />
        </AbsoluteFill>
      ) : null}

      {/* Cinematic Dark Overlay */}
      <AbsoluteFill
        style={{
          backgroundColor: `rgba(4, 4, 6, ${dim * dimIn})`,
        }}
      />

      {/* Warm Cinematic Flare Gradient in Bottom Corner */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 85% 85%, ${accentColor}33 0%, transparent 60%)`,
          opacity: dimIn,
          pointerEvents: "none",
        }}
      />

      {/* Cinematic Letterbox Vignette */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.85) 0%, transparent 18%, transparent 82%, rgba(0,0,0,0.85) 100%)",
          opacity: dimIn,
        }}
      />

      {/* Main Cinematic Banner */}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div
          style={{
            width: 1320,
            padding: "50px 70px",
            background: "linear-gradient(135deg, rgba(20, 18, 15, 0.88) 0%, rgba(10, 10, 12, 0.92) 100%)",
            borderLeft: `8px solid ${accentColor}`,
            borderTop: "1px solid rgba(245, 158, 11, 0.3)",
            borderBottom: "1px solid rgba(245, 158, 11, 0.3)",
            borderRight: "1px solid rgba(255, 255, 255, 0.1)",
            boxShadow: `0 35px 90px rgba(0,0,0,0.9), -10px 0 35px ${accentColor}44`,
            borderRadius: 8,
            transform: `scale(${cardScale})`,
            opacity: cardOpacity * cardExit,
            position: "relative",
          }}
        >
          {/* Category Tag */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "4px 14px",
              background: `rgba(245, 158, 11, 0.15)`,
              border: `1px solid ${accentColor}66`,
              borderRadius: 4,
              marginBottom: 18,
            }}
          >
            <span
              style={{
                fontSize: 15,
                letterSpacing: 2,
                fontWeight: 800,
                color: accentColor,
                textTransform: "uppercase",
                fontFamily: "'Segoe UI', 'Microsoft JhengHei', sans-serif",
              }}
            >
              {category || "CRITICAL MOMENT"}
            </span>
          </div>

          {/* Headline */}
          {headline ? (
            <h1
              style={{
                fontSize: 60,
                fontWeight: 900,
                color: "#ffffff",
                margin: "0 0 24px 0",
                lineHeight: 1.22,
                letterSpacing: 0.5,
                textShadow: "0 4px 20px rgba(0,0,0,0.8)",
                fontFamily: "'Segoe UI', 'Microsoft JhengHei', sans-serif",
              }}
            >
              {headline}
            </h1>
          ) : null}

          {/* Golden Impact Metric Badge */}
          {metric ? (
            <div
              style={{
                display: "inline-flex",
                alignItems: "baseline",
                gap: 16,
                background: "linear-gradient(90deg, rgba(245, 158, 11, 0.22) 0%, rgba(180, 83, 9, 0.15) 100%)",
                border: `1.5px solid ${accentColor}`,
                boxShadow: `0 0 30px ${accentColor}44`,
                borderRadius: 8,
                padding: "12px 28px",
                marginBottom: 20,
                transform: `scale(${metricScale})`,
                opacity: metricOpacity,
              }}
            >
              <span
                style={{
                  fontSize: 74,
                  fontWeight: 900,
                  color: "#fef3c7",
                  letterSpacing: -1,
                  textShadow: `0 0 20px ${accentColor}`,
                  fontFamily: "'Segoe UI', 'Microsoft JhengHei', sans-serif",
                }}
              >
                {metric}
              </span>
              {metricLabel ? (
                <span
                  style={{
                    fontSize: 22,
                    fontWeight: 700,
                    color: accentColor,
                    letterSpacing: 1,
                    textTransform: "uppercase",
                    fontFamily: "'Segoe UI', 'Microsoft JhengHei', sans-serif",
                  }}
                >
                  {metricLabel}
                </span>
              ) : null}
            </div>
          ) : null}

          {/* Cinematic Subtext */}
          {subtext ? (
            <p
              style={{
                fontSize: 28,
                color: "#e2e8f0",
                margin: 0,
                fontWeight: 500,
                lineHeight: 1.5,
                fontFamily: "'Segoe UI', 'Microsoft JhengHei', sans-serif",
              }}
            >
              {subtext}
            </p>
          ) : null}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
