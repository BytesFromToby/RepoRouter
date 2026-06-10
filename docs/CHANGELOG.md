# Changelog

All notable changes to RepoRouter are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.3.0] — 2026-06-10

Hardening release: rebuilt for safe operation on small local models.

### Changed
- **Two-phase pipeline** — a small categorize call, then a decision call carrying only
  the docs relevant to that category (was: one monolithic prompt with every doc and
  reference file). `triage-rubric.md` is included only for bugs; `identity.md` is no
  longer sent at all.
- **Doc discovery rewritten** — lists the repo root and `docs/` and matches names
  case-insensitively (was: a hardcoded lowercase candidate list that missed
  `docs/SPEC.md` — the operator triaged its own repo nearly doc-blind).
- **Labels are now additive** (`add_to_labels`) — existing labels are never stripped
  (was: `set_labels`, which replaced them, violating hard rule 5 on every triage).
- **Author role is real** — `author_association` is read per issue (was: every author
  hardcoded as "external", which made rules.md's Owner/internal branch dead code).
- `chat.py` repo mode now calls `run_triage()` directly — the duplicated (and buggy)
  posting loop is gone.
- `rules.md` and `identity.md` are mode-aware: "never post" now correctly describes
  who posts in manual vs automated mode, instead of contradicting the harness.
- Default Ollama model unified to `qwen3:8b` everywhere (was: three different names
  across README/SPEC/code, one of them a non-pullable local tag).

### Added
- **Harness guardrails** (`validate_decision`) — security/hostile issues are
  short-circuited in code and can never take a public route; spam closes with a canned
  reply; unparseable routes, missing drafts, and drafts containing pipeline metadata
  all escalate instead of posting. Every override logs its reason.
- **`<think>` stripping** — chain-of-thought (including unclosed tags) can never reach
  a posted comment. Previously a parse failure posted the raw model output publicly.
- **Label whitelist** — only GitHub's nine standard labels can be applied; invented
  labels are dropped, never created.
- `.github/workflows/triage.yml` — the self-triage workflow, actually committed this
  time (see 0.2.0 note). Escalations surface in the run step summary and as an artifact.
- `tests/` — 34 pytest tests pinning the parser, validators, and guardrails.
- Actions compatibility: `BOT_LOGIN` fallback (the Actions token has no `/user`
  endpoint), retry with backoff on GitHub write rate limits.
- Ollama health check at startup; `--issue N` and `--since YYYY-MM-DD` flags.
- Per-issue JSON logs now record the guardrail reason and author role.

---

## [0.2.0] — 2026-06-09

### Changed
- Renamed project from The Maintainer to **RepoRouter**
- All path references in README updated to `RepoRouter/`
- Default LLM provider switched from Anthropic to **Ollama** (`gemma4:e2b`)
- `ANTHROPIC_API_KEY` is no longer required for the default configuration

### Added
- `.gitignore` — blocks `.env`, `__pycache__/`, `followup.md`, and build artifacts from being committed
- `.github/workflows/triage.yml` — GitHub Actions workflow for self-hosted triage
  *(correction: this entry was written but the workflow file was never committed —
  it actually ships in 0.3.0)*
- `docs/` folder with `CHANGELOG.md`, `ROADMAP.md`, and `SPEC.md`
- `.env.example` committed as a credential template

---

## [0.1.0] — 2026-06-08

### Added
- `triage.py` — core triage pipeline and CLI runner
  - Reads `identity.md`, `rules.md`, and all `reference/` files at startup
  - Discovers repo documentation at runtime via `get_repo_docs()`
  - Skips issues already commented on by the authenticated account
  - `--dry-run` flag previews decisions without touching GitHub
  - `--provider` and `--model` flags for Anthropic or Ollama backends
  - Writes `followup.md` with any escalations each run
- `chat.py` — browser-based chat interface (Flask, SSE) for manual and live triage
  - Sidebar model/provider switcher; Ollama model list auto-discovered
  - Live progress stream during automated repo triage
- `identity.md` — operator identity: scope, inputs, the three output routes, hard limits
- `rules.md` — seven-step decision pipeline (orient, read, categorize, short-circuit, fetch docs, confirm/flip, output)
- `examples.md` — five worked decisions against the sample project, including edge cases
- `reference/label-taxonomy.md` — routing to GitHub's nine standard labels
- `reference/triage-rubric.md` — P0–P3 priority scoring for confirmed bugs
- `reference/response-templates.md` — voice-matched draft scaffolds per route
- `reference/security-handling.md` — absolute rules for vulnerability reports
- `reference/sample-project/` — a complete demo repo (Log_breakdown) for immediate testing
