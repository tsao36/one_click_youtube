import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { QueuedAgent } from "./simulationTypes";

interface AgentQueueVisualizerProps {
  agents: QueuedAgent[];
  accentColor?: string;
  phaseProgress?: number;
}

export const AgentQueueVisualizer: React.FC<AgentQueueVisualizerProps> = ({
  agents,
  accentColor = "#F59E0B",
  phaseProgress = 1.0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Queue cycling animation: every 60 frames, the queue steps forward by 1 slot
  const stepDuration = 60;
  const cycleIndex = Math.floor(frame / stepDuration);
  const cycleFrac = (frame % stepDuration) / stepDuration;

  // Dispenser breathing pulse
  const dispenserGlow = Math.sin(frame / 10) * 0.2 + 0.8;

  // Floating ration bread/fish physics
  const rationFloat = Math.sin(frame / 8) * 4;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 24,
        left: 36,
        right: 36,
        backgroundColor: "rgba(15, 23, 42, 0.94)",
        border: `1.5px solid ${accentColor}`,
        borderRadius: 14,
        padding: "14px 20px 16px 20px",
        boxShadow: `0 8px 36px rgba(0, 0, 0, 0.7), 0 0 20px ${accentColor}30`,
        backdropFilter: "blur(12px)",
        zIndex: 35,
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
          paddingBottom: 8,
          marginBottom: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              padding: "2px 8px",
              borderRadius: 4,
              backgroundColor: `${accentColor}25`,
              color: accentColor,
              border: `1px solid ${accentColor}60`,
              fontSize: 10,
              fontFamily: "monospace",
              fontWeight: 800,
              letterSpacing: 1,
            }}
          >
            CIV-50 EMERGENCE MONITOR
          </span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 800,
              color: "#F8FAFC",
              letterSpacing: 0.5,
            }}
          >
            Automated Food Rationing &amp; Bureaucracy Line
          </span>
        </div>

        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <div style={{ fontSize: 11, fontFamily: "monospace", color: "#94A3B8" }}>
            QUEUE ORDER: <strong style={{ color: "#10B981" }}>STRICT FIFO</strong>
          </div>
          <div style={{ fontSize: 11, fontFamily: "monospace", color: "#94A3B8" }}>
            TOTAL AGENTS: <strong style={{ color: "#38BDF8" }}>50 / 50</strong>
          </div>
        </div>
      </div>

      {/* Main Queue Conveyor Line */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          position: "relative",
          overflow: "hidden",
          padding: "4px 0",
        }}
      >
        {/* Head of the Line: Food Dispenser Chest */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            width: 130,
            height: 90,
            borderRadius: 10,
            backgroundColor: "#1E293B",
            border: `2px solid ${accentColor}`,
            boxShadow: `0 0 ${15 * dispenserGlow}px ${accentColor}`,
            flexShrink: 0,
            position: "relative",
          }}
        >
          <div
            style={{
              fontSize: 26,
              transform: `translateY(${rationFloat}px)`,
              transition: "transform 0.1s ease-out",
            }}
          >
            📦
          </div>
          <div
            style={{
              fontSize: 10,
              fontFamily: "monospace",
              fontWeight: 800,
              color: accentColor,
              marginTop: 4,
            }}
          >
            DISPENSER CHEST
          </div>
          <div style={{ fontSize: 9, color: "#94A3B8" }}>Rationing Station #1</div>

          {/* Outgoing floating bread */}
          <div
            style={{
              position: "absolute",
              right: -10,
              top: 15,
              fontSize: 16,
              opacity: interpolate(cycleFrac, [0, 0.4, 0.9], [1, 0.8, 0]),
              transform: `translateX(${interpolate(cycleFrac, [0, 1], [0, 30])}px)`,
            }}
          >
            🍞
          </div>
        </div>

        {/* Direction Arrow */}
        <div style={{ fontSize: 18, color: accentColor, opacity: 0.8 }}>&larr;</div>

        {/* Queuing Slots & Agents */}
        <div
          style={{
            display: "flex",
            gap: 12,
            flex: 1,
            alignItems: "center",
          }}
        >
          {agents.slice(0, 5).map((agent, slotIdx) => {
            // Shift offset based on cycle
            const activeAgentIndex = (slotIdx + cycleIndex) % Math.max(1, agents.length);
            const currentAgent = agents[activeAgentIndex] || agent;

            const isFrontOfLine = slotIdx === 0;

            const slotSpring = spring({
              frame: frame - slotIdx * 4,
              fps,
              config: { damping: 14, mass: 0.7, stiffness: 120 },
            });

            return (
              <div
                key={`${currentAgent.id}-${slotIdx}`}
                style={{
                  flex: 1,
                  minWidth: 140,
                  height: 90,
                  borderRadius: 10,
                  backgroundColor: isFrontOfLine ? "rgba(245, 158, 11, 0.15)" : "rgba(30, 41, 59, 0.7)",
                  border: `1.5px solid ${isFrontOfLine ? accentColor : "rgba(148, 163, 184, 0.2)"}`,
                  boxShadow: isFrontOfLine ? `0 0 16px ${accentColor}40` : "none",
                  padding: "8px 10px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  transform: `scale(${slotSpring})`,
                  transition: "all 0.25s ease-out",
                }}
              >
                {/* Slot Number & State */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span
                    style={{
                      fontSize: 9,
                      fontFamily: "monospace",
                      fontWeight: 700,
                      color: isFrontOfLine ? accentColor : "#94A3B8",
                    }}
                  >
                    SLOT #{slotIdx + 1} {isFrontOfLine ? "[RECEIVING]" : "[WAITING]"}
                  </span>
                  <span style={{ fontSize: 12 }}>{currentAgent.rationItem || "🍞"}</span>
                </div>

                {/* Agent Name & ID */}
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div
                    style={{
                      width: 18,
                      height: 18,
                      borderRadius: 4,
                      backgroundColor: currentAgent.color || "#38BDF8",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 10,
                      fontWeight: 900,
                      color: "#0F172A",
                    }}
                  >
                    🤖
                  </div>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 800,
                      color: "#FFFFFF",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {currentAgent.name}
                  </span>
                </div>

                {/* Assigned Bureaucracy Role */}
                <div
                  style={{
                    fontSize: 9.5,
                    fontFamily: "monospace",
                    fontWeight: 700,
                    color: isFrontOfLine ? "#34D399" : "#CBD5E1",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  ROLE: {currentAgent.role}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
