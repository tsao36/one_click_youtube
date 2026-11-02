# 0007. Fail-Fast Quota Guard on Cloud Credit Depletion

Date: 2026-11-02  
Status: Accepted

## Context
High-fidelity short drama video generation relies on cloud GPU API providers (such as MiniMax Video 01, Hedra Character-2 Lip-Sync, Fal.ai, and commercial TTS engines). During large-batch generation or long video renders, account credit balance or quota can be exhausted mid-pipeline.

In previous designs, the pipeline attempted silent fallback cascades:
- If high-grade dynamic video generation failed due to credit exhaustion, it would silently downgrade to placeholder animations or low-quality fallback talking-head avatars.
- This resulted in broken user expectations: users would wait through a 30-minute render only to discover that the final video had lost its cinematic character dynamics, reverted to robotic static avatars, or produced mismatched scene visuals.
- Furthermore, silent downgrades wasted compute, time, and downstream tokens on an unacceptable product.

## Decision
We established a strict **Fail-Fast Quota Guard** architectural policy across all cloud generation stages:

1. **Explicit Balance & Depletion Interception**:
   - Any API error signaling insufficient credits, quota exhaustion, or depleted balances (e.g., HTTP 402 Payment Required, `balance_depleted`, `insufficient_credits`, `quota_exceeded`, `credit_exhausted`) is trapped immediately at the provider boundary.
   - The provider raises a specialized, non-retryable `CloudCreditDepletedError`.

2. **Immediate Pipeline Halt (No Silent Downgrade)**:
   - When a `CloudCreditDepletedError` is caught during Stage 5 (Images/Video) or Stage 7 (Lip-Sync Animation), the pipeline **MUST NOT** downgrade to silent low-tier fallback generators.
   - The pipeline immediately halts execution, sets the current stage to `Status.FAILED`, and marks the project state as `failed`.

3. **High-Visibility UI Warning Notification**:
   - The pipeline surfaces a prominent, human-readable error banner in the activity log and Studio UI:
     `⚠️ [雲端餘額不足警告] 服務商「{provider_name}」餘額已耗盡或配額不足。管線已自動停止生成以防止品質降級，請充值後點擊「重新執行此階段」。`
   - Preserves all upstream stage assets (research, script, audio takes, canonical anchor portraits) intact so that after recharging, the user can resume or re-run directly from the failed stage without restarting from scratch.

## Consequences
- **Pros**: Protects production quality by eliminating degraded, unintended fallback videos. Avoids wasting remaining cloud credits on unviable downstream stages. Provides instant, unambiguous feedback so creators know exactly which provider needs a balance top-up.
- **Cons**: Requires human intervention to recharge account balances before the video can finish rendering.
