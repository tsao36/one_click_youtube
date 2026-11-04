import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FoxBackground } from "./FoxBackground";
import { FoxDataListSceneProps } from "./types";

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

  // Header entrance
  const headerSpring = spring({
    frame,
    fps,
    config: { damping: 16, mass: 0.8, stiffness: 120 },
  });

  const cardSpring = spring({
    frame: frame - 6,
    fps,
    config: { damping: 15, mass: 0.9, stiffness: 110 },
  });

  return (
    <FoxBackground bgSrc={bgSrc} dim={dim}>
      <div
        style={{
          position: "absolute",
          top: 140,
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
            fontSize: 46,
            fontWeight: 900,
            color: "#FFFFFF",
            lineHeight: 1.25,
            letterSpacing: "-0.5px",
            margin: "0 0 32px 0",
            opacity: headerSpring,
            transform: `translateY(${interpolate(headerSpring, [0, 1], [16, 0])}px)`,
            textShadow: "0 3px 16px rgba(0, 0, 0, 0.8)",
          }}
        >
          {title}
        </h1>

        {/* Card Container */}
        <div
          style={{
            maxWidth: 1050,
            backgroundColor: "rgba(15, 23, 42, 0.82)",
            border: "1px solid rgba(255, 255, 255, 0.14)",
            borderRadius: 16,
            boxShadow: "0 20px 50px rgba(0, 0, 0, 0.6)",
            backdropFilter: "blur(20px)",
            padding: "24px 36px",
            opacity: cardSpring,
            transform: `translateY(${interpolate(cardSpring, [0, 1], [24, 0])}px)`,
          }}
        >
          {items.map((item, index) => {
            const itemSpring = spring({
              frame: frame - (10 + index * 6),
              fps,
              config: { damping: 15, mass: 0.8, stiffness: 120 },
            });

            return (
              <div
                key={index}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "16px 0",
                  borderBottom:
                    index < items.length - 1
                      ? "1px solid rgba(255, 255, 255, 0.08)"
                      : undefined,
                  opacity: itemSpring,
                  transform: `translateX(${interpolate(itemSpring, [0, 1], [-20, 0])}px)`,
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <div
                    style={{
                      fontSize: 26,
                      fontWeight: 700,
                      color: "#FFFFFF",
                      letterSpacing: 0.5,
                    }}
                  >
                    {item.label}
                  </div>
                  {item.note && (
                    <div
                      style={{
                        fontSize: 18,
                        color: "rgba(255, 255, 255, 0.55)",
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
                  }}
                >
                  {item.value}
                </div>
              </div>
            );
          })}

          {/* Optional Total Row */}
          {totalValue && (
            <div
              style={{
                marginTop: 18,
                paddingTop: 18,
                borderTop: `2px solid ${accentColor}66`,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 700,
                  color: "rgba(255, 255, 255, 0.8)",
                  letterSpacing: 1,
                }}
              >
                {totalLabel}
              </div>
              <div
                style={{
                  fontSize: 36,
                  fontWeight: 900,
                  color: accentColor,
                  letterSpacing: 1,
                  textShadow: `0 0 16px ${accentColor}66`,
                }}
              >
                {totalValue}
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
