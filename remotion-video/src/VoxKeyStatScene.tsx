import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { VoxBackground } from './VoxBackground';
import { VoxKeyStatSceneProps } from './types';

export const VoxKeyStatScene: React.FC<VoxKeyStatSceneProps> = ({
  headline = 'GLOBAL ENERGY CRISIS',
  tag = 'KEY FINDING',
  mainStat = '74%',
  statLabel = 'of industrial supply chains disrupted by geopolitical embargoes',
  supportingPoints = [
    { label: 'Estimated loss', value: '$1.4 Trillion', trend: 'down' },
    { label: 'Affected countries', value: '48 Nations', trend: 'neutral' },
    { label: 'Recovery timeframe', value: '24-36 Months', trend: 'neutral' },
  ],
  source = 'VOX INVESTIGATIVE DATABASE / WORLD BANK 2024 REPORT',
  accentColor = '#FACC15',
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Entrance spring
  const headerEntrance = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 120 },
  });

  const statEntrance = spring({
    frame: frame - 8,
    fps,
    config: { damping: 12, stiffness: 140 },
  });

  const lineProgress = interpolate(frame, [15, 35], [0, 100], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const pointsEntrance = spring({
    frame: frame - 20,
    fps,
    config: { damping: 15, stiffness: 100 },
  });

  return (
    <VoxBackground accentColor={accentColor} headline={headline}>
      <AbsoluteFill
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 100px',
        }}
      >
        {/* Main Content Box */}
        <div
          style={{
            maxWidth: '1300px',
            width: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            transform: `translateY(${(1 - headerEntrance) * 30}px)`,
            opacity: headerEntrance,
          }}
        >
          {/* Tag pill */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: accentColor,
              color: '#000000',
              fontWeight: 900,
              fontSize: '15px',
              letterSpacing: '3px',
              textTransform: 'uppercase',
              padding: '6px 18px',
              borderRadius: '2px',
              marginBottom: '28px',
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#000000',
              }}
            />
            {tag}
          </div>

          {/* Big Number / Stat */}
          <div
            style={{
              position: 'relative',
              marginBottom: '16px',
              transform: `scale(${interpolate(statEntrance, [0, 1], [0.85, 1])})`,
              opacity: statEntrance,
            }}
          >
            <h1
              style={{
                fontSize: '140px',
                fontWeight: 950,
                color: '#ffffff',
                lineHeight: 0.95,
                margin: 0,
                letterSpacing: '-3px',
                fontFamily:
                  'Impact, "Arial Black", "PingFang SC", "Microsoft YaHei", sans-serif',
                textShadow: '0 8px 30px rgba(0,0,0,0.7)',
              }}
            >
              {mainStat}
            </h1>

            {/* Sharp Underline marker */}
            <div
              style={{
                position: 'absolute',
                bottom: '-8px',
                left: '50%',
                transform: 'translateX(-50%)',
                width: `${lineProgress}%`,
                maxWidth: '100%',
                height: '10px',
                backgroundColor: accentColor,
                borderRadius: '1px',
              }}
            />
          </div>

          {/* Stat Label */}
          <p
            style={{
              fontSize: '28px',
              fontWeight: 600,
              color: '#E2E8F0',
              maxWidth: '850px',
              lineHeight: 1.4,
              marginTop: '24px',
              marginBottom: '44px',
              opacity: headerEntrance,
            }}
          >
            {statLabel}
          </p>

          {/* Supporting metrics row */}
          {supportingPoints && supportingPoints.length > 0 && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: `repeat(${supportingPoints.length}, 1fr)`,
                gap: '24px',
                width: '100%',
                maxWidth: '1050px',
                opacity: pointsEntrance,
                transform: `translateY(${(1 - pointsEntrance) * 20}px)`,
              }}
            >
              {supportingPoints.map((pt, idx) => (
                <div
                  key={idx}
                  style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    borderTop: `3px solid ${accentColor}`,
                    padding: '18px 24px',
                    borderRadius: '4px',
                    backdropFilter: 'blur(10px)',
                    textAlign: 'left',
                  }}
                >
                  <div
                    style={{
                      fontSize: '13px',
                      color: '#94A3B8',
                      letterSpacing: '1px',
                      textTransform: 'uppercase',
                      fontWeight: 700,
                      marginBottom: '8px',
                    }}
                  >
                    {pt.label}
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: '#FFFFFF',
                      fontFamily: '"Arial Black", Impact, sans-serif',
                    }}
                  >
                    {pt.value}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Footnote / Source */}
          {source && (
            <div
              style={{
                marginTop: '40px',
                fontSize: '12px',
                letterSpacing: '1.5px',
                color: '#64748B',
                fontWeight: 600,
                textTransform: 'uppercase',
                opacity: headerEntrance,
              }}
            >
              [ {source} ]
            </div>
          )}
        </div>
      </AbsoluteFill>
    </VoxBackground>
  );
};
