import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import {
  ProceduralBackground,
  RveSceneFooter,
  RveSceneHeader,
} from "./ProceduralBackground";
import { RveCardFlipSceneProps } from "./types";
import { GlintSheen, RadarBeacon, useContinuousDrift } from "./animations";

export const RveCardFlipScene: React.FC<RveCardFlipSceneProps> = ({
  badge = "PERSPECTIVE SHIFT",
  title = "表象與底層真相翻轉",
  subtitle = "",
  frontTag = "表面認知 · MYTH",
  frontTitle = "傳統直覺認知",
  frontBody = "只看單一表層指標，容易忽略結構性的系統瓶頸。",
  backTag = "底層真相 · REALITY",
  backTitle = "真實運作機制",
  backBody = "真正決定結果上限的，往往是最稀缺的關鍵依賴節點。",
  flipAtRatio = 0.42,
  source = "",
  accentColor = "#38BDF8",
  bgSrc = "",
  dim = 0.5,
  bgVariant = "bokeh",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const { floatY, glowPulse } = useContinuousDrift(0.00015);

  const entranceSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 120 },
  });

  const flipFrame = Math.floor(durationInFrames * (flipAtRatio || 0.42));
  const flipSpring = spring({
    frame: Math.max(0, frame - flipFrame),
    fps,
    config: { damping: 15, mass: 0.7, stiffness: 95 },
  });
  const rotateY = interpolate(flipSpring, [0, 1], [0, 180]);

  const faceStyle: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    borderRadius: 28,
    backfaceVisibility: "hidden",
    WebkitBackfaceVisibility: "hidden",
    padding: "56px 64px",
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    overflow: "hidden",
  };

  return (
    <ProceduralBackground
      variant={bgVariant}
      accentColor={accentColor}
      bgSrc={bgSrc}
      dim={dim}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: "100%",
          height: "100%",
          padding: "64px 110px 52px",
          boxSizing: "border-box",
        }}
      >
        <RveSceneHeader
          badge={badge}
          title={title}
          subtitle={subtitle}
          accentColor={accentColor}
        />

        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            perspective: "1500px",
            transform: `translateY(${floatY}px)`,
          }}
        >
          <div
            style={{
              width: 1080,
              height: 480,
              position: "relative",
              transformStyle: "preserve-3d",
              opacity: entranceSpring,
              transform: `scale(${interpolate(entranceSpring, [0, 1], [0.9, 1])}) rotateY(${rotateY}deg)`,
            }}
          >
            {/* Front Face */}
            <div
              style={{
                ...faceStyle,
                background:
                  "linear-gradient(135deg, rgba(30, 41, 59, 0.92), rgba(15, 23, 42, 0.95))",
                border: "2px solid rgba(248, 113, 113, 0.55)",
                boxShadow: "0 28px 70px rgba(0, 0, 0, 0.55)",
              }}
            >
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 10,
                  alignSelf: "flex-start",
                  padding: "8px 20px",
                  borderRadius: 999,
                  backgroundColor: "rgba(239, 68, 68, 0.16)",
                  border: "1px solid rgba(248, 113, 113, 0.55)",
                  color: "#FCA5A5",
                  fontSize: 20,
                  fontWeight: 800,
                  letterSpacing: "0.08em",
                  marginBottom: 24,
                }}
              >
                <RadarBeacon color="#F87171" size={8} />
                <span>{frontTag}</span>
              </div>

              <div
                style={{
                  fontSize: 54,
                  fontWeight: 900,
                  color: "#FFFFFF",
                  lineHeight: 1.2,
                  marginBottom: 22,
                }}
              >
                {frontTitle}
              </div>

              <div
                style={{
                  fontSize: 30,
                  lineHeight: 1.55,
                  color: "#CBD5E1",
                  fontWeight: 500,
                }}
              >
                {frontBody}
              </div>
            </div>

            {/* Back Face */}
            <div
              style={{
                ...faceStyle,
                transform: "rotateY(180deg)",
                background: `linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(30, 58, 138, 0.65))`,
                border: `2.5px solid ${accentColor}`,
                boxShadow: `0 28px 70px rgba(0, 0, 0, 0.58), 0 0 ${34 * glowPulse}px ${accentColor}40`,
              }}
            >
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 10,
                  alignSelf: "flex-start",
                  padding: "8px 20px",
                  borderRadius: 999,
                  backgroundColor: `${accentColor}24`,
                  border: `1.5px solid ${accentColor}`,
                  color: accentColor,
                  fontSize: 20,
                  fontWeight: 800,
                  letterSpacing: "0.08em",
                  marginBottom: 24,
                }}
              >
                <RadarBeacon color={accentColor} size={8} />
                <span>{backTag}</span>
              </div>

              <div
                style={{
                  fontSize: 54,
                  fontWeight: 900,
                  color: "#FFFFFF",
                  lineHeight: 1.2,
                  marginBottom: 22,
                  textShadow: `0 0 24px ${accentColor}44`,
                }}
              >
                {backTitle}
              </div>

              <div
                style={{
                  fontSize: 30,
                  lineHeight: 1.55,
                  color: "#E2E8F0",
                  fontWeight: 550,
                }}
              >
                {backBody}
              </div>

              <GlintSheen color={`${accentColor}35`} periodFrames={90} />
            </div>
          </div>
        </div>

        <RveSceneFooter source={source} accentColor={accentColor} />
      </div>
    </ProceduralBackground>
  );
};
