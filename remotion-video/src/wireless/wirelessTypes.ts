import { z } from "zod";

export const WirelessDeviceRoleSchema = z.enum([
  "ap",
  "sta",
  "laptop",
  "smartphone",
  "bt_controller",
  "headphones",
  "iot",
]);
export type WirelessDeviceRole = z.infer<typeof WirelessDeviceRoleSchema>;

export const FrameCategorySchema = z.enum([
  "management",
  "control",
  "data",
]);
export type FrameCategory = z.infer<typeof FrameCategorySchema>;

export const ProtocolFamilySchema = z.enum([
  "wifi_80211",
  "ble",
  "bt_classic",
]);
export type ProtocolFamily = z.infer<typeof ProtocolFamilySchema>;

export const SignalStateSchema = z.enum([
  "ok",
  "collision",
  "lost",
  "retrying",
  "coex_blocked",
  "mlo_switch_pause",
]);
export type SignalState = z.infer<typeof SignalStateSchema>;

export const MloModeSchema = z.enum(["none", "str", "emlsr"]);
export type MloMode = z.infer<typeof MloModeSchema>;

export const WirelessDeviceSchema = z.object({
  id: z.string(),
  name: z.string(),
  role: WirelessDeviceRoleSchema,
  x: z.number().min(0).max(100), // X percentage (0-100)
  y: z.number().min(0).max(100), // Y percentage (0-100)
  mac: z.string().optional().default(""),
  status: z.enum(["idle", "transmitting", "receiving", "interfered", "backoff", "roaming"]).default("idle"),
  activeBand: z.enum(["2.4GHz", "5GHz", "6GHz", "dual", "tri"]).default("2.4GHz"),
  mloMode: MloModeSchema.optional().default("none"),
  sublabel: z.string().optional().default(""),
});
export type WirelessDevice = z.infer<typeof WirelessDeviceSchema>;

export const RadioEventSchema = z.object({
  id: z.string(),
  startFrame: z.number().min(0),
  durationFrames: z.number().min(1),
  protocol: ProtocolFamilySchema,
  frameCategory: FrameCategorySchema,
  frameSubtype: z.string(), // e.g., "Beacon", "ProbeReq", "ADV_IND", "CIS_DATA", etc.
  sourceId: z.string(),
  targetId: z.string(), // device id or "broadcast"
  channel: z.union([z.number(), z.string()]), // e.g. 1, 6, 37, "5G-Ch36", "6G-Ch1"
  frequencyMhz: z.number(), // e.g. 2412, 2437, 2402, 5180, 6115
  bandwidthMhz: z.number().optional().default(20), // 2 for BLE, 20/40/80/160/320 for Wi-Fi
  linkId: z.number().optional().default(0), // 0 or 1 for Wi-Fi 7 MLO links
  signalState: SignalStateSchema.optional().default("ok"),
  rssiDbm: z.number().optional().default(-50),
  annotation: z.string().optional().default(""),
  // Real trace / PCAP metadata
  metadata: z.record(z.string(), z.any()).optional().default({}),
  unavailableFields: z.array(z.string()).optional().default([]),
});
export type RadioEvent = z.infer<typeof RadioEventSchema>;

export const NarrativeBeatSchema = z.object({
  atFrame: z.number().min(0),
  headline: z.string(),
  detail: z.string(),
  highlightDeviceIds: z.array(z.string()).optional().default([]),
  calloutType: z.enum(["wifi", "ble", "coex", "mlo", "csma", "roam"]).optional().default("wifi"),
});
export type NarrativeBeat = z.infer<typeof NarrativeBeatSchema>;

export const WirelessScenePropsSchema = z.object({
  badge: z.string().optional().default("WIRELESS SPECTRUM ENGINE"),
  title: z.string().default("Wi-Fi & Bluetooth Traffic Visualizer"),
  subtitle: z.string().optional().default("Real-time physical layer and packet protocol choreography"),
  mode: z.enum(["simplified", "trace_replay"]).default("simplified"),
  devices: z.array(WirelessDeviceSchema),
  events: z.array(RadioEventSchema),
  narrativeBeats: z.array(NarrativeBeatSchema).optional().default([]),
  showSpectrumTimeline: z.boolean().optional().default(true),
  showSequenceDiagram: z.boolean().optional().default(true),
  showCoexMonitor: z.boolean().optional().default(true),
  showMloDualLinks: z.boolean().optional().default(false),
  timeScale: z.number().optional().default(1.0),
  accentColor: z.string().optional().default("#06B6D4"),
  bgSrc: z.string().optional().default(""),
  dim: z.number().min(0).max(1).optional().default(0.7),
  captionAudioSrc: z.string().optional().default(""),
});
export type WirelessSceneProps = z.infer<typeof WirelessScenePropsSchema>;
