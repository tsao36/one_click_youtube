import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { EditorialExplainerSceneProps, EditorialExplainerItem } from "./types";
import {
  editorialExplainerTheme as theme,
  editorialExplainerTiming as timing,
} from "./editorialExplainerTemplate";

const statusColor = (status?: EditorialExplainerItem["status"], accent: string = theme.question) => {
  if (status === "positive") return theme.positive;
  if (status === "negative") return theme.negative;
  if (status === "active") return accent;
  return theme.muted;
};

const ItemCard: React.FC<{
  item: EditorialExplainerItem;
  index: number;
  accent: string;
  compact?: boolean;
}> = ({ item, index, accent, compact = false }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({
    frame: frame - timing.buildStartFrame - index * timing.itemStaggerFrames,
    fps,
    config: { damping: 15, stiffness: 120, mass: 0.8 },
  });
  const color = statusColor(item.status, accent);

  return (
    <div
      style={{
        position: "relative",
        flex: 1,
        minWidth: 0,
        padding: compact ? "18px 20px" : "24px 26px",
        borderRadius: 18,
        border: `1px solid ${item.status === "active" ? `${color}AA` : theme.line}`,
        background: theme.panelSoft,
        boxShadow: item.status === "active" ? `0 0 30px ${color}22` : "0 16px 36px rgba(0,0,0,.25)",
        opacity: progress,
        transform: `translateY(${interpolate(progress, [0, 1], [30, 0])}px) scale(${interpolate(progress, [0, 1], [0.96, 1])})`,
        overflow: "hidden",
      }}
    >
      <div style={{ width: 38, height: 4, borderRadius: 3, background: color, marginBottom: 16 }} />
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12 }}>
        <div style={{ color: theme.text, fontSize: compact ? 25 : 30, fontWeight: 850 }}>{item.label}</div>
        {item.value && <div style={{ color, fontSize: compact ? 26 : 34, fontWeight: 900 }}>{item.value}</div>}
      </div>
      {item.note && (
        <div style={{ color: theme.muted, fontSize: compact ? 18 : 21, lineHeight: 1.45, marginTop: 10 }}>
          {item.note}
        </div>
      )}
    </div>
  );
};

export const EditorialExplainerScene: React.FC<EditorialExplainerSceneProps> = ({
  sceneRole = "process",
  kicker = "EXPLAINER",
  title,
  statement = "",
  metric = "",
  metricLabel = "",
  items = [],
  source = "",
  mediaSrc = "",
  accentColor = theme.question,
  positiveColor = theme.positive,
  negativeColor = theme.negative,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 16, stiffness: 110 } });
  const emphasis = spring({
    frame: frame - timing.emphasisStartFrame,
    fps,
    config: { damping: 13, stiffness: 125 },
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - timing.exitFrames, durationInFrames - 1],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const safeItems = items.slice(0, 6);

  const header = (
    <>
      <div style={{ color: accentColor, fontSize: 18, fontWeight: 900, letterSpacing: 3.5 }}>{kicker}</div>
      <h1
        style={{
          color: theme.text,
          fontSize: 54,
          lineHeight: 1.18,
          letterSpacing: -1.2,
          maxWidth: 1420,
          margin: "12px 0 0",
          opacity: enter,
          transform: `translateY(${interpolate(enter, [0, 1], [24, 0])}px)`,
        }}
      >
        {title}
      </h1>
    </>
  );

  const renderRole = () => {
    if (sceneRole === "hook") {
      return (
        <div style={{ width: 1320, marginTop: 110 }}>
          <div style={{ color: accentColor, fontSize: 24, fontWeight: 900, letterSpacing: 4 }}>{kicker}</div>
          <div style={{ color: theme.text, fontSize: 76, fontWeight: 950, lineHeight: 1.15, marginTop: 22 }}>{title}</div>
          {statement && (
            <div
              style={{
                display: "inline-block",
                color: theme.text,
                fontSize: 34,
                fontWeight: 750,
                marginTop: 34,
                paddingBottom: 10,
                borderBottom: `6px solid ${accentColor}`,
                opacity: emphasis,
                transform: `translateX(${interpolate(emphasis, [0, 1], [-24, 0])}px)`,
              }}
            >
              {statement}
            </div>
          )}
        </div>
      );
    }

    if (sceneRole === "identity") {
      const identity = safeItems[0];
      return (
        <div style={{ display: "grid", gridTemplateColumns: "560px 1fr", gap: 70, alignItems: "center", marginTop: 82 }}>
          <div style={{ height: 420, borderRadius: 24, overflow: "hidden", border: `1px solid ${theme.line}`, background: theme.panel }}>
            {mediaSrc ? (
              <Img src={staticFile(mediaSrc)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            ) : (
              <div style={{ height: "100%", display: "grid", placeItems: "center", color: theme.identity, fontSize: 92, fontWeight: 950 }}>
                {(identity?.label || title).slice(0, 1)}
              </div>
            )}
          </div>
          <div>
            {header}
            <div style={{ color: theme.identity, fontSize: 38, fontWeight: 900, marginTop: 26 }}>{identity?.label}</div>
            <div style={{ color: theme.muted, fontSize: 26, marginTop: 8 }}>{identity?.value}</div>
            {statement && <div style={{ color: theme.text, fontSize: 25, lineHeight: 1.55, marginTop: 28 }}>{statement}</div>}
          </div>
        </div>
      );
    }

    if (sceneRole === "metric") {
      return (
        <div style={{ marginTop: 105 }}>
          {header}
          <div style={{ display: "flex", alignItems: "baseline", gap: 22, marginTop: 46 }}>
            <div style={{ color: accentColor, fontSize: 150, fontWeight: 950, letterSpacing: -5 }}>{metric}</div>
            <div style={{ color: theme.text, fontSize: 38, fontWeight: 800 }}>{metricLabel}</div>
          </div>
          <div style={{ display: "flex", gap: 14, marginTop: 36, maxWidth: 1260 }}>
            {safeItems.map((item, index) => <ItemCard key={`${item.label}-${index}`} item={item} index={index} accent={accentColor} compact />)}
          </div>
        </div>
      );
    }

    if (sceneRole === "comparison") {
      return (
        <div style={{ marginTop: 66 }}>
          {header}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 30, marginTop: 48 }}>
            {safeItems.slice(0, 2).map((item, index) => (
              <ItemCard
                key={`${item.label}-${index}`}
                item={{ ...item, status: item.status || (index === 0 ? "negative" : "positive") }}
                index={index}
                accent={index === 0 ? negativeColor : positiveColor}
              />
            ))}
          </div>
          {statement && <div style={{ color: theme.text, fontSize: 30, fontWeight: 800, textAlign: "center", marginTop: 38 }}>{statement}</div>}
        </div>
      );
    }

    if (sceneRole === "constraint") {
      const center = safeItems[0];
      const satellites = safeItems.slice(1, 6);
      const positions = [
        { left: 30, top: 220 },
        { left: 1270, top: 220 },
        { left: 180, top: 500 },
        { left: 1120, top: 500 },
        { left: 650, top: 570 },
      ];
      return (
        <div style={{ position: "relative", height: 700, marginTop: 36 }}>
          {header}
          <svg width="100%" height="700" style={{ position: "absolute", top: 0, left: 0, overflow: "visible" }}>
            {satellites.map((_, index) => {
              const position = positions[index];
              return <line key={index} x1="845" y1="400" x2={position.left + 125} y2={position.top + 65} stroke={theme.line} strokeWidth="3" strokeDasharray="10 10" />;
            })}
          </svg>
          <div style={{ position: "absolute", left: 675, top: 335, width: 340 }}>
            <ItemCard item={{ ...(center || { label: "核心系統" }), status: "active" }} index={0} accent={accentColor} compact />
          </div>
          {satellites.map((item, index) => {
            const { left, top } = positions[index];
            return (
              <div key={`${item.label}-${index}`} style={{ position: "absolute", left, top, width: 250 }}>
                <ItemCard item={item} index={index + 1} accent={accentColor} compact />
              </div>
            );
          })}
        </div>
      );
    }

    if (sceneRole === "timeline") {
      return (
        <div style={{ marginTop: 72 }}>
          {header}
          <div style={{ position: "relative", marginTop: 110, display: "flex", gap: 18, alignItems: "stretch" }}>
            <div style={{ position: "absolute", left: 20, right: 20, top: 25, height: 4, background: theme.line }} />
            {safeItems.map((item, index) => (
              <div key={`${item.label}-${index}`} style={{ flex: 1, position: "relative", paddingTop: 62 }}>
                <div style={{ position: "absolute", top: 10, left: 22, width: 34, height: 34, borderRadius: "50%", background: statusColor(item.status, accentColor), border: `7px solid ${theme.canvas}` }} />
                <ItemCard item={item} index={index} accent={accentColor} compact />
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (sceneRole === "evidence") {
      return (
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr .8fr", gap: 54, alignItems: "center", marginTop: 54 }}>
          <div style={{ background: "#F3F0E8", color: "#20242A", borderRadius: 18, padding: "52px 58px", minHeight: 510, boxShadow: "0 28px 70px rgba(0,0,0,.45)", transform: `rotate(${interpolate(enter, [0, 1], [-2, -0.4])}deg)` }}>
            <div style={{ color: "#5D6470", fontSize: 18, fontWeight: 800, letterSpacing: 2 }}>{kicker}</div>
            <div style={{ fontSize: 34, fontWeight: 900, lineHeight: 1.3, marginTop: 22 }}>{title}</div>
            <div style={{ fontSize: 25, lineHeight: 1.7, marginTop: 36 }}>{statement}</div>
            <div style={{ height: 18, background: `${accentColor}88`, width: `${interpolate(emphasis, [0, 1], [0, 94])}%`, marginTop: -28 }} />
          </div>
          <div>
            <div style={{ color: accentColor, fontSize: 22, fontWeight: 900 }}>WHY THIS MATTERS</div>
            <div style={{ display: "grid", gap: 18, marginTop: 26 }}>
              {safeItems.map((item, index) => <ItemCard key={`${item.label}-${index}`} item={item} index={index} accent={accentColor} compact />)}
            </div>
          </div>
        </div>
      );
    }

    return (
      <div style={{ marginTop: 70 }}>
        {header}
        <div style={{ display: "grid", gridTemplateColumns: sceneRole === "synthesis" ? "repeat(3, 1fr)" : `repeat(${Math.min(4, Math.max(1, safeItems.length))}, 1fr)`, gap: 22, marginTop: 50 }}>
          {safeItems.map((item, index) => <ItemCard key={`${item.label}-${index}`} item={item} index={index} accent={accentColor} />)}
        </div>
        {statement && (
          <div style={{ color: theme.text, fontSize: 32, lineHeight: 1.45, fontWeight: 850, textAlign: "center", margin: "42px auto 0", maxWidth: 1240, opacity: emphasis }}>
            {statement}
          </div>
        )}
      </div>
    );
  };

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at 78% 22%, ${accentColor}16, transparent 32%), linear-gradient(135deg, #0B1017, ${theme.canvas})`,
        color: theme.text,
        fontFamily: "Inter, 'Noto Sans TC', 'Microsoft JhengHei', system-ui, sans-serif",
        overflow: "hidden",
        opacity: fadeOut,
      }}
    >
      <AbsoluteFill style={{ opacity: 0.16, backgroundImage: "repeating-linear-gradient(135deg, transparent 0 52px, rgba(255,255,255,.035) 52px 54px)" }} />
      <div style={{ position: "absolute", inset: "82px 112px 72px" }}>{renderRole()}</div>
      {source && (
        <div style={{ position: "absolute", left: 112, bottom: 34, color: "rgba(255,255,255,.52)", fontSize: 16, letterSpacing: 0.4 }}>
          {source}
        </div>
      )}
      <div style={{ position: "absolute", right: 112, bottom: 30, color: accentColor, fontSize: 14, fontWeight: 900, letterSpacing: 2 }}>
        {sceneRole.toUpperCase()}
      </div>
    </AbsoluteFill>
  );
};

