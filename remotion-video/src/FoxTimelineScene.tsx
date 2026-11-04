import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FoxBackground } from "./FoxBackground";
import { FoxTimelineSceneProps } from "./types";

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

  const headerSpring = spring({
    frame,
    fps,
    config: { damping: 16, mass: 0.8, stiffness: 120 },
  });

  const timelineSpring = spring({
    frame: frame - 8,
    fps,
    config: { damping: 16, mass: 0.9, stiffness: 110 },
  });

  // Animated line progress from 0% to 100%
  const progress = interpolate(frame, [15, 55], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const p1Spring = spring({ frame: frame - 18, fps });
  const p2Spring = spring({ frame: frame - 32, fps });
  const p3Spring = spring({ frame: frame - 48, fps });

  return (
    <FoxBackground bgSrc={bgSrc} dim={dim}>
      <div
        style={{
          position: "absolute",
          top: 180,
          left: 140,
          right: 140,
          zIndex: 20,
        }}
      >
        {/* Chapter / Badge */}
        {chapter && (
          <div
            style={{
              fontSize: 22,
              fontWeight: 800,
              color: accentColor,
              letterSpacing: 3,
              textTransform: "uppercase",
              opacity: headerSpring,
              transform: `translateY(${interpolate(headerSpring, [0, 1], [-10, 0])}px)`,
              marginBottom: 10,
            }}
          >
            {chapter}
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
            margin: "0 0 70px 0",
            opacity: headerSpring,
            transform: `translateY(${interpolate(headerSpring, [0, 1], [16, 0])}px)`,
            textShadow: "0 3px 16px rgba(0, 0, 0, 0.8)",
          }}
        >
          {title}
        </h1>

        {/* Timeline Slider Track */}
        <div
          style={{
            position: "relative",
            width: "100%",
            maxWidth: 1200,
            height: 180,
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

          {/* Active progress rail */}
          <div
            style={{
              position: "absolute",
              top: 50,
              left: 40,
              width: `calc((100% - 80px) * ${progress / 100})`,
              height: 4,
              backgroundColor: accentColor,
              borderRadius: 2,
              boxShadow: `0 0 16px ${accentColor}AA`,
            }}
          />

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
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                backgroundColor: "#0F172A",
                border: `4px solid ${accentColor}`,
                boxShadow: `0 0 16px ${accentColor}88`,
                marginBottom: 16,
              }}
            />
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
                color: "rgba(255, 255, 255, 0.75)",
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
                opacity: progress >= 50 ? p2Spring : 0.3,
              }}
            >
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  backgroundColor: "#0F172A",
                  border: `3px solid ${progress >= 50 ? accentColor : "rgba(255,255,255,0.4)"}`,
                  boxShadow: progress >= 50 ? `0 0 12px ${accentColor}66` : "none",
                  marginBottom: 18,
                }}
              />
              <div
                style={{
                  fontSize: 28,
                  fontWeight: 800,
                  color: progress >= 50 ? "#FFFFFF" : "rgba(255, 255, 255, 0.6)",
                  fontFamily: "system-ui, -apple-system, sans-serif",
                  letterSpacing: 1,
                }}
              >
                {middleYear}
              </div>
              <div
                style={{
                  fontSize: 17,
                  color: "rgba(255, 255, 255, 0.65)",
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
              opacity: progress >= 95 ? p3Spring : 0.3,
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                backgroundColor: "#0F172A",
                border: `4px solid ${progress >= 95 ? accentColor : "rgba(255,255,255,0.4)"}`,
                boxShadow: progress >= 95 ? `0 0 16px ${accentColor}88` : "none",
                marginBottom: 16,
              }}
            />
            <div
              style={{
                fontSize: 32,
                fontWeight: 900,
                color: progress >= 95 ? "#FFFFFF" : "rgba(255, 255, 255, 0.6)",
                fontFamily: "system-ui, -apple-system, sans-serif",
                letterSpacing: 1,
              }}
            >
              {endYear}
            </div>
            <div
              style={{
                fontSize: 18,
                color: "rgba(255, 255, 255, 0.8)",
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

        {/* Subtext description below slider */}
        {subtext && (
          <div
            style={{
              fontSize: 24,
              color: "rgba(255, 255, 255, 0.8)",
              marginTop: 60,
              maxWidth: 1000,
              lineHeight: 1.5,
              opacity: headerSpring,
              textShadow: "0 2px 10px rgba(0, 0, 0, 0.8)",
            }}
          >
            {subtext}
          </div>
        )}
      </div>

      {/* Source Footnote */}
      {source && (
        <div
          style={{
            position: "absolute",
            bottom: 48,
            right: 80,
            fontSize: 16,
            color: "rgba(255, 255, 255, 0.45)",
            letterSpacing: 0.5,
            zIndex: 20,
          }}
        >
          {source}
        </div>
      )}
    </FoxBackground>
  );
};
