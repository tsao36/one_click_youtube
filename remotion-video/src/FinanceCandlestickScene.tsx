import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FinanceBackground } from "./FinanceBackground";
import { FinanceCandlestickSceneProps } from "./types";
import {
  GlintSheen,
  RadarBeacon,
  useContinuousDrift,
  useCountUp,
} from "./animations";

export const FinanceCandlestickScene: React.FC<FinanceCandlestickSceneProps> = ({
  ticker = "NVDA / 輝達",
  badge = "MARKET BREAKOUT ANALYSIS",
  title = "AI 算力霸權下的關鍵突破點",
  subtitle = "突破歷史阻力位，形成強勁多頭上升通道",
  price = "$148.50",
  change = "+24.8%",
  isBullish = true,
  metric1Label = "本益比 (Forward P/E)",
  metric1Value = "34.2x",
  metric2Label = "目標估值市值",
  metric2Value = "$3.65T",
  thesis = "資料中心營收年增率突破 150%，Blackwell 架構全面量產帶動毛利率維持 75% 高檔水準。",
  accentColor = "#10B981",
  bgSrc = "",
  dim = 0.35,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { floatY, glowPulse } = useContinuousDrift(0.0002);

  // Entrance spring
  const entrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 100 },
  });

  // Animated line drawing progress (0 to 1)
  const lineProgress = interpolate(frame, [15, 65], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Rolling count-up for hero price
  const { display: animatedPrice, punchScale: pricePunch } = useCountUp(price, {
    startFrame: 8,
    duration: 32,
    fps,
  });

  // Sample K-line data
  const candles = [
    { o: 28, c: 35, h: 38, l: 24, g: true },
    { o: 35, c: 32, h: 40, l: 30, g: false },
    { o: 32, c: 42, h: 45, l: 30, g: true },
    { o: 42, c: 48, h: 52, l: 39, g: true },
    { o: 48, c: 45, h: 50, l: 42, g: false },
    { o: 45, c: 56, h: 60, l: 44, g: true },
    { o: 56, c: 52, h: 58, l: 50, g: false },
    { o: 52, c: 68, h: 72, l: 50, g: true },
    { o: 68, c: 64, h: 70, l: 62, g: false },
    { o: 64, c: 78, h: 82, l: 62, g: true },
    { o: 78, c: 88, h: 94, l: 76, g: true },
  ];

  const primaryColor = isBullish ? "#10B981" : "#EF4444";

  return (
    <FinanceBackground bgSrc={bgSrc} dim={dim} accentColor={accentColor}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          height: "100%",
          padding: "36px 60px",
          boxSizing: "border-box",
          transform: `scale(${entrance}) translateY(${floatY}px)`,
          opacity: entrance,
        }}
      >
        {/* Top Header Bar */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: 20,
          }}
        >
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 8,
              }}
            >
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  backgroundColor: "rgba(16, 185, 129, 0.15)",
                  color: primaryColor,
                  border: `1.5px solid ${primaryColor}`,
                  borderRadius: 6,
                  padding: "4px 12px",
                  fontSize: 12,
                  fontWeight: 800,
                  letterSpacing: 1,
                  boxShadow: `0 0 ${10 * glowPulse}px ${primaryColor}44`,
                }}
              >
                <RadarBeacon color={primaryColor} size={6} />
                <span>{badge}</span>
              </span>
              <span
                style={{
                  fontSize: 18,
                  fontWeight: 900,
                  color: "#38BDF8",
                  fontFamily: "monospace",
                  letterSpacing: 1,
                }}
              >
                {ticker}
              </span>
            </div>
            <div
              style={{
                fontSize: 34,
                fontWeight: 900,
                color: "#FFFFFF",
                letterSpacing: 0.5,
              }}
            >
              {title}
            </div>
            {subtitle && (
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  color: "#94A3B8",
                  marginTop: 4,
                }}
              >
                {subtitle}
              </div>
            )}
          </div>

          {/* Current Price Hero Badge with Count-up */}
          <div
            style={{
              position: "relative",
              backgroundColor: "rgba(15, 23, 42, 0.9)",
              border: `2px solid ${primaryColor}`,
              borderRadius: 12,
              padding: "12px 24px",
              boxShadow: `0 0 25px ${primaryColor}44`,
              textAlign: "right",
              overflow: "hidden",
            }}
          >
            <GlintSheen color={`${primaryColor}88`} periodFrames={80} />
            <div
              style={{
                fontSize: 12,
                fontWeight: 700,
                color: "#94A3B8",
                letterSpacing: 1,
              }}
            >
              CURRENT PRICE
            </div>
            <div
              style={{
                fontSize: 38,
                fontWeight: 900,
                color: "#FFFFFF",
                fontFamily: "monospace",
                transform: `scale(${pricePunch})`,
              }}
            >
              {animatedPrice}
            </div>
            <div
              style={{
                fontSize: 16,
                fontWeight: 800,
                color: primaryColor,
                fontFamily: "monospace",
              }}
            >
              {isBullish ? "▲ " : "▼ "}
              {change}
            </div>
          </div>
        </div>

        {/* Main Grid: Left Chart + Right Metric Analysis */}
        <div
          style={{
            flex: 1,
            display: "grid",
            gridTemplateColumns: "1.3fr 0.9fr",
            gap: 32,
            alignItems: "center",
          }}
        >
          {/* Left: Candlestick Chart Window */}
          <div
            style={{
              height: "100%",
              maxHeight: 460,
              backgroundColor: "rgba(11, 19, 38, 0.85)",
              border: "1.5px solid #1E293B",
              borderRadius: 12,
              padding: "24px 28px",
              boxSizing: "border-box",
              position: "relative",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              boxShadow: "0 10px 30px rgba(0,0,0,0.4)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 12,
                color: "#64748B",
                fontWeight: 700,
              }}
            >
              <span>INTERVAL: DAILY (K-LINE + EMA 20)</span>
              <span
                style={{
                  color: primaryColor,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <RadarBeacon color={primaryColor} size={6} />
                <span>BULLISH MOMENTUM</span>
              </span>
            </div>

            {/* SVG Candlestick Canvas */}
            <div
              style={{
                position: "relative",
                width: "100%",
                height: 320,
                marginTop: 10,
              }}
            >
              <svg
                viewBox="0 0 550 280"
                style={{ width: "100%", height: "100%", overflow: "visible" }}
              >
                {/* Horizontal price guide lines */}
                <line
                  x1="0"
                  y1="60"
                  x2="550"
                  y2="60"
                  stroke="#1E293B"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                />
                <line
                  x1="0"
                  y1="140"
                  x2="550"
                  y2="140"
                  stroke="#1E293B"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                />
                <line
                  x1="0"
                  y1="220"
                  x2="550"
                  y2="220"
                  stroke="#1E293B"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                />

                {/* Candles with progressive drawing entrance */}
                {candles.map((c, idx) => {
                  const candleEntrance = spring({
                    frame: frame - (10 + idx * 3),
                    fps,
                    config: { damping: 12, stiffness: 110 },
                  });

                  const cx = 35 + idx * 46;
                  const cColor = c.g ? "#10B981" : "#EF4444";
                  const top = 260 - Math.max(c.o, c.c) * 2.4;
                  const bot = 260 - Math.min(c.o, c.c) * 2.4;
                  const h = 260 - c.h * 2.4;
                  const l = 260 - c.l * 2.4;
                  const bodyHeight = Math.max(6, (bot - top) * candleEntrance);

                  return (
                    <g key={idx} opacity={candleEntrance}>
                      {/* Upper & Lower Wick */}
                      <line
                        x1={cx}
                        y1={h}
                        x2={cx}
                        y2={l}
                        stroke={cColor}
                        strokeWidth="2"
                      />
                      {/* Real Body */}
                      <rect
                        x={cx - 12}
                        y={top}
                        width="24"
                        height={bodyHeight}
                        fill={cColor}
                        rx="2"
                      />
                    </g>
                  );
                })}

                {/* Smooth Exponential Moving Average Line */}
                <path
                  d="M 35 200 Q 150 170, 260 135 T 510 50"
                  fill="none"
                  stroke="#38BDF8"
                  strokeWidth="3.5"
                  strokeDasharray="500"
                  strokeDashoffset={500 * (1 - lineProgress)}
                  style={{
                    filter: "drop-shadow(0 0 8px rgba(56, 189, 248, 0.6))",
                  }}
                />

                {/* Pulsing Beacon at Breakout Tip */}
                {lineProgress > 0.85 && (
                  <circle
                    cx="510"
                    cy="50"
                    r={6 + Math.sin(frame / 6) * 2}
                    fill="#38BDF8"
                    filter="drop-shadow(0 0 8px #38BDF8)"
                  />
                )}
              </svg>
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 11,
                color: "#475569",
                fontFamily: "monospace",
              }}
            >
              <span>T-60D</span>
              <span>T-40D</span>
              <span>T-20D</span>
              <span style={{ color: "#38BDF8" }}>CURRENT BREAKOUT POINT</span>
            </div>
          </div>

          {/* Right: Key Valuation & Catalyst Panel */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Metric 1 Card */}
            <div
              style={{
                backgroundColor: "rgba(15, 23, 42, 0.8)",
                border: "1.5px solid #1E293B",
                borderRadius: 10,
                padding: "16px 22px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: "#94A3B8",
                  }}
                >
                  {metric1Label}
                </div>
                <div
                  style={{
                    fontSize: 26,
                    fontWeight: 900,
                    color: "#FFFFFF",
                    fontFamily: "monospace",
                    marginTop: 2,
                  }}
                >
                  {metric1Value}
                </div>
              </div>
              <div style={{ fontSize: 22, color: "#38BDF8" }}>📈</div>
            </div>

            {/* Metric 2 Card */}
            <div
              style={{
                backgroundColor: "rgba(15, 23, 42, 0.8)",
                border: "1.5px solid #1E293B",
                borderRadius: 10,
                padding: "16px 22px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: "#94A3B8",
                  }}
                >
                  {metric2Label}
                </div>
                <div
                  style={{
                    fontSize: 26,
                    fontWeight: 900,
                    color: "#FFFFFF",
                    fontFamily: "monospace",
                    marginTop: 2,
                  }}
                >
                  {metric2Value}
                </div>
              </div>
              <div style={{ fontSize: 22, color: primaryColor }}>🎯</div>
            </div>

            {/* Core Catalyst Box */}
            <div
              style={{
                backgroundColor: "rgba(15, 23, 42, 0.8)",
                border: "1.5px solid #1E293B",
                borderRadius: 10,
                padding: "18px 22px",
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 800,
                  color: "#94A3B8",
                  letterSpacing: 1,
                  marginBottom: 6,
                }}
              >
                CORE CATALYST
              </div>
              <div
                style={{
                  fontSize: 15,
                  fontWeight: 600,
                  color: "#CBD5E1",
                  lineHeight: 1.55,
                }}
              >
                {thesis}
              </div>
            </div>
          </div>
        </div>
      </div>
    </FinanceBackground>
  );
};
