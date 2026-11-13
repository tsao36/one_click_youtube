import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FoxBackground } from "./FoxBackground";
import { OverlayGraphicSceneProps } from "./types";

export const CornerMetricOverlayScene: React.FC<OverlayGraphicSceneProps> = ({
  bgSrc = "",
  dim = 0.2,
  accentColor = "#FF5A1F",
  metric_callout = null,
  headline = "",
  subtext = "",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entrance = spring({ frame, fps, config: { damping: 14, mass: 0.8, stiffness: 130 } });
  const displayValue = metric_callout?.value || headline;
  const supportingText = metric_callout?.label || metric_callout?.unit || subtext;

  return (
    <FoxBackground bgSrc={bgSrc} dim={dim}>
      {(displayValue || supportingText) && (
        <div style={{
          position: "absolute", top: 70, left: 80, zIndex: 10,
          display: "flex", overflow: "hidden", minWidth: 560,
          padding: "26px 34px 24px 0", borderRadius: 18,
          background: "rgba(3, 8, 14, 0.94)",
          boxShadow: "0 16px 34px rgba(0,0,0,0.42)",
          opacity: entrance, transform: `translateY(${(1 - entrance) * 16}px) scale(${0.94 + entrance * 0.06})`,
          transformOrigin: "top left",
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans TC', 'Microsoft JhengHei', sans-serif",
        }}>
          <div style={{ width: 14, flexShrink: 0, background: accentColor, marginRight: 30 }} />
          <div>
            {displayValue && <div style={{ color: accentColor, fontSize: 82, lineHeight: 0.98, fontWeight: 850, letterSpacing: "-0.035em", whiteSpace: "nowrap" }}>{displayValue}</div>}
            {supportingText && <div style={{ marginTop: 14, color: "#F8FAFC", fontSize: 34, lineHeight: 1.12, fontWeight: 700, whiteSpace: "nowrap" }}>{supportingText}</div>}
          </div>
        </div>
      )}
    </FoxBackground>
  );
};
