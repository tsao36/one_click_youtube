import React from "react";
import {
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { CoordinateZeroBackground } from "./CoordinateZeroBackground";
import { CoordinateZeroSplitSceneProps } from "./types";

export const CoordinateZeroSplitScene: React.FC<CoordinateZeroSplitSceneProps> = ({
  verdictBadge = "各對一半",
  badgeColor = "#2563EB",
  leftCard = {
    tag: "彼得斯說對的",
    tagColor: "#EF4444",
    title: "高爾—彼得斯視角",
    caption: "赤道附近，看起來比較小",
    imgSrc: "",
  },
  rightCard = {
    tag: "製圖學家說對的",
    tagColor: "#0D9488",
    title: "麥卡托現代製圖視角",
    caption: "放大的規則：只看緯度",
    imgSrc: "",
  },
  summary = "地圖從來不只是幾何線條，而是不同時代航海與政治意圖的投影抉擇",
  accentColor = "#0D9488",
  bgSrc = "",
  dim = 0.15,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Entrance animations
  const badgeEntrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.7, stiffness: 100 },
  });

  const leftCardEntrance = spring({
    frame: frame - 10,
    fps,
    config: { damping: 14, mass: 0.9, stiffness: 85 },
  });

  const rightCardEntrance = spring({
    frame: frame - 20,
    fps,
    config: { damping: 14, mass: 0.9, stiffness: 85 },
  });

  return (
    <CoordinateZeroBackground bgSrc={bgSrc} dim={dim} showPaper={false}>
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          padding: "40px 80px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          boxSizing: "border-box",
        }}
      >
        {/* Top Verdict Capsule Badge */}
        <div
          style={{
            backgroundColor: badgeColor,
            color: "#FFFFFF",
            fontSize: 26,
            fontWeight: 900,
            padding: "8px 36px",
            borderRadius: 999,
            boxShadow: "0 4px 16px rgba(37, 99, 235, 0.4)",
            marginBottom: 35,
            transform: `scale(${badgeEntrance})`,
            opacity: badgeEntrance,
            zIndex: 10,
          }}
        >
          {verdictBadge}
        </div>

        {/* Central Vertical Dashed Line on Cutting Mat */}
        <div
          style={{
            position: "absolute",
            top: 100,
            bottom: 120,
            left: "50%",
            width: 2,
            borderLeft: "2px dashed rgba(255, 255, 255, 0.25)",
            pointerEvents: "none",
          }}
        />

        {/* Dual Cards Comparison Container */}
        <div
          style={{
            flex: 1,
            width: "100%",
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 60,
            alignItems: "center",
          }}
        >
          {/* Left Card (Side A) */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              transform: `scale(${leftCardEntrance}) rotate(-1.5deg)`,
              opacity: leftCardEntrance,
            }}
          >
            {/* Pill Header */}
            <div
              style={{
                backgroundColor: leftCard.tagColor || "#EF4444",
                color: "#FFFFFF",
                fontSize: 22,
                fontWeight: 900,
                padding: "6px 28px",
                borderRadius: 999,
                boxShadow: "0 4px 12px rgba(239, 68, 68, 0.35)",
                marginBottom: 16,
              }}
            >
              {leftCard.tag}
            </div>

            {/* Polaroid / Paper Card with Masking Tape */}
            <div
              style={{
                position: "relative",
                width: "90%",
                maxWidth: 580,
                backgroundColor: "#FAF7F0",
                borderRadius: 8,
                padding: "24px 28px 20px 28px",
                boxShadow: "0 18px 45px rgba(0,0,0,0.3)",
                display: "flex",
                flexDirection: "column",
              }}
            >
              {/* Corner Masking Tape */}
              <div
                style={{
                  position: "absolute",
                  top: -12,
                  left: 30,
                  width: 90,
                  height: 28,
                  backgroundColor: "rgba(244, 238, 222, 0.85)",
                  transform: "rotate(-6deg)",
                  boxShadow: "0 2px 5px rgba(0,0,0,0.15)",
                }}
              />

              {/* Card Title & Content Area */}
              <div
                style={{
                  height: 260,
                  backgroundColor: "#E0F2FE",
                  borderRadius: 6,
                  border: "1.5px solid #BAE6FD",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  overflow: "hidden",
                  position: "relative",
                  marginBottom: 16,
                }}
              >
                {/* Visual Map / Graphic Grid Pattern */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    backgroundImage: `
                      linear-gradient(to right, rgba(14, 116, 144, 0.15) 1px, transparent 1px),
                      linear-gradient(to bottom, rgba(14, 116, 144, 0.15) 1px, transparent 1px)
                    `,
                    backgroundSize: "40px 40px",
                  }}
                />
                <div
                  style={{
                    position: "relative",
                    fontSize: 28,
                    fontWeight: 900,
                    color: "#0369A1",
                    textAlign: "center",
                    padding: "0 20px",
                  }}
                >
                  {leftCard.title}
                </div>
              </div>

              {/* Bold Takeaway Caption */}
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 900,
                  color: "#0F172A",
                  textAlign: "center",
                  lineHeight: 1.3,
                }}
              >
                {leftCard.caption}
              </div>
            </div>
          </div>

          {/* Right Card (Side B) */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              transform: `scale(${rightCardEntrance}) rotate(1.5deg)`,
              opacity: rightCardEntrance,
            }}
          >
            {/* Pill Header */}
            <div
              style={{
                backgroundColor: rightCard.tagColor || "#0D9488",
                color: "#FFFFFF",
                fontSize: 22,
                fontWeight: 900,
                padding: "6px 28px",
                borderRadius: 999,
                boxShadow: "0 4px 12px rgba(13, 148, 136, 0.35)",
                marginBottom: 16,
              }}
            >
              {rightCard.tag}
            </div>

            {/* Polaroid / Paper Card with Masking Tape */}
            <div
              style={{
                position: "relative",
                width: "90%",
                maxWidth: 580,
                backgroundColor: "#FAF7F0",
                borderRadius: 8,
                padding: "24px 28px 20px 28px",
                boxShadow: "0 18px 45px rgba(0,0,0,0.3)",
                display: "flex",
                flexDirection: "column",
              }}
            >
              {/* Corner Masking Tape */}
              <div
                style={{
                  position: "absolute",
                  top: -12,
                  right: 30,
                  width: 90,
                  height: 28,
                  backgroundColor: "rgba(244, 238, 222, 0.85)",
                  transform: "rotate(5deg)",
                  boxShadow: "0 2px 5px rgba(0,0,0,0.15)",
                }}
              />

              {/* Card Title & Content Area */}
              <div
                style={{
                  height: 260,
                  backgroundColor: "#CCFBF1",
                  borderRadius: 6,
                  border: "1.5px solid #99F6E4",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  overflow: "hidden",
                  position: "relative",
                  marginBottom: 16,
                }}
              >
                {/* Visual Map / Graphic Grid Pattern */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    backgroundImage: `
                      linear-gradient(to right, rgba(15, 118, 110, 0.15) 1px, transparent 1px),
                      linear-gradient(to bottom, rgba(15, 118, 110, 0.15) 1px, transparent 1px)
                    `,
                    backgroundSize: "40px 40px",
                  }}
                />
                <div
                  style={{
                    position: "relative",
                    fontSize: 28,
                    fontWeight: 900,
                    color: "#0F766E",
                    textAlign: "center",
                    padding: "0 20px",
                  }}
                >
                  {rightCard.title}
                </div>
              </div>

              {/* Bold Takeaway Caption */}
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 900,
                  color: "#0F172A",
                  textAlign: "center",
                  lineHeight: 1.3,
                }}
              >
                {rightCard.caption}
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Takeaway Note */}
        {summary && (
          <div
            style={{
              marginTop: 15,
              fontSize: 15,
              fontWeight: 700,
              color: "rgba(255, 255, 255, 0.75)",
              letterSpacing: 0.5,
              textAlign: "center",
            }}
          >
            {summary}
          </div>
        )}
      </div>
    </CoordinateZeroBackground>
  );
};
