import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import {
  ProceduralBackground,
  RveSceneFooter,
  RveSceneHeader,
} from "./ProceduralBackground";
import { RveProgressStepsSceneProps } from "./types";
import { useContinuousDrift } from "./animations";

const DEFAULT_STEPS = [
  { label: "定義問題", detail: "釐清核心邊界條件與基準數據", tag: "STEP 01" },
  { label: "結構拆解", detail: "識別關鍵依賴與系統瓶頸", tag: "STEP 02" },
  { label: "方案驗證", detail: "小規模測試並量化實際效益", tag: "STEP 03" },
  { label: "全面落地", detail: "穩定擴展並持續監控指標", tag: "STEP 04" },
];

export const RveProgressStepsScene: React.FC<RveProgressStepsSceneProps> = ({
  badge = "EXECUTION ROADMAP",
  title = "多階段推進核心流程",
  subtitle = "",
  steps = DEFAULT_STEPS,
  source = "",
  accentColor = "#38BDF8",
  bgSrc = "",
  dim = 0.5,
  bgVariant = "gradient-shift",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const { floatY } = useContinuousDrift(0.00015);

  const safeSteps =
    steps && steps.length >= 2 ? steps.slice(0, 6) : DEFAULT_STEPS;
  const framesPerStep = Math.max(
    18,
    Math.floor((durationInFrames * 0.72) / safeSteps.length)
  );

  return (
    <ProceduralBackground
      variant={bgVariant}
      accentColor={accentColor}
      bgSrc={bgSrc}
      dim={dim}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: "100%",
          height: "100%",
          padding: "64px 110px 52px",
          boxSizing: "border-box",
        }}
      >
        <RveSceneHeader
          badge={badge}
          title={title}
          subtitle={subtitle}
          accentColor={accentColor}
        />

        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            transform: `translateY(${floatY}px)`,
          }}
        >
          {/* Connected node track + cards */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${safeSteps.length}, 1fr)`,
              gap: 24,
              alignItems: "stretch",
              position: "relative",
            }}
          >
            {safeSteps.map((step, i) => {
              const stepStart = 6 + i * framesPerStep;
              const fillProg = interpolate(
                frame,
                [stepStart, stepStart + framesPerStep * 0.55],
                [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
              );
              const isActive =
                frame >= stepStart && frame < stepStart + framesPerStep;
              const isReached = frame >= stepStart;

              const nodePulse = isActive
                ? spring({
                    frame: Math.max(0, frame - stepStart),
                    fps,
                    config: { damping: 9, stiffness: 150, mass: 0.5 },
                  })
                : isReached
                  ? 1
                  : 0.92;

              const cardSpring = spring({
                frame: Math.max(0, frame - stepStart + 4),
                fps,
                config: { damping: 14, stiffness: 115 },
              });

              const lineProg =
                i < safeSteps.length - 1
                  ? interpolate(
                      frame,
                      [stepStart + framesPerStep * 0.45, stepStart + framesPerStep],
                      [0, 1],
                      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
                    )
                  : 0;

              const circleScale = isActive
                ? 0.94 + nodePulse * 0.16
                : isReached
                  ? 1.04
                  : 0.94;

              return (
                <div
                  key={`step-${i}`}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    position: "relative",
                  }}
                >
                  {/* Connector line to next step */}
                  {i < safeSteps.length - 1 && (
                    <div
                      style={{
                        position: "absolute",
                        top: 38,
                        left: "calc(50% + 44px)",
                        width: "calc(100% - 64px)",
                        height: 6,
                        borderRadius: 3,
                        backgroundColor: "rgba(255, 255, 255, 0.12)",
                        overflow: "hidden",
                        zIndex: 1,
                      }}
                    >
                      <div
                        style={{
                          width: `${lineProg * 100}%`,
                          height: "100%",
                          background: `linear-gradient(90deg, ${accentColor}, #8B5CF6)`,
                          boxShadow: `0 0 12px ${accentColor}`,
                        }}
                      />
                    </div>
                  )}

                  {/* Step Circle */}
                  <div
                    style={{
                      width: 78,
                      height: 78,
                      borderRadius: "50%",
                      border: `3px solid ${fillProg > 0.05 ? accentColor : "rgba(255,255,255,0.22)"}`,
                      background:
                        fillProg > 0.05
                          ? `linear-gradient(135deg, ${accentColor}, #6366F1)`
                          : "rgba(15, 23, 42, 0.85)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 30,
                      fontWeight: 900,
                      color: fillProg > 0.05 ? "#FFFFFF" : "#64748B",
                      transform: `scale(${circleScale})`,
                      boxShadow: isActive
                        ? `0 0 28px ${accentColor}88`
                        : fillProg > 0.05
                          ? `0 0 14px ${accentColor}44`
                          : "none",
                      zIndex: 2,
                      marginBottom: 26,
                    }}
                  >
                    {`0${i + 1}`}
                  </div>

                  {/* Step Detail Card */}
                  <div
                    style={{
                      width: "100%",
                      flex: 1,
                      padding: safeSteps.length >= 5 ? "22px 18px" : "28px 24px",
                      borderRadius: 20,
                      background: isActive
                        ? "rgba(30, 41, 59, 0.88)"
                        : "rgba(15, 23, 42, 0.72)",
                      border: isActive
                        ? `2px solid ${accentColor}`
                        : "1px solid rgba(255, 255, 255, 0.12)",
                      boxShadow: isActive
                        ? `0 16px 40px rgba(0,0,0,0.45), 0 0 24px ${accentColor}26`
                        : "0 12px 32px rgba(0, 0, 0, 0.35)",
                      backdropFilter: "blur(14px)",
                      opacity: Math.max(0.25, cardSpring),
                      transform: `translateY(${(1 - cardSpring) * 20}px)`,
                      boxSizing: "border-box",
                      display: "flex",
                      flexDirection: "column",
                      gap: 12,
                    }}
                  >
                    {step.tag && (
                      <div
                        style={{
                          fontSize: 14,
                          fontWeight: 800,
                          letterSpacing: "0.08em",
                          color: isReached ? accentColor : "#64748B",
                          textTransform: "uppercase",
                        }}
                      >
                        {step.tag}
                      </div>
                    )}
                    <div
                      style={{
                        fontSize: safeSteps.length >= 5 ? 24 : 28,
                        fontWeight: 800,
                        color: "#FFFFFF",
                        lineHeight: 1.3,
                      }}
                    >
                      {step.label}
                    </div>
                    {step.detail && (
                      <div
                        style={{
                          fontSize: safeSteps.length >= 5 ? 18 : 21,
                          lineHeight: 1.55,
                          color: "#CBD5E1",
                          fontWeight: 450,
                        }}
                      >
                        {step.detail}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <RveSceneFooter source={source} accentColor={accentColor} />
      </div>
    </ProceduralBackground>
  );
};
