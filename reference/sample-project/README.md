# Log_breakdown

`logbd` — a small CLI that turns a wall of logs into a readable breakdown.

```bash
pip install log-breakdown
logbd server.log
```

## What you get

```
$ logbd server.log
LEVELS    ERROR 412   WARN 1,033   INFO 18,247
TOP ERRORS
  1. connection reset by peer            188
  2. timeout waiting for upstream         97
TIMELINE  (hourly)  ▁▂▃▅█▅▃▂
```

## Usage

```bash
logbd app.log                 # default table output
logbd app.log --json          # machine-readable
logbd app.log --csv           # spreadsheet-friendly
logbd app.log --level ERROR   # filter by level
logbd app.log --since 14:00 --until 15:00
cat app.log | logbd -         # read from stdin
```

## Supported formats

Plain-text line logs, JSON-lines, and syslog. Pass `--format` to force one; otherwise
`logbd` auto-detects.

## Requirements

Python 3.10+. Works on Linux and macOS.

---

> NOTE: This README is intentionally a little out of date — it's the target of the sample
> issue #1 ("README is stale") used in the operator's `examples.md`. Compare its claims to
> `CHANGELOG.md` and `docs/` and you'll find the drift the operator is meant to catch.
