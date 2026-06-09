# Changelog

All notable changes to RepoRouter are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
  - Triggers on `issues: opened/reopened`, 30-minute cron, and `workflow_dispatch`
  - Installs Ollama and pulls `gemma4:e2b` on the runner
  - Requires only the auto-injected `GITHUB_TOKEN` — no external secrets
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
