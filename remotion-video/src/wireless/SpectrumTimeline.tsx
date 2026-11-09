import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { RadioEvent } from "./wirelessTypes";

interface SpectrumTimelineProps {
  activeEvents: RadioEvent[];
  recentEvents: RadioEvent[];
  currentFrame: number;
  showCoexMonitor?: boolean;
}

export const SpectrumTimeline: React.FC<SpectrumTimelineProps> = ({
  activeEvents,
  recentEvents,
  currentFrame,
  showCoexMonitor = true,
}) => {
  // 2.4 GHz spectrum boundaries: 2400 MHz to 2485 MHz (85 MHz width)
  const fMin = 2400;
  const fMax = 2485;
  const freqToPct = (freq: number) => {
    return Math.min(100, Math.max(0, ((freq - fMin) / (fMax - fMin)) * 100));
  };

  // Find active 2.4 GHz events
  const activeWifi24 = activeEvents.filter(
    (e) => e.protocol === "wifi_80211" && e.frequencyMhz >= 2400 && e.frequencyMhz <= 2485
  );
  const activeBle = activeEvents.filter(
    (e) => (e.protocol === "ble" || e.protocol === "bt_classic") && e.frequencyMhz >= 2400 && e.frequencyMhz <= 2485
  );

  // Check if any BLE channel collides with any Wi-Fi channel
  const collisions = activeBle.filter((bleEvt) => {
    return activeWifi24.some((wifiEvt) => {
      const halfBw = (wifiEvt.bandwidthMhz || 20) / 2;
      return Math.abs(bleEvt.frequencyMhz - wifiEvt.frequencyMhz) < halfBw;
    });
  });

  const hasCollision = collisions.length > 0;

  // Derive current PTA state
  let ptaStatus = "IDLE (CLEAR SPECTRUM)";
  let ptaColor = "#10B981";
  if (hasCollision) {
    ptaStatus = "COLLISION DETECTED -> PTA ARBITRATION TRIGGERED";
    ptaColor = "#EF4444";
  } else if (activeBle.some((e) => e.frameSubtype.includes("CIS") || e.frameSubtype.includes("AUDIO"))) {
    ptaStatus = "PTA: BLE ISOCHRONOUS PRIORITY (AUDIO GUARANTEE)";
    ptaColor = "#EC4899";
  } else if (activeWifi24.length > 0 && activeBle.length > 0) {
    ptaStatus = "PTA: DUAL-BAND SCHEDULED COEXISTENCE";
    ptaColor = "#38BDF8";
  } else if (activeWifi24.length > 0) {
    ptaStatus = "WIFI 2.4GHz TXOP IN PROGRESS";
    ptaColor = "#06B6D4";
  } else if (activeBle.length > 0) {
    ptaStatus = "BLE ACTIVE FREQUENCY HOPPING";
    ptaColor = "#A855F7";
  }

  return (
    <div
      style={{
        position: "absolute",
        bottom: 24,
        left: 36,
        right: 36,
        background: "rgba(15, 23, 42, 0.92)",
        border: `1px solid ${hasCollision ? "rgba(239, 68, 68, 0.6)" : "rgba(56, 189, 248, 0.3)"}`,
        borderRadius: 12,
        padding: "14px 20px 10px 20px",
        boxShadow: hasCollision
          ? "0 0 30px rgba(239, 68, 68, 0.35)"
          : "0 8px 32px rgba(0, 0, 0, 0.6)",
        backdropFilter: "blur(12px)",
        zIndex: 40,
      }}
    >
      {/* Top Header & PTA Telemetry */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              fontFamily: "monospace",
              fontSize: 12,
              fontWeight: 800,
              color: "#38BDF8",
              letterSpacing: 1.2,
            }}
          >
            2.4 GHz ISM BAND SPECTRUM OCCUPANCY (2400 – 2485 MHz)
          </span>
          <span
            style={{
              padding: "2px 8px",
              borderRadius: 4,
              backgroundColor: "rgba(6, 182, 212, 0.15)",
              color: "#22D3EE",
              fontSize: 10,
              fontFamily: "monospace",
              fontWeight: 700,
              border: "1px solid rgba(6, 182, 212, 0.4)",
            }}
          >
            REAL-TIME FREQUENCY vs TIME
          </span>
        </div>

        {/* Coex / PTA Status Pill */}
        {showCoexMonitor && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              backgroundColor: "rgba(0, 0, 0, 0.45)",
              padding: "3px 12px",
              borderRadius: 6,
              border: `1px solid ${ptaColor}`,
            }}
          >
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                backgroundColor: ptaColor,
                boxShadow: `0 0 8px ${ptaColor}`,
              }}
            />
            <span
              style={{
                fontFamily: "monospace",
                fontSize: 11,
                fontWeight: 700,
                color: ptaColor,
                letterSpacing: 0.5,
              }}
            >
              {ptaStatus}
            </span>
          </div>
        )}
      </div>

      {/* Spectrum Waterfall / Power Graph Display */}
      <div
        style={{
          position: "relative",
          height: 72,
          backgroundColor: "#090D16",
          borderRadius: 8,
          border: "1px solid rgba(148, 163, 184, 0.2)",
          overflow: "hidden",
        }}
      >
        {/* Background Grid Lines (every 10 MHz) */}
        {[2410, 2420, 2430, 2440, 2450, 2460, 2470, 2480].map((freq) => (
          <div
            key={freq}
            style={{
              position: "absolute",
              left: `${freqToPct(freq)}%`,
              top: 0,
              bottom: 0,
              width: 1,
              backgroundColor: "rgba(255, 255, 255, 0.08)",
            }}
          />
        ))}

        {/* Static 2.4 GHz Wi-Fi Standard Channels Reference Lobes */}
        {[
          { ch: 1, center: 2412, name: "CH 1" },
          { ch: 6, center: 2437, name: "CH 6" },
          { ch: 11, center: 2462, name: "CH 11" },
        ].map((wifi) => {
          const leftPct = freqToPct(wifi.center - 11);
          const widthPct = freqToPct(wifi.center + 11) - leftPct;
          const isActive = activeWifi24.some((e) => e.channel === wifi.ch || Math.abs(e.frequencyMhz - wifi.center) < 5);

          return (
            <div
              key={wifi.ch}
              style={{
                position: "absolute",
                left: `${leftPct}%`,
                width: `${widthPct}%`,
                bottom: 0,
                top: 0,
                backgroundColor: isActive
                  ? "rgba(6, 182, 212, 0.25)"
                  : "rgba(100, 116, 139, 0.08)",
                borderLeft: `1px dashed ${isActive ? "#06B6D4" : "rgba(100, 116, 139, 0.3)"}`,
                borderRight: `1px dashed ${isActive ? "#06B6D4" : "rgba(100, 116, 139, 0.3)"}`,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "flex-end",
                paddingBottom: 2,
              }}
            >
              {/* Wi-Fi Bell Spectral Mask */}
              {isActive && (
                <div
                  style={{
                    position: "absolute",
                    bottom: 0,
                    width: "100%",
                    height: "85%",
                    background: "linear-gradient(to top, rgba(6, 182, 212, 0.6) 0%, rgba(6, 182, 212, 0.1) 80%, transparent 100%)",
                    borderTop: "2px solid #38BDF8",
                    borderRadius: "12px 12px 0 0",
                  }}
                />
              )}
              <span
                style={{
                  position: "relative",
                  fontFamily: "monospace",
                  fontSize: 10,
                  fontWeight: 700,
                  color: isActive ? "#38BDF8" : "#64748B",
                  zIndex: 2,
                }}
              >
                Wi-Fi {wifi.name} (20MHz)
              </span>
            </div>
          );
        })}

        {/* Primary BLE Advertising Channels Indicators */}
        {[
          { ch: 37, freq: 2402, label: "37" },
          { ch: 38, freq: 2426, label: "38" },
          { ch: 39, freq: 2480, label: "39" },
        ].map((adv) => (
          <div
            key={adv.ch}
            style={{
              position: "absolute",
              left: `${freqToPct(adv.freq)}%`,
              top: 0,
              bottom: 0,
              width: 2,
              backgroundColor: "rgba(168, 85, 247, 0.4)",
            }}
          >
            <span
              style={{
                position: "absolute",
                top: 2,
                left: -12,
                fontSize: 8,
                fontFamily: "monospace",
                color: "#A855F7",
                fontWeight: 700,
              }}
            >
              ADV{adv.ch}
            </span>
          </div>
        ))}

        {/* Dynamic Active BLE Channels Spikes */}
        {activeBle.map((bleEvt) => {
          const xPct = freqToPct(bleEvt.frequencyMhz);
          const isCollision = collisions.includes(bleEvt);
          const spikeColor = isCollision ? "#EF4444" : "#A855F7";

          return (
            <div
              key={bleEvt.id}
              style={{
                position: "absolute",
                left: `${xPct}%`,
                bottom: 0,
                width: 6,
                transform: "translateX(-50%)",
                height: "90%",
                background: `linear-gradient(to top, ${spikeColor} 0%, rgba(255,255,255,0.9) 100%)`,
                boxShadow: `0 0 12px ${spikeColor}`,
                borderRadius: "3px 3px 0 0",
                zIndex: 10,
              }}
            >
              {/* Floating Channel Tag */}
              <div
                style={{
                  position: "absolute",
                  top: -20,
                  left: "50%",
                  transform: "translateX(-50%)",
                  backgroundColor: "#0F172A",
                  border: `1px solid ${spikeColor}`,
                  borderRadius: 4,
                  padding: "1px 4px",
                  fontSize: 9,
                  fontFamily: "monospace",
                  fontWeight: 800,
                  color: spikeColor,
                  whiteSpace: "nowrap",
                }}
              >
                {bleEvt.frameSubtype} (CH {bleEvt.channel})
              </div>
            </div>
          );
        })}

        {/* Collision Warning Banner inside Spectrum if Active */}
        {hasCollision && (
          <div
            style={{
              position: "absolute",
              top: "30%",
              left: "40%",
              transform: "translate(-50%, -50%)",
              backgroundColor: "rgba(239, 68, 68, 0.9)",
              color: "#FFF",
              padding: "3px 12px",
              borderRadius: 4,
              fontFamily: "monospace",
              fontSize: 11,
              fontWeight: 900,
              letterSpacing: 0.8,
              zIndex: 25,
              boxShadow: "0 0 15px rgba(239, 68, 68, 0.8)",
            }}
          >
            ! SPECTRUM COLLISION: BLE HOP IN WIFI BAND !
          </div>
        )}
      </div>

      {/* Frequency Axis Scale Labels */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: 4,
          fontSize: 9,
          fontFamily: "monospace",
          color: "#94A3B8",
        }}
      >
        <span>2400 MHz</span>
        <span>2412 (Ch1)</span>
        <span>2426 (Adv38)</span>
        <span>2437 (Ch6)</span>
        <span>2450 MHz</span>
        <span>2462 (Ch11)</span>
        <span>2480 (Adv39)</span>
        <span>2485 MHz</span>
      </div>
    </div>
  );
};
