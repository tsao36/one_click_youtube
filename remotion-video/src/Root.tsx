import { Composition, Folder } from "remotion";
import { HelloWorld } from "./HelloWorld";
import { Logo } from "./HelloWorld/Logo";
import { Title } from "./HelloWorld/Title";
import { TechCard } from "./TechCard";
import { MinimalistCard } from "./MinimalistCard";
import { CinemaImpactCard } from "./CinemaImpactCard";
import { TitleScene } from "./TitleScene";
import { GridCompareScene } from "./GridCompareScene";
import { KCurveScene } from "./KCurveScene";
import { StatNumberScene } from "./StatNumberScene";
import {
  TitleSceneSchema,
  GridCompareSceneSchema,
  KCurveSceneSchema,
  StatNumberSceneSchema,
} from "./types";

// Each <Composition> is an entry in the sidebar!

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Folder name="Elements">
        <Composition
          id="Logo"
          component={Logo}
          durationInFrames={150}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            logoColor1: "#91EAE4",
            logoColor2: "#86A8E7",
          }}
        />
        <Composition
          id="Title"
          component={Title}
          durationInFrames={115}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            titleText: "Welcome to Remotion",
            titleColor: "#000000",
          }}
        />
      </Folder>
      <Composition
        id="HelloWorld"
        component={HelloWorld}
        durationInFrames={150}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          titleText: "Welcome to Remotion",
          titleColor: "#000000",
        }}
      />
      {/* 1. Cyberpunk / Neon Glassmorphic Data Card */}
      <Composition
        id="TechCard"
        component={TechCard as any}
        durationInFrames={120}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          category: "BREAKING ANALYSIS",
          headline: "WiFi 7 關鍵變革：極致吞吐量與低延遲突破",
          metric: "46 Gbps",
          metricLabel: "峰值傳輸率",
          subtext: "相比 WiFi 6 提供 4.8 倍峰值傳輸速度與 MLO 多鏈路聚合",
          accentColor: "#00F5FF",
        }}
      />
      {/* 2. Swiss Typographic / Clean Editorial Minimalist Card */}
      <Composition
        id="MinimalistCard"
        component={MinimalistCard as any}
        durationInFrames={120}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          category: "SWISS EDITORIAL",
          headline: "極致極簡：關鍵數據與專業排版圖卡",
          metric: "99.9%",
          metricLabel: "傳輸穩定度",
          subtext: "專為乾淨俐落、高可讀性的學術與深度知識類影片打造",
          accentColor: "#10b981",
        }}
      />
      {/* 3. Bold Cinematic / Blockbuster High-Contrast Impact Card */}
      <Composition
        id="CinemaImpactCard"
        component={CinemaImpactCard as any}
        durationInFrames={120}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          category: "CINEMATIC SPOTLIGHT",
          headline: "電影巨幕級：高對比金曜震撼視覺圖卡",
          metric: "4.8x",
          metricLabel: "效能暴增",
          subtext: "強烈動態縮放與金曜質感，適合高張力重大情節與精彩時刻",
          accentColor: "#f59e0b",
        }}
      />
      {/* 4. AI Motion Graphics: TitleScene */}
      <Composition
        id="TitleScene"
        component={TitleScene as any}
        schema={TitleSceneSchema}
        durationInFrames={150}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          title: "核心結論：經濟成長與薪資差距",
          subtitle: "深度剖析全球化與自動化如何重塑財富分配",
          category: "重點結論",
          accentColor: "#3B82F6",
          animationStyle: "fade_slide",
          bgSrc: "",
          dim: 0.75,
        }}
      />
      {/* 5. AI Motion Graphics: GridCompareScene */}
      <Composition
        id="GridCompareScene"
        component={GridCompareScene as any}
        schema={GridCompareSceneSchema}
        durationInFrames={150}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          leftTitle: "資產持有者",
          leftBody: "享受股市與房地產增值紅利，資本報酬率遠高於經濟成長率。",
          rightTitle: "薪資所得者",
          rightBody: "實質薪資成長停滯，承受通膨壓力與生活成本激增。",
          comparisonLabel: "VS",
          leftColor: "#3B82F6",
          rightColor: "#EF4444",
          accentColor: "#3B82F6",
          bgSrc: "",
          dim: 0.8,
        }}
      />
      {/* 6. AI Motion Graphics: KCurveScene */}
      <Composition
        id="KCurveScene"
        component={KCurveScene as any}
        schema={KCurveSceneSchema}
        durationInFrames={150}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          title: "K 型兩極分化軌跡",
          upperText: "高科技與頂尖資本 (持續飆升)",
          lowerText: "傳統製造與一般勞工 (停滯落後)",
          forkProgress: 0.35,
          upperColor: "#10B981",
          lowerColor: "#EF4444",
          accentColor: "#10B981",
          bgSrc: "",
          dim: 0.8,
        }}
      />
      {/* 7. AI Motion Graphics: StatNumberScene */}
      <Composition
        id="StatNumberScene"
        component={StatNumberScene as any}
        schema={StatNumberSceneSchema}
        durationInFrames={150}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          value: 2000,
          prefix: "超過",
          suffix: "",
          unit: "億美元",
          label: "四大科技巨頭年度資本支出",
          subtext: "微軟、Google、Meta 與亞馬遜合計投資金額創下歷史新高",
          decimals: 0,
          accentColor: "#F59E0B",
          bgSrc: "",
          dim: 0.75,
        }}
      />
    </>
  );
};
