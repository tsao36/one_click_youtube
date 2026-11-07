import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

export const ModernExplainerBackground: React.FC<{
  accentColor?: string;
  dim?: number;
}> = ({ accentColor = "#38BDF8", dim = 0.5 }) => {
  const frame = useCurrentFrame();

  // Gentle ambient breathing glow
  const glowScale = interpolate(
    Math.sin(frame / 45),
    [-1, 1],
    [0.92, 1.08]
  );
  const glowOpacity = interpolate(
    Math.cos(frame / 50),
    [-1, 1],
    [0.18, 0.28]
  );

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#090A0F",
        overflow: "hidden",
      }}
    >
      {/* 1. Subtle Radial Ambient Spotlight */}
      <div
        style={{
          position: "absolute",
          top: "15%",
          left: "50%",
          width: 900,
          height: 650,
          transform: `translate(-50%, -50%) scale(${glowScale})`,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accentColor} 0%, rgba(56, 189, 248, 0.08) 45%, transparent 70%)`,
          opacity: glowOpacity * (1 - dim * 0.3),
          filter: "blur(90px)",
          pointerEvents: "none",
        }}
      />

      {/* 2. Secondary Corner Fill Light */}
      <div
        style={{
          position: "absolute",
          bottom: "-10%",
          right: "10%",
          width: 600,
          height: 450,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(168, 85, 247, 0.15) 0%, transparent 65%)",
          filter: "blur(80px)",
          pointerEvents: "none",
        }}
      />

      {/* 3. Modern Micro-Dot Grid */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "radial-gradient(rgba(255, 255, 255, 0.08) 1.2px, transparent 1.2px)",
          backgroundSize: "32px 32px",
          opacity: 0.55,
          pointerEvents: "none",
        }}
      />

      {/* 4. Sleek Vignette */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse at center, transparent 45%, rgba(4, 6, 12, 0.75) 100%)",
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
