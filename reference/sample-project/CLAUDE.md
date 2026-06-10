# CLAUDE.md — Log_breakdown

> This file is the project's sitemap. The RepoRouter operator reads it first (Step 0) to
> learn where authoritative docs live, so it never has to guess the layout.

**Log_breakdown** (`logbd`) is a Python CLI that ingests log files and prints a structured
breakdown: counts by level, top error messages, and an events-over-time histogram.

## Where the ground truth lives

- **What it does / how it parses:** `docs/spec-overview.md`, `docs/spec-parsing.md`
- **What it deliberately won't do:** `docs/non-goals.md`
- **What's planned:** `docs/roadmap.md`
- **What shipped when:** `CHANGELOG.md`
- **What's already filed:** `open-issues.md` (snapshot of open issues)
- **User-facing docs:** `README.md`

## Quick facts (authoritative summaries — verify against the docs above)

- Supported input: uncompressed plain-text logs, JSON-lines, syslog (RFC 3164), and stdin.
- Timestamps are normalized to **UTC by design** (see non-goals).
- Supported platforms: Linux and macOS. Windows is best-effort, **unsupported**.
- Python 3.10+.
- Current release: **v0.3.1**.
