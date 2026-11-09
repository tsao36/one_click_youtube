import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { RadioEvent, WirelessDevice } from "./wirelessTypes";

interface RfTransmissionPathProps {
  event: RadioEvent;
  sourceDevice: WirelessDevice;
  targetDevice?: WirelessDevice; // optional if broadcast
  currentFrame: number;
}

export const RfTransmissionPath: React.FC<RfTransmissionPathProps> = ({
  event,
  sourceDevice,
  targetDevice,
  currentFrame,
}) => {
  const relFrame = currentFrame - event.startFrame;
  if (relFrame < 0 || relFrame > event.durationFrames) {
    return null;
  }

  // Progress along the path (0 -> 1)
  const progress = Math.min(1, Math.max(0, relFrame / event.durationFrames));

  // Frame category colors
  let frameColor = "#06B6D4"; // data: cyan
  if (event.frameCategory === "management") {
    frameColor = "#A855F7"; // purple
  } else if (event.frameCategory === "control") {
    frameColor = "#F59E0B"; // amber
  }

  if (event.signalState === "collision") {
    frameColor = "#EF4444"; // red on collision
  }

  const isBroadcast = !targetDevice || event.targetId === "broadcast";

  // Broadcast radial wave
  if (isBroadcast) {
    const waveRadius = interpolate(progress, [0, 1], [30, 480]);
    const waveOpacity = interpolate(progress, [0, 0.7, 1], [0.8, 0.5, 0]);

    return (
      <svg
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
          zIndex: 20,
        }}
      >
        <circle
          cx={`${sourceDevice.x}%`}
          cy={`${sourceDevice.y}%`}
          r={waveRadius}
          fill="none"
          stroke={frameColor}
          strokeWidth="3"
          strokeDasharray="8 6"
          opacity={waveOpacity}
        />
        {/* Broadcast label */}
        <text
          x={`${sourceDevice.x}%`}
          y={`calc(${sourceDevice.y}% - ${waveRadius * 0.7}px)`}
          fill={frameColor}
          fontSize="11"
          fontFamily="monospace"
          fontWeight="bold"
          textAnchor="middle"
          opacity={waveOpacity}
        >
          {event.frameSubtype} [BROADCAST CH {event.channel}]
        </text>
      </svg>
    );
  }

  // Point-to-point transmission
  const x1 = sourceDevice.x;
  const y1 = sourceDevice.y;
  const x2 = targetDevice.x;
  const y2 = targetDevice.y;

  // Curvature for multi-link or multiple streams (e.g. Wi-Fi 7 link 0 vs 1)
  const arcOffset = event.linkId === 1 ? -12 : event.linkId === 0 ? 0 : 6;
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2 + arcOffset;

  // Current packet position along quadratic bezier
  const t = progress;
  const curX = (1 - t) * (1 - t) * x1 + 2 * (1 - t) * t * midX + t * t * x2;
  const curY = (1 - t) * (1 - t) * y1 + 2 * (1 - t) * t * midY + t * t * y2;

  // Collision explosion effect if collision occurred
  const isColliding = event.signalState === "collision" && progress > 0.45;
  const collisionScale = isColliding ? interpolate(progress, [0.45, 1], [0.5, 2.5]) : 0;
  const collisionOpacity = isColliding ? interpolate(progress, [0.45, 0.7, 1], [1, 0.8, 0]) : 0;

  return (
    <svg
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        zIndex: 22,
        overflow: "visible",
      }}
    >
      {/* Defined Gradient and Glow Filter */}
      <defs>
        <filter id={`glow-${event.id}`} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Guide Carrier Path Line */}
      <path
        d={`M ${x1}% ${y1}% Q ${midX}% ${midY}% ${x2}% ${y2}%`}
        fill="none"
        stroke={frameColor}
        strokeWidth="1.5"
        strokeDasharray="4 6"
        opacity="0.35"
      />

      {/* Active RF Pulse Beam trailing the packet */}
      <path
        d={`M ${x1}% ${y1}% Q ${midX}% ${midY}% ${curX}% ${curY}%`}
        fill="none"
        stroke={frameColor}
        strokeWidth="3"
        strokeLinecap="round"
        filter={`url(#glow-${event.id})`}
        opacity="0.85"
      />

      {/* Packet Flying Capsule */}
      <g transform={`translate(0, 0)`}>
        {/* Packet Aura */}
        <circle
          cx={`${curX}%`}
          cy={`${curY}%`}
          r="16"
          fill={frameColor}
          opacity="0.25"
        />
        {/* Central Packet Icon */}
        <circle
          cx={`${curX}%`}
          cy={`${curY}%`}
          r="7"
          fill={frameColor}
          stroke="#0F172A"
          strokeWidth="2"
        />

        {/* Packet Tag Box */}
        <rect
          x={`calc(${curX}% - 40px)`}
          y={`calc(${curY}% - 30px)`}
          width="80"
          height="20"
          rx="5"
          fill="rgba(15, 23, 42, 0.92)"
          stroke={frameColor}
          strokeWidth="1.5"
        />
        <text
          x={`${curX}%`}
          y={`calc(${curY}% - 16px)`}
          fill="#F8FAFC"
          fontSize="9.5"
          fontFamily="monospace"
          fontWeight="bold"
          textAnchor="middle"
        >
          {event.frameSubtype}
        </text>
      </g>

      {/* Collision Burst if signalState === 'collision' */}
      {isColliding && (
        <g transform={`translate(0, 0)`}>
          <circle
            cx={`${midX}%`}
            cy={`${midY}%`}
            r={30 * collisionScale}
            fill="none"
            stroke="#EF4444"
            strokeWidth="3"
            opacity={collisionOpacity}
          />
          <circle
            cx={`${midX}%`}
            cy={`${midY}%`}
            r="12"
            fill="#EF4444"
            opacity={collisionOpacity}
          />
          <text
            x={`${midX}%`}
            y={`calc(${midY}% - 32px)`}
            fill="#EF4444"
            fontSize="12"
            fontFamily="monospace"
            fontWeight="900"
            textAnchor="middle"
            filter="drop-shadow(0px 2px 4px rgba(0,0,0,0.8))"
          >
            COLLISION / INTERFERENCE!
          </text>
        </g>
      )}
    </svg>
  );
};
