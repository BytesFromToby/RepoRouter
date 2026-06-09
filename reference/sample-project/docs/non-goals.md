# Non-goals (what Log_breakdown will NOT do)

These are deliberate scope boundaries. Feature requests that contradict this list are
declined (`enhancement` + `wontfix`), not deferred.

- **No timezone localization.** All timestamps are normalized to and displayed in **UTC**,
  always. Showing logs in local time is explicitly out of scope — UTC is the contract so
  that breakdowns from machines in different zones line up. Requests for `--local` or
  per-zone display are declined.
- **No real-time alerting.** `logbd` analyzes logs you give it; it does not watch, alert,
  page, or notify. (Live tailing via `--follow` is a separate, planned read feature — see
  roadmap — but alerting on top of it is not.)
- **No log shipping or storage.** It does not forward, upload, or persist logs to any
  backend. It reads, breaks down, and exits.
- **No GUI / web server.** CLI only. (Static HTML *report output* is on the roadmap; a
  running web UI is not.)
- **No write-back.** `logbd` never modifies the input log files.
