import React from "react";
import {
  AbsoluteFill,
  Audio,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { ModernExplainerBackground } from "../ModernExplainerBackground";
import { WirelessSceneProps } from "./wirelessTypes";
import { WirelessDeviceNode } from "./WirelessDeviceNode";
import { RfTransmissionPath } from "./RfTransmissionPath";
import { SpectrumTimeline } from "./SpectrumTimeline";
import { PacketSequenceDiagram } from "./PacketSequenceDiagram";
import { MloVisualizer } from "./MloVisualizer";

export const WirelessNetworkScene: React.FC<WirelessSceneProps> = ({
  badge = "WIRELESS SPECTRUM ENGINE",
  title = "Wi-Fi & Bluetooth Traffic Visualizer",
  subtitle = "Physical-layer radio frames and protocol choreography",
  mode = "simplified",
  devices = [],
  events = [],
  narrativeBeats = [],
  showSpectrumTimeline = true,
  showSequenceDiagram = true,
  showCoexMonitor = true,
  showMloDualLinks = false,
  timeScale = 1.0,
  accentColor = "#06B6D4",
  bgSrc = "",
  dim = 0.75,
  captionAudioSrc = "",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Header entrance spring
  const headerSpring = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 100 },
  });

  // Calculate scaled frame if timeScale is customized
  const effectiveFrame = Math.round(frame * timeScale);

  // Identify currently active radio events
  const activeEvents = events.filter((e) => {
    return effectiveFrame >= e.startFrame && effectiveFrame <= e.startFrame + e.durationFrames;
  });

  // Identify recently completed events (past 90 frames)
  const recentEvents = events.filter((e) => {
    return effectiveFrame > e.startFrame + e.durationFrames && effectiveFrame <= e.startFrame + e.durationFrames + 90;
  });

  // Find active narrative beat
  const currentBeat = narrativeBeats.slice().reverse().find((b) => effectiveFrame >= b.atFrame);

  // Check if any device is in MLO mode
  const mloDevice = devices.find((d) => d.mloMode && d.mloMode !== "none");
  const isMloScene = showMloDualLinks || Boolean(mloDevice);

  return (
    <AbsoluteFill style={{ backgroundColor: "#080B12", overflow: "hidden", color: "#F8FAFC" }}>
      {/* Background with Ambient Glow */}
      <ModernExplainerBackground accentColor={accentColor} dim={dim} />

      {/* Cyberpunk Grid Coordinate Layer */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "linear-gradient(rgba(148, 163, 184, 0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(148, 163, 184, 0.04) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
          pointerEvents: "none",
        }}
      />

      {/* Optional Narration Audio */}
      {captionAudioSrc && (
        <Audio src={captionAudioSrc.startsWith("http") ? captionAudioSrc : staticFile(captionAudioSrc)} />
      )}

      {/* Top Header HUD */}
      <div
        style={{
          position: "absolute",
          top: 24,
          left: 36,
          right: 36,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          zIndex: 50,
          transform: `translateY(${interpolate(headerSpring, [0, 1], [-40, 0])}px)`,
          opacity: headerSpring,
        }}
      >
        <div>
          {/* Badge */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "3px 12px",
              borderRadius: 20,
              backgroundColor: "rgba(6, 182, 212, 0.15)",
              border: `1px solid ${accentColor}`,
              boxShadow: `0 0 16px ${accentColor}40`,
              marginBottom: 6,
            }}
          >
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                backgroundColor: accentColor,
                boxShadow: `0 0 8px ${accentColor}`,
              }}
            />
            <span
              style={{
                fontFamily: "monospace",
                fontSize: 11,
                fontWeight: 800,
                color: "#E0F2FE",
                letterSpacing: 1.5,
              }}
            >
              {badge}
            </span>
          </div>

          {/* Title & Subtitle */}
          <h1
            style={{
              margin: 0,
              fontSize: 28,
              fontWeight: 800,
              letterSpacing: -0.5,
              color: "#FFFFFF",
              textShadow: "0 2px 10px rgba(0,0,0,0.8)",
            }}
          >
            {title}
          </h1>
          {subtitle && (
            <p
              style={{
                margin: "4px 0 0 0",
                fontSize: 14,
                color: "#94A3B8",
                fontWeight: 500,
              }}
            >
              {subtitle}
            </p>
          )}
        </div>

        {/* Right Top Status Counters */}
        <div
          style={{
            display: "flex",
            gap: 12,
            alignItems: "center",
            background: "rgba(15, 23, 42, 0.8)",
            border: "1px solid rgba(148, 163, 184, 0.2)",
            borderRadius: 8,
            padding: "6px 14px",
            backdropFilter: "blur(8px)",
          }}
        >
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 9, fontFamily: "monospace", color: "#64748B" }}>RENDER MODE</div>
            <div style={{ fontSize: 11, fontFamily: "monospace", fontWeight: 700, color: "#38BDF8" }}>
              {mode.toUpperCase()}
            </div>
          </div>
          <div style={{ width: 1, height: 24, backgroundColor: "rgba(255,255,255,0.1)" }} />
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 9, fontFamily: "monospace", color: "#64748B" }}>TIMELINE TIME</div>
            <div style={{ fontSize: 12, fontFamily: "monospace", fontWeight: 700, color: "#10B981" }}>
              {(effectiveFrame / fps).toFixed(2)}s ({effectiveFrame}f)
            </div>
          </div>
        </div>
      </div>

      {/* Dynamic Narrative Beat Banner (Centrally Anchored) */}
      {currentBeat && (
        <div
          style={{
            position: "absolute",
            top: 104,
            left: "50%",
            transform: "translateX(-50%)",
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            border: "1px solid rgba(56, 189, 248, 0.4)",
            borderRadius: 10,
            padding: "8px 24px",
            boxShadow: "0 8px 30px rgba(0, 0, 0, 0.7)",
            backdropFilter: "blur(10px)",
            zIndex: 45,
            textAlign: "center",
            maxWidth: 720,
          }}
        >
          <div
            style={{
              fontFamily: "monospace",
              fontSize: 13,
              fontWeight: 800,
              color: "#38BDF8",
              letterSpacing: 0.8,
            }}
          >
            {currentBeat.headline}
          </div>
          <div
            style={{
              fontSize: 12,
              color: "#E2E8F0",
              marginTop: 2,
            }}
          >
            {currentBeat.detail}
          </div>
        </div>
      )}

      {/* Active RF Transmission Paths & Waves */}
      {activeEvents.map((evt) => {
        const srcDev = devices.find((d) => d.id === evt.sourceId);
        const dstDev = devices.find((d) => d.id === evt.targetId);
        if (!srcDev) return null;

        return (
          <RfTransmissionPath
            key={evt.id}
            event={evt}
            sourceDevice={srcDev}
            targetDevice={dstDev}
            currentFrame={effectiveFrame}
          />
        );
      })}

      {/* Wireless Devices Rendering */}
      {devices.map((device) => {
        // Determine dynamic device states from active events
        const isTx = activeEvents.some((e) => e.sourceId === device.id);
        const isRx = activeEvents.some((e) => e.targetId === device.id || (e.targetId === "broadcast" && e.sourceId !== device.id));
        const hasCollided = activeEvents.some((e) => (e.sourceId === device.id || e.targetId === device.id) && e.signalState === "collision");
        const activeEvt = activeEvents.find((e) => e.sourceId === device.id || e.targetId === device.id);

        const isHighlighted = currentBeat?.highlightDeviceIds?.includes(device.id);

        let mloActiveLinks;
        if (device.mloMode && device.mloMode !== "none") {
          const l1 = activeEvents.some((e) => e.linkId === 0);
          const l2 = activeEvents.some((e) => e.linkId === 1);
          mloActiveLinks = { link1Active: l1, link2Active: l2, mode: device.mloMode };
        }

        return (
          <WirelessDeviceNode
            key={device.id}
            device={device}
            isTransmitting={isTx}
            isReceiving={isRx}
            isInterfered={hasCollided}
            activeChannel={activeEvt?.channel}
            highlighted={isHighlighted}
            pulseColor={device.role === "ap" ? "#06B6D4" : device.role.startsWith("bt") ? "#A855F7" : "#38BDF8"}
            mloActiveLinks={mloActiveLinks}
          />
        );
      })}

      {/* Optional Wi-Fi 7 MLO Visualizer Box */}
      {isMloScene && mloDevice && (
        <MloVisualizer
          mode={(mloDevice.mloMode as "str" | "emlsr") || "str"}
          activeEvents={activeEvents}
          currentFrame={effectiveFrame}
        />
      )}

      {/* Optional Sequence Ladder Diagram */}
      {showSequenceDiagram && (
        <PacketSequenceDiagram
          events={events}
          devices={devices}
          currentFrame={effectiveFrame}
        />
      )}

      {/* 2.4 GHz Spectrum Frequency vs Time Waterfall */}
      {showSpectrumTimeline && (
        <SpectrumTimeline
          activeEvents={activeEvents}
          recentEvents={recentEvents}
          currentFrame={effectiveFrame}
          showCoexMonitor={showCoexMonitor}
        />
      )}
    </AbsoluteFill>
  );
};
