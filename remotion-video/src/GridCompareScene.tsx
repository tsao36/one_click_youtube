import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { GridCompareSceneProps } from "./types";

export const GridCompareScene: React.FC<GridCompareSceneProps> = ({
  leftTitle,
  leftBody,
  rightTitle,
  rightBody,
  comparisonLabel = "VS",
  leftColor = "#3B82F6",
  rightColor = "#EF4444",
  bgSrc = "",
  dim = 0.8,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const leftSpring = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
  });

  const rightSpring = spring({
    frame: Math.max(0, frame - 6),
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
  });

  const badgeSpring = spring({
    frame: Math.max(0, frame - 12),
    fps,
    config: { damping: 12, mass: 0.6, stiffness: 120 },
  });

  const leftX = interpolate(leftSpring, [0, 1], [-60, 0]);
  const rightX = interpolate(rightSpring, [0, 1], [60, 0]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0B0F19",
        color: "#FFFFFF",
        fontFamily: "'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', sans-serif",
        overflow: "hidden",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Background Dimmed Image */}
      {bgSrc ? (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <Img
            src={staticFile(bgSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${1 + frame * 0.0006})`,
            }}
          />
          <AbsoluteFill
            style={{
              backgroundColor: `rgba(11, 15, 25, ${dim})`,
              backdropFilter: "blur(14px)",
            }}
          />
        </AbsoluteFill>
      ) : null}

      <div
        style={{
          position: "relative",
          zIndex: 10,
          maxWidth: 1600,
          width: "90%",
          display: "flex",
          alignItems: "stretch",
          justifyContent: "center",
          gap: 40,
        }}
      >
        {/* Left Card */}
        <div
          style={{
            flex: 1,
            padding: "50px 48px",
            background: "rgba(17, 24, 39, 0.8)",
            backdropFilter: "blur(20px)",
            borderRadius: 24,
            border: `1.5px solid ${leftColor}55`,
            boxShadow: `0 20px 40px -10px rgba(0, 0, 0, 0.7), 0 0 30px ${leftColor}22`,
            transform: `translateX(${leftX}px)`,
            opacity: leftSpring,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              display: "inline-block",
              width: "fit-content",
              padding: "6px 16px",
              borderRadius: 8,
              backgroundColor: `${leftColor}26`,
              color: leftColor,
              fontWeight: 800,
              fontSize: 18,
              marginBottom: 20,
              border: `1px solid ${leftColor}66`,
            }}
          >
            POINT A
          </div>
          <h2
            style={{
              fontSize: 44,
              fontWeight: 800,
              lineHeight: 1.3,
              margin: "0 0 20px 0",
              color: "#FFFFFF",
            }}
          >
            {leftTitle}
          </h2>
          <div
            style={{
              width: 60,
              height: 4,
              backgroundColor: leftColor,
              borderRadius: 2,
              marginBottom: 24,
            }}
          />
          <p
            style={{
              fontSize: 26,
              lineHeight: 1.6,
              color: "#CBD5E1",
              margin: 0,
            }}
          >
            {leftBody}
          </p>
        </div>

        {/* Center VS Badge */}
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: "50%",
            transform: `translate(-50%, -50%) scale(${badgeSpring})`,
            zIndex: 20,
            width: 80,
            height: 80,
            borderRadius: "50%",
            backgroundColor: "#1E293B",
            border: "2px solid rgba(255, 255, 255, 0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 900,
            fontSize: 24,
            color: "#F8FAFC",
            boxShadow: "0 10px 25px rgba(0,0,0,0.8)",
            letterSpacing: 1,
          }}
        >
          {comparisonLabel}
        </div>

        {/* Right Card */}
        <div
          style={{
            flex: 1,
            padding: "50px 48px",
            background: "rgba(17, 24, 39, 0.8)",
            backdropFilter: "blur(20px)",
            borderRadius: 24,
            border: `1.5px solid ${rightColor}55`,
            boxShadow: `0 20px 40px -10px rgba(0, 0, 0, 0.7), 0 0 30px ${rightColor}22`,
            transform: `translateX(${rightX}px)`,
            opacity: rightSpring,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              display: "inline-block",
              width: "fit-content",
              padding: "6px 16px",
              borderRadius: 8,
              backgroundColor: `${rightColor}26`,
              color: rightColor,
              fontWeight: 800,
              fontSize: 18,
              marginBottom: 20,
              border: `1px solid ${rightColor}66`,
            }}
          >
            POINT B
          </div>
          <h2
            style={{
              fontSize: 44,
              fontWeight: 800,
              lineHeight: 1.3,
              margin: "0 0 20px 0",
              color: "#FFFFFF",
            }}
          >
            {rightTitle}
          </h2>
          <div
            style={{
              width: 60,
              height: 4,
              backgroundColor: rightColor,
              borderRadius: 2,
              marginBottom: 24,
            }}
          />
          <p
            style={{
              fontSize: 26,
              lineHeight: 1.6,
              color: "#CBD5E1",
              margin: 0,
            }}
          >
            {rightBody}
          </p>
        </div>
      </div>
    </AbsoluteFill>
  );
};
