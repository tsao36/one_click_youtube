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

export interface TechCardProps {
  category?: string;
  headline: string;
  metric?: string;
  metricLabel?: string;
  subtext?: string;
  accentColor?: string;
  /** File name inside remotion-video/public (e.g. "bg/scene_004.png"). Empty = no image. */
  bgSrc?: string;
  /** 0..1 strength of the dark overlay on top of the background image. */
  dim?: number;
  /** Gaussian blur (px) applied to the background so the card stays legible. */
  bgBlur?: number;
}

export const TechCard: React.FC<TechCardProps> = ({
  category = "",
  headline = "",
  metric = "",
  metricLabel = "",
  subtext = "",
  accentColor = "#00F5FF",
  bgSrc = "",
  dim = 0.62,
  bgBlur = 3,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Card entrance (delayed slightly so the viewer first registers the image)
  const cardSpring = spring({
    frame: frame - 8,
    fps,
    config: { damping: 13, stiffness: 90, mass: 0.8 },
  });
  const cardScale = interpolate(cardSpring, [0, 1], [0.9, 1]);
  const cardOpacity = interpolate(cardSpring, [0, 1], [0, 1]);

  // Metric reveal
  const metricProgress = interpolate(frame, [22, 50], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Background: dims in over the first ~0.6s, slow push-in for the whole clip
  const dimIn = interpolate(frame, [0, Math.round(fps * 0.6)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const bgScale = interpolate(frame, [0, durationInFrames], [1.0, 1.08]);

  // Card exits near the end; the background stays so scene transitions remain clean
  const cardExit = interpolate(
    frame,
    [durationInFrames - 14, durationInFrames - 2],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const glowPulse = interpolate(
    Math.sin((frame / fps) * Math.PI * 1.2),
    [-1, 1],
    [0.12, 0.24],
  );

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#000",
        fontFamily: "'Microsoft JhengHei', 'Segoe UI', sans-serif",
      }}
    >
      {/* Scene background image */}
      {bgSrc ? (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <Img
            src={staticFile(bgSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${bgScale})`,
              filter: `blur(${bgBlur * dimIn}px) saturate(${1 - 0.35 * dimIn})`,
            }}
          />
        </AbsoluteFill>
      ) : null}

      {/* Dark, opaque overlay + vignette */}
      <AbsoluteFill
        style={{
          backgroundColor: `rgba(2, 6, 18, ${dim * dimIn})`,
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,0.55) 100%)",
          opacity: dimIn,
        }}
      />

      {/* Accent glow behind the card */}
      <AbsoluteFill
        style={{ alignItems: "center", justifyContent: "center", pointerEvents: "none" }}
      >
        <div
          style={{
            width: 900,
            height: 900,
            borderRadius: "50%",
            background: `radial-gradient(circle, ${accentColor} 0%, transparent 70%)`,
            opacity: glowPulse * cardOpacity * cardExit,
            filter: "blur(90px)",
          }}
        />
      </AbsoluteFill>

      {/* Motion graphic card */}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div
          style={{
            width: 1280,
            padding: "50px 70px",
            background: "rgba(8, 14, 30, 0.72)",
            border: "1.5px solid rgba(56, 189, 248, 0.35)",
            boxShadow: `0 20px 60px rgba(0,0,0,0.7), 0 0 40px ${accentColor}33`,
            borderRadius: 24,
            transform: `scale(${cardScale})`,
            opacity: cardOpacity * cardExit,
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              height: 4,
              background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,
            }}
          />

          {category ? (
            <div style={{ marginBottom: 22 }}>
              <span
                style={{
                  fontSize: 22,
                  letterSpacing: 2,
                  fontWeight: 800,
                  padding: "6px 18px",
                  borderRadius: 30,
                  color: "#ffffff",
                  background: `linear-gradient(135deg, ${accentColor} 0%, #0284c7 100%)`,
                  boxShadow: `0 0 15px ${accentColor}66`,
                }}
              >
                {category}
              </span>
            </div>
          ) : null}

          {headline ? (
            <h1
              style={{
                fontSize: 58,
                fontWeight: 900,
                color: "#ffffff",
                margin: "0 0 24px 0",
                lineHeight: 1.25,
                textShadow: "0 2px 10px rgba(0,0,0,0.6)",
              }}
            >
              {headline}
            </h1>
          ) : null}

          {metric ? (
            <div
              style={{
                display: "inline-flex",
                alignItems: "baseline",
                gap: 16,
                background: "rgba(15, 23, 42, 0.75)",
                border: `1px solid ${accentColor}55`,
                borderRadius: 16,
                padding: "16px 28px",
                marginBottom: 20,
                opacity: metricProgress,
                transform: `translateY(${interpolate(metricProgress, [0, 1], [20, 0])}px)`,
              }}
            >
              <span
                style={{
                  fontSize: 72,
                  fontWeight: 900,
                  color: accentColor,
                  letterSpacing: -1,
                  textShadow: `0 0 25px ${accentColor}88`,
                }}
              >
                {metric}
              </span>
              {metricLabel ? (
                <span style={{ fontSize: 24, fontWeight: 700, color: "#94a3b8" }}>
                  {metricLabel}
                </span>
              ) : null}
            </div>
          ) : null}

          {subtext ? (
            <p
              style={{
                fontSize: 30,
                color: "#d5deea",
                margin: 0,
                fontWeight: 500,
                lineHeight: 1.5,
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
