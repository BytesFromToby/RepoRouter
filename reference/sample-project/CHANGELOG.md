# Changelog

## v0.3.1 — current
- Fixed: crash on empty input files; now exits 0 with an empty breakdown.
- Fixed: JSON-lines parser dropped the final line when the file had no trailing newline.
- Fixed: `--since`/`--until` off-by-one at exact minute boundaries.

## v0.3.0
- Added: syslog (RFC 3164) parser with year inference from file mtime.
- Added: `--csv` output.
- Changed: levels now normalized uppercase with synonym mapping (`WARNING→WARN`, etc.).

## v0.2.0
- Added: JSON-lines format support.
- Added: `--since` / `--until` time filters.
- Added: stdin input via `-`.

## v0.1.0
- Initial release: plain-text parsing, level counts, top errors, hourly timeline, table
  and `--json` output.
