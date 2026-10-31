# 0002. Hybrid Local-First with Cloud-Accelerated Stage Polymorphism

## Status
Accepted

## Context
Video generation tools are typically built either as closed cloud SaaS platforms with continuous API subscription costs and privacy trade-offs, or as pure offline desktop applications constrained by local GPU VRAM and slower inference speeds. Developers and creators need the privacy and zero cost of local hardware for experimentation, combined with the power to selectively deploy state-of-the-art cloud AI models for production quality.

## Decision
We implement a hybrid architecture with per-stage polymorphism across all 9 pipeline stages:
1. **Zero-Cost Local Baseline**: Every stage has a fully functional local implementation requiring $0 cloud spend:
   - LLM: Local Ollama
   - Voice: Local BlueMagpie (CosyVoice) / Windows SAPI
   - Image: Local ComfyUI / DirectML
   - Animation: Hardware AMF / QSV / CPU Ken Burns motion
   - Presenter: Local SadTalker / FFmpeg
   - Render: Local GPU Hardware Encoders (`h264_amf`, `h264_qsv`, `h264_nvenc`)
2. **Per-Stage Cloud Acceleration**: Any stage can be selectively overridden in project settings (`settings.stage_models[stage_name]`) to use cloud APIs (such as Google Gemini for research, Nano Banana / FLUX for images, or VoAI / ElevenLabs for voice) without changing downstream rendering code.
3. **Transparent Cost Attribution**: All cloud API calls are metered and reported in an integrated stage cost summary table against model pricing tables.

## Consequences
- **Benefits**: Users can draft and iterate entirely offline for free, then optionally pay pennies only on stages where high visual fidelity or expressiveness is needed (e.g. cloud images or cloud lip-sync).
- **Trade-offs**: Pipeline providers must maintain dual abstractions (local process runners vs asynchronous HTTP cloud clients), and ensure schema consistency across wildly differing model outputs.
