import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { SimulationMetric } from "./simulationTypes";

interface SimulationTimelineTickerProps {
  metrics: SimulationMetric[];
  currentTimeCode?: string;
  totalDurationSeconds?: number;
}

export const SimulationTimelineTicker: React.FC<SimulationTimelineTickerProps> = ({
  metrics,
  currentTimeCode = "03:00:00",
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Progress 0 -> 1 across the scene
  const progress = Math.min(1, Math.max(0, frame / durationInFrames));

  return (
    <div
      style={{
        position: "absolute",
        top: 96,
        right: 36,
        width: 340,
        backgroundColor: "rgba(15, 23, 42, 0.92)",
        border: "1px solid rgba(148, 163, 184, 0.25)",
        borderRadius: 12,
        padding: "12px 16px",
        boxShadow: "0 10px 30px rgba(0, 0, 0, 0.6)",
        backdropFilter: "blur(10px)",
        zIndex: 35,
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      {/* Header bar with Elapsed In-Game Time */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
          paddingBottom: 6,
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontFamily: "monospace",
            fontWeight: 800,
            color: "#38BDF8",
            letterSpacing: 1,
          }}
        >
          SIMULATION TELEMETRY
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              backgroundColor: "#10B981",
              boxShadow: "0 0 6px #10B981",
            }}
          />
          <span
            style={{
              fontSize: 12,
              fontFamily: "monospace",
              fontWeight: 800,
              color: "#F8FAFC",
            }}
          >
            {currentTimeCode}
          </span>
        </div>
      </div>

      {/* Dynamic Metric Tickers */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {metrics.map((metric) => {
          // Dynamic interpolated counter value
          const curVal = interpolate(progress, [0, 1], [metric.startValue, metric.endValue]);
          const displayVal =
            metric.endValue % 1 === 0 ? Math.round(curVal).toLocaleString() : curVal.toFixed(1);

          return (
            <div key={metric.id} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 11, color: "#94A3B8", fontWeight: 600 }}>{metric.label}</span>
                <span
                  style={{
                    fontSize: 13,
                    fontFamily: "monospace",
                    fontWeight: 800,
                    color: metric.color || "#38BDF8",
                  }}
                >
                  {displayVal}
                  {metric.suffix}
                </span>
              </div>

              {/* Progress bar */}
              <div
                style={{
                  height: 4,
                  width: "100%",
                  backgroundColor: "rgba(255, 255, 255, 0.08)",
                  borderRadius: 2,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${Math.min(100, Math.max(0, (curVal / Math.max(1, metric.endValue)) * 100))}%`,
                    backgroundColor: metric.color || "#38BDF8",
                    borderRadius: 2,
                    boxShadow: `0 0 8px ${metric.color || "#38BDF8"}`,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
