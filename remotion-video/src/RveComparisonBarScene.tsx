import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import {
  ProceduralBackground,
  RveSceneFooter,
  RveSceneHeader,
} from "./ProceduralBackground";
import { RveComparisonBarSceneProps } from "./types";
import { GlintSheen, useContinuousDrift, useCountUp } from "./animations";

export const RveComparisonBarScene: React.FC<RveComparisonBarSceneProps> = ({
  badge = "BEFORE VS AFTER",
  title = "關鍵效能前後對比",
  subtitle = "",
  beforeLabel = "改善前 (Before)",
  beforeValue = 34,
  beforeDisplay = "34%",
  beforeColor = "#EF4444",
  afterLabel = "改善後 (After)",
  afterValue = 89,
  afterDisplay = "89%",
  afterColor = "#38BDF8",
  takeaway = "核心效能指標獲得顯著躍升",
  source = "",
  accentColor = "#38BDF8",
  bgSrc = "",
  dim = 0.5,
  bgVariant = "liquid",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { floatY } = useContinuousDrift(0.00015);

  const effectiveAfterColor = afterColor || accentColor;
  const maxBarVal = Math.max(1, Math.abs(beforeValue), Math.abs(afterValue));
  const maxBarPx = 310;

  const beforeProg = interpolate(frame, [10, 42], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const afterProg = interpolate(frame, [20, 52], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const beforeH = Math.max(14, (Math.abs(beforeValue) / maxBarVal) * maxBarPx * (1 - Math.pow(1 - beforeProg, 3)));
  const afterH = Math.max(14, (Math.abs(afterValue) / maxBarVal) * maxBarPx * (1 - Math.pow(1 - afterProg, 3)));

  const { display: animBefore, punchScale: beforePunch } = useCountUp(beforeDisplay, {
    startFrame: 10,
    duration: 32,
    fps,
  });
  const { display: animAfter, punchScale: afterPunch } = useCountUp(afterDisplay, {
    startFrame: 20,
    duration: 32,
    fps,
  });

  const dividerSpring = spring({
    frame: Math.max(0, frame - 4),
    fps,
    config: { damping: 16, stiffness: 110 },
  });

  const takeawaySpring = spring({
    frame: Math.max(0, frame - 34),
    fps,
    config: { damping: 14, stiffness: 105 },
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
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            gap: 28,
            transform: `translateY(${floatY}px)`,
          }}
        >
          <div
            style={{
              position: "relative",
              width: 1180,
              height: 490,
              borderRadius: 26,
              background: "rgba(15, 23, 42, 0.74)",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              boxShadow: "0 24px 60px rgba(0, 0, 0, 0.48)",
              backdropFilter: "blur(16px)",
              padding: "36px 70px",
              boxSizing: "border-box",
              display: "flex",
              alignItems: "flex-end",
              justifyContent: "center",
              overflow: "hidden",
            }}
          >
            {/* Before column */}
            <div
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "flex-end",
                height: "100%",
              }}
            >
              <div
                style={{
                  fontSize: 66,
                  fontWeight: 950,
                  color: beforeColor,
                  marginBottom: 18,
                  transform: `scale(${beforePunch})`,
                  textShadow: `0 0 24px ${beforeColor}44`,
                }}
              >
                {animBefore}
              </div>
              <div
                style={{
                  width: 170,
                  height: beforeH,
                  borderRadius: "14px 14px 4px 4px",
                  background: `linear-gradient(180deg, ${beforeColor} 0%, ${beforeColor}99 100%)`,
                  boxShadow: `0 0 30px ${beforeColor}40`,
                }}
              />
              <div
                style={{
                  fontSize: 28,
                  fontWeight: 750,
                  color: "#E2E8F0",
                  marginTop: 18,
                }}
              >
                {beforeLabel}
              </div>
            </div>

            {/* Center vertical divider */}
            <div
              style={{
                width: 2,
                height: 360 * dividerSpring,
                background:
                  "linear-gradient(180deg, transparent, rgba(255,255,255,0.35), transparent)",
                margin: "0 56px",
                alignSelf: "center",
                opacity: dividerSpring,
              }}
            />

            {/* After column */}
            <div
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "flex-end",
                height: "100%",
              }}
            >
              <div
                style={{
                  fontSize: 66,
                  fontWeight: 950,
                  color: effectiveAfterColor,
                  marginBottom: 18,
                  transform: `scale(${afterPunch})`,
                  textShadow: `0 0 26px ${effectiveAfterColor}55`,
                }}
              >
                {animAfter}
              </div>
              <div
                style={{
                  width: 170,
                  height: afterH,
                  borderRadius: "14px 14px 4px 4px",
                  background: `linear-gradient(180deg, ${effectiveAfterColor} 0%, ${effectiveAfterColor}99 100%)`,
                  boxShadow: `0 0 34px ${effectiveAfterColor}4D`,
                }}
              />
              <div
                style={{
                  fontSize: 28,
                  fontWeight: 750,
                  color: "#FFFFFF",
                  marginTop: 18,
                }}
              >
                {afterLabel}
              </div>
            </div>

            <GlintSheen color={`${effectiveAfterColor}26`} periodFrames={105} />
          </div>

          {takeaway && (
            <div
              style={{
                opacity: takeawaySpring,
                transform: `translateY(${(1 - takeawaySpring) * 18}px)`,
                padding: "16px 36px",
                borderRadius: 16,
                background: `linear-gradient(90deg, ${effectiveAfterColor}22, rgba(15, 23, 42, 0.85))`,
                border: `1.5px solid ${effectiveAfterColor}66`,
                fontSize: 26,
                fontWeight: 750,
                color: "#F8FAFC",
                boxShadow: "0 12px 32px rgba(0, 0, 0, 0.4)",
              }}
            >
              {takeaway}
            </div>
          )}
        </div>

        <RveSceneFooter source={source} accentColor={accentColor} />
      </div>
    </ProceduralBackground>
  );
};
