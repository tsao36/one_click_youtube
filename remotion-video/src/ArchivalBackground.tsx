import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";

export interface ArchivalBackgroundProps {
  bgSrc?: string;
  dim?: number;
  archiveId?: string;
  children?: React.ReactNode;
}

export const ArchivalBackground: React.FC<ArchivalBackgroundProps> = ({
  bgSrc,
  dim = 0.2,
  archiveId = "RECORD ID: DECLASSIFIED / 1945-DOC-772",
  children,
}) => {
  const frame = useCurrentFrame();
  const bgScale = 1 + frame * 0.0003;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#EFE6D5",
        backgroundImage: `
          radial-gradient(ellipse at 50% 50%, #FAF4E8 0%, #E2D3B8 100%)
        `,
        color: "#291E14",
        fontFamily:
          "'Noto Serif TC', 'Songti TC', 'GenYoMin2 TW', serif",
        overflow: "hidden",
      }}
    >
      {/* Background Image if supplied */}
      {bgSrc && (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <Img
            src={staticFile(bgSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${bgScale})`,
              filter: "sepia(0.6) contrast(1.1)",
              opacity: 0.22,
            }}
          />
          <AbsoluteFill style={{ backgroundColor: `rgba(239, 230, 213, ${dim})` }} />
        </AbsoluteFill>
      )}

      {/* Subtle aged paper grain lines */}
      <AbsoluteFill
        style={{
          backgroundImage: `
            linear-gradient(to right, rgba(120, 80, 40, 0.04) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(120, 80, 40, 0.04) 1px, transparent 1px)
          `,
          backgroundSize: "30px 30px",
          pointerEvents: "none",
        }}
      />

      {/* Heavy Vignette around edges */}
      <AbsoluteFill
        style={{
          background: "radial-gradient(ellipse at center, transparent 55%, rgba(60, 40, 20, 0.35) 100%)",
          pointerEvents: "none",
        }}
      />

      {/* Top Archival Header Bar */}
      <div
        style={{
          position: "absolute",
          top: 16,
          left: 45,
          right: 45,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1.5px solid rgba(120, 80, 40, 0.3)",
          paddingBottom: 8,
          zIndex: 10,
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 800, letterSpacing: 2, color: "#785028", fontFamily: "monospace" }}>
          NATIONAL ARCHIVES & HISTORICAL RECORDS ADMINISTRATION
        </span>
        <span style={{ fontSize: 13, fontWeight: 900, color: "#991B1B", letterSpacing: 1.5, fontFamily: "monospace" }}>
          {archiveId}
        </span>
      </div>

      {/* Content */}
      <div style={{ position: "relative", zIndex: 5, height: "100%", width: "100%", paddingTop: 30 }}>
        {children}
      </div>
    </AbsoluteFill>
  );
};
