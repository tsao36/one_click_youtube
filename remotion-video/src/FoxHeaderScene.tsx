import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FoxBackground } from "./FoxBackground";
import { FoxHeaderSceneProps } from "./types";

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

  // Entrance springs
  const categorySpring = spring({
    frame,
    fps,
    config: { damping: 16, mass: 0.8, stiffness: 120 },
  });

  const titleSpring = spring({
    frame: frame - 6,
    fps,
    config: { damping: 15, mass: 0.9, stiffness: 110 },
  });

  const lineProgress = interpolate(frame, [16, 40], [0, 140], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const subtitleSpring = spring({
    frame: frame - 18,
    fps,
    config: { damping: 16, mass: 0.8, stiffness: 100 },
  });

  return (
    <FoxBackground bgSrc={bgSrc} dim={dim}>
      <div
        style={{
          position: "absolute",
          top: 180,
          left: 180,
          maxWidth: 950,
          zIndex: 20,
        }}
      >
        {/* Category Label (e.g. "背景" / "第 1 章 換車需求" / "核心觀點") */}
        {category && (
          <div
            style={{
              fontSize: 26,
              fontWeight: 800,
              color: accentColor,
              letterSpacing: 4,
              textTransform: "uppercase",
              opacity: categorySpring,
              transform: `translateY(${interpolate(categorySpring, [0, 1], [-12, 0])}px)`,
              marginBottom: 12,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span>{category}</span>
          </div>
        )}

        {/* Main Title */}
        <h1
          style={{
            fontSize: 58,
            fontWeight: 900,
            color: "#FFFFFF",
            lineHeight: 1.25,
            letterSpacing: "-0.5px",
            margin: 0,
            opacity: titleSpring,
            transform: `translateY(${interpolate(titleSpring, [0, 1], [24, 0])}px)`,
            textShadow: "0 4px 20px rgba(0, 0, 0, 0.7)",
          }}
        >
          {title}
        </h1>

        {/* Dynamic Underline Accent Bar */}
        <div
          style={{
            height: 4,
            width: `${lineProgress}px`,
            backgroundColor: accentColor,
            borderRadius: 2,
            marginTop: 20,
            boxShadow: `0 0 12px ${accentColor}88`,
          }}
        />

        {/* Subtitle / Context Clause (if present) */}
        {subtitle && (
          <p
            style={{
              fontSize: 26,
              color: "rgba(255, 255, 255, 0.85)",
              lineHeight: 1.5,
              marginTop: 22,
              marginBottom: 0,
              opacity: subtitleSpring,
              transform: `translateY(${interpolate(subtitleSpring, [0, 1], [15, 0])}px)`,
              textShadow: "0 2px 10px rgba(0, 0, 0, 0.8)",
            }}
          >
            {subtitle}
          </p>
        )}
      </div>

      {/* Source Footnote (Bottom-Right) */}
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
