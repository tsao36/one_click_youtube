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

export interface MinimalistCardProps {
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

export const MinimalistCard: React.FC<MinimalistCardProps> = ({
  category = "",
  headline = "",
  metric = "",
  metricLabel = "",
  subtext = "",
  accentColor = "#10b981", // Emerald accent by default
  bgSrc = "",
  dim = 0.70,
  bgBlur = 4,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Smooth entrance
  const cardSpring = spring({
    frame: frame - 6,
    fps,
    config: { damping: 16, stiffness: 100, mass: 0.9 },
  });
  const cardY = interpolate(cardSpring, [0, 1], [40, 0]);
  const cardOpacity = interpolate(cardSpring, [0, 1], [0, 1]);

  // Animated divider line expansion (0% -> 100%)
  const lineWidth = interpolate(frame, [18, 48], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Background slow zoom
  const dimIn = interpolate(frame, [0, Math.round(fps * 0.5)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const bgScale = interpolate(frame, [0, durationInFrames], [1.0, 1.05]);

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
        backgroundColor: "#090d16",
        fontFamily: "'Segoe UI', -apple-system, 'Microsoft JhengHei', sans-serif",
      }}
    >
      {/* Background Image */}
      {bgSrc ? (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <Img
            src={staticFile(bgSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${bgScale})`,
              filter: `blur(${bgBlur * dimIn}px) grayscale(40%)`,
            }}
          />
        </AbsoluteFill>
      ) : null}

      {/* Modern Matte Dark Dim */}
      <AbsoluteFill
        style={{
          backgroundColor: `rgba(10, 15, 26, ${dim * dimIn})`,
        }}
      />

      {/* Subtle Linear Grid Pattern */}
      <AbsoluteFill
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
          opacity: 0.4 * dimIn,
        }}
      />

      {/* Main Minimalist Swiss Card */}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div
          style={{
            width: 1240,
            padding: "55px 75px",
            background: "rgba(15, 23, 42, 0.88)",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            borderRadius: 16,
            boxShadow: "0 30px 80px rgba(0, 0, 0, 0.75)",
            transform: `translateY(${cardY}px)`,
            opacity: cardOpacity * cardExit,
            position: "relative",
          }}
        >
          {/* Top Metadata Row */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginBottom: 20,
            }}
          >
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                backgroundColor: accentColor,
                boxShadow: `0 0 10px ${accentColor}`,
                display: "inline-block",
              }}
            />
            <span
              style={{
                fontSize: 18,
                letterSpacing: 3,
                fontWeight: 700,
                color: "#94a3b8",
                textTransform: "uppercase",
              }}
            >
              {category || "KEY INSIGHT"}
            </span>
          </div>

          {/* Headline */}
          {headline ? (
            <h1
              style={{
                fontSize: 54,
                fontWeight: 800,
                color: "#f8fafc",
                margin: "0 0 20px 0",
                lineHeight: 1.3,
                letterSpacing: -0.5,
              }}
            >
              {headline}
            </h1>
          ) : null}

          {/* Clean Divider Line */}
          <div
            style={{
              width: `${lineWidth}%`,
              height: 2,
              backgroundColor: accentColor,
              marginBottom: 26,
              transition: "width 0.1s linear",
            }}
          />

          {/* Metric / Stat Row */}
          {metric ? (
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 18,
                marginBottom: 20,
              }}
            >
              <span
                style={{
                  fontSize: 76,
                  fontWeight: 900,
                  color: "#ffffff",
                  letterSpacing: -2,
                }}
              >
                {metric}
              </span>
              {metricLabel ? (
                <span
                  style={{
                    fontSize: 22,
                    fontWeight: 600,
                    color: accentColor,
                    letterSpacing: 0.5,
                  }}
                >
                  {metricLabel}
                </span>
              ) : null}
            </div>
          ) : null}

          {/* Subtext */}
          {subtext ? (
            <p
              style={{
                fontSize: 28,
                color: "#cbd5e1",
                margin: 0,
                fontWeight: 400,
                lineHeight: 1.6,
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
