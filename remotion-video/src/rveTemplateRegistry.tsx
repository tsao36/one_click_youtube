import React from "react";
import AnimatedList from "./rve-templates/animated-list";
import AnimatedText from "./rve-templates/animated-text";
import AreaChart from "./rve-templates/area-chart";
import BlindsTransition from "./rve-templates/blinds-transition";
import BokehCircles from "./rve-templates/bokeh-circles";
import BounceText from "./rve-templates/bounce-text";
import BubblePopText from "./rve-templates/bubble-pop-text";
import CameraShake from "./rve-templates/camera-shake";
import CardFlip from "./rve-templates/card-flip";
import ChapterTitle from "./rve-templates/chapter-title";
import ChartAnimation from "./rve-templates/chart-animation";
import CinematicTitleIntro from "./rve-templates/cinematic-title-intro";
import CircularProgress from "./rve-templates/circular-progress";
import ClockWipe from "./rve-templates/clock-wipe";
import ComparisonChart from "./rve-templates/comparison-chart";
import CountdownIntro from "./rve-templates/countdown-intro";
import CountdownTimer from "./rve-templates/countdown-timer";
import CreditsRoll from "./rve-templates/credits-roll";
import CrossDissolve from "./rve-templates/cross-dissolve";
import DonutChart from "./rve-templates/donut-chart";
import EndCard from "./rve-templates/end-card";
import FadeThroughBlack from "./rve-templates/fade-through-black";
import FilmBurn from "./rve-templates/film-burn";
import FloatingBubbleText from "./rve-templates/floating-bubble-text";
import GalleryGrid from "./rve-templates/gallery-grid";
import GeometricPatterns from "./rve-templates/geometric-patterns";
import GlitchText from "./rve-templates/glitch-text";
import GradientShift from "./rve-templates/gradient-shift";
import GridPulse from "./rve-templates/grid-pulse";
import ImageCarousel from "./rve-templates/image-carousel";
import ImageComparisonSlider from "./rve-templates/image-comparison-slider";
import ImageZoomReveal from "./rve-templates/image-zoom-reveal";
import IrisTransition from "./rve-templates/iris-transition";
import KenBurns from "./rve-templates/ken-burns";
import LetterboxReveal from "./rve-templates/letterbox-reveal";
import LineChart from "./rve-templates/line-chart";
import LiquidWave from "./rve-templates/liquid-wave";
import LogoBlurReveal from "./rve-templates/logo-blur-reveal";
import LogoBounceDrop from "./rve-templates/logo-bounce-drop";
import LogoFadeReveal from "./rve-templates/logo-fade-reveal";
import LogoGlitchReveal from "./rve-templates/logo-glitch-reveal";
import LogoScaleRotate from "./rve-templates/logo-scale-rotate";
import LogoSpinReveal from "./rve-templates/logo-spin-reveal";
import LogoSplitReveal from "./rve-templates/logo-split-reveal";
import LogoStrokeDraw from "./rve-templates/logo-stroke-draw";
import LogoTypewriter from "./rve-templates/logo-typewriter";
import LowerThird from "./rve-templates/lower-third";
import MasonryGallery from "./rve-templates/masonry-gallery";
import MatrixRain from "./rve-templates/matrix-rain";
import MorphTransition from "./rve-templates/morph-transition";
import NoiseGrain from "./rve-templates/noise-grain";
import NotificationPop from "./rve-templates/notification-pop";
import ParallaxPan from "./rve-templates/parallax-pan";
import ParticleExplosion from "./rve-templates/particle-explosion";
import PhotoStack from "./rve-templates/photo-stack";
import PictureInPicture from "./rve-templates/picture-in-picture";
import PieChart from "./rve-templates/pie-chart";
import PixelTransition from "./rve-templates/pixel-transition";
import PolaroidFrame from "./rve-templates/polaroid-frame";
import PoppingText from "./rve-templates/popping-text";
import ProgressBars from "./rve-templates/progress-bars";
import ProgressSteps from "./rve-templates/progress-steps";
import PulsingText from "./rve-templates/pulsing-text";
import PushTransition from "./rve-templates/push-transition";
import QuoteCard from "./rve-templates/quote-card";
import RotatingCarousel from "./rve-templates/rotating-carousel";
import SlideText from "./rve-templates/slide-text";
import SlideWipe from "./rve-templates/slide-wipe";
import SoundWave from "./rve-templates/sound-wave";
import SplitScreen from "./rve-templates/split-screen";
import SpotlightReveal from "./rve-templates/spotlight-reveal";
import Starfield from "./rve-templates/starfield";
import StatCounter from "./rve-templates/stat-counter";
import SubscribeReminder from "./rve-templates/subscribe-reminder";
import TextHighlight from "./rve-templates/text-highlight";
import TitleSplit from "./rve-templates/title-split";
import TypewriterSubtitle from "./rve-templates/typewriter-subtitle";
import VignettePulse from "./rve-templates/vignette-pulse";
import WhipPan from "./rve-templates/whip-pan";
import ZoomPulse from "./rve-templates/zoom-pulse";
import ZoomThrough from "./rve-templates/zoom-through";

export type RveTemplateEntry = {
  id: string;
  component: React.ComponentType<{}>;
};

export const RVE_TEMPLATE_REGISTRY: RveTemplateEntry[] = [
  { id: "RveTemplateAnimatedList", component: AnimatedList },
  { id: "RveTemplateAnimatedText", component: AnimatedText },
  { id: "RveTemplateAreaChart", component: AreaChart },
  { id: "RveTemplateBlindsTransition", component: BlindsTransition },
  { id: "RveTemplateBokehCircles", component: BokehCircles },
  { id: "RveTemplateBounceText", component: BounceText },
  { id: "RveTemplateBubblePopText", component: BubblePopText },
  { id: "RveTemplateCameraShake", component: CameraShake },
  { id: "RveTemplateCardFlip", component: CardFlip },
  { id: "RveTemplateChapterTitle", component: ChapterTitle },
  { id: "RveTemplateChartAnimation", component: ChartAnimation },
  { id: "RveTemplateCinematicTitleIntro", component: CinematicTitleIntro },
  { id: "RveTemplateCircularProgress", component: CircularProgress },
  { id: "RveTemplateClockWipe", component: ClockWipe },
  { id: "RveTemplateComparisonChart", component: ComparisonChart },
  { id: "RveTemplateCountdownIntro", component: CountdownIntro },
  { id: "RveTemplateCountdownTimer", component: CountdownTimer },
  { id: "RveTemplateCreditsRoll", component: CreditsRoll },
  { id: "RveTemplateCrossDissolve", component: CrossDissolve },
  { id: "RveTemplateDonutChart", component: DonutChart },
  { id: "RveTemplateEndCard", component: EndCard },
  { id: "RveTemplateFadeThroughBlack", component: FadeThroughBlack },
  { id: "RveTemplateFilmBurn", component: FilmBurn },
  { id: "RveTemplateFloatingBubbleText", component: FloatingBubbleText },
  { id: "RveTemplateGalleryGrid", component: GalleryGrid },
  { id: "RveTemplateGeometricPatterns", component: GeometricPatterns },
  { id: "RveTemplateGlitchText", component: GlitchText },
  { id: "RveTemplateGradientShift", component: GradientShift },
  { id: "RveTemplateGridPulse", component: GridPulse },
  { id: "RveTemplateImageCarousel", component: ImageCarousel },
  { id: "RveTemplateImageComparisonSlider", component: ImageComparisonSlider },
  { id: "RveTemplateImageZoomReveal", component: ImageZoomReveal },
  { id: "RveTemplateIrisTransition", component: IrisTransition },
  { id: "RveTemplateKenBurns", component: KenBurns },
  { id: "RveTemplateLetterboxReveal", component: LetterboxReveal },
  { id: "RveTemplateLineChart", component: LineChart },
  { id: "RveTemplateLiquidWave", component: LiquidWave },
  { id: "RveTemplateLogoBlurReveal", component: LogoBlurReveal },
  { id: "RveTemplateLogoBounceDrop", component: LogoBounceDrop },
  { id: "RveTemplateLogoFadeReveal", component: LogoFadeReveal },
  { id: "RveTemplateLogoGlitchReveal", component: LogoGlitchReveal },
  { id: "RveTemplateLogoScaleRotate", component: LogoScaleRotate },
  { id: "RveTemplateLogoSpinReveal", component: LogoSpinReveal },
  { id: "RveTemplateLogoSplitReveal", component: LogoSplitReveal },
  { id: "RveTemplateLogoStrokeDraw", component: LogoStrokeDraw },
  { id: "RveTemplateLogoTypewriter", component: LogoTypewriter },
  { id: "RveTemplateLowerThird", component: LowerThird },
  { id: "RveTemplateMasonryGallery", component: MasonryGallery },
  { id: "RveTemplateMatrixRain", component: MatrixRain },
  { id: "RveTemplateMorphTransition", component: MorphTransition },
  { id: "RveTemplateNoiseGrain", component: NoiseGrain },
  { id: "RveTemplateNotificationPop", component: NotificationPop },
  { id: "RveTemplateParallaxPan", component: ParallaxPan },
  { id: "RveTemplateParticleExplosion", component: ParticleExplosion },
  { id: "RveTemplatePhotoStack", component: PhotoStack },
  { id: "RveTemplatePictureInPicture", component: PictureInPicture },
  { id: "RveTemplatePieChart", component: PieChart },
  { id: "RveTemplatePixelTransition", component: PixelTransition },
  { id: "RveTemplatePolaroidFrame", component: PolaroidFrame },
  { id: "RveTemplatePoppingText", component: PoppingText },
  { id: "RveTemplateProgressBars", component: ProgressBars },
  { id: "RveTemplateProgressSteps", component: ProgressSteps },
  { id: "RveTemplatePulsingText", component: PulsingText },
  { id: "RveTemplatePushTransition", component: PushTransition },
  { id: "RveTemplateQuoteCard", component: QuoteCard },
  { id: "RveTemplateRotatingCarousel", component: RotatingCarousel },
  { id: "RveTemplateSlideText", component: SlideText },
  { id: "RveTemplateSlideWipe", component: SlideWipe },
  { id: "RveTemplateSoundWave", component: SoundWave },
  { id: "RveTemplateSplitScreen", component: SplitScreen },
  { id: "RveTemplateSpotlightReveal", component: SpotlightReveal },
  { id: "RveTemplateStarfield", component: Starfield },
  { id: "RveTemplateStatCounter", component: StatCounter },
  { id: "RveTemplateSubscribeReminder", component: SubscribeReminder },
  { id: "RveTemplateTextHighlight", component: TextHighlight },
  { id: "RveTemplateTitleSplit", component: TitleSplit },
  { id: "RveTemplateTypewriterSubtitle", component: TypewriterSubtitle },
  { id: "RveTemplateVignettePulse", component: VignettePulse },
  { id: "RveTemplateWhipPan", component: WhipPan },
  { id: "RveTemplateZoomPulse", component: ZoomPulse },
  { id: "RveTemplateZoomThrough", component: ZoomThrough },
];
