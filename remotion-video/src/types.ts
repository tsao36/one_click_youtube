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

