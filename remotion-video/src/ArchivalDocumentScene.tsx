import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ArchivalBackground } from "./ArchivalBackground";
import { ArchivalDocumentSceneProps } from "./types";

export const ArchivalDocumentScene: React.FC<ArchivalDocumentSceneProps> = ({
  archiveId = "CABINET ARCHIVE 1945-TS-089",
  docDate = "1945 年 8 月 15 日",
  stampText = "DECLASSIFIED 絕密解密",
  title = "二次大戰終戰內閣極密備忘錄",
  documentExcerpt = "「此項抉擇並非出於單一戰術考量，而是考量帝國全體存續之終局底線。所有軍事指令即刻停止。」",
  highlightPhrase = "帝國全體存續之終局底線",
  significance = "這份解密電報證實了戰後格局的核心決策並非戰場偶發，而是內閣內部經歷數月激烈辯論的最終共識。",
  source = "來源：國立公文書館 · 昭和天皇終戰詔書起草案卷",
  accentColor = "#DC2626",
  bgSrc = "",
  dim = 0.2,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Paper entrance
  const paperEntrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
  });

  // Stamp slams down at frame 25
  const stampSpring = spring({
    frame: frame - 25,
    fps,
    config: { damping: 10, mass: 0.5, stiffness: 180 },
  });

  // Highlight marker animation
  const markerProgress = interpolate(frame, [38, 70], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <ArchivalBackground bgSrc={bgSrc} dim={dim} archiveId={archiveId}>
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100%",
          padding: "20px 80px",
          boxSizing: "border-box",
        }}
      >
        {/* Main Parchment Document Sheet */}
        <div
          style={{
            position: "relative",
            width: "100%",
            maxWidth: 1080,
            backgroundColor: "#FAF7EF",
            borderRadius: 6,
            padding: "40px 50px",
            boxShadow: "0 20px 60px rgba(60, 40, 20, 0.35), 0 2px 10px rgba(0,0,0,0.15)",
            border: "1.5px solid #D6C3A5",
            transform: `scale(${paperEntrance}) rotate(-0.5deg)`,
            opacity: paperEntrance,
            boxSizing: "border-box",
          }}
        >
          {/* Top Folder Tab & Date */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              borderBottom: "2px solid #8C6239",
              paddingBottom: 14,
              marginBottom: 20,
            }}
          >
            <div>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 900,
                  letterSpacing: 2,
                  color: "#8C6239",
                  fontFamily: "monospace",
                }}
              >
                ORIGINAL ARCHIVAL DISPATCH
              </span>
              <div style={{ fontSize: 26, fontWeight: 900, color: "#2B1810", marginTop: 4 }}>
                {title}
              </div>
            </div>

            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 13, fontWeight: 800, color: "#8C6239", fontFamily: "monospace" }}>
                DATE RECORDED
              </div>
              <div style={{ fontSize: 18, fontWeight: 800, color: "#2B1810", fontFamily: "monospace" }}>
                {docDate}
              </div>
            </div>
          </div>

          {/* Document Main Excerpt with Vintage Red Marker Stroke */}
          <div
            style={{
              position: "relative",
              fontSize: 24,
              lineHeight: 1.8,
              color: "#332211",
              fontFamily: "'Noto Serif TC', 'GenYoMin2 TW', serif",
              margin: "24px 0",
              padding: "16px 20px",
              backgroundColor: "rgba(230, 215, 190, 0.3)",
              borderLeft: "4px solid #8C6239",
              borderRadius: 4,
            }}
          >
            {documentExcerpt}

            {/* Dynamic Red Marker underline beneath the highlighted phrase */}
            <div
              style={{
                position: "relative",
                width: `${markerProgress}%`,
                height: 4,
                backgroundColor: accentColor,
                marginTop: 10,
                borderRadius: 2,
                opacity: 0.85,
              }}
            />
          </div>

          {/* Historical Significance Callout */}
          {significance && (
            <div
              style={{
                marginTop: 20,
                fontSize: 15,
                lineHeight: 1.6,
                color: "#5C4033",
                fontFamily: "sans-serif",
                fontWeight: 600,
                backgroundColor: "rgba(220, 38, 38, 0.05)",
                padding: "12px 18px",
                borderRadius: 6,
                border: "1px dashed rgba(220, 38, 38, 0.3)",
              }}
            >
              <b>📜 歷史解密意義：</b> {significance}
            </div>
          )}

          {/* Footnote */}
          {source && (
            <div
              style={{
                marginTop: 16,
                fontSize: 12,
                color: "#8C6239",
                fontFamily: "sans-serif",
                textAlign: "right",
              }}
            >
              {source}
            </div>
          )}

          {/* Red Rubber Stamp (Slam Entrance) */}
          <div
            style={{
              position: "absolute",
              top: 30,
              right: 60,
              border: `4px double ${accentColor}`,
              borderRadius: 8,
              padding: "6px 20px",
              color: accentColor,
              fontSize: 24,
              fontWeight: 900,
              letterSpacing: 3,
              fontFamily: "monospace",
              textTransform: "uppercase",
              transform: `scale(${stampSpring}) rotate(-14deg)`,
              opacity: stampSpring,
              boxShadow: `0 0 15px rgba(220, 38, 38, 0.25)`,
              backgroundColor: "rgba(250, 240, 235, 0.85)",
              pointerEvents: "none",
            }}
          >
            {stampText}
          </div>
        </div>
      </div>
    </ArchivalBackground>
  );
};
