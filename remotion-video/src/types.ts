import { z } from "zod";

// Base Scene Schema
export const BaseScenePropsSchema = z.object({
  bgSrc: z.string().optional().default(""),
  dim: z.number().min(0).max(1).optional().default(0.7),
  accentColor: z.string().optional().default("#3B82F6"),
});

// 1. TitleScene Schema
export const TitleSceneSchema = BaseScenePropsSchema.extend({
  title: z.string().min(1).max(80),
  subtitle: z.string().max(120).optional().default(""),
  category: z.string().max(40).optional().default("KEY TAKEAWAY"),
  animationStyle: z.enum(["fade_slide", "typewriter", "zoom_in"]).optional().default("fade_slide"),
});
export type TitleSceneProps = z.input<typeof TitleSceneSchema>;

// 2. GridCompareScene Schema
export const GridCompareSceneSchema = BaseScenePropsSchema.extend({
  leftTitle: z.string().min(1).max(40),
  leftBody: z.string().min(1).max(120),
  rightTitle: z.string().min(1).max(40),
  rightBody: z.string().min(1).max(120),
  comparisonLabel: z.string().max(40).optional().default("VS"),
  leftColor: z.string().optional().default("#3B82F6"),
  rightColor: z.string().optional().default("#EF4444"),
});
export type GridCompareSceneProps = z.input<typeof GridCompareSceneSchema>;

// 3. KCurveScene Schema
export const KCurveSceneSchema = BaseScenePropsSchema.extend({
  title: z.string().max(60).optional().default("K 型兩極分化趨勢"),
  upperText: z.string().min(1).max(60),
  lowerText: z.string().min(1).max(60),
  forkProgress: z.number().min(0.1).max(0.8).optional().default(0.35),
  upperColor: z.string().optional().default("#10B981"),
  lowerColor: z.string().optional().default("#EF4444"),
});
export type KCurveSceneProps = z.input<typeof KCurveSceneSchema>;

// 4. StatNumberScene Schema
export const StatNumberSceneSchema = BaseScenePropsSchema.extend({
  value: z.number(),
  prefix: z.string().max(20).optional().default(""),
  suffix: z.string().max(20).optional().default(""),
  unit: z.string().max(20).optional().default(""),
  label: z.string().min(1).max(80),
  subtext: z.string().max(120).optional().default(""),
  decimals: z.number().int().min(0).max(4).optional().default(0),
});
export type StatNumberSceneProps = z.input<typeof StatNumberSceneSchema>;
