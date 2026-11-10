import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FoxBackground } from "./FoxBackground";
import { FoxHeaderSceneProps } from "./types";
import {
  DynamicAccentBar,
  GlintSheen,
  RadarBeacon,
  useContinuousDrift,
} from "./animations";

export const FoxHeaderScene: React.FC<FoxHeaderSceneProps> = ({
  category = "核心觀點",
  title = "為什麼現代金融體系仍在製造悲劇？",
  subtitle = "",
  source = "",
  bgSrc = "",
  dim = 0.35,
  accentColor = "#F87171",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { floatY, glowPulse } = useContinuousDrift(0.0002);

  // Entrance springs
  const categorySpring = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 130 },
  });

  const titleSpring = spring({
    frame: frame - 5,
    fps,
    config: { damping: 13, mass: 0.85, stiffness: 120 },
  });

  const subtitleSpring = spring({
    frame: frame - 16,
    fps,
    config: { damping: 15, mass: 0.8, stiffness: 100 },
  });

  const sourceSpring = spring({
    frame: frame - 24,
    fps,
    config: { damping: 16, stiffness: 100 },
  });

  return (
    <FoxBackground bgSrc={bgSrc} dim={dim}>
      <div
        style={{
          position: "absolute",
          top: 180,
          left: 180,
          maxWidth: 1000,
          zIndex: 20,
          transform: `translateY(${floatY}px)`,
        }}
      >
        {/* Category Label with Live Radar Beacon */}
        {category && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "6px 16px",
              borderRadius: 20,
              backgroundColor: "rgba(255, 255, 255, 0.08)",
              border: `1px solid ${accentColor}55`,
              backdropFilter: "blur(12px)",
              fontSize: 22,
              fontWeight: 800,
              color: accentColor,
              letterSpacing: 3,
              textTransform: "uppercase",
              opacity: categorySpring,
              transform: `translateY(${interpolate(
                categorySpring,
                [0, 1],
                [-14, 0]
              )}px) scale(${interpolate(categorySpring, [0, 1], [0.92, 1])})`,
              marginBottom: 16,
              boxShadow: `0 0 ${12 * glowPulse}px ${accentColor}44`,
            }}
          >
            <RadarBeacon color={accentColor} size={8} />
            <span>{category}</span>
          </div>
        )}

        {/* Main Title Container with Kinetic Glint Sweep */}
        <div style={{ position: "relative", display: "inline-block" }}>
          <h1
            style={{
              fontSize: 58,
              fontWeight: 900,
              color: "#FFFFFF",
              lineHeight: 1.25,
              letterSpacing: "-0.5px",
              margin: 0,
              opacity: titleSpring,
              transform: `translateY(${interpolate(
                titleSpring,
                [0, 1],
                [26, 0]
              )}px)`,
              textShadow: `0 4px 24px rgba(0, 0, 0, 0.8), 0 0 ${
                20 * glowPulse
              }px ${accentColor}33`,
            }}
          >
            {title}
          </h1>

          {/* Periodic Luminous Shimmer across Title */}
          <GlintSheen color={`${accentColor}99`} periodFrames={85} />
        </div>

        {/* Dynamic Underline Accent Bar with Travelling Spark Head */}
        <DynamicAccentBar
          color={accentColor}
          maxWidth={160}
          startFrame={12}
          duration={28}
          height={5}
        />

        {/* Subtitle / Context Clause */}
        {subtitle && (
          <p
            style={{
              fontSize: 26,
              color: "rgba(255, 255, 255, 0.88)",
              lineHeight: 1.55,
              marginTop: 22,
              marginBottom: 0,
              opacity: subtitleSpring,
              transform: `translateY(${interpolate(
                subtitleSpring,
                [0, 1],
                [16, 0]
              )}px)`,
              textShadow: "0 2px 12px rgba(0, 0, 0, 0.9)",
            }}
          >
            {subtitle}
          </p>
        )}

        {/* Source citation footnote */}
        {source && (
          <div
            style={{
              fontSize: 16,
              color: "rgba(255, 255, 255, 0.6)",
              marginTop: 20,
              opacity: sourceSpring,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span
              style={{
                width: 4,
                height: 4,
                borderRadius: "50%",
                backgroundColor: accentColor,
              }}
            />
            <span>{source}</span>
          </div>
        )}
      </div>
    </FoxBackground>
  );
};
