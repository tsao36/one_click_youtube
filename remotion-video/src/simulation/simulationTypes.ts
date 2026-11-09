import { z } from "zod";

export const TrackingAnchorSchema = z.object({
  id: z.string(),
  label: z.string().min(1).max(100),
  sublabel: z.string().max(160).optional().default(""),
  targetX: z.number().min(0).max(100), // Subject anchor percentage on background
  targetY: z.number().min(0).max(100),
  boxX: z.number().min(0).max(100),    // Floating card percentage position
  boxY: z.number().min(0).max(100),
  metric: z.string().max(60).optional().default(""),
  status: z.enum(["active", "warning", "eliminated", "completed", "normal"]).default("normal"),
  highlightColor: z.string().optional().default("#38BDF8"),
});
export type TrackingAnchor = z.infer<typeof TrackingAnchorSchema>;

export const QueuedAgentSchema = z.object({
  id: z.string(),
  name: z.string().max(80),
  role: z.string().max(100),
  state: z.enum(["waiting", "receiving", "assigned", "chaotic"]).default("waiting"),
  color: z.string().optional().default("#38BDF8"),
  rationItem: z.string().optional().default("🍞 Bread"),
});
export type QueuedAgent = z.infer<typeof QueuedAgentSchema>;

export const SimulationMetricSchema = z.object({
  id: z.string(),
  label: z.string().max(60),
  startValue: z.number(),
  endValue: z.number(),
  suffix: z.string().optional().default(""),
  color: z.string().optional().default("#38BDF8"),
});
export type SimulationMetric = z.infer<typeof SimulationMetricSchema>;

export const SimulationMilestoneSchema = z.object({
  atFrame: z.number().min(0),
  timeCode: z.string().max(30),
  headline: z.string().max(120),
  detail: z.string().max(300),
  badge: z.string().optional().default("SIMULATION EVENT"),
  highlightAnchorIds: z.array(z.string()).optional().default([]),
});
export type SimulationMilestone = z.infer<typeof SimulationMilestoneSchema>;

export const AgentSimulationScenePropsSchema = z.object({
  badge: z.string().optional().default("AI EMERGENCE EXPERIMENT"),
  title: z.string().default("50 AI Agents in Sandbox Simulation"),
  subtitle: z.string().optional().default("From early chaos to self-organizing bureaucracy"),
  experimentPrompt: z.string().optional().default("INSTRUCTION: 'Build a prosperous civilization'"),
  anchors: z.array(TrackingAnchorSchema).default([]),
  agents: z.array(QueuedAgentSchema).default([]),
  metrics: z.array(SimulationMetricSchema).default([]),
  milestones: z.array(SimulationMilestoneSchema).default([]),
  finalPunchline: z.string().optional().default("RESULT: 3 HOURS LATER -> ORDERLY FOOD QUEUING & BUREAUCRACY"),
  bgSrc: z.string().optional().default(""),
  dim: z.number().min(0).max(1).optional().default(0.55),
  accentColor: z.string().optional().default("#F59E0B"),
  enableSfx: z.boolean().optional().default(true),
});
export type AgentSimulationSceneProps = z.infer<typeof AgentSimulationScenePropsSchema>;
