export const EDITORIAL_EXPLAINER_ROLES = [
  "hook",
  "identity",
  "process",
  "metric",
  "comparison",
  "constraint",
  "timeline",
  "evidence",
  "synthesis",
] as const;

export type EditorialExplainerRole = (typeof EDITORIAL_EXPLAINER_ROLES)[number];

export const editorialExplainerTheme = {
  canvas: "#090D12",
  panel: "rgba(20, 27, 36, 0.92)",
  panelSoft: "rgba(20, 27, 36, 0.68)",
  text: "#F6F7F9",
  muted: "#AAB3C0",
  question: "#F59E0B",
  positive: "#43D39E",
  negative: "#FF6B6B",
  identity: "#42C7D9",
  line: "rgba(255, 255, 255, 0.16)",
} as const;

export const editorialExplainerTiming = {
  enterFrames: 14,
  buildStartFrame: 12,
  itemStaggerFrames: 7,
  emphasisStartFrame: 42,
  exitFrames: 10,
} as const;

export const editorialExplainerRoleGuide: Record<
  EditorialExplainerRole,
  { purpose: string; preferredBeatSeconds: [number, number] }
> = {
  hook: { purpose: "Open a curiosity gap and state the stakes", preferredBeatSeconds: [4, 8] },
  identity: { purpose: "Ground a person, institution, or source", preferredBeatSeconds: [4, 7] },
  process: { purpose: "Show an ordered mechanism as accumulating states", preferredBeatSeconds: [6, 12] },
  metric: { purpose: "Make one quantity or rate visually dominant", preferredBeatSeconds: [4, 8] },
  comparison: { purpose: "Contrast two systems, outcomes, or scenarios", preferredBeatSeconds: [5, 10] },
  constraint: { purpose: "Expose a bottleneck, dependency, or failed node", preferredBeatSeconds: [6, 12] },
  timeline: { purpose: "Turn dates or phases into causal progression", preferredBeatSeconds: [6, 12] },
  evidence: { purpose: "Show the claim's documentary basis", preferredBeatSeconds: [5, 10] },
  synthesis: { purpose: "Recombine prior facts into the final answer", preferredBeatSeconds: [5, 9] },
};

