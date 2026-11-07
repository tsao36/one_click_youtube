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
              gap: 8,
              padding: "5px 12px",
              borderRadius: 16,
              background: "rgba(168, 85, 247, 0.15)",
              border: `1px solid ${accentColor}60`,
              color: accentColor,
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginBottom: 10,
            }}
          >
            <span>💬</span>
            {badge}
          </div>

          <div style={{ fontSize: 42, fontWeight: 800, color: "#FFFFFF", letterSpacing: "-0.02em" }}>
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
            borderRadius: 20,
            background: "rgba(15, 23, 42, 0.75)",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            boxShadow: `0 20px 50px rgba(0,0,0,0.5), 0 0 30px ${accentColor}18`,
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
              padding: "14px 22px",
              background: "rgba(30, 41, 59, 0.6)",
              borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#EF4444" }} />
              <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#F59E0B" }} />
              <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#10B981" }} />
            </div>
            <div style={{ fontSize: 13, color: "#CBD5E1", fontWeight: 600, fontFamily: "monospace" }}>
              {systemTag}
            </div>
            <div style={{ width: 44 }} />
          </div>

          {/* Chat Content Body */}
          <div style={{ flex: 1, padding: 28, display: "flex", flexDirection: "column", gap: 20, overflow: "hidden" }}>
            {/* User Message Bubble */}
            <div
              style={{
                alignSelf: "flex-end",
                maxWidth: "85%",
                background: "linear-gradient(135deg, rgba(168, 85, 247, 0.25) 0%, rgba(126, 34, 206, 0.35) 100%)",
                border: "1px solid rgba(168, 85, 247, 0.4)",
                padding: "16px 22px",
                borderRadius: "18px 18px 4px 18px",
                boxShadow: "0 4px 16px rgba(0,0,0,0.25)",
              }}
            >
              <div style={{ fontSize: 12, color: "#D8B4FE", fontWeight: 700, marginBottom: 4 }}>
                👤 USER PROMPT
              </div>
              <div style={{ fontSize: 16, color: "#F8FAFC", lineHeight: 1.5, fontFamily: "monospace" }}>
                {displayedPrompt}
                {isTyping && cursorBlink && (
                  <span style={{ color: accentColor, fontWeight: 700 }}>▎</span>
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
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                  <div
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: 6,
                      background: accentColor,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 12,
                      fontWeight: 800,
                      color: "#fff",
                    }}
                  >
                    ✦
                  </div>
                  <span style={{ fontSize: 14, color: "#E2E8F0", fontWeight: 700 }}>
                    {responseTitle}
                  </span>
                </div>

                {/* Staggered Response Items */}
                <div style={{ display: "grid", gridTemplateColumns: `repeat(${responseItems.length}, 1fr)`, gap: 16 }}>
                  {responseItems.map((item, idx) => {
                    const itemDelay = 42 + idx * 8;
                    const iSpring = spring({
                      frame: Math.max(0, frame - itemDelay),
                      fps,
                      config: { mass: 0.5, damping: 14, stiffness: 120 },
                    });
                    const iOpacity = interpolate(iSpring, [0, 1], [0, 1]);
                    const iY = interpolate(iSpring, [0, 1], [25, 0]);

                    return (
                      <div
                        key={idx}
                        style={{
                          opacity: iOpacity,
                          transform: `translateY(${iY}px)`,
                          padding: 18,
                          borderRadius: 14,
                          background: "rgba(30, 41, 59, 0.65)",
                          border: "1px solid rgba(255, 255, 255, 0.08)",
                          display: "flex",
                          flexDirection: "column",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                          <span style={{ fontSize: 15, fontWeight: 700, color: "#FFFFFF" }}>
                            {item.title}
                          </span>
                          {item.tag && (
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 800,
                                padding: "2px 6px",
                                borderRadius: 6,
                                background: "rgba(168, 85, 247, 0.2)",
                                color: "#D8B4FE",
                              }}
                            >
                              {item.tag}
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: 13.5, color: "#CBD5E1", lineHeight: 1.5 }}>
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
