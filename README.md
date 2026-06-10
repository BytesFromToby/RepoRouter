# RepoRouter

**An AI operator that triages GitHub issues end-to-end.** Point it at a repo and it fetches every new issue, makes the call, and posts the result — labeled reply, close, or private escalation — checking each issue against the project's own docs first. It decides and acts. It does not hand the question back.

Three ways to run it: **self-hosted on GitHub Actions** (the repo triages its own issues automatically), **local CLI** (`triage.py`), or **manual** (paste an issue into the browser UI for a one-off draft).

# It is running on this Repo right now!

It is checking for issues on this repo every 10 minutes.  This readme and other docs are "Not Great" on purpose.  Report issues even if they are little or fake. This is part of demoing the repo and also improving it.  


## How it works

```
full issue ─► categorize ─► (security/spam/noise short-circuit) ─►
    fetch only the relevant docs ─► confirm-or-flip ─► ONE of:
        RESPOND + LABEL  ·  CLOSE  ·  ESCALATE (private, with a recommendation)
```

Every issue gets: a final category, which docs were checked, a route, labels (respecting any already there), a priority for confirmed bugs, and a finished draft — or a private escalation brief that ends with a recommendation, never a blank question.

---

## Quickstart — Self-hosting on GitHub Actions

The workflow is already included. RepoRouter triages issues filed against itself automatically — no setup beyond enabling Actions.

**Ollama (default)** — no secrets needed. The workflow installs Ollama on the runner and pulls `qwen3:8b` at runtime.

**Anthropic (alternative)** — add `ANTHROPIC_API_KEY` under Settings → Secrets and variables → Actions, then change the `run` line in `.github/workflows/triage.yml` to remove `--provider ollama --model qwen3:8b`.

`GITHUB_TOKEN` is injected automatically — you never set it manually.

Open an issue to test it. The workflow fires on `issues: opened` and on a 30-minute cron — check the Actions tab to watch it run.

---

## Quickstart — Local CLI

**Step 1 — Install dependencies.**

```bash
pip install -r requirements.txt
```

**Step 2 — Set credentials.**

```bash
# Ollama (default — requires a running Ollama instance)
export GITHUB_TOKEN=ghp_...

# Anthropic (alternative)
export GITHUB_TOKEN=ghp_...
export ANTHROPIC_API_KEY=sk-ant-...
```

Or copy `.env.example` to `.env` and fill in your values.

**Step 3 — Run.**

```bash
# CLI
python triage.py owner/your-repo

# CLI with Ollama (default model: qwen3:8b)
python triage.py owner/your-repo --provider ollama --model qwen3:8b

# Browser UI — then open http://localhost:5000
python chat.py
```

**Preview before posting** — add `--dry-run` to see every decision without touching GitHub.

Each run:
- Finds every open issue the operator account hasn't commented on yet
- Runs each through the full triage pipeline (reads your repo's own docs first)
- Posts labels, replies, and closes issues as appropriate
- Writes `followup.md` with any escalations that need your decision

---

## Quickstart — Manual mode (one-off drafts)

Use this to triage a single issue in any AI chat session without running any code.

**Step 1 — Orient the model.** Paste this prompt once at the start of a session:

```text
You are RepoRouter, an issue-triage operator. Read identity.md and rules.md and follow
them exactly. Locate this repo's docs (spec, roadmap, changelog, README) so you have
ground truth to check against. When I paste a GitHub issue, run it through your pipeline
and return ONE decision — respond+label, close, or escalate — with the labels and a
finished draft. Draft only; never post. Reply "ready" and I'll paste the first issue.
```

If your repo has a `CLAUDE.md`, add this block to it instead so the operator loads automatically:

```markdown
## Issue triage — RepoRouter
When I paste a GitHub issue (or say "triage this"), act as the operator in `RepoRouter/`:
read `identity.md` and `rules.md`, then run the issue through the pipeline.
Check claims against this repo's own docs. Draft only — never post.
```

**Step 2 — Triage.** Paste a GitHub issue — **the whole block**, not just the title (author, role, body, existing labels, activity log). Say *"triage this."* You get back one decision, ready to act on.

---

## What makes it trustworthy

- **It checks against your docs, not vibes.** A "bug" that the spec says is intended gets closed correctly; a feature on the roadmap gets the right holding reply.
- **It branches on author role.** An issue filed by the `Owner` is treated as an internal note, not answered like an external ticket.
- **It never guesses.** If the docs are silent on the behavior, it escalates with the open question spelled out instead of inventing a spec citation.
- **It handles security safely.** Security reports are escalated privately and **unlabeled** — never confirmed, discussed, or tagged in public. See `reference/security-handling.md`.
- **It drafts, never posts unreviewed.** Safe to run unattended; you review and click.

---

## What's in the repo

```
RepoRouter/
├── triage.py              Core pipeline + CLI runner (also imported by chat.py)
├── chat.py                Browser UI — paste issues or triage a repo live
├── requirements.txt       Python deps (anthropic, PyGithub, flask, requests)
├── .env.example           Credential template (copy to .env, never commit it)
├── identity.md            Operator scope and limits
├── rules.md               The decision pipeline — the heart
├── examples.md            Five worked decisions, including edge cases
├── followup.md            Written each run — escalations needing a human decision (auto-created, gitignored)
├── docs/
│   ├── SPEC.md            Full technical specification
│   ├── ROADMAP.md         Planned milestones and non-goals
│   └── CHANGELOG.md       Version history
└── reference/
    ├── label-taxonomy.md      Routing → GitHub's nine standard labels
    ├── triage-rubric.md       P0–P3 priority scoring for confirmed bugs
    ├── response-templates.md  Voice-matched draft scaffolds per route
    ├── security-handling.md   Absolute rules for vulnerability reports
    └── sample-project/        Demo repo (Log_breakdown) for immediate testing
```

---

## Configure it for your project (optional, ~2 min)

- **Labels** — defaults to GitHub's nine standard labels. Edit `reference/label-taxonomy.md` if yours differ.
- **Priority** — tune the thresholds in `reference/triage-rubric.md` to your project's bar.
- **Voice** — the templates in `reference/response-templates.md` are scaffolds; adjust tone once and every draft follows.
- **Docs map** — if your repo has a `CLAUDE.md` or docs index, the operator finds your docs automatically. Otherwise it falls back to searching `docs/`, `rfcs/`, `CHANGELOG`, and similar conventions.

---

## Limits (by design)

In automated mode it posts replies, applies labels, and closes issues — but it never claims a bug is "reproduced" or "fixed" (it cannot run your code). It is only as good as your docs: if the spec is stale, it escalates uncertain calls to `followup.md` rather than guessing. Security reports are never posted publicly — always escalated privately.

In manual mode it drafts only; you review before touching GitHub.
