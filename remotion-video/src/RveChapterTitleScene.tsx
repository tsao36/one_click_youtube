import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ProceduralBackground } from "./ProceduralBackground";
import { RveChapterTitleSceneProps } from "./types";
import { RadarBeacon, useContinuousDrift } from "./animations";

export const RveChapterTitleScene: React.FC<RveChapterTitleSceneProps> = ({
  chapterLabel = "CHAPTER",
  chapterNumber = "01",
  title = "關鍵轉折起點",
  subtitle = "從歷史脈絡解析核心機制",
  source = "",
  accentColor = "#38BDF8",
  bgSrc = "",
  dim = 0.5,
  bgVariant = "geometric",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { floatY, glowPulse } = useContinuousDrift(0.00015);

  const labelOpacity = interpolate(frame, [2, 16], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const numberScale = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 95 },
  });

  const lineWidth = interpolate(frame, [8, 34], [0, 220], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const titleSpring = spring({
    frame: Math.max(0, frame - 10),
    fps,
    config: { damping: 15, stiffness: 110 },
  });

  const subtitleOpacity = interpolate(frame, [20, 38], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const subtitleY = interpolate(frame, [20, 38], [22, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <ProceduralBackground
      variant={bgVariant}
      accentColor={accentColor}
      bgSrc={bgSrc}
      dim={dim}
    >
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          padding: "80px 140px",
          boxSizing: "border-box",
          textAlign: "center",
          transform: `translateY(${floatY}px)`,
        }}
      >
        <div
          style={{
            color: accentColor,
            fontSize: 22,
            fontWeight: 800,
            letterSpacing: "0.28em",
            textTransform: "uppercase",
            marginBottom: 12,
            opacity: labelOpacity,
          }}
        >
          {chapterLabel}
        </div>

        <div
          style={{
            color: "#FFFFFF",
            fontSize: 168,
            fontWeight: 950,
            lineHeight: 0.95,
            letterSpacing: "-0.04em",
            transform: `scale(${numberScale})`,
            textShadow: `0 8px 34px rgba(0,0,0,0.65), 0 0 ${30 * glowPulse}px ${accentColor}44`,
          }}
        >
          {chapterNumber}
        </div>

        {/* Expanding left/right accent lines with glowing center node */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 24,
            marginTop: 28,
            marginBottom: 28,
          }}
        >
          <div
            style={{
              height: 3,
              width: lineWidth,
              borderRadius: 2,
              background: `linear-gradient(90deg, transparent, ${accentColor})`,
            }}
          />
          <RadarBeacon color={accentColor} size={11} />
          <div
            style={{
              height: 3,
              width: lineWidth,
              borderRadius: 2,
              background: `linear-gradient(90deg, ${accentColor}, transparent)`,
            }}
          />
        </div>

        <h1
          style={{
            margin: 0,
            color: "#FFFFFF",
            fontSize: 64,
            fontWeight: 900,
            lineHeight: 1.22,
            maxWidth: 1320,
            opacity: titleSpring,
            transform: `translateY(${(1 - titleSpring) * 20}px)`,
            textShadow: "0 4px 24px rgba(0, 0, 0, 0.75)",
          }}
        >
          {title}
        </h1>

        {subtitle && (
          <p
            style={{
              margin: "22px 0 0 0",
              color: "#CBD5E1",
              fontSize: 30,
              fontWeight: 500,
              lineHeight: 1.45,
              maxWidth: 1120,
              opacity: subtitleOpacity,
              transform: `translateY(${subtitleY}px)`,
            }}
          >
            {subtitle}
          </p>
        )}

        {source && (
          <div
            style={{
              position: "absolute",
              bottom: 42,
              fontSize: 17,
              color: "rgba(226, 232, 240, 0.55)",
            }}
          >
            {source}
          </div>
        )}
      </div>
    </ProceduralBackground>
  );
};
