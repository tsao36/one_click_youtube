import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Parses numeric and text components from a display string.
 * Examples:
 *   "73.6 公噸" -> { prefix: "", num: 73.6, decimals: 1, suffix: " 公噸" }
 *   "$1.4 Trillion" -> { prefix: "$", num: 1.4, decimals: 1, suffix: " Trillion" }
 *   "108 輛" -> { prefix: "", num: 108, decimals: 0, suffix: " 輛" }
 *   "+24.8%" -> { prefix: "+", num: 24.8, decimals: 1, suffix: "%" }
 *   "約 20 億美元" -> { prefix: "約 ", num: 20, decimals: 0, suffix: " 億美元" }
 */
export function parseMetricNumber(raw: string | number): {
  prefix: string;
  num: number | null;
  decimals: number;
  suffix: string;
} {
  const str = String(raw || "").trim();
  if (!str) {
    return { prefix: "", num: null, decimals: 0, suffix: "" };
  }

  // Regex to extract prefix, first continuous number (int or float), and suffix
  const match = str.match(/^([^\d\-+.]*?)([-+]?\d+(?:\.\d+)?)(.*)$/);
  if (!match) {
    return { prefix: "", num: null, decimals: 0, suffix: str };
  }

  const prefix = match[1] || "";
  const numVal = parseFloat(match[2]);
  const suffix = match[3] || "";

  // Count decimal places
  const decParts = match[2].split(".");
  const decimals = decParts.length > 1 ? decParts[1].length : 0;

  return {
    prefix,
    num: isNaN(numVal) ? null : numVal,
    decimals,
    suffix,
  };
}

/**
 * Animated number hook that smoothly rolls from 0 to target value.
 * Includes completion punch scale effect when target is reached.
 */
export function useCountUp(
  target: string | number,
  options: {
    startFrame?: number;
    duration?: number;
    fps?: number;
    startFrom?: number;
  } = {}
) {
  const frame = useCurrentFrame();
  const config = useVideoConfig();
  const fps = options.fps || config.fps || 30;
  const startFrame = options.startFrame ?? 8;
  const duration = options.duration ?? 35;
  const parsed = parseMetricNumber(target);

  if (parsed.num === null) {
    return {
      display: String(target),
      progress: 1,
      isFinished: true,
      punchScale: 1,
    };
  }

  const progress = interpolate(
    frame,
    [startFrame, startFrame + duration],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  // Smooth ease-out cubic
  const easeProgress = 1 - Math.pow(1 - progress, 3);
  const startVal = options.startFrom ?? 0;
  const currentNum = startVal + (parsed.num - startVal) * easeProgress;
  const formattedNum = currentNum.toFixed(parsed.decimals);

  // Micro-punch scale when hitting 100%
  const finishFrame = startFrame + duration;
  const punchSpring = spring({
    frame: frame - finishFrame,
    fps,
    config: { damping: 10, stiffness: 200 },
  });
  const punchScale =
    frame >= finishFrame
      ? interpolate(punchSpring, [0, 0.4, 1], [1, 1.08, 1])
      : 1;

  return {
    display: `${parsed.prefix}${formattedNum}${parsed.suffix}`,
    progress,
    isFinished: progress >= 1,
    punchScale,
  };
}

/**
 * Subtle continuous ambient drift and breathing glow.
 * Ensures scenes never look like static frozen PowerPoint slides.
 */
export function useContinuousDrift(speed: number = 0.0003) {
  const frame = useCurrentFrame();
  const scale = 1 + frame * speed;
  const floatY = Math.sin(frame / 40) * 3;
  const glowPulse = 0.85 + Math.sin(frame / 25) * 0.15;
  return { scale, floatY, glowPulse };
}

/**
 * Periodic luminous shimmer/glint that sweeps across text or cards every few seconds.
 */
export const GlintSheen: React.FC<{
  color?: string;
  periodFrames?: number;
  width?: number | string;
  style?: React.CSSProperties;
}> = ({
  color = "rgba(255, 255, 255, 0.6)",
  periodFrames = 90,
  width = "100%",
  style,
}) => {
  const frame = useCurrentFrame();
  const loopFrame = frame % periodFrames;
  const glintProgress = interpolate(loopFrame, [15, 45], [-120, 220], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(
    loopFrame,
    [15, 25, 35, 45],
    [0, 0.8, 0.8, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  if (loopFrame < 15 || loopFrame > 45) return null;

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width,
        height: "100%",
        overflow: "hidden",
        pointerEvents: "none",
        zIndex: 5,
        ...style,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: `${glintProgress}%`,
          width: "35%",
          height: "100%",
          background: `linear-gradient(90deg, transparent 0%, ${color} 50%, transparent 100%)`,
          transform: "skewX(-25deg)",
          opacity,
          filter: "blur(4px)",
        }}
      />
    </div>
  );
};

/**
 * Animated pulsating beacon dot with expanding radar shockwave rings.
 */
export const RadarBeacon: React.FC<{
  color?: string;
  size?: number;
  label?: string;
}> = ({ color = "#38BDF8", size = 10, label }) => {
  const frame = useCurrentFrame();
  const ring1 = (frame % 40) / 40;
  const ring2 = ((frame + 20) % 40) / 40;

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        position: "relative",
      }}
    >
      <div
        style={{
          position: "relative",
          width: size,
          height: size,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* Core Dot */}
        <div
          style={{
            width: size,
            height: size,
            borderRadius: "50%",
            backgroundColor: color,
            boxShadow: `0 0 10px ${color}`,
            zIndex: 2,
          }}
        />
        {/* Radar Ring 1 */}
        <div
          style={{
            position: "absolute",
            width: size * (1 + ring1 * 2.8),
            height: size * (1 + ring1 * 2.8),
            borderRadius: "50%",
            border: `1.5px solid ${color}`,
            opacity: 1 - ring1,
            pointerEvents: "none",
          }}
        />
        {/* Radar Ring 2 */}
        <div
          style={{
            position: "absolute",
            width: size * (1 + ring2 * 2.8),
            height: size * (1 + ring2 * 2.8),
            borderRadius: "50%",
            border: `1.5px solid ${color}`,
            opacity: 1 - ring2,
            pointerEvents: "none",
          }}
        />
      </div>
      {label && <span>{label}</span>}
    </div>
  );
};

/**
 * Animated underline / accent bar with a travelling leading spark.
 */
export const DynamicAccentBar: React.FC<{
  color?: string;
  maxWidth?: number;
  startFrame?: number;
  duration?: number;
  height?: number;
  style?: React.CSSProperties;
}> = ({
  color = "#38BDF8",
  maxWidth = 180,
  startFrame = 12,
  duration = 28,
  height = 4,
  style,
}) => {
  const frame = useCurrentFrame();
  const width = interpolate(
    frame,
    [startFrame, startFrame + duration],
    [0, maxWidth],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  const isExpanding = frame >= startFrame && frame <= startFrame + duration;
  const glowHeadOpacity = isExpanding ? 1 : 0;

  return (
    <div
      style={{
        position: "relative",
        height,
        width: `${width}px`,
        backgroundColor: color,
        borderRadius: height / 2,
        boxShadow: `0 0 12px ${color}88`,
        marginTop: 18,
        ...style,
      }}
    >
      {/* Spark head during draw */}
      {width > 2 && (
        <div
          style={{
            position: "absolute",
            right: -3,
            top: (height - 10) / 2,
            width: 10,
            height: 10,
            borderRadius: "50%",
            backgroundColor: "#FFFFFF",
            boxShadow: `0 0 14px 4px ${color}, 0 0 6px #FFFFFF`,
            opacity: glowHeadOpacity,
            transition: "opacity 0.2s ease-out",
          }}
        />
      )}
    </div>
  );
};

/**
 * Cinematic drifting particles to bring any dark background alive.
 */
export const AmbientParticles: React.FC<{ count?: number; color?: string }> = ({
  count = 16,
  color = "rgba(255, 255, 255, 0.25)",
}) => {
  const frame = useCurrentFrame();

  const particles = React.useMemo(() => {
    return Array.from({ length: count }).map((_, i) => ({
      id: i,
      x: ((i * 37) % 95) + 2.5,
      y: ((i * 53) % 90) + 5,
      size: ((i * 13) % 3) + 1.5,
      speed: 0.2 + ((i * 7) % 5) * 0.08,
      offset: (i * 29) % 100,
    }));
  }, [count]);

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        overflow: "hidden",
        zIndex: 2,
      }}
    >
      {particles.map((p) => {
        const driftY = (frame * p.speed + p.offset) % 110;
        const driftX = Math.sin((frame + p.offset) / 30) * 12;
        const opacity = interpolate(
          driftY,
          [0, 15, 85, 105],
          [0, 0.6, 0.6, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        return (
          <div
            key={p.id}
            style={{
              position: "absolute",
              left: `calc(${p.x}% + ${driftX}px)`,
              top: `${100 - driftY}%`,
              width: p.size,
              height: p.size,
              borderRadius: "50%",
              backgroundColor: color,
              opacity,
              filter: "blur(0.5px)",
              boxShadow: `0 0 ${p.size * 2}px ${color}`,
            }}
          />
        );
      })}
    </div>
  );
};
