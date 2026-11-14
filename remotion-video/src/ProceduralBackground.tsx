import React from "react";
import {
  AbsoluteFill,
  Img,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { AmbientParticles } from "./animations";

export type ProceduralBgVariant =
  | "grid-pulse"
  | "bokeh"
  | "geometric"
  | "liquid"
  | "gradient-shift";

export interface ProceduralBackgroundProps {
  variant?: ProceduralBgVariant;
  accentColor?: string;
  bgSrc?: string;
  dim?: number;
  children?: React.ReactNode;
}

function hexToRgbTuple(hex: string): [number, number, number] {
  const clean = (hex || "").trim().replace(/^#/, "");
  if (clean.length === 3) {
    const r = parseInt(clean[0] + clean[0], 16);
    const g = parseInt(clean[1] + clean[1], 16);
    const b = parseInt(clean[2] + clean[2], 16);
    if (!Number.isNaN(r) && !Number.isNaN(g) && !Number.isNaN(b)) {
      return [r, g, b];
    }
  } else if (clean.length === 6) {
    const r = parseInt(clean.slice(0, 2), 16);
    const g = parseInt(clean.slice(2, 4), 16);
    const b = parseInt(clean.slice(4, 6), 16);
    if (!Number.isNaN(r) && !Number.isNaN(g) && !Number.isNaN(b)) {
      return [r, g, b];
    }
  }
  return [56, 189, 248];
}

const GridPulseLayer: React.FC<{ accentColor: string }> = ({ accentColor }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();

  const cols = 14;
  const rows = 8;
  const dotSize = 11;
  const spacingX = width / (cols + 1);
  const spacingY = height / (rows + 1);
  const centerCol = (cols - 1) / 2;
  const centerRow = (rows - 1) / 2;
  const t = frame / fps;

  const dots: Array<{
    x: number;
    y: number;
    opacity: number;
    scale: number;
    key: number;
  }> = [];

  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const dx = col - centerCol;
      const dy = row - centerRow;
      const distance = Math.sqrt(dx * dx + dy * dy);
      const wave = Math.sin(t * 3 - distance * 0.75) * 0.5 + 0.5;
      dots.push({
        x: spacingX * (col + 1),
        y: spacingY * (row + 1),
        opacity: 0.08 + wave * 0.34,
        scale: 0.45 + wave * 0.65,
        key: row * cols + col,
      });
    }
  }

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse at 50% 45%, #0F172A 0%, #090D16 70%, #05070D 100%)",
        pointerEvents: "none",
      }}
    >
      {dots.map((dot) => (
        <div
          key={dot.key}
          style={{
            position: "absolute",
            left: dot.x,
            top: dot.y,
            width: dotSize,
            height: dotSize,
            borderRadius: "50%",
            backgroundColor: accentColor,
            opacity: dot.opacity,
            transform: `translate(-50%, -50%) scale(${dot.scale})`,
            boxShadow: `0 0 12px ${accentColor}55`,
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

const BokehCirclesLayer: React.FC<{ accentColor: string }> = ({ accentColor }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const t = frame / fps;
  const accentRgb = hexToRgbTuple(accentColor);
  const colorOptions: Array<[number, number, number]> = [
    accentRgb,
    [139, 92, 246],
    [20, 184, 166],
  ];

  const circles = Array.from({ length: 16 }, (_, i) => {
    const baseX = ((i * 173 + 53) % 100) / 100;
    const baseY = ((i * 241 + 97) % 100) / 100;
    const driftX = Math.sin(t * 0.25 + i * 1.3) * 48;
    const driftY = Math.cos(t * 0.18 + i * 0.9) * 38;
    const baseSize = 110 + ((i * 53 + 17) % 190);
    const pulse = Math.sin(t * 0.45 + i * 0.7) * 0.18 + 1;
    const opacity = 0.1 + ((i * 19 + 7) % 18) / 100;
    const rgb = colorOptions[i % colorOptions.length];

    return {
      key: i,
      x: baseX * width + driftX,
      y: baseY * height + driftY,
      size: baseSize * pulse,
      opacity,
      rgb,
    };
  });

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(145deg, #090D16 0%, #111827 55%, #0B1120 100%)",
        pointerEvents: "none",
      }}
    >
      {circles.map((c) => (
        <div
          key={c.key}
          style={{
            position: "absolute",
            left: c.x,
            top: c.y,
            width: c.size,
            height: c.size,
            borderRadius: "50%",
            background: `radial-gradient(circle, rgba(${c.rgb[0]}, ${c.rgb[1]}, ${c.rgb[2]}, ${c.opacity + 0.12}) 0%, rgba(${c.rgb[0]}, ${c.rgb[1]}, ${c.rgb[2]}, 0) 72%)`,
            transform: "translate(-50%, -50%)",
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

const GeometricPatternsLayer: React.FC<{ accentColor: string }> = ({
  accentColor,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const patterns = Array.from({ length: 12 }, (_, i) => {
    const enter = spring({
      frame: Math.max(0, frame - i * 3),
      fps,
      from: 0,
      to: 1,
      config: { damping: 24, stiffness: 60 },
    });
    const rotation = enter * (30 + i * 12) + frame * (0.08 + i * 0.015);
    const scale = 0.35 + enter * (0.28 + i * 0.075);
    return { index: i, rotation, scale };
  });

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(45deg, #090D16 0%, #0F172A 50%, #1E293B 100%)",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(circle at 50% 50%, ${accentColor}1A 0%, transparent 65%)`,
        }}
      />
      {patterns.map(({ index, rotation, scale }) => (
        <div
          key={index}
          style={{
            position: "absolute",
            left: "50%",
            top: "50%",
            width: 1100,
            height: 1100,
            transform: `translate(-50%, -50%) rotate(${rotation}deg) scale(${scale})`,
            border: "1.5px solid rgba(255, 255, 255, 0.07)",
            borderRadius: `${Math.min(48, index * 4)}%`,
            boxShadow: index % 4 === 0 ? `inset 0 0 32px ${accentColor}10` : undefined,
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

const LiquidWaveLayer: React.FC<{ accentColor: string }> = ({ accentColor }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const gradId1 = React.useId();
  const gradId2 = React.useId();

  const numPoints = 48;
  const buildWavePath = (baseY: number, amp: number, speed: number, phase: number) => {
    const pts = Array.from({ length: numPoints + 1 }, (_, i) => {
      const x = (i / numPoints) * width;
      const y = baseY + Math.sin(frame / speed + i / 4.5 + phase) * amp;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return `M 0,${height} L ${pts.join(" L ")} L ${width},${height} Z`;
  };

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(180deg, #090D16 0%, #0F172A 100%)",
        pointerEvents: "none",
      }}
    >
      <svg width={width} height={height} style={{ position: "absolute", inset: 0 }}>
        <defs>
          <linearGradient id={gradId1} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#1E3A8A" stopOpacity="0.55" />
            <stop offset="100%" stopColor={accentColor} stopOpacity="0.45" />
          </linearGradient>
          <linearGradient id={gradId2} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={accentColor} stopOpacity="0.28" />
            <stop offset="100%" stopColor="#1E3A8A" stopOpacity="0.4" />
          </linearGradient>
        </defs>
        <path
          d={buildWavePath(height * 0.56, 56, 22, 0)}
          fill={`url(#${gradId1})`}
          style={{ filter: "blur(10px)" }}
        />
        <path
          d={buildWavePath(height * 0.66, 44, 17, 2.2)}
          fill={`url(#${gradId2})`}
          style={{ filter: "blur(10px)" }}
        />
      </svg>
    </AbsoluteFill>
  );
};

const GradientShiftLayer: React.FC<{ accentColor: string }> = ({ accentColor }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const phase1 = Math.sin(t * 0.35) * 0.5 + 0.5;
  const phase2 = Math.sin(t * 0.35 + 2) * 0.5 + 0.5;
  const phase3 = Math.sin(t * 0.35 + 4) * 0.5 + 0.5;

  const stops = [
    { r: 15, g: 23, b: 42 },
    { r: 22, g: 33, b: 62 },
    { r: 15, g: 52, b: 96 },
    { r: 15, g: 23, b: 42 },
  ];

  const mix = (phase: number) => {
    const idx = Math.min(2, Math.floor(phase * 2));
    const frac = phase * 2 - idx;
    const a = stops[idx];
    const b = stops[idx + 1];
    const lerp = (x: number, y: number) => Math.round(x + (y - x) * frac);
    return `rgb(${lerp(a.r, b.r)}, ${lerp(a.g, b.g)}, ${lerp(a.b, b.b)})`;
  };

  const angle = (frame * 0.5) % 360;

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(${angle}deg, ${mix(phase1)}, ${mix(phase2)}, ${mix(phase3)})`,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(circle at 75% 22%, ${accentColor}22 0%, transparent 45%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "radial-gradient(rgba(255, 255, 255, 0.07) 1.2px, transparent 1.2px)",
          backgroundSize: "32px 32px",
          opacity: 0.65,
        }}
      />
    </AbsoluteFill>
  );
};

export const ProceduralBackground: React.FC<ProceduralBackgroundProps> = ({
  variant = "grid-pulse",
  accentColor = "#38BDF8",
  bgSrc = "",
  dim = 0.5,
  children,
}) => {
  const frame = useCurrentFrame();
  const bgScale = 1 + frame * 0.0004;

  const renderVariant = () => {
    switch (variant) {
      case "bokeh":
        return <BokehCirclesLayer accentColor={accentColor} />;
      case "geometric":
        return <GeometricPatternsLayer accentColor={accentColor} />;
      case "liquid":
        return <LiquidWaveLayer accentColor={accentColor} />;
      case "gradient-shift":
        return <GradientShiftLayer accentColor={accentColor} />;
      case "grid-pulse":
      default:
        return <GridPulseLayer accentColor={accentColor} />;
    }
  };

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#090D16",
        color: "#F8FAFC",
        fontFamily:
          "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans TC', 'Microsoft JhengHei', sans-serif",
        overflow: "hidden",
      }}
    >
      <AbsoluteFill style={{ opacity: bgSrc ? 0.35 : 1 }}>
        {renderVariant()}
      </AbsoluteFill>

      {bgSrc && (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <Img
            src={staticFile(bgSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${bgScale})`,
            }}
          />
          <AbsoluteFill
            style={{
              background: `radial-gradient(ellipse at 50% 45%, rgba(9, 13, 22, ${Math.min(0.88, Math.max(0.2, dim * 0.7))}) 0%, rgba(5, 7, 13, ${Math.min(0.95, Math.max(0.45, dim + 0.15))}) 100%)`,
            }}
          />
        </AbsoluteFill>
      )}

      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 48%, rgba(4, 6, 12, 0.72) 100%)",
          pointerEvents: "none",
        }}
      />

      <AmbientParticles count={12} color="rgba(255, 255, 255, 0.16)" />

      <AbsoluteFill style={{ zIndex: 10 }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export interface RveSceneHeaderProps {
  badge?: string;
  title: string;
  subtitle?: string;
  accentColor?: string;
  rightSlot?: React.ReactNode;
}

export const RveSceneHeader: React.FC<RveSceneHeaderProps> = ({
  badge,
  title,
  subtitle,
  accentColor = "#38BDF8",
  rightSlot,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headerSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 120, mass: 0.7 },
  });

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: 32,
        opacity: headerSpring,
        transform: `translateY(${(1 - headerSpring) * -22}px)`,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        {badge && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "7px 18px",
              borderRadius: 999,
              backgroundColor: "rgba(15, 23, 42, 0.72)",
              border: `1.5px solid ${accentColor}66`,
              color: accentColor,
              fontSize: 17,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginBottom: 14,
              backdropFilter: "blur(10px)",
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                backgroundColor: accentColor,
                boxShadow: `0 0 10px ${accentColor}`,
              }}
            />
            <span>{badge}</span>
          </div>
        )}
        <h1
          style={{
            margin: 0,
            fontSize: 52,
            fontWeight: 850,
            lineHeight: 1.18,
            letterSpacing: "-0.02em",
            color: "#FFFFFF",
            textShadow: "0 4px 20px rgba(0, 0, 0, 0.65)",
          }}
        >
          {title}
        </h1>
        {subtitle && (
          <p
            style={{
              margin: "10px 0 0 0",
              fontSize: 24,
              fontWeight: 500,
              lineHeight: 1.4,
              color: "#94A3B8",
            }}
          >
            {subtitle}
          </p>
        )}
      </div>
      {rightSlot && <div style={{ flexShrink: 0 }}>{rightSlot}</div>}
    </div>
  );
};

export const RveSceneFooter: React.FC<{
  source?: string;
  accentColor?: string;
}> = ({ source, accentColor = "#38BDF8" }) => {
  if (!source) return null;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        fontSize: 17,
        color: "rgba(226, 232, 240, 0.65)",
        fontWeight: 500,
        marginTop: 18,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          backgroundColor: accentColor,
        }}
      />
      <span>{source}</span>
    </div>
  );
};
