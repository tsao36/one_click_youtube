import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { AgentSimulationSceneProps } from "./simulationTypes";
import { SpatialTrackingAnchor } from "./SpatialTrackingAnchor";
import { AgentQueueVisualizer } from "./AgentQueueVisualizer";
import { SimulationTimelineTicker } from "./SimulationTimelineTicker";

export const AgentSimulationScene: React.FC<AgentSimulationSceneProps> = ({
  badge = "AI EMERGENCE EXPERIMENT",
  title = "50 AI Agents in Sandbox Simulation",
  subtitle = "From early chaos to self-organizing bureaucracy",
  experimentPrompt = "MISSION PROMPT: 'Build a prosperous civilization'",
  anchors = [],
  agents = [],
  metrics = [],
  milestones = [],
  finalPunchline = "RESULT: 3 HOURS LATER -> ORDERLY FOOD QUEUING & BUREAUCRACY",
  bgSrc = "",
  dim = 0.55,
  accentColor = "#F59E0B",
  enableSfx = true,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Three-Phase Boundaries
  const phase1End = Math.floor(durationInFrames * 0.3);
  const phase2End = Math.floor(durationInFrames * 0.7);

  // Entrance spring
  const headerSpring = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 100 },
  });

  // Climax punchline spring for Phase 3
  const punchlineSpring = spring({
    frame: frame - phase2End,
    fps,
    config: { damping: 12, mass: 0.7, stiffness: 110 },
  });

  // Active milestone based on frame
  const activeMilestone =
    milestones.slice().reverse().find((m) => frame >= m.atFrame) || milestones[0];

  // Ambient breathing spotlight
  const breatheScale = interpolate(Math.sin(frame / 35), [-1, 1], [0.94, 1.06]);

  return (
    <AbsoluteFill style={{ backgroundColor: "#080B12", overflow: "hidden", color: "#F8FAFC" }}>
      {/* 1. Grounding Media / Background Layer */}
      {bgSrc ? (
        <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
          <Img
            src={bgSrc.startsWith("http") ? bgSrc : staticFile(bgSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${interpolate(frame, [0, durationInFrames], [1.02, 1.08])})`,
              filter: `brightness(${1 - dim * 0.7}) contrast(1.1)`,
            }}
          />
        </div>
      ) : (
        /* Atmospheric Gradient if no image provided */
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "radial-gradient(circle at 50% 30%, #172033 0%, #080B12 75%)",
          }}
        />
      )}

      {/* Volumetric Radial Spotlight */}
      <div
        style={{
          position: "absolute",
          top: "20%",
          left: "50%",
          width: 900,
          height: 600,
          transform: `translate(-50%, -50%) scale(${breatheScale})`,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accentColor}18 0%, transparent 65%)`,
          filter: "blur(90px)",
          pointerEvents: "none",
        }}
      />

      {/* Survey Grid Lines Overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "linear-gradient(rgba(148, 163, 184, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(148, 163, 184, 0.05) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
          pointerEvents: "none",
        }}
      />

      {/* 2. Audio SFX Sync */}
      {enableSfx && frame === 2 && <Audio src={staticFile("sfx/whoosh.wav")} volume={0.6} />}
      {enableSfx && frame === phase2End && <Audio src={staticFile("sfx/pop.wav")} volume={0.8} />}

      {/* 3. Top Header HUD */}
      <div
        style={{
          position: "absolute",
          top: 24,
          left: 36,
          right: 36,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          zIndex: 40,
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
              backgroundColor: "rgba(245, 158, 11, 0.15)",
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
                color: "#FEF3C7",
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
              textShadow: "0 2px 12px rgba(0,0,0,0.85)",
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

          {/* Experiment Prompt Banner */}
          {experimentPrompt && (
            <div
              style={{
                marginTop: 8,
                display: "inline-flex",
                alignItems: "center",
                backgroundColor: "rgba(15, 23, 42, 0.8)",
                border: "1px dashed rgba(245, 158, 11, 0.5)",
                padding: "3px 10px",
                borderRadius: 6,
                fontSize: 11,
                fontFamily: "monospace",
                color: "#FDE68A",
              }}
            >
              &gt; {experimentPrompt}
            </div>
          )}
        </div>
      </div>

      {/* 4. Active Milestone Headline Banner (Center Anchor) */}
      {activeMilestone && (
        <div
          style={{
            position: "absolute",
            top: 100,
            left: "50%",
            transform: "translateX(-50%)",
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            border: `1.5px solid ${accentColor}80`,
            borderRadius: 10,
            padding: "8px 24px",
            boxShadow: `0 8px 30px rgba(0, 0, 0, 0.7), 0 0 16px ${accentColor}25`,
            backdropFilter: "blur(12px)",
            zIndex: 42,
            textAlign: "center",
            maxWidth: 680,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              gap: 8,
              marginBottom: 2,
            }}
          >
            <span
              style={{
                fontSize: 9,
                fontFamily: "monospace",
                fontWeight: 800,
                backgroundColor: `${accentColor}25`,
                color: accentColor,
                padding: "1px 6px",
                borderRadius: 4,
              }}
            >
              {activeMilestone.timeCode}
            </span>
            <span
              style={{
                fontFamily: "monospace",
                fontSize: 13,
                fontWeight: 800,
                color: "#F8FAFC",
                letterSpacing: 0.8,
              }}
            >
              {activeMilestone.headline}
            </span>
          </div>
          <div style={{ fontSize: 11.5, color: "#CBD5E1" }}>{activeMilestone.detail}</div>
        </div>
      )}

      {/* 5. Spatial Tracking Anchors on Image Coordinates */}
      {anchors.map((anchor, idx) => (
        <SpatialTrackingAnchor
          key={anchor.id}
          anchor={anchor}
          delayIndex={idx}
          isHighlighted={activeMilestone?.highlightAnchorIds?.includes(anchor.id)}
        />
      ))}

      {/* 6. Live Simulation Telemetry Ticker */}
      {metrics.length > 0 && (
        <SimulationTimelineTicker
          metrics={metrics}
          currentTimeCode={activeMilestone?.timeCode || "03:00:00"}
        />
      )}

      {/* 7. Animated Food Queue & Bureaucracy Line */}
      {agents.length > 0 && (
        <AgentQueueVisualizer
          agents={agents}
          accentColor={accentColor}
          phaseProgress={frame / durationInFrames}
        />
      )}

      {/* 8. Phase 3 Dramatic Climax Punchline Stamp */}
      {frame >= phase2End && finalPunchline && (
        <div
          style={{
            position: "absolute",
            top: "42%",
            left: "50%",
            transform: `translate(-50%, -50%) scale(${punchlineSpring})`,
            opacity: punchlineSpring,
            backgroundColor: "rgba(239, 68, 68, 0.95)",
            border: "3px solid #FEE2E2",
            borderRadius: 12,
            padding: "14px 28px",
            boxShadow: "0 0 50px rgba(239, 68, 68, 0.8), 0 12px 30px rgba(0,0,0,0.9)",
            zIndex: 60,
            textAlign: "center",
            maxWidth: 820,
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontFamily: "monospace",
              fontWeight: 900,
              color: "#FEF2F2",
              letterSpacing: 2,
              marginBottom: 4,
            }}
          >
            ★ EXPERIMENT OUTCOME DECODED ★
          </div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 900,
              color: "#FFFFFF",
              letterSpacing: -0.5,
              textShadow: "0 2px 8px rgba(0,0,0,0.6)",
            }}
          >
            {finalPunchline}
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};
