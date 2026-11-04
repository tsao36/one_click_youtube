import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FoxBackground } from "./FoxBackground";
import { FoxMetricSceneProps } from "./types";

export const FoxMetricScene: React.FC<FoxMetricSceneProps> = ({
  badge = "核心數據",
  value = "73.6",
  unit = "公噸",
  conversion = "",
  description = "",
  subtext = "",
  source = "",
  bgSrc = "",
  dim = 0.4,
  accentColor = "#38BDF8",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Entrance animations
  const badgeSpring = spring({
    frame,
    fps,
    config: { damping: 16, mass: 0.8, stiffness: 120 },
  });

  const valueSpring = spring({
    frame: frame - 6,
    fps,
    config: { damping: 14, mass: 0.9, stiffness: 110 },
  });

  const descSpring = spring({
    frame: frame - 16,
    fps,
    config: { damping: 16, mass: 0.8, stiffness: 100 },
  });

  const lineProgress = interpolate(frame, [14, 38], [0, 160], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <FoxBackground bgSrc={bgSrc} dim={dim}>
      <div
        style={{
          position: "absolute",
          top: 240,
          left: 160,
          maxWidth: 1100,
          zIndex: 20,
        }}
      >
        {/* Category / Metric Badge */}
        {badge && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              padding: "6px 16px",
              borderRadius: 20,
              backgroundColor: "rgba(255, 255, 255, 0.08)",
              border: `1px solid ${accentColor}66`,
              backdropFilter: "blur(12px)",
              fontSize: 22,
              fontWeight: 700,
              color: accentColor,
              letterSpacing: 2,
              opacity: badgeSpring,
              transform: `translateY(${interpolate(badgeSpring, [0, 1], [-10, 0])}px)`,
              marginBottom: 20,
            }}
          >
            <span>{badge}</span>
          </div>
        )}

        {/* Massive Metric Value */}
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            flexWrap: "wrap",
            gap: 16,
            opacity: valueSpring,
            transform: `translateY(${interpolate(valueSpring, [0, 1], [30, 0])}px) scale(${interpolate(
              valueSpring,
              [0, 1],
              [0.96, 1]
            )})`,
          }}
        >
          <span
            style={{
              fontSize: 96,
              fontWeight: 900,
              color: "#FFFFFF",
              letterSpacing: "-1px",
              lineHeight: 1.05,
              textShadow: "0 4px 24px rgba(0, 0, 0, 0.8)",
              fontFamily: "system-ui, -apple-system, sans-serif",
            }}
          >
            {value}
          </span>

          {unit && (
            <span
              style={{
                fontSize: 44,
                fontWeight: 700,
                color: accentColor,
                letterSpacing: 1,
                textShadow: "0 2px 16px rgba(0, 0, 0, 0.7)",
              }}
            >
              {unit}
            </span>
          )}

          {conversion && (
            <span
              style={{
                fontSize: 36,
                fontWeight: 600,
                color: "rgba(255, 255, 255, 0.7)",
                letterSpacing: 1,
                marginLeft: 8,
                textShadow: "0 2px 12px rgba(0, 0, 0, 0.7)",
              }}
            >
              {conversion}
            </span>
          )}
        </div>

        {/* Accent Bar */}
        <div
          style={{
            height: 4,
            width: `${lineProgress}px`,
            backgroundColor: accentColor,
            borderRadius: 2,
            marginTop: 22,
            marginBottom: 22,
            boxShadow: `0 0 14px ${accentColor}99`,
          }}
        />

        {/* Primary Description */}
        {description && (
          <div
            style={{
              fontSize: 32,
              fontWeight: 700,
              color: "#FFFFFF",
              lineHeight: 1.35,
              opacity: descSpring,
              transform: `translateY(${interpolate(descSpring, [0, 1], [16, 0])}px)`,
              textShadow: "0 2px 12px rgba(0, 0, 0, 0.8)",
              marginBottom: 12,
            }}
          >
            {description}
          </div>
        )}

        {/* Secondary Subtext / Explanatory Note */}
        {subtext && (
          <div
            style={{
              fontSize: 24,
              color: "rgba(255, 255, 255, 0.82)",
              lineHeight: 1.5,
              opacity: descSpring,
              transform: `translateY(${interpolate(descSpring, [0, 1], [16, 0])}px)`,
              textShadow: "0 2px 10px rgba(0, 0, 0, 0.8)",
            }}
          >
            {subtext}
          </div>
        )}
      </div>

      {/* Source Footnote */}
      {source && (
        <div
          style={{
            position: "absolute",
            bottom: 48,
            right: 80,
            fontSize: 16,
            color: "rgba(255, 255, 255, 0.45)",
            letterSpacing: 0.5,
            zIndex: 20,
          }}
        >
          {source}
        </div>
      )}
    </FoxBackground>
  );
};
