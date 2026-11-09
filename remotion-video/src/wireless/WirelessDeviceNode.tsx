import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { WirelessDevice } from "./wirelessTypes";

interface WirelessDeviceNodeProps {
  device: WirelessDevice;
  isTransmitting?: boolean;
  isReceiving?: boolean;
  isInterfered?: boolean;
  isBackingOff?: boolean;
  activeChannel?: string | number;
  highlighted?: boolean;
  pulseColor?: string;
  mloActiveLinks?: { link1Active: boolean; link2Active: boolean; mode: string };
}

export const WirelessDeviceNode: React.FC<WirelessDeviceNodeProps> = ({
  device,
  isTransmitting = false,
  isReceiving = false,
  isInterfered = false,
  isBackingOff = false,
  activeChannel,
  highlighted = false,
  pulseColor = "#06B6D4",
  mloActiveLinks,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Gentle breathing idle animation
  const breathe = Math.sin(frame / 20 + device.x) * 0.04 + 1.0;

  // Concentric wave ripple animation when transmitting
  const wave1 = (frame * 3) % 60;
  const wave2 = (frame * 3 + 20) % 60;
  const wave3 = (frame * 3 + 40) % 60;

  const renderIcon = () => {
    switch (device.role) {
      case "ap":
        return (
          <g>
            {/* AP Dual Antennas */}
            <line x1="28" y1="28" x2="22" y2="8" stroke={pulseColor} strokeWidth="3.5" strokeLinecap="round" />
            <circle cx="22" cy="8" r="3" fill={pulseColor} />
            <line x1="52" y1="28" x2="58" y2="8" stroke={pulseColor} strokeWidth="3.5" strokeLinecap="round" />
            <circle cx="58" cy="8" r="3" fill={pulseColor} />
            {/* Main Router Body */}
            <rect x="14" y="28" width="52" height="28" rx="7" fill="#1E293B" stroke={pulseColor} strokeWidth="2.5" />
            {/* LED Status Dots */}
            <circle cx="24" cy="42" r="2.5" fill="#10B981" />
            <circle cx="32" cy="42" r="2.5" fill={isTransmitting ? "#38BDF8" : "#64748B"} />
            <circle cx="40" cy="42" r="2.5" fill={isReceiving ? "#A855F7" : "#64748B"} />
            <circle cx="48" cy="42" r="2.5" fill={isInterfered ? "#EF4444" : "#10B981"} />
            <circle cx="56" cy="42" r="2.5" fill="#38BDF8" />
          </g>
        );
      case "laptop":
        return (
          <g>
            {/* Laptop Screen */}
            <rect x="18" y="16" width="44" height="28" rx="4" fill="#0F172A" stroke={pulseColor} strokeWidth="2" />
            <rect x="22" y="20" width="36" height="20" rx="2" fill="#1E293B" />
            <path d="M 28 32 L 34 26 L 42 34 L 50 24" stroke={pulseColor} strokeWidth="1.5" fill="none" />
            {/* Base */}
            <path d="M 10 46 L 70 46 L 66 54 L 14 54 Z" fill="#334155" stroke={pulseColor} strokeWidth="1.5" />
            <line x1="34" y1="48" x2="46" y2="48" stroke="#94A3B8" strokeWidth="1.5" strokeLinecap="round" />
          </g>
        );
      case "smartphone":
        return (
          <g>
            {/* Phone Body */}
            <rect x="25" y="12" width="30" height="56" rx="6" fill="#0F172A" stroke={pulseColor} strokeWidth="2" />
            <rect x="28" y="16" width="24" height="46" rx="3" fill="#1E293B" />
            {/* Camera notch */}
            <circle cx="40" cy="19" r="1.5" fill="#64748B" />
            {/* Screen Wave */}
            <circle cx="40" cy="38" r="6" stroke={pulseColor} strokeWidth="1" fill="none" opacity="0.6" />
            <circle cx="40" cy="38" r="2" fill={pulseColor} />
          </g>
        );
      case "bt_controller":
        return (
          <g>
            {/* Gamepad / BT Controller */}
            <path
              d="M 18 26 C 24 20, 56 20, 62 26 C 68 32, 66 52, 56 54 C 50 56, 44 46, 40 46 C 36 46, 30 56, 24 54 C 14 52, 12 32, 18 26 Z"
              fill="#1E293B"
              stroke={pulseColor}
              strokeWidth="2"
            />
            {/* D-pad & Buttons */}
            <circle cx="28" cy="34" r="3" fill="#38BDF8" />
            <circle cx="52" cy="34" r="3" fill="#EC4899" />
            <circle cx="40" cy="32" r="2" fill="#94A3B8" />
          </g>
        );
      case "headphones":
        return (
          <g>
            {/* Over-Ear Headphones Arc */}
            <path d="M 20 40 A 20 20 0 0 1 60 40" stroke={pulseColor} strokeWidth="3" fill="none" strokeLinecap="round" />
            {/* Left Ear Cup */}
            <rect x="14" y="34" width="10" height="20" rx="4" fill="#334155" stroke={pulseColor} strokeWidth="2" />
            {/* Right Ear Cup */}
            <rect x="56" y="34" width="10" height="20" rx="4" fill="#334155" stroke={pulseColor} strokeWidth="2" />
            {/* Audio Wave mark */}
            <path d="M 36 42 Q 40 38 44 42" stroke="#38BDF8" strokeWidth="2" fill="none" strokeLinecap="round" />
          </g>
        );
      case "iot":
      default:
        return (
          <g>
            {/* IoT Sensor node */}
            <circle cx="40" cy="40" r="18" fill="#1E293B" stroke={pulseColor} strokeWidth="2.5" />
            <circle cx="40" cy="40" r="9" fill="#0F172A" stroke={pulseColor} strokeWidth="1.5" />
            <line x1="40" y1="22" x2="40" y2="12" stroke={pulseColor} strokeWidth="2.5" strokeLinecap="round" />
            <circle cx="40" cy="12" r="2.5" fill="#F59E0B" />
          </g>
        );
    }
  };

  // Status color logic
  let statusBadgeColor = "#10B981"; // ready
  let statusText = "STANDBY";
  if (isInterfered) {
    statusBadgeColor = "#EF4444";
    statusText = "COLLISION / RETRY";
  } else if (isBackingOff) {
    statusBadgeColor = "#F59E0B";
    statusText = "CSMA BACKOFF";
  } else if (isTransmitting) {
    statusBadgeColor = "#06B6D4";
    statusText = "TRANSMITTING";
  } else if (isReceiving) {
    statusBadgeColor = "#A855F7";
    statusText = "RECEIVING";
  } else if (device.status === "roaming") {
    statusBadgeColor = "#EC4899";
    statusText = "ROAMING 802.11r";
  }

  return (
    <div
      style={{
        position: "absolute",
        left: `${device.x}%`,
        top: `${device.y}%`,
        transform: `translate(-50%, -50%) scale(${highlighted ? 1.15 : breathe})`,
        transition: "transform 0.2s ease-out",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        zIndex: highlighted ? 30 : 15,
        pointerEvents: "none",
      }}
    >
      {/* Concentric RF Waves when Transmitting */}
      {isTransmitting && (
        <svg
          style={{
            position: "absolute",
            top: -50,
            left: -50,
            width: 180,
            height: 180,
            pointerEvents: "none",
            overflow: "visible",
          }}
        >
          <circle
            cx="90"
            cy="90"
            r={15 + wave1 * 1.2}
            stroke={pulseColor}
            strokeWidth={interpolate(wave1, [0, 60], [2.5, 0])}
            fill="none"
            opacity={interpolate(wave1, [0, 60], [0.85, 0])}
          />
          <circle
            cx="90"
            cy="90"
            r={15 + wave2 * 1.2}
            stroke={pulseColor}
            strokeWidth={interpolate(wave2, [0, 60], [2.5, 0])}
            fill="none"
            opacity={interpolate(wave2, [0, 60], [0.85, 0])}
          />
          <circle
            cx="90"
            cy="90"
            r={15 + wave3 * 1.2}
            stroke={pulseColor}
            strokeWidth={interpolate(wave3, [0, 60], [2.5, 0])}
            fill="none"
            opacity={interpolate(wave3, [0, 60], [0.85, 0])}
          />
        </svg>
      )}

      {/* Main Device SVG Container */}
      <div
        style={{
          width: 80,
          height: 80,
          borderRadius: "50%",
          background: isInterfered
            ? "radial-gradient(circle, rgba(239, 68, 68, 0.25) 0%, rgba(15, 23, 42, 0.85) 75%)"
            : highlighted
            ? `radial-gradient(circle, rgba(6, 182, 212, 0.3) 0%, rgba(15, 23, 42, 0.9) 75%)`
            : "rgba(15, 23, 42, 0.85)",
          border: `2px solid ${isInterfered ? "#EF4444" : highlighted ? pulseColor : "rgba(148, 163, 184, 0.3)"}`,
          boxShadow: isInterfered
            ? "0 0 25px rgba(239, 68, 68, 0.6)"
            : highlighted
            ? `0 0 30px ${pulseColor}`
            : "0 8px 24px rgba(0, 0, 0, 0.5)",
          backdropFilter: "blur(8px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
        }}
      >
        <svg width="80" height="80" viewBox="0 0 80 80">
          {renderIcon()}
        </svg>

        {/* Small Band Pill */}
        <div
          style={{
            position: "absolute",
            top: -8,
            right: -8,
            backgroundColor: "#0F172A",
            border: `1px solid ${pulseColor}`,
            borderRadius: 8,
            padding: "1px 6px",
            fontSize: 10,
            fontFamily: "monospace",
            fontWeight: 700,
            color: pulseColor,
            boxShadow: "0 2px 6px rgba(0,0,0,0.4)",
          }}
        >
          {device.activeBand}
        </div>
      </div>

      {/* Device Metadata Card */}
      <div
        style={{
          marginTop: 8,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          background: "rgba(15, 23, 42, 0.85)",
          border: "1px solid rgba(255, 255, 255, 0.12)",
          borderRadius: 8,
          padding: "4px 10px",
          backdropFilter: "blur(6px)",
          boxShadow: "0 4px 16px rgba(0, 0, 0, 0.4)",
          minWidth: 120,
        }}
      >
        <div
          style={{
            color: "#F8FAFC",
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: 0.5,
            textAlign: "center",
          }}
        >
          {device.name}
        </div>

        {/* Sublabel / MAC / Channel */}
        <div
          style={{
            display: "flex",
            gap: 6,
            alignItems: "center",
            marginTop: 2,
            fontSize: 10,
            fontFamily: "monospace",
            color: "#94A3B8",
          }}
        >
          {activeChannel ? (
            <span style={{ color: "#38BDF8", fontWeight: 600 }}>CH {activeChannel}</span>
          ) : device.mac ? (
            <span>{device.mac}</span>
          ) : (
            <span>{device.sublabel || device.role.toUpperCase()}</span>
          )}
        </div>

        {/* Dynamic Status Pill */}
        <div
          style={{
            marginTop: 4,
            display: "flex",
            alignItems: "center",
            gap: 4,
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            padding: "2px 6px",
            borderRadius: 4,
          }}
        >
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              backgroundColor: statusBadgeColor,
              boxShadow: `0 0 6px ${statusBadgeColor}`,
            }}
          />
          <span
            style={{
              fontSize: 9,
              fontFamily: "monospace",
              fontWeight: 700,
              color: statusBadgeColor,
              letterSpacing: 0.5,
            }}
          >
            {statusText}
          </span>
        </div>

        {/* Wi-Fi 7 MLO Links Status (if enabled for this device) */}
        {mloActiveLinks && (
          <div
            style={{
              marginTop: 4,
              display: "flex",
              gap: 4,
              fontSize: 8,
              fontFamily: "monospace",
            }}
          >
            <span
              style={{
                padding: "1px 4px",
                borderRadius: 2,
                backgroundColor: mloActiveLinks.link1Active ? "rgba(16, 185, 129, 0.25)" : "rgba(100, 116, 139, 0.2)",
                color: mloActiveLinks.link1Active ? "#34D399" : "#64748B",
                border: `1px solid ${mloActiveLinks.link1Active ? "#10B981" : "#475569"}`,
              }}
            >
              L1: 5GHz {mloActiveLinks.link1Active ? "TX/RX" : "IDLE"}
            </span>
            <span
              style={{
                padding: "1px 4px",
                borderRadius: 2,
                backgroundColor: mloActiveLinks.link2Active
                  ? "rgba(6, 182, 212, 0.25)"
                  : mloActiveLinks.mode === "emlsr"
                  ? "rgba(239, 68, 68, 0.2)"
                  : "rgba(100, 116, 139, 0.2)",
                color: mloActiveLinks.link2Active
                  ? "#22D3EE"
                  : mloActiveLinks.mode === "emlsr"
                  ? "#F87171"
                  : "#64748B",
                border: `1px solid ${
                  mloActiveLinks.link2Active
                    ? "#06B6D4"
                    : mloActiveLinks.mode === "emlsr"
                    ? "#EF4444"
                    : "#475569"
                }`,
              }}
            >
              L2: 6GHz {mloActiveLinks.link2Active ? "TX/RX" : mloActiveLinks.mode === "emlsr" ? "BLOCKED" : "IDLE"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
