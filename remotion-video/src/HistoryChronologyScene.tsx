import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ArchivalBackground } from "./ArchivalBackground";
import { HistoryChronologySceneProps } from "./types";

export const HistoryChronologyScene: React.FC<HistoryChronologySceneProps> = ({
  archiveId = "CHRONOLOGY DOSSIER / VOL. IV",
  era = "近代地緣秩序重構期",
  title = "推動戰後秩序成型的三大歷史轉折",
  events = [
    { year: "1939", title: "衝突全面爆發", detail: "既有國際聯盟機制崩解，大國全面進入總體戰動員體系" },
    { year: "1943", title: "開羅與德黑蘭峰會", detail: "三大盟國首度確立戰後領土處分與勢力劃分最高原則" },
    { year: "1945", title: "雅爾達協定與聯合國創立", detail: "安理會五常否決權體制成型，冷戰東西陣營分界線正式確立" },
  ],
  takeaway = "歷史的重大分水嶺從不是單一事件，而是數個關鍵決策連鎖反應的終局產物",
  accentColor = "#991B1B",
  bgSrc = "",
  dim = 0.2,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
  });

  return (
    <ArchivalBackground bgSrc={bgSrc} dim={dim} archiveId={archiveId}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          height: "100%",
          padding: "36px 80px",
          boxSizing: "border-box",
          justifyContent: "space-between",
          transform: `scale(${entrance})`,
          opacity: entrance,
        }}
      >
        {/* Header */}
        <div>
          <span
            style={{
              backgroundColor: "rgba(153, 27, 27, 0.12)",
              color: accentColor,
              border: `1.5px solid ${accentColor}`,
              borderRadius: 6,
              padding: "4px 14px",
              fontSize: 13,
              fontWeight: 800,
              letterSpacing: 1.5,
              fontFamily: "monospace",
            }}
          >
            {era}
          </span>
          <div style={{ fontSize: 32, fontWeight: 900, color: "#2B1810", marginTop: 8 }}>
            {title}
          </div>
        </div>

        {/* 3 Chronology Pillars */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 28, margin: "20px 0" }}>
          {events.map((ev, idx) => {
            const cardSpring = spring({
              frame: frame - idx * 6,
              fps,
              config: { damping: 14, stiffness: 85 },
            });

            return (
              <div
                key={idx}
                style={{
                  backgroundColor: "#FAF7EF",
                  border: "1.5px solid #D6C3A5",
                  borderRadius: 8,
                  padding: "24px 22px",
                  boxShadow: "0 10px 25px rgba(60, 40, 20, 0.2)",
                  transform: `translateY(${(1 - cardSpring) * 30}px)`,
                  opacity: cardSpring,
                  display: "flex",
                  flexDirection: "column",
                  position: "relative",
                }}
              >
                {/* Year Seal Badge */}
                {(() => {
                  const rawYear = String(ev.year || "").trim();
                  const stageMatch = rawYear.match(/^STAGE\s*(\d+)$/i);
                  if (stageMatch) {
                    return (
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          alignItems: "center",
                          justifyContent: "center",
                          width: 68,
                          height: 68,
                          borderRadius: "50%",
                          border: `2.5px solid ${accentColor}`,
                          color: accentColor,
                          marginBottom: 14,
                          backgroundColor: "rgba(255, 255, 255, 0.95)",
                          boxShadow: "0 4px 10px rgba(153, 27, 27, 0.2)",
                          boxSizing: "border-box",
                          lineHeight: 1,
                          flexShrink: 0,
                        }}
                      >
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 800,
                            letterSpacing: 1.2,
                            fontFamily: "sans-serif",
                            textTransform: "uppercase",
                            opacity: 0.85,
                            marginBottom: 2,
                            lineHeight: 1,
                          }}
                        >
                          STAGE
                        </span>
                        <span
                          style={{
                            fontSize: 22,
                            fontWeight: 900,
                            fontFamily: "monospace",
                            lineHeight: 1,
                          }}
                        >
                          {stageMatch[1]}
                        </span>
                      </div>
                    );
                  }
                  return (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: 68,
                        height: 68,
                        borderRadius: "50%",
                        border: `2.5px solid ${accentColor}`,
                        color: accentColor,
                        fontSize: rawYear.length > 4 ? 13 : 18,
                        fontWeight: 900,
                        fontFamily: "monospace",
                        marginBottom: 14,
                        backgroundColor: "rgba(255, 255, 255, 0.95)",
                        boxShadow: "0 4px 10px rgba(153, 27, 27, 0.2)",
                        boxSizing: "border-box",
                        lineHeight: 1,
                        flexShrink: 0,
                      }}
                    >
                      {rawYear}
                    </div>
                  );
                })()}

                <div style={{ fontSize: 20, fontWeight: 900, color: "#2B1810", marginBottom: 8 }}>
                  {ev.title}
                </div>

                <div style={{ fontSize: 14, lineHeight: 1.6, color: "#5C4033", fontWeight: 600 }}>
                  {ev.detail}
                </div>
              </div>
            );
          })}
        </div>

        {/* Bottom Takeaway */}
        {takeaway && (
          <div
            style={{
              borderTop: "1.5px dashed #8C6239",
              paddingTop: 12,
              fontSize: 14,
              fontWeight: 700,
              color: "#5C4033",
              textAlign: "center",
            }}
          >
            📜 {takeaway}
          </div>
        )}
      </div>
    </ArchivalBackground>
  );
};
