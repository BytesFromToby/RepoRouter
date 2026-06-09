# Spec — Parsing

## Formats

### Plain-text
Default pattern expects `TIMESTAMP LEVEL MESSAGE`. Timestamp formats accepted: ISO 8601,
RFC 3339, and `MMM DD HH:MM:SS` (syslog-style). A custom pattern can be supplied with
`--pattern` (named groups `ts`, `level`, `msg`).

### JSON-lines
One JSON object per line. Fields `time`/`timestamp`/`ts` map to timestamp; `level`/`lvl`/
`severity` map to level; `msg`/`message` map to message. Unmapped keys are kept in
`fields`. A line without a trailing newline is still parsed (fixed in v0.3.1).

### syslog (RFC 3164)
Standard priority + timestamp + host + tag + message. Year is inferred from file mtime when
absent (RFC 3164 omits the year).

## Levels

Recognized levels, normalized uppercase: `TRACE, DEBUG, INFO, WARN, ERROR, FATAL`.
Synonyms mapped: `WARNING→WARN`, `ERR→ERROR`, `CRIT/CRITICAL→FATAL`. An unrecognized level
is preserved verbatim and bucketed under `OTHER`.

## Malformed input

Lines that match no parser are skipped and tallied under `parse_errors`. `logbd` never
aborts a run on a single bad line. If **every** line fails to parse, `logbd` prints a
warning suggesting `--format`/`--pattern` and exits 0 with an empty breakdown.

## Encoding

Input is read as UTF-8. Invalid bytes are replaced (not fatal). Non-UTF-8 logs are not
officially supported.
