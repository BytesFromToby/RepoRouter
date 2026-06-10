# RepoRouter — Technical Specification

Version 0.3.1. Covers the automated triage pipeline, the chat interface, the LLM contract,
and the GitHub integration. The decision logic lives in `rules.md`; this document covers
the system that executes it.

---

## 1. Overview

RepoRouter is a two-mode automated GitHub issue operator.

**Automated mode** (`triage.py`) — fetches every open issue the operator account has not
yet commented on, runs each through the two-phase triage pipeline, validates the model's
output, and posts the result (labels, reply, close) to GitHub. Escalations go to
`GithubIssues/followup.md` — and, under GitHub Actions, to the run's step summary.

**Manual mode** (`chat.py`) — a browser-based Flask interface where a maintainer pastes
an individual issue (or points at a repo) and receives a triage decision in real time.
Paste mode is draft-only; repo mode behaves exactly like the CLI (including `--dry-run`).

Both modes share the same pipeline: `chat.py` imports `triage.py` and calls
`run_triage()` / `triage_issue_text()` — no triage logic is duplicated.

---

## 2. File layout

```
RepoRouter/
├── triage.py               Core pipeline + CLI entry point
├── chat.py                 Browser interface (Flask + SSE)
├── tests/test_triage.py    Pytest suite — parser, validators, guardrails
├── requirements.txt        Python dependencies
├── .env.example            Credential template
├── .github/workflows/      triage.yml — the self-triage workflow
├── identity.md             Operator scope and limits
├── rules.md                The decision pipeline (the heart)
├── examples.md             Five worked decisions against the sample project
├── GithubIssues/           Run output (gitignored):
│   ├── followup.md         Escalations requiring human action
│   └── IssueLog/<n>.json   Per-issue decision record
└── reference/              Label taxonomy, rubric, templates, security rules,
                            sample project
```

Operator files (`identity.md`, `rules.md`, all `reference/*.md`) are read once at process
startup using `Path(__file__).parent` — no hardcoded paths.

---

## 3. Triage pipeline (two-phase)

Designed for small models: two scoped calls instead of one monolithic prompt, with the
dangerous rules enforced by the harness rather than the prompt.

### Phase 1 — categorize (`categorize()`)

A minimal classification prompt (`CATEGORIZE_SYSTEM`, ~30 lines) assigns one category:
`security, hostile, noise, spam, duplicate, bug, feature, question, docs`. Unparseable
output → `unknown` (treated as a full-decision category, never dropped).

### Harness short-circuits (no second call, no model drafting)

| Category | Action | Why the LLM is excluded |
|---|---|---|
| `security` | Private escalation with a canned brief + the original issue. Nothing posted, nothing labeled. | No model output can leak or acknowledge a vulnerability. |
| `hostile`  | Private escalation, canned brief. | Moderation is a human call; no engagement. |
| `spam`     | CLOSE with the canned spam template + `invalid` label. | A canned reply can't be prompt-injected. |
| `noise`    | No action, logged only. | Nothing worth a model call. |

### Phase 2 — decide (`decide` via `build_decide_prompt()`)

For `bug / feature / question / docs / duplicate / unknown`:

1. **Doc selection** — `select_docs()` maps the category to doc kinds
   (bug → spec+changelog+readme; feature → roadmap+scope+open-issues; …),
   capped at `MAX_DOCS` (5), each truncated to `DOC_CHAR_CAP` (6000 chars).
2. **Decision prompt** — operator header + `rules.md` + the scoped reference files
   (`triage-rubric.md` is included only for bugs) + the selected docs + the output
   contract. `identity.md` is not included (persona prose, no decision value).
3. **The model returns** the structured Step 7 block; the parser and validator below
   decide whether it is safe to act on.

### Doc discovery (`discover_docs()`)

One listing pass over the repo root and `docs/` directory, matching file names
case-insensitively against patterns (readme, changelog, roadmap, spec/design/rfc/adr,
non-goals/scope, open-issues, faq, contributing, CLAUDE/AGENTS). This implements
rules.md Step 0 in the harness; Step 4 is `select_docs` + `fetch_docs`.

---

## 4. Output parsing and validation

### `parse_output()` guarantees

- `<think>…</think>` blocks are stripped first; an **unclosed** `<think>` truncates the
  rest of the output (chain-of-thought can never reach a draft).
- `route` ∈ {RESPOND, CLOSE, ESCALATE} or `None`.
- `labels` ⊆ the nine-label whitelist; anything else is dropped, never created.
- `priority` matches `P[0-3]` or is `n/a`.
- The draft is the text after the first separator line (`─`/`-`/`=`/`_` ×4+) or after a
  `DRAFT:` / `ESCALATION BRIEF:` header. **No match → draft is `None` — the parser never
  falls back to raw model output.**
- Never raises.

### `validate_decision()` — the harness disposes

| Condition | Result |
|---|---|
| category is security/hostile | ESCALATE (forced, regardless of model route) |
| no parseable ROUTE | ESCALATE |
| route RESPOND/CLOSE but no draft | ESCALATE |
| draft still contains pipeline metadata (`ROUTE:`, `LABELS:`, …) | ESCALATE |
| otherwise | the model's route stands |

Every forced escalation records its reason (`guardrail`) in the issue log and followup.

---

## 5. Routes

Exactly one route is assigned per issue.

- **RESPOND** — post a public comment, add labels. Confirmed bugs, answerable questions,
  valid docs gaps, already-planned features.
- **CLOSE** — post a closing comment, add labels, close. Duplicates, works-as-designed,
  spam, out-of-scope.
- **ESCALATE** — write a private brief to `GithubIssues/followup.md`; never posted.
  Security, roadmap-level calls, hostile threads, anything the docs cannot resolve,
  and any malformed model output. Every brief ends with a recommendation.

Labels are applied with `issue.add_to_labels()` — **additive**; existing labels are
never stripped (rules.md hard rule 5 is enforced by API choice, not model behavior).

---

## 6. LLM backends

Both phases go through `call_llm()`, temperature 0.

- **Anthropic** — `anthropic` SDK, `ANTHROPIC_API_KEY`, default `claude-sonnet-4-6`,
  `max_tokens` 4096 (512 for the classifier).
- **Ollama** — REST `POST /api/chat`, default host `http://localhost:11434`, default
  model **`qwen3:8b`** (a publicly pullable tag). `check_ollama()` fails fast at startup
  with a clear message if the host is unreachable or the model isn't pulled.

The structured output format is enforced by the prompt **and re-checked by the parser**;
malformed output degrades to escalation, never to a bad post.

---

## 7. GitHub integration

- **Auth** — `GITHUB_TOKEN` (PAT with `repo` scope) or the Actions-injected token.
  The Actions token has no `/user` endpoint, so the operator identity falls back to
  `BOT_LOGIN` (set in the workflow) or `github-actions[bot]`.
- **Issue selection** — open issues, excluding PRs, excluding issues the operator has
  already commented on. `--issue N` and `--since YYYY-MM-DD` narrow the set.
- **Author role** — `author_association` is read per issue and mapped to
  Owner/Member/Collaborator/Contributor/external; rules.md branches on it.
- **Writes** — wrapped in retry with backoff (3 attempts) on 403/429/5xx.
- **Dry run** — full pipeline, no GitHub writes; followup and logs still written.

---

## 8. Run artifacts

- `GithubIssues/followup.md` — escalations with reasons; "no escalations" is recorded
  explicitly. Overwritten each run.
- `GithubIssues/IssueLog/<n>.json` — per-issue record: category, route, labels,
  priority, guardrail reason, draft, model, provider, dry-run flag.
- `GITHUB_STEP_SUMMARY` — under Actions, escalations are appended to the run summary
  page so they are seen without downloading anything; the workflow also uploads
  `followup.md` as an artifact.

---

## 9. GitHub Actions deployment

`.github/workflows/triage.yml` — triggers on `issues: opened/reopened`, a 30-minute
cron, and `workflow_dispatch`; `issues: write` + `contents: read` permissions; a
concurrency group prevents overlapping runs.

Default target is a **self-hosted runner** with Python and Ollama already present
(model pulled once). A commented-out install step supports `ubuntu-latest`. Only the
auto-injected `GITHUB_TOKEN` is required; `--provider anthropic` needs an
`ANTHROPIC_API_KEY` secret instead.

---

## 10. Hard constraints (enforced by the harness, not the prompt)

1. **A parse failure can never publish model output.** No draft → no post → escalate.
2. **Security/hostile issues never take a public route**, whatever the model says.
3. **Labels are whitelisted and additive.** Nothing invented, nothing stripped.
4. **Never claim reproduction or fix.** The operator cannot run code (prompt rule,
   reinforced by templates).
5. **Chain-of-thought is stripped** before any text is parsed or stored as a draft.
6. **Always exactly one route**, with the guardrail reason logged when the harness
   overrode the model.

---

## 11. Tests

`python -m pytest tests/ -q` — 34 tests pinning the deterministic safety layer:
think-stripping (incl. unclosed tags), category parsing, output parsing (separator
variants, missing separators, garbage), label whitelisting, route validation, forced
escalations, internal-metadata detection, doc selection/scoping, and prompt-mode notes.
No network, no LLM, no GitHub.
