import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface GlassTagProps {
  text?: string;
  accentColor?: string;
  style?: React.CSSProperties;
}

export const GlassTag: React.FC<GlassTagProps> = ({
  text,
  accentColor = "#38BDF8",
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!text || !text.trim()) {
    return null;
  }

  const entrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 130 },
  });

  const opacity = Math.min(1, Math.max(0, entrance));
  const translateY = (1 - entrance) * 16;
  const scale = 0.92 + 0.08 * entrance;

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 22px",
        borderRadius: 9999,
        background: "rgba(15, 23, 42, 0.65)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        border: "1px solid rgba(255, 255, 255, 0.2)",
        boxShadow:
          "0 8px 32px 0 rgba(0, 0, 0, 0.37), inset 0 1px 0 rgba(255, 255, 255, 0.15)",
        opacity,
        transform: `translateY(${translateY}px) scale(${scale})`,
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans TC', 'Microsoft JhengHei', sans-serif",
        ...style,
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          backgroundColor: accentColor,
          boxShadow: `0 0 10px ${accentColor}`,
          flexShrink: 0,
        }}
      />
      <span
        style={{
          color: "#FFFFFF",
          fontSize: 22,
          fontWeight: 700,
          letterSpacing: "0.06em",
          whiteSpace: "nowrap",
        }}
      >
        {text.trim()}
      </span>
    </div>
  );
};
