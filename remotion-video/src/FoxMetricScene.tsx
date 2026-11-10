import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FoxBackground } from "./FoxBackground";
import { FoxMetricSceneProps } from "./types";
import {
  DynamicAccentBar,
  GlintSheen,
  RadarBeacon,
  useContinuousDrift,
  useCountUp,
} from "./animations";

export const FoxMetricScene: React.FC<FoxMetricSceneProps> = ({
  badge = "核心數據",
  value = "73.6",
  unit = "公噸",
  conversion = "",
  description = "",
  subtext = "",
  source = "",
  bgSrc = "",
  dim = 0.4,
  accentColor = "#38BDF8",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { floatY, glowPulse } = useContinuousDrift(0.0002);

  // Entrance animations
  const badgeSpring = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 130 },
  });

  const valueSpring = spring({
    frame: frame - 6,
    fps,
    config: { damping: 13, mass: 0.85, stiffness: 120 },
  });

  const descSpring = spring({
    frame: frame - 16,
    fps,
    config: { damping: 15, mass: 0.8, stiffness: 100 },
  });

  const subtextSpring = spring({
    frame: frame - 22,
    fps,
    config: { damping: 16, mass: 0.8, stiffness: 90 },
  });

  // Animated dynamic count-up with completion bounce punch!
  const { display: animatedValue, progress: countProgress, punchScale } =
    useCountUp(value, { startFrame: 8, duration: 32, fps });

  return (
    <FoxBackground bgSrc={bgSrc} dim={dim}>
      <div
        style={{
          position: "absolute",
          top: 220,
          left: 160,
          maxWidth: 1100,
          zIndex: 20,
          transform: `translateY(${floatY}px)`,
        }}
      >
        {/* Category / Metric Badge with Live Radar Beacon */}
        {badge && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "6px 18px",
              borderRadius: 20,
              backgroundColor: "rgba(255, 255, 255, 0.08)",
              border: `1px solid ${accentColor}66`,
              backdropFilter: "blur(12px)",
              fontSize: 22,
              fontWeight: 700,
              color: accentColor,
              letterSpacing: 2,
              opacity: badgeSpring,
              transform: `translateY(${interpolate(
                badgeSpring,
                [0, 1],
                [-12, 0]
              )}px)`,
              marginBottom: 20,
              boxShadow: `0 0 ${12 * glowPulse}px ${accentColor}44`,
            }}
          >
            <RadarBeacon color={accentColor} size={8} />
            <span>{badge}</span>
          </div>
        )}

        {/* Massive Metric Value with Rolling Count-up & Completion Punch */}
        <div
          style={{
            position: "relative",
            display: "inline-flex",
            alignItems: "baseline",
            flexWrap: "wrap",
            gap: 16,
            opacity: valueSpring,
            transform: `translateY(${interpolate(
              valueSpring,
              [0, 1],
              [32, 0]
            )}px) scale(${
              interpolate(valueSpring, [0, 1], [0.94, 1]) * punchScale
            })`,
          }}
        >
          <span
            style={{
              fontSize: 104,
              fontWeight: 900,
              color: "#FFFFFF",
              letterSpacing: "-1.5px",
              lineHeight: 1.05,
              textShadow: `0 4px 28px rgba(0, 0, 0, 0.9), 0 0 ${
                25 * glowPulse
              }px ${accentColor}44`,
              fontFamily: "system-ui, -apple-system, sans-serif",
            }}
          >
            {animatedValue}
          </span>

          {unit && (
            <span
              style={{
                fontSize: 48,
                fontWeight: 800,
                color: accentColor,
                letterSpacing: 1,
                textShadow: `0 2px 18px rgba(0, 0, 0, 0.8), 0 0 16px ${accentColor}66`,
                transform: `scale(${interpolate(
                  countProgress,
                  [0, 1],
                  [0.85, 1]
                )})`,
              }}
            >
              {unit}
            </span>
          )}

          {conversion && (
            <span
              style={{
                fontSize: 36,
                fontWeight: 600,
                color: "rgba(255, 255, 255, 0.75)",
                letterSpacing: 1,
                marginLeft: 8,
                textShadow: "0 2px 12px rgba(0, 0, 0, 0.8)",
              }}
            >
              {conversion}
            </span>
          )}

          {/* Shimmer sweep over number */}
          <GlintSheen color={`${accentColor}AA`} periodFrames={90} />
        </div>

        {/* Dynamic Energy Gauge Line Under the Metric */}
        <div
          style={{
            position: "relative",
            width: 320,
            height: 6,
            backgroundColor: "rgba(255, 255, 255, 0.12)",
            borderRadius: 3,
            marginTop: 20,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${countProgress * 100}%`,
              height: "100%",
              backgroundColor: accentColor,
              borderRadius: 3,
              boxShadow: `0 0 16px ${accentColor}`,
            }}
          />
        </div>

        {/* Description / Headline */}
        {description && (
          <h2
            style={{
              fontSize: 40,
              fontWeight: 800,
              color: "#FFFFFF",
              letterSpacing: "-0.5px",
              lineHeight: 1.3,
              margin: "24px 0 0 0",
              opacity: descSpring,
              transform: `translateY(${interpolate(
                descSpring,
                [0, 1],
                [18, 0]
              )}px)`,
              textShadow: "0 3px 14px rgba(0, 0, 0, 0.8)",
            }}
          >
            {description}
          </h2>
        )}

        {/* Subtext / Context clause */}
        {subtext && (
          <p
            style={{
              fontSize: 24,
              color: "rgba(255, 255, 255, 0.85)",
              lineHeight: 1.5,
              marginTop: 16,
              marginBottom: 0,
              opacity: subtextSpring,
              transform: `translateY(${interpolate(
                subtextSpring,
                [0, 1],
                [14, 0]
              )}px)`,
              textShadow: "0 2px 10px rgba(0, 0, 0, 0.8)",
            }}
          >
            {subtext}
          </p>
        )}

        {/* Dynamic Accent Bar */}
        <DynamicAccentBar
          color={accentColor}
          maxWidth={180}
          startFrame={18}
          duration={24}
          height={4}
          style={{ marginTop: 20 }}
        />

        {/* Source citation */}
        {source && (
          <div
            style={{
              fontSize: 16,
              color: "rgba(255, 255, 255, 0.6)",
              marginTop: 22,
              opacity: descSpring,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span
              style={{
                width: 4,
                height: 4,
                borderRadius: "50%",
                backgroundColor: accentColor,
              }}
            />
            <span>{source}</span>
          </div>
        )}
      </div>
    </FoxBackground>
  );
};
