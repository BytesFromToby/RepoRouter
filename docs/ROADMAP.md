# Roadmap

Priority order within each milestone. Items marked **[stretch]** ship only if the core is solid.

---

## v0.3 — Reliability & Observability

The self-triage workflow has run against this repo's real issues. This milestone hardens the
runtime so the operator fails gracefully and leaves a clear audit trail.

- **Structured run log** — append a machine-readable JSON line per issue to `triage-log.jsonl`
  (issue number, route, labels, priority, timestamp, model). Lets maintainers review decisions
  in bulk and spot drift over time.
- **Rate-limit handling** — catch GitHub API 403/429 responses and retry with backoff rather
  than crashing mid-run and leaving issues half-processed.
- **Ollama health check at startup** — fail fast with a clear error if the Ollama host is
  unreachable, rather than surfacing a confusing requests exception mid-triage.
- **`followup.md` diff** — on each run, show which escalations are new vs. carried over from
  the previous run so the maintainer isn't re-reading the same brief twice.
- **`--since` flag** — triage only issues opened after a given date, for repos with a large
  backlog of pre-existing issues.
- **[stretch]** `--issue N` flag — triage a single issue by number, useful for testing and
  for re-running a failed triage.

---

## v0.4 — GitHub App (drop the PAT)

Personal access tokens are a long-lived credential scoped to a user account. A GitHub App
is a first-class installation credential scoped to exactly the repos it's installed on,
with short-lived tokens that rotate automatically.

- **GitHub App authentication** — support `APP_ID` + private key as an alternative to
  `GITHUB_TOKEN`. The triage loop picks whichever credential is present.
- **Installation-level operation** — one App installation can triage multiple repos in a
  single run without separate tokens per repo.
- **Webhook trigger** — register the App webhook so triage fires in real time on
  `issues.opened` rather than on a polling cron, reducing median response latency from
  ~15 minutes to seconds.
- **[stretch]** App marketplace listing so any maintainer can install RepoRouter on their
  repo without cloning it.

---

## v0.5 — Multi-repo & Configuration

- **Multi-repo config file** — a `repos.yml` listing repos, per-repo model overrides,
  and per-repo label customizations. One `triage.py` invocation processes the whole list.
- **Per-repo operator overrides** — drop a `reporouter.yml` into a target repo to override
  the default label taxonomy, priority thresholds, or response tone without touching the
  core reference files.
- **`--report` flag** — print a triage summary (counts by route, labels applied, escalations)
  after each run, suitable for posting as a GitHub issue comment or a status update.
- **[stretch]** Slack/Discord webhook for escalation notifications — send a message when
  `followup.md` has new items, so the maintainer doesn't have to remember to check the file.

---

## Longer term (unscheduled)

- **Regression detection** — cross-reference new bug reports against recent CHANGELOG entries
  and flag likely regressions automatically before the maintainer has to check.
- **Duplicate clustering** — use embedding similarity to detect near-duplicate issues that
  don't reference each other by number (the current approach only catches explicit links and
  textual overlaps).
- **Human-in-the-loop mode** — post the triage decision as a draft comment visible only to
  collaborators for one-click approve/edit/reject, rather than posting directly.
- **Test harness** — a `pytest` suite that runs the full pipeline against the sample project
  issues and asserts expected routes, so regressions in the decision logic are caught before
  they reach a real repo.

---

## Non-goals (will not be built)

- **Code execution** — RepoRouter will never run, build, or test code. It triages; it does
  not fix.
- **PR review** — pull request review is a different problem with different ground truth and
  different risk. Out of scope.
- **Multi-LLM ensemble / voting** — complexity without proven accuracy gain for this use case.
- **Hosted SaaS** — RepoRouter is designed to be self-hosted. A multi-tenant hosted version
  is not planned.
