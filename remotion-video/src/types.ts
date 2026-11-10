import { z } from "zod";

// Base Scene Schema
export const BaseScenePropsSchema = z.object({
  bgSrc: z.string().optional().default(""),
  dim: z.number().min(0).max(1).optional().default(0.75),
  accentColor: z.string().optional().default("#00F5FF"),
  badge: z.string().optional().default("INVESTIGATIVE ANALYSIS"),
});
export type BaseSceneProps = z.infer<typeof BaseScenePropsSchema>;

// 1. BranchPathwayScene Schema
export const PathwayNodeSchema = z.object({
  id: z.string(),
  name: z.string().min(1).max(80),
  category: z.string().max(40).optional().default(""),
  detail: z.string().max(160),
  status: z.enum(["eliminated", "selected", "neutral"]).default("neutral"),
  eliminationReason: z.string().max(120).optional().default(""),
  highlightTag: z.string().max(40).optional().default(""),
});
export type PathwayNode = z.infer<typeof PathwayNodeSchema>;

export const BranchPathwaySceneSchema = BaseScenePropsSchema.extend({
  title: z.string().min(1).max(100),
  subtitle: z.string().max(160).optional().default(""),
  paths: z.array(PathwayNodeSchema).min(2).max(6),
  selectedId: z.string().optional().default(""),
});
export type BranchPathwaySceneProps = z.input<typeof BranchPathwaySceneSchema>;

// 2. LeaderCalloutScene Schema
export const CalloutPointSchema = z.object({
  id: z.string(),
  label: z.string().min(1).max(80),
  sublabel: z.string().max(120).optional().default(""),
  anchorX: z.number().min(0.05).max(0.95), // Normalized 0-1 on background image
  anchorY: z.number().min(0.05).max(0.95),
  boxX: z.number().min(0.05).max(0.95),
  boxY: z.number().min(0.05).max(0.95),
  metric: z.string().max(40).optional().default(""),
  status: z.enum(["active", "normal", "warning"]).default("normal"),
});
export type CalloutPoint = z.infer<typeof CalloutPointSchema>;

export const LeaderCalloutSceneSchema = BaseScenePropsSchema.extend({
  title: z.string().min(1).max(100),
  subtitle: z.string().max(160).optional().default(""),
  callouts: z.array(CalloutPointSchema).min(1).max(6),
});
export type LeaderCalloutSceneProps = z.input<typeof LeaderCalloutSceneSchema>;

// 3. ScaleCompareScene Schema
export const ScaleCompareSceneSchema = BaseScenePropsSchema.extend({
  title: z.string().min(1).max(100),
  subtitle: z.string().max(160).optional().default(""),
  macroLabel: z.string().min(1).max(80),
  macroValue: z.string().min(1).max(40),
  macroDesc: z.string().max(160).optional().default(""),
  microLabel: z.string().min(1).max(80),
  microValue: z.string().min(1).max(40),
  microDesc: z.string().max(160).optional().default(""),
  ratioMultiplier: z.string().max(40).default("20×"),
  ratioLabel: z.string().max(80).optional().default("尺度極限差距"),
  magnificationFactor: z.string().max(40).optional().default("20X ZOOM"),
});
export type ScaleCompareSceneProps = z.input<typeof ScaleCompareSceneSchema>;

// 4. EvidenceHighlightScene Schema
export const TelemetryStatSchema = z.object({
  label: z.string().max(60),
  value: z.string().max(60),
  badge: z.string().max(40).optional().default(""),
});
export type TelemetryStat = z.infer<typeof TelemetryStatSchema>;

export const EvidenceHighlightSceneSchema = BaseScenePropsSchema.extend({
  title: z.string().min(1).max(100),
  docHeader: z.string().max(80).optional().default("ARCHIVAL RECORD / CLINICAL PROTOCOL"),
  docDate: z.string().max(40).optional().default(""),
  documentExcerpt: z.string().min(1).max(600),
  highlightPhrase: z.string().min(1).max(300),
  telemetryStats: z.array(TelemetryStatSchema).optional().default([]),
});
export type EvidenceHighlightSceneProps = z.input<typeof EvidenceHighlightSceneSchema>;


// ==========================================
// 5. fOx Hsiao Style Documentary Archetypes
// ==========================================

// 5.1 FoxHeaderScene Schema
export const FoxHeaderSceneSchema = z.object({
  category: z.string().optional().default(""),
  title: z.string().min(1).max(120),
  subtitle: z.string().max(200).optional().default(""),
  source: z.string().max(100).optional().default(""),
  bgSrc: z.string().optional().default(""),
  dim: z.number().min(0).max(1).optional().default(0.35),
  accentColor: z.string().optional().default("#F87171"),
});
export type FoxHeaderSceneProps = z.input<typeof FoxHeaderSceneSchema>;

// 5.2 FoxMetricScene Schema
export const FoxMetricSceneSchema = z.object({
  badge: z.string().max(80).optional().default(""),
  value: z.string().min(1).max(60),
  unit: z.string().max(40).optional().default(""),
  conversion: z.string().max(60).optional().default(""),
  description: z.string().max(160).optional().default(""),
  subtext: z.string().max(240).optional().default(""),
  source: z.string().max(100).optional().default(""),
  bgSrc: z.string().optional().default(""),
  dim: z.number().min(0).max(1).optional().default(0.4),
  accentColor: z.string().optional().default("#38BDF8"),
});
export type FoxMetricSceneProps = z.input<typeof FoxMetricSceneSchema>;

// 5.3 FoxDataListScene Schema
export const FoxDataListItemSchema = z.object({
  label: z.string().min(1).max(80),
  value: z.string().min(1).max(60),
  note: z.string().max(100).optional().default(""),
  highlight: z.boolean().optional().default(false),
});
export type FoxDataListItem = z.infer<typeof FoxDataListItemSchema>;

export const FoxDataListSceneSchema = z.object({
  chapter: z.string().max(80).optional().default(""),
  title: z.string().min(1).max(120),
  items: z.array(FoxDataListItemSchema).min(1).max(8),
  totalLabel: z.string().max(60).optional().default(""),
  totalValue: z.string().max(80).optional().default(""),
  source: z.string().max(100).optional().default(""),
  bgSrc: z.string().optional().default(""),
  dim: z.number().min(0).max(1).optional().default(0.5),
  accentColor: z.string().optional().default("#38BDF8"),
});
export type FoxDataListSceneProps = z.input<typeof FoxDataListSceneSchema>;

// 5.4 FoxTimelineScene Schema
export const FoxTimelineSceneSchema = z.object({
  chapter: z.string().max(80).optional().default(""),
  title: z.string().min(1).max(120),
  startYear: z.string().min(1).max(30),
  startLabel: z.string().min(1).max(100),
  endYear: z.string().min(1).max(30),
  endLabel: z.string().min(1).max(100),
  middleYear: z.string().max(30).optional().default(""),
  middleLabel: z.string().max(100).optional().default(""),
  subtext: z.string().max(240).optional().default(""),
  source: z.string().max(100).optional().default(""),
  bgSrc: z.string().optional().default(""),
  dim: z.number().min(0).max(1).optional().default(0.45),
  accentColor: z.string().optional().default("#38BDF8"),
});
export type FoxTimelineSceneProps = z.input<typeof FoxTimelineSceneSchema>;


// ==============================================================
// 6. Modern Tech Explainer Archetypes (Gary Chen / Kinetic Style)
// ==============================================================

// 6.1 FrameworkMatrixScene Schema (e.g. 4-Pillar Grid: 速度/高度/深度/廣度)
export const FrameworkPillarSchema = z.object({
  id: z.string(),
  title: z.string().min(1).max(60),
  subtitle: z.string().max(100).optional().default(""),
  icon: z.string().max(30).optional().default("⚡"),
  metric: z.string().max(40).optional().default(""),
  points: z.array(z.string().max(100)).optional().default([]),
  isHighlighted: z.boolean().optional().default(false),
});
export type FrameworkPillar = z.infer<typeof FrameworkPillarSchema>;

export const FrameworkMatrixSceneSchema = z.object({
  badge: z.string().max(60).optional().default("THE 4-PILLAR FRAMEWORK"),
  title: z.string().min(1).max(120),
  subtitle: z.string().max(200).optional().default(""),
  pillars: z.array(FrameworkPillarSchema).min(2).max(4),
  activePillarId: z.string().optional().default(""),
  accentColor: z.string().optional().default("#38BDF8"),
});
export type FrameworkMatrixSceneProps = z.input<typeof FrameworkMatrixSceneSchema>;

// 6.2 PromptComparisonScene Schema (Before vs After / Basic vs Ambitious)
export const PromptComparisonSceneSchema = z.object({
  badge: z.string().max(60).optional().default("PROMPT STRATEGY COMPARISON"),
  title: z.string().min(1).max(120),
  subtitle: z.string().max(200).optional().default(""),
  leftBadge: z.string().max(50).optional().default("一般用法 (Conventional)"),
  leftTitle: z.string().min(1).max(80),
  leftContent: z.string().min(1).max(400),
  leftTags: z.array(z.string().max(40)).optional().default([]),
  rightBadge: z.string().max(50).optional().default("高手做法 (Ambitious Prompt)"),
  rightTitle: z.string().min(1).max(80),
  rightContent: z.string().min(1).max(400),
  rightTags: z.array(z.string().max(40)).optional().default([]),
  takeaway: z.string().max(160).optional().default(""),
  accentColor: z.string().optional().default("#38BDF8"),
});
export type PromptComparisonSceneProps = z.input<typeof PromptComparisonSceneSchema>;

// 6.3 ChatSimulationScene Schema (Simulated Claude/ChatGPT UI)
export const ChatResponseItemSchema = z.object({
  title: z.string().min(1).max(80),
  detail: z.string().min(1).max(200),
  tag: z.string().max(40).optional().default(""),
});
export type ChatResponseItem = z.infer<typeof ChatResponseItemSchema>;

export const ChatSimulationSceneSchema = z.object({
  badge: z.string().max(60).optional().default("AI WORKFLOW EXECUTION"),
  title: z.string().min(1).max(120),
  systemTag: z.string().max(60).optional().default("Claude 3.5 Sonnet"),
  promptText: z.string().min(1).max(300),
  responseTitle: z.string().max(80).optional().default("深度執行產出 (Generated Plan)"),
  responseItems: z.array(ChatResponseItemSchema).min(1).max(4),
  accentColor: z.string().optional().default("#A855F7"),
});
export type ChatSimulationSceneProps = z.input<typeof ChatSimulationSceneSchema>;

// 6.4 KineticQuoteScene Schema (Authority Quote Card)
export const KineticQuoteSceneSchema = z.object({
  badge: z.string().max(60).optional().default("EXPERT INSIGHT"),
  quote: z.string().min(1).max(300),
  author: z.string().min(1).max(80),
  authorTitle: z.string().max(120).optional().default(""),
  authorAvatarUrl: z.string().optional().default(""),
  highlightPhrase: z.string().max(100).optional().default(""),
  accentColor: z.string().optional().default("#F59E0B"),
});
export type KineticQuoteSceneProps = z.input<typeof KineticQuoteSceneSchema>;

// 6.5 WorkflowStepScene Schema (Connected Pipeline 01 -> 02 -> 03)
export const WorkflowStepItemSchema = z.object({
  stepNumber: z.string().min(1).max(20),
  label: z.string().min(1).max(60),
  detail: z.string().min(1).max(160),
  tag: z.string().max(40).optional().default(""),
});
export type WorkflowStepItem = z.infer<typeof WorkflowStepItemSchema>;

export const WorkflowStepSceneSchema = z.object({
  badge: z.string().max(60).optional().default("ITERATIVE PIPELINE"),
  title: z.string().min(1).max(120),
  subtitle: z.string().max(200).optional().default(""),
  steps: z.array(WorkflowStepItemSchema).min(2).max(4),
  activeStepIndex: z.number().int().min(0).max(4).optional().default(1),
  accentColor: z.string().optional().default("#38BDF8"),
});
export type WorkflowStepSceneProps = z.input<typeof WorkflowStepSceneSchema>;


// 6.6 KineticTypographyScene Schema (Spoken Word Lighting / Centered Thesis)
export const KineticWordItemSchema = z.object({
  word: z.string(),
  start: z.number().optional().default(0),
  end: z.number().optional().default(0),
  highlight: z.boolean().optional().default(false),
});
export type KineticWordItem = z.infer<typeof KineticWordItemSchema>;

export const KineticTypographySceneSchema = z.object({
  badge: z.string().max(60).optional().default("CORE THESIS"),
  text: z.string().min(1).max(200),
  highlightPhrase: z.string().max(100).optional().default(""),
  words: z.array(KineticWordItemSchema).optional().default([]),
  subtext: z.string().max(200).optional().default(""),
  accentColor: z.string().optional().default("#38BDF8"),
});
export type KineticTypographySceneProps = z.input<typeof KineticTypographySceneSchema>;


// ==============================================================
// 7. Coordinate Zero (座標零) Geographic Lab Archetypes
// ==============================================================

// 7.1 CoordinateZeroScaleScene Schema (Multi-subject scale morphing comparison)
export const CoordinateZeroCompareItemSchema = z.object({
  id: z.string(),
  name: z.string().min(1).max(60),
  initialMultiplier: z.number().default(2.0),
  actualMultiplier: z.number().default(1.0),
  initialLabel: z.string().max(30).optional().default(""),
  actualLabel: z.string().max(30).optional().default(""),
  isAnchor: z.boolean().optional().default(false),
  isTargetFocus: z.boolean().optional().default(false),
  customShape: z.string().optional().default(""),
  color: z.string().optional().default(""),
});
export type CoordinateZeroCompareItem = z.infer<typeof CoordinateZeroCompareItemSchema>;

export const CoordinateZeroScaleSceneSchema = z.object({
  badge: z.string().max(80).optional().default("台灣，其實比你想像中還大"),
  initialTitle: z.string().max(120).optional().default("常見的世界地圖上：畫出來的大小"),
  calibratedTitle: z.string().max(120).optional().default("搬到台灣身邊（同一個緯度）：真實大小"),
  anchorLabel: z.string().max(40).optional().default("和台灣比"),
  items: z.array(CoordinateZeroCompareItemSchema).min(2).max(6),
  accentColor: z.string().optional().default("#0D9488"),
  bgSrc: z.string().optional().default(""),
  dim: z.number().min(0).max(1).optional().default(0.15),
});
export type CoordinateZeroScaleSceneProps = z.input<typeof CoordinateZeroScaleSceneSchema>;

// 7.2 CoordinateZeroExperimentScene Schema (Experiment card + vertical magnification ruler)
export const CoordinateZeroExperimentSceneSchema = z.object({
  experimentNo: z.string().max(20).optional().default("03"),
  experimentBadge: z.string().max(40).optional().default("實驗"),
  title: z.string().min(1).max(100),
  subtitle: z.string().max(160).optional().default(""),
  gaugeLabel: z.string().max(40).optional().default("放大倍率"),
  currentMagnification: z.string().max(30).optional().default("×4.9"),
  gaugePointerPosition: z.number().min(0).max(1).optional().default(0.45),
  measurementHeader: z.string().max(40).optional().default("量測"),
  measurementTag: z.string().max(40).optional().default("地圖上"),
  measurementFormula: z.string().min(1).max(100).default("俄羅斯 = 非洲 × 2.5"),
  measurementSubtext: z.string().max(160).optional().default(""),
  accentColor: z.string().optional().default("#EF4444"),
  bgSrc: z.string().optional().default(""),
  dim: z.number().min(0).max(1).optional().default(0.15),
});
export type CoordinateZeroExperimentSceneProps = z.input<typeof CoordinateZeroExperimentSceneSchema>;

// 7.3 CoordinateZeroSplitScene Schema (Dual card pro-con split verdict)
export const CoordinateZeroSplitCardSchema = z.object({
  tag: z.string().min(1).max(60),
  tagColor: z.string().optional().default("#EF4444"),
  title: z.string().min(1).max(100),
  caption: z.string().max(160).optional().default(""),
  imgSrc: z.string().optional().default(""),
});
export type CoordinateZeroSplitCard = z.infer<typeof CoordinateZeroSplitCardSchema>;

export const CoordinateZeroSplitSceneSchema = z.object({
  verdictBadge: z.string().max(60).optional().default("各對一半"),
  badgeColor: z.string().optional().default("#3B82F6"),
  leftCard: CoordinateZeroSplitCardSchema,
  rightCard: CoordinateZeroSplitCardSchema,
  summary: z.string().max(200).optional().default(""),
  bgSrc: z.string().optional().default(""),
  dim: z.number().min(0).max(1).optional().default(0.15),
  accentColor: z.string().optional().default("#0D9488"),
});
export type CoordinateZeroSplitSceneProps = z.input<typeof CoordinateZeroSplitSceneSchema>;


// ============================================================================
// 8. Finance & Market Explainer Schemas
// ============================================================================
export const CandlestickDatumSchema = z.object({
  date: z.string().optional().default(''),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
});
export type CandlestickDatum = z.infer<typeof CandlestickDatumSchema>;

export const KeyLevelSchema = z.object({
  label: z.string(),
  price: z.number(),
  color: z.string().optional().default('#E2E8F0'),
});
export type KeyLevel = z.infer<typeof KeyLevelSchema>;

export const FinanceCandlestickSceneSchema = z.object({
  headline: z.string().max(120).optional().default('NVDA Q3 BREAKOUT STRUCTURE'),
  badge: z.string().max(80).optional().default('MARKET BREAKOUT ANALYSIS'),
  ticker: z.string().max(60).optional().default('NVDA · NASDAQ'),
  title: z.string().max(120).optional().default('AI 算力霸權下的關鍵突破點'),
  subtitle: z.string().max(200).optional().default('突破歷史阻力位，形成強勁多頭上升通道'),
  price: z.string().max(40).optional().default('.50'),
  change: z.string().max(40).optional().default('+24.8%'),
  changePercent: z.string().max(40).optional().default('+24.8%'),
  isBullish: z.boolean().optional().default(true),
  metric1Label: z.string().max(60).optional().default('本益比 (Forward P/E)'),
  metric1Value: z.string().max(40).optional().default('34.2x'),
  metric2Label: z.string().max(60).optional().default('目標估值市值'),
  metric2Value: z.string().max(40).optional().default('.65T'),
  thesis: z.string().max(400).optional().default('資料中心營收年增率突破 150%，Blackwell 架構全面量產帶動毛利率維持 75% 高檔水準。'),
  candlesticks: z.array(z.any()).optional().default([]),
  keyLevels: z.array(z.any()).optional().default([]),
  insightBadge: z.string().max(60).optional().default('KEY TRIGGER'),
  insightText: z.string().max(200).optional().default('High-volume breakout confirmed above 50-day moving average'),
  accentColor: z.string().optional().default('#10B981'),
  bgSrc: z.string().optional().default(''),
  dim: z.number().min(0).max(1).optional().default(0.35),
});
export type FinanceCandlestickSceneProps = z.input<typeof FinanceCandlestickSceneSchema>;

export const MetricCompareRowSchema = z.object({
  label: z.string(),
  valueA: z.string(),
  valueB: z.string(),
  diff: z.string().optional().default(''),
  isAdvantageA: z.boolean().optional().default(true),
});
export type MetricCompareRow = z.infer<typeof MetricCompareRowSchema>;

export const FinanceMetricCompareSceneSchema = z.object({
  badge: z.string().max(80).optional().default('COMPETITIVE FUNDAMENTALS'),
  headline: z.string().max(120).optional().default('COMPETITIVE FUNDAMENTALS'),
  title: z.string().max(120).optional().default('FY2024 估值與營運效率同業對比'),
  subtitle: z.string().max(200).optional().default('FY2024 Valuation & Operating Efficiency Comparison'),
  summary: z.string().max(300).optional().default('營收爆發力與毛利率顯著領先同業，支撐高溢價倍數'),
  bars: z.array(z.any()).optional().default([]),
  metrics: z.array(MetricCompareRowSchema).optional().default([
    { label: 'Revenue Growth (YoY)', valueA: '+122%', valueB: '+18%', diff: '+104% Spread', isAdvantageA: true },
    { label: 'Gross Margin', valueA: '75.2%', valueB: '46.1%', diff: '+29.1% Spread', isAdvantageA: true },
    { label: 'Operating Cash Flow', valueA: '.5B', valueB: '.2B', diff: '+.3B Spread', isAdvantageA: true },
    { label: 'P/E (Forward)', valueA: '36.4x', valueB: '24.1x', diff: 'Premium Multiple', isAdvantageA: false },
  ]),
  legendA: z.string().max(60).optional().default('NVIDIA (NVDA)'),
  legendB: z.string().max(60).optional().default('PEER AVERAGE'),
  accentColor: z.string().optional().default('#38BDF8'),
  bgSrc: z.string().optional().default(''),
  dim: z.number().min(0).max(1).optional().default(0.2),
});
export type FinanceMetricCompareSceneProps = z.input<typeof FinanceMetricCompareSceneSchema>;

// ============================================================================
// 9. Archival History & Chronicles Schemas
// ============================================================================
export const ArchivalDocumentSceneSchema = z.object({
  archiveId: z.string().max(100).optional().default('CABINET ARCHIVE 1945-TS-089'),
  docDate: z.string().max(60).optional().default('1945 年 8 月 15 日'),
  stampText: z.string().max(60).optional().default('DECLASSIFIED 絕密解密'),
  title: z.string().max(120).optional().default('二次大戰終戰內閣極密備忘錄'),
  documentTitle: z.string().max(120).optional().default('DECLARATION OF EMPIRE RESTRUCTURING'),
  date: z.string().max(60).optional().default('14 OCTOBER 1806'),
  archiveReference: z.string().max(100).optional().default('NATIONAL ARCHIVES · DOSSIER A-791'),
  classification: z.string().max(60).optional().default('DECLASSIFIED DISPATCH'),
  documentExcerpt: z.string().max(600).optional().default('「此項抉擇並非出於單一戰術考量，而是考量帝國全體存續之終局底線。所有軍事指令即刻停止。」'),
  excerpt: z.string().max(600).optional().default('His Majesty commands that all diplomatic envoys cease negotiations forthwith, asserting full sovereign jurisdiction over maritime corridors.'),
  highlightPhrase: z.string().max(200).optional().default('帝國全體存續之終局底線'),
  significance: z.string().max(300).optional().default('這份解密電報證實了戰後格局的核心決策並非戰場偶發，而是內閣內部經歷數月激烈辯論的最終共識。'),
  source: z.string().max(120).optional().default('來源：國立公文書館 · 昭和天皇終戰詔書起草案卷'),
  accentColor: z.string().optional().default('#DC2626'),
  bgSrc: z.string().optional().default(''),
  dim: z.number().min(0).max(1).optional().default(0.2),
});
export type ArchivalDocumentSceneProps = z.input<typeof ArchivalDocumentSceneSchema>;

export const ChronologyEventSchema = z.object({
  year: z.string().max(20),
  title: z.string().max(80),
  description: z.string().max(160),
  tag: z.string().max(40).optional().default('MILESTONE'),
});
export type ChronologyEvent = z.infer<typeof ChronologyEventSchema>;

export const HistoryChronologySceneSchema = z.object({
  archiveId: z.string().max(100).optional().default('HISTORICAL CHRONOLOGY'),
  headline: z.string().max(120).optional().default('CHRONICLE OF INDUSTRIAL EXPANSION'),
  title: z.string().max(120).optional(),
  subtitle: z.string().max(200).optional().default('Key geopolitical inflection points from 1880 to 1914'),
  events: z.array(z.any()).optional().default([
    { year: '1882', title: 'Triple Alliance Signed', description: 'Secret agreement between Germany, Austria-Hungary, and Italy.', tag: 'TREATY' },
    { year: '1898', title: 'Naval Expansion Act', description: 'Imperial fleet expansion triggers global naval arms race.', tag: 'MILITARY' },
    { year: '1907', title: 'Triple Entente Formed', description: 'Britain, France, and Russia align against central European powers.', tag: 'DIPLOMACY' },
    { year: '1914', title: 'Sarajevo Crisis', description: 'Assassination sparks chain reaction leading to World War I.', tag: 'TURNING POINT' },
  ]),
  activeYear: z.string().max(20).optional().default('1914'),
  accentColor: z.string().optional().default('#B45309'),
  bgSrc: z.string().optional().default(''),
  dim: z.number().min(0).max(1).optional().default(0.12),
});
export type HistoryChronologySceneProps = z.input<typeof HistoryChronologySceneSchema>;

// ============================================================================
// 10. Vox Investigative Journalism Schemas
// ============================================================================
export const VoxSplitScreenSceneSchema = z.object({
  headline: z.string().max(80).optional().default('HOW WE GOT HERE: THE INFRASTRUCTURE GAP'),
  subhead: z.string().max(160).optional().default('Investigating two decades of policy vs reality'),
  leftTitle: z.string().max(60).optional().default('1990: PROMISED CAPEX'),
  leftDetail: z.string().max(200).optional().default('Federal projections pledged  toward high-speed regional rail networks.'),
  leftStat: z.string().max(30).optional().default(' BILLION'),
  leftColor: z.string().optional().default('#38BDF8'),
  rightTitle: z.string().max(60).optional().default('2024: ACTUAL BUILT'),
  rightDetail: z.string().max(200).optional().default('Only 18% of projected corridor miles were completed due to environmental red tape.'),
  rightStat: z.string().max(30).optional().default('18% COMPLETED'),
  rightColor: z.string().optional().default('#EF4444'),
  source: z.string().max(120).optional().default('DATA SOURCE: DEPT OF TRANSPORTATION & GAO REPORTS'),
  accentColor: z.string().optional().default('#FACC15'),
});
export type VoxSplitScreenSceneProps = z.input<typeof VoxSplitScreenSceneSchema>;

export const SupportingPointSchema = z.object({
  label: z.string(),
  value: z.string(),
  trend: z.string().optional().default('neutral'),
});
export type SupportingPoint = z.infer<typeof SupportingPointSchema>;

export const VoxKeyStatSceneSchema = z.object({
  headline: z.string().max(80).optional().default('GLOBAL ENERGY CRISIS'),
  tag: z.string().max(40).optional().default('KEY FINDING'),
  mainStat: z.string().max(40).optional().default('74%'),
  statLabel: z.string().max(200).optional().default('of industrial supply chains disrupted by geopolitical embargoes'),
  supportingPoints: z.array(SupportingPointSchema).optional().default([
    { label: 'Estimated loss', value: '.4 Trillion', trend: 'down' },
    { label: 'Affected countries', value: '48 Nations', trend: 'neutral' },
    { label: 'Recovery timeframe', value: '24-36 Months', trend: 'neutral' },
  ]),
  source: z.string().max(140).optional().default('VOX INVESTIGATIVE DATABASE / WORLD BANK 2024 REPORT'),
  accentColor: z.string().optional().default('#FACC15'),
});
export type VoxKeyStatSceneProps = z.input<typeof VoxKeyStatSceneSchema>;


// Wireless Network Visualization Schemas
export * from "./wireless/wirelessTypes";

// AI Agent Simulation Archetype Schemas
export * from "./simulation/simulationTypes";
