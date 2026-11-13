import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { useCountUp } from "./animations";

export interface MetricData {
  value: string;
  unit?: string;
  label?: string;
}

export interface MetricCardProps {
  data?: MetricData | null;
  accentColor?: string;
  style?: React.CSSProperties;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  data,
  accentColor = "#38BDF8",
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!data || !data.value) {
    return null;
  }

  // Fast pop entrance (0.5s)
  const entrance = spring({
    frame: frame - 4,
    fps,
    config: { damping: 13, mass: 0.85, stiffness: 120 },
  });

  // 0.5s pop/count-up (approx 15 frames at 30fps)
  const { display: animatedValue, punchScale } = useCountUp(data.value, {
    startFrame: 6,
    duration: 15,
    fps,
  });

  const opacity = Math.min(1, Math.max(0, entrance));
  const scale = (0.88 + 0.12 * entrance) * punchScale;
  const translateY = (1 - entrance) * 20;

  return (
    <div
      style={{
        display: "inline-flex",
        flexDirection: "column",
        gap: 6,
        padding: "16px 24px",
        borderRadius: 16,
        background: "rgba(15, 23, 42, 0.78)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        border: "1px solid rgba(255, 255, 255, 0.18)",
        boxShadow:
          "0 20px 40px rgba(0, 0, 0, 0.45), 0 0 20px rgba(56, 189, 248, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.2)",
        opacity,
        transform: `translateY(${translateY}px) scale(${scale})`,
        transformOrigin: "top right",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans TC', 'Microsoft JhengHei', sans-serif",
        ...style,
      }}
    >
      {data.label && (
        <span
          style={{
            fontSize: 15,
            fontWeight: 600,
            color: "#94A3B8",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          {data.label}
        </span>
      )}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 6,
        }}
      >
        <span
          style={{
            fontSize: 54,
            fontWeight: 800,
            lineHeight: 1,
            color: "#FFFFFF",
            fontVariantNumeric: "tabular-nums",
            letterSpacing: "-0.02em",
          }}
        >
          {animatedValue}
        </span>
        {data.unit && (
          <span
            style={{
              fontSize: 24,
              fontWeight: 700,
              color: accentColor,
              letterSpacing: "0.02em",
            }}
          >
            {data.unit}
          </span>
        )}
      </div>
    </div>
  );
};
