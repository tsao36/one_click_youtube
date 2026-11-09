import React from "react";
import { RadioEvent } from "./wirelessTypes";

interface MloVisualizerProps {
  mode: "str" | "emlsr";
  activeEvents: RadioEvent[];
  currentFrame: number;
}

export const MloVisualizer: React.FC<MloVisualizerProps> = ({
  mode,
  activeEvents,
  currentFrame,
}) => {
  // Check active events on Link 0 (5 GHz) and Link 1 (6 GHz)
  const link1Events = activeEvents.filter((e) => e.linkId === 0 || e.frequencyMhz < 6000);
  const link2Events = activeEvents.filter((e) => e.linkId === 1 || e.frequencyMhz >= 6000);

  const link1Active = link1Events.length > 0;
  let link2Active = link2Events.length > 0;
  let link2Blocked = false;

  if (mode === "emlsr" && link1Active) {
    // In eMLSR, active link 1 causes single-radio frontend lock; link 2 is locked out!
    link2Blocked = true;
    link2Active = false;
  }

  return (
    <div
      style={{
        position: "absolute",
        top: 96,
        left: 36,
        width: 380,
        backgroundColor: "rgba(15, 23, 42, 0.92)",
        border: "1px solid rgba(56, 189, 248, 0.3)",
        borderRadius: 12,
        padding: "14px 18px",
        boxShadow: "0 12px 36px rgba(0, 0, 0, 0.6)",
        backdropFilter: "blur(12px)",
        zIndex: 35,
      }}
    >
      {/* Title & Mode Badge */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
        }}
      >
        <span
          style={{
            fontSize: 12,
            fontFamily: "monospace",
            fontWeight: 800,
            color: "#38BDF8",
            letterSpacing: 1,
          }}
        >
          WI-FI 7 MLO ARCHITECTURE
        </span>
        <span
          style={{
            padding: "2px 8px",
            borderRadius: 4,
            backgroundColor: mode === "str" ? "rgba(16, 185, 129, 0.2)" : "rgba(245, 158, 11, 0.2)",
            color: mode === "str" ? "#34D399" : "#FBBF24",
            border: `1px solid ${mode === "str" ? "#10B981" : "#F59E0B"}`,
            fontSize: 10,
            fontFamily: "monospace",
            fontWeight: 800,
          }}
        >
          MODE: {mode.toUpperCase()}
        </span>
      </div>

      {/* Mode Description */}
      <div
        style={{
          fontSize: 11,
          color: "#CBD5E1",
          marginBottom: 14,
          lineHeight: 1.4,
        }}
      >
        {mode === "str" ? (
          <span>
            <strong style={{ color: "#34D399" }}>Simultaneous Transmit &amp; Receive (STR):</strong> Independent dual
            radios allow concurrent TX/RX on 5 GHz &amp; 6 GHz without blocking.
          </span>
        ) : (
          <span>
            <strong style={{ color: "#FBBF24" }}>enhanced Multi-Link Single Radio (eMLSR):</strong> Dual listening
            antennas dynamically lock the single radio to the active link, blocking concurrent second link!
          </span>
        )}
      </div>

      {/* Link 1 Lane (5 GHz) */}
      <div
        style={{
          marginBottom: 10,
          padding: "8px 10px",
          borderRadius: 8,
          backgroundColor: link1Active ? "rgba(16, 185, 129, 0.15)" : "rgba(30, 41, 59, 0.4)",
          border: `1px solid ${link1Active ? "#10B981" : "rgba(148, 163, 184, 0.2)"}`,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 11, fontFamily: "monospace", fontWeight: 700, color: "#F8FAFC" }}>
            LINK 1: 5 GHz Band (160 MHz)
          </span>
          <span
            style={{
              fontSize: 10,
              fontFamily: "monospace",
              fontWeight: 800,
              color: link1Active ? "#34D399" : "#64748B",
            }}
          >
            {link1Active ? "ACTIVE TX/RX" : "LISTENING"}
          </span>
        </div>
      </div>

      {/* Link 2 Lane (6 GHz) */}
      <div
        style={{
          padding: "8px 10px",
          borderRadius: 8,
          backgroundColor: link2Blocked
            ? "rgba(239, 68, 68, 0.18)"
            : link2Active
            ? "rgba(6, 182, 212, 0.15)"
            : "rgba(30, 41, 59, 0.4)",
          border: `1px solid ${
            link2Blocked ? "#EF4444" : link2Active ? "#06B6D4" : "rgba(148, 163, 184, 0.2)"
          }`,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 11, fontFamily: "monospace", fontWeight: 700, color: "#F8FAFC" }}>
            LINK 2: 6 GHz Band (320 MHz)
          </span>
          <span
            style={{
              fontSize: 10,
              fontFamily: "monospace",
              fontWeight: 800,
              color: link2Blocked ? "#EF4444" : link2Active ? "#22D3EE" : "#64748B",
            }}
          >
            {link2Blocked ? "LOCKED OUT (SINGLE RADIO)" : link2Active ? "ACTIVE TX/RX" : "LISTENING"}
          </span>
        </div>
      </div>
    </div>
  );
};
