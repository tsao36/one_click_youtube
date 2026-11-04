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
