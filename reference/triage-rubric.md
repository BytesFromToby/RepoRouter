# reference/triage-rubric.md

How the operator scores a **confirmed bug**'s priority. Priority is assigned only after a
defect is confirmed (repro sufficient, behavior contradicts spec). Questions, features,
docs, and duplicates do not get a P-level.

## The four levels

### P0 — Drop everything
Ship-blocker. Any one of these qualifies:
- **Data loss or corruption** — the tool destroys, mangles, or silently drops user data.
- **Security** — (note: security never reaches this rubric; it escalates at Step 3. Listed
  here only so the severity ordering is complete.)
- **Broken install / build / startup** — users cannot get the current release running at all.
- **Core feature fully broken, no workaround** — the main thing the project exists to do
  does not work for the common case.

### P1 — This release
- Core feature broken for a **common** input or configuration.
- A workaround exists but is painful, non-obvious, or data-risky.
- Affects many users (judging by the issue, linked dupes, reactions).

### P2 — Soon / backlog
- Non-core feature broken, **or** a real bug behind an easy, documented workaround.
- Edge-case input that most users won't hit.
- Degraded but functional behavior.

### P3 — Whenever
- Cosmetic (typo in output, off-by-one in a log line, formatting).
- Documentation-only.
- Rare, marginal, or theoretical.

## Modifiers

- **Regression** (CHANGELOG shows it worked in a prior release, broke since) → **+1 level**
  (P2 becomes P1, etc.). A regression is more urgent than a long-standing bug because it
  broke a promise the project already shipped.
- **Crash with a clean workaround** → cap at P2.
- **Affects only an unsupported environment** (per spec's supported-platforms list) → cap
  at P3, and consider whether it's `invalid` instead.

## Tie-breakers

When a bug sits between two levels, ask in order:
1. Can a user lose data? → at least P1, usually P0.
2. Can a new user not get started at all? → at least P1.
3. Is there a workaround a non-expert could find? → at most P2.
4. Would most users ever hit this? → if no, P3.

## What priority is NOT

Priority is the operator's **recommendation**, surfaced in the draft for the maintainer.
It is not a commitment, an SLA, or a promise in the public reply. The drafted public
comment never states a P-level — that's internal signal only.
