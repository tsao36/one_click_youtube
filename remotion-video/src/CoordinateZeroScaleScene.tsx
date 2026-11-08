import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { CoordinateZeroBackground } from "./CoordinateZeroBackground";
import { CoordinateZeroScaleSceneProps } from "./types";

// SVG Silhouettes for iconic geographic landmasses
const SVG_SHAPES: Record<string, string> = {
  taiwan:
    "M 48 10 C 60 22, 68 45, 72 75 C 75 110, 68 140, 58 175 C 50 198, 42 215, 35 220 C 30 222, 26 210, 25 190 C 22 160, 24 130, 28 95 C 33 65, 36 35, 48 10 Z",
  netherlands:
    "M 25 30 C 45 15, 75 18, 85 40 C 78 55, 92 70, 85 95 C 75 115, 90 140, 80 165 C 65 185, 45 190, 30 175 C 18 160, 15 135, 22 115 C 15 95, 18 70, 22 45 Z",
  denmark:
    "M 50 15 C 70 25, 65 55, 78 75 C 70 100, 82 130, 65 155 C 45 170, 30 145, 38 115 C 25 100, 30 65, 50 15 Z",
  switzerland:
    "M 15 65 C 38 45, 75 50, 105 55 C 130 60, 145 80, 135 105 C 115 125, 92 118, 70 130 C 48 138, 25 120, 16 100 C 12 82, 14 70, 15 65 Z",
  belgium:
    "M 40 40 C 65 32, 90 45, 100 65 C 105 90, 95 115, 82 128 C 58 140, 35 135, 28 110 C 22 85, 28 60, 40 40 Z",
};

export const CoordinateZeroScaleScene: React.FC<CoordinateZeroScaleSceneProps> = ({
  badge = "台灣，其實比你想像中還大",
  initialTitle = "常見的世界地圖上：畫出來的大小",
  calibratedTitle = "搬到台灣身邊（同一個緯度）：真實大小",
  anchorLabel = "和台灣比",
  items = [
    {
      id: "tw",
      name: "台灣",
      initialMultiplier: 1.0,
      actualMultiplier: 1.0,
      initialLabel: "基準",
      actualLabel: "基準",
      isAnchor: true,
      customShape: "taiwan",
      color: "#F59E0B",
    },
    {
      id: "nl",
      name: "荷蘭",
      initialMultiplier: 2.3,
      actualMultiplier: 1.0,
      initialLabel: "×2.3",
      actualLabel: "≈ 1倍",
      customShape: "netherlands",
    },
    {
      id: "dk",
      name: "丹麥",
      initialMultiplier: 3.2,
      actualMultiplier: 1.2,
      initialLabel: "×3.2",
      actualLabel: "1.2倍",
      customShape: "denmark",
    },
    {
      id: "ch",
      name: "瑞士",
      initialMultiplier: 2.0,
      actualMultiplier: 1.1,
      initialLabel: "×2.0",
      actualLabel: "1.1倍",
      customShape: "switzerland",
    },
    {
      id: "be",
      name: "比利時",
      initialMultiplier: 1.8,
      actualMultiplier: 0.85,
      initialLabel: "×1.8",
      actualLabel: "0.85倍",
      isTargetFocus: true,
      customShape: "belgium",
    },
  ],
  accentColor = "#0D9488",
  bgSrc = "",
  dim = 0.15,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Entrance spring for paper sheet
  const paperEntrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
  });

  // Morph transition starts around frame 45
  const morphProgress = spring({
    frame: frame - 45,
    fps,
    config: { damping: 16, mass: 1, stiffness: 75 },
  });

  // Crossfade between titles
  const titleOpacityInitial = interpolate(frame, [38, 52], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const titleOpacityCalibrated = interpolate(frame, [45, 60], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Focus circle ring animation around target (Belgium)
  const focusCircleProgress = spring({
    frame: frame - 70,
    fps,
    config: { damping: 12, mass: 0.7, stiffness: 100 },
  });

  return (
    <CoordinateZeroBackground bgSrc={bgSrc} dim={dim} showPaper={true} paperPadding="48px 60px">
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          height: "100%",
          transform: `scale(${paperEntrance})`,
          opacity: paperEntrance,
        }}
      >
        {/* Top Header Capsule Badge */}
        {badge && (
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 20 }}>
            <div
              style={{
                backgroundColor: accentColor,
                color: "#FFFFFF",
                fontSize: 26,
                fontWeight: 900,
                letterSpacing: 1.5,
                padding: "8px 36px",
                borderRadius: 999,
                boxShadow: "0 4px 14px rgba(13, 148, 136, 0.35)",
              }}
            >
              {badge}
            </div>
          </div>
        )}

        {/* Dynamic Title switching from Inflated to Calibrated */}
        <div style={{ position: "relative", height: 44, marginBottom: 30 }}>
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              fontSize: 28,
              fontWeight: 800,
              color: "#EF4444",
              opacity: titleOpacityInitial,
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <span>{initialTitle}</span>
          </div>
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              fontSize: 28,
              fontWeight: 800,
              color: "#0F766E",
              opacity: titleOpacityCalibrated,
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <span>{calibratedTitle}</span>
          </div>
        </div>

        {/* Multi-Country / Subject Comparison Row */}
        <div
          style={{
            flex: 1,
            display: "grid",
            gridTemplateColumns: `repeat(${items.length}, 1fr)`,
            alignItems: "center",
            gap: 20,
            padding: "10px 0",
          }}
        >
          {items.map((item, idx) => {
            const isAnchor = item.isAnchor;

            // Compute current scale for non-anchors based on morphProgress
            const currentScaleFactor = isAnchor
              ? 1.0
              : interpolate(
                  morphProgress,
                  [0, 1],
                  [item.initialMultiplier || 2.0, item.actualMultiplier || 1.0]
                );

            // Shape visual scale (relative to container)
            const visualScale = 1.05 * currentScaleFactor;

            // Multiplier pill label
            const currentLabel =
              morphProgress > 0.5
                ? item.actualLabel || `≈ ${item.actualMultiplier}倍`
                : item.initialLabel || `×${item.initialMultiplier}`;

            // Multiplier pill background color
            const pillBg = isAnchor
              ? "transparent"
              : morphProgress > 0.5
              ? "#0D9488"
              : "#EF4444";

            // Shape fill color
            const shapeColor = isAnchor
              ? item.color || "#F59E0B"
              : morphProgress > 0.5
              ? "#0F766E"
              : "#EF4444";

            // Item entrance
            const itemEntrance = spring({
              frame,
              fps,
              config: { damping: 14, stiffness: 100 },
            });

            return (
              <div
                key={item.id || idx}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
                  transform: `scale(${itemEntrance})`,
                  opacity: itemEntrance,
                  position: "relative",
                  gap: 16,
                }}
              >
                {/* Multiplier Tag Pill Row */}
                <div style={{ height: 42, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {isAnchor ? (
                    <span
                      style={{
                        fontSize: 18,
                        fontWeight: 800,
                        color: "#475569",
                        letterSpacing: 1,
                      }}
                    >
                      {anchorLabel}
                    </span>
                  ) : (
                    <div
                      style={{
                        backgroundColor: pillBg,
                        color: "#FFFFFF",
                        padding: "4px 18px",
                        borderRadius: 999,
                        fontSize: 18,
                        fontWeight: 900,
                        letterSpacing: 0.5,
                        boxShadow: "0 2px 8px rgba(0,0,0,0.18)",
                        transition: "background-color 0.2s ease",
                      }}
                    >
                      {currentLabel}
                    </div>
                  )}
                </div>

                {/* Silhouette Stage */}
                <div
                  style={{
                    position: "relative",
                    width: 170,
                    height: 220,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {/* Focus Ring around Target (e.g. Belgium) */}
                  {item.isTargetFocus && (
                    <div
                      style={{
                        position: "absolute",
                        width: 170,
                        height: 170,
                        borderRadius: "50%",
                        border: `3px solid #0D9488`,
                        boxShadow: "0 0 20px rgba(13, 148, 136, 0.4)",
                        transform: `scale(${focusCircleProgress})`,
                        opacity: focusCircleProgress,
                        pointerEvents: "none",
                      }}
                    />
                  )}

                  {/* SVG Shape Silhouette */}
                  <svg
                    viewBox="0 0 100 200"
                    style={{
                      width: 140,
                      height: 190,
                      transform: `scale(${visualScale})`,
                      transition: "transform 0.05s ease-out",
                      filter: "drop-shadow(0 4px 6px rgba(0,0,0,0.2))",
                      overflow: "visible",
                    }}
                  >
                    <path
                      d={
                        (item.customShape && SVG_SHAPES[item.customShape.toLowerCase()]) ||
                        SVG_SHAPES.taiwan
                      }
                      fill={shapeColor}
                      stroke="#1E293B"
                      strokeWidth="2.5"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>

                {/* Country / Item Label Row */}
                <div
                  style={{
                    fontSize: 26,
                    fontWeight: 900,
                    color: "#0F172A",
                    letterSpacing: 1,
                    textAlign: "center",
                  }}
                >
                  {item.name}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </CoordinateZeroBackground>
  );
};
