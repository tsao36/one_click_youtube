# Editorial Explainer Architecture — Reference Analysis

Reference: [Jim AI Notebook — 台積電，為什麼也做不出夠多的晶片？](https://www.youtube.com/watch?v=dgrSyztWz1w), inspected from the published 14:16 video on 2026-11-11.

This document extracts the transferable method. It is not a shot-for-shot recreation and does not reuse the reference's art assets.

## What the video is actually doing

The video uses a stable editorial world rather than inventing a new visual language for every sentence. A dark charcoal canvas, white editorial type, one warm question color, one green confirmation color, and one red exception color make very different evidence feel like one argument. Flat objects are treated as nouns; animation changes their state to express verbs.

The durable unit is an **argument beat**, not a decoration:

1. Ask a concrete question.
2. Ground the speaker or source.
3. Make the mechanism visible.
4. Quantify the scale or rate.
5. Reveal the limiting dependency.
6. Test an alternative or counterargument.
7. Return to evidence.
8. Synthesize the answer and local implication.

## Timestamp reverse engineering

| Time | Editorial role | Visual construction | Reusable Remotion rule |
| --- | --- | --- | --- |
| 00:00–00:20 | Hook | Brand sting, title question, compact premise cards | Use `hook`; reveal question first, then the one-line stakes statement. |
| 00:20–00:52 | Evidence + roadmap | Source excerpt, interview frame, three-part agenda | Alternate `evidence`, `identity`, then `process`; do not put every fact in one card. |
| 00:52–01:33 | Authority grounding | Speaker portraits, lower-third identity, institution comparison | Use `identity`; reserve cyan/teal for names and roles. |
| 01:33–03:10 | Mechanism | Wafer-to-die sequence, repeated machines, yield grid changing state | Use `process` and `metric`; animate accumulation, replacement, and defect state rather than moving everything continuously. |
| 03:10–04:15 | Scarce dependency | Light-wave explanation, supplier image, machine counts, missing-machine state | Use `constraint`; place the system centrally and let one failed satellite explain the bottleneck. |
| 04:15–04:59 | Quantified tension | Server stacks grow, “3× per year”, report excerpt, spending numbers | Use `metric` followed by `evidence`; one dominant number per beat. |
| 04:59–06:10 | Expert answer | Interview footage interrupts graphics, then supply-chain explanation | Reset credibility with real footage; graphics should resume only when the explanation becomes structural. |
| 06:10–08:46 | Capacity model | Supplier network, utilization gauge, equipment rows, dates and queues | Rotate `constraint`, `metric`, and `timeline`; keep the same objects and change their state. |
| 08:46–11:10 | Comparison | Map, historical timeline, two-wafer yield comparison, scale economics | Use `timeline`, `comparison`, and `metric`; compare like with like and label the axis of comparison. |
| 11:10–12:56 | Counterargument | Industry-specialization diagram, new-factory claim, memory bottleneck, forecast-vs-demand curve | Use `process`, `constraint`, and `comparison`; show why the obvious solution fails. |
| 12:56–14:00 | Synthesis | Global supply map, source return, equipment lead-time icon, Taiwan implication | Use `evidence` then `synthesis`; repeat earlier nouns so the conclusion feels earned. |

## Composition rules

- Treat the canvas as a stage with a persistent visual hierarchy: headline zone, explanatory object zone, subtitle-safe lower band, and source footer.
- Give each beat one job. A scene may explain a mechanism, show proof, or state an implication; combining all three weakens readability.
- Prefer 3–5 visible objects. Repetition expresses quantity; color/state changes express causality.
- Use entrance → build → emphasis. The template exposes these as shared timing phases instead of hand-tuning every scene.
- Use hard cuts between argument beats. Use internal motion only to explain change inside a beat.
- Keep on-screen wording shorter than narration. The picture supplies structure; subtitles supply full language.
- Reuse earlier visual nouns in the synthesis. This is visual argument closure, not ornamental continuity.
- Use interview or documentary footage as an authority reset, not as a background under dense cards.

## Template contract

`EditorialExplainerScene` accepts nine `sceneRole` values:

- `hook`: curiosity gap and stakes
- `identity`: person, institution, or source grounding
- `process`: ordered mechanism
- `metric`: one dominant quantity or rate
- `comparison`: two commensurate systems or outcomes
- `constraint`: bottleneck and dependency network
- `timeline`: causal progression over dates or phases
- `evidence`: primary-source excerpt and interpretation
- `synthesis`: final answer assembled from prior beats

All roles share the same props shape. Start from `remotion-video/examples/editorial-explainer-template.json`, replace only verified content, and render each scene to the narration-derived duration. Specialized existing scenes remain useful when a subject needs a real candlestick chart, RF packet animation, geographic scale experiment, or other domain-specific visualization.

## Subject adaptation examples

- Medicine: symptom hook → clinician identity → biological process → risk metric → treatment comparison → diagnostic bottleneck → trial evidence → patient implication.
- History: disputed question → archive identity → event process → casualty/economic scale → faction comparison → logistics constraint → chronology → primary document → modern implication.
- Business: market question → company/source identity → value chain → unit economics → competitor comparison → supply constraint → adoption timeline → filing excerpt → strategic conclusion.
- Science: phenomenon hook → researcher identity → mechanism → measured magnitude → model comparison → experimental constraint → discovery timeline → paper excerpt → explanatory synthesis.

