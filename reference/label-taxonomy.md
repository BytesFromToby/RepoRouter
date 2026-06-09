# reference/label-taxonomy.md

The operator's label vocabulary is **GitHub's nine default labels** — the set every repo
ships with. Using the defaults (not a custom taxonomy) means the operator works on a
fresh repo with zero setup. If a project has renamed or extended its labels, update the
"project's actual labels" note at the bottom; the decision logic in `rules.md` references
labels by *role*, so remapping names is the only change needed.

## The nine defaults and when to apply each

| Label | GitHub definition | The operator applies it when… |
|---|---|---|
| `bug` | Something isn't working | Repro is sufficient **and** behavior contradicts the spec. A confirmed defect. |
| `documentation` | Improvements or additions to documentation | A doc is missing, wrong, or stale — or a reasonable bug turned out to be a docs gap. |
| `duplicate` | This issue or PR already exists | The issue restates a known/open issue. Always paired with a link to the canonical one. |
| `enhancement` | New feature or request | Any feature request — kept on accept, defer, **and** decline (decline also gets `wontfix`). |
| `good first issue` | Good for newcomers | A confirmed bug that is small, well-scoped, low-risk, and self-contained. Paired with `bug`. |
| `help wanted` | Extra attention is needed | A valid item the maintainer wants external hands on. Applied after triage, not as a verdict. |
| `invalid` | This doesn't seem right | Spam, gibberish, or works-as-designed. Closing label. |
| `question` | Further information is requested | Two uses: (a) a real usage question, (b) a bug with **insufficient repro** — the "needs info" hold. |
| `wontfix` | This will not be worked on | A decided-no: out-of-scope feature or a defect the maintainer won't address. Paired with the category label. |

## Routing → label cheat sheet

| Final decision | Labels |
|---|---|
| Confirmed defect | `bug` (+`good first issue` if tiny) |
| Defect, no repro yet | `question` |
| Works-as-designed | `invalid` (+`documentation` if expectation was reasonable) |
| Feature, on roadmap / accepted | `enhancement` |
| Feature, declined | `enhancement` + `wontfix` |
| Usage question | `question` |
| Docs gap | `documentation` |
| Duplicate | `duplicate` |
| Spam | `invalid` |
| Already fixed in newer version | `question` (ask to upgrade) |

## Deliberately unlabeled: security

There is **no** `security` label in the default set, and the operator does **not** add
one. Publicly labeling an issue "security" advertises an unpatched vulnerability. Security
reports are escalated privately and left unlabeled until the maintainer decides how to
handle disclosure. The absence of a label here is a choice, not an oversight. See
`security-handling.md`.

## Optional additions (only if the project already uses them)

If the host project maintains richer labels, the operator can use them; map them to roles:

- `needs-repro` → use instead of `question` for the no-repro hold.
- `regression` → add when CHANGELOG shows it worked in a prior release.
- `priority: P0–P3` → if the project labels priority rather than tracking it in the body.

Absent these, the operator stays on the nine defaults.

## Project's actual labels

> Default: GitHub's nine standard labels (above). Edit this line if the project's labels
> differ, and the operator will use these instead.
