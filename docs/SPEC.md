# RepoRouter — Technical Specification

Version 0.2. Covers the automated triage pipeline, the chat interface, the LLM contract,
and the GitHub integration. The decision logic lives in `rules.md`; this document covers
the system that executes it.

---

## 1. Overview

RepoRouter is a two-mode automated GitHub issue operator.

**Automated mode** (`triage.py`) — fetches every open issue the operator account has not
yet commented on, runs each through the triage pipeline, and posts the result (labels,
reply, close) to GitHub. Writes escalations to `followup.md` for human review.

**Manual mode** (`chat.py`) — a browser-based Flask interface where a maintainer pastes
an individual issue (or points at a repo) and receives a triage decision in real time.
Draft only — nothing is posted.

Both modes share the same pipeline, LLM backends, and operator files. `chat.py` imports
`triage.py`; no logic is duplicated.

---

## 2. File layout

```
RepoRouter/
├── triage.py               Core pipeline + CLI entry point
├── chat.py                 Browser interface (Flask + SSE)
├── requirements.txt        Python dependencies
├── .env.example            Credential template
├── identity.md             Operator scope and limits
├── rules.md                Seven-step decision pipeline (the heart)
├── examples.md             Five worked decisions against the sample project
├── followup.md             Written each run — escalations requiring human action
└── reference/
    ├── label-taxonomy.md   Routing → GitHub's nine standard labels
    ├── triage-rubric.md    P0–P3 priority scoring for confirmed bugs
    ├── response-templates.md  Draft scaffolds per route
    ├── security-handling.md   Absolute rules for vulnerability reports
    └── sample-project/     Demo repo (Log_breakdown) for immediate testing
```

Operator files (`identity.md`, `rules.md`, all `reference/*.md`) are read once at process
startup using `Path(__file__).parent` — no hardcoded paths, works wherever the folder lives.

---

## 3. Triage pipeline

The pipeline is defined in `rules.md` and executed once per issue.

| Step | Name | What happens |
|------|------|--------------|
| 0 | Orient | Discover the target repo's documentation surface (map → convention dirs → glob fallback). Build a mental index; do not read full docs yet. |
| 1 | Read | Parse the full issue block: author role, body, repro, existing labels, activity log, tone. Branch immediately on author role (Owner/Member/Collaborator = internal item). |
| 2 | Categorize | Provisional primary category: security, hostile, noise, spam, duplicate, bug, feature, question, docs. Higher row in the table wins ties. |
| 3 | Short-circuit | Security and hostile exit immediately to ESCALATE. Spam exits to CLOSE. Noise exits with no action. No doc lookup for any of these. |
| 4 | Fetch docs | Pull only the docs relevant to this issue (not the whole repo). Always check CHANGELOG for "already fixed?" and roadmap/open-issues for "already tracked?". |
| 5 | Confirm or flip | Re-test the Step 2 category against the docs. The doc check may overturn the first read. Route to exactly one of RESPOND+LABEL, CLOSE, or ESCALATE. |
| 6 | Priority | For confirmed bugs only: P0–P3 per `reference/triage-rubric.md`. Regressions bump one level. |
| 7 | Output | Emit the structured output block (ISSUE, AUTHOR, CATEGORY, DOCS CHECKED, ROUTE, LABELS, PRIORITY, DRAFT or ESCALATION BRIEF). |

---

## 4. Routes

Exactly one route is assigned per issue. No partial routes, no "maybe."

### RESPOND + LABEL
Post a public comment and apply labels. Used for: confirmed bugs, answerable questions,
valid docs gaps, in-scope feature requests.

### CLOSE
Post a closing comment, apply labels, and close the issue. Used for: duplicates,
works-as-designed, spam, out-of-scope requests.

### ESCALATE
Write a private brief to `followup.md` — not posted to GitHub. Used for: security reports,
roadmap-level decisions, hostile threads, anything the docs cannot resolve. Every escalation
brief ends with a **recommendation**, never a blank question.

---

## 5. Output format

Every triage decision, whether posted or escalated, uses this format:

```
ISSUE: <repo>#<n> — <title>
AUTHOR: <name> (<role>)
CATEGORY: <final>   (was: <provisional> — flipped because …, or "unchanged")
DOCS CHECKED: <paths read, or "none found / not needed">
ROUTE: RESPOND + LABEL | CLOSE | ESCALATE
LABELS: <to apply>  (KEEP: <existing valid> | REMOVE: <none, normally>)
PRIORITY: P0–P3 | n/a
─────────────────────────────────────────────
DRAFT (or ESCALATION BRIEF):
<finished artifact>
```

The separator line (`─────`) is used by `parse_output()` to split metadata from the draft.

---

## 6. LLM backends

### Anthropic
Uses the `anthropic` Python SDK. Requires `ANTHROPIC_API_KEY` in the environment.
Default model: `claude-sonnet-4-6`. Override with `--model`.

### Ollama
Uses the Ollama REST API (`POST /api/chat`). Requires a running Ollama instance.
Default host: `http://localhost:11434`. Override with `--ollama-host`.
Default model for this deployment: `gemma4:e2b`.

Both backends receive the same system prompt and user message. The system prompt contains
`identity.md`, `rules.md`, all `reference/` files, and the target repo's discovered docs.
The user message is the formatted issue block prefixed with "Triage this:".

`max_tokens` is set to 2048. The structured output format is enforced by the system prompt,
not by function calling or JSON mode.

---

## 7. GitHub integration

### Authentication
`GITHUB_TOKEN` is read from the environment via `os.environ`. The token requires:
- `repo` scope: read issues, write comments, apply labels, close issues.

In GitHub Actions, `GITHUB_TOKEN` is the auto-injected Actions token with `issues: write`
and `contents: read` permissions — no personal access token needed.

### Issue selection
`run_triage()` fetches all open issues (excluding pull requests) and filters to those
where the authenticated account has not yet commented. This prevents double-triaging.

### Label management
`_ensure_labels()` creates any label that does not already exist in the repo, using
colors from `_LABEL_COLORS` (GitHub's nine standard defaults) before applying them.
Existing labels on an issue are validated and kept; RepoRouter does not silently strip them.

### Dry run
`--dry-run` runs the full pipeline (LLM call, parse, log output) but skips all GitHub
writes: no comment, no label, no close. `followup.md` is still written.

---

## 8. `followup.md`

Written to the same directory as `triage.py` after every run, overwriting the previous file.
Contains: repo name, timestamp, run mode, and one section per escalation with the issue URL,
author, and the full triage output block.

If there are no escalations, the file records "No escalations this run" so the maintainer
does not wonder if it was skipped.

`followup.md` is listed in `.gitignore` and is not committed to version control.

---

## 9. GitHub Actions deployment

`triage.yml` runs on `ubuntu-latest` with `issues: write` permissions. On each trigger it:

1. Checks out the repo
2. Installs Python 3.11 and `requirements.txt`
3. Installs Ollama via the official install script
4. Starts `ollama serve` in the background, waits 5 seconds, pulls `gemma4:e2b`
5. Runs `python triage.py <repo>` with the auto-injected `GITHUB_TOKEN`

No external secrets are required. `ANTHROPIC_API_KEY` is not used in this deployment.

---

## 10. Hard constraints (never violated by design)

1. **Never post without a human decision path.** Automated mode posts only after the LLM
   decision; manual mode drafts only.
2. **Never label or discuss a security issue publicly.** Security reports exit before any
   doc lookup, are escalated privately, and are deliberately left unlabeled.
3. **Never claim reproduction or fix.** The operator cannot run code. It checks consistency
   with docs, not execution.
4. **Never invent a spec or config item.** If the docs are silent, the call escalates.
5. **Never strip a valid existing label** without an explicit documented reason in the output.
6. **Always emit exactly one route.** No "it could be either" outputs.
