import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { VoxBackground } from "./VoxBackground";
import { VoxSplitScreenSceneProps } from "./types";

export const VoxSplitScreenScene: React.FC<VoxSplitScreenSceneProps> = ({
  category = "THE BIG STORY",
  badge = "KEY FINDING",
  headline = "為什麼這個數據改變了整個產業的遊戲規則？",
  excerpt = "「當規模效應跨過臨界點，後進者的研發成本將呈現幾何級數放大，市場終將走向單一寡占。」",
  highlightPhrase = "研發成本呈現幾何級數放大",
  points = [
    "前三大巨頭掌握全球超過 85% 的尖端製程專利",
    "單一晶圓廠建置成本突破 200 億美元，形成不可逾越的資金護城河",
    "全球供應鏈重構引發各國主權晶片法案全面加碼補助",
  ],
  source = "VOX INVESTIGATIVE DATA ANALYSIS · SOURCE: SEC FILINGS & TECHINSIGHTS",
  accentColor = "#FACC15",
  bgSrc = "",
  dim = 0.4,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Entrance spring
  const entrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 95 },
  });

  // Highlighter expansion (frame 25 -> 55)
  const highlightWidth = interpolate(frame, [25, 55], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <VoxBackground bgSrc={bgSrc} dim={dim} category={category}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          height: "100%",
          padding: "36px 60px",
          gap: 48,
          boxSizing: "border-box",
          alignItems: "center",
          transform: `scale(${entrance})`,
          opacity: entrance,
        }}
      >
        {/* Left Side: Document Evidence with Bold Yellow Highlighter */}
        <div
          style={{
            backgroundColor: "#FFFFFF",
            borderRadius: 8,
            padding: "32px 36px",
            boxShadow: "0 18px 45px rgba(0,0,0,0.5)",
            border: "2px solid #E2E8F0",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            minHeight: 380,
          }}
        >
          <div>
            <div
              style={{
                display: "inline-block",
                backgroundColor: "#0F172A",
                color: "#FFFFFF",
                fontSize: 11,
                fontWeight: 900,
                letterSpacing: 1.5,
                padding: "3px 10px",
                borderRadius: 3,
                marginBottom: 16,
              }}
            >
              EXHIBIT A: INDUSTRY REPORT
            </div>

            {/* Quote with dynamic yellow highlighter */}
            <div
              style={{
                position: "relative",
                fontSize: 22,
                fontWeight: 800,
                color: "#0F172A",
                lineHeight: 1.8,
                marginTop: 10,
              }}
            >
              {excerpt}

              {/* Dynamic Yellow Highlighter Layer */}
              <div
                style={{
                  position: "relative",
                  width: `${highlightWidth}%`,
                  height: 12,
                  backgroundColor: accentColor,
                  opacity: 0.8,
                  marginTop: -16,
                  borderRadius: 2,
                  zIndex: 0,
                }}
              />
            </div>
          </div>

          <div
            style={{
              borderTop: "1px solid #E2E8F0",
              paddingTop: 12,
              fontSize: 11,
              fontWeight: 700,
              color: "#64748B",
            }}
          >
            {source}
          </div>
        </div>

        {/* Right Side: Giant Editorial Typography & Key Takeaways */}
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
          {/* Yellow Badge */}
          <div
            style={{
              display: "inline-block",
              alignSelf: "flex-start",
              backgroundColor: accentColor,
              color: "#000000",
              fontSize: 12,
              fontWeight: 900,
              letterSpacing: 1,
              padding: "4px 12px",
              borderRadius: 3,
              marginBottom: 14,
            }}
          >
            {badge}
          </div>

          {/* Headline */}
          <div
            style={{
              fontSize: 32,
              fontWeight: 900,
              color: "#FFFFFF",
              lineHeight: 1.35,
              marginBottom: 20,
              letterSpacing: 0.5,
            }}
          >
            {headline}
          </div>

          {/* Bulleted Points */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {points.map((pt, idx) => {
              const ptSpring = spring({
                frame: frame - 15 - idx * 6,
                fps,
                config: { damping: 14, stiffness: 90 },
              });

              return (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 12,
                    transform: `translateX(${(1 - ptSpring) * 25}px)`,
                    opacity: ptSpring,
                  }}
                >
                  <div
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      backgroundColor: accentColor,
                      marginTop: 8,
                      flexShrink: 0,
                    }}
                  />
                  <div style={{ fontSize: 16, fontWeight: 600, color: "#CBD5E1", lineHeight: 1.5 }}>
                    {pt}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </VoxBackground>
  );
};
