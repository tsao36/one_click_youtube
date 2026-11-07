import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ModernExplainerBackground } from "./ModernExplainerBackground";
import { KineticTypographySceneProps } from "./types";

export const KineticTypographyScene: React.FC<KineticTypographySceneProps> = ({
  badge = "CORE PRINCIPLE",
  text = "想把 AI 用得好，你得再瘋一點。",
  highlightPhrase = "再瘋一點",
  words = [],
  subtext = "同一個工具、同樣的月費，差別在於你敢不敢設定更高的成果規格",
  accentColor = "#38BDF8",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  // Header / Badge Spring
  const bSpring = spring({ frame, fps, config: { mass: 0.5, damping: 14, stiffness: 120 } });
  const bOpacity = interpolate(bSpring, [0, 1], [0, 1]);
  const bY = interpolate(bSpring, [0, 1], [-20, 0]);

  // Main text container spring
  const tSpring = spring({ frame: Math.max(0, frame - 6), fps, config: { mass: 0.6, damping: 14, stiffness: 110 } });
  const tOpacity = interpolate(tSpring, [0, 1], [0, 1]);
  const tScale = interpolate(tSpring, [0, 1], [0.92, 1]);

  // Subtext spring
  const sSpring = spring({ frame: Math.max(0, frame - 18), fps, config: { mass: 0.5, damping: 14, stiffness: 110 } });
  const sOpacity = interpolate(sSpring, [0, 1], [0, 1]);
  const sY = interpolate(sSpring, [0, 1], [20, 0]);

  // Glow pulsing on highlight
  const glowPulse = interpolate(
    Math.sin(frame / 20),
    [-1, 1],
    [0.18, 0.4]
  );

  return (
    <AbsoluteFill
      style={{
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        color: "#F8FAFC",
        overflow: "hidden",
      }}
    >
      <ModernExplainerBackground accentColor={accentColor} dim={0.35} />

      <div
        style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          width: "100%",
          height: "100%",
          padding: "80px 140px",
          boxSizing: "border-box",
          textAlign: "center",
        }}
      >
        {/* Top Badge */}
        <div
          style={{
            opacity: bOpacity,
            transform: `translateY(${bY}px)`,
            marginBottom: 36,
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "6px 16px",
              borderRadius: 20,
              background: "rgba(56, 189, 248, 0.12)",
              border: `1px solid ${accentColor}60`,
              color: accentColor,
              fontSize: 13,
              fontWeight: 700,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
            }}
          >
            <span>✦</span>
            {badge}
          </div>
        </div>

        {/* Central Kinetic Headline */}
        <div
          style={{
            opacity: tOpacity,
            transform: `scale(${tScale})`,
            maxWidth: 1400,
            fontSize: 64,
            fontWeight: 800,
            lineHeight: 1.35,
            letterSpacing: "-0.02em",
            color: "#FFFFFF",
            marginBottom: 36,
            textShadow: "0 4px 30px rgba(0,0,0,0.7)",
          }}
        >
          {/* If words array with timestamps is provided */}
          {words && words.length > 0 ? (
            words.map((w, i) => {
              const isWordActive = (w.start && w.end)
                ? (currentTime >= w.start && currentTime <= w.end)
                : (currentTime >= i * 0.4 && currentTime <= (i + 1) * 0.4);

              return (
                <span
                  key={i}
                  style={{
                    display: "inline-block",
                    margin: "0 6px",
                    color: isWordActive || w.highlight ? accentColor : "rgba(255, 255, 255, 0.45)",
                    transform: isWordActive ? "scale(1.06)" : "scale(1)",
                    textShadow: isWordActive ? `0 0 25px ${accentColor}` : "none",
                    transition: "color 0.15s, transform 0.15s",
                  }}
                >
                  {w.word}
                </span>
              );
            })
          ) : highlightPhrase && text.includes(highlightPhrase) ? (
            // Text split by highlightPhrase
            (() => {
              const parts = text.split(highlightPhrase);
              return (
                <>
                  <span>{parts[0]}</span>
                  <span
                    style={{
                      color: accentColor,
                      background: `rgba(56, 189, 248, ${glowPulse})`,
                      padding: "2px 14px",
                      borderRadius: 14,
                      boxShadow: `0 0 35px ${accentColor}50`,
                      borderBottom: `3px solid ${accentColor}`,
                      display: "inline-block",
                      margin: "0 6px",
                    }}
                  >
                    {highlightPhrase}
                  </span>
                  <span>{parts[1]}</span>
                </>
              );
            })()
          ) : (
            text
          )}
        </div>

        {/* Subtext Card */}
        {subtext && (
          <div
            style={{
              opacity: sOpacity,
              transform: `translateY(${sY}px)`,
              maxWidth: 900,
              fontSize: 22,
              lineHeight: 1.6,
              color: "#94A3B8",
              fontWeight: 400,
              padding: "16px 28px",
              borderRadius: 16,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              backdropFilter: "blur(12px)",
            }}
          >
            {subtext}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
