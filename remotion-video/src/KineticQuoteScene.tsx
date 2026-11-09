import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ModernExplainerBackground } from "./ModernExplainerBackground";
import { KineticQuoteSceneProps } from "./types";

export const KineticQuoteScene: React.FC<KineticQuoteSceneProps> = ({
  badge = "EXPERT INSIGHT",
  quote = "「同一個 AI、同樣的月費，有人拿它做出驚人的成果，有人只拿來寫郵件。差別就在於：你敢不敢把 AI 當作真正的高階專案合夥人。」",
  author = "Felix Rieseberg",
  authorTitle = "Anthropic 工程主管 · 破 500 萬瀏覽觀點",
  authorAvatarUrl = "",
  highlightPhrase = "真正的高階專案合夥人",
  accentColor = "#F59E0B",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Badge & Title animation
  const bSpring = spring({ frame, fps, config: { mass: 0.5, damping: 14, stiffness: 120 } });
  const bOpacity = interpolate(bSpring, [0, 1], [0, 1]);
  const bY = interpolate(bSpring, [0, 1], [-20, 0]);

  // Main Card spring
  const cSpring = spring({ frame: Math.max(0, frame - 8), fps, config: { mass: 0.6, damping: 15, stiffness: 110 } });
  const cOpacity = interpolate(cSpring, [0, 1], [0, 1]);
  const cScale = interpolate(cSpring, [0, 1], [0.93, 1]);

  // Highlight glow on key phrase
  const hlSpring = spring({ frame: Math.max(0, frame - 25), fps, config: { mass: 0.5, damping: 12, stiffness: 100 } });
  const hlOpacity = interpolate(hlSpring, [0, 1], [0.15, 0.35]);

  // Split quote by highlightPhrase if provided
  const parts = highlightPhrase && quote.includes(highlightPhrase)
    ? quote.split(highlightPhrase)
    : [quote];

  // Dynamic quote font sizing
  const quoteLen = (quote || "").length;
  const quoteFontSize = quoteLen < 70 ? 44 : quoteLen < 140 ? 38 : 32;
  const quoteLineHeight = quoteLen < 70 ? 1.45 : 1.55;

  return (
    <AbsoluteFill
      style={{
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        color: "#F8FAFC",
        overflow: "hidden",
      }}
    >
      <ModernExplainerBackground accentColor={accentColor} dim={0.4} />

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
          padding: "70px 140px",
          boxSizing: "border-box",
        }}
      >
        {/* Top Badge */}
        <div
          style={{
            opacity: bOpacity,
            transform: `translateY(${bY}px)`,
            marginBottom: 32,
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "7px 18px",
              borderRadius: 20,
              background: "rgba(245, 158, 11, 0.16)",
              border: `1.5px solid ${accentColor}65`,
              color: accentColor,
              fontSize: 16,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            <span style={{ fontSize: 18 }}>💡</span>
            {badge}
          </div>
        </div>

        {/* Central Quote Card */}
        <div
          style={{
            opacity: cOpacity,
            transform: `scale(${cScale})`,
            width: "100%",
            maxWidth: 1300,
            padding: "54px 70px",
            borderRadius: 24,
            background: "linear-gradient(180deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%)",
            border: `1.5px solid ${accentColor}45`,
            boxShadow: `0 28px 70px rgba(0,0,0,0.55), 0 0 45px ${accentColor}20`,
            backdropFilter: "blur(20px)",
            position: "relative",
            display: "flex",
            flexDirection: "column",
            gap: 36,
          }}
        >
          {/* Decorative Quote Mark */}
          <div
            style={{
              position: "absolute",
              top: 20,
              left: 40,
              fontSize: 100,
              lineHeight: 1,
              fontFamily: "Georgia, serif",
              color: `${accentColor}30`,
              userSelect: "none",
            }}
          >
            “
          </div>

          {/* Quote Body */}
          <div
            style={{
              fontSize: quoteFontSize,
              lineHeight: quoteLineHeight,
              fontWeight: 700,
              color: "#FFFFFF",
              letterSpacing: "-0.01em",
              zIndex: 2,
            }}
          >
            {parts.length === 2 ? (
              <>
                {parts[0]}
                <span
                  style={{
                    color: accentColor,
                    background: `rgba(245, 158, 11, ${hlOpacity})`,
                    padding: "2px 10px",
                    borderRadius: 10,
                    borderBottom: `3px solid ${accentColor}`,
                  }}
                >
                  {highlightPhrase}
                </span>
                {parts[1]}
              </>
            ) : (
              quote
            )}
          </div>

          {/* Author Details Footer */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 20,
              borderTop: "1px solid rgba(255, 255, 255, 0.12)",
              paddingTop: 26,
            }}
          >
            {/* Avatar Circle */}
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                background: `linear-gradient(135deg, ${accentColor} 0%, #D97706 100%)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 24,
                fontWeight: 800,
                color: "#FFFFFF",
                boxShadow: `0 4px 18px ${accentColor}45`,
                overflow: "hidden",
                flexShrink: 0,
              }}
            >
              {authorAvatarUrl ? (
                <img src={authorAvatarUrl} alt={author} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              ) : (
                author.slice(0, 2).toUpperCase()
              )}
            </div>

            <div>
              <div style={{ fontSize: 26, fontWeight: 700, color: "#F8FAFC" }}>
                {author}
              </div>
              {authorTitle && (
                <div style={{ fontSize: 18, color: "#CBD5E1", marginTop: 4, fontWeight: 500 }}>
                  {authorTitle}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
