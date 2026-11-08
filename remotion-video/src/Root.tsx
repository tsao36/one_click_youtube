import React from "react";
import { Composition, Folder } from "remotion";
import { BranchPathwayScene } from "./BranchPathwayScene";
import { LeaderCalloutScene } from "./LeaderCalloutScene";
import { ScaleCompareScene } from "./ScaleCompareScene";
import { EvidenceHighlightScene } from "./EvidenceHighlightScene";
import { FoxHeaderScene } from "./FoxHeaderScene";
import { FoxMetricScene } from "./FoxMetricScene";
import { FoxDataListScene } from "./FoxDataListScene";
import { FoxTimelineScene } from "./FoxTimelineScene";
import {
  BranchPathwaySceneSchema,
  LeaderCalloutSceneSchema,
  ScaleCompareSceneSchema,
  EvidenceHighlightSceneSchema,
  FoxHeaderSceneSchema,
  FoxMetricSceneSchema,
  FoxDataListSceneSchema,
  FoxTimelineSceneSchema,
} from "./types";

import { FrameworkMatrixScene } from "./FrameworkMatrixScene";
import { PromptComparisonScene } from "./PromptComparisonScene";
import { ChatSimulationScene } from "./ChatSimulationScene";
import { KineticQuoteScene } from "./KineticQuoteScene";
import { WorkflowStepScene } from "./WorkflowStepScene";
import { KineticTypographyScene } from "./KineticTypographyScene";
import { CoordinateZeroScaleScene } from "./CoordinateZeroScaleScene";
import { CoordinateZeroExperimentScene } from "./CoordinateZeroExperimentScene";
import { CoordinateZeroSplitScene } from "./CoordinateZeroSplitScene";
import {
  FrameworkMatrixSceneSchema,
  PromptComparisonSceneSchema,
  ChatSimulationSceneSchema,
  KineticQuoteSceneSchema,
  WorkflowStepSceneSchema,
  KineticTypographySceneSchema,
  CoordinateZeroScaleSceneSchema,
  CoordinateZeroExperimentSceneSchema,
  CoordinateZeroSplitSceneSchema,
} from "./types";

const videoDimensions = { fps: 30, width: 1920, height: 1080 };

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* 1. Production Documentary Archetypes */}
      <Folder name="Documentary-Archetypes">
        <Composition
          id="BranchPathwayScene"
          component={BranchPathwayScene}
          schema={BranchPathwaySceneSchema}
          durationInFrames={150}
          {...videoDimensions}
          defaultProps={{
            title: "大腦訊號讀取的四條技術路線",
            subtitle: "從非侵入式到深層皮層植入的極限抉擇",
            paths: [
              {
                id: "p1",
                name: "路線 1: EEG 頭皮電極",
                category: "非侵入式",
                detail: "貼在頭皮表面，訊號受頭骨強烈濾波與衰減，只能讀取百萬神經元的模糊總和。",
                status: "eliminated",
                eliminationReason: "嚴重衰減，無法精確控制滑鼠游標",
              },
              {
                id: "p2",
                name: "路線 2: ECoG 硬腦膜下電極",
                category: "半侵入式",
                detail: "需開顱手術放置於大腦硬腦膜下方，解析度提升但仍無法捕捉單一動作電位。",
                status: "eliminated",
                eliminationReason: "無法貼近深層錐體細胞",
              },
              {
                id: "p3",
                name: "路線 3: 血管支架 Stentrode",
                category: "微創血管穿刺",
                detail: "經頸靜脈導入大腦皮質血管，免開顱但電極位置完全受限於大腦天然血管走向。",
                status: "eliminated",
                eliminationReason: "電極密度過低，位置無法自主選擇",
              },
              {
                id: "p4",
                name: "路線 4: 穿透式微電極 (Neuralink)",
                category: "深層皮質侵入",
                detail: "微米級柔性電極絲直接穿入大腦皮層第 4/5 層，以單一神經元解析度捕捉電訊號。",
                status: "selected",
                highlightTag: "NEURALINK 最終選擇",
              },
            ],
            selectedId: "p4",
            accentColor: "#00F5FF",
          }}
        />

        <Composition
          id="LeaderCalloutScene"
          component={LeaderCalloutScene}
          schema={LeaderCalloutSceneSchema}
          durationInFrames={150}
          {...videoDimensions}
          defaultProps={{
            title: "大腦皮層穿透深度與解剖層次",
            subtitle: "手術機器人如何避開微血管，將電極送入皮質錐體神經元",
            callouts: [
              {
                id: "c1",
                label: "頭皮與顱骨 (Scalp & Skull)",
                sublabel: "開出直徑約 23mm 微孔以容納 N1 植入晶片",
                anchorX: 0.35,
                anchorY: 0.22,
                boxX: 0.68,
                boxY: 0.18,
                metric: "孔徑 23mm",
                status: "normal",
              },
              {
                id: "c2",
                label: "硬腦膜微孔 (Dura Mater)",
                sublabel: "高強韌保護膜，需微米雷射或極細導針輕微切開",
                anchorX: 0.38,
                anchorY: 0.45,
                boxX: 0.68,
                boxY: 0.45,
                metric: "厚度 ~1.0mm",
                status: "normal",
              },
              {
                id: "c3",
                label: "運動皮質第 IV/V 層 (Motor Cortex)",
                sublabel: "電極絲最終著陸點，近距離監聽控制肢體運動的錐體神經元",
                anchorX: 0.42,
                anchorY: 0.72,
                boxX: 0.68,
                boxY: 0.74,
                metric: "植入深度 1.5mm",
                status: "active",
              },
            ],
            accentColor: "#00F5FF",
          }}
        />

        <Composition
          id="ScaleCompareScene"
          component={ScaleCompareScene}
          schema={ScaleCompareSceneSchema}
          durationInFrames={150}
          {...videoDimensions}
          defaultProps={{
            title: "極致尺度對比：柔性電極絲 vs 人類頭髮",
            subtitle: "直徑相差近 20 倍的微米級聚合物工藝",
            macroLabel: "人類頭髮直徑 (Human Hair)",
            macroValue: "100 μm",
            macroDesc: "肉眼可見的剛性毛髮，若強行插入大腦會引起劇烈免疫排異反應",
            microLabel: "Neuralink 柔性電極絲 (Thread)",
            microValue: "5 μm",
            microDesc: "比紅血球 (7μm) 還細，質地極為柔軟，能隨大腦在顱內自然搏動而漂移",
            ratioMultiplier: "20×",
            ratioLabel: "粗細極限差距",
            magnificationFactor: "20X OPTICAL",
            accentColor: "#00F5FF",
          }}
        />

        <Composition
          id="EvidenceHighlightScene"
          component={EvidenceHighlightScene}
          schema={EvidenceHighlightSceneSchema}
          durationInFrames={150}
          {...videoDimensions}
          defaultProps={{
            title: "手術機器人縫紉機臨床數據",
            docHeader: "NEURALINK R-1 SURGICAL ROBOT PROTOCOL",
            docDate: "REV 2024.1",
            documentExcerpt:
              "專用 R-1 手術機器人配備微米光學相機，每隔 1.5 秒插入一根比頭髮還細的柔性線，並即時自動避開腦表面微血管，全過程將神經組織創傷降至最低。",
            highlightPhrase:
              "每隔 1.5 秒插入一根比頭髮還細的柔性線，並即時自動避開腦表面微血管",
            telemetryStats: [
              { label: "穿刺週期", value: "1.5 秒 / 根", badge: "超高速" },
              { label: "單次總絲數", value: "64 根 (1024 頻道)", badge: "高頻寬" },
              { label: "血管避障精度", value: "&lt; 5 微米", badge: "自動光學追蹤" },
            ],
            accentColor: "#00F5FF",
          }}
        />
      </Folder>

      {/* 2. Neuralink Reference Audition Folder (Instant Visual Verification) */}
      <Folder name="Neuralink-Previews">
        <Composition
          id="Preview-BranchPathway"
          component={BranchPathwayScene}
          schema={BranchPathwaySceneSchema}
          durationInFrames={180}
          {...videoDimensions}
          defaultProps={{
            title: "從大腦讀訊號的四條路：為什麼選最深的那條？",
            subtitle: "Neuralink 權衡訊號解析度與手術代價的關鍵抉擇",
            paths: [
              {
                id: "p1",
                name: "路線 1: EEG 頭皮電極",
                category: "非侵入式",
                detail: "放置在頭皮外側，受阻於頭骨濾波，信噪比極低，無法單獨控制游標。",
                status: "eliminated",
                eliminationReason: "信噪比過低",
              },
              {
                id: "p2",
                name: "路線 2: ECoG 腦膜電極",
                category: "半侵入式",
                detail: "需開顱手術放置於硬腦膜下，解析度較高但仍無法識別單一動作電位。",
                status: "eliminated",
                eliminationReason: "電極無法深入皮層",
              },
              {
                id: "p3",
                name: "路線 3: 血管支架 Stentrode",
                category: "血管介入",
                detail: "微創導入頸靜脈進入運動皮質血管，免開顱但電極位置受限於天然血管分佈。",
                status: "eliminated",
                eliminationReason: "通道數與位置受限",
              },
              {
                id: "p4",
                name: "路線 4: 穿透式柔性皮層探針",
                category: "深層皮質侵入",
                detail: "微米級柔性電極絲直達大腦第 4/5 層，近距離精準監聽單一神經元放電。",
                status: "selected",
                highlightTag: "NEURALINK 選擇",
              },
            ],
            selectedId: "p4",
            accentColor: "#00F5FF",
          }}
        />

        <Composition
          id="Preview-LeaderCallout"
          component={LeaderCalloutScene}
          schema={LeaderCalloutSceneSchema}
          durationInFrames={180}
          {...videoDimensions}
          defaultProps={{
            title: "運動皮質第 IV/V 層穿透標註",
            subtitle: "手術縫紉機避開血管穿透各層大腦組織的動態引線",
            callouts: [
              {
                id: "c1",
                label: "硬腦膜 (Dura Mater)",
                sublabel: "強韌外膜，切開微米小孔以供電極穿入",
                anchorX: 0.35,
                anchorY: 0.25,
                boxX: 0.65,
                boxY: 0.22,
                metric: "微孔穿透",
                status: "normal",
              },
              {
                id: "c2",
                label: "軟腦膜血管網 (Pia Mater Vessels)",
                sublabel: "光學感測器即時偵測血管反光，導針自動計算安全路徑避開",
                anchorX: 0.38,
                anchorY: 0.5,
                boxX: 0.65,
                boxY: 0.48,
                metric: "避障安全距 20μm",
                status: "warning",
              },
              {
                id: "c3",
                label: "大腦運動皮質 (Motor Cortex)",
                sublabel: "目標深層錐體神經元放電熱區",
                anchorX: 0.42,
                anchorY: 0.75,
                boxX: 0.65,
                boxY: 0.74,
                metric: "植入深度 1.5mm",
                status: "active",
              },
            ],
            accentColor: "#00F5FF",
          }}
        />

        <Composition
          id="Preview-ScaleCompare"
          component={ScaleCompareScene}
          schema={ScaleCompareSceneSchema}
          durationInFrames={180}
          {...videoDimensions}
          defaultProps={{
            title: "極致尺度對比：5 微米柔性絲 vs 100 微米頭髮",
            subtitle: "為什麼電極絲必須比頭髮還細 20 倍？",
            macroLabel: "人類頭髮直徑 (Human Hair)",
            macroValue: "100 μm",
            macroDesc: "剛性結構，插入活體腦組織會引發嚴重發炎與膠質瘢痕包裹",
            microLabel: "Neuralink 聚合物電極絲 (Thread)",
            microValue: "5 μm",
            microDesc: "細於紅血球，柔軟如絲，隨大腦搏動漂移，大幅降低免疫反應",
            ratioMultiplier: "20×",
            ratioLabel: "直徑極限縮小",
            magnificationFactor: "20X OPTICAL",
            accentColor: "#00F5FF",
          }}
        />

        <Composition
          id="Preview-EvidenceHighlight"
          component={EvidenceHighlightScene}
          schema={EvidenceHighlightSceneSchema}
          durationInFrames={180}
          {...videoDimensions}
          defaultProps={{
            title: "手術機器人縫紉機：一秒半插一根線",
            docHeader: "SURGICAL TELEMETRY SPECIFICATION",
            docDate: "NEURALINK WHITEPAPER",
            documentExcerpt:
              "神經外科機器人以高精密度機械臂夾持鎢針，每隔 1.5 秒插入一根比頭髮還細的線，自動避開腦表面微血管，全過程將組織創傷降至最低。",
            highlightPhrase:
              "每隔 1.5 秒插入一根比頭髮還細的線，自動避開腦表面微血管",
            telemetryStats: [
              { label: "植入速度", value: "1.5 秒 / 根", badge: "自動循環" },
              { label: "總通道數", value: "1,024 Channels", badge: "64 條絲" },
              { label: "避障安全率", value: "99.8%", badge: "光學感應" },
            ],
            accentColor: "#00F5FF",
          }}
        />
        {/* 2. fOx Hsiao Signature Archetypes */}
        <Folder name="Fox-Hsiao-Archetypes">
          <Composition
            id="FoxHeaderScene"
            component={FoxHeaderScene}
            schema={FoxHeaderSceneSchema}
            durationInFrames={150}
            {...videoDimensions}
            defaultProps={{
              category: "背景脈絡",
              title: "為什麼要買新戰車？",
              subtitle: "既有戰車服役已超過半世紀，裝甲與射控早已無法因應現代戰場威脅",
              source: "資料來源：國防部公開預算書",
              accentColor: "#F87171",
              dim: 0.35,
            }}
          />

          <Composition
            id="FoxMetricScene"
            component={FoxMetricScene}
            schema={FoxMetricSceneSchema}
            durationInFrames={150}
            {...videoDimensions}
            defaultProps={{
              badge: "美軍 M1A2 SEPv3 戰鬥重量",
              value: "73.6",
              unit: "美制短噸",
              conversion: "≈ 66.8 公噸",
              description: "實際重量遠超國軍現役戰車，已逼近台灣多數公路與橋樑設計極限",
              subtext: "美制短噸 (Short Ton) 約為 907 公斤，換算公噸後仍高達 66.8 噸",
              source: "資料：美國陸軍武器手冊 / 國防安全研究院",
              accentColor: "#38BDF8",
              dim: 0.4,
            }}
          />

          <Composition
            id="FoxDataListScene"
            component={FoxDataListScene}
            schema={FoxDataListSceneSchema}
            durationInFrames={150}
            {...videoDimensions}
            defaultProps={{
              chapter: "採購清單與預算",
              title: "台灣陸軍 M1A2T 採購案主要裝備",
              items: [
                { label: "M1A2T 艾布蘭主力戰車", value: "108 輛", note: "最新客製化防護與數位射控系統" },
                { label: "M88A2 重型裝甲救濟車", value: "14 輛", note: "70 噸級戰場拖救能力" },
                { label: "M1070A1 重型裝備運輸拖車", value: "16 輛", note: "公路高速機動運載" },
              ],
              totalLabel: "總採購預算",
              totalValue: "約 20 億美元（405 億台幣）",
              source: "資料來源：國防部公開採購決標公告",
              accentColor: "#38BDF8",
              dim: 0.5,
            }}
          />

          <Composition
            id="FoxTimelineScene"
            component={FoxTimelineScene}
            schema={FoxTimelineSceneSchema}
            durationInFrames={150}
            {...videoDimensions}
            defaultProps={{
              chapter: "採購歷程",
              title: "長達 20 年的換車長跑歷程",
              startYear: "2000",
              startLabel: "陸軍首度提出採購新戰車需求",
              middleYear: "2011",
              middleLabel: "評估採購美軍庫存 M1A1",
              endYear: "2019",
              endLabel: "正式簽署發價書 (LOA)",
              subtext: "橫跨近二十年漫長建案評估，最終拍板採購全新 M1A2T",
              source: "資料來源：立法院國防委員會專題報告",
              accentColor: "#38BDF8",
              dim: 0.45,
            }}
          />
        </Folder>
        {/* 3. Modern Tech Explainer Archetypes (Gary Chen Style) */}
        <Folder name="Modern-Tech-Explainer">
          <Composition
            id="FrameworkMatrixScene"
            component={FrameworkMatrixScene}
            schema={FrameworkMatrixSceneSchema}
            durationInFrames={150}
            {...videoDimensions}
          />
          <Composition
            id="PromptComparisonScene"
            component={PromptComparisonScene}
            schema={PromptComparisonSceneSchema}
            durationInFrames={150}
            {...videoDimensions}
          />
          <Composition
            id="ChatSimulationScene"
            component={ChatSimulationScene}
            schema={ChatSimulationSceneSchema}
            durationInFrames={150}
            {...videoDimensions}
          />
          <Composition
            id="KineticQuoteScene"
            component={KineticQuoteScene}
            schema={KineticQuoteSceneSchema}
            durationInFrames={150}
            {...videoDimensions}
          />
          <Composition
            id="WorkflowStepScene"
            component={WorkflowStepScene}
            schema={WorkflowStepSceneSchema}
            durationInFrames={150}
            {...videoDimensions}
          />
          <Composition
            id="KineticTypographyScene"
            component={KineticTypographyScene}
            schema={KineticTypographySceneSchema}
            durationInFrames={150}
            {...videoDimensions}
          />
                </Folder>

        {/* 4. Coordinate Zero Geographic Lab Archetypes */}
        <Folder name="Coordinate-Zero-Geographic-Lab">
          <Composition
            id="CoordinateZeroScaleScene"
            component={CoordinateZeroScaleScene}
            schema={CoordinateZeroScaleSceneSchema}
            durationInFrames={150}
            {...videoDimensions}
            defaultProps={{
              badge: "台灣，其實比你想像中還大",
              initialTitle: "常見的世界地圖上：畫出來的大小",
              calibratedTitle: "搬到台灣身邊（同一個緯度）：真實大小",
              anchorLabel: "和台灣比",
              items: [
                {
                  id: "tw",
                  name: "台灣",
                  initialMultiplier: 1.0,
                  actualMultiplier: 1.0,
                  initialLabel: "基準",
                  actualLabel: "基準",
                  isAnchor: true,
                  customShape: "taiwan",
                  color: "#F59E0B",
                },
                {
                  id: "nl",
                  name: "荷蘭",
                  initialMultiplier: 2.3,
                  actualMultiplier: 1.0,
                  initialLabel: "×2.3",
                  actualLabel: "≈ 1倍",
                  customShape: "netherlands",
                },
                {
                  id: "dk",
                  name: "丹麥",
                  initialMultiplier: 3.2,
                  actualMultiplier: 1.2,
                  initialLabel: "×3.2",
                  actualLabel: "1.2倍",
                  customShape: "denmark",
                },
                {
                  id: "ch",
                  name: "瑞士",
                  initialMultiplier: 2.0,
                  actualMultiplier: 1.1,
                  initialLabel: "×2.0",
                  actualLabel: "1.1倍",
                  customShape: "switzerland",
                },
                {
                  id: "be",
                  name: "比利時",
                  initialMultiplier: 1.8,
                  actualMultiplier: 0.85,
                  initialLabel: "×1.8",
                  actualLabel: "0.85倍",
                  isTargetFocus: true,
                  customShape: "belgium",
                },
              ],
              accentColor: "#0D9488",
              dim: 0.15,
            }}
          />
          <Composition
            id="CoordinateZeroExperimentScene"
            component={CoordinateZeroExperimentScene}
            schema={CoordinateZeroExperimentSceneSchema}
            durationInFrames={150}
            {...videoDimensions}
            defaultProps={{
              experimentNo: "03",
              experimentBadge: "實驗",
              title: "俄羅斯 vs 非洲",
              subtitle: "把俄羅斯搬到赤道做真實面積對比",
              gaugeLabel: "放大倍率",
              currentMagnification: "×4.9",
              gaugePointerPosition: 0.58,
              measurementHeader: "量測",
              measurementTag: "地圖上",
              measurementFormula: "俄羅斯 = 非洲 × 2.5",
              measurementSubtext: "高緯度嚴重拉伸，赤道處才是真實物理尺度",
              accentColor: "#EF4444",
              dim: 0.15,
            }}
          />
          <Composition
            id="CoordinateZeroSplitScene"
            component={CoordinateZeroSplitScene}
            schema={CoordinateZeroSplitSceneSchema}
            durationInFrames={150}
            {...videoDimensions}
            defaultProps={{
              verdictBadge: "各對一半",
              badgeColor: "#2563EB",
              leftCard: {
                tag: "彼得斯說對的",
                tagColor: "#EF4444",
                title: "高爾—彼得斯視角",
                caption: "赤道附近，看起來比較小",
                imgSrc: "",
              },
              rightCard: {
                tag: "製圖學家說對的",
                tagColor: "#0D9488",
                title: "麥卡托現代製圖視角",
                caption: "放大的規則：只看緯度",
                imgSrc: "",
              },
              summary: "地圖從來不只是幾何線條，而是不同時代航海與政治意圖的投影抉擇",
              accentColor: "#0D9488",
              dim: 0.15,
            }}
          />
        </Folder>
      </Folder>
    </>
  );
};
