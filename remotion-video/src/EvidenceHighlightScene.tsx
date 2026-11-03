import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { BlueprintBackground } from "./BlueprintBackground";
import { EvidenceHighlightSceneProps } from "./types";

export const EvidenceHighlightScene: React.FC<EvidenceHighlightSceneProps> = ({
  title,
  docHeader = "CLINICAL PROTOCOL & SURGICAL TRIAL",
  docDate = "2024 SPECIFICATION",
  documentExcerpt,
  highlightPhrase,
  telemetryStats = [],
  bgSrc,
  dim = 0.75,
  accentColor = "#00F5FF",
  badge = "PRIMARY EVIDENCE / PROTOCOL",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Paper card entrance spring
  const paperSpring = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.9, stiffness: 100 },
  });

  // Highlighter marker animation (sweeping across key sentence)
  const markerProgress = interpolate(frame, [25, 55], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Telemetry stats entrance
  const statsSpring = spring({
    frame: frame - 20,
    fps,
    config: { damping: 15, mass: 0.8, stiffness: 110 },
  });

  // Split excerpt into before, highlight, and after if present
  let beforeText = documentExcerpt;
  let markedText = highlightPhrase;
  let afterText = "";

  if (highlightPhrase && documentExcerpt.includes(highlightPhrase)) {
    const parts = documentExcerpt.split(highlightPhrase);
    beforeText = parts[0];
    markedText = highlightPhrase;
    afterText = parts.slice(1).join(highlightPhrase);
  }

  return (
    <BlueprintBackground
      bgSrc={bgSrc}
      dim={dim}
      badge={badge}
      title={title}
      accentColor={accentColor}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: telemetryStats.length > 0 ? "1.2fr 0.8fr" : "1fr",
          gap: 40,
          height: "100%",
          alignItems: "center",
          padding: "10px 0",
        }}
      >
        {/* Tactile Archival Paper Document */}
        <div
          style={{
            position: "relative",
            transform: `scale(${paperSpring}) translateY(${interpolate(
              paperSpring,
              [0, 1],
              [40, 0]
            )}px) rotate(-0.8deg)`,
            opacity: paperSpring,
            backgroundColor: "#F8FAFC",
            color: "#0F172A",
            borderRadius: 8,
            padding: "36px 40px",
            boxShadow:
              "0 25px 60px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.1)",
            fontFamily:
              "'Georgia', 'Times New Roman', 'Noto Serif TC', serif",
          }}
        >
          {/* Paper Top Header & Stamp */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              borderBottom: "2px solid #E2E8F0",
              paddingBottom: 14,
              marginBottom: 24,
              fontFamily: "monospace",
              fontSize: 12,
              letterSpacing: "0.1em",
              color: "#64748B",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  display: "inline-block",
                  padding: "2px 8px",
                  backgroundColor: "#0F172A",
                  color: "#FFFFFF",
                  fontWeight: 700,
                  borderRadius: 3,
                }}
              >
                RECORD
              </span>
              <span>{docHeader}</span>
            </div>
            {docDate && <span style={{ fontWeight: 600 }}>{docDate}</span>}
          </div>

          {/* Document Excerpt with Highlighter Marker */}
          <div
            style={{
              fontSize: 24,
              lineHeight: 1.8,
              letterSpacing: "0.01em",
              color: "#1E293B",
            }}
          >
            <span>{beforeText}</span>
            <span
              style={{
                position: "relative",
                display: "inline",
                fontWeight: 700,
                color: "#0F172A",
                padding: "2px 0",
              }}
            >
              {/* Animated Highlighter Ink Wash Layer */}
              <span
                style={{
                  position: "absolute",
                  left: 0,
                  top: "12%",
                  bottom: "10%",
                  width: `${markerProgress * 100}%`,
                  backgroundColor: "rgba(254, 240, 138, 0.85)", // High-contrast translucent marker yellow
                  boxShadow: "0 0 10px rgba(250, 204, 21, 0.4)",
                  zIndex: 0,
                  borderRadius: 3,
                  transform: "rotate(-0.5deg)",
                }}
              />
              <span style={{ position: "relative", zIndex: 1 }}>{markedText}</span>
            </span>
            <span>{afterText}</span>
          </div>

          {/* Official Verification Seal */}
          <div
            style={{
              marginTop: 28,
              display: "flex",
              justifyContent: "flex-end",
              alignItems: "center",
              gap: 8,
              fontFamily: "monospace",
              fontSize: 11,
              color: "#94A3B8",
            }}
          >
            <span>STATUS: VERIFIED CLINICAL DATASHEET</span>
            <span style={{ color: "#10B981", fontWeight: 700 }}>[CONFIRMED]</span>
          </div>
        </div>

        {/* Right Side Telemetry Cards */}
        {telemetryStats.length > 0 && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 18,
              transform: `scale(${statsSpring})`,
              opacity: statsSpring,
            }}
          >
            {telemetryStats.map((stat, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: "rgba(10, 18, 30, 0.85)",
                  border: `1px solid ${accentColor}66`,
                  borderRadius: 8,
                  padding: "20px 24px",
                  boxShadow: "0 10px 30px rgba(0,0,0,0.5)",
                  backdropFilter: "blur(10px)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 6,
                    fontSize: 12,
                    fontFamily: "monospace",
                    color: "rgba(255, 255, 255, 0.6)",
                  }}
                >
                  <span>{stat.label}</span>
                  {stat.badge && (
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: 4,
                        backgroundColor: "rgba(0, 245, 255, 0.15)",
                        color: accentColor,
                        fontWeight: 700,
                      }}
                    >
                      {stat.badge}
                    </span>
                  )}
                </div>
                <div
                  style={{
                    fontSize: 32,
                    fontWeight: 900,
                    color: "#FFFFFF",
                    fontFamily: "monospace",
                    letterSpacing: "-0.02em",
                  }}
                >
                  {stat.value}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </BlueprintBackground>
  );
};
