# Roadmap

## v0.4 (next)
- **Compressed input** — read `.gz` and `.bz2` log files directly, no manual decompression.
  (This is the #1 requested feature; tracked in issue #7.)
- **`--follow`** — tail mode that streams the breakdown as new lines arrive.

## v0.5
- **Plugin parsers** — drop-in custom format parsers via an entry-point API.
- **HTML report** — `--html report.html` static output (tracked in issue #15).

## Under consideration (not committed)
- Multi-file merge with per-source attribution.
- Configurable top-N for error ranking.

## Explicitly not planned
See `non-goals.md`. Timezone localization, alerting, log shipping, and a web UI are out of
scope regardless of demand.
