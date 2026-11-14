import React from "react";
import {
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  ProceduralBackground,
  RveSceneFooter,
  RveSceneHeader,
} from "./ProceduralBackground";
import { RveImageComparisonSceneProps } from "./types";
import { useContinuousDrift } from "./animations";

const resolveMediaSrc = (src: string) =>
  /^https?:\/\//i.test(src) ? src : staticFile(src);

export const RveImageComparisonScene: React.FC<RveImageComparisonSceneProps> = ({
  badge = "VISUAL COMPARISON",
  title = "前後視角對照驗證",
  subtitle = "",
  beforeLabel = "BEFORE",
  beforeCaption = "既有狀態與基準對照",
  beforeImgSrc = "",
  afterLabel = "AFTER",
  afterCaption = "新階段架構與成果對照",
  afterImgSrc = "",
  source = "",
  accentColor = "#38BDF8",
  bgSrc = "",
  dim = 0.5,
  bgVariant = "grid-pulse",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const { floatY } = useContinuousDrift(0.00015);

  const sweepEnd = Math.max(45, Math.floor(durationInFrames * 0.78));
  const dividerPercent = interpolate(frame, [10, sweepEnd], [12, 88], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const frameSpring = spring({
    frame,
    fps,
    config: { damping: 16, stiffness: 110 },
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
          padding: "58px 110px 46px",
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
            marginTop: 18,
            opacity: frameSpring,
            transform: `translateY(${floatY + (1 - frameSpring) * 20}px)`,
          }}
        >
          <div
            style={{
              width: 1460,
              height: 680,
              borderRadius: 24,
              overflow: "hidden",
              position: "relative",
              border: "1.5px solid rgba(255, 255, 255, 0.16)",
              boxShadow: "0 26px 70px rgba(0, 0, 0, 0.55)",
            }}
          >
            {/* After layer (full background) */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: `linear-gradient(135deg, #1E3A8A 0%, ${accentColor}99 55%, #0F172A 100%)`,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                alignItems: "center",
              }}
            >
              {afterImgSrc ? (
                <Img
                  src={resolveMediaSrc(afterImgSrc)}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              ) : (
                <div
                  style={{
                    padding: "0 80px",
                    textAlign: "center",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 18,
                  }}
                >
                  <div
                    style={{
                      fontSize: 72,
                      fontWeight: 950,
                      color: "#FFFFFF",
                      letterSpacing: "0.02em",
                    }}
                  >
                    {afterLabel}
                  </div>
                  {afterCaption && (
                    <div
                      style={{
                        fontSize: 32,
                        fontWeight: 600,
                        color: "rgba(255, 255, 255, 0.9)",
                        maxWidth: 900,
                        lineHeight: 1.45,
                      }}
                    >
                      {afterCaption}
                    </div>
                  )}
                </div>
              )}

              <div
                style={{
                  position: "absolute",
                  top: 26,
                  right: 28,
                  padding: "8px 20px",
                  borderRadius: 999,
                  backgroundColor: "rgba(15, 23, 42, 0.82)",
                  border: `1.5px solid ${accentColor}`,
                  color: accentColor,
                  fontSize: 20,
                  fontWeight: 800,
                  letterSpacing: "0.06em",
                }}
              >
                {afterLabel}
              </div>
              {afterImgSrc && afterCaption && (
                <div
                  style={{
                    position: "absolute",
                    bottom: 24,
                    right: 28,
                    maxWidth: "42%",
                    padding: "10px 18px",
                    borderRadius: 12,
                    backgroundColor: "rgba(15, 23, 42, 0.8)",
                    color: "#F8FAFC",
                    fontSize: 20,
                    fontWeight: 600,
                  }}
                >
                  {afterCaption}
                </div>
              )}
            </div>

            {/* Before layer (clipped on the left side of dividerPercent) */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                clipPath: `inset(0 ${100 - dividerPercent}% 0 0)`,
                background:
                  "linear-gradient(135deg, #111827 0%, #334155 55%, #1E293B 100%)",
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                alignItems: "center",
              }}
            >
              {beforeImgSrc ? (
                <Img
                  src={resolveMediaSrc(beforeImgSrc)}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              ) : (
                <div
                  style={{
                    padding: "0 80px",
                    textAlign: "center",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 18,
                  }}
                >
                  <div
                    style={{
                      fontSize: 72,
                      fontWeight: 950,
                      color: "#CBD5E1",
                      letterSpacing: "0.02em",
                    }}
                  >
                    {beforeLabel}
                  </div>
                  {beforeCaption && (
                    <div
                      style={{
                        fontSize: 32,
                        fontWeight: 600,
                        color: "#94A3B8",
                        maxWidth: 900,
                        lineHeight: 1.45,
                      }}
                    >
                      {beforeCaption}
                    </div>
                  )}
                </div>
              )}

              <div
                style={{
                  position: "absolute",
                  top: 26,
                  left: 28,
                  padding: "8px 20px",
                  borderRadius: 999,
                  backgroundColor: "rgba(15, 23, 42, 0.85)",
                  border: "1.5px solid rgba(248, 113, 113, 0.7)",
                  color: "#FCA5A5",
                  fontSize: 20,
                  fontWeight: 800,
                  letterSpacing: "0.06em",
                }}
              >
                {beforeLabel}
              </div>
              {beforeImgSrc && beforeCaption && (
                <div
                  style={{
                    position: "absolute",
                    bottom: 24,
                    left: 28,
                    maxWidth: "42%",
                    padding: "10px 18px",
                    borderRadius: 12,
                    backgroundColor: "rgba(15, 23, 42, 0.82)",
                    color: "#E2E8F0",
                    fontSize: 20,
                    fontWeight: 600,
                  }}
                >
                  {beforeCaption}
                </div>
              )}
            </div>

            {/* Sweeping Divider Line & Handle */}
            <div
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                left: `${dividerPercent}%`,
                width: 4,
                backgroundColor: "#FFFFFF",
                boxShadow: `0 0 20px ${accentColor}`,
                zIndex: 4,
              }}
            >
              <div
                style={{
                  position: "absolute",
                  top: "50%",
                  left: "50%",
                  transform: "translate(-50%, -50%)",
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  backgroundColor: "#FFFFFF",
                  border: `4px solid ${accentColor}`,
                  boxShadow: "0 4px 16px rgba(0, 0, 0, 0.45)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#0F172A",
                  fontSize: 18,
                  fontWeight: 900,
                }}
              >
                ↔
              </div>
            </div>
          </div>
        </div>

        <RveSceneFooter source={source} accentColor={accentColor} />
      </div>
    </ProceduralBackground>
  );
};
