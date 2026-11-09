import React from "react";
import { RadioEvent, WirelessDevice } from "./wirelessTypes";

interface PacketSequenceDiagramProps {
  events: RadioEvent[];
  devices: WirelessDevice[];
  currentFrame: number;
}

export const PacketSequenceDiagram: React.FC<PacketSequenceDiagramProps> = ({
  events,
  devices,
  currentFrame,
}) => {
  // Find current and recent events
  const currentIndex = events.findIndex(
    (e) => currentFrame >= e.startFrame && currentFrame <= e.startFrame + e.durationFrames
  );

  // Keep a sliding window of events around current frame
  const visibleEvents = events.filter((e) => {
    return e.startFrame <= currentFrame + 60 && e.startFrame + e.durationFrames >= currentFrame - 150;
  });

  return (
    <div
      style={{
        position: "absolute",
        top: 96,
        right: 36,
        width: 380,
        maxHeight: 460,
        backgroundColor: "rgba(15, 23, 42, 0.92)",
        border: "1px solid rgba(148, 163, 184, 0.25)",
        borderRadius: 12,
        padding: "12px 14px",
        boxShadow: "0 12px 36px rgba(0, 0, 0, 0.6)",
        backdropFilter: "blur(12px)",
        zIndex: 35,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Title */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
          paddingBottom: 8,
          marginBottom: 10,
        }}
      >
        <span
          style={{
            fontSize: 11,
            fontFamily: "monospace",
            fontWeight: 800,
            color: "#38BDF8",
            letterSpacing: 1,
          }}
        >
          PACKET SEQUENCE LADDER
        </span>
        <span
          style={{
            fontSize: 10,
            fontFamily: "monospace",
            color: "#94A3B8",
          }}
        >
          FRAME {currentFrame}
        </span>
      </div>

      {/* Sequence List */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 6,
          overflowY: "hidden",
        }}
      >
        {visibleEvents.slice(-6).map((evt) => {
          const isActive = currentFrame >= evt.startFrame && currentFrame <= evt.startFrame + evt.durationFrames;
          const isPast = currentFrame > evt.startFrame + evt.durationFrames;

          let categoryColor = "#06B6D4";
          if (evt.frameCategory === "management") categoryColor = "#A855F7";
          if (evt.frameCategory === "control") categoryColor = "#F59E0B";
          if (evt.signalState === "collision") categoryColor = "#EF4444";

          const srcDev = devices.find((d) => d.id === evt.sourceId);
          const dstDev = devices.find((d) => d.id === evt.targetId);

          return (
            <div
              key={evt.id}
              style={{
                display: "flex",
                flexDirection: "column",
                padding: "6px 8px",
                borderRadius: 6,
                backgroundColor: isActive
                  ? "rgba(6, 182, 212, 0.15)"
                  : isPast
                  ? "rgba(30, 41, 59, 0.4)"
                  : "rgba(15, 23, 42, 0.2)",
                borderLeft: `3px solid ${isActive ? categoryColor : isPast ? "#475569" : "#1E293B"}`,
                boxShadow: isActive ? `0 0 12px ${categoryColor}40` : "none",
                transform: isActive ? "scale(1.02)" : "scale(1)",
                transition: "all 0.15s ease-out",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      fontFamily: "monospace",
                      fontSize: 11,
                      fontWeight: 800,
                      color: isActive ? "#F8FAFC" : "#CBD5E1",
                    }}
                  >
                    {evt.frameSubtype}
                  </span>
                  <span
                    style={{
                      fontSize: 9,
                      padding: "1px 4px",
                      borderRadius: 3,
                      backgroundColor: `${categoryColor}25`,
                      color: categoryColor,
                      fontFamily: "monospace",
                      fontWeight: 700,
                    }}
                  >
                    {evt.protocol.toUpperCase()}
                  </span>
                </div>

                <span
                  style={{
                    fontSize: 9,
                    fontFamily: "monospace",
                    color: evt.signalState === "collision" ? "#EF4444" : "#94A3B8",
                    fontWeight: 700,
                  }}
                >
                  {evt.signalState === "collision" ? "COLLISION" : `T+${evt.startFrame}f`}
                </span>
              </div>

              {/* Source -> Destination & Channel */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginTop: 2,
                  fontSize: 10,
                  fontFamily: "monospace",
                  color: "#94A3B8",
                }}
              >
                <span>
                  {srcDev?.name.split(" ")[0] || evt.sourceId} &rarr;{" "}
                  {evt.targetId === "broadcast" ? "ALL (BC)" : dstDev?.name.split(" ")[0] || evt.targetId}
                </span>
                <span style={{ color: "#38BDF8" }}>
                  {typeof evt.channel === "number" ? `Ch ${evt.channel}` : evt.channel} ({evt.frequencyMhz}MHz)
                </span>
              </div>

              {/* Educational Annotation / Callout */}
              {evt.annotation && (
                <div
                  style={{
                    marginTop: 3,
                    fontSize: 9.5,
                    color: isActive ? "#E2E8F0" : "#64748B",
                    fontStyle: "italic",
                  }}
                >
                  &bull; {evt.annotation}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
