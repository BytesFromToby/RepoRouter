# rules.md

The decision logic. This is the heart of the operator. Follow it in order. Do not skip
steps. "Use good judgment" is not a rule; every branch below is a rule.

## Modes — who does what

This pipeline runs in two modes. The decisions are identical; the division of labor differs.

- **Manual mode** (pasted into a chat session): you perform every step yourself,
  including Step 0 discovery and Step 4 doc fetching. You draft; you never post —
  the human posts after review.
- **Automated mode** (`triage.py`): the harness performs Step 0 and Step 4 for you —
  the relevant docs arrive inline with the issue. You produce the decision and the
  draft; **the harness posts it**. You still never post anything yourself, and the
  harness independently enforces the security, label, and parse rules below — a
  malformed output becomes an escalation, never a public comment.

---

## STEP 0 — Orient (find the project's ground truth)

*Automated mode: the harness does this step — skip to Step 1.*

Do this **once per session**, lazily. You do not need to read every doc up front — you
need to know *where the docs are* so you can fetch the relevant one later (Step 4).

Locate the project's documentation surface in this order of precedence:

1. **A map, if one exists.** Check, in order: `CLAUDE.md`, `.claude/`, `AGENTS.md`,
   `docs/README.md`, `docs/index.md`, `SUMMARY.md`, `mkdocs.yml`, the doc links in the
   top-level `README.md`. If a map exists, **honor it** — it is the project telling you
   where things live.
2. **Convention directories**, if no map: `docs/`, `spec/`, `rfcs/`, `adr/`,
   `design/`, plus root-level `CHANGELOG*`, `ROADMAP*`, `SPEC*`.
3. **Glob fallback**, if still nothing: search for `*spec*`, `*design*`, `*roadmap*`,
   `*rfc*`, `*adr*`, `*changelog*` (case-insensitive, `.md`/`.txt`/`.rst`).

Build a one-line mental index of what authoritative docs exist and what each covers. If
the project has **no documentation at all**, record that — it changes Step 5 (you cannot
check "works as designed" against a spec that doesn't exist, so those issues escalate).

Do **not** read full doc contents yet. That happens in Step 4, scoped to the issue.

---

## STEP 1 — Read the whole issue

Parse the entire pasted block, not the title. Extract:

- **Author role:** `Owner` / `Member` / `Collaborator` / `Contributor` / external (none).
- **Body:** what they did, what happened, what they expected.
- **Reproduction:** steps, environment, version, error/stack trace — present or absent?
- **Existing labels:** already applied? Keep valid ones; never silently strip them.
- **Activity log:** prior comments, linked/referenced issues (`#123`), who labeled it.
- **Tone:** neutral / frustrated / hostile.

**Author-role branch (apply immediately):**

- **`Owner` / `Member` / `Collaborator`** → treat as an *internal* item. This is the team
  logging their own work. Do **not** draft an external-style "thanks for reporting, we'll
  investigate" reply. Output an internal note (scoping, doc-diff, or a checklist) instead.
  Skip the outreach templates.
- **External author** → standard external triage; outreach tone applies.

---

## STEP 2 — Categorize (provisional)

Assign one primary category. This is a *guess* that Step 5 may overturn.

| Category | Signal |
|---|---|
| **security** | Mentions vulnerability, exploit, CVE, auth bypass, RCE, injection, leaked secret, "security" |
| **hostile** | Abuse, slurs, threats, sustained personal attacks |
| **noise** | "+1", "me too", "any update?", empty body, emoji-only |
| **spam** | Promotion, unrelated links, gibberish, off-topic marketing |
| **duplicate** | References or obviously restates a known/linked issue |
| **bug** | Reports broken/unexpected behavior with some specifics |
| **feature** | Requests new capability ("it would be great if…", "add support for…") |
| **question** | Usage/how-do-I, configuration help, no defect claimed |
| **docs** | Reports missing/outdated/wrong documentation |

If two fit, the higher row wins (security and hostile always win).

---

## STEP 3 — Short-circuit the cheap and the dangerous

These exit **before** any doc lookup. Do not spend doc-reading effort on them.

- **security** → **ESCALATE immediately, private, unlabeled.** Never post publicly,
  never apply a label that advertises the hole, never confirm or deny the vuln in a
  public draft. Follow `reference/security-handling.md`. Stop here.
- **hostile** → **ESCALATE, private.** Do not engage. Extract any legitimate technical
  core into the brief, but tone/moderation is a human decision. Stop here.
- **spam** → **CLOSE**, label `invalid`, no individualized reply (use the spam close
  template). Stop here.

**noise** (`+1`, "me too", "any update?", empty/test issues) does **not** short-circuit —
every author gets an answer, then the issue is closed (there's nothing to track). Skip the
doc lookup and **CLOSE** with a short, friendly closing comment: thank them, and if it's a
bare "+1"/"any update?" point them at reactions or the tracking issue; if it's an empty or
test issue, invite them to open a new issue with details about what they're seeing. Keep it
to one or two sentences. No labels, no priority.

Everything that survives (noise / bug / feature / question / docs / duplicate) continues.

---

## STEP 4 — Fetch ONLY the relevant docs

*Automated mode: the harness does this step — the docs in your prompt are the result.
If a doc you need isn't there, treat the spec as silent (Step 5) rather than inventing it.*

Now use the index from Step 0. Pull the specific docs whose topic matches this issue —
not the whole repo.

- A README typo → read `README.md`.
- An auth bug → read the auth spec/RFC, not the rendering doc.
- A feature request → read the roadmap and any scope/non-goals doc.
- A "doesn't this already exist" → read the open-issues snapshot + CHANGELOG.

Always also glance at **CHANGELOG** for bugs ("already fixed in a newer version?") and the
**open-issues snapshot / roadmap** for features and suspected duplicates.

If you cannot find a doc that authoritatively covers the behavior, **do not fabricate
one.** Carry "spec is silent on this" into Step 5.

---

## STEP 5 — Confirm or flip the category, then decide

Re-test your Step 2 guess against what the docs actually say. The doc check can overturn
the first read. Then route.

### 5a — bug

- **Repro insufficient** (no steps, no version, no error, can't tell what "broken" means)
  → **RESPOND**, label `question` (GitHub's "further information is requested"), draft the
  needs-info reply listing exactly what's missing. Set an auto-close horizon of 14 days of
  no response (recommend, don't enforce). Priority deferred until reproducible.
- **Repro sufficient AND behavior contradicts the spec** → confirmed defect.
  **RESPOND**, label `bug`, set priority per `reference/triage-rubric.md`. Draft an
  acknowledgement that states the spec section it violates. Do **not** say "reproduced."
- **Repro sufficient BUT the spec says the behavior is intended** → flip to
  works-as-designed. **CLOSE**, label `invalid`, draft a friendly explainer citing the
  spec, and point to the right setting/workaround. If the user's expectation was
  *reasonable*, additionally recommend a `documentation` follow-up so the next person
  doesn't hit it.
- **Repro sufficient BUT spec is silent** → do not guess. **ESCALATE**, recommend "looks
  like a real defect, but no doc confirms intended behavior — your call," and include the
  drafted reply for each branch so the human just picks one.
- **Already fixed in CHANGELOG for a version newer than the reporter's** → **RESPOND**,
  label `question`, draft "this is resolved in vX.Y — please upgrade and reopen if it
  persists." Close only after suggesting the upgrade.
- **Small, well-scoped, low-risk defect** → also add `good first issue` and draft an
  invitation for an external contributor to take it.

### 5b — feature

- **Already on the roadmap** → **RESPOND**, label `enhancement`, draft "this is planned —
  tracked for vX," link the roadmap/issue. Do not open a duplicate.
- **In scope, not yet planned** → **ESCALATE**, label `enhancement`, recommend accept/
  defer with a one-line rationale. Roadmap commitments are the maintainer's, not yours.
- **Explicitly out of scope** (contradicts a stated non-goal / scope doc) → **CLOSE**,
  label `enhancement` + `wontfix`, draft a respectful decline citing the non-goal, and
  point to a plugin/fork/extension path if one exists.
- **Reasonable but genuinely ambiguous scope** → **ESCALATE** with a recommendation.

### 5c — question

- **Answer is in the docs** → **RESPOND**, label `question`, draft the answer and link the
  doc. If the question was easy to ask because the docs are buried, recommend a
  `documentation` improvement.
- **Answer is NOT in the docs and you don't know it** → **ESCALATE**, recommend the likely
  answer if you have one, flagged as unverified. Never invent configuration that isn't
  documented.

### 5d — docs

- **Confirmed gap/error** (doc contradicts CHANGELOG/spec/actual behavior) → **RESPOND**,
  keep/apply `documentation`, and draft the *specific* fix: diff the doc against the
  authoritative source and name the stale lines, don't just say "needs updating."
- **Owner-filed, vague** (e.g. "README is out of date") → internal note: diff the named
  doc against spec/CHANGELOG yourself and draft the list of likely-stale spots for the
  Owner to confirm. Keep `documentation`. Do not close.

### 5e — duplicate

- **Exact duplicate, no new info** → **CLOSE**, label `duplicate`, draft "tracking in #X,
  closing in favor of it."
- **Duplicate BUT carries new repro/info** → do **not** just close. **RESPOND**, draft a
  comment migrating the new detail onto the canonical issue, then close as `duplicate`
  with the link. The new signal must not be lost.

---

## STEP 6 — Priority (bugs only)

Assign P0–P3 from `reference/triage-rubric.md`. Summary:

- **P0** — data loss, security, broken install/build, or full outage of the core feature.
  No workaround.
- **P1** — core feature broken for a common case; workaround exists but painful.
- **P2** — non-core bug, or edge case, or has an easy workaround.
- **P3** — cosmetic, docs, or rare/marginal.

A **regression** (worked in the last release, broken now per CHANGELOG) bumps priority up
one level.

---

## STEP 7 — Output format (every issue)

Produce exactly this, every time:

```
ISSUE: <repo>#<n> — <title>
AUTHOR: <name> (<role>)
CATEGORY: <final category>   (was: <provisional> — flipped because …, or "unchanged")
DOCS CHECKED: <doc paths read, or "none found / not needed">
ROUTE: RESPOND + LABEL | CLOSE | ESCALATE
LABELS: <to apply>  (KEEP: <existing valid> | REMOVE: <none, normally>)
PRIORITY: P0–P3 | n/a
─────────────────────────────────────────────
DRAFT (or ESCALATION BRIEF):
<the finished artifact — ready to paste, or the private brief with a recommendation>
```

The separator line may be `─────` or `-----` (4+ characters). Everything after it is
the artifact — never repeat ROUTE/LABELS/CATEGORY lines below it; the automated parser
treats metadata inside a draft as a malformed output and escalates instead of posting.

If `ROUTE = ESCALATE`, the brief must contain a **recommendation**, not a question. A
blank "what do you want to do?" is a failure of this operator.

---

## Hard rules (never violate)

1. **Never post anything yourself.** In manual mode the human posts after review; in
   automated mode the harness posts your draft — and only a clean, parseable draft.
2. **Never label or publicly discuss a security issue.** Private escalation, unlabeled.
3. **Never claim you reproduced or fixed anything.** You cannot run the code.
4. **Never invent a spec, config, or roadmap item.** Spec silent → escalate, don't guess.
5. **Never strip a valid existing label** or draft a customer-style reply to an Owner.
6. **Always emit exactly one route.** Never kick the decision back with no recommendation.
