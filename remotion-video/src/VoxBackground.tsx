import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";

export interface VoxBackgroundProps {
  bgSrc?: string;
  dim?: number;
  category?: string;
  children?: React.ReactNode;
}

export const VoxBackground: React.FC<VoxBackgroundProps> = ({
  bgSrc,
  dim = 0.4,
  category = "VOX EXPLAINER / DEEP DIVE INVESTIGATION",
  children,
}) => {
  const frame = useCurrentFrame();
  const bgScale = 1 + frame * 0.0003;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#121316",
        color: "#FFFFFF",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans TC', sans-serif",
        overflow: "hidden",
      }}
    >
      {/* Background image if provided */}
      {bgSrc && (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <Img
            src={staticFile(bgSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${bgScale})`,
              filter: "grayscale(0.8) contrast(1.2)",
              opacity: 0.25,
            }}
          />
          <AbsoluteFill style={{ backgroundColor: `rgba(18, 19, 22, ${dim})` }} />
        </AbsoluteFill>
      )}

      {/* Modern Vox Editorial Grid & Halftone */}
      <AbsoluteFill
        style={{
          backgroundImage: `
            linear-gradient(to right, rgba(255, 255, 255, 0.04) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.04) 1px, transparent 1px)
          `,
          backgroundSize: "40px 40px",
          pointerEvents: "none",
        }}
      />

      {/* Top Editorial Category Banner */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 36,
          backgroundColor: "#181A20",
          borderBottom: "2px solid #FACC15",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 36px",
          zIndex: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 10, height: 10, backgroundColor: "#FACC15" }} />
          <span style={{ fontSize: 12, fontWeight: 900, color: "#FACC15", letterSpacing: 1.5 }}>
            {category}
          </span>
        </div>
        <span style={{ fontSize: 11, fontWeight: 700, color: "#94A3B8", letterSpacing: 1 }}>
          VISUAL JOURNALISM
        </span>
      </div>

      {/* Content */}
      <div style={{ position: "relative", zIndex: 5, height: "100%", width: "100%", paddingTop: 36 }}>
        {children}
      </div>
    </AbsoluteFill>
  );
};
