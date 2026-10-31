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
import { TitleSceneProps } from "./types";

export const TitleScene: React.FC<TitleSceneProps> = ({
  title,
  subtitle = "",
  category = "重點結論",
  accentColor = "#3B82F6",
  bgSrc = "",
  dim = 0.75,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Entrance spring
  const entrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
  });

  const cardOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });
  const translateY = interpolate(entrance, [0, 1], [40, 0]);

  // Accent line glow pulse
  const pulse = Math.sin(frame / 12) * 0.15 + 0.85;

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
              transform: `scale(${1 + frame * 0.0008})`,
            }}
          />
          <AbsoluteFill
            style={{
              backgroundColor: `rgba(11, 15, 25, ${dim})`,
              backdropFilter: "blur(12px)",
            }}
          />
        </AbsoluteFill>
      ) : null}

      {/* Decorative Cyber / Modern Grid Lines */}
      <AbsoluteFill
        style={{
          opacity: 0.08,
          backgroundImage: `linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)`,
          backgroundSize: "60px 60px",
        }}
      />

      {/* Central Content Box */}
      <div
        style={{
          position: "relative",
          zIndex: 10,
          maxWidth: 1400,
          width: "85%",
          padding: "60px 80px",
          background: "rgba(17, 24, 39, 0.75)",
          backdropFilter: "blur(20px)",
          borderRadius: 24,
          border: `1px solid rgba(255, 255, 255, 0.12)`,
          boxShadow: `0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 40px ${accentColor}22`,
          opacity: cardOpacity,
          transform: `translateY(${translateY}px)`,
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
          textAlign: "left",
        }}
      >
        {/* Category Pill */}
        {category ? (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 20px",
              borderRadius: 30,
              backgroundColor: `${accentColor}26`,
              border: `1px solid ${accentColor}88`,
              color: accentColor,
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: 2,
              marginBottom: 24,
              textTransform: "uppercase",
            }}
          >
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                backgroundColor: accentColor,
                display: "inline-block",
                boxShadow: `0 0 10px ${accentColor}`,
              }}
            />
            {category}
          </div>
        ) : null}

        {/* Title */}
        <h1
          style={{
            fontSize: 68,
            fontWeight: 900,
            lineHeight: 1.25,
            margin: "0 0 20px 0",
            letterSpacing: "-0.5px",
            background: `linear-gradient(135deg, #FFFFFF 40%, ${accentColor} 100%)`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            textShadow: "0 4px 20px rgba(0,0,0,0.5)",
          }}
        >
          {title}
        </h1>

        {/* Accent Bar */}
        <div
          style={{
            width: `${Math.min(100, Math.max(20, entrance * 100))}%`,
            height: 4,
            borderRadius: 2,
            backgroundColor: accentColor,
            marginBottom: 24,
            boxShadow: `0 0 ${16 * pulse}px ${accentColor}`,
          }}
        />

        {/* Subtitle */}
        {subtitle ? (
          <p
            style={{
              fontSize: 32,
              fontWeight: 400,
              lineHeight: 1.6,
              margin: 0,
              color: "#E2E8F0",
              opacity: interpolate(frame, [15, 30], [0, 0.95], {
                extrapolateRight: "clamp",
              }),
            }}
          >
            {subtitle}
          </p>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
