import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";

export interface FinanceBackgroundProps {
  bgSrc?: string;
  dim?: number;
  tickerText?: string;
  accentColor?: string;
  children?: React.ReactNode;
}

export const FinanceBackground: React.FC<FinanceBackgroundProps> = ({
  bgSrc,
  dim = 0.35,
  tickerText = "NASDAQ ▲ +1.42%   S&P 500 ▲ +0.85%   NVDA ▲ +3.14%   TSMC ▲ +2.48%   SOXX ▲ +2.10%   AAPL ▼ -0.32%   MSFT ▲ +0.75%",
  accentColor = "#10B981",
  children,
}) => {
  const frame = useCurrentFrame();
  const bgScale = 1 + frame * 0.0003;

  // Seamless looping ticker offset
  const tickerOffset = (frame * 1.5) % 800;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#070B16",
        backgroundImage: `
          radial-gradient(ellipse at 70% 30%, #0D1A33 0%, #060913 100%)
        `,
        color: "#F8FAFC",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans TC', sans-serif",
        overflow: "hidden",
      }}
    >
      {/* Background Image if present */}
      {bgSrc && (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <Img
            src={staticFile(bgSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${bgScale})`,
              filter: "blur(2px) saturate(0.8)",
              opacity: 0.25,
            }}
          />
          <AbsoluteFill style={{ backgroundColor: `rgba(7, 11, 22, ${dim})` }} />
        </AbsoluteFill>
      )}

      {/* Financial Terminal Chart Grid */}
      <AbsoluteFill
        style={{
          backgroundImage: `
            linear-gradient(to right, rgba(30, 41, 59, 0.45) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(30, 41, 59, 0.45) 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
          pointerEvents: "none",
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage: `
            linear-gradient(to right, rgba(16, 185, 129, 0.06) 1.5px, transparent 1.5px),
            linear-gradient(to bottom, rgba(16, 185, 129, 0.06) 1.5px, transparent 1.5px)
          `,
          backgroundSize: "240px 240px",
          pointerEvents: "none",
        }}
      />

      {/* Top Financial Ticker Tape */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 38,
          backgroundColor: "rgba(10, 17, 36, 0.88)",
          borderBottom: "1px solid rgba(56, 189, 248, 0.18)",
          backdropFilter: "blur(6px)",
          display: "flex",
          alignItems: "center",
          overflow: "hidden",
          zIndex: 10,
        }}
      >
        <div
          style={{
            position: "absolute",
            left: 20,
            display: "flex",
            alignItems: "center",
            gap: 8,
            backgroundColor: "#0F172A",
            padding: "2px 10px",
            borderRadius: 4,
            border: `1px solid ${accentColor}`,
            zIndex: 12,
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              backgroundColor: accentColor,
              boxShadow: `0 0 8px ${accentColor}`,
            }}
          />
          <span style={{ fontSize: 11, fontWeight: 800, color: accentColor, letterSpacing: 1 }}>
            LIVE MARKET TERMINAL
          </span>
        </div>

        <div
          style={{
            display: "flex",
            whiteSpace: "nowrap",
            transform: `translateX(220px)`,
            fontFamily: "monospace",
            fontSize: 12,
            fontWeight: 700,
            color: "#94A3B8",
            letterSpacing: 1.2,
          }}
        >
          <span style={{ transform: `translateX(-${tickerOffset}px)` }}>
            {tickerText} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {tickerText}
          </span>
        </div>
      </div>

      {/* Content Layer */}
      <div style={{ position: "relative", zIndex: 5, height: "100%", width: "100%", paddingTop: 38 }}>
        {children}
      </div>
    </AbsoluteFill>
  );
};
