---
name: grill-with-docs
description: A relentless interview to sharpen a plan, architecture, or design while actively building and writing repo docs (GLOSSARY.md and ADRs) inline as decisions crystallise.
---

# Grill With Docs

> **Language & Localization Directive (Fix for Issue #199):**
> Conduct the grilling session — all questions, recommendations, analysis, and inline notes — in the same language the user writes in (e.g. Traditional Chinese 繁體中文 if the user writes in Chinese).
> Canonical domain terminology (e.g. ADR, GLOSSARY.md, CONTEXT.md, bounded context, ubiquitous language) can remain in English where it serves as a canonical term.

## Overview

Interview the user relentlessly about a plan, feature, or design until you reach a shared understanding, while actively building and recording the project's domain vocabulary (`GLOSSARY.md`) and architectural decisions (`docs/adr/`) directly into the repository inline during the session.

---

## 1. Grilling Discipline (The Design Tree)

Map the user's plan as a **design tree**: every decision branches into subsequent decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask *now* without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and provide your recommended answer. Then wait for the user's answers before the next round.

### Round Formatting

Format each question round clearly:

```markdown
❓ **Q1** - **<Question Title>**: <Question body with context, implications, trade-offs, and options>

➡️ <Your recommended answer>

---

❓ **Q2** - **<Question Title>**: <Question body with context, implications, trade-offs, and options>

➡️ <Your recommended answer>
```

### Grilling Rules
1. **"Yes" accepts recommendation**: Word each question so that the user replying "yes" accepts your recommended answer.
2. **Finding facts is your job**: When a question needs facts from the codebase, environment, or dependencies, inspect the codebase yourself (grep, read files). Never ask the user for information you can discover yourself.
3. **Decisions belong to the user**: Put architectural, product, and design forks to the user with clear pros/cons and a recommendation.
4. **Iterative tree expansion**: Each round of user answers settles decisions, pushing the frontier outward and unblocking downstream questions for the next round.
5. **No implementation during grilling**: Do not write feature code while grilling. The goal is sharp clarity and documented decisions first.

---

## 2. Active Domain Modeling & Inline Documentation

While grilling, actively capture and sharpen domain language and hard decisions into the repository:

### A. Inline GLOSSARY.md Updates
When a domain term resolves during conversation:
- Immediately create or update `GLOSSARY.md` in the repository root (or context root). Do NOT wait until the end.
- Define what the term IS (tight 1-2 sentences), avoiding implementation detail.
- Be opinionated: list terms to avoid under `_Avoid_`.

Example format:
```markdown
# Glossary

## Language

**Order**:
A customer's confirmed request to purchase one or more items.
_Avoid_: Purchase, transaction, cart

**Presenter Scene**:
A storyboard video scene where a synthetic human avatar speaks on-screen.
_Avoid_: Talking head, face clip
```

### B. ADRs (Architecture Decision Records)
Create an ADR in `docs/adr/000X-<slug>.md` ONLY when all three criteria are met:
1. **Hard to reverse**: The cost of changing later is high.
2. **Surprising without context**: A future engineer would ask "why was it done this way?"
3. **Real trade-off**: Deliberately chosen among viable alternatives.

Example format (`docs/adr/0001-video-transition-multithreading.md`):
```markdown
# Use 8-thread Ultrafast intermediate rendering for scene transitions

We switch intermediate transition rendering from 2 threads veryfast to 8 threads ultrafast. This utilizes the 16 E-cores/P-cores of the i7-13700K without thermal throttling, cutting transition join time by ~65% while caching intermediate mp4 clips.
```

---

## 3. Session Completion

The grilling session is complete when:
- The frontier is empty: every branch of the design tree has been explored.
- Key domain terms are captured in `GLOSSARY.md`.
- Critical trade-offs are recorded as ADRs in `docs/adr/`.
- The user confirms shared understanding.
