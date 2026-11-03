import React from "react";
import {
  AbsoluteFill,
  Img,
  staticFile,
  useCurrentFrame,
} from "remotion";

export interface BlueprintBackgroundProps {
  bgSrc?: string;
  dim?: number;
  badge?: string;
  title?: string;
  subtitle?: string;
  accentColor?: string;
  children: React.ReactNode;
}

export const BlueprintBackground: React.FC<BlueprintBackgroundProps> = ({
  bgSrc,
  dim = 0.75,
  badge = "INVESTIGATIVE ANALYSIS",
  title,
  subtitle,
  accentColor = "#00F5FF",
  children,
}) => {
  const frame = useCurrentFrame();

  // Subtle slow push-in for background
  const bgScale = 1 + frame * 0.0006;
  const gridOpacity = 0.08;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#070B12",
        color: "#FFFFFF",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans TC', 'Microsoft JhengHei', sans-serif",
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
              filter: "blur(2px) saturate(0.85) contrast(1.1)",
            }}
          />
          {/* Dimmer overlay */}
          <AbsoluteFill
            style={{
              backgroundColor: `rgba(7, 11, 18, ${dim})`,
            }}
          />
        </AbsoluteFill>
      )}

      {/* Blueprint Grid Lines & Dots */}
      <AbsoluteFill
        style={{
          backgroundImage: `
            linear-gradient(to right, rgba(255, 255, 255, ${gridOpacity}) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, ${gridOpacity}) 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
          pointerEvents: "none",
        }}
      />

      {/* Radial Vignette */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 40%, rgba(5, 7, 13, 0.88) 100%)",
          pointerEvents: "none",
        }}
      />

      {/* Technical HUD Frame & Corner Reticles */}
      <div
        style={{
          position: "absolute",
          top: 36,
          left: 48,
          right: 48,
          bottom: 36,
          border: "1px solid rgba(255, 255, 255, 0.07)",
          pointerEvents: "none",
          zIndex: 5,
        }}
      >
        {/* Corner Crosshairs */}
        <div style={{ position: "absolute", top: -8, left: -8, color: accentColor, fontSize: 16, fontWeight: "bold" }}>+</div>
        <div style={{ position: "absolute", top: -8, right: -8, color: accentColor, fontSize: 16, fontWeight: "bold" }}>+</div>
        <div style={{ position: "absolute", bottom: -8, left: -8, color: accentColor, fontSize: 16, fontWeight: "bold" }}>+</div>
        <div style={{ position: "absolute", bottom: -8, right: -8, color: accentColor, fontSize: 16, fontWeight: "bold" }}>+</div>

        {/* Top Header Bar */}
        <div
          style={{
            position: "absolute",
            top: 12,
            left: 16,
            right: 16,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 12,
            letterSpacing: "0.15em",
            color: "rgba(255, 255, 255, 0.5)",
            fontFamily: "monospace",
            textTransform: "uppercase",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                display: "inline-block",
                width: 7,
                height: 7,
                backgroundColor: accentColor,
                borderRadius: "50%",
                boxShadow: `0 0 8px ${accentColor}`,
              }}
            />
            <span style={{ color: "#FFFFFF", fontWeight: 700 }}>{badge}</span>
            <span style={{ color: "rgba(255, 255, 255, 0.3)" }}>|</span>
            <span>SYSTEM 1080P // BLUEPRINT V2</span>
          </div>
          <div>
            <span>FRAME: {frame.toString().padStart(4, "0")}</span>
            <span style={{ marginLeft: 16, color: accentColor }}>LATENCY &lt; 1.5ms</span>
          </div>
        </div>

        {/* Bottom Status Bar */}
        <div
          style={{
            position: "absolute",
            bottom: 12,
            left: 16,
            right: 16,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 11,
            letterSpacing: "0.12em",
            color: "rgba(255, 255, 255, 0.4)",
            fontFamily: "monospace",
          }}
        >
          <span>PRECISION MEDICAL TELEMETRY // STAGE STUDIO</span>
          <span>SCALE: 1:1 // CALIBRATED</span>
        </div>
      </div>

      {/* Main Content Area */}
      <AbsoluteFill
        style={{
          padding: "80px 72px 64px 72px",
          display: "flex",
          flexDirection: "column",
          zIndex: 10,
        }}
      >
        {/* Title & Subtitle Block if provided */}
        {title && (
          <div style={{ marginBottom: 28, zIndex: 12 }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                backgroundColor: "rgba(0, 245, 255, 0.1)",
                border: `1px solid ${accentColor}44`,
                padding: "4px 12px",
                borderRadius: 4,
                marginBottom: 10,
              }}
            >
              <span
                style={{
                  fontSize: 12,
                  fontFamily: "monospace",
                  letterSpacing: "0.15em",
                  color: accentColor,
                  fontWeight: 700,
                  textTransform: "uppercase",
                }}
              >
                {badge}
              </span>
            </div>
            <h1
              style={{
                fontSize: 44,
                fontWeight: 900,
                letterSpacing: "-0.02em",
                margin: "0 0 8px 0",
                color: "#FFFFFF",
                textShadow: "0 4px 16px rgba(0,0,0,0.8)",
                lineHeight: 1.2,
              }}
            >
              {title}
            </h1>
            {subtitle && (
              <p
                style={{
                  fontSize: 20,
                  margin: 0,
                  color: "rgba(255, 255, 255, 0.72)",
                  fontWeight: 400,
                  maxWidth: 1200,
                  lineHeight: 1.4,
                }}
              >
                {subtitle}
              </p>
            )}
          </div>
        )}

        {/* Children Visual Component */}
        <div style={{ flex: 1, position: "relative" }}>{children}</div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
