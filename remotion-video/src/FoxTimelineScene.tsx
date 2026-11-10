import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FoxBackground } from "./FoxBackground";
import { FoxTimelineSceneProps } from "./types";
import {
  DynamicAccentBar,
  GlintSheen,
  RadarBeacon,
  useContinuousDrift,
} from "./animations";

export const FoxTimelineScene: React.FC<FoxTimelineSceneProps> = ({
  chapter = "時間演進",
  title = "長達 20 年的換車長跑歷程",
  startYear = "2000",
  startLabel = "陸軍首度提出採購新戰車需求",
  endYear = "2019",
  endLabel = "正式簽署發價書 (LOA)",
  middleYear = "2011",
  middleLabel = "評估採購二手 M1A1",
  subtext = "橫跨近二十年漫長建案評估，最終拍板採購全新 M1A2T",
  source = "",
  bgSrc = "",
  dim = 0.45,
  accentColor = "#38BDF8",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { floatY, glowPulse } = useContinuousDrift(0.0002);

  const headerSpring = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 130 },
  });

  const timelineSpring = spring({
    frame: frame - 8,
    fps,
    config: { damping: 14, mass: 0.85, stiffness: 110 },
  });

  // Animated line progress from 0% to 100%
  const progress = interpolate(frame, [15, 60], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const p1Spring = spring({ frame: frame - 16, fps, config: { damping: 12 } });
  const p2Spring = spring({ frame: frame - 35, fps, config: { damping: 12 } });
  const p3Spring = spring({ frame: frame - 55, fps, config: { damping: 12 } });

  // Shockwave expansion when node is reached
  const shock1 = frame >= 15 ? ((frame - 15) % 35) / 35 : 0;
  const shock2 = frame >= 35 ? ((frame - 35) % 35) / 35 : 0;
  const shock3 = frame >= 55 ? ((frame - 55) % 35) / 35 : 0;

  const isMidActive = progress >= 50;
  const isEndActive = progress >= 95;

  return (
    <FoxBackground bgSrc={bgSrc} dim={dim}>
      <div
        style={{
          position: "absolute",
          top: 160,
          left: 140,
          right: 140,
          zIndex: 20,
          transform: `translateY(${floatY}px)`,
        }}
      >
        {/* Chapter / Badge with Live Radar Beacon */}
        {chapter && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "5px 16px",
              borderRadius: 20,
              backgroundColor: "rgba(255, 255, 255, 0.08)",
              border: `1px solid ${accentColor}55`,
              backdropFilter: "blur(12px)",
              fontSize: 20,
              fontWeight: 800,
              color: accentColor,
              letterSpacing: 3,
              textTransform: "uppercase",
              opacity: headerSpring,
              transform: `translateY(${interpolate(
                headerSpring,
                [0, 1],
                [-12, 0]
              )}px)`,
              marginBottom: 12,
              boxShadow: `0 0 ${10 * glowPulse}px ${accentColor}44`,
            }}
          >
            <RadarBeacon color={accentColor} size={8} />
            <span>{chapter}</span>
          </div>
        )}

        {/* Title */}
        <h1
          style={{
            fontSize: 48,
            fontWeight: 900,
            color: "#FFFFFF",
            letterSpacing: "-0.5px",
            lineHeight: 1.25,
            margin: "0 0 16px 0",
            opacity: headerSpring,
            transform: `translateY(${interpolate(
              headerSpring,
              [0, 1],
              [18, 0]
            )}px)`,
            textShadow: `0 3px 18px rgba(0, 0, 0, 0.85), 0 0 ${
              16 * glowPulse
            }px ${accentColor}22`,
          }}
        >
          {title}
        </h1>

        <DynamicAccentBar
          color={accentColor}
          maxWidth={160}
          startFrame={10}
          duration={24}
          height={4}
          style={{ marginTop: 0, marginBottom: 50 }}
        />

        {/* Timeline Slider Track */}
        <div
          style={{
            position: "relative",
            width: "100%",
            maxWidth: 1200,
            height: 220,
            opacity: timelineSpring,
          }}
        >
          {/* Background rail */}
          <div
            style={{
              position: "absolute",
              top: 50,
              left: 40,
              right: 40,
              height: 4,
              backgroundColor: "rgba(255, 255, 255, 0.15)",
              borderRadius: 2,
            }}
          />

          {/* Active progress rail with luminous glow */}
          <div
            style={{
              position: "absolute",
              top: 50,
              left: 40,
              width: `calc((100% - 80px) * ${progress / 100})`,
              height: 4,
              backgroundColor: accentColor,
              borderRadius: 2,
              boxShadow: `0 0 18px ${accentColor}`,
            }}
          >
            {/* Comet Leading Spark Head */}
            {progress > 1 && progress < 99 && (
              <div
                style={{
                  position: "absolute",
                  right: -6,
                  top: -5,
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  backgroundColor: "#FFFFFF",
                  boxShadow: `0 0 16px 4px ${accentColor}, 0 0 6px #FFFFFF`,
                }}
              />
            )}
          </div>

          {/* Node 1: Start */}
          <div
            style={{
              position: "absolute",
              top: 36,
              left: 40,
              transform: "translateX(-50%)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              opacity: p1Spring,
            }}
          >
            <div style={{ position: "relative" }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  backgroundColor: "#0F172A",
                  border: `4px solid ${accentColor}`,
                  boxShadow: `0 0 16px ${accentColor}`,
                  marginBottom: 16,
                  transform: `scale(${interpolate(p1Spring, [0, 1], [0.6, 1])})`,
                }}
              />
              {/* Expanding Shockwave */}
              {frame >= 15 && (
                <div
                  style={{
                    position: "absolute",
                    top: -16 * shock1,
                    left: -16 * shock1,
                    width: 32 + 32 * shock1,
                    height: 32 + 32 * shock1,
                    borderRadius: "50%",
                    border: `2px solid ${accentColor}`,
                    opacity: 1 - shock1,
                    pointerEvents: "none",
                  }}
                />
              )}
            </div>

            <div
              style={{
                fontSize: 32,
                fontWeight: 900,
                color: "#FFFFFF",
                fontFamily: "system-ui, -apple-system, sans-serif",
                letterSpacing: 1,
              }}
            >
              {startYear}
            </div>
            <div
              style={{
                fontSize: 18,
                color: "rgba(255, 255, 255, 0.8)",
                marginTop: 6,
                textAlign: "center",
                maxWidth: 220,
                lineHeight: 1.35,
              }}
            >
              {startLabel}
            </div>
          </div>

          {/* Node 2: Middle (if present) */}
          {middleYear && (
            <div
              style={{
                position: "absolute",
                top: 36,
                left: "50%",
                transform: "translateX(-50%)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                opacity: isMidActive ? p2Spring : 0.4,
              }}
            >
              <div style={{ position: "relative" }}>
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    backgroundColor: "#0F172A",
                    border: `3.5px solid ${
                      isMidActive ? accentColor : "rgba(255,255,255,0.4)"
                    }`,
                    boxShadow: isMidActive
                      ? `0 0 16px ${accentColor}`
                      : "none",
                    marginBottom: 18,
                    transform: `scale(${
                      isMidActive
                        ? interpolate(p2Spring, [0, 1], [0.6, 1])
                        : 0.9
                    })`,
                  }}
                />
                {isMidActive && (
                  <div
                    style={{
                      position: "absolute",
                      top: -14 * shock2,
                      left: -14 * shock2,
                      width: 28 + 28 * shock2,
                      height: 28 + 28 * shock2,
                      borderRadius: "50%",
                      border: `2px solid ${accentColor}`,
                      opacity: 1 - shock2,
                      pointerEvents: "none",
                    }}
                  />
                )}
              </div>

              <div
                style={{
                  fontSize: 28,
                  fontWeight: 800,
                  color: isMidActive
                    ? "#FFFFFF"
                    : "rgba(255, 255, 255, 0.6)",
                  fontFamily: "system-ui, -apple-system, sans-serif",
                  letterSpacing: 1,
                }}
              >
                {middleYear}
              </div>
              <div
                style={{
                  fontSize: 17,
                  color: isMidActive
                    ? "rgba(255, 255, 255, 0.75)"
                    : "rgba(255, 255, 255, 0.4)",
                  marginTop: 6,
                  textAlign: "center",
                  maxWidth: 220,
                  lineHeight: 1.35,
                }}
              >
                {middleLabel}
              </div>
            </div>
          )}

          {/* Node 3: End */}
          <div
            style={{
              position: "absolute",
              top: 36,
              right: 40,
              transform: "translateX(50%)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              opacity: isEndActive ? p3Spring : 0.4,
            }}
          >
            <div style={{ position: "relative" }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  backgroundColor: isEndActive ? accentColor : "#0F172A",
                  border: `4px solid ${
                    isEndActive ? "#FFFFFF" : "rgba(255,255,255,0.4)"
                  }`,
                  boxShadow: isEndActive
                    ? `0 0 24px ${accentColor}`
                    : "none",
                  marginBottom: 16,
                  transform: `scale(${
                    isEndActive ? interpolate(p3Spring, [0, 1], [0.6, 1]) : 0.9
                  })`,
                }}
              />
              {isEndActive && (
                <div
                  style={{
                    position: "absolute",
                    top: -16 * shock3,
                    left: -16 * shock3,
                    width: 32 + 32 * shock3,
                    height: 32 + 32 * shock3,
                    borderRadius: "50%",
                    border: `2px solid ${accentColor}`,
                    opacity: 1 - shock3,
                    pointerEvents: "none",
                  }}
                />
              )}
            </div>

            <div
              style={{
                fontSize: 32,
                fontWeight: 900,
                color: isEndActive
                  ? accentColor
                  : "rgba(255, 255, 255, 0.6)",
                fontFamily: "system-ui, -apple-system, sans-serif",
                letterSpacing: 1,
                textShadow: isEndActive
                  ? `0 0 16px ${accentColor}88`
                  : "none",
              }}
            >
              {endYear}
            </div>
            <div
              style={{
                fontSize: 18,
                color: isEndActive
                  ? "#FFFFFF"
                  : "rgba(255, 255, 255, 0.4)",
                fontWeight: isEndActive ? 700 : 400,
                marginTop: 6,
                textAlign: "center",
                maxWidth: 240,
                lineHeight: 1.35,
              }}
            >
              {endLabel}
            </div>
          </div>
        </div>

        {/* Subtext description card */}
        {subtext && (
          <div
            style={{
              maxWidth: 900,
              backgroundColor: "rgba(15, 23, 42, 0.75)",
              border: `1px solid ${accentColor}44`,
              borderRadius: 12,
              padding: "16px 24px",
              marginTop: 10,
              fontSize: 22,
              color: "rgba(255, 255, 255, 0.9)",
              lineHeight: 1.5,
              opacity: p2Spring,
              transform: `translateY(${interpolate(
                p2Spring,
                [0, 1],
                [16, 0]
              )}px)`,
            }}
          >
            {subtext}
          </div>
        )}
      </div>

      {/* Source citation */}
      {source && (
        <div
          style={{
            position: "absolute",
            bottom: 48,
            right: 80,
            fontSize: 16,
            color: "rgba(255, 255, 255, 0.5)",
            zIndex: 20,
          }}
        >
          {source}
        </div>
      )}
    </FoxBackground>
  );
};
