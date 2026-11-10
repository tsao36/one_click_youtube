import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { VoxBackground } from "./VoxBackground";
import { VoxKeyStatSceneProps } from "./types";
import {
  GlintSheen,
  RadarBeacon,
  useContinuousDrift,
  useCountUp,
} from "./animations";

export const VoxKeyStatScene: React.FC<VoxKeyStatSceneProps> = ({
  headline = "GLOBAL ENERGY CRISIS",
  tag = "KEY FINDING",
  mainStat = "74%",
  statLabel = "of industrial supply chains disrupted by geopolitical embargoes",
  supportingPoints = [
    { label: "Estimated loss", value: "$1.4 Trillion", trend: "down" },
    { label: "Affected countries", value: "48 Nations", trend: "neutral" },
    { label: "Recovery timeframe", value: "24-36 Months", trend: "neutral" },
  ],
  source = "VOX INVESTIGATIVE DATABASE / WORLD BANK 2024 REPORT",
  accentColor = "#FACC15",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { floatY, glowPulse } = useContinuousDrift(0.0002);

  // Entrance spring
  const headerEntrance = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 130 },
  });

  const statEntrance = spring({
    frame: frame - 6,
    fps,
    config: { damping: 12, stiffness: 140 },
  });

  // Animated Underline Bar Progress
  const lineProgress = interpolate(frame, [14, 38], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const pointsEntrance = spring({
    frame: frame - 18,
    fps,
    config: { damping: 15, stiffness: 100 },
  });

  // Rolling count-up for the big stat
  const { display: animatedStat, punchScale } = useCountUp(mainStat, {
    startFrame: 6,
    duration: 30,
    fps,
  });

  return (
    <VoxBackground accentColor={accentColor} headline={headline}>
      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "60px 100px",
          transform: `translateY(${floatY}px)`,
        }}
      >
        {/* Main Content Box */}
        <div
          style={{
            maxWidth: "1300px",
            width: "100%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
            transform: `translateY(${(1 - headerEntrance) * 30}px)`,
            opacity: headerEntrance,
          }}
        >
          {/* Tag pill with Live Radar Beacon */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "10px",
              backgroundColor: accentColor,
              color: "#000000",
              fontWeight: 900,
              fontSize: "15px",
              letterSpacing: "3px",
              textTransform: "uppercase",
              padding: "6px 20px",
              borderRadius: "4px",
              marginBottom: "28px",
              boxShadow: `0 0 ${16 * glowPulse}px ${accentColor}88`,
            }}
          >
            <RadarBeacon color="#000000" size={8} />
            <span>{tag}</span>
          </div>

          {/* Big Number / Stat with Rolling Count-up & Completion Punch */}
          <div
            style={{
              position: "relative",
              marginBottom: "16px",
              transform: `scale(${
                interpolate(statEntrance, [0, 1], [0.85, 1]) * punchScale
              })`,
              opacity: statEntrance,
            }}
          >
            <h1
              style={{
                fontSize: "144px",
                fontWeight: 950,
                color: "#ffffff",
                lineHeight: 0.95,
                margin: 0,
                letterSpacing: "-3px",
                fontFamily:
                  'Impact, "Arial Black", "PingFang SC", "Microsoft YaHei", sans-serif',
                textShadow: `0 8px 30px rgba(0,0,0,0.8), 0 0 ${
                  25 * glowPulse
                }px ${accentColor}33`,
              }}
            >
              {animatedStat}
            </h1>

            {/* Sharp Underline marker with travelling leading head */}
            <div
              style={{
                position: "absolute",
                bottom: "-10px",
                left: "50%",
                transform: "translateX(-50%)",
                width: `${lineProgress}%`,
                maxWidth: "100%",
                height: "10px",
                backgroundColor: accentColor,
                borderRadius: "2px",
                boxShadow: `0 0 16px ${accentColor}`,
              }}
            />

            {/* Shimmer sweep over giant stat */}
            <GlintSheen color={`${accentColor}BB`} periodFrames={85} />
          </div>

          {/* Stat Label */}
          <p
            style={{
              fontSize: "28px",
              fontWeight: 600,
              color: "#E2E8F0",
              maxWidth: "850px",
              lineHeight: 1.45,
              marginTop: "26px",
              marginBottom: "44px",
              opacity: headerEntrance,
              textShadow: "0 2px 10px rgba(0,0,0,0.8)",
            }}
          >
            {statLabel}
          </p>

          {/* Supporting metrics row with staggered entrance */}
          {supportingPoints && supportingPoints.length > 0 && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: `repeat(${supportingPoints.length}, 1fr)`,
                gap: "24px",
                width: "100%",
                maxWidth: "1050px",
                opacity: pointsEntrance,
                transform: `translateY(${(1 - pointsEntrance) * 20}px)`,
              }}
            >
              {supportingPoints.map((pt, idx) => {
                const itemSpring = spring({
                  frame: frame - (18 + idx * 5),
                  fps,
                  config: { damping: 14, stiffness: 120 },
                });

                return (
                  <div
                    key={idx}
                    style={{
                      position: "relative",
                      backgroundColor: "rgba(255, 255, 255, 0.06)",
                      border: "1px solid rgba(255, 255, 255, 0.14)",
                      borderTop: `3px solid ${accentColor}`,
                      padding: "18px 24px",
                      borderRadius: "6px",
                      backdropFilter: "blur(12px)",
                      textAlign: "left",
                      opacity: itemSpring,
                      transform: `translateY(${interpolate(
                        itemSpring,
                        [0, 1],
                        [16, 0]
                      )}px)`,
                      boxShadow: `0 8px 20px rgba(0,0,0,0.4), 0 0 ${
                        10 * glowPulse
                      }px ${accentColor}18`,
                    }}
                  >
                    <div
                      style={{
                        fontSize: "13px",
                        color: "#94A3B8",
                        letterSpacing: "1px",
                        textTransform: "uppercase",
                        fontWeight: 700,
                        marginBottom: "8px",
                      }}
                    >
                      {pt.label}
                    </div>
                    <div
                      style={{
                        fontSize: "30px",
                        fontWeight: 800,
                        color: "#FFFFFF",
                        fontFamily: '"Arial Black", Impact, sans-serif',
                        letterSpacing: "0.5px",
                      }}
                    >
                      {pt.value}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Footnote / Source */}
          {source && (
            <div
              style={{
                marginTop: "40px",
                fontSize: "13px",
                letterSpacing: "1.5px",
                color: "#94A3B8",
                fontWeight: 600,
                textTransform: "uppercase",
                opacity: headerEntrance,
              }}
            >
              [ {source} ]
            </div>
          )}
        </div>
      </AbsoluteFill>
    </VoxBackground>
  );
};
