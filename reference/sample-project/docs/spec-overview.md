# Spec — Overview

`logbd` reads one or more log sources, parses each line into a normalized record, and
emits an aggregate breakdown.

## Pipeline

1. **Input** — a file path, multiple paths, or `-` for stdin. Input must be uncompressed
   in v0.3.x (compressed input is roadmap v0.4 — see `roadmap.md`).
2. **Detect format** — auto-detect among plain-text, JSON-lines, and syslog, unless
   `--format` forces one.
3. **Parse** — each line becomes a record `{timestamp, level, message, fields}`. Parsing
   rules are in `spec-parsing.md`.
4. **Normalize** — timestamps are converted to **UTC**. This is intentional and fixed; see
   `non-goals.md`.
5. **Aggregate** — counts by level, top-N error messages, and an events-over-time
   histogram.
6. **Output** — table (default), `--json`, or `--csv`.

## Filters

`--level`, `--since`, `--until`, `--grep` narrow records before aggregation. Times given to
`--since`/`--until` are interpreted as **UTC**.

## Supported platforms

Linux and macOS are supported and tested. Windows is **best-effort and unsupported**: path
handling and console encoding are known to differ and bugs that reproduce only on Windows
are triaged as `P3` or closed `invalid` unless they also affect a supported platform.

## Exit behavior

A malformed line is skipped and counted under `parse_errors`; it does not abort the run.
An empty file produces an empty breakdown and exit code 0 (as of v0.3.1).
