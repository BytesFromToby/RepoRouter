# examples.md

Five worked decisions, run against the sample project in `reference/sample-project/`
(Log_breakdown). Each shows the full pipeline and the operator's output. At least two are
edge cases the obvious rules don't cover (Example 2 flips category after the doc check;
Example 4 is a security report filed in the open).

Paste format the operator expects: the **whole** GitHub issue block — author + role,
body, existing labels, activity.

---

## Example 1 — Owner-filed, vague docs note (the dogfood case)

**Input**
```
BytesFromToby (Owner) opened 2 hours ago
There are some things that are not current in the readme. need to update
Labels: documentation
Activity: BytesFromToby added documentation 2 hours ago
```

**Pipeline**
- Step 1 — Author role: **Owner** → internal item, no external "thanks for reporting" reply.
- Step 2 — Provisional category: **docs**.
- Step 3 — Not cheap/dangerous; continue.
- Step 4 — Relevant docs: `README.md` vs `CHANGELOG.md` + `docs/`. The body is vague, so
  instead of asking "which parts?", diff the README against ground truth.
- Step 5d — Owner-filed + vague → internal note. Found drift: README shows a `WARN 1,033`
  example but still describes pre-v0.3.0 level names; README lists only three formats and
  omits syslog (added v0.3.0); README doesn't mention `--csv` (added v0.3.0). Keep
  `documentation`. Do not close.

**Output**
```
ISSUE: Log_breakdown#1 — README is out of date, needs update
AUTHOR: BytesFromToby (Owner)
CATEGORY: docs (unchanged)
DOCS CHECKED: README.md, CHANGELOG.md, docs/spec-parsing.md
ROUTE: RESPOND + LABEL  (internal note — author is Owner)
LABELS: KEEP documentation
PRIORITY: n/a
─────────────────────────────────────────────
INTERNAL NOTE (not a public reply):
README diff vs CHANGELOG/spec — likely-stale spots:
  • "Supported formats" lists plain-text + JSON-lines only; syslog shipped in v0.3.0.
  • No mention of `--csv` (added v0.3.0).
  • Level examples predate the v0.3.0 uppercase+synonym normalization.
Confirm this list and I'll draft the README patch. Keeping `documentation`. Not closing.
```
*Why it matters: the operator branches on the Owner role (no customer-style reply) and
does the work — it finds the staleness instead of handing the question back.*

---

## Example 2 — "Bug" that isn't a bug (category flip) ⟵ edge case

**Input**
```
dmitri-k (Contributor) opened 1 day ago
logbd crashes on my .gz logs. Ran `logbd access.log.gz` and got a UnicodeDecodeError
instead of a breakdown. This is clearly broken.
Labels: (none)
```

**Pipeline**
- Step 1 — External author. Repro present (exact command, error).
- Step 2 — Provisional category: **bug** (user says "crashes / broken").
- Step 3 — Continue.
- Step 4 — Read `spec-overview.md` (input must be uncompressed in v0.3.x), `roadmap.md`
  (gzip is planned v0.4), `open-issues.md` (#7 already tracks gzip).
- Step 5a → **flip**. The crash is not a defect: reading `.gz` is explicitly not supported
  yet, and feeding compressed bytes to the UTF-8 reader producing a decode error is
  expected, not contractual breakage. This is a **feature request already on the roadmap**
  and a **duplicate of #7**. Reclassify feature/duplicate.

**Output**
```
ISSUE: Log_breakdown#— logbd crashes on .gz logs
AUTHOR: dmitri-k (Contributor)
CATEGORY: feature/duplicate (was: bug — flipped: .gz is unsupported in v0.3.x and planned in v0.4; dup of #7)
DOCS CHECKED: docs/spec-overview.md, docs/roadmap.md, open-issues.md
ROUTE: CLOSE
LABELS: enhancement, duplicate
PRIORITY: n/a
─────────────────────────────────────────────
DRAFT (public reply):
Thanks for trying this! Compressed input isn't supported yet in v0.3.x — `logbd` expects
uncompressed logs, so a `.gz` file lands in the UTF-8 reader and errors out (rough, agreed
— a clean "unsupported format" message would be better). Good news: gzip support is the #1
roadmap item for v0.4, tracked in #7. Closing this as a duplicate of #7 so it stays in one
place — follow along there. For now: `gunzip -c access.log.gz | logbd -` works today.
─────────────────────────────────────────────
INTERNAL: worth a P3 follow-up to emit a friendly "compressed input not supported" error
instead of a raw UnicodeDecodeError. Recommend filing as good first issue.
```
*Why it matters: the provisional "bug" was overturned by the docs. A naive triager labels
this `bug` and sends it to the fix queue; the operator catches that it's a known,
scoped-out feature and closes it correctly — while still spotting the real (separate) UX
paper-cut.*

---

## Example 3 — Works as designed

**Input**
```
lena-ops (none) opened 3 hours ago
Bug: all my timestamps are off. Logs are from a server in Berlin but logbd shows everything
in UTC. Expected local time. Please fix.
Labels: bug
```

**Pipeline**
- Step 1 — External. Clear repro (UTC vs local).
- Step 2 — Provisional: **bug**.
- Step 4 — `docs/non-goals.md`: UTC normalization is intentional and fixed; local-time
  display is explicitly out of scope.
- Step 5a → flip to **works-as-designed**. Reasonable expectation, but it's a stated
  non-goal. The existing `bug` label is wrong → replace with `invalid`. Expectation was
  reasonable → recommend a docs follow-up.

**Output**
```
ISSUE: Log_breakdown#— timestamps shown in UTC, expected local
AUTHOR: lena-ops (external)
CATEGORY: works-as-designed (was: bug)
DOCS CHECKED: docs/non-goals.md, docs/spec-overview.md
ROUTE: CLOSE
LABELS: invalid   (REMOVE: bug — incorrect)
PRIORITY: n/a
─────────────────────────────────────────────
DRAFT (public reply):
Reasonable thing to expect, but this one's intentional: `logbd` normalizes every timestamp
to UTC on purpose so breakdowns from servers in different zones line up. Local-time display
is a deliberate non-goal (docs/non-goals.md). For Berlin logs you can shift the display
downstream, e.g. pipe `--json` into your own formatter. Closing as `invalid` (our label for
"not a defect"), but I hear you that it's surprising.
─────────────────────────────────────────────
INTERNAL: expectation was reasonable → recommend a `documentation` note in the README
"timestamps are always UTC" so the next person doesn't file this. (Removed the `bug` label
the reporter self-applied.)
```
*Why it matters: shows the operator overriding an incorrect user-applied label and pairing
a decline with a docs recommendation rather than just bouncing the user.*

---

## Example 4 — Security report, filed in public ⟵ edge case

**Input**
```
sec-researcher-9 (none) opened 20 minutes ago
Heads up: `logbd --pattern` with a crafted pattern plus the multi-file glob lets you make
logbd open and dump files outside the target dir. Looks like a path traversal. Here's a PoC:
[steps redacted in this example]
Labels: (none)
```

**Pipeline**
- Step 1 — External. Body posts a working PoC.
- Step 2 — Provisional: **security** (path traversal, "PoC", file disclosure).
- Step 3 — **Short-circuit. Stop.** No doc lookup, no public reply, no label. Already
  public → time-sensitive.

**Output**
```
ISSUE: Log_breakdown#— possible path traversal via --pattern + glob
AUTHOR: sec-researcher-9 (external)
CATEGORY: security
DOCS CHECKED: none (security short-circuits before doc lookup)
ROUTE: ESCALATE (private)
LABELS: none — deliberately unlabeled (a label advertises the hole)
PRIORITY: n/a (escalated)
─────────────────────────────────────────────
ESCALATION BRIEF (private — DO NOT POST):
**SECURITY — handle privately. TIME-SENSITIVE: already public.**
Claim: path traversal / arbitrary file read via crafted `--pattern` + multi-file glob; a
PoC is already posted in the open issue.
Exposure: the report and PoC are PUBLIC right now. Clock is running.
Recommendation:
  1. Triage the PoC privately and patch on an accelerated timeline if it reproduces.
  2. Move discussion to a GitHub Security Advisory; consider requesting a CVE.
  3. The project has no SECURITY.md — recommend adding one.
Suggested private reply to reporter:
  "Thanks for the report and for the detail. Moving this to a private advisory so we can
   fix before it spreads — invited you there. Really appreciate it."
I did NOT post anything, label anything, or confirm/deny the issue publicly.
```
*Why it matters: the one path where a wrong move causes real harm. The operator refuses to
label or reply in public, and flags the already-public PoC as time-sensitive instead of
quietly closing it.*

---

## Example 5 — Frustrated tone, valid regression (tone ≠ hostile)

**Input**
```
mara-87 (none) opened 5 hours ago
Third release in a row something breaks. `--csv` now prints a header twice on every run
since I upgraded to 0.3.1. It worked fine in 0.3.0. Getting tired of this.
Labels: (none)
```

**Pipeline**
- Step 1 — External. Frustrated, but **not hostile** (no abuse/threats) → do not escalate
  for tone; handle the technical merit. Repro is sufficient (exact symptom, versions).
- Step 2 — Provisional: **bug**.
- Step 4 — `CHANGELOG.md`: `--csv` shipped v0.3.0, worked then; broke at 0.3.1 →
  **regression**. `open-issues.md`: no existing dupe.
- Step 5a — confirmed defect (duplicated CSV header contradicts intended single-header
  output). Step 6 — base severity P2 (cosmetic-ish, easy workaround) **+1 for regression →
  P1**.

**Output**
```
ISSUE: Log_breakdown#— --csv prints header twice since 0.3.1 (regression)
AUTHOR: mara-87 (external)
CATEGORY: bug (unchanged)
DOCS CHECKED: CHANGELOG.md, open-issues.md
ROUTE: RESPOND + LABEL
LABELS: bug
PRIORITY: P1 (P2 base, +1 regression — worked in 0.3.0)
─────────────────────────────────────────────
DRAFT (public reply):
Thanks for the precise report — and sorry for the churn. You're right: `--csv` worked in
0.3.0 and the doubled header is new in 0.3.1, so this is a regression on us. Labeling `bug`
and bumping its priority since it's a regression. Quick unblock until the fix ships: pipe
through `tail -n +2` to drop the extra header. We'll get this out in a patch.
─────────────────────────────────────────────
INTERNAL: regression introduced 0.3.0→0.3.1; likely the CSV writer emitting the header on
both init and first row. P1.
```
*Why it matters: separates **tone** from **merit**. A naive rule might escalate anything
that sounds annoyed; the operator notes the frustration, declines to escalate (it's not
abuse), and handles the real, upgraded-priority regression underneath it.*
