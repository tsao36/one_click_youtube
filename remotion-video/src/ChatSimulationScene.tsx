import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ModernExplainerBackground } from "./ModernExplainerBackground";
import { ChatSimulationSceneProps } from "./types";

export const ChatSimulationScene: React.FC<ChatSimulationSceneProps> = ({
  badge = "AI WORKFLOW EXECUTION",
  title = "模擬實際提問與階梯式成果輸出",
  systemTag = "Claude 3.5 Sonnet · 200k Context",
  promptText = "請分析我們的產品官網文案，找出造成跳出率 72% 的三個認知摩擦點，並重寫首屏價值主張。",
  responseTitle = "深度執行產出 (Generated Output)",
  responseItems = [
    {
      title: "1. 認知摩擦點診斷",
      detail: "首屏主標題過於抽象（'賦能全場景協同'），用戶前 3 秒無法辨識具體用途與自身痛點關聯。",
      tag: "DIAGNOSTIC",
    },
    {
      title: "2. 首屏文案 A/B 重構方案",
      detail: "改為直球痛點：'不必再手動校對 50 份報表，AI 5 秒找出數據異常，每天省下 2 小時。'",
      tag: "COPYWRITING",
    },
    {
      title: "3. 轉化觸發點與行動呼籲",
      detail: "將模糊的'了解更多'升級為低阻力試用承諾：'免費測試你的第一份數據，無需綁定信用卡'。",
      tag: "CONVERSION",
    },
  ],
  accentColor = "#A855F7",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Top header spring
  const hSpring = spring({ frame, fps, config: { mass: 0.5, damping: 14, stiffness: 120 } });
  const hOpacity = interpolate(hSpring, [0, 1], [0, 1]);
  const hY = interpolate(hSpring, [0, 1], [-25, 0]);

  // Window container spring
  const wSpring = spring({ frame: Math.max(0, frame - 5), fps, config: { mass: 0.6, damping: 15, stiffness: 110 } });
  const wOpacity = interpolate(wSpring, [0, 1], [0, 1]);
  const wScale = interpolate(wSpring, [0, 1], [0.95, 1]);

  // Typewriter effect on user prompt
  // Starts at frame 15, types 1 character every 0.6 frames
  const typeStart = 15;
  const charsCount = Math.floor(Math.max(0, frame - typeStart) * 1.6);
  const displayedPrompt = promptText.slice(0, charsCount);
  const isTyping = charsCount < promptText.length;
  const cursorBlink = Math.floor(frame / 8) % 2 === 0;

  return (
    <AbsoluteFill
      style={{
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        color: "#F8FAFC",
        overflow: "hidden",
      }}
    >
      <ModernExplainerBackground accentColor={accentColor} dim={0.45} />

      <div
        style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          width: "100%",
          height: "100%",
          padding: "55px 95px",
          boxSizing: "border-box",
        }}
      >
        {/* Header */}
        <div style={{ opacity: hOpacity, transform: `translateY(${hY}px)`, marginBottom: 28 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "7px 18px",
              borderRadius: 20,
              background: "rgba(168, 85, 247, 0.16)",
              border: `1.5px solid ${accentColor}65`,
              color: accentColor,
              fontSize: 16,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginBottom: 12,
            }}
          >
            <span style={{ fontSize: 18 }}>💬</span>
            {badge}
          </div>

          <div style={{ fontSize: 48, fontWeight: 800, color: "#FFFFFF", letterSpacing: "-0.02em", lineHeight: 1.2 }}>
            {title}
          </div>
        </div>

        {/* Mockup Chat Window */}
        <div
          style={{
            opacity: wOpacity,
            transform: `scale(${wScale})`,
            flex: 1,
            display: "flex",
            flexDirection: "column",
            borderRadius: 22,
            background: "rgba(15, 23, 42, 0.85)",
            border: "1.5px solid rgba(255, 255, 255, 0.15)",
            boxShadow: `0 24px 60px rgba(0,0,0,0.55), 0 0 35px ${accentColor}22`,
            backdropFilter: "blur(20px)",
            overflow: "hidden",
          }}
        >
          {/* Window Chrome Titlebar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "16px 26px",
              background: "rgba(30, 41, 59, 0.75)",
              borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#EF4444" }} />
              <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#F59E0B" }} />
              <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#10B981" }} />
            </div>
            <div style={{ fontSize: 16, color: "#E2E8F0", fontWeight: 700, fontFamily: "monospace", letterSpacing: "0.02em" }}>
              {systemTag}
            </div>
            <div style={{ width: 44 }} />
          </div>

          {/* Chat Content Body */}
          <div style={{ flex: 1, padding: 32, display: "flex", flexDirection: "column", gap: 24, overflow: "hidden" }}>
            {/* User Message Bubble */}
            <div
              style={{
                alignSelf: "flex-end",
                maxWidth: "88%",
                background: "linear-gradient(135deg, rgba(168, 85, 247, 0.28) 0%, rgba(126, 34, 206, 0.42) 100%)",
                border: "1.5px solid rgba(168, 85, 247, 0.55)",
                padding: "20px 28px",
                borderRadius: "20px 20px 4px 20px",
                boxShadow: "0 6px 20px rgba(0,0,0,0.3)",
              }}
            >
              <div style={{ fontSize: 15, color: "#E9D5FF", fontWeight: 800, marginBottom: 6, letterSpacing: "0.05em" }}>
                👤 USER PROMPT
              </div>
              <div style={{ fontSize: promptText.length < 80 ? 24 : 21, color: "#FFFFFF", lineHeight: 1.55, fontWeight: 500 }}>
                {displayedPrompt}
                {isTyping && cursorBlink && (
                  <span style={{ color: accentColor, fontWeight: 800 }}>▎</span>
                )}
              </div>
            </div>

            {/* AI Assistant Response Block */}
            {frame > 35 && (
              <div
                style={{
                  alignSelf: "flex-start",
                  width: "100%",
                  display: "flex",
                  flexDirection: "column",
                  gap: 16,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 2 }}>
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 8,
                      background: accentColor,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 16,
                      fontWeight: 800,
                      color: "#fff",
                      boxShadow: `0 0 15px ${accentColor}80`,
                    }}
                  >
                    ✦
                  </div>
                  <span style={{ fontSize: 22, color: "#F8FAFC", fontWeight: 700 }}>
                    {responseTitle}
                  </span>
                </div>

                {/* Staggered Response Items */}
                <div style={{ display: "grid", gridTemplateColumns: `repeat(${responseItems.length}, 1fr)`, gap: 20 }}>
                  {responseItems.map((item, idx) => {
                    const itemDelay = 42 + idx * 8;
                    const iSpring = spring({
                      frame: Math.max(0, frame - itemDelay),
                      fps,
                      config: { mass: 0.5, damping: 14, stiffness: 120 },
                    });
                    const iOpacity = interpolate(iSpring, [0, 1], [0, 1]);
                    const iY = interpolate(iSpring, [0, 1], [25, 0]);

                    const detailFontSize = responseItems.length <= 2 ? 19 : 17;

                    return (
                      <div
                        key={idx}
                        style={{
                          opacity: iOpacity,
                          transform: `translateY(${iY}px)`,
                          padding: 24,
                          borderRadius: 16,
                          background: "rgba(30, 41, 59, 0.75)",
                          border: "1.5px solid rgba(255, 255, 255, 0.12)",
                          boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
                          display: "flex",
                          flexDirection: "column",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                          <span style={{ fontSize: 22, fontWeight: 700, color: "#FFFFFF" }}>
                            {item.title}
                          </span>
                          {item.tag && (
                            <span
                              style={{
                                fontSize: 13,
                                fontWeight: 800,
                                padding: "4px 10px",
                                borderRadius: 8,
                                background: "rgba(168, 85, 247, 0.25)",
                                color: "#E9D5FF",
                                border: "1px solid rgba(168, 85, 247, 0.4)",
                              }}
                            >
                              {item.tag}
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: detailFontSize, color: "#E2E8F0", lineHeight: 1.55, fontWeight: 500 }}>
                          {item.detail}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
