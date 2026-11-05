import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";

export interface FoxBackgroundProps {
  bgSrc?: string;
  dim?: number;
  children: React.ReactNode;
}

export const FoxBackground: React.FC<FoxBackgroundProps> = ({
  bgSrc,
  dim = 0.0,
  children,
}) => {
  const frame = useCurrentFrame();
  const bgScale = 1 + frame * 0.0004;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0B0E14",
        color: "#FFFFFF",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans TC', 'Microsoft JhengHei', sans-serif",
        overflow: "hidden",
      }}
    >
      {/* Background visual asset */}
      {bgSrc && (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <Img
            src={staticFile(bgSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${bgScale})`,
              filter: "contrast(1.02) brightness(1.0)",
            }}
          />
          {/* Subtle Transparent Vignette only if dim requested to avoid blocking the image */}
          {dim > 0.05 && (
            <AbsoluteFill
              style={{
                background: `radial-gradient(ellipse at 25% 45%, rgba(10, 14, 22, ${dim * 0.4}) 0%, rgba(6, 9, 15, ${Math.min(0.6, dim + 0.1)}) 100%)`,
              }}
            />
          )}
        </AbsoluteFill>
      )}

      {/* Content Container */}
      <AbsoluteFill style={{ zIndex: 10 }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};
