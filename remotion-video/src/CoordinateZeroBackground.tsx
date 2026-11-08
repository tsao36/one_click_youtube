import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";

export interface CoordinateZeroBackgroundProps {
  bgSrc?: string;
  dim?: number;
  showPaper?: boolean;
  paperPadding?: number | string;
  children?: React.ReactNode;
}

export const CoordinateZeroBackground: React.FC<CoordinateZeroBackgroundProps> = ({
  bgSrc,
  dim = 0.2,
  showPaper = false,
  paperPadding = "60px 80px",
  children,
}) => {
  const frame = useCurrentFrame();

  // Subtle breathing camera drift
  const bgScale = 1 + frame * 0.0003;

  // Cutting mat border marks
  const horizontalTicks = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60];
  const verticalTicks = [0, 5, 10, 15, 20, 25, 30, 35];

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#163C2E",
        backgroundImage: `
          radial-gradient(ellipse at 50% 40%, #1A4737 0%, #112F24 100%)
        `,
        color: "#1E293B",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Noto Sans TC', 'Microsoft JhengHei', sans-serif",
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
              filter: "blur(1.5px) saturate(0.9)",
              opacity: 0.35,
            }}
          />
          <AbsoluteFill
            style={{
              backgroundColor: `rgba(22, 60, 46, ${dim})`,
            }}
          />
        </AbsoluteFill>
      )}

      {/* Cutting Mat Minor & Major Grid Lines */}
      <AbsoluteFill
        style={{
          backgroundImage: `
            linear-gradient(to right, rgba(255, 255, 255, 0.065) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.065) 1px, transparent 1px)
          `,
          backgroundSize: "40px 40px",
          pointerEvents: "none",
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage: `
            linear-gradient(to right, rgba(255, 255, 255, 0.16) 1.5px, transparent 1.5px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.16) 1.5px, transparent 1.5px)
          `,
          backgroundSize: "200px 200px",
          pointerEvents: "none",
        }}
      />

      {/* 45° Angle Cutting Mat Guide Lines */}
      <svg
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
          opacity: 0.18,
        }}
      >
        <line x1="0" y1="1080" x2="1080" y2="0" stroke="#FFFFFF" strokeWidth="1" strokeDasharray="6 6" />
        <line x1="840" y1="1080" x2="1920" y2="0" stroke="#FFFFFF" strokeWidth="1" strokeDasharray="6 6" />
        <line x1="1400" y1="1080" x2="1920" y2="560" stroke="#FFFFFF" strokeWidth="1" strokeDasharray="6 6" />
        <line x1="0" y1="500" x2="500" y2="0" stroke="#FFFFFF" strokeWidth="1" strokeDasharray="6 6" />
      </svg>

      {/* Cutting Mat Top Ruler Numbers */}
      <div
        style={{
          position: "absolute",
          top: 6,
          left: 40,
          right: 40,
          display: "flex",
          justifyContent: "space-between",
          color: "rgba(255, 255, 255, 0.4)",
          fontSize: 13,
          fontWeight: 700,
          fontFamily: "monospace",
          pointerEvents: "none",
        }}
      >
        {horizontalTicks.map((n) => (
          <span key={`ht-${n}`}>{n}</span>
        ))}
      </div>

      {/* Cutting Mat Left Ruler Numbers */}
      <div
        style={{
          position: "absolute",
          top: 35,
          bottom: 35,
          left: 8,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          color: "rgba(255, 255, 255, 0.4)",
          fontSize: 13,
          fontWeight: 700,
          fontFamily: "monospace",
          pointerEvents: "none",
        }}
      >
        {verticalTicks.map((n) => (
          <span key={`vt-${n}`}>{n}</span>
        ))}
      </div>

      {/* Optional Central Ivory Paper Sheet */}
      {showPaper ? (
        <div
          style={{
            position: "absolute",
            top: 48,
            left: 72,
            right: 72,
            bottom: 48,
            backgroundColor: "#FAF7F0",
            borderRadius: 6,
            boxShadow:
              "0 20px 50px rgba(0, 0, 0, 0.35), 0 2px 8px rgba(0, 0, 0, 0.2)",
            padding: paperPadding,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* Subtle cartographic blue grid on paper */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              backgroundImage: `
                linear-gradient(to right, rgba(14, 116, 144, 0.08) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(14, 116, 144, 0.08) 1px, transparent 1px)
              `,
              backgroundSize: "70px 70px",
              pointerEvents: "none",
            }}
          />

          {/* Corner Masking Tapes (Washi Tape) */}
          <div
            style={{
              position: "absolute",
              top: -8,
              left: 40,
              width: 110,
              height: 34,
              backgroundColor: "rgba(244, 238, 222, 0.82)",
              backdropFilter: "blur(2px)",
              transform: "rotate(-4deg)",
              boxShadow: "0 2px 6px rgba(0,0,0,0.12)",
              borderLeft: "2px dashed rgba(200,190,170,0.5)",
              borderRight: "2px dashed rgba(200,190,170,0.5)",
              pointerEvents: "none",
              zIndex: 10,
            }}
          />
          <div
            style={{
              position: "absolute",
              top: -8,
              right: 40,
              width: 110,
              height: 34,
              backgroundColor: "rgba(244, 238, 222, 0.82)",
              backdropFilter: "blur(2px)",
              transform: "rotate(3deg)",
              boxShadow: "0 2px 6px rgba(0,0,0,0.12)",
              borderLeft: "2px dashed rgba(200,190,170,0.5)",
              borderRight: "2px dashed rgba(200,190,170,0.5)",
              pointerEvents: "none",
              zIndex: 10,
            }}
          />

          <div style={{ position: "relative", zIndex: 2, height: "100%", width: "100%" }}>
            {children}
          </div>
        </div>
      ) : (
        <div style={{ position: "relative", zIndex: 2, height: "100%", width: "100%" }}>
          {children}
        </div>
      )}
    </AbsoluteFill>
  );
};
