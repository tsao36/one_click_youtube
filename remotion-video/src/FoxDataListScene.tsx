import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FoxBackground } from "./FoxBackground";
import { FoxDataListSceneProps } from "./types";
import {
  DynamicAccentBar,
  GlintSheen,
  RadarBeacon,
  useContinuousDrift,
  useCountUp,
} from "./animations";

export const FoxDataListScene: React.FC<FoxDataListSceneProps> = ({
  chapter = "採購清單與預算",
  title = "台灣陸軍新一代主力戰車採購裝備",
  items = [
    { label: "M1A2T 主力戰車", value: "108 輛", note: "最新特製防護裝甲規格" },
    { label: "M88A2 裝甲救濟車", value: "14 輛", note: "70 噸級戰場拖救能力" },
    { label: "M1070A1 重型拖車", value: "16 輛", note: "公路高速機動運載" },
  ],
  totalLabel = "總採購預算",
  totalValue = "約 20 億美元（405 億台幣）",
  source = "",
  bgSrc = "",
  dim = 0.5,
  accentColor = "#38BDF8",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { floatY, glowPulse } = useContinuousDrift(0.0002);

  // Header entrance
  const headerSpring = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 130 },
  });

  const cardSpring = spring({
    frame: frame - 6,
    fps,
    config: { damping: 14, mass: 0.85, stiffness: 120 },
  });

  // Animated total count-up
  const totalStartFrame = 12 + items.length * 6;
  const { display: animatedTotal, punchScale: totalPunch } = useCountUp(
    totalValue,
    { startFrame: totalStartFrame, duration: 30, fps }
  );

  return (
    <FoxBackground bgSrc={bgSrc} dim={dim}>
      <div
        style={{
          position: "absolute",
          top: 130,
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
            fontSize: 46,
            fontWeight: 900,
            color: "#FFFFFF",
            lineHeight: 1.25,
            letterSpacing: "-0.5px",
            margin: "0 0 20px 0",
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
          maxWidth={140}
          startFrame={8}
          duration={22}
          height={4}
          style={{ marginTop: 0, marginBottom: 24 }}
        />

        {/* Card Container with animated border & glint sheen */}
        <div
          style={{
            position: "relative",
            maxWidth: 1050,
            backgroundColor: "rgba(15, 23, 42, 0.82)",
            border: `1px solid rgba(255, 255, 255, ${0.12 + 0.08 * glowPulse})`,
            borderRadius: 16,
            boxShadow: `0 20px 50px rgba(0, 0, 0, 0.6), 0 0 ${
              25 * glowPulse
            }px ${accentColor}18`,
            backdropFilter: "blur(20px)",
            padding: "24px 36px",
            opacity: cardSpring,
            transform: `translateY(${interpolate(
              cardSpring,
              [0, 1],
              [24, 0]
            )}px)`,
            overflow: "hidden",
          }}
        >
          <GlintSheen color={`${accentColor}55`} periodFrames={95} />

          {items.map((item, index) => {
            const itemEntrance = frame - (10 + index * 6);
            const itemSpring = spring({
              frame: itemEntrance,
              fps,
              config: { damping: 14, mass: 0.8, stiffness: 120 },
            });

            // Sequential scanning highlight
            const highlightActive = itemEntrance >= 0 && itemEntrance <= 25;
            const highlightProgress = interpolate(
              itemEntrance,
              [0, 25],
              [-100, 200],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }
            );

            return (
              <div
                key={index}
                style={{
                  position: "relative",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "16px 12px",
                  borderBottom:
                    index < items.length - 1
                      ? "1px solid rgba(255, 255, 255, 0.08)"
                      : undefined,
                  opacity: itemSpring,
                  transform: `translateX(${interpolate(
                    itemSpring,
                    [0, 1],
                    [-24, 0]
                  )}px)`,
                  overflow: "hidden",
                  borderRadius: 8,
                }}
              >
                {/* Highlight laser beam across active item */}
                {highlightActive && (
                  <div
                    style={{
                      position: "absolute",
                      top: 0,
                      left: `${highlightProgress}%`,
                      width: "40%",
                      height: "100%",
                      background: `linear-gradient(90deg, transparent, ${accentColor}33, transparent)`,
                      pointerEvents: "none",
                    }}
                  />
                )}

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                    zIndex: 2,
                  }}
                >
                  <div
                    style={{
                      fontSize: 26,
                      fontWeight: 700,
                      color: "#FFFFFF",
                      letterSpacing: 0.5,
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        backgroundColor: accentColor,
                        boxShadow: `0 0 8px ${accentColor}`,
                      }}
                    />
                    <span>{item.label}</span>
                  </div>
                  {item.note && (
                    <div
                      style={{
                        fontSize: 18,
                        color: "rgba(255, 255, 255, 0.6)",
                        paddingLeft: 14,
                      }}
                    >
                      {item.note}
                    </div>
                  )}
                </div>

                <div
                  style={{
                    fontSize: 32,
                    fontWeight: 800,
                    color: item.highlight ? accentColor : "#FFFFFF",
                    fontFamily: "system-ui, -apple-system, sans-serif",
                    letterSpacing: 1,
                    textShadow: item.highlight
                      ? `0 0 16px ${accentColor}`
                      : "0 2px 8px rgba(0,0,0,0.8)",
                    zIndex: 2,
                    transform: `scale(${interpolate(
                      itemSpring,
                      [0, 1],
                      [0.88, 1]
                    )})`,
                  }}
                >
                  {item.value}
                </div>
              </div>
            );
          })}

          {/* Dynamic Total Row */}
          {totalValue && (
            <div
              style={{
                marginTop: 18,
                paddingTop: 18,
                borderTop: `2px solid ${accentColor}77`,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                paddingLeft: 12,
                paddingRight: 12,
              }}
            >
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 700,
                  color: "rgba(255, 255, 255, 0.85)",
                  letterSpacing: 1,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <RadarBeacon color={accentColor} size={6} />
                <span>{totalLabel}</span>
              </div>
              <div
                style={{
                  fontSize: 36,
                  fontWeight: 900,
                  color: accentColor,
                  letterSpacing: 1,
                  textShadow: `0 0 20px ${accentColor}88`,
                  transform: `scale(${totalPunch})`,
                }}
              >
                {animatedTotal}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Source Footnote */}
      {source && (
        <div
          style={{
            position: "absolute",
            bottom: 48,
            right: 80,
            fontSize: 16,
            color: "rgba(255, 255, 255, 0.5)",
            letterSpacing: 0.5,
            zIndex: 20,
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
    </FoxBackground>
  );
};
