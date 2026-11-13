import React from "react";
import { FoxBackground } from "./FoxBackground";
import { GlassTag } from "./GlassTag";
import { MetricCard } from "./MetricCard";
import { OverlayGraphicSceneProps } from "./types";

export const OverlayGraphicScene: React.FC<OverlayGraphicSceneProps> = ({
  bgSrc = "",
  dim = 0.2,
  accentColor = "#38BDF8",
  overlay_tag = "",
  metric_callout = null,
  headline = "",
  subtext = "",
}) => {
  return (
    <FoxBackground bgSrc={bgSrc} dim={dim}>
      {/* Top Left GlassTag */}
      {overlay_tag && (
        <div
          style={{
            position: "absolute",
            top: 70,
            left: 80,
            zIndex: 10,
          }}
        >
          <GlassTag text={overlay_tag} accentColor={accentColor} />
        </div>
      )}

      {/* Top Right MetricCard */}
      {metric_callout && (
        <div
          style={{
            position: "absolute",
            top: 70,
            right: 80,
            zIndex: 10,
          }}
        >
          <MetricCard data={metric_callout} accentColor={accentColor} />
        </div>
      )}

      {/* Optional contextual title/subtext if present */}
      {(headline || subtext) && (
        <div
          style={{
            position: "absolute",
            bottom: 120,
            left: 80,
            maxWidth: 1000,
            zIndex: 10,
          }}
        >
          {headline && (
            <h2
              style={{
                fontSize: 40,
                fontWeight: 800,
                color: "#FFFFFF",
                margin: 0,
                textShadow: "0 2px 10px rgba(0,0,0,0.6)",
              }}
            >
              {headline}
            </h2>
          )}
          {subtext && (
            <p
              style={{
                fontSize: 22,
                fontWeight: 500,
                color: "#CBD5E1",
                marginTop: 8,
                marginBottom: 0,
                textShadow: "0 2px 8px rgba(0,0,0,0.6)",
              }}
            >
              {subtext}
            </p>
          )}
        </div>
      )}
    </FoxBackground>
  );
};
