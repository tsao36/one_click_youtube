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
import { StatNumberSceneProps } from "./types";

export const StatNumberScene: React.FC<StatNumberSceneProps> = ({
  value,
  prefix = "",
  suffix = "",
  unit = "",
  label,
  subtext = "",
  decimals = 0,
  accentColor = "#F59E0B",
  bgSrc = "",
  dim = 0.75,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Entrance spring for card container
  const cardEntrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
  });

  // Animated number counter
  const animValue = interpolate(frame, [5, 45], [0, value], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const formattedNum = decimals > 0 ? animValue.toFixed(decimals) : Math.round(animValue).toLocaleString();

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

      {/* Modern Circular Glow */}
      <div
        style={{
          position: "absolute",
          width: 700,
          height: 700,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accentColor}25 0%, transparent 70%)`,
          filter: "blur(40px)",
        }}
      />

      <div
        style={{
          position: "relative",
          zIndex: 10,
          maxWidth: 1300,
          width: "80%",
          padding: "60px 80px",
          background: "rgba(17, 24, 39, 0.82)",
          backdropFilter: "blur(24px)",
          borderRadius: 28,
          border: `1.5px solid ${accentColor}44`,
          boxShadow: `0 30px 60px -12px rgba(0, 0, 0, 0.8), 0 0 50px ${accentColor}22`,
          opacity: cardEntrance,
          transform: `scale(${interpolate(cardEntrance, [0, 1], [0.92, 1])})`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
        }}
      >
        {/* Large Number Value */}
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "center",
            gap: 12,
            marginBottom: 16,
          }}
        >
          {prefix ? (
            <span
              style={{
                fontSize: 64,
                fontWeight: 700,
                color: accentColor,
              }}
            >
              {prefix}
            </span>
          ) : null}

          <span
            style={{
              fontSize: 140,
              fontWeight: 900,
              lineHeight: 1,
              letterSpacing: "-2px",
              background: `linear-gradient(180deg, #FFFFFF 40%, ${accentColor} 100%)`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              textShadow: "0 10px 30px rgba(0,0,0,0.5)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {formattedNum}
          </span>

          {suffix || unit ? (
            <span
              style={{
                fontSize: 64,
                fontWeight: 800,
                color: accentColor,
              }}
            >
              {suffix} {unit}
            </span>
          ) : null}
        </div>

        {/* Separator Line */}
        <div
          style={{
            width: 120,
            height: 4,
            borderRadius: 2,
            backgroundColor: accentColor,
            marginBottom: 24,
            boxShadow: `0 0 16px ${accentColor}`,
          }}
        />

        {/* Label Title */}
        <h2
          style={{
            fontSize: 48,
            fontWeight: 800,
            color: "#FFFFFF",
            margin: "0 0 16px 0",
            lineHeight: 1.3,
            maxWidth: 1000,
          }}
        >
          {label}
        </h2>

        {/* Subtext description */}
        {subtext ? (
          <p
            style={{
              fontSize: 26,
              color: "#CBD5E1",
              margin: 0,
              lineHeight: 1.5,
              maxWidth: 900,
            }}
          >
            {subtext}
          </p>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
